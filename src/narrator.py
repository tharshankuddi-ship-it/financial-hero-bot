"""
src/narrator.py — The Voice
Uses edge-tts (Microsoft's free neural TTS) to synthesise an MP3.
No API key required.
"""

import asyncio
import logging

import edge_tts

log = logging.getLogger(__name__)

# Pick any voice from: `edge-tts --list-voices`
VOICE = "en-US-GuyNeural"          # male, natural, works great for facts
RATE  = "+35%"                     # fast energetic pace for Shorts
PITCH = "+2Hz"                     # slightly higher = more energy


def generate_audio(script: str, output_path: str) -> None:
    """Synthesise *script* and save as MP3 to *output_path*."""
    asyncio.run(_synthesise(script, output_path))
    log.info(f"Audio saved → {output_path}")


async def _synthesise(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await communicate.save(output_path)
