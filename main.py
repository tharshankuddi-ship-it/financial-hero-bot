import os
import sys
import tempfile
import logging
import subprocess
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from scripter import generate_script, pick_topic
from narrator import generate_audio
from editor import render_video
from uploader import upload_video
from tiktok_uploader import upload_to_tiktok

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)
FONT_PATH = Path("fonts/main.ttf")


def quality_check(video_path: str, min_duration=40, max_duration=65) -> bool:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())
        size_mb  = os.path.getsize(video_path) / 1024 / 1024
        log.info(f"QC → Duration: {duration:.1f}s | Size: {size_mb:.1f}MB")
        if duration < min_duration:
            log.error(f"QC FAILED: too short ({duration:.1f}s < {min_duration}s)")
            return False
        if duration > max_duration:
            log.error(f"QC FAILED: too long ({duration:.1f}s > {max_duration}s)")
            return False
        if size_mb < 0.5:
            log.error(f"QC FAILED: file too small ({size_mb:.1f}MB)")
            return False
        log.info("QC PASSED ✅")
        return True
    except Exception as e:
        log.warning(f"QC check failed ({e}) — uploading anyway")
        return True


def run():
    topic = pick_topic()
    log.info(f"Topic: {topic}")

    with tempfile.TemporaryDirectory() as tmp:
        audio_path = os.path.join(tmp, "audio.mp3")
        video_path = os.path.join(tmp, "short.mp4")

        log.info("Generating script...")
        script = generate_script(topic)
        log.info(f"Script ({len(script.split())} words): {script[:80]}...")

        log.info("Generating audio...")
        timestamps = generate_audio(script, audio_path)

        log.info("Rendering video...")
        render_video(
            script=script,
            audio_path=audio_path,
            output_path=video_path,
            font_path=str(FONT_PATH),
            word_timestamps=timestamps,
        )

        if not quality_check(video_path):
            log.error("Video failed quality check — NOT uploading")
            sys.exit(1)

        sentences    = script.split('. ')
        desc_preview = '. '.join(sentences[:2]) + '.'
        title        = f"{topic.title()} #Shorts #TheFinancialHero"
        description  = (
            f"{desc_preview}\n\n"
            "Follow The Financial Hero for daily money tips.\n\n"
            "#Shorts #Finance #Money #WealthTips "
            "#FinancialFreedom #Investing #TheFinancialHero #PersonalFinance"
        )

        # Upload to YouTube
        log.info("Uploading to YouTube...")
        try:
            upload_video(video_path, title=title, description=description)
            log.info("✅ YouTube upload done!")
        except Exception as e:
            log.error(f"YouTube upload failed: {e}")

        # Upload to TikTok
        log.info("Uploading to TikTok...")
        try:
            tiktok_id = upload_to_tiktok(video_path, title=title)
            if tiktok_id:
                log.info(f"✅ TikTok upload done! publish_id={tiktok_id}")
        except Exception as e:
            log.error(f"TikTok upload failed: {e}")

    log.info("Done! ✅")


if __name__ == "__main__":
    run()
