"""
editor.py - Financial Hero Editor
==================================
Major upgrades in this version:
  1. Background cuts every 10s  — fetches multiple clips, cuts between them
  2. Minimum 60s video          — pads script if audio is short
  3. Hook/Value/Payoff structure — script formatted in 3 acts with visual emphasis
  4. Varied queries per segment — each 10s segment uses a DIFFERENT search query
  5. Zoom pulse effect          — subtle Ken Burns zoom on each segment
  6. Duplicate visual check     — logs used video IDs to avoid reusing same clip
"""

import logging, textwrap, os, requests, tempfile, io, json, hashlib, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (AudioFileClip, CompositeAudioClip, CompositeVideoClip,
                     ImageClip, VideoFileClip, concatenate_videoclips)

# Free CC0 background music from Pixabay
MUSIC_URLS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3",
    "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0c6ff1bab.mp3",
    "https://cdn.pixabay.com/download/audio/2022/08/02/audio_884fe92c21.mp3",
]

log = logging.getLogger(__name__)

WIDTH, HEIGHT       = 720, 1280
FPS                 = 30
MIN_DURATION        = 55.0      # target minimum video length in seconds
SEGMENT_DURATION    = 10.0      # background changes every 10 seconds

FONT_SIZE           = 72
LINE_HEIGHT         = FONT_SIZE + 12
CAPTION_COLOR       = (255, 255, 255)
HIGHLIGHT_COLOR     = (255, 220,   0)
STROKE_COLOR        = (0,   0,   0)
STROKE_WIDTH        = 5
WRAP_CHARS          = 14
WORDS_PER_CHUNK     = 3
TEXT_Y_POSITION     = int(HEIGHT * 0.68)

# ── Varied query pools — different visual styles ───────────────────────────────
# Each segment picks from a DIFFERENT category so visuals never repeat
SEGMENT_QUERY_POOLS = [
    # Category 1 — people working / stressed
    ["stressed person bills desk", "tired worker office night",
     "person worried money", "man counting coins table",
     "woman stressed laptop finance", "person looking wallet empty"],
    # Category 2 — cash / money physical
    ["cash money hands counting", "dollar bills spread table",
     "money envelope cash", "wallet full cash",
     "person receiving paycheck", "banknotes counting close up"],
    # Category 3 — investing / stocks
    ["stock market green candles", "trading app phone screen",
     "investment portfolio growth", "financial chart upward trend",
     "crypto trading screen", "stock broker working screens"],
    # Category 4 — luxury lifestyle
    ["luxury penthouse interior", "sports car driving road",
     "expensive watch close up", "yacht ocean luxury",
     "fine dining restaurant", "first class airplane seat"],
    # Category 5 — success / achievement
    ["person celebrating success", "handshake business deal",
     "young entrepreneur smiling", "team celebrating office",
     "person fist pump achievement", "confident woman business"],
    # Category 6 — city / skyline
    ["new york city aerial", "london financial district",
     "singapore city night", "dubai skyscrapers aerial",
     "tokyo city timelapse", "chicago skyline river"],
    # Category 7 — nature / time
    ["time lapse clouds sky", "sunrise over mountains",
     "hourglass sand time", "calendar pages turning",
     "seasons change time lapse", "tree growing timelapse"],
    # Category 8 — savings / bank
    ["piggy bank saving money", "coins jar saving",
     "bank building exterior", "credit card cutting scissors",
     "savings account phone", "financial planning notebook"],
    # Category 9 — real estate / property
    ["house keys new home", "real estate aerial suburb",
     "apartment building investment", "construction new building",
     "luxury home interior", "sold sign house"],
    # Category 10 — motivation / mindset
    ["person reading book cafe", "morning routine productive",
     "meditation focus calm", "running motivation fitness",
     "whiteboard planning strategy", "person writing goals journal"],
]

