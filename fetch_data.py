"""
For every creator we have an authorized token for:
  1. Pull channel + video metadata (YouTube Data API v3)
  2. Pull per-video daily performance (YouTube Analytics API) for a lookback window

Writes results to local CSV files under ./raw_data/{channel_id}/
"""

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from googleapiclient.discovery import build

from auth import list_authorized_creators, load_credentials

# Temporarily widened for testing with thin data (single video from 2022).
# Set back to 90 once real creators with recent activity are being tested.
LOOKBACK_DAYS = 90
RAW_DIR = Path("raw_data")


def fetch_video_list(youtube, channel_id: str) -> list[dict]:
    """
    Returns lightweight metadata (video_id, title, published_at) for every
    video in the channel's uploads playlist.
    """
    # Resolve the uploads playlist ID for this channel
    ch_response = youtube.channels().list(
        part="contentDetails", id=channel_id
    ).execute()
    uploads_playlist_id = (
        ch_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )

    videos = []
    page_token = None
    while True:
        pl_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()

        for item in pl_response.get("items", []):
            snippet = item["snippet"]
            videos.append({
                "video_id": snippet["resourceId"]["videoId"],
                "title": snippet["title"],
                "published_at": snippet["publishedAt"],
            })

        page_token = pl_response.get("nextPageToken")
        if not page_token:
            break

    return videos


def fetch_video_details(youtube, video_ids: list[str]) -> list[dict]:
    """
    Returns contentDetails + statistics for each video ID.
    Batches requests in groups of 50 (API limit).
    """
    results = []
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
            results.append({
                "video_id": item["id"],
                "category_id": item["snippet"]["categoryId"],
                "duration": item["contentDetails"]["duration"],
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
                "comment_count": int(stats.get("commentCount", 0)),
                "thumbnail_url": thumbnail_url,
            })

    return results


def fetch_daily_analytics(
    youtube_analytics,
    channel_id: str,
    start_date: date,
    end_date: date,
    video_ids: list[str],
) -> pd.DataFrame:
    """
    Queries the YouTube Analytics API for per-video daily metrics over the
    given date range. Returns a DataFrame whose column names match the API
    response headers (day, video, views, likes, comments,
    estimatedMinutesWatched, averageViewDuration).
    """
    response = youtube_analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=start_date.isoformat(),
        endDate=end_date.isoformat(),
        metrics="views,likes,comments,estimatedMinutesWatched,averageViewDuration",
        dimensions="day,video",
        filters=f"video=={','.join(video_ids)}",
        maxResults=10000,
    ).execute()

    columns = [h["name"] for h in response.get("columnHeaders", [])]
    rows = response.get("rows", [])
    return pd.DataFrame(rows, columns=columns)


def fetch_all_for_creator(channel_id: str) -> pd.DataFrame:
    """
    Fetches and merges video list + details for one creator, writes to
    raw_data/{channel_id}/videos.csv, and returns the combined DataFrame.
    Also fetches daily analytics and saves to raw_data/{channel_id}/daily_analytics.csv.
    """
    creds = load_credentials(channel_id)
    youtube = build("youtube", "v3", credentials=creds)

    ch_response = youtube.channels().list(part="snippet", id=channel_id).execute()
    channel_title = ch_response["items"][0]["snippet"]["title"]

    out_dir = RAW_DIR / channel_id
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "channel_info.json", "w") as f:
        json.dump({"channel_id": channel_id, "channel_title": channel_title}, f)

    video_list = fetch_video_list(youtube, channel_id)
    if not video_list:
        print(f"No videos found for {channel_id}")
        return pd.DataFrame()

    video_ids = [v["video_id"] for v in video_list]
    details = fetch_video_details(youtube, video_ids)

    df = pd.DataFrame(video_list).merge(
        pd.DataFrame(details), on="video_id", how="left"
    )

    out_dir = RAW_DIR / channel_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "videos.csv"
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} videos -> {out_path}")

    youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)
    df_analytics = fetch_daily_analytics(youtube_analytics, channel_id, start_date, end_date, video_ids)
    analytics_path = out_dir / "daily_analytics.csv"
    df_analytics.to_csv(analytics_path, index=False)
    print(f"Saved {len(df_analytics)} rows -> {analytics_path}")

    return df


if __name__ == "__main__":
    creators = list_authorized_creators()
    if not creators:
        print("No authorized creators found. Run auth.py first to authorize a creator.")
    else:
        for channel_id in creators:
            fetch_all_for_creator(channel_id)
