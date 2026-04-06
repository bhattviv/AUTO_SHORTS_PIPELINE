"""
Module 2: media_collector.py
─────────────────────────────
Downloads free B-roll video clips from:
  - Pexels (free API, 200 req/hr, HD video)
  - Pixabay (free API, no rate limit stated)

Picks the best clips based on script keywords.
Falls back to images if no video found.
"""

import os
import time
import requests
import random
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

ASSETS_DIR = Path("output/assets")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

PEXELS_BASE = "https://api.pexels.com/videos/search"
PIXABAY_BASE = "https://pixabay.com/api/videos/"
PIXABAY_IMG_BASE = "https://pixabay.com/api/"


def _download_file(url: str, dest_path: Path) -> bool:
    """Download a file from a URL to dest_path."""
    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info(f"Downloaded: {dest_path.name}")
        return True
    except Exception as e:
        logger.warning(f"Download failed for {url}: {e}")
        return False


def search_pexels_videos(keyword: str, count: int = 3) -> list[Path]:
    """
    Search Pexels for free stock video clips.
    Returns list of downloaded file paths.
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        logger.warning("No PEXELS_API_KEY found, skipping Pexels")
        return []

    headers = {"Authorization": api_key}
    params = {
        "query": keyword,
        "per_page": count + 3,  # request a few extra for fallback
        "orientation": "portrait",  # 9:16 for shorts
        "size": "medium",
    }

    try:
        resp = requests.get(PEXELS_BASE, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"Pexels API error: {e}")
        return []

    paths = []
    videos = data.get("videos", [])[:count]

    for i, video in enumerate(videos):
        # pick the HD file (720p or 1080p)
        video_files = video.get("video_files", [])
        # sort by quality, prefer 720p or 1080p
        hd_files = [
            vf for vf in video_files
            if vf.get("quality") in ("hd", "sd") and vf.get("link")
        ]
        if not hd_files:
            continue

        # pick portrait orientation if available, else just grab the first
        portrait = [vf for vf in hd_files if vf.get("width", 0) < vf.get("height", 1)]
        chosen = portrait[0] if portrait else hd_files[0]
        url = chosen["link"]

        safe_kw = keyword.replace(" ", "_")[:30]
        dest = ASSETS_DIR / f"pexels_{safe_kw}_{i}.mp4"

        if _download_file(url, dest):
            paths.append(dest)

    logger.info(f"Pexels: downloaded {len(paths)} clips for '{keyword}'")
    return paths


def search_pixabay_videos(keyword: str, count: int = 2) -> list[Path]:
    """
    Search Pixabay for free stock video clips.
    """
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        logger.warning("No PIXABAY_API_KEY found, skipping Pixabay")
        return []

    params = {
        "key": api_key,
        "q": keyword,
        "video_type": "film",
        "per_page": count + 2,
        "safesearch": "true",
    }

    try:
        resp = requests.get(PIXABAY_BASE, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"Pixabay API error: {e}")
        return []

    paths = []
    hits = data.get("hits", [])[:count]

    for i, hit in enumerate(hits):
        videos = hit.get("videos", {})
        # prefer medium quality for faster download
        chosen = videos.get("medium") or videos.get("large") or videos.get("small")
        if not chosen:
            continue

        url = chosen.get("url")
        if not url:
            continue

        safe_kw = keyword.replace(" ", "_")[:30]
        dest = ASSETS_DIR / f"pixabay_{safe_kw}_{i}.mp4"

        if _download_file(url, dest):
            paths.append(dest)

    logger.info(f"Pixabay: downloaded {len(paths)} clips for '{keyword}'")
    return paths


def collect_media_for_script(keywords: list[str], clips_needed: int = 6) -> list[Path]:
    """
    Main function — collect enough B-roll clips for the full video.
    Tries multiple keywords until we have enough clips.
    Returns list of video file paths.
    """
    all_clips = []
    clips_per_keyword = max(2, clips_needed // len(keywords))

    for keyword in keywords:
        if len(all_clips) >= clips_needed:
            break

        logger.info(f"Searching media for keyword: '{keyword}'")

        # Try Pexels first (better quality)
        pexels_clips = search_pexels_videos(keyword, count=clips_per_keyword)
        all_clips.extend(pexels_clips)

        # Add Pixabay clips if we still need more
        if len(all_clips) < clips_needed:
            pixabay_clips = search_pixabay_videos(keyword, count=2)
            all_clips.extend(pixabay_clips)

        # Small delay to respect rate limits
        time.sleep(0.5)

    # deduplicate (same file downloaded twice edge case)
    seen = set()
    unique_clips = []
    for clip in all_clips:
        if clip not in seen:
            seen.add(clip)
            unique_clips.append(clip)

    logger.info(f"Total clips collected: {len(unique_clips)}")

    if len(unique_clips) == 0:
        logger.error("No clips downloaded! Check your API keys in .env")

    return unique_clips[:clips_needed]


if __name__ == "__main__":
    # Quick test
    keywords = ["space", "galaxy", "stars", "universe", "astronaut"]
    clips = collect_media_for_script(keywords, clips_needed=5)
    print(f"\nDownloaded clips:")
    for c in clips:
        print(f"  {c}")