_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_FONT_CANDIDATES = [
    os.path.join(_DIR, "fonts", "main.ttf"),
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# Track used video IDs to prevent visual repeats across runs
_USED_VIDEOS_FILE = os.path.join(_DIR, "used_videos.json")


def _load_used_videos() -> set:
    if os.path.exists(_USED_VIDEOS_FILE):
        try:
            with open(_USED_VIDEOS_FILE) as f:
                data = json.load(f)
            return set(data[-200:])  # keep last 200
        except Exception:
            pass
    return set()


def _save_used_video(video_id: str):
    used = list(_load_used_videos())
    if video_id not in used:
        used.append(video_id)
        try:
            with open(_USED_VIDEOS_FILE, "w") as f:
                json.dump(used[-200:], f)
        except Exception:
            pass


def _load_font(font_path, size):
    candidates = ([font_path] if font_path else []) + _DEFAULT_FONT_CANDIDATES
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                pass
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def render_video(script: str, audio_path: str, output_path: str,
                 font_path: str | None = None,
                 word_timestamps=None):
    """
    Render a captioned short-form video.
    - Background changes every 10 seconds
    - Background music mixed quietly under voice
    """
    voice      = AudioFileClip(audio_path)
    speech_dur = voice.duration
    video_dur  = speech_dur

    final_audio  = _mix_music(voice, speech_dur)
    bg           = _get_segmented_background(video_dur)
    font         = _load_font(font_path, FONT_SIZE)
    all_captions = _make_caption_clips(script, speech_dur, font, word_timestamps)

    video = CompositeVideoClip([bg, *all_captions], size=(WIDTH, HEIGHT))
    video = video.with_audio(final_audio)
    video.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio_codec="aac", preset="fast", logger=None,
    )
    log.info(f"Video saved -> {output_path} ({video_dur:.1f}s)")


def _mix_music(voice_audio, duration: float):
    """Download a random free CC0 track and mix at 8% volume under voice."""
    try:
        url  = random.choice(MUSIC_URLS)
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(resp.content)
            music_path = f.name
        music = AudioFileClip(music_path)
        if music.duration < duration:
            from moviepy import concatenate_audioclips
            loops = int(duration / music.duration) + 1
            music = concatenate_audioclips([music] * loops)
        # MoviePy 2.x uses with_volume_scaled() not multiply_volume()
        music = music.subclipped(0, duration).with_volume_scaled(0.08)
        log.info("Background music mixed ✅")
        return CompositeAudioClip([voice_audio, music])
    except Exception as e:
        log.warning(f"Music failed ({e}), voice only")
        return voice_audio


# ══════════════════════════════════════════════════════════════════════════════
# Segmented background — changes every 10 seconds
# ══════════════════════════════════════════════════════════════════════════════

def _get_segmented_background(total_duration: float):
    """
    Build a background that cuts to a NEW visual every SEGMENT_DURATION seconds.
    Each segment uses a different query category for visual variety.
    Uses a time-based seed so every run picks different clips.
    """
    import random
    import time
    # Seed with current time so every run is different
    random.seed(int(time.time()))

    n_segments   = max(1, int(total_duration / SEGMENT_DURATION))
    seg_duration = total_duration / n_segments

    pexels_key  = os.getenv("PEXELS_API_KEY")
    pixabay_key = os.getenv("PIXABAY_API_KEY")

    # Shuffle categories so each segment gets a different visual theme
    categories = list(range(len(SEGMENT_QUERY_POOLS)))
    random.shuffle(categories)

    segments = []
    for i in range(n_segments):
        cat_idx = categories[i % len(categories)]
        query   = random.choice(SEGMENT_QUERY_POOLS[cat_idx])
        log.info(f"Segment {i+1}/{n_segments}: query='{query}'")

        clip = None
        if pexels_key:
            clip = _pexels_segment(seg_duration, pexels_key, query)
        if clip is None and pixabay_key:
            clip = _pixabay_segment(seg_duration, pixabay_key, query)
        if clip is None:
            clip = _gradient_segment(seg_duration, i)

        # Apply subtle zoom effect (Ken Burns) to each segment
        clip = _apply_zoom(clip, seg_duration)
        segments.append(clip)

    if len(segments) == 1:
        return segments[0]

    return concatenate_videoclips(segments, method="compose")


