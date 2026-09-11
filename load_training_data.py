"""
Loads public channel video data into Snowflake's MODELING schema
as training data for predictive models.
"""

import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

from load_to_snowflake import _derive_published_fields, _iso_duration_to_seconds
from pull_public_channel import SOURCE_CHANNEL_ID, SOURCE_CHANNEL_TITLE

load_dotenv()

PUBLIC_DATA_DIR = Path("public_channel_data")


def get_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema="MODELING",
    )


def load_training_data() -> int:
    """
    Reads the public channel CSV, derives features, and bulk-upserts into
    MODELING.VIDEOS_TRAINING_DATA. Returns the number of rows processed.
    """
    csv_path = PUBLIC_DATA_DIR / f"{SOURCE_CHANNEL_ID}_videos.csv"
    df = pd.read_csv(csv_path)

    if df.empty:
        print("No data found in CSV — nothing to load.")
        return 0

    df = df.copy()
    df = _derive_published_fields(df)
    df["duration_seconds"] = df["duration"].apply(_iso_duration_to_seconds)

    rows = [
        (
            row["video_id"],
            SOURCE_CHANNEL_ID,
            SOURCE_CHANNEL_TITLE,
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

    staging = "videos_training_staging_tmp"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                CREATE TEMPORARY TABLE IF NOT EXISTS {staging} (
                    VIDEO_ID             VARCHAR,
                    SOURCE_CHANNEL_ID    VARCHAR,
                    SOURCE_CHANNEL_TITLE VARCHAR,
                    TITLE                VARCHAR,
                    PUBLISHED_AT         TIMESTAMP_NTZ,
                    PUBLISHED_WEEKDAY    VARCHAR,
                    PUBLISHED_HOUR       INTEGER,
                    DURATION_SECONDS     INTEGER,
                    CATEGORY_ID          VARCHAR,
                    VIEW_COUNT           INTEGER,
                    LIKE_COUNT           INTEGER,
                    COMMENT_COUNT        INTEGER,
                    THUMBNAIL_URL        VARCHAR
                )
            """)
            cur.execute(f"TRUNCATE TABLE {staging}")
            cur.executemany(
                f"INSERT INTO {staging} VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                rows,
            )
            cur.execute(f"""
                MERGE INTO VIDEOS_TRAINING_DATA AS target
                USING {staging} AS source
                    ON target.VIDEO_ID = source.VIDEO_ID
                WHEN MATCHED THEN UPDATE SET
                    VIEW_COUNT        = source.VIEW_COUNT,
                    LIKE_COUNT        = source.LIKE_COUNT,
                    COMMENT_COUNT     = source.COMMENT_COUNT,
                    THUMBNAIL_URL     = source.THUMBNAIL_URL,
                    LOADED_AT         = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT (
                    VIDEO_ID, SOURCE_CHANNEL_ID, SOURCE_CHANNEL_TITLE, TITLE, PUBLISHED_AT,
                    PUBLISHED_WEEKDAY, PUBLISHED_HOUR, DURATION_SECONDS,
                    CATEGORY_ID, VIEW_COUNT, LIKE_COUNT, COMMENT_COUNT,
                    THUMBNAIL_URL, LOADED_AT
                ) VALUES (
                    source.VIDEO_ID, source.SOURCE_CHANNEL_ID, source.SOURCE_CHANNEL_TITLE,
                    source.TITLE, source.PUBLISHED_AT, source.PUBLISHED_WEEKDAY,
                    source.PUBLISHED_HOUR, source.DURATION_SECONDS, source.CATEGORY_ID,
                    source.VIEW_COUNT, source.LIKE_COUNT, source.COMMENT_COUNT,
                    source.THUMBNAIL_URL, CURRENT_TIMESTAMP()
                )
            """)
        conn.commit()
    finally:
        conn.close()

    return len(rows)


if __name__ == "__main__":
    count = load_training_data()
    print(f"Loaded {count} rows into MODELING.VIDEOS_TRAINING_DATA.")
