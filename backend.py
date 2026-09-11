"""
FastAPI backend exposing the YouTube analytics pipeline over HTTP.
Run with: uvicorn backend:app --reload
"""

import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
# NOTE: This disables an HTTPS-only safety check in oauthlib, needed
# only for local development over http://127.0.0.1. This MUST be
# removed once deployed to a real domain, since production OAuth
# should genuinely enforce HTTPS.

import tempfile
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from snowflake.snowpark import Session
from starlette.middleware.sessions import SessionMiddleware
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build as google_build

import joblib

from app_router import route
from auth import SCOPES, CLIENT_SECRET_FILE, TOKEN_DIR

load_dotenv()


def _get_session() -> Session:
    return Session.builder.configs({
        "account":   os.environ["SNOWFLAKE_ACCOUNT"],
        "user":      os.environ["SNOWFLAKE_USER"],
        "password":  os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database":              os.environ["SNOWFLAKE_DATABASE"],
        "schema":                "MODELING",
        "client_session_keep_alive": True,
    }).create()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.session = _get_session()
    app.state.model = joblib.load("model.pkl")
    yield
    app.state.session.close()


REDIRECT_URI = "http://127.0.0.1:8000/oauth/callback"
WEB_CLIENT_SECRET_FILE = "client_secret_web.json"

app = FastAPI(lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET_KEY"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    channel_id: str
    question: str


@app.get("/login")
def login():
    flow = Flow.from_client_secrets_file(
        WEB_CLIENT_SECRET_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    return RedirectResponse(auth_url)


@app.get("/oauth/callback")
def oauth_callback(request: Request):
    flow = Flow.from_client_secrets_file(
        WEB_CLIENT_SECRET_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=str(request.url))
    credentials = flow.credentials

    youtube = google_build("youtube", "v3", credentials=credentials)
    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    channel_id = response["items"][0]["id"]

    TOKEN_DIR.mkdir(exist_ok=True)
    with open(TOKEN_DIR / f"{channel_id}.json", "w") as f:
        f.write(credentials.to_json())

    request.session["channel_id"] = channel_id
    return RedirectResponse("http://127.0.0.1:5500/index.html")


@app.get("/session")
def get_session_info(request: Request):
    return {"channel_id": request.session.get("channel_id")}


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/analytics")
def analytics(channel_id: str, days: int | None = None):
    session = app.state.session

    date_filter = f"AND PUBLISHED_AT >= DATEADD(day, -{days}, CURRENT_DATE())" if days else ""

    kpi = session.sql(f"""
        SELECT COUNT(*) AS TOTAL_VIDEOS,
               AVG(VIEW_COUNT) AS AVG_VIEWS,
               AVG(LIKE_COUNT) AS AVG_LIKES
        FROM RAW.VIDEOS
        WHERE CHANNEL_ID = ? {date_filter}
    """, [channel_id]).collect()[0]

    weekday_rows = session.sql(f"""
        SELECT PUBLISHED_WEEKDAY, AVG(VIEW_COUNT) AS AVG_LIFETIME_VIEWS
        FROM RAW.VIDEOS
        WHERE CHANNEL_ID = ? {date_filter}
        GROUP BY PUBLISHED_WEEKDAY
        ORDER BY CASE PUBLISHED_WEEKDAY
            WHEN 'Sunday'    THEN 1
            WHEN 'Monday'    THEN 2
            WHEN 'Tuesday'   THEN 3
            WHEN 'Wednesday' THEN 4
            WHEN 'Thursday'  THEN 5
            WHEN 'Friday'    THEN 6
            WHEN 'Saturday'  THEN 7
        END
    """, [channel_id]).collect()

    baseline = session.sql(f"""
        WITH channel_avg AS (
            SELECT AVG(VIEW_COUNT) AS AVG_VIEWS
            FROM RAW.VIDEOS WHERE CHANNEL_ID = ? {date_filter}
        )
        SELECT
            COUNT(*) AS VIDEOS_WITH_BASELINE_DATA,
            SUM(CASE WHEN v.VIEW_COUNT > c.AVG_VIEWS THEN 1 ELSE 0 END) AS VIDEOS_ABOVE_AVERAGE
        FROM RAW.VIDEOS v, channel_avg c
        WHERE v.CHANNEL_ID = ? {date_filter}
    """, [channel_id, channel_id]).collect()[0]

    WEEKDAY_ORDER = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    weekday_map = {r["PUBLISHED_WEEKDAY"]: float(r["AVG_LIFETIME_VIEWS"]) for r in weekday_rows}

    has_sufficient = int(kpi["TOTAL_VIDEOS"]) >= 5
    if has_sufficient and weekday_map:
        best_day = max(weekday_map, key=lambda d: weekday_map[d])
        best_day_avg_views = weekday_map[best_day]
    else:
        best_day = None
        best_day_avg_views = None

    return {
        "total_videos":              int(kpi["TOTAL_VIDEOS"]),
        "avg_views":                 float(kpi["AVG_VIEWS"]) if kpi["AVG_VIEWS"] is not None else None,
        "avg_likes":                 float(kpi["AVG_LIKES"]) if kpi["AVG_LIKES"] is not None else None,
        "best_day":                  best_day,
        "best_day_avg_views":        best_day_avg_views,
        "weekday_performance": [
            {"weekday": day, "avg_views": weekday_map.get(day, 0)}
            for day in WEEKDAY_ORDER
        ],
        "videos_with_baseline_data": int(baseline["VIDEOS_WITH_BASELINE_DATA"]),
        "videos_above_average":      int(baseline["VIDEOS_ABOVE_AVERAGE"]),
    }


@app.post("/ask")
def ask(body: AskRequest):
    result = route(
        channel_id=body.channel_id,
        session=app.state.session,
        question=body.question,
    )
    return {"answer": result}


@app.post("/upload")
def upload(
    video: UploadFile = File(...),
    thumbnail: UploadFile = File(...),
    channel_id: str = Form(...),
    category_id: str = Form(...),
    published_weekday: str = Form(...),
    published_hour: int = Form(...),
    title: str = Form(...),
):
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, video.filename or "video.mp4")
        with open(video_path, "wb") as f:
            f.write(video.file.read())

        thumbnail_path = os.path.join(tmpdir, thumbnail.filename or "thumbnail.jpg")
        with open(thumbnail_path, "wb") as f:
            f.write(thumbnail.file.read())

        result = route(
            channel_id=channel_id,
            session=app.state.session,
            model=app.state.model,
            video_file_path=video_path,
            thumbnail_url=thumbnail_path,
            category_id=category_id,
            published_weekday=published_weekday,
            published_hour=published_hour,
            title=title,
        )

    return result
