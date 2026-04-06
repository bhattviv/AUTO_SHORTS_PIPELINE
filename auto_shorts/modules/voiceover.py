"""
Module 3: voiceover.py
───────────────────────
Generates voiceover audio using COMPLETELY FREE TTS:

  Option A: edge-tts (default)
    - Uses Microsoft Edge's neural TTS
    - No API key, no account needed
    - 300+ voices in 70+ languages
    - Quality is surprisingly good (neural voices)

  Option B: kokoro-tts (local)
    - Open-source model, runs on your GPU/CPU
    - Zero internet dependency after install
    - Install: pip install kokoro-onnx soundfile

Returns path to generated .mp3 or .wav file.
"""

import os
import asyncio
import subprocess
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

AUDIO_DIR = Path("output/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Best edge-tts voices (all free):
VOICE_OPTIONS = {
    "male_us":     "en-US-GuyNeural",
    "female_us":   "en-US-AriaNeural",       # default — sounds most natural
    "male_uk":     "en-GB-RyanNeural",
    "female_uk":   "en-GB-SoniaNeural",
    "male_au":     "en-AU-NathanNeural",
    "female_au":   "en-AU-NatashaNeural",
}


async def _edge_tts_async(text: str, voice: str, output_path: Path) -> Path:
    """Async edge-tts call."""
    import edge_tts

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="+8%",    # slightly faster — good for short-form video
        pitch="+0Hz",
        volume="+0%",
    )
    await communicate.save(str(output_path))
    return output_path


def generate_voiceover_edge(script: str, output_filename: str = "voiceover.mp3") -> Path:
    """
    Generate voiceover using edge-tts (free, no API key).
    This is the default and recommended method.
    """
    voice = os.getenv("TTS_VOICE", "en-US-AriaNeural")
    output_path = AUDIO_DIR / output_filename

    logger.info(f"Generating voiceover with edge-tts, voice: {voice}")
    logger.info(f"Script length: {len(script.split())} words")

    # edge-tts is async, run it
    asyncio.run(_edge_tts_async(script, voice, output_path))

    if output_path.exists():
        size_kb = output_path.stat().st_size / 1024
        logger.info(f"Voiceover saved: {output_path} ({size_kb:.1f} KB)")
    else:
        raise FileNotFoundError("edge-tts failed to generate audio file")

    return output_path


def generate_voiceover_kokoro(script: str, output_filename: str = "voiceover.wav") -> Path:
    """
    Generate voiceover using Kokoro (local open-source model).
    Higher quality than edge-tts but requires more setup.
    
    Setup:
      pip install kokoro-onnx soundfile
      # Downloads ~82MB model on first run
    """
    try:
        import soundfile as sf
        from kokoro_onnx import Kokoro
    except ImportError:
        logger.error(
            "kokoro-onnx not installed. Run: pip install kokoro-onnx soundfile\n"
            "Falling back to edge-tts..."
        )
        return generate_voiceover_edge(script, output_filename.replace(".wav", ".mp3"))

    output_path = AUDIO_DIR / output_filename
    logger.info("Generating voiceover with Kokoro (local model)...")

    kokoro = Kokoro("kokoro-v0_19.onnx", "voices.bin")
    samples, sample_rate = kokoro.create(
        script,
        voice="af_bella",  # good English voice
        speed=1.1,          # slightly faster for short-form
        lang="en-us",
    )

    sf.write(str(output_path), samples, sample_rate)
    logger.info(f"Kokoro voiceover saved: {output_path}")
    return output_path


def generate_voiceover(script: str, run_id: str = "video") -> Path:
    """
    Main entry point. Picks engine from .env TTS_ENGINE setting.
    Automatically falls back to edge-tts if anything fails.
    """
    engine = os.getenv("TTS_ENGINE", "edge").lower()
    filename = f"voiceover_{run_id}.mp3"

    try:
        if engine == "kokoro":
            return generate_voiceover_kokoro(script, filename.replace(".mp3", ".wav"))
        else:
            return generate_voiceover_edge(script, filename)
    except Exception as e:
        logger.error(f"TTS failed with engine '{engine}': {e}")
        if engine != "edge":
            logger.info("Falling back to edge-tts...")
            return generate_voiceover_edge(script, filename)
        raise


def get_audio_duration(audio_path: Path) -> float:
    """Return audio duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
        raise RuntimeError(result.stderr.strip() or "ffprobe returned no duration")
    except Exception as e:
        logger.warning(f"Could not get audio duration: {e}")
        return 45.0  # assume 45 seconds as fallback


if __name__ == "__main__":
    test_script = """
    Did you know Saturn's rings are actually disappearing? 
    Scientists discovered that the rings are being pulled into Saturn 
    by its own gravity at a rate that will make them completely vanish 
    in just 100 million years. That sounds like a long time, but in 
    cosmic terms, it's basically tomorrow. The rings we see today are 
    actually relatively young — only 10 to 100 million years old. 
    So we're living in a rare window of time to witness this spectacle. 
    Follow for more mind-blowing space facts!
    """

    path = generate_voiceover(test_script.strip(), run_id="test")
    duration = get_audio_duration(path)
    print(f"\nVoiceover generated: {path}")
    print(f"Duration: {duration:.1f}s")
