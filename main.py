"""
main.py - Financial Hero Entry Point
=====================================
This file is called by GitHub Actions daily.
It uses pipeline.py for everything — no Gemini, no old scripter.

The pipeline:
  1. Picks a unique topic (never repeats from used_topics.json)
  2. Generates a 160-200 word script from built-in templates
     OR uses Claude AI if ANTHROPIC_API_KEY is set
  3. Creates voice audio with gTTS (sounds human, free)
  4. Mixes background music under the voice
  5. Renders 60s video with changing backgrounds every 10s
  6. Generates thumbnail
  7. Uploads to YouTube (+ TikTok/Instagram if configured)
"""

import logging
import os
import sys

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    run(
        auto           = True,                              # auto-pick unused topic
        out_dir        = "/tmp/financial_hero_output",     # temp output folder
        tts_engine     = "gtts",                           # human-sounding voice
        add_music      = True,                             # background beat
        thumb_style    = "split",                          # poor vs rich thumbnail
        api_key        = os.getenv("ANTHROPIC_API_KEY"),  # optional — better scripts
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY"), # optional — better voice
    )