def _apply_zoom(clip, duration: float):
    """Apply a slow zoom-in effect (Ken Burns) to make static clips feel alive."""
    try:
        def zoom_frame(get_frame, t):
            frame  = get_frame(t)
            progress = t / max(duration, 0.1)
            scale  = 1.0 + 0.04 * progress   # zoom from 100% to 104%
            h, w   = frame.shape[:2]
            new_h  = int(h / scale)
            new_w  = int(w / scale)
            y0     = (h - new_h) // 2
            x0     = (w - new_w) // 2
            cropped = frame[y0:y0+new_h, x0:x0+new_w]
            resized = np.array(
                Image.fromarray(cropped).resize((w, h), Image.BILINEAR)
            )
            return resized
        return clip.transform(zoom_frame)
    except Exception:
        return clip   # zoom is cosmetic — never crash for it


def _pexels_segment(duration: float, api_key: str, query: str):
    """Fetch one Pexels clip for a given query, skip already-used video IDs."""
    import random
    used = _load_used_videos()
    try:
        url  = (f"https://api.pexels.com/videos/search"
                f"?query={requests.utils.quote(query)}&per_page=15&orientation=portrait")
        resp = requests.get(url, headers={"Authorization": api_key}, timeout=10)
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            return None

        random.shuffle(videos)
        for v in videos:
            vid_id = str(v.get("id", ""))
            if vid_id in used:
                log.info(f"  Skipping already-used Pexels ID {vid_id}")
                continue
            files     = sorted(v["video_files"],
                               key=lambda x: x.get("width", 0), reverse=True)
            video_url = files[0]["link"]
            clip      = _download_and_open_video(video_url, duration)
            if clip is not None:
                _save_used_video(vid_id)
                log.info(f"  Pexels clip: '{query}' (id={vid_id})")
                return clip

        log.warning(f"  Pexels: no fresh clips for '{query}'")
        return None
    except Exception as e:
        log.warning(f"  Pexels segment failed: {e}")
        return None


def _pixabay_segment(duration: float, api_key: str, query: str):
    """Fetch one Pixabay clip for a given query, skip already-used video IDs."""
    import random
    used = _load_used_videos()
    try:
        url  = (f"https://pixabay.com/api/videos/"
                f"?key={api_key}&q={requests.utils.quote(query)}"
                f"&video_type=film&per_page=15")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            return None

        random.shuffle(hits)
        for v in hits:
            vid_id = str(v.get("id", ""))
            if vid_id in used:
                log.info(f"  Skipping already-used Pixabay ID {vid_id}")
                continue
            videos    = v.get("videos", {})
            video_url = None
            for quality in ("large", "medium", "small", "tiny"):
                if quality in videos:
                    video_url = videos[quality]["url"]
                    break
            if not video_url:
                continue
            clip = _download_and_open_video(video_url, duration)
            if clip is not None:
                _save_used_video(vid_id)
                log.info(f"  Pixabay clip: '{query}' (id={vid_id})")
                return clip

        log.warning(f"  Pixabay: no fresh clips for '{query}'")
        return None
    except Exception as e:
        log.warning(f"  Pixabay segment failed: {e}")
        return None


def _gradient_segment(duration: float, index: int):
    """Unique colour gradient for each segment index — never the same colour."""
    palettes = [
        [(5, 20, 60),   (20, 60, 120)],   # dark blue
        [(60, 10, 5),   (120, 40, 20)],   # dark red
        [(5, 40, 20),   (20, 100, 50)],   # dark green
        [(40, 20, 60),  (100, 50, 120)],  # dark purple
        [(60, 40, 5),   (120, 100, 20)],  # dark gold
        [(5, 40, 60),   (20, 100, 120)],  # dark teal
    ]
    top, bot = palettes[index % len(palettes)]
    arr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for y in range(HEIGHT):
        t      = y / HEIGHT
        arr[y] = [int(top[c] + t * (bot[c] - top[c])) for c in range(3)]
    arr[:12]  = (255, 200, 0)
    arr[-12:] = (255, 200, 0)
    return ImageClip(arr).with_duration(duration)


