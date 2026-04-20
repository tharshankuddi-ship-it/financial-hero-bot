import os
import sys
import tempfile
import logging
from pathlib import Path

# Make sure src/ is on the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from scripter import generate_script, pick_topic
from narrator import generate_audio
from editor import render_video
from uploader import upload_video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

FONT_PATH = Path("fonts/main.ttf")

def run():
    topic = pick_topic()
    log.info(f"Topic: {topic}")

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.mp3")
        video_path = os.path.join(tmp, "short.mp4")

        log.info("Generating script...")
        script = generate_script(topic)
        log.info(f"Script: {script[:80]}...")

        log.info("Generating audio...")
        generate_audio(script, audio_path)

        log.info("Rendering video...")
        render_video(
            script=script,
            audio_path=audio_path,
            output_path=video_path,
            font_path=str(FONT_PATH),
        )

        log.info("Uploading to YouTube...")
        title = f"{topic.title()} #Shorts"
        description = (
            f"Did you know? {script}\n\n"
            "#Shorts #Finance #Money #WealthTips "
            "#FinancialFreedom #Investing #TheFinancialHero"
        )
        upload_video(video_path, title=title, description=description)

    log.info("Done!")

if __name__ == "__main__":
    run()
