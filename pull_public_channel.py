"""
Pulls public YouTube channel data using an API key (no OAuth required).
Used for channels we don't own/manage — public metadata and stats only.
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

SOURCE_CHANNEL_ID = "UCpB959t8iPrxQWj7G6n0ctQ"
SOURCE_CHANNEL_TITLE = "SSSniperWolf"


def _build_client():
    return build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])


def get_uploads_playlist_id(youtube, channel_id: str) -> str:
    response = youtube.channels().list(
        part="contentDetails", id=channel_id
    ).execute()
    return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def pull_all_videos(youtube, channel_id: str) -> list[dict]:
    """
    Returns one dict per video with all metadata and stats combined.
    Fetches the full upload history regardless of size.
    """
    # Step 1: paginate through the uploads playlist for video_id/title/published_at
    uploads_playlist_id = get_uploads_playlist_id(youtube, channel_id)
    playlist_items = []
    page_token = None
    while True:
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()

        for item in response.get("items", []):
            snippet = item["snippet"]
            playlist_items.append({
                "video_id": snippet["resourceId"]["videoId"],
                "title": snippet["title"],
                "published_at": snippet["publishedAt"],
            })

        if len(playlist_items) % 500 == 0 and len(playlist_items) > 0:
            print(f"  {len(playlist_items)} videos listed so far...")

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    print(f"  {len(playlist_items)} total videos found, fetching details...")

    # Step 2: batch video IDs 50 at a time to get stats and content details
    video_ids = [v["video_id"] for v in playlist_items]
    details_by_id = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(batch),
            maxResults=50,
        ).execute()

        for item in response.get("items", []):
            stats = item.get("statistics", {})
            thumbnails = item["snippet"].get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("high", {}).get("url")
                or thumbnails.get("default", {}).get("url")
            )
            details_by_id[item["id"]] = {
                "category_id": item["snippet"]["categoryId"],
                "duration": item["contentDetails"]["duration"],
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
                "thumbnail_url": thumbnail_url,
            }

        fetched = min(i + 50, len(video_ids))
        if fetched % 500 == 0:
            print(f"  {fetched} video details fetched so far...")

    # Step 3: merge playlist metadata with details
    _empty_details = {
        "category_id": None,
        "duration": "PT0S",
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "thumbnail_url": None,
    }
    results = []
    for item in playlist_items:
        details = details_by_id.get(item["video_id"], _empty_details)
        results.append({**item, **details})

    print(f"  Done. {len(results)} videos merged.")
    return results


def run() -> None:
    youtube = _build_client()
    videos = pull_all_videos(youtube, SOURCE_CHANNEL_ID)

    out_dir = Path("public_channel_data")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{SOURCE_CHANNEL_ID}_videos.csv"

    pd.DataFrame(videos).to_csv(out_path, index=False)
    print(f"Saved {len(videos)} videos -> {out_path}")


if __name__ == "__main__":
    run()
