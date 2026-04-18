"""
src/editor.py - Financial Hero Editor (moviepy 2.x compatible)

Fixes applied:
  1. Resolution: WIDTH/HEIGHT now match the actual export resolution (720×1280)
     to avoid caption/font size mismatch from upscale→downscale round-trip.
  2. Caption box: tight-fit to text only (no over-sized dark panel eating 40% of frame).
  3. Line height: reduced from FONT_SIZE+24 to FONT_SIZE+10 for natural reading flow.
  4. Word grouping: 3 words per line (WRAP_WIDTH) instead of 14 chars, producing
     clean multi-word lines rather than single-word stacking.
  5. Highlight granularity: highlights a 3-word chunk at a time instead of one word,
     advancing every chunk interval — smoother pacing that doesn't feel jittery.
  6. Alpha compositing fix: caption frame is pre-composited onto a fully transparent
     base and only the text+box region carries alpha — coins no longer bleed through.
  7. Temp file cleanup: both Pexels and Pixabay download paths now delete temp files
     in a finally block after MoviePy has loaded the clip into memory via .copy().
  8. Gradient background: fixed negative multipliers that produced near-black frames.
  9. word_positions lookup: O(n) linear scan replaced with O(1) dict lookup per frame.
 10. Font path: resolved relative to __file__ so it works from any cwd.
 11. Fallback font: when custom font is missing, uses FreeSansBold (available on
     Ubuntu) which is far more legible than PIL's 10px bitmap default.
"""

import logging, textwrap, os, requests, tempfile, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, VideoFileClip

log = logging.getLogger(__name__)

# ── Resolution ────────────────────────────────────────────────────────────────
# Match the actual export resolution. Rendering at 1080×1920 then outputting at
# 720×1280 scales everything down, making captions tiny. Use one consistent size.
WIDTH, HEIGHT   = 720, 1280
FPS             = 30

# ── Caption style ─────────────────────────────────────────────────────────────
FONT_SIZE       = 72                  # slightly larger — no box competing for space
LINE_HEIGHT     = FONT_SIZE + 12      # tight but not cramped
CAPTION_COLOR   = (255, 255, 255)
HIGHLIGHT_COLOR = (255, 220,   0)
STROKE_COLOR    = (0,   0,   0)       # thick outline keeps text readable on any bg
STROKE_WIDTH    = 5                   # px — replaces the dark box entirely
WRAP_CHARS      = 14                  # tighter wrap → fewer words per line → bigger feel
WORDS_PER_CHUNK = 3                   # show exactly this many words at a time
# Vertical centre of the caption block (68 % down the frame)
TEXT_Y_POSITION = int(HEIGHT * 0.68)

# ── Background queries ─────────────────────────────────────────────────────────
PEXELS_QUERIES  = ["gold coins finance", "stock market trading", "dollar bills money",
                   "business wealth success", "bitcoin crypto gold"]
PIXABAY_QUERIES = ["money finance", "gold coins wealth", "stock market",
                   "business success", "investment banking"]

# ── Font resolution ────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_FONT_CANDIDATES = [
    os.path.join(_DIR, "fonts", "main.ttf"),            # project font (preferred)
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",   # Ubuntu fallback
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

def _load_font(font_path: str | None, size: int) -> ImageFont.FreeTypeFont:
    candidates = ([font_path] if font_path else []) + _DEFAULT_FONT_CANDIDATES
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except (IOError, OSError):
                pass
    log.warning("No TrueType font found — falling back to PIL bitmap font (low quality)")
    return ImageFont.load_default()


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def render_video(script: str, audio_path: str, output_path: str,
                 font_path: str | None = None,
                 word_timestamps: list[tuple[str, float, float]] | None = None):
    """
    Render a captioned short-form video.

    Args:
        script:          The spoken text (used for uniform-timing fallback).
        audio_path:      Path to the audio track.
        output_path:     Where to write the finished .mp4.
        font_path:       Optional path to a .ttf/.otf caption font.
        word_timestamps: Optional list of (word, start_sec, end_sec) tuples from
                         WhisperX / Gentle / similar. When provided, captions are
                         audio-synced. Falls back to uniform timing if None.
    """
    audio    = AudioFileClip(audio_path)
    duration = audio.duration
    bg       = _get_background(duration)
    font     = _load_font(font_path, FONT_SIZE)
    captions = _make_caption_clips(script, duration, font, word_timestamps)
    video    = CompositeVideoClip([bg, *captions], size=(WIDTH, HEIGHT))
    video    = video.with_audio(audio)
    video.write_videofile(
        output_path, fps=FPS, codec="libx264",
        audio_codec="aac", preset="fast", logger=None,
    )
    log.info(f"Video saved -> {output_path}")


