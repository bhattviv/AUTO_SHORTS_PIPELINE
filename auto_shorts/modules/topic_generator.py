"""
Module 1: topic_generator.py
─────────────────────────────
Uses Gemini (free) or Groq (free) to:
  1. Pick a random engaging topic
  2. Write a 30–60 second short-form video script
     with hook → body → CTA structure

No paid tier needed. Both APIs have generous free quotas.
"""

import os
import json
import random
import warnings
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ── Topic categories (the AI picks freely within these) ──────────────────────
TOPIC_POOLS = [
    "mind-blowing science facts",
    "surprising history moments",
    "psychology tricks and biases",
    "space and universe facts",
    "animal world records",
    "ancient civilizations",
    "future technology predictions",
    "life hacks backed by science",
    "famous unsolved mysteries",
    "economics explained simply",
    "philosophy concepts in 60 seconds",
    "interesting language facts",
    "world record breaking moments",
    "optical illusions explained",
    "biology facts that sound fake",
]


def _call_gemini(prompt: str) -> str:
    """Call Gemini free tier (Google AI Studio key)."""
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = os.getenv("GEMINI_API_KEY")

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        return response.text or ""
    except ImportError:
        logger.warning(
            "google-genai is not installed yet; falling back to deprecated "
            "google-generativeai SDK. Run 'pip install -r requirements.txt' "
            "to upgrade when convenient."
        )

    warnings.filterwarnings(
        "ignore",
        category=FutureWarning,
        module=r"google\.generativeai",
    )
    import google.generativeai as legacy_genai

    legacy_genai.configure(api_key=api_key)
    model = legacy_genai.GenerativeModel(model_name)
    response = model.generate_content(prompt)
    return response.text


def _call_groq(prompt: str) -> str:
    """Call Groq free tier (llama3-8b is free with generous limits)."""
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama3-8b-8192",  # free model on Groq
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=1024,
    )
    return response.choices[0].message.content


def call_llm(prompt: str) -> str:
    """Route to whichever LLM provider is set in .env."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "groq":
        return _call_groq(prompt)
    return _call_gemini(prompt)


def generate_topic() -> str:
    """Ask the LLM to pick a specific, interesting video topic."""
    category = random.choice(TOPIC_POOLS)
    prompt = f"""
You are a viral short-form video content strategist.
Pick ONE very specific, surprising, and engaging topic from the category: "{category}"

Rules:
- Be extremely specific (not just "space facts" but "why Saturn's rings are disappearing")
- It must work as a 40–55 second YouTube Short or Instagram Reel
- Make it sound irresistible to click on
- Return ONLY the topic title, nothing else. No quotes, no explanation.
"""
    topic = call_llm(prompt).strip().strip('"').strip("'")
    logger.info(f"Generated topic: {topic}")
    return topic


def generate_script(topic: str) -> dict:
    """
    Generate a full short-form video script for the topic.
    Returns a dict with: title, hook, body, cta, full_script, keywords
    """
    prompt = f"""
You are a viral short-form video scriptwriter. Write a script for this topic:
"{topic}"

STRICT FORMAT — return valid JSON only, no markdown, no extra text:
{{
  "title": "YouTube/Instagram video title (max 60 chars, no clickbait)",
  "hook": "Opening line that GRABS attention in first 3 seconds (1–2 sentences)",
  "body": "Core content — 3 to 5 punchy sentences with the actual information",
  "cta": "End call-to-action (e.g. Follow for more, Comment below, etc.)",
  "full_script": "Hook + body + CTA combined, natural speaking flow, 80–120 words total",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "description": "YouTube/Instagram description with hashtags (150 words max)"
}}

Requirements:
- full_script should take 40–55 seconds to speak at normal pace
- No filler words. Every sentence must earn its place.
- keywords are for finding B-roll stock footage
"""
    raw = call_llm(prompt).strip()

    # strip markdown code blocks if LLM wraps in them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        script_data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned malformed JSON, attempting repair...")
        # fallback: wrap the raw text into a basic structure
        script_data = {
            "title": topic[:60],
            "hook": "Here's something you probably never knew...",
            "body": raw[:400],
            "cta": "Follow for more mind-blowing facts!",
            "full_script": raw[:500],
            "keywords": topic.lower().split()[:5],
            "description": f"{topic} #facts #shorts #didyouknow",
        }

    logger.info(f"Script generated — title: {script_data.get('title')}")
    logger.info(f"Word count: {len(script_data.get('full_script','').split())} words")
    return script_data


if __name__ == "__main__":
    # Quick test
    topic = generate_topic()
    print(f"\nTopic: {topic}\n")
    script = generate_script(topic)
    print(json.dumps(script, indent=2))
