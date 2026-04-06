# Auto Shorts Pipeline
### Fully automated YouTube Shorts + Instagram Reels — 100% free

---

## What this does
Runs on a schedule → generates a random video topic → writes a script → downloads B-roll → 
creates voiceover → adds subtitles → assembles a 9:16 Short → uploads to YouTube and Instagram. 
Zero manual work after setup.

---

## Prerequisites

- Python 3.10+
- FFmpeg installed and in PATH
- Git

### Install FFmpeg

**Windows:**
```
winget install ffmpeg
```
Or download from https://ffmpeg.org/download.html → add to PATH

**Linux/Mac:**
```bash
sudo apt install ffmpeg       # Ubuntu/Debian
brew install ffmpeg           # Mac
```

---

## Step-by-step setup

### 1. Clone and install

```bash
git clone your-repo-url
cd auto_shorts
pip install -r requirements.txt
```

### 2. Copy .env and fill it in

```bash
cp .env.example .env
```

Open `.env` and fill in your API keys (see guide below for each).

---

## Getting your free API keys

### A. Gemini API (LLM — script writing)
1. Go to https://aistudio.google.com
2. Click "Get API Key" → Create API key
3. Free tier: 15 req/min, 1500 req/day — more than enough
4. Paste into `.env` as `GEMINI_API_KEY`

### B. Groq API (alternative LLM)
1. Go to https://console.groq.com
2. Sign up → API Keys → Create
3. Free tier: 14,400 req/day on llama3-8b
4. Paste as `GROQ_API_KEY`, set `LLM_PROVIDER=groq`

### C. Pexels API (stock video)
1. Go to https://www.pexels.com/api
2. Click "Get Started" — no credit card
3. Free: 200 req/hour, unlimited total
4. Paste as `PEXELS_API_KEY`

### D. Pixabay API (stock video backup)
1. Go to https://pixabay.com/api/docs
2. Log in → get your API key from the docs page
3. Free: no strict rate limit stated
4. Paste as `PIXABAY_API_KEY`

### E. edge-tts (voiceover) — NO KEY NEEDED
`edge-tts` works out of the box. No account, no key.
Just set `TTS_ENGINE=edge` in .env.

To see all available voices:
```bash
python -c "import asyncio; import edge_tts; asyncio.run(edge_tts.list_voices())" | head -50
```

### F. Whisper (subtitles) — LOCAL, NO KEY NEEDED
Whisper runs on your machine. First run downloads the model (~74MB for "base").
No API calls, no account, free forever.

### G. YouTube Data API
1. Go to https://console.cloud.google.com
2. Create project → APIs & Services → Library
3. Enable "YouTube Data API v3"
4. Credentials → Create → OAuth 2.0 Client ID → Desktop app
5. Download JSON → save as `config/yt_client_secrets.json`
6. Run once to authenticate:
   ```bash
   python modules/youtube_uploader.py
   ```
   (browser opens, log in, done — token saved automatically)

Free quota: 10,000 units/day → ~6 uploads/day

### H. Instagram Graph API
1. Go to https://developers.facebook.com → Create App → Business
2. Add "Instagram Graph API" product
3. Connect your Instagram account (must be Business or Creator)
   - Instagram → Settings → Account → Switch to Professional
   - Link to a Facebook Page
4. In Graph API Explorer: generate token with permissions:
   - `instagram_basic`
   - `instagram_content_publish`
5. Exchange for long-lived token (60 days):
   ```
   GET https://graph.facebook.com/oauth/access_token?
     grant_type=fb_exchange_token&
     client_id=YOUR_APP_ID&
     client_secret=YOUR_APP_SECRET&
     fb_exchange_token=YOUR_SHORT_TOKEN
   ```
6. Get your IG Business ID:
   ```
   GET https://graph.facebook.com/me/accounts?access_token=YOUR_LONG_TOKEN
   ```
   Find `instagram_business_account` → `id`
7. Add both to `.env`

---

## Running the pipeline

