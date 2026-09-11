"""
FastAPI backend exposing the YouTube analytics pipeline over HTTP.
Run with: uvicorn backend:app --reload
"""

import os
import tempfile
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from snowflake.snowpark import Session

import joblib

from app_router import route

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


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    channel_id: str
    question: str


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
