"""
Module 4: subtitle_generator.py
─────────────────────────────────
Uses OpenAI Whisper (runs LOCALLY — free forever, no API call)
to transcribe the voiceover and generate .srt subtitle files.

Whisper sizes (all free):
  tiny   — fastest, lower accuracy, good for English
  base   — good balance, recommended default
  small  — better accuracy, ~500MB RAM
  medium — near-perfect, ~1.5GB RAM (use if you have GPU)

The .srt file is then burned into the video by the assembler module.
"""

import os
import re
from pathlib import Path
from loguru import logger

SUBS_DIR = Path("output/subtitles")
SUBS_DIR.mkdir(parents=True, exist_ok=True)


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _segments_to_srt(segments: list[dict]) -> str:
    """Convert Whisper segments to SRT format string."""
    srt_lines = []
    for i, seg in enumerate(segments, start=1):
        start = _seconds_to_srt_time(seg["start"])
        end = _seconds_to_srt_time(seg["end"])
        text = seg["text"].strip()
        srt_lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(srt_lines)


def _chunk_long_segments(segments: list[dict], max_chars: int = 60) -> list[dict]:
    """
    Break long subtitle lines into shorter chunks.
    Short-form video subtitles should be max 6-8 words per line.
    """
    chunked = []
    for seg in segments:
        text = seg["text"].strip()
        words = text.split()

        if len(text) <= max_chars:
            chunked.append(seg)
            continue

        # split into roughly equal halves
        mid = len(words) // 2
        duration = seg["end"] - seg["start"]

        chunked.append({
            "start": seg["start"],
            "end": seg["start"] + duration * 0.5,
            "text": " ".join(words[:mid]),
        })
        chunked.append({
            "start": seg["start"] + duration * 0.5,
            "end": seg["end"],
            "text": " ".join(words[mid:]),
        })

    return chunked


def generate_subtitles(
    audio_path: Path,
    run_id: str = "video",
    whisper_model: str = "base",
) -> Path:
    """
    Transcribe audio using local Whisper and save as .srt file.

    Args:
        audio_path: Path to the voiceover audio file
        run_id: Unique ID for this video run
        whisper_model: Whisper model size ("tiny", "base", "small", "medium")

    Returns:
        Path to the generated .srt file
    """
    try:
        import whisper
    except ImportError:
        raise ImportError(
            "Whisper not installed. Run: pip install openai-whisper"
        )

    srt_path = SUBS_DIR / f"subtitles_{run_id}.srt"

    logger.info(f"Loading Whisper model: {whisper_model}")
    logger.info("(First run downloads the model — ~74MB for 'base', one-time only)")

    model = whisper.load_model(whisper_model)

    logger.info(f"Transcribing: {audio_path.name}")
    result = model.transcribe(
        str(audio_path),
        language="hi",
        word_timestamps=False,  # segment-level is enough for SRT
        verbose=False,
    )

    segments = result.get("segments", [])

    if not segments:
        logger.warning("Whisper returned no segments — creating fallback subtitle")
        # create one subtitle covering the whole audio
        segments = [{
            "start": 0.0,
            "end": 50.0,
            "text": result.get("text", ""),
        }]

    # break long lines into shorter chunks for readability
    segments = _chunk_long_segments(segments, max_chars=55)

    # write the .srt file
    srt_content = _segments_to_srt(segments)
    srt_path.write_text(srt_content, encoding="utf-8")

    logger.info(f"Subtitles saved: {srt_path} ({len(segments)} segments)")
    return srt_path


def create_subtitle_style_filter(srt_path: Path) -> str:
    """
    Returns an FFmpeg subtitle filter string with nice styling for Shorts.
    Subtitles are white bold text with black border — works on any background.
    """
    # FFmpeg subtitles filter with style overrides
    # Position at bottom-center with large, readable text
    style = (
        "FontName=Arial,"
        "FontSize=18,"
        "PrimaryColour=&H00FFFFFF,"   # white text
        "OutlineColour=&H00000000,"   # black outline
        "BackColour=&H80000000,"      # semi-transparent black bg
        "Bold=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"               # center bottom
        "MarginV=40"                 # margin from bottom
    )
    escaped_path = str(srt_path).replace("\\", "/").replace(":", "\\:")
    return f"subtitles='{escaped_path}':force_style='{style}'"


if __name__ == "__main__":
    # Quick test — needs a real audio file to run
    import sys
    if len(sys.argv) < 2:
        print("Usage: python subtitle_generator.py path/to/audio.mp3")
        sys.exit(1)

    audio = Path(sys.argv[1])
    srt = generate_subtitles(audio, run_id="test", whisper_model="base")
    print(f"\nSubtitles: {srt}")
    print("\nContent preview:")
    print(srt.read_text()[:500])