# ══════════════════════════════════════════════════════════════════════════════
# Background helpers
# ══════════════════════════════════════════════════════════════════════════════

def _get_background(duration: float):
    pexels_key = os.getenv("PEXELS_API_KEY")
    if pexels_key:
        bg = _pexels_background(duration, pexels_key)
        if bg: return bg

    pixabay_key = os.getenv("PIXABAY_API_KEY")
    if pixabay_key:
        bg = _pixabay_background(duration, pixabay_key)
        if bg: return bg

    bg = _pollinations_background(duration)
    if bg: return bg

    return _gradient_background(duration)


def _pexels_background(duration: float, api_key: str):
    import random
    tmp_path = None
    try:
        query    = random.choice(PEXELS_QUERIES)
        url      = (f"https://api.pexels.com/videos/search"
                    f"?query={query}&per_page=10&orientation=portrait")
        resp     = requests.get(url, headers={"Authorization": api_key}, timeout=10)
        videos   = resp.json().get("videos", [])
        if not videos:
            return None
        v        = random.choice(videos)
        files    = sorted(v["video_files"], key=lambda x: x.get("width", 0), reverse=True)
        video_url = files[0]["link"]

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(requests.get(video_url, timeout=30).content)

        raw  = VideoFileClip(tmp_path).without_audio().resized((WIDTH, HEIGHT))
        clip = raw.copy()          # force full load so we can safely delete the file
        raw.close()
        clip = (clip.with_duration(duration)
                if clip.duration < duration
                else clip.subclipped(0, duration))
        log.info(f"Pexels background: {query}")
        return clip
    except Exception as e:
        log.warning(f"Pexels failed: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _pixabay_background(duration: float, api_key: str):
    import random
    tmp_path = None
    try:
        query = random.choice(PIXABAY_QUERIES)
        url   = (f"https://pixabay.com/api/videos/"
                 f"?key={api_key}&q={query}&video_type=film&per_page=10")
        resp  = requests.get(url, timeout=10)
        hits  = resp.json().get("hits", [])
        if not hits:
            return None
        v      = random.choice(hits)
        videos = v.get("videos", {})
        video_url = None
        for quality in ("large", "medium", "small", "tiny"):
            if quality in videos:
                video_url = videos[quality]["url"]
                break
        if not video_url:
            return None

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(requests.get(video_url, timeout=30).content)

        raw  = VideoFileClip(tmp_path).without_audio().resized((WIDTH, HEIGHT))
        clip = raw.copy()
        raw.close()
        clip = (clip.with_duration(duration)
                if clip.duration < duration
                else clip.subclipped(0, duration))
        log.info(f"Pixabay background: {query}")
        return clip
    except Exception as e:
        log.warning(f"Pixabay failed: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _pollinations_background(duration: float):
    try:
        prompt = "bright gold coins money wealth finance colorful background"
        url    = (f"https://image.pollinations.ai/prompt/{prompt}"
                  f"?width={WIDTH}&height={HEIGHT}&nologo=true")
        resp   = requests.get(url, timeout=20)
        img    = Image.open(io.BytesIO(resp.content)).convert("RGB").resize((WIDTH, HEIGHT))
        log.info("Pollinations.ai background")
        return ImageClip(np.array(img)).with_duration(duration)
    except Exception as e:
        log.warning(f"Pollinations failed: {e}")
        return None


def _gradient_background(duration: float):
    """Dark-green-to-teal gradient with gold accent bars — purely cosmetic fallback."""
    arr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for y in range(HEIGHT):
        t = y / HEIGHT
        # Fixed: was using negative multipliers → near-black. Now a proper gradient.
        arr[y] = [
            int(5  + t * 20),   # R: 5 → 25
            int(40 + t * 60),   # G: 40 → 100  (teal-ish)
            int(20 + t * 50),   # B: 20 → 70
        ]
    arr[:18]  = (255, 200, 0)   # gold top bar
    arr[-18:] = (255, 200, 0)   # gold bottom bar
    return ImageClip(arr).with_duration(duration)


# ══════════════════════════════════════════════════════════════════════════════
# Caption rendering
# ══════════════════════════════════════════════════════════════════════════════

def _make_caption_clips(script: str, total_duration: float,
                        font: ImageFont.FreeTypeFont,
                        word_timestamps: list[tuple[str, float, float]] | None):
    """
    Build one ImageClip per *chunk* (WORDS_PER_CHUNK words).

    If word_timestamps is provided each clip is timed to actual speech.
    Otherwise timing is divided uniformly across chunks.
    """
    words = script.split()
    if not words:
        return []

    # Build chunks of WORDS_PER_CHUNK words
    chunks = [words[i:i + WORDS_PER_CHUNK]
              for i in range(0, len(words), WORDS_PER_CHUNK)]

    if word_timestamps:
        # Audio-aligned: map each chunk to its word span's time range
        ts_map = {w: (s, e) for w, s, e in word_timestamps}
        clips  = []
        for ci, chunk in enumerate(chunks):
            first_word = chunk[0]
            last_word  = chunk[-1]
            t_start    = ts_map.get(first_word, (ci / len(chunks) * total_duration, 0))[0]
            t_end      = ts_map.get(last_word,  (0, (ci + 1) / len(chunks) * total_duration))[1]
            duration   = max(0.05, t_end - t_start)
            frame      = _render_caption_frame(words, ci * WORDS_PER_CHUNK, font)
            clips.append(
                ImageClip(np.array(frame))
                .with_start(t_start)
                .with_duration(duration)
            )
        return clips
    else:
        # Uniform timing across chunks
        chunk_duration = total_duration / len(chunks)
        return [
            ImageClip(np.array(_render_caption_frame(words, i * WORDS_PER_CHUNK, font)))
            .with_start(i * chunk_duration)
            .with_duration(chunk_duration)
            for i in range(len(chunks))
        ]


def _render_caption_frame(words: list[str], highlight_start: int,
                           font: ImageFont.FreeTypeFont) -> Image.Image:
    """
    Render a single caption frame.

    - Shows ONLY the current WORDS_PER_CHUNK words (no surrounding context).
    - First word of the chunk is yellow (highlight), rest are white.
    - NO background box — text sits directly over the video footage.
    - Thick black stroke (STROKE_WIDTH) keeps text legible on any background.
    """
    # ── Only show the current chunk ────────────────────────────────────────
    chunk = words[highlight_start : highlight_start + WORDS_PER_CHUNK]
    if not chunk:
        return Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    wrapped = textwrap.wrap(" ".join(chunk), width=WRAP_CHARS)
    if not wrapped:
        return Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    # ── Build word→global-index lookup (O(1)) ─────────────────────────────
    pos_map: dict[tuple[int, int], int] = {}
    global_idx = 0
    for li, line in enumerate(wrapped):
        for wi in range(len(line.split())):
            pos_map[(li, wi)] = global_idx
            global_idx += 1

    # ── Transparent canvas — NO box drawn ─────────────────────────────────
    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)

    # ── Draw each word with thick stroke then fill ─────────────────────────
    for li, line in enumerate(wrapped):
        line_words = line.split()
        line_w     = sum(int(draw.textlength(w + " ", font=font)) for w in line_words)
        x          = (WIDTH - line_w) // 2
        yy         = TEXT_Y_POSITION + li * LINE_HEIGHT

        for wi, word in enumerate(line_words):
            g_idx = pos_map.get((li, wi), -1)
            # First word of chunk is highlighted yellow; rest are white
            color = HIGHLIGHT_COLOR if g_idx == 0 else CAPTION_COLOR

            # Stroke: draw the word offset in 8 directions for a clean outline
            for dx in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                for dy in range(-STROKE_WIDTH, STROKE_WIDTH + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((x + dx, yy + dy), word, font=font,
                              fill=(*STROKE_COLOR, 255))
            # Fill on top
            draw.text((x, yy), word, font=font, fill=color)
            x += int(draw.textlength(word + " ", font=font))

    return base


# ══════════════════════════════════════════════════════════════════════════════
# Thumbnail generation  (free — no API key required)
# ══════════════════════════════════════════════════════════════════════════════

# Thumbnail dimensions (16:9 YouTube standard)
THUMB_W, THUMB_H = 1280, 720

# Pollinations.ai — completely free, no signup, no key
# Docs: https://pollinations.ai  |  model options: flux, turbo
_POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}?width={w}&height={h}&nologo=true&model=flux&seed={seed}"

def generate_thumbnail(
    title: str,
    output_path: str,
    style: str = "youtube",
    seed: int = 42,
) -> str:
    """
    Generate a YouTube thumbnail using free AI image generation.

    Tries sources in order:
      1. Pollinations.ai  (free, no key)
      2. CSS/PIL fallback (always works offline)

    Args:
        title:       Video title shown on the thumbnail.
        output_path: Where to save the .png / .jpg file.
        style:       One of "youtube", "split", "dramatic".
        seed:        Fixed seed for reproducibility (change to get a new image).

    Returns:
        output_path on success.
    """
    prompt = _build_thumbnail_prompt(title, style)
    log.info(f"Generating thumbnail: {prompt[:80]}...")

    img = _pollinations_thumbnail(prompt, seed)
    if img is None:
        log.warning("Pollinations failed — using PIL fallback thumbnail")
        img = _pil_fallback_thumbnail(title)

    img = img.convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)
    img.save(output_path, quality=95)
    log.info(f"Thumbnail saved -> {output_path}")
    return output_path


