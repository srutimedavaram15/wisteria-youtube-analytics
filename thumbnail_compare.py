"""
Fetches top and bottom performing video thumbnails from VIDEOS_TRAINING_DATA
for visual comparison of what high- vs low-performing thumbnails look like.
"""

import base64
import os

import anthropic
import requests
from dotenv import load_dotenv
from snowflake.snowpark import Session
from snowflake.snowpark import functions as F

from pull_public_channel import SOURCE_CHANNEL_ID

load_dotenv()


def get_session() -> Session:
    return Session.builder.configs({
        "account":   os.environ["SNOWFLAKE_ACCOUNT"],
        "user":      os.environ["SNOWFLAKE_USER"],
        "password":  os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database":  os.environ["SNOWFLAKE_DATABASE"],
        "schema":    "MODELING",
    }).create()


_EXT_TO_MEDIA_TYPE = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
    ".gif":  "image/gif",
}


def image_url_to_base64(url: str) -> tuple[str, str]:
    """
    Downloads an image from url and returns (base64_string, media_type).
    media_type is taken from the response Content-Type header.
    """
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    media_type = response.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    b64 = base64.standard_b64encode(response.content).decode("utf-8")
    return b64, media_type


def build_image_block(source: str) -> dict:
    """
    Returns an Anthropic API base64-type image content block for either a
    URL or a local file path.
    """
    if source.startswith("http"):
        b64, media_type = image_url_to_base64(source)
    else:
        ext = os.path.splitext(source)[1].lower()
        media_type = _EXT_TO_MEDIA_TYPE.get(ext, "image/jpeg")
        with open(source, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": b64},
    }


def get_reference_thumbnails(session, channel_id: str, n: int = 3) -> tuple[list[dict], list[dict]]:
    """
    Returns (top_n, bottom_n) lists of dicts with TITLE and THUMBNAIL_URL,
    ordered by VIEW_COUNT descending/ascending. Rows with null THUMBNAIL_URL
    are excluded.
    """
    df = (
        session.table("MODELING.VIDEOS_TRAINING_DATA")
        .filter(F.col("SOURCE_CHANNEL_ID") == channel_id)
        .filter(F.col("THUMBNAIL_URL").is_not_null())
        .select("TITLE", "THUMBNAIL_URL", "VIEW_COUNT")
    )

    top = (
        df.order_by(F.col("VIEW_COUNT").desc())
        .limit(n)
        .to_pandas()
        [["TITLE", "THUMBNAIL_URL"]]
        .to_dict(orient="records")
    )
    bottom = (
        df.order_by(F.col("VIEW_COUNT").asc())
        .limit(n)
        .to_pandas()
        [["TITLE", "THUMBNAIL_URL"]]
        .to_dict(orient="records")
    )

    return top, bottom


def compare_thumbnail(
    new_thumbnail_url: str,
    top_videos: list[dict],
    bottom_videos: list[dict],
) -> str:
    """
    Sends the new thumbnail alongside top- and bottom-performing reference
    thumbnails to Claude vision and returns 2-3 sentences of actionable feedback.
    new_thumbnail_url may be a public URL or a local file path.
    """
    content: list[dict] = [
        {"type": "text", "text": "Here is the new YouTube thumbnail to evaluate:"},
        build_image_block(new_thumbnail_url),
        {"type": "text", "text": "\nThese are TOP-PERFORMING thumbnails (high view counts) from the same channel:"},
    ]
    for v in top_videos:
        content.append({"type": "text", "text": f"Title: {v['TITLE']}"})
        content.append(build_image_block(v["THUMBNAIL_URL"]))

    content.append({
        "type": "text",
        "text": "\nThese are BOTTOM-PERFORMING thumbnails (low view counts) from the same channel:",
    })
    for v in bottom_videos:
        content.append({"type": "text", "text": f"Title: {v['TITLE']}"})
        content.append(build_image_block(v["THUMBNAIL_URL"]))

    content.append({
        "type": "text",
        "text": (
            "\nCompare the new thumbnail against the high-performing and low-performing examples above. "
            "In 2-3 sentences of plain English, give actionable feedback on how the new thumbnail could "
            "be improved to perform more like the top videos. Focus on visual elements, composition, "
            "text, and emotional appeal — do not give a numeric score. "
            "Respond in plain, conversational text only — no markdown formatting, no headers, "
            "no asterisks for bold, no bullet points. Just natural sentences."
        ),
    })

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def main() -> None:
    session = get_session()
    try:
        top, bottom = get_reference_thumbnails(session, SOURCE_CHANNEL_ID)

        print(f"Top {len(top)} videos by view count:")
        for v in top:
            print(f"  {v['TITLE']}")
            print(f"    {v['THUMBNAIL_URL']}")

        print(f"\nBottom {len(bottom)} videos by view count:")
        for v in bottom:
            print(f"  {v['TITLE']}")
            print(f"    {v['THUMBNAIL_URL']}")

        print("\n--- Thumbnail comparison (using lowest-performing video as subject) ---")
        feedback = compare_thumbnail(bottom[0]["THUMBNAIL_URL"], top, bottom)
        print(feedback)
    finally:
        session.close()


if __name__ == "__main__":
    main()
