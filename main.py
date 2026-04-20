"""
main.py - Financial Hero Entry Point
Place this file inside the src/ folder alongside pipeline.py
GitHub Actions runs: python src/main.py
"""

import logging
import os
import sys

# pipeline.py is in the same src/ folder as this file
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    run(
        auto           = True,
        out_dir        = "/tmp/financial_hero_output",
        tts_engine     = "gtts",
        add_music      = True,
        thumb_style    = "split",
        api_key        = os.getenv("ANTHROPIC_API_KEY"),
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY"),
    )