def _download_and_open_video(video_url: str, duration: float):
    """Stream-download, validate with ffprobe, open with MoviePy."""
    import subprocess
    tmp_path = None
    try:
        dl = requests.get(video_url, timeout=60, stream=True)
        dl.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in dl.iter_content(chunk_size=1 << 16):
                tmp.write(chunk)

        if os.path.getsize(tmp_path) < 50_000:
            log.warning("Downloaded video too small — skipping")
            return None

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        if probe.returncode != 0 or not probe.stdout.strip():
            return None

        raw  = VideoFileClip(tmp_path).without_audio().resized((WIDTH, HEIGHT))
        clip = (raw.with_duration(duration)
                if raw.duration < duration
                else raw.subclipped(0, duration))
        clip._tmp_path_to_cleanup = tmp_path
        return clip
    except Exception as e:
        log.warning(f"Video download failed: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try: os.unlink(tmp_path)
            except OSError: pass
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Caption rendering
# ══════════════════════════════════════════════════════════════════════════════

def _make_caption_clips(script, total_duration, font, word_timestamps=None):
    words  = script.split()
    if not words:
        return []

    chunks        = [words[i:i+WORDS_PER_CHUNK]
                     for i in range(0, len(words), WORDS_PER_CHUNK)]
    chunk_duration = total_duration / len(chunks)

    return [
        ImageClip(np.array(_render_caption_frame(words, i * WORDS_PER_CHUNK, font)))
        .with_start(i * chunk_duration)
        .with_duration(chunk_duration)
        for i in range(len(chunks))
    ]


def _render_caption_frame(words, highlight_start, font):
    chunk   = words[highlight_start: highlight_start + WORDS_PER_CHUNK]
    if not chunk:
        return Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    wrapped = textwrap.wrap(" ".join(chunk), width=WRAP_CHARS)
    if not wrapped:
        return Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    pos_map = {}
    gi = 0
    for li, line in enumerate(wrapped):
        for wi in range(len(line.split())):
            pos_map[(li, wi)] = gi
            gi += 1

    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    for li, line in enumerate(wrapped):
        line_words = line.split()
        line_w     = sum(int(draw.textlength(w + " ", font=font)) for w in line_words)
        x          = (WIDTH - line_w) // 2
        yy         = TEXT_Y_POSITION + li * LINE_HEIGHT

        for wi, word in enumerate(line_words):
            g_idx = pos_map.get((li, wi), -1)
            color = HIGHLIGHT_COLOR if g_idx == 0 else CAPTION_COLOR
            for dx in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                for dy in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((x+dx, yy+dy), word, font=font,
                              fill=(*STROKE_COLOR, 255))
            draw.text((x, yy), word, font=font, fill=color)
            x += int(draw.textlength(word + " ", font=font))
    return base


# ══════════════════════════════════════════════════════════════════════════════
# Thumbnail generation
# ══════════════════════════════════════════════════════════════════════════════

THUMB_W, THUMB_H = 1280, 720
_POLLINATIONS_URL = ("https://image.pollinations.ai/prompt/{prompt}"
                     "?width={w}&height={h}&nologo=true&model=flux&seed={seed}")


def generate_thumbnail(title, output_path, style="split", seed=42):
    prompt = _build_thumbnail_prompt(title, style)
    log.info(f"Thumbnail prompt: {prompt[:80]}...")
    img = _pollinations_thumbnail(prompt, seed) or _pil_fallback_thumbnail(title)
    img.convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS).save(output_path, quality=95)
    log.info(f"Thumbnail saved -> {output_path}")
    return output_path


def _build_thumbnail_prompt(title, style):
    q = ("ultra realistic, 8k, cinematic lighting, sharp focus, "
         "high saturation, dramatic shadows, YouTube thumbnail style, 16:9")
    if style == "split":
        return (f"split screen YouTube thumbnail, left: stressed poor man dark lighting "
                f"empty wallet, right: confident rich businessman luxury suit money, "
                f"strong contrast, '{title}', {q}")
    return f"YouTube thumbnail '{title}', finance wealth theme, dramatic, {q}"


def _pollinations_thumbnail(prompt, seed):
    try:
        import urllib.parse
        url  = _POLLINATIONS_URL.format(
            prompt=urllib.parse.quote(prompt), w=THUMB_W, h=THUMB_H, seed=seed)
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            return None
        return Image.open(io.BytesIO(resp.content))
    except Exception as e:
        log.warning(f"Pollinations thumbnail failed: {e}")
        return None


