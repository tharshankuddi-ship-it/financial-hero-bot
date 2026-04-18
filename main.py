import os
import sys
import tempfile
import logging
import subprocess
from pathlib import Path

from src.scripter import generate_script
from src.narrator import generate_audio
from src.editor import render_video
from src.uploader import upload_video

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

FONT_PATH = Path("fonts/main.ttf")
TOPIC_ROTATION = [
    "a surprising science fact",
    "a little-known history moment",
    "a mind-bending math trick",
    "a psychology principle everyone should know",
    "an interesting space discovery",
    "a counterintuitive economics concept",
    "a weird animal superpower",
]

def pick_topic():
    import datetime
    now = datetime.datetime.utcnow()
    slot = now.weekday() * 2 + (0 if now.hour < 12 else 1)
    return TOPIC_ROTATION[slot % len(TOPIC_ROTATION)]

def run():
    from src.scripter import pick_topic as _pick; topic = _pick()
    log.info(f"Topic: {topic}")
    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.mp3")
        video_path = os.path.join(tmp, "short.mp4")
        log.info("Generating script...")
        script = generate_script(topic)
        log.info("Generating audio...")
        generate_audio(script, audio_path)
        log.info("Rendering video...")
        render_video(script=script, audio_path=audio_path, output_path=video_path, font_path=str(FONT_PATH))
        log.info("Getting fresh token...")
        result = subprocess.run(["python", "get_token.py"], cwd="E:\\files", capture_output=True, text=True)
        lines = [l.strip() for l in result.stdout.split('\n') if l.strip().startswith('1//') or l.strip().startswith('1/')]
        if lines:
            os.environ["YT_REFRESH_TOKEN"] = lines[0]
            os.environ["YT_CLIENT_ID"] = "764743703979-nif776k7898jfb9q6iqeojng9afbj76e.apps.googleusercontent.com"
            os.environ["YT_CLIENT_SECRET"] = "YOUR_CLIENT_SECRET"
        log.info("Uploading to YouTube...")
        title = f"{topic.title()} #Shorts"
        description = f"Did you know? {script}\n\n#Shorts #Facts #LearnSomethingNew #Education"
        upload_video(video_path, title=title, description=description)
    log.info("Done!")

if __name__ == "__main__":
    run()
