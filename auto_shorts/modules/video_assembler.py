"""
Module 5: video_assembler.py
─────────────────────────────
Assembles the final Short/Reel video using MoviePy + FFmpeg.

Pipeline:
  1. Load B-roll clips and trim/resize to 9:16 (1080x1920)
  2. Loop/extend clips to match voiceover duration
  3. Overlay voiceover audio
  4. Add background music at low volume (from local royalty-free file)
  5. Burn in subtitles via FFmpeg
  6. Export final .mp4

Output: 1080x1920 @ 30fps, H.264, AAC audio — ready for upload
"""

import os
import subprocess
import random
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

VIDEO_DIR = Path("output/videos")
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Target dimensions for Shorts/Reels
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30


def _get_video_duration(clip_path: Path) -> float:
    """Get video duration in seconds using FFprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(clip_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 10.0  # default fallback


def _get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 45.0


def _prepare_clip(clip_path: Path, duration: float, index: int) -> Path:
    """
    Resize and crop a single clip to 9:16, trim to `duration` seconds.
    Uses FFmpeg's crop filter for smart center-crop.
    """
    out_path = VIDEO_DIR / f"_prepared_{index}.mp4"

    # FFmpeg filter: scale to fill 1080x1920, then center-crop
    # scale=w to fill height, then crop width
    vf = (
        f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_WIDTH}:{TARGET_HEIGHT},"
        f"fps={TARGET_FPS}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",               # remove original audio from clip
        str(out_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.warning(f"FFmpeg clip prep failed for {clip_path.name}: {result.stderr[-200:]}")
        return None

    return out_path


def _create_concat_video(clip_paths: list[Path], target_duration: float) -> Path:
    """
    Concatenate clips and loop them to fill target_duration.
    """
    concat_path = VIDEO_DIR / "_concat.mp4"
    
    # Build concat list file
    concat_list = VIDEO_DIR / "_concat_list.txt"
    
    # Figure out how many times to loop through clips
    total_clip_duration = sum(_get_video_duration(p) for p in clip_paths if p and p.exists())
    if total_clip_duration == 0:
        raise ValueError("No valid clips to assemble")
    
    loops_needed = max(1, int(target_duration / total_clip_duration) + 1)
    
    with open(concat_list, "w") as f:
        for _ in range(loops_needed):
            for clip in clip_paths:
                if clip and clip.exists():
                    f.write(f"file '{clip.absolute()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-t", str(target_duration),
        "-c", "copy",
        str(concat_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(f"Concat failed: {result.stderr[-300:]}")

    return concat_path


def _mix_audio(voiceover_path: Path, target_duration: float, bgm_path: Path = None) -> Path:
    """
    Mix voiceover with optional background music.
    BGM is lowered to 8% volume so voiceover is always clear.
    """
    mixed_path = VIDEO_DIR / "_mixed_audio.aac"

    if bgm_path and bgm_path.exists():
        logger.info(f"Mixing BGM: {bgm_path.name} at 8% volume")
        # Mix: voiceover full volume + BGM at 8%
        cmd = [
            "ffmpeg", "-y",
            "-i", str(voiceover_path),
            "-i", str(bgm_path),
            "-filter_complex",
            f"[1:a]volume=0.08,aloop=loop=-1:size=2e+09,atrim=duration={target_duration}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first[out]",
            "-map", "[out]",
            "-t", str(target_duration),
            "-c:a", "aac",
            "-b:a", "128k",
            str(mixed_path)
        ]
    else:
        # Just convert voiceover to AAC
        cmd = [
            "ffmpeg", "-y",
            "-i", str(voiceover_path),
            "-t", str(target_duration),
            "-c:a", "aac",
            "-b:a", "128k",
            str(mixed_path)
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.warning(f"Audio mix warning: {result.stderr[-200:]}")

    return mixed_path if mixed_path.exists() else voiceover_path


def _burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> Path:
    """
    Burn subtitles into the video using FFmpeg's subtitles filter.
    White bold text with black outline — readable on any background.
    """
    # Escape the path for FFmpeg on Windows
    srt_escaped = str(srt_path.absolute()).replace("\\", "/")
    if ":" in srt_escaped:
        # Windows drive letter handling
        parts = srt_escaped.split(":", 1)
        srt_escaped = parts[0] + "\\:" + parts[1]

    style = (
        "FontName=Arial,"
        "FontSize=16,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BackColour=&H60000000,"
        "Bold=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=50"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"subtitles='{srt_escaped}':force_style='{style}'",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "copy",
        str(output_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.warning(f"Subtitle burn failed: {result.stderr[-200:]}")
        logger.warning("Proceeding without burned subtitles...")
        # Return video without subtitles as fallback
        import shutil
        shutil.copy(str(video_path), str(output_path))

    return output_path


def _merge_video_audio(video_path: Path, audio_path: Path) -> Path:
    """Merge video (no audio) with the mixed audio track."""
    merged_path = VIDEO_DIR / "_merged.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "copy",
        "-shortest",
        str(merged_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Merge failed: {result.stderr[-300:]}")
    return merged_path


def assemble_video(
    clips: list[Path],
    voiceover_path: Path,
    srt_path: Path,
    run_id: str = "video",
    bgm_path: Path = None,
) -> Path:
    """
    Full pipeline: clips + voiceover + subtitles → final .mp4

    Args:
        clips: List of downloaded B-roll video files
        voiceover_path: Path to TTS audio file
        srt_path: Path to .srt subtitle file
        run_id: Unique ID for naming output
        bgm_path: Optional background music file

    Returns:
        Path to final rendered video
    """
    final_output = VIDEO_DIR / f"short_{run_id}.mp4"

    logger.info(f"Starting video assembly — {len(clips)} clips")

    # Step 1: Get target duration from voiceover
    target_duration = _get_audio_duration(voiceover_path)
    logger.info(f"Target duration: {target_duration:.1f}s")

    # Step 2: Prepare each clip (resize to 9:16, remove audio)
    prepared_clips = []
    per_clip_duration = max(3.0, target_duration / max(len(clips), 1))

    for i, clip in enumerate(clips):
        logger.info(f"Preparing clip {i+1}/{len(clips)}: {clip.name}")
        prepared = _prepare_clip(clip, per_clip_duration, i)
        if prepared:
            prepared_clips.append(prepared)

    if not prepared_clips:
        raise RuntimeError("All clip preparation failed — check FFmpeg installation")

    # Step 3: Concatenate + loop clips to fill target duration
    logger.info("Concatenating clips...")
    concat_video = _create_concat_video(prepared_clips, target_duration)

    # Step 4: Mix audio (voiceover + optional BGM)
    logger.info("Mixing audio...")
    mixed_audio = _mix_audio(voiceover_path, target_duration, bgm_path)

    # Step 5: Merge video + audio
    logger.info("Merging video and audio...")
    merged = _merge_video_audio(concat_video, mixed_audio)

    # Step 6: Burn in subtitles
    logger.info("Burning subtitles...")
    _burn_subtitles(merged, srt_path, final_output)

    # Cleanup temp files
    for temp in [concat_video, mixed_audio, merged]:
        if temp.exists():
            temp.unlink()
    for clip in prepared_clips:
        if clip.exists():
            clip.unlink()

    size_mb = final_output.stat().st_size / (1024 * 1024)
    logger.info(f"Final video: {final_output} ({size_mb:.1f} MB)")
    return final_output


if __name__ == "__main__":
    print("Video assembler module loaded. Run from main.py for full pipeline.")
    print("FFmpeg check:")
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if result.returncode == 0:
        print("FFmpeg is installed!")
    else:
        print("FFmpeg NOT found — install from https://ffmpeg.org/download.html")
