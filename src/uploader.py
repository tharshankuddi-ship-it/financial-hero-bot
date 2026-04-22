"""
src/narrator.py — The Voice with word-level timestamps
"""
import asyncio
import logging
import json
import edge_tts

log = logging.getLogger(__name__)

VOICE = "en-US-GuyNeural"
RATE  = "+5%"
PITCH = "+2Hz"


def generate_audio(script: str, output_path: str) -> list:
    """
    Synthesise script and save MP3. Returns word timestamps list:
    [{"word": "Hello", "start": 0.0, "end": 0.4}, ...]
    """
    timestamps = asyncio.run(_synthesise_with_timestamps(script, output_path))
    log.info(f"Audio saved → {output_path} ({len(timestamps)} word timestamps)")
    return timestamps


async def _synthesise_with_timestamps(text: str, output_path: str) -> list:
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    timestamps = []
    audio_chunks = []

    async for event in communicate.stream():
        if event["type"] == "audio":
            audio_chunks.append(event["data"])
        elif event["type"] == "WordBoundary":
            timestamps.append({
                "word":  event["text"],
                "start": event["offset"] / 10_000_000,   # 100ns → seconds
                "end":   (event["offset"] + event["duration"]) / 10_000_000,
            })

    with open(output_path, "wb") as f:
        for chunk in audio_chunks:
            f.write(chunk)

    return timestamps
