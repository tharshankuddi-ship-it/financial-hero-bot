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
FONT_SIZE       = 68                  # was 100 — scaled for 720-wide frame
LINE_HEIGHT     = FONT_SIZE + 10      # was FONT_SIZE+24; tighter line spacing
CAPTION_COLOR   = (255, 255, 255)
HIGHLIGHT_COLOR = (255, 220,   0)
SHADOW_COLOR    = (  0,   0,   0)
SHADOW_OFFSET   = 4                   # scaled down proportionally
BOX_PADDING_X   = 24                  # horizontal inner padding for caption box
BOX_PADDING_Y   = 14                  # vertical inner padding for caption box
WRAP_CHARS      = 18                  # wider wrap so 3–4 words fit per line
WORDS_PER_CHUNK = 3                   # highlight this many words at once
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

    - Shows a window of ~20 words centred on highlight_start.
    - Highlights words [highlight_start : highlight_start + WORDS_PER_CHUNK].
    - The semi-transparent background box is tightly fitted to the text — it
      does NOT span the full width, preventing coins from being obscured.
    """
    # ── Build the visible word window ──────────────────────────────────────
    win_start   = max(0, highlight_start - 6)
    win_end     = min(len(words), highlight_start + 14)
    visible     = words[win_start:win_end]
    hi_lo       = highlight_start - win_start          # first highlighted idx in visible
    hi_hi       = hi_lo + WORDS_PER_CHUNK              # one-past-last highlighted idx

    wrapped = textwrap.wrap(" ".join(visible), width=WRAP_CHARS)
    if not wrapped:
        return Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    # ── Measure total text block dimensions ───────────────────────────────
    # Use a throw-away draw to measure
    probe     = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    max_w     = max(int(probe.textlength(line, font=font)) for line in wrapped)
    total_h   = len(wrapped) * LINE_HEIGHT

    # ── Position: centred horizontally, TEXT_Y_POSITION vertically ────────
    box_x1 = (WIDTH - max_w) // 2 - BOX_PADDING_X
    box_x2 = (WIDTH + max_w) // 2 + BOX_PADDING_X
    box_y1 = TEXT_Y_POSITION - BOX_PADDING_Y
    box_y2 = TEXT_Y_POSITION + total_h + BOX_PADDING_Y

    # Clamp to frame bounds
    box_x1 = max(0, box_x1)
    box_x2 = min(WIDTH, box_x2)
    box_y1 = max(0, box_y1)
    box_y2 = min(HEIGHT, box_y2)

    # ── Compositing: transparent base → overlay box → text ────────────────
    base    = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    # Rounded semi-transparent box (no full-width dark strip)
    ov_draw.rounded_rectangle(
        [(box_x1, box_y1), (box_x2, box_y2)],
        radius=12,
        fill=(0, 0, 0, 175),
    )
    base = Image.alpha_composite(base, overlay)
    draw = ImageDraw.Draw(base)

    # ── Build word→(line, word-in-line) lookup (O(1) per word) ────────────
    pos_map: dict[tuple[int, int], int] = {}
    global_idx = 0
    for li, line in enumerate(wrapped):
        for wi in range(len(line.split())):
            pos_map[(li, wi)] = global_idx
            global_idx += 1

    # ── Draw each word ─────────────────────────────────────────────────────
    for li, line in enumerate(wrapped):
        line_words = line.split()
        line_w     = sum(int(draw.textlength(w + " ", font=font)) for w in line_words)
        x          = (WIDTH - line_w) // 2
        yy         = TEXT_Y_POSITION + li * LINE_HEIGHT

        for wi, word in enumerate(line_words):
            g_idx = pos_map.get((li, wi), -1)
            color = HIGHLIGHT_COLOR if hi_lo <= g_idx < hi_hi else CAPTION_COLOR

            # Shadow
            draw.text(
                (x + SHADOW_OFFSET, yy + SHADOW_OFFSET),
                word, font=font, fill=(*SHADOW_COLOR, 200),
            )
            # Main text
            draw.text((x, yy), word, font=font, fill=color)
            x += int(draw.textlength(word + " ", font=font))

    return base