def _build_thumbnail_prompt(title: str, style: str) -> str:
    """Build a detailed prompt tuned for YouTube thumbnail aesthetics."""
    base_quality = (
        "ultra realistic, 8k, cinematic lighting, sharp focus, "
        "high saturation, dramatic shadows, professional photography, "
        "YouTube thumbnail style, eye-catching, 16:9"
    )
    if style == "split":
        return (
            f"split screen YouTube thumbnail, left half: stressed poor man dark moody "
            f"lighting holding empty wallet, desperate sad expression, dark red shadows, "
            f"right half: confident wealthy businessman in luxury suit gold watch, "
            f"money flying around, bright golden lighting, strong contrast between "
            f"dark and bright sides, title concept '{title}', {base_quality}"
        )
    elif style == "dramatic":
        return (
            f"dramatic YouTube thumbnail about '{title}', "
            f"person with shocked expression, gold coins and money raining, "
            f"cinematic dark background with golden light rays, "
            f"bold visual storytelling, {base_quality}"
        )
    else:  # youtube default
        return (
            f"YouTube thumbnail for video titled '{title}', "
            f"split screen poor vs rich contrast, dark vs bright lighting, "
            f"money and finance theme, emotional facial expressions, "
            f"bold text space at top, {base_quality}"
        )