### Run once (test)
```bash
# Full pipeline
python main.py

# Skip uploads (just generate video)
python main.py --no-youtube --no-instagram

# Use smaller/faster Whisper model
python main.py --whisper-model tiny

# With background music
python main.py --bgm path/to/music.mp3
```

### Run on a schedule (local machine)
```bash
python main.py --schedule
```
Set `SCHEDULE_INTERVAL_HOURS=24` in .env for daily.

### Run on a schedule (GitHub Actions — recommended)
1. Push project to GitHub (private repo is fine)
2. Go to: Settings → Secrets and variables → Actions
3. Add secrets for all your .env keys PLUS:
   - `YOUTUBE_TOKEN_JSON` — paste contents of `config/yt_token.json`
   - `YOUTUBE_CLIENT_SECRETS_JSON` — paste contents of `config/yt_client_secrets.json`
4. Push `.github/workflows/daily_video.yml`
5. Done — GitHub runs it daily at 9 AM UTC for free

---

## Project structure

```
auto_shorts/
├── main.py                        # Orchestrator — runs everything
├── requirements.txt
├── .env.example                   # Copy to .env, fill in keys
├── .github/
│   └── workflows/
│       └── daily_video.yml        # GitHub Actions scheduler
├── modules/
│   ├── topic_generator.py         # LLM topic + script generation
│   ├── media_collector.py         # Pexels + Pixabay B-roll download
│   ├── voiceover.py               # edge-tts or Kokoro TTS
│   ├── subtitle_generator.py      # Whisper local transcription
│   ├── video_assembler.py         # FFmpeg + MoviePy assembly
│   ├── youtube_uploader.py        # YouTube Data API v3 upload
│   └── instagram_uploader.py      # Instagram Graph API upload
├── config/
│   ├── yt_client_secrets.json     # (you create this)
│   └── yt_token.json              # (auto-generated on first auth)
└── output/
    ├── videos/                    # Final .mp4 files
    ├── audio/                     # Voiceover files
    ├── subtitles/                  # .srt subtitle files
    └── assets/                    # Downloaded B-roll clips
```

---

## Free background music sources

These are CC0/royalty-free, safe for YouTube monetization:
- YouTube Audio Library: https://studio.youtube.com → Audio Library
- Pixabay Music: https://pixabay.com/music (free, no attribution needed)
- Free Music Archive: https://freemusicarchive.org (filter by CC0)
- ccMixter: https://ccmixter.org

Download a few tracks, put them in a `music/` folder, pick randomly in main.py.

---

## Monetization path

Once you have consistent uploads:
1. YouTube Partner Program: 1,000 subscribers + 10M Shorts views (last 90 days)
2. Instagram Reels Bonus: invitation-based, depends on country
3. Brand deals: usually start coming at 5k-10k followers
4. The content is free to make — every dollar is profit

---

## Real limitations (honest answers)

| Thing | Reality |
|---|---|
| YouTube quota | 6 uploads/day max free |
| Gemini free tier | 1,500 req/day — never hits limit for this use |
| B-roll quality | Good but can feel repetitive over time |
| Voice quality | edge-tts is neural — surprisingly good, not perfect |
| Instagram setup | More complex, requires Business account |
| Whisper speed | ~1 min per minute of audio on CPU, faster with GPU |
| Video quality | Looks like a standard faceless YouTube channel |

---

## Troubleshooting

**FFmpeg not found:**
Windows: Run `winget install ffmpeg` in PowerShell as admin, restart terminal

**edge-tts timeout:**
Requires internet. Try again — Microsoft's servers occasionally blip.

**YouTube quota exceeded:**
Quota resets at midnight Pacific. Set `MAX_VIDEOS_PER_DAY=1` in .env.

**Instagram "Application does not have permission":**
Make sure you added `instagram_content_publish` permission when generating the token.

**Whisper very slow:**
Switch to `--whisper-model tiny` — accuracy drops slightly but 5x faster on CPU.
