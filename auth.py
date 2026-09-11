"""
Handles per-creator OAuth authorization for the YouTube APIs.
"""

import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_DIR = Path("tokens")


def authorize_new_creator() -> str:
    """
    Runs the OAuth consent flow for one creator. Returns the channel_id the
    resulting credentials belong to, and writes tokens/{channel_id}.json.
    """
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise FileNotFoundError(
            f"{CLIENT_SECRET_FILE} not found. Download it from GCP Console -> "
            "Credentials -> your OAuth client ID."
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    credentials = flow.run_local_server(port=0)

    youtube = build("youtube", "v3", credentials=credentials)
    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    channel_id = response["items"][0]["id"]
    channel_title = response["items"][0]["snippet"]["title"]

    TOKEN_DIR.mkdir(exist_ok=True)
    token_path = TOKEN_DIR / f"{channel_id}.json"
    with open(token_path, "w") as f:
        f.write(credentials.to_json())

    print(f"Authorized: {channel_title} ({channel_id}) -> saved to {token_path}")
    return channel_id


def load_credentials(channel_id: str):
    """Loads and refreshes stored credentials for a previously authorized creator."""
    from google.oauth2.credentials import Credentials

    token_path = TOKEN_DIR / f"{channel_id}.json"
    if not token_path.exists():
        raise FileNotFoundError(f"No stored token for {channel_id}. Run authorize_new_creator() first.")

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


def list_authorized_creators() -> list[str]:
    """Returns channel_ids for every creator we currently have a stored token for."""
    if not TOKEN_DIR.exists():
        return []
    return [p.stem for p in TOKEN_DIR.glob("*.json")]


if __name__ == "__main__":
    authorize_new_creator()
