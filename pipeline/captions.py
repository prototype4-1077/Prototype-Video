"""Render caption and title overlays for portrait social and landscape YouTube.

Portrait keeps the established 16:9 picture band and lower caption zone. The
YouTube overlays use a native 1920x1080 safe area with captions in the lower third.
"""
import os, re
from PIL import Image, ImageDraw, ImageFont

from video_format import (
    BAND_HEIGHT, BAND_Y, HEIGHT, WIDTH, YOUTUBE_HEIGHT, YOUTUBE_WIDTH,
)

W, H = WIDTH, HEIGHT               # 9:16 phone canvas
BAND_H = BAND_HEIGHT               # 16:9 footage band, shared with assemble.py
YT_W, YT_H = YOUTUBE_WIDTH, YOUTUBE_HEIGHT
_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
CAPTION_FONT = os.environ.get("CAPTION_FONT", os.path.join(_F, "Questrial-Regular.ttf"))
TITLE_FONT = os.environ.get("TITLE_FONT", os.path.join(_F, "Baloo2-ExtraBold.ttf"))
FONT_SIZE = 44
LINE_PAD_X, LINE_PAD_Y, LINE_GAP = 16, 8, 6
BOX_RGBA = (24, 24, 24, 150)       # subtle: near-invisible on the black band
WHITE = (255, 255, 255, 255)
YELLOW = (230, 232, 126, 255)
BLOCK_CENTER_Y = 1430              # below the footage band, above TikTok UI zone
MAX_LINE_W = 820
TITLE_MAX_LINE_W = 940
TITLE_MAX_BLOCK_H = 820            # stays above captions and TikTok UI
TITLE_MIN_FONT_SIZE = 12
TITLE_FONT_STEP = 6

# Landscape text is larger in pixels but occupies a similar share of the frame.
YT_FONT_SIZE = 50
YT_BLOCK_CENTER_Y = 900
YT_MAX_LINE_W = 1460
YT_TITLE_MAX_LINE_W = 1680
YT_TITLE_MAX_BLOCK_H = 610
YT_TITLE_CENTER_Y = 445


def _font(path, size):
    f = ImageFont.truetype(path, size)
    try: f.set_variation_by_axes([800])  # no-op for static fonts
    except Exception: pass
    return f


def _split_overlong_word(word, font, draw, max_line_w):
    """Split a single unbroken token so it can never escape the safe width."""
    text, marker = word
    if draw.textlength(text, font=font) <= max_line_w:
        return [word]
    parts, cur = [], ""
    for char in text:
        if cur and draw.textlength(cur + char, font=font) > max_line_w:
            parts.append((cur, marker))
            cur = char
        else:
            cur += char
    if cur:
        parts.append((cur, marker))
    return parts


def _wrap(words, font, draw, max_line_w=MAX_LINE_W, split_overlong=True):
    expanded = []
    for word in words:
        expanded.extend(_split_overlong_word(word, font, draw, max_line_w)
                        if split_overlong else [word])
    lines, cur = [], []
    for w in expanded:
        test = " ".join(x[0] for x in cur + [w])
        if cur and draw.textlength(test, font=font) > max_line_w:
            lines.append(cur); cur = [w]
        else:
            cur.append(w)
    if cur: lines.append(cur)
    return lines