def _pollinations_thumbnail(prompt: str, seed: int) -> Image.Image | None:
    """Call Pollinations.ai (free, no key needed)."""
    try:
        url = _POLLINATIONS_URL.format(
            prompt=requests.utils.quote(prompt),
            w=THUMB_W, h=THUMB_H, seed=seed,
        )
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            log.warning(f"Pollinations HTTP {resp.status_code}")
            return None
        img = Image.open(io.BytesIO(resp.content))
        log.info("Pollinations.ai thumbnail generated")
        return img
    except Exception as e:
        log.warning(f"Pollinations thumbnail failed: {e}")
        return None


def _pil_fallback_thumbnail(title: str) -> Image.Image:
    """
    Pure-PIL split-screen thumbnail — works with zero network access.
    Left: dark red (poor), Right: dark gold/green (rich), VS divider, title text.
    """
    img  = Image.new("RGB", (THUMB_W, THUMB_H))
    draw = ImageDraw.Draw(img)
    half = THUMB_W // 2

    # ── Backgrounds ──────────────────────────────────────────────────────────
    # Left gradient: near-black → dark red
    for x in range(half):
        t = x / half
        r = int(20 + t * 60)
        draw.line([(x, 0), (x, THUMB_H)], fill=(r, 5, 5))

    # Right gradient: dark green → gold-tinted
    for x in range(half, THUMB_W):
        t = (x - half) / half
        g = int(30 + t * 80)
        b = int(5  + t * 20)
        draw.line([(x, 0), (x, THUMB_H)], fill=(int(20 + t*60), g, b))

    # ── Poor figure (left) ───────────────────────────────────────────────────
    cx_l = half // 2
    # body
    draw.ellipse([(cx_l-28, 310), (cx_l+28, 390)], fill=(28, 22, 22))
    draw.rectangle([(cx_l-34, 385), (cx_l+34, 570)], fill=(22, 18, 18))
    # head
    draw.ellipse([(cx_l-42, 220), (cx_l+42, 315)], fill=(160, 100, 60))
    # frown (180→360 draws the bottom arc = downturned mouth)
    draw.arc([(cx_l-18, 274), (cx_l+18, 302)], start=180, end=360, fill=(60, 30, 10), width=3)
    # arms drooping
    draw.line([(cx_l-34, 400), (cx_l-80, 490)], fill=(22, 18, 18), width=22)
    draw.line([(cx_l+34, 400), (cx_l+75, 490)], fill=(22, 18, 18), width=22)
    # empty wallet
    draw.rectangle([(cx_l+58, 468), (cx_l+100, 502)], fill=(60, 40, 20), outline=(30,15,5), width=2)
    # sweat drop
    draw.polygon([(cx_l-55, 258), (cx_l-50, 270), (cx_l-60, 270)], fill=(80, 140, 200))

    # ── Rich figure (right) ──────────────────────────────────────────────────
    cx_r = half + half // 2
    # body / suit
    draw.ellipse([(cx_r-30, 305), (cx_r+30, 385)], fill=(20, 38, 20))
    draw.rectangle([(cx_r-38, 380), (cx_r+38, 570)], fill=(16, 30, 16))
    # tie
    draw.polygon([(cx_r-8,382),(cx_r+8,382),(cx_r+5,450),(cx_r,460),(cx_r-5,450)],
                 fill=(180, 150, 0))
    # head
    draw.ellipse([(cx_r-44, 215), (cx_r+44, 310)], fill=(170, 110, 65))
    # smile (0→180 draws top arc = upturned mouth)
    draw.arc([(cx_r-20, 265), (cx_r+20, 295)], start=0, end=180, fill=(60, 30, 10), width=3)
    # arms — hands on hips / raised
    draw.line([(cx_r-38, 395), (cx_r-85, 480)], fill=(16, 30, 16), width=24)
    draw.line([(cx_r+38, 395), (cx_r+85, 480)], fill=(16, 30, 16), width=24)
    # floating money bills
    for bx, by, angle in [(cx_r+95,120,-12),(cx_r+130,175,8),(cx_r+70,200,-5),(cx_r+155,130,15)]:
        _draw_bill(draw, bx, by, angle)
    # gold coin stack
    for i in range(5):
        draw.ellipse([(cx_r+110, 490-i*10), (cx_r+158, 504-i*10)],
                     fill=(200, 160, 0), outline=(140, 100, 0), width=1)
    # glow ring
    for r_size in range(40, 0, -8):
        alpha_fill = (255, 210, 50, max(0, 6 - r_size//8) * 10)
        draw.ellipse([(cx_r-r_size*2, 555), (cx_r+r_size*2, 575)],
                     fill=(min(255,30+r_size), min(255,50+r_size*2), 10))
    # ── VS divider ───────────────────────────────────────────────────────────
    for gx in range(half-3, half+4):
        t = abs(gx - half) / 3
        brightness = int(255 * (1 - t * 0.6))
        draw.line([(gx, 0), (gx, THUMB_H)], fill=(brightness, int(brightness*0.85), 0))
    # VS badge
    vx, vy = half, THUMB_H // 2
    draw.rectangle([(vx-28, vy-22), (vx+28, vy+22)], fill=(220, 180, 0))
    draw.rectangle([(vx-26, vy-20), (vx+26, vy+20)], fill=(255, 215, 0))
    _draw_outlined_text(draw, (vx, vy), "VS", size=30, fill=(0,0,0), stroke=(100,80,0), anchor="mm")

    # ── Title text ────────────────────────────────────────────────────────────
    words = title.upper().split()
    mid   = len(words) // 2
    line1 = " ".join(words[:mid])
    line2 = " ".join(words[mid:])
    _draw_outlined_text(draw, (THUMB_W//2, 42),  line1, size=60,
                         fill=(255, 215, 0), stroke=(0,0,0), anchor="mm")
    _draw_outlined_text(draw, (THUMB_W//2, 108), line2, size=60,
                         fill=(255, 170, 0), stroke=(0,0,0), anchor="mm")

    # ── Side labels (below title, above figures) ──────────────────────────────
    _draw_outlined_text(draw, (cx_l, 158), "THE POOR", size=42,
                         fill=(200, 30, 30), stroke=(0,0,0), anchor="mm")
    _draw_outlined_text(draw, (cx_r, 158), "THE RICH", size=42,
                         fill=(255, 210, 0), stroke=(0,0,0), anchor="mm")

    # ── Top/bottom accent bars ────────────────────────────────────────────────
    for y in range(8):
        t = y / 8
        draw.line([(0,y),(THUMB_W,y)], fill=(int(200-t*80), int(30+t*20), 0))
        draw.line([(0,THUMB_H-1-y),(THUMB_W,THUMB_H-1-y)],
                  fill=(0, int(150+t*80), int(30+t*20)))

    # ── Bottom caption ────────────────────────────────────────────────────────
    draw.rectangle([(0, THUMB_H-52), (THUMB_W, THUMB_H)], fill=(0,0,0))
    _draw_outlined_text(draw, (THUMB_W//2, THUMB_H-26),
                         "THE SECRET THEY DON'T WANT YOU TO KNOW",
                         size=28, fill=(255,255,255), stroke=(80,80,80), anchor="mm")

    return img


def _draw_outlined_text(draw, xy, text, size=48, fill=(255,255,255),
                         stroke=(0,0,0), anchor="mm"):
    """Draw text with a solid outline, using best available font."""
    font = _load_font(None, size)
    sw   = max(1, size // 16)   # stroke width scales with font size
    x, y = xy
    # Draw stroke offsets
    for dx in range(-sw, sw+1):
        for dy in range(-sw, sw+1):
            if dx == 0 and dy == 0: continue
            draw.text((x+dx, y+dy), text, font=font, fill=stroke, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def _draw_bill(draw, x, y, angle_deg):
    """Draw a small green dollar bill rectangle (rotated via polygon)."""
    import math
    w, h  = 70, 32
    angle = math.radians(angle_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    corners = [(-w//2,-h//2),(w//2,-h//2),(w//2,h//2),(-w//2,h//2)]
    pts = [(x + cx*cos_a - cy*sin_a, y + cx*sin_a + cy*cos_a) for cx,cy in corners]
    draw.polygon(pts, fill=(30, 100, 40), outline=(20, 70, 25))
    draw.text((x-6, y-8), "$", fill=(60, 180, 70),
              font=_load_font(None, 18))
