"""
Module 7: instagram_uploader.py
──────────────────────────────────
Uploads videos to Instagram as Reels using the Instagram Graph API.

FREE — but setup is involved:
  1. You need a Facebook Business or Creator account
  2. Connect your Instagram account to a Facebook Page
  3. Create a Facebook App at developers.facebook.com
  4. Get a long-lived access token (valid 60 days, refreshable)

Instagram Reels requirements:
  - Aspect ratio: 9:16 (1080x1920)
  - Duration: 3–90 seconds
  - Format: MP4
  - Max file size: 1GB (we're well under this)

Upload flow:
  Step 1: Create a media container (POST with video URL)
  Step 2: Wait for processing (poll status)
  Step 3: Publish the container
  
NOTE: Instagram requires a PUBLIC video URL to import from.
We use a free file hosting service (0x0.st or transfer.sh) as a workaround.
For production, consider Cloudflare R2 free tier (10GB/month free) or Backblaze B2.
"""

import os
import time
import requests
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def _upload_video_to_temp_host(video_path: Path) -> str:
    """
    Upload video to a free temp hosting service to get a public URL.
    Instagram Graph API needs a public URL to pull the video from.
    
    Uses 0x0.st — free, no account needed, files kept for ~1 year.
    Alternative: transfer.sh (7 days), file.io (1 use)
    """
    logger.info(f"Uploading to temp host for Instagram access...")

    with open(video_path, "rb") as f:
        try:
            # 0x0.st — anonymous file hosting
            response = requests.post(
                "https://0x0.st",
                files={"file": (video_path.name, f, "video/mp4")},
                timeout=120,
            )
            if response.status_code == 200:
                url = response.text.strip()
                logger.info(f"Temp host URL: {url}")
                return url
        except Exception as e:
            logger.warning(f"0x0.st failed: {e}")

    # Fallback: transfer.sh
    with open(video_path, "rb") as f:
        try:
            response = requests.put(
                f"https://transfer.sh/{video_path.name}",
                data=f,
                headers={"Max-Days": "7"},
                timeout=120,
            )
            if response.status_code == 200:
                url = response.text.strip()
                logger.info(f"transfer.sh URL: {url}")
                return url
        except Exception as e:
            logger.warning(f"transfer.sh failed: {e}")

    raise RuntimeError(
        "Could not upload to any temp host. "
        "Consider setting up Cloudflare R2 free tier for reliable hosting."
    )


def _create_reels_container(
    business_id: str,
    access_token: str,
    video_url: str,
    caption: str,
) -> str:
    """Step 1: Create an Instagram media container."""
    url = f"{GRAPH_API_BASE}/{business_id}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",  # also shows in regular feed
        "access_token": access_token,
    }

    response = requests.post(url, params=params, timeout=30)
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"Instagram container creation failed: {data['error']}")

    container_id = data["id"]
    logger.info(f"Instagram container created: {container_id}")
    return container_id


def _wait_for_processing(
    container_id: str,
    access_token: str,
    max_wait_seconds: int = 300,
) -> bool:
    """Step 2: Poll until Instagram finishes processing the video."""
    url = f"{GRAPH_API_BASE}/{container_id}"
    params = {
        "fields": "status_code,status",
        "access_token": access_token,
    }

    logger.info("Waiting for Instagram to process video...")
    waited = 0
    poll_interval = 10

    while waited < max_wait_seconds:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        status = data.get("status_code", "")

        logger.info(f"Processing status: {status} ({waited}s elapsed)")

        if status == "FINISHED":
            return True
        elif status == "ERROR":
            logger.error(f"Instagram processing error: {data}")
            return False
        elif status in ("IN_PROGRESS", "PUBLISHED"):
            pass  # keep waiting

        time.sleep(poll_interval)
        waited += poll_interval

    logger.warning(f"Timed out waiting for Instagram processing after {max_wait_seconds}s")
    return False


def _publish_container(
    business_id: str,
    container_id: str,
    access_token: str,
) -> str:
    """Step 3: Publish the media container as a Reel."""
    url = f"{GRAPH_API_BASE}/{business_id}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": access_token,
    }

    response = requests.post(url, params=params, timeout=30)
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"Instagram publish failed: {data['error']}")

    media_id = data["id"]
    logger.info(f"Instagram Reel published! Media ID: {media_id}")
    return media_id


def upload_to_instagram(
    video_path: Path,
    caption: str,
    hashtags: list[str] = None,
) -> str:
    """
    Full Instagram Reels upload pipeline.
    
    Returns the published media ID.
    """
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    business_id = os.getenv("INSTAGRAM_BUSINESS_ID")

    if not access_token or not business_id:
        raise ValueError(
            "INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ID must be set in .env\n"
            "See setup guide: python modules/instagram_uploader.py"
        )

    # Build caption with hashtags
    if hashtags:
        hashtag_str = " ".join(f"#{tag.strip('#')}" for tag in hashtags[:30])
        full_caption = f"{caption}\n\n{hashtag_str}"
    else:
        full_caption = caption
    full_caption += "\n\n#reels #viral #shorts"

    # Step 0: Get public URL for the video
    video_url = _upload_video_to_temp_host(video_path)

    # Step 1: Create container
    container_id = _create_reels_container(
        business_id, access_token, video_url, full_caption
    )

    # Step 2: Wait for processing
    success = _wait_for_processing(container_id, access_token)
    if not success:
        raise RuntimeError("Instagram video processing failed or timed out")

    # Step 3: Publish
    media_id = _publish_container(business_id, container_id, access_token)
    return media_id


if __name__ == "__main__":
    print("Instagram Graph API Setup Guide")
    print("=" * 40)
    print("""
1. Go to: developers.facebook.com → Create App
2. Select "Business" as app type
3. Add product: "Instagram Graph API"
4. Connect your Instagram Business/Creator account
   (Settings → Instagram → Add Account)
5. Generate a User Access Token:
   - Tools → Graph API Explorer
   - Select your app
   - Add permissions: instagram_basic, instagram_content_publish
   - Click "Generate Access Token"
6. Convert to Long-Lived Token (60 days):
   GET https://graph.facebook.com/oauth/access_token?
     grant_type=fb_exchange_token&
     client_id=YOUR_APP_ID&
     client_secret=YOUR_APP_SECRET&
     fb_exchange_token=YOUR_SHORT_TOKEN
7. Get your Instagram Business Account ID:
   GET https://graph.facebook.com/me/accounts?access_token=YOUR_TOKEN
   (find ig_id in the response)
8. Add to .env:
   INSTAGRAM_ACCESS_TOKEN=your_long_lived_token
   INSTAGRAM_BUSINESS_ID=your_ig_business_id

Note: Token expires every 60 days. Refresh with the same exchange endpoint.
""")
