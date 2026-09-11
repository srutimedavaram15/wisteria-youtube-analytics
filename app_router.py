"""
Routes incoming requests to the appropriate pipeline:
  - Video upload → duration + ML tier prediction + thumbnail feedback
  - Natural-language question → SQL generation + plain-English answer
"""

import os

from dotenv import load_dotenv
from snowflake.snowpark import Session

from llm_query import execute_and_answer

load_dotenv()
from model_predict import build_feature_vector, load_model, predict_tier
from thumbnail_compare import compare_thumbnail, get_reference_thumbnails
from video_upload import get_video_duration_seconds

_TIER_LABELS = {
    "below_average": "📉 Below your usual",
    "typical":       "➡️ Right in your typical range",
    "above_average": "📈 Above your usual",
}


def handle_upload(
    video_file_path: str,
    thumbnail_url: str,
    category_id: str,
    published_weekday: str,
    published_hour: int,
    title: str,
    channel_id: str,
    session: Session,
    model,
) -> dict:
    """
    Runs the full upload analysis pipeline:
    - Derives duration from the local video file
    - Predicts performance tier using the pre-loaded ML model
    - Compares the thumbnail against channel reference thumbnails via Claude vision
    Returns {"performance_tier": str, "thumbnail_feedback": str}.
    """
    duration_seconds = get_video_duration_seconds(video_file_path)

    feature_vector = build_feature_vector(
        duration_seconds=duration_seconds,
        published_weekday=published_weekday,
        category_id=category_id,
        title=title,
        published_hour=published_hour,
        feature_names=model.feature_names_in_,
    )
    raw_tier = predict_tier(model, feature_vector)
    friendly_tier = _TIER_LABELS.get(raw_tier, raw_tier)

    top_videos, bottom_videos = get_reference_thumbnails(session, channel_id)
    thumbnail_feedback = compare_thumbnail(thumbnail_url, top_videos, bottom_videos)

    return {
        "performance_tier": friendly_tier,
        "thumbnail_feedback": thumbnail_feedback,
    }


def handle_question(question: str, channel_id: str, session: Session) -> str:
    """Answers a creator's natural-language analytics question."""
    return execute_and_answer(question, channel_id, session)


def route(
    channel_id: str,
    session: Session,
    model=None,
    question: str | None = None,
    video_file_path: str | None = None,
    thumbnail_url: str | None = None,
    category_id: str | None = None,
    published_weekday: str | None = None,
    published_hour: int | None = None,
    title: str | None = None,
) -> dict | str:
    """
    Dispatches to the appropriate handler based on what was provided.
    Returns a dict for upload requests, a string for question requests.
    """
    if video_file_path is not None:
        return handle_upload(
            video_file_path=video_file_path,
            thumbnail_url=thumbnail_url,
            category_id=category_id,
            published_weekday=published_weekday,
            published_hour=published_hour,
            title=title,
            channel_id=channel_id,
            session=session,
            model=model,
        )

    if question is not None:
        return handle_question(question, channel_id, session)

    return "I need either a question or a video file to help you."


def get_session() -> Session:
    return Session.builder.configs({
        "account":   os.environ["SNOWFLAKE_ACCOUNT"],
        "user":      os.environ["SNOWFLAKE_USER"],
        "password":  os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database":  os.environ["SNOWFLAKE_DATABASE"],
        "schema":    "MODELING",
    }).create()


def main() -> None:
    channel_id = "UCpB959t8iPrxQWj7G6n0ctQ"
    session = get_session()
    try:
        model = load_model(session)

        print("=== Upload analysis ===")
        upload_result = route(
            channel_id=channel_id,
            session=session,
            model=model,
            video_file_path="test_video.mp4",
            thumbnail_url="https://i.ytimg.com/vi/8wzXfSKjq20/hqdefault.jpg",
            category_id="20",
            published_weekday="Friday",
            published_hour=18,
            title="I Tried the Weirdest Gaming Setup Ever",
        )
        print(upload_result)

        print("\n=== Question answering (SSSniperWolf channel) ===")
        question_result = route(
            channel_id=channel_id,
            session=session,
            question="What's my best day to post?",
        )
        print(question_result)

        print("\n=== Question answering (UC_5MDffbru8OYck3HCTUoIw channel) ===")
        question_result_2 = route(
            channel_id="UC_5MDffbru8OYck3HCTUoIw",
            session=session,
            question="What's my best day to post?",
        )
        print(question_result_2)
    finally:
        
        session.close()


if __name__ == "__main__":
    main()
