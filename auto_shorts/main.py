"""
main.py — The Orchestrator
───────────────────────────
Runs the full pipeline end-to-end:
  1. Generate topic + script
  2. Download B-roll media
  3. Generate voiceover (edge-tts, free)
  4. Generate subtitles (Whisper, local)
  5. Assemble video (FFmpeg + MoviePy)
  6. Upload to YouTube Shorts
  7. Upload to Instagram Reels

Run once:    python main.py
Run on a schedule: the scheduler at bottom handles this automatically
"""

import os
import sys
import uuid
import traceback
import shutil
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def _ensure_ffmpeg_on_path() -> None:
    """Make ffmpeg/ffprobe visible to subprocesses on Windows."""
    ffmpeg_bin = os.getenv("FFMPEG_BIN", r"C:\ffmpeg\bin")

    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return

    ffmpeg_path = Path(ffmpeg_bin)
    if ffmpeg_path.exists():
        os.environ["PATH"] = str(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")


_ensure_ffmpeg_on_path()

# ── Configure logging ──────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logger.remove()
logger.add(sys.stderr, level=os.getenv("LOG_LEVEL", "INFO"))
logger.add(
    f"logs/pipeline_{datetime.now().strftime('%Y%m%d')}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
)

# ── Import pipeline modules ────────────────────────────────────────────────
from modules.topic_generator import generate_topic, generate_script
from modules.media_collector import collect_media_for_script
from modules.voiceover import generate_voiceover, get_audio_duration
from modules.subtitle_generator import generate_subtitles
from modules.video_assembler import assemble_video
from modules.youtube_uploader import upload_to_youtube
from modules.instagram_uploader import upload_to_instagram


def run_pipeline(
    upload_youtube: bool = True,
    upload_instagram: bool = True,
    bgm_path: Path = None,
    whisper_model: str = "base",
) -> dict:
    """
    Runs the full video creation and upload pipeline.
    
    Args:
        upload_youtube: Whether to upload to YouTube
        upload_instagram: Whether to upload to Instagram
        bgm_path: Optional background music file path
        whisper_model: Whisper model size for transcription
    
    Returns:
        dict with status and URLs of uploaded videos
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    result = {
        "run_id": run_id,
        "status": "running",
        "topic": None,
        "youtube_id": None,
        "instagram_id": None,
        "video_path": None,
        "errors": [],
    }

    logger.info(f"{'='*50}")
    logger.info(f"Starting pipeline — run_id: {run_id}")
    logger.info(f"{'='*50}")

    try:
        # ── Step 1: Generate topic and script ──────────────────────────────
        logger.info("STEP 1/7: Generating topic and script...")
        topic = generate_topic()
        script_data = generate_script(topic)
        result["topic"] = topic

        logger.info(f"Topic: {topic}")
        logger.info(f"Script word count: {len(script_data['full_script'].split())}")

        # ── Step 2: Collect B-roll media ───────────────────────────────────
        logger.info("STEP 2/7: Collecting B-roll media...")
        keywords = script_data.get("keywords", topic.split()[:5])
        clips = collect_media_for_script(keywords, clips_needed=6)

        if not clips:
            raise RuntimeError(
                "No B-roll clips downloaded. "
                "Check PEXELS_API_KEY and PIXABAY_API_KEY in .env"
            )

        logger.info(f"Collected {len(clips)} clips")

        # ── Step 3: Generate voiceover ─────────────────────────────────────
        logger.info("STEP 3/7: Generating voiceover...")
        voiceover_path = generate_voiceover(script_data["full_script"], run_id=run_id)
        duration = get_audio_duration(voiceover_path)
        logger.info(f"Voiceover: {voiceover_path.name} ({duration:.1f}s)")

        # ── Step 4: Generate subtitles ─────────────────────────────────────
        logger.info("STEP 4/7: Generating subtitles with Whisper...")
        srt_path = generate_subtitles(
            voiceover_path,
            run_id=run_id,
            whisper_model=whisper_model,
        )
        logger.info(f"Subtitles: {srt_path.name}")

        # ── Step 5: Assemble video ─────────────────────────────────────────
        logger.info("STEP 5/7: Assembling video...")
        video_path = assemble_video(
            clips=clips,
            voiceover_path=voiceover_path,
            srt_path=srt_path,
            run_id=run_id,
            bgm_path=bgm_path,
        )
        result["video_path"] = str(video_path)
        logger.info(f"Video assembled: {video_path.name}")

        # ── Step 6: Upload to YouTube ──────────────────────────────────────
        if upload_youtube:
            logger.info("STEP 6/7: Uploading to YouTube Shorts...")
            try:
                yt_id = upload_to_youtube(
                    video_path=video_path,
                    title=script_data["title"],
                    description=script_data.get("description", topic),
                    keywords=script_data.get("keywords", []),
                )
                result["youtube_id"] = yt_id
                logger.info(f"YouTube: https://youtube.com/shorts/{yt_id}")
            except Exception as e:
                logger.error(f"YouTube upload failed: {e}")
                result["errors"].append(f"YouTube: {str(e)}")
        else:
            logger.info("STEP 6/7: YouTube upload skipped")

        # ── Step 7: Upload to Instagram ────────────────────────────────────
        if upload_instagram:
            logger.info("STEP 7/7: Uploading to Instagram Reels...")
            try:
                ig_id = upload_to_instagram(
                    video_path=video_path,
                    caption=script_data["title"] + "\n\n" + script_data.get("description", ""),
                    hashtags=script_data.get("keywords", []),
                )
                result["instagram_id"] = ig_id
                logger.info(f"Instagram Reel published: {ig_id}")
            except Exception as e:
                logger.error(f"Instagram upload failed: {e}")
                result["errors"].append(f"Instagram: {str(e)}")
        else:
            logger.info("STEP 7/7: Instagram upload skipped")

        result["status"] = "success" if not result["errors"] else "partial"

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        logger.debug(traceback.format_exc())
        result["status"] = "failed"
        result["errors"].append(str(e))

    logger.info(f"{'='*50}")
    logger.info(f"Pipeline complete — status: {result['status']}")
    if result.get("youtube_id"):
        logger.info(f"YouTube: https://youtube.com/shorts/{result['youtube_id']}")
    if result.get("instagram_id"):
        logger.info(f"Instagram ID: {result['instagram_id']}")
    logger.info(f"{'='*50}")

    return result


def run_scheduler():
    """
    Run the pipeline on a schedule using APScheduler.
    Set SCHEDULE_INTERVAL_HOURS in .env (default: 24 = once daily)
    """
    from apscheduler.schedulers.blocking import BlockingScheduler

    interval_hours = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "24"))

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_pipeline,
        "interval",
        hours=interval_hours,
        id="video_pipeline",
        name=f"Auto Video Pipeline (every {interval_hours}h)",
        max_instances=1,  # never run two at once
        coalesce=True,    # if missed, run once (not catch-up)
    )

    logger.info(f"Scheduler started — running every {interval_hours} hour(s)")
    logger.info("Press Ctrl+C to stop")

    # Run once immediately on start, then on schedule
    logger.info("Running first job immediately...")
    run_pipeline()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Auto Shorts Pipeline — generate and upload videos automatically"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run on a schedule (set interval in .env SCHEDULE_INTERVAL_HOURS)",
    )
    parser.add_argument(
        "--no-youtube",
        action="store_true",
        help="Skip YouTube upload",
    )
    parser.add_argument(
        "--no-instagram",
        action="store_true",
        help="Skip Instagram upload",
    )
    parser.add_argument(
        "--bgm",
        type=str,
        default=None,
        help="Path to background music file (.mp3 or .wav)",
    )
    parser.add_argument(
        "--whisper-model",
        type=str,
        default="base",
        choices=["tiny", "base", "small", "medium"],
        help="Whisper model size for subtitle generation",
    )

    args = parser.parse_args()

    if args.schedule:
        run_scheduler()
    else:
        result = run_pipeline(
            upload_youtube=not args.no_youtube,
            upload_instagram=not args.no_instagram,
            bgm_path=Path(args.bgm) if args.bgm else None,
            whisper_model=args.whisper_model,
        )
        sys.exit(0 if result["status"] in ("success", "partial") else 1)
