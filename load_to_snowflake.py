"""
Loads the CSVs written by fetch_data.py into Snowflake.
"""

import json
import os
import re
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path("raw_data")


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
    )


def upsert_creator(conn, channel_id: str, channel_title: str | None = None) -> None:
    """
    Merges one creator row into the CREATORS table.
    Updates LAST_SYNCED_AT on match; inserts a full row on no match.
    """
    sql = """
        MERGE INTO CREATORS AS target
        USING (SELECT %s AS channel_id, %s AS channel_title) AS source
            ON target.CHANNEL_ID = source.channel_id
        WHEN MATCHED THEN
            UPDATE SET
                CHANNEL_TITLE  = source.channel_title,
                LAST_SYNCED_AT = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN
            INSERT (CHANNEL_ID, CHANNEL_TITLE, AUTHORIZED_AT, LAST_SYNCED_AT)
            VALUES (source.channel_id, source.channel_title,
                    CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())
    """
    with conn.cursor() as cur:
        cur.execute(sql, (channel_id, channel_title))


def _iso_duration_to_seconds(duration: str) -> int:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _derive_published_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Adds published_weekday, published_hour, and published_at_ntz columns in-place."""
    published = pd.to_datetime(df["published_at"], utc=True)
    df["published_weekday"] = published.dt.day_name()
    df["published_hour"] = published.dt.hour
    df["published_at_ntz"] = published.dt.tz_localize(None).dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def upsert_videos(conn, channel_id: str, df: pd.DataFrame) -> None:
    """
    Bulk-upserts rows from a videos DataFrame into the VIDEOS table.
    Derives published_weekday, published_hour, and duration_seconds before loading.
    Matched on VIDEO_ID: updates counts on match, inserts full row on no match.
    """
    if df.empty:
        return

    df = df.copy()
    df = _derive_published_fields(df)
    df["duration_seconds"] = df["duration"].apply(_iso_duration_to_seconds)

    rows = [
        (
            row["video_id"],
            channel_id,
            row["title"],
            row["published_at_ntz"],
            row["published_weekday"],
            int(row["published_hour"]),
            int(row["duration_seconds"]),
            str(row["category_id"]) if pd.notna(row["category_id"]) else None,
            int(row["view_count"]),
            int(row["like_count"]),
            int(row["comment_count"]),
            row["thumbnail_url"] if pd.notna(row.get("thumbnail_url")) else None,
        )
        for _, row in df.iterrows()
    ]

    staging = "videos_staging_tmp"
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TEMPORARY TABLE IF NOT EXISTS {staging} (
                VIDEO_ID          VARCHAR,
                CHANNEL_ID        VARCHAR,
                TITLE             VARCHAR,
                PUBLISHED_AT      TIMESTAMP_NTZ,
                PUBLISHED_WEEKDAY VARCHAR,
                PUBLISHED_HOUR    INTEGER,
                DURATION_SECONDS  INTEGER,
                CATEGORY_ID       VARCHAR,
                VIEW_COUNT        INTEGER,
                LIKE_COUNT        INTEGER,
                COMMENT_COUNT     INTEGER,
                THUMBNAIL_URL     VARCHAR
            )
        """)
        cur.execute(f"TRUNCATE TABLE {staging}")
        cur.executemany(
            f"INSERT INTO {staging} VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )
        cur.execute(f"""
            MERGE INTO VIDEOS AS target
            USING {staging} AS source
                ON target.VIDEO_ID = source.VIDEO_ID
            WHEN MATCHED THEN UPDATE SET
                VIEW_COUNT    = source.VIEW_COUNT,
                LIKE_COUNT    = source.LIKE_COUNT,
                COMMENT_COUNT = source.COMMENT_COUNT,
                THUMBNAIL_URL = source.THUMBNAIL_URL,
                LOADED_AT     = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                VIDEO_ID, CHANNEL_ID, TITLE, PUBLISHED_AT,
                PUBLISHED_WEEKDAY, PUBLISHED_HOUR, DURATION_SECONDS,
                CATEGORY_ID, VIEW_COUNT, LIKE_COUNT, COMMENT_COUNT,
                THUMBNAIL_URL, LOADED_AT
            ) VALUES (
                source.VIDEO_ID, source.CHANNEL_ID, source.TITLE, source.PUBLISHED_AT,
                source.PUBLISHED_WEEKDAY, source.PUBLISHED_HOUR, source.DURATION_SECONDS,
                source.CATEGORY_ID, source.VIEW_COUNT, source.LIKE_COUNT,
                source.COMMENT_COUNT, source.THUMBNAIL_URL, CURRENT_TIMESTAMP()
            )
        """)


def upsert_daily_stats(conn, channel_id: str, df: pd.DataFrame) -> None:
    """
    Bulk-upserts rows from a daily_analytics DataFrame into VIDEO_DAILY_STATS.
    Matched on (VIDEO_ID, STAT_DATE): updates all metrics on match,
    inserts a full row (including CHANNEL_ID) on no match.
    """
    if df.empty:
        return

    rows = [
        (
            row["video"],
            channel_id,
            row["day"],
            int(row["views"]),
            int(row["likes"]),
            int(row["comments"]),
            float(row["estimatedMinutesWatched"]),
            float(row["averageViewDuration"]),
        )
        for _, row in df.iterrows()
    ]

    staging = "daily_stats_staging_tmp"
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TEMPORARY TABLE IF NOT EXISTS {staging} (
                VIDEO_ID                  VARCHAR,
                CHANNEL_ID                VARCHAR,
                STAT_DATE                 DATE,
                VIEWS                     INTEGER,
                LIKES                     INTEGER,
                COMMENTS                  INTEGER,
                ESTIMATED_MINUTES_WATCHED FLOAT,
                AVERAGE_VIEW_DURATION     FLOAT
            )
        """)
        cur.execute(f"TRUNCATE TABLE {staging}")
        cur.executemany(
            f"INSERT INTO {staging} VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )
        cur.execute(f"""
            MERGE INTO VIDEO_DAILY_STATS AS target
            USING {staging} AS source
                ON target.VIDEO_ID = source.VIDEO_ID
               AND target.STAT_DATE = source.STAT_DATE
            WHEN MATCHED THEN UPDATE SET
                VIEWS                     = source.VIEWS,
                LIKES                     = source.LIKES,
                COMMENTS                  = source.COMMENTS,
                ESTIMATED_MINUTES_WATCHED = source.ESTIMATED_MINUTES_WATCHED,
                AVERAGE_VIEW_DURATION     = source.AVERAGE_VIEW_DURATION,
                LOADED_AT                 = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (
                VIDEO_ID, CHANNEL_ID, STAT_DATE, VIEWS, LIKES, COMMENTS,
                ESTIMATED_MINUTES_WATCHED, AVERAGE_VIEW_DURATION
            ) VALUES (
                source.VIDEO_ID, source.CHANNEL_ID, source.STAT_DATE,
                source.VIEWS, source.LIKES, source.COMMENTS,
                source.ESTIMATED_MINUTES_WATCHED, source.AVERAGE_VIEW_DURATION
            )
        """)


def load_all() -> None:
    conn = get_connection()
    try:
        for channel_dir in sorted(RAW_DIR.iterdir()):
            if not channel_dir.is_dir():
                continue
            channel_id = channel_dir.name

            try:
                channel_info_path = channel_dir / "channel_info.json"
                if channel_info_path.exists():
                    with open(channel_info_path) as f:
                        channel_title = json.load(f)["channel_title"]
                else:
                    channel_title = None

                upsert_creator(conn, channel_id, channel_title)

                if not (channel_dir / "videos.csv").exists():
                    conn.commit()
                    print(f"{channel_id}: no videos yet, registered creator only")
                    continue

                df_videos = pd.read_csv(channel_dir / "videos.csv")
                df_analytics = pd.read_csv(channel_dir / "daily_analytics.csv")

                upsert_videos(conn, channel_id, df_videos)
                upsert_daily_stats(conn, channel_id, df_analytics)
                conn.commit()

                print(
                    f"{channel_id}: loaded {len(df_videos)} video rows, "
                    f"{len(df_analytics)} daily stat rows"
                )
            except Exception as e:
                conn.rollback()
                print(f"{channel_id}: failed, rolled back — {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    load_all()