def _caption_png(text, keywords, out_path, width, height, font_size,
                 block_center_y, max_line_w, kw_overlay_prefix=None):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(CAPTION_FONT, font_size)
    kwmap = {}
    for j, k in enumerate(keywords):
        for wd in re.findall(r"[\w']+", k.lower()):
            kwmap.setdefault(wd, j)
    words = [(w, kwmap.get(re.sub(r"[^\w']", "", w).lower())) for w in text.split()]
    lines = _wrap(words, font, d, max_line_w=max_line_w)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + 2 * LINE_PAD_Y
    total_h = len(lines) * line_h + (len(lines) - 1) * LINE_GAP
    y = min(block_center_y - total_h // 2, height - total_h - 24)
    dynamic = kw_overlay_prefix is not None
    ovs = {}
    if dynamic:
        for j in set(kwmap.values()):
            ovs[j] = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for line in lines:
        line_text = " ".join(w for w, _ in line)
        lw = d.textlength(line_text, font=font)
        x0 = (width - lw) / 2
        d.rounded_rectangle([x0 - LINE_PAD_X, y, x0 + lw + LINE_PAD_X, y + line_h],
                            radius=6, fill=BOX_RGBA)
        x = x0
        for w, j in line:
            hot = j is not None
            base_fill = WHITE if (dynamic or not hot) else YELLOW
            d.text((x, y + LINE_PAD_Y), w, font=font, fill=base_fill)
            if dynamic and hot:
                ImageDraw.Draw(ovs[j]).text((x, y + LINE_PAD_Y), w, font=font, fill=YELLOW)
            x += d.textlength(w + " ", font=font)
        y += line_h + LINE_GAP
    img.save(out_path)
    result = []
    if dynamic:
        for j, ov in sorted(ovs.items()):
            p = f"{kw_overlay_prefix}{j}.png"
            ov.save(p)
            result.append((keywords[j], p))
    return result


def caption_png(text, keywords, out_path, kw_overlay_prefix=None):
    """Render the established 1080x1920 social caption overlay."""
    return _caption_png(text, keywords, out_path, W, H, FONT_SIZE,
                        BLOCK_CENTER_Y, MAX_LINE_W, kw_overlay_prefix)


def youtube_caption_png(text, keywords, out_path, kw_overlay_prefix=None):
    """Render a native 1920x1080 lower-third caption overlay."""
    return _caption_png(text, keywords, out_path, YT_W, YT_H, YT_FONT_SIZE,
                        YT_BLOCK_CENTER_Y, YT_MAX_LINE_W, kw_overlay_prefix)


def _fit_title(title, draw, font_size, max_line_w=TITLE_MAX_LINE_W,
               max_block_h=TITLE_MAX_BLOCK_H):
    """Return a wrapped title layout guaranteed to fit its target safe area."""
    words = [(w, False) for w in title.split()]
    size = max(int(font_size), TITLE_MIN_FONT_SIZE)
    while size >= TITLE_MIN_FONT_SIZE:
        font = _font(TITLE_FONT, size)
        lines = _wrap(words, font, draw, max_line_w=max_line_w,
                      split_overlong=False)
        ascent, descent = font.getmetrics()
        line_h = int((ascent + descent) * 0.98)
        widest = max(draw.textlength(" ".join(w for w, _ in line), font=font)
                     for line in lines)
        total_h = line_h * len(lines)
        if widest <= max_line_w and total_h <= max_block_h:
            return font, lines, line_h
        size -= TITLE_FONT_STEP
    font = _font(TITLE_FONT, TITLE_MIN_FONT_SIZE)
    lines = _wrap(words, font, draw, max_line_w=max_line_w,
                  split_overlong=True)
    ascent, descent = font.getmetrics()
    return font, lines, int((ascent + descent) * 0.98)


def _title_png(title, out_path, width, height, center_y, max_line_w,
               max_block_h, font_size):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    title = " ".join(title.upper().split()) or "UNTITLED"
    font, lines, line_h = _fit_title(title, d, font_size, max_line_w, max_block_h)
    total_h = line_h * len(lines)
    y = center_y - total_h // 2
    for line in lines:
        words = " ".join(w for w, _ in line)
        lw = d.textlength(words, font=font)
        x = (width - lw) / 2
        for dx, dy in [(-4, 4), (4, 4), (0, 6), (0, -3)]:
            d.text((x + dx, y + dy), words, font=font, fill=(0, 0, 0, 170))
        d.text((x, y), words, font=font, fill=WHITE)
        y += line_h
    img.save(out_path)
    return out_path


def title_png(title, out_path, font_size=190):
    """Render the established title over the portrait picture band."""
    return _title_png(title, out_path, W, H, BAND_Y + BAND_H // 2,
                      TITLE_MAX_LINE_W, TITLE_MAX_BLOCK_H, font_size)


def youtube_title_png(title, out_path, font_size=170):
    """Render a native 16:9 title above the YouTube caption safe area."""
    return _title_png(title, out_path, YT_W, YT_H, YT_TITLE_CENTER_Y,
                      YT_TITLE_MAX_LINE_W, YT_TITLE_MAX_BLOCK_H, font_size)
