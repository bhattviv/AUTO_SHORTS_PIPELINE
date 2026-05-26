"""
Module 1: topic_generator.py
─────────────────────────────
Uses Gemini (free) or Groq (free) to:
  1. Pick a random food character and emotion
  2. Write a 30–45 second Hindi food character talking video script

No paid tier needed. Both APIs have generous free quotas.
"""

import os
import json
import random
import warnings
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ── Food characters for Hindi talking videos ──────────────────────────────
FOOD_CHARACTERS = [
    "Samosa", "Jalebi", "Maggi", "Chocolate", "Pizza", "Burger",
    "Broccoli", "Paneer", "Chai", "Biryani", "Dosa", "Gulab Jamun",
    "Ice Cream", "Bread", "Butter", "Aloo", "Mango", "Banana",
    "Pakora", "Ladoo", "Pani Puri", "Idli", "Paratha", "Rasgulla"
]

EMOTIONS = [
    "pleading not to be eaten",
    "boasting about being the best food",
    "jealous of another food",
    "sad because nobody chose them",
    "angry at being ignored",
    "excited to be eaten",
    "crying because they are going stale",
    "arguing with another food",
    "proud of their taste",
    "nervous before being cooked",
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
        model="llama3-8b-8192",
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
    """Pick a random food character and emotion."""
    character = random.choice(FOOD_CHARACTERS)
    emotion = random.choice(EMOTIONS)
    topic = f"{character} {emotion}"
    logger.info(f"Generated topic: {topic}")
    return topic


def generate_script(topic: str) -> dict:
    """
    Generate a Hindi food character talking video script.
    """
    parts = topic.split(" ", 1)
    character = parts[0]
    emotion = parts[1] if len(parts) > 1 else "pleading not to be eaten"

    prompt = f"""
Tu ek viral Hindi short-form video scriptwriter hai jo food character talking videos banata hai.

Food character: {character}
Character ki feeling: {emotion}

Ek funny aur emotional script likho jisme {character} khud bolta hai — first person mein, Hindi mein.
Script bilkul natural Hinglish ho sakti hai (Hindi + thoda English mix).
Character apni feelings express kare, jaise woh sach mein bol raha ho.

STRICT FORMAT — sirf valid JSON return karo, koi markdown nahi:
{{
  "title": "Video title Hindi mein (max 60 chars)",
  "hook": "Pehli 2 second ki line jo log rok de — shocking ya funny",
  "body": "Character ki main baat — 4-5 punchy sentences, emotional ya funny",
  "cta": "End mein call to action Hindi mein",
  "full_script": "Hook + body + CTA mila ke, natural bolne wali Hindi, 60-90 words",
  "keywords": ["food", "{character.lower()}", "hindi", "funny", "viral"],
  "description": "YouTube description Hindi mein with hashtags"
}}

Requirements:
- full_script mein {character} khud bol raha ho, first person mein
- Emotional, funny aur relatable ho
- Hinglish chalega — Hindi main rakho, thoda English mix kar sakte ho
- Har sentence impactful ho, filler words nahi
- 30-45 seconds ka script ho
"""
    raw = call_llm(prompt).strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        script_data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned malformed JSON, attempting repair...")
        script_data = {
            "title": topic[:60],
            "hook": f"Yaar, main {character} hoon aur mujhe baat karni hai...",
            "body": raw[:400],
            "cta": "Follow karo aur share karo!",
            "full_script": raw[:500],
            "keywords": ["food", character.lower(), "hindi", "funny", "viral"],
            "description": f"{character} ki kahani #hindi #funny #shorts #food",
        }

    logger.info(f"Script generated — title: {script_data.get('title')}")
    logger.info(f"Word count: {len(script_data.get('full_script','').split())} words")
    return script_data


if __name__ == "__main__":
    # Quick test
    topic = generate_topic()
    print(f"\nTopic: {topic}\n")
    script = generate_script(topic)
    print(json.dumps(script, indent=2, ensure_ascii=False))