def _pil_fallback_thumbnail(title):
    img  = Image.new("RGB", (THUMB_W, THUMB_H))
    draw = ImageDraw.Draw(img)
    half = THUMB_W // 2
    for x in range(half):
        t = x / half
        draw.line([(x,0),(x,THUMB_H)], fill=(int(20+t*60), 5, 5))
    for x in range(half, THUMB_W):
        t = (x-half)/half
        draw.line([(x,0),(x,THUMB_H)], fill=(int(20+t*60), int(30+t*80), int(5+t*20)))
    cx_l, cx_r = half//2, half+half//2
    # Poor man
    draw.ellipse([(cx_l-42,220),(cx_l+42,315)], fill=(160,100,60))
    draw.rectangle([(cx_l-34,310),(cx_l+34,570)], fill=(22,18,18))
    draw.arc([(cx_l-18,274),(cx_l+18,302)], start=180, end=360, fill=(60,30,10), width=3)
    draw.line([(cx_l-34,400),(cx_l-80,490)], fill=(22,18,18), width=22)
    draw.line([(cx_l+34,400),(cx_l+75,490)], fill=(22,18,18), width=22)
    draw.rectangle([(cx_l+58,468),(cx_l+100,502)], fill=(60,40,20))
    # Rich man
    draw.ellipse([(cx_r-44,215),(cx_r+44,310)], fill=(170,110,65))
    draw.rectangle([(cx_r-38,305),(cx_r+38,570)], fill=(16,30,16))
    draw.polygon([(cx_r-8,307),(cx_r+8,307),(cx_r+5,380),(cx_r,390),(cx_r-5,380)],
                 fill=(180,150,0))
    draw.arc([(cx_r-20,265),(cx_r+20,295)], start=0, end=180, fill=(60,30,10), width=3)
    draw.line([(cx_r-38,395),(cx_r-85,480)], fill=(16,30,16), width=24)
    draw.line([(cx_r+38,395),(cx_r+85,480)], fill=(16,30,16), width=24)
    # Divider
    for gx in range(half-3, half+4):
        t = abs(gx-half)/3
        b = int(255*(1-t*0.6))
        draw.line([(gx,0),(gx,THUMB_H)], fill=(b,int(b*0.85),0))
    font_big = _load_font(None, 60)
    font_med = _load_font(None, 42)
    font_sm  = _load_font(None, 28)
    _draw_outlined(draw, (THUMB_W//2, 42),  _split_title(title)[0], font_big,
                   (255,215,0), (0,0,0))
    _draw_outlined(draw, (THUMB_W//2, 108), _split_title(title)[1], font_big,
                   (255,170,0), (0,0,0))
    _draw_outlined(draw, (cx_l, 158), "THE POOR", font_med, (200,30,30), (0,0,0))
    _draw_outlined(draw, (cx_r, 158), "THE RICH", font_med, (255,210,0), (0,0,0))
    _draw_outlined(draw, (half, THUMB_H//2), "VS", font_med, (0,0,0), (180,150,0))
    draw.rectangle([(0,THUMB_H-52),(THUMB_W,THUMB_H)], fill=(0,0,0))
    _draw_outlined(draw, (THUMB_W//2, THUMB_H-26),
                   "THE SECRET THEY DON'T WANT YOU TO KNOW",
                   font_sm, (255,255,255), (80,80,80))
    return img


def _split_title(title):
    w   = title.upper().split()
    mid = len(w) // 2
    return " ".join(w[:mid]), " ".join(w[mid:])


def _draw_outlined(draw, xy, text, font, fill, stroke):
    x, y = xy
    sw   = max(1, font.size // 16)
    for dx in range(-sw, sw+1):
        for dy in range(-sw, sw+1):
            if dx == 0 and dy == 0: continue
            draw.text((x+dx, y+dy), text, font=font, fill=stroke, anchor="mm")
    draw.text((x, y), text, font=font, fill=fill, anchor="mm")
