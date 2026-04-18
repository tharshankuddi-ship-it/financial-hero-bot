"""
src/editor.py - Financial Hero Editor
- Bottom-positioned bold captions (like viral Shorts)
- Pexels + Pixabay video backgrounds
- Pollinations AI image fallback
"""
import logging, textwrap, os, requests, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, CompositeVideoClip,
    ImageClip, VideoFileClip,
)

log = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920
FPS           = 30
FONT_SIZE     = 100
CAPTION_COLOR   = (255, 255, 255)
HIGHLIGHT_COLOR = (255, 220,   0)
SHADOW_COLOR    = (  0,   0,   0)
SHADOW_OFFSET   = 6
WRAP_WIDTH      = 14
# Bottom position - like viral Shorts
TEXT_Y_POSITION = int(HEIGHT * 0.68)

PEXELS_QUERIES  = ["money coins finance", "stock market trading", "gold investment wealth", "business success city", "dollar bills cash"]
PIXABAY_QUERIES = ["money finance", "gold coins wealth", "stock market", "business success", "investment banking"]

def render_video(script, audio_path, output_path, font_path="fonts/main.ttf"):
    audio    = AudioFileClip(audio_path)
    duration = audio.duration
    bg       = _get_background(duration)
    captions = _make_caption_clips(script, duration, font_path)
    video    = CompositeVideoClip([bg, *captions], size=(WIDTH, HEIGHT))
    video    = video.set_audio(audio)
    video.write_videofile(output_path, fps=FPS, codec="libx264", audio_codec="aac", preset="fast", logger=None)
    log.info(f"Video saved -> {output_path}")

def _get_background(duration):
    # Try Pexels first
    pexels_key = os.getenv("PEXELS_API_KEY")
    if pexels_key:
        bg = _pexels_background(duration, pexels_key)
        if bg:
            return bg
    # Try Pixabay second
    pixabay_key = os.getenv("PIXABAY_API_KEY")
    if pixabay_key:
        bg = _pixabay_background(duration, pixabay_key)
        if bg:
            return bg
    # Try Pollinations image third
    bg = _pollinations_background(duration)
    if bg:
        return bg
    # Final fallback: gradient
    return _gradient_background(duration)

def _pexels_background(duration, api_key):
    try:
        import random
        query = random.choice(PEXELS_QUERIES)
        url   = f"https://api.pexels.com/videos/search?query={query}&per_page=10&orientation=portrait"
        resp  = requests.get(url, headers={"Authorization": api_key}, timeout=10)
        videos = resp.json().get("videos", [])
        if not videos:
            return None
        v         = random.choice(videos)
        files     = sorted(v["video_files"], key=lambda x: x.get("width", 0), reverse=True)
        video_url = files[0]["link"]
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(requests.get(video_url, timeout=30).content)
        tmp.close()
        clip = VideoFileClip(tmp.name).without_audio().resize((WIDTH, HEIGHT), Image.LANCZOS)
        clip = clip.loop(duration=duration) if clip.duration < duration else clip.subclip(0, duration)
        log.info(f"Pexels background: {query}")
        return clip
    except Exception as e:
        log.warning(f"Pexels failed: {e}")
        return None

def _pixabay_background(duration, api_key):
    try:
        import random
        query = random.choice(PIXABAY_QUERIES)
        url   = f"https://pixabay.com/api/videos/?key={api_key}&q={query}&video_type=film&per_page=10"
        resp  = requests.get(url, timeout=10)
        hits  = resp.json().get("hits", [])
        if not hits:
            return None
        v         = random.choice(hits)
        videos    = v.get("videos", {})
        # Pick best quality available
        for quality in ["large", "medium", "small", "tiny"]:
            if quality in videos:
                video_url = videos[quality]["url"]
                break
        else:
            return None
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(requests.get(video_url, timeout=30).content)
        tmp.close()
        clip = VideoFileClip(tmp.name).without_audio().resize((WIDTH, HEIGHT), Image.LANCZOS)
        clip = clip.loop(duration=duration) if clip.duration < duration else clip.subclip(0, duration)
        log.info(f"Pixabay background: {query}")
        return clip
    except Exception as e:
        log.warning(f"Pixabay failed: {e}")
        return None

def _pollinations_background(duration):
    try:
        prompt = "financial wealth money gold coins abstract background portrait 9:16"
        url    = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true"
        resp   = requests.get(url, timeout=20)
        import io
        img    = Image.open(io.BytesIO(resp.content)).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
        log.info("Pollinations.ai background")
        return ImageClip(np.array(img)).set_duration(duration)
    except Exception as e:
        log.warning(f"Pollinations failed: {e}")
        return None

def _gradient_background(duration):
    arr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for y in range(HEIGHT):
        t = y / HEIGHT
        arr[y] = [int(10 + t * (5 - 10)), int(40 + t * (20 - 40)), int(20 + t * (10 - 20))]
    arr[:18]  = (255, 200, 0)
    arr[-18:] = (255, 200, 0)
    return ImageClip(arr).set_duration(duration)

def _make_caption_clips(script, total_duration, font_path):
    words = script.split()
    if not words:
        return []
    time_per_word = total_duration / len(words)
    return [
        ImageClip(np.array(_render_caption_frame(words, i, font_path)))
        .set_start(i * time_per_word)
        .set_duration(time_per_word)
        for i in range(len(words))
    ]

def _render_caption_frame(words, highlight_index, font_path):
    img  = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(font_path, FONT_SIZE)
    except (IOError, OSError):
        log.warning("Font not found, using default PIL font")
        font = ImageFont.load_default()

    # Show only a window of ~6 words around current word for readability
    start = max(0, highlight_index - 5)
    end   = min(len(words), highlight_index + 8)
    visible_words   = words[start:end]
    visible_highlight = highlight_index - start

    wrapped = textwrap.wrap(" ".join(visible_words), width=WRAP_WIDTH)
    if not wrapped:
        return img

    line_height = FONT_SIZE + 24
    total_h     = len(wrapped) * line_height
    y           = TEXT_Y_POSITION

    # Dark semi-transparent background box for readability
    pad = 20
    box_top    = y - pad
    box_bottom = y + total_h + pad
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rectangle([(60, box_top), (WIDTH - 60, box_bottom)], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Recount word positions in visible window
    word_positions = []
    for li, line in enumerate(wrapped):
        for wi in range(len(line.split())):
            word_positions.append((li, wi))

    for li, line in enumerate(wrapped):
        line_words = line.split()
        line_width = sum(draw.textlength(w + " ", font=font) for w in line_words)
        x = (WIDTH - line_width) // 2
        yy = y + li * line_height
        for wi, word in enumerate(line_words):
            g_idx = next((idx for idx, (l, w) in enumerate(word_positions) if l == li and w == wi), -1)
            color = HIGHLIGHT_COLOR if g_idx == visible_highlight else CAPTION_COLOR
            # Shadow
            draw.text((x + SHADOW_OFFSET, yy + SHADOW_OFFSET), word, font=font, fill=(*SHADOW_COLOR, 200))
            # Main text
            draw.text((x, yy), word, font=font, fill=color)
            x += draw.textlength(word + " ", font=font)
    return img
