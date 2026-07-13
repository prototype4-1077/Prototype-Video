"""Render caption + title overlays on the canonical 1080x1920 portrait canvas.

The 16:9 footage band is vertically centered, captions sit in the lower black band,
white text + pale-yellow keywords in subtle dark boxes, bold rounded all-caps title."""
import os, re
from PIL import Image, ImageDraw, ImageFont

from video_format import BAND_HEIGHT, BAND_Y, HEIGHT, WIDTH

W, H = WIDTH, HEIGHT               # 9:16 phone canvas
BAND_H = BAND_HEIGHT                # 16:9 footage band, shared with assemble.py
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
TITLE_MAX_BLOCK_H = 820             # stays above captions and TikTok UI
TITLE_MIN_FONT_SIZE = 12
TITLE_FONT_STEP = 6


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


def caption_png(text, keywords, out_path, kw_overlay_prefix=None):
    """Static mode (kw_overlay_prefix=None): keywords baked yellow.
    Dynamic mode: keywords white in the base PNG; per-keyword yellow glyph
    overlay PNGs written to <prefix><j>.png; returns [(keyword, overlay_path)]."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(CAPTION_FONT, FONT_SIZE)
    kwmap = {}  # normalized word -> keyword index
    for j, k in enumerate(keywords):
        for wd in re.findall(r"[\w']+", k.lower()):
            kwmap.setdefault(wd, j)
    words = [(w, kwmap.get(re.sub(r"[^\w']", "", w).lower())) for w in text.split()]
    lines = _wrap(words, font, d)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + 2 * LINE_PAD_Y
    total_h = len(lines) * line_h + (len(lines) - 1) * LINE_GAP
    y = min(BLOCK_CENTER_Y - total_h // 2, H - total_h - 24)
    dynamic = kw_overlay_prefix is not None
    ovs = {}
    if dynamic:
        for j in set(kwmap.values()):
            ovs[j] = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for line in lines:
        line_text = " ".join(w for w, _ in line)
        lw = d.textlength(line_text, font=font)
        x0 = (W - lw) / 2
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


def _fit_title(title, draw, font_size):
    """Return a wrapped title layout guaranteed to fit the portrait safe area."""
    words = [(w, False) for w in title.split()]
    size = max(int(font_size), TITLE_MIN_FONT_SIZE)
    while size >= TITLE_MIN_FONT_SIZE:
        font = _font(TITLE_FONT, size)
        lines = _wrap(words, font, draw, max_line_w=TITLE_MAX_LINE_W,
                      split_overlong=False)
        ascent, descent = font.getmetrics()
        line_h = int((ascent + descent) * 0.98)
        widest = max(draw.textlength(" ".join(w for w, _ in line), font=font)
                     for line in lines)
        total_h = line_h * len(lines)
        if widest <= TITLE_MAX_LINE_W and total_h <= TITLE_MAX_BLOCK_H:
            return font, lines, line_h
        size -= TITLE_FONT_STEP
    # TITLE_MIN_FONT_SIZE plus character-splitting makes this reachable only for
    # pathological titles, but still return a deterministic in-bounds layout.
    font = _font(TITLE_FONT, TITLE_MIN_FONT_SIZE)
    lines = _wrap(words, font, draw, max_line_w=TITLE_MAX_LINE_W,
                  split_overlong=True)
    ascent, descent = font.getmetrics()
    return font, lines, int((ascent + descent) * 0.98)


def title_png(title, out_path, font_size=190):
    """Bold rounded ALL-CAPS title, white with shadow, centered over the footage band.
    It automatically wraps, splits long tokens, and shrinks when necessary so
    every title remains inside the 9:16 portrait safe area."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    title = " ".join(title.upper().split()) or "UNTITLED"
    font, lines, line_h = _fit_title(title, d, font_size)
    total_h = line_h * len(lines)
    cy = BAND_Y + BAND_H // 2       # center of footage band
    y = cy - total_h // 2
    for line in lines:
        wd = " ".join(w for w, _ in line)
        lw = d.textlength(wd, font=font)
        x = (W - lw) / 2
        for dx, dy in [(-4, 4), (4, 4), (0, 6), (0, -3)]:
            d.text((x + dx, y + dy), wd, font=font, fill=(0, 0, 0, 170))
        d.text((x, y), wd, font=font, fill=WHITE)
        y += line_h
    img.save(out_path)
    return out_path
