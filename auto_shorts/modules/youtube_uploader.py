"""
Module 6: youtube_uploader.py
───────────────────────────────
Uploads videos to YouTube as Shorts using YouTube Data API v3.

FREE QUOTA: 10,000 units/day
  - 1 upload = ~1,600 units
  - So you get ~6 uploads/day for free
  - Resets every midnight Pacific time

SETUP (one-time):
  1. Go to console.cloud.google.com
  2. Create a project → Enable "YouTube Data API v3"
  3. Create OAuth 2.0 credentials (Desktop app type)
  4. Download the client_secrets JSON → save as config/yt_client_secrets.json
  5. Run this script once to authenticate → it saves config/yt_token.json
  6. After that, uploads are fully automated
"""

import os
import json
import pickle
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

TOKEN_FILE = Path(os.getenv("YOUTUBE_TOKEN_FILE", "config/yt_token.json"))
CLIENT_SECRETS_FILE = Path("config/yt_client_secrets.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_youtube_service():
    """
    Get an authenticated YouTube API service object.
    First run: opens browser for OAuth consent.
    After that: uses saved token automatically.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Google API packages not installed.\n"
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )

    creds = None

    # Load existing token if available
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "r") as f:
            token_data = json.load(f)
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing YouTube token...")
            creds.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE.exists():
                raise FileNotFoundError(
                    f"YouTube client secrets not found at {CLIENT_SECRETS_FILE}\n"
                    "Download from Google Cloud Console → APIs & Services → Credentials"
                )
            logger.info("Starting YouTube OAuth flow (browser will open)...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        logger.info(f"YouTube token saved: {TOKEN_FILE}")

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    keywords: list[str],
    category_id: str = "22",  # 22 = People & Blogs, good default
) -> str:
    """
    Upload a video to YouTube as a Short.

    A video is automatically treated as a Short by YouTube if:
    - It's 60 seconds or less
    - It has 9:16 aspect ratio
    - Title or description contains #Shorts

    Returns the YouTube video ID.
    """
    from googleapiclient.http import MediaFileUpload

    youtube = _get_youtube_service()

    # Ensure #Shorts is in the title for algorithm recognition
    if "#Shorts" not in title and "#shorts" not in title:
        title = title[:55] + " #Shorts"

    # Add #Shorts to description too
    full_description = f"{description}\n\n#Shorts #short"

    body = {
        "snippet": {
            "title": title[:100],  # YouTube title limit
            "description": full_description[:5000],
            "tags": keywords + ["shorts", "short", "viral"],
            "categoryId": category_id,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",   # change to "private" for testing
            "selfDeclaredMadeForKids": False,
        },
    }

    logger.info(f"Uploading to YouTube: '{title}'")
    logger.info(f"File size: {video_path.stat().st_size / (1024*1024):.1f} MB")

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,  # resumable upload is safer for larger files
        chunksize=1024 * 1024 * 5,  # 5MB chunks
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.info(f"Upload progress: {progress}%")

    video_id = response["id"]
    video_url = f"https://youtube.com/shorts/{video_id}"
    logger.info(f"YouTube upload complete! URL: {video_url}")
    return video_id


if __name__ == "__main__":
    print("YouTube Uploader Setup Guide")
    print("=" * 40)
    print("""
1. Go to: https://console.cloud.google.com
2. Create a new project (or use existing)
3. Go to: APIs & Services → Library
4. Search for "YouTube Data API v3" → Enable it
5. Go to: APIs & Services → Credentials
6. Click "Create Credentials" → "OAuth client ID"
7. Select "Desktop app" as application type
8. Download the JSON file
9. Save it as: config/yt_client_secrets.json
10. Run this script to authenticate:
    python modules/youtube_uploader.py

After authentication, uploads are fully automated!
""")

    # Test authentication
    try:
        service = _get_youtube_service()
        print("Authentication successful!")
    except FileNotFoundError as e:
        print(f"Setup needed: {e}")
