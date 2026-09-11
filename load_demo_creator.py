from dotenv import load_dotenv
from app_router import get_session

load_dotenv(dotenv_path=".env")

session = get_session()
try:
    # Upsert creator row
    session.sql("""
        MERGE INTO RAW.CREATORS AS tgt
        USING (
            SELECT DISTINCT
                SOURCE_CHANNEL_ID  AS CHANNEL_ID,
                SOURCE_CHANNEL_TITLE AS CHANNEL_TITLE
            FROM MODELING.VIDEOS_TRAINING_DATA
        ) AS src
        ON tgt.CHANNEL_ID = src.CHANNEL_ID
        WHEN NOT MATCHED THEN INSERT (
            CHANNEL_ID, CHANNEL_TITLE, AUTHORIZED_AT, LAST_SYNCED_AT
        ) VALUES (
            src.CHANNEL_ID, src.CHANNEL_TITLE,
            CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
        )
    """).collect()

    creator_rows = session.sql("SELECT COUNT(*) AS N FROM RAW.CREATORS").collect()
    print(f"RAW.CREATORS rows: {creator_rows[0]['N']}")

    # Upsert videos
    session.sql("""
        MERGE INTO RAW.VIDEOS AS tgt
        USING (
            SELECT
                VIDEO_ID,
                SOURCE_CHANNEL_ID  AS CHANNEL_ID,
                TITLE,
                PUBLISHED_AT,
                PUBLISHED_WEEKDAY,
                PUBLISHED_HOUR,
                DURATION_SECONDS,
                CATEGORY_ID,
                VIEW_COUNT,
                LIKE_COUNT,
                COMMENT_COUNT,
                THUMBNAIL_URL
            FROM MODELING.VIDEOS_TRAINING_DATA
        ) AS src
        ON tgt.VIDEO_ID = src.VIDEO_ID
        WHEN NOT MATCHED THEN INSERT (
            VIDEO_ID, CHANNEL_ID, TITLE, PUBLISHED_AT, PUBLISHED_WEEKDAY,
            PUBLISHED_HOUR, DURATION_SECONDS, CATEGORY_ID, VIEW_COUNT,
            LIKE_COUNT, COMMENT_COUNT, LOADED_AT, THUMBNAIL_URL
        ) VALUES (
            src.VIDEO_ID, src.CHANNEL_ID, src.TITLE, src.PUBLISHED_AT,
            src.PUBLISHED_WEEKDAY, src.PUBLISHED_HOUR, src.DURATION_SECONDS,
            src.CATEGORY_ID, src.VIEW_COUNT, src.LIKE_COUNT, src.COMMENT_COUNT,
            CURRENT_TIMESTAMP(), src.THUMBNAIL_URL
        )
    """).collect()

    video_rows = session.sql("SELECT COUNT(*) AS N FROM RAW.VIDEOS").collect()
    print(f"RAW.VIDEOS rows: {video_rows[0]['N']}")
finally:
    session.close()
