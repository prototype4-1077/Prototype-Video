"""Render caption + title overlay PNGs (1080x1080 transparent), reference letterbox style:
footage band 1080x608 centered (y 236-844), captions in the bottom black band,
white text + pale-yellow keywords in subtle dark boxes, bold rounded all-caps title."""
import os, re
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920                  # 9:16 phone canvas
BAND_Y, BAND_H = 656, 608          # 16:9 footage band, vertically centered; used by assemble.py
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


def _font(path, size):
    f = ImageFont.truetype(path, size)
    try: f.set_variation_by_axes([800])  # no-op for static fonts
    except Exception: pass
    return f


def _wrap(words, font, draw):
    lines, cur = [], []
    for w in words:
        test = " ".join(x[0] for x in cur + [w])
        if cur and draw.textlength(test, font=font) > MAX_LINE_W:
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


def title_png(title, out_path, font_size=190):
    """Bold rounded ALL-CAPS title, white with shadow, centered over the footage band.
    2x size (James, July 2026); wraps onto multiple lines and may extend past the
    letterbox band onto the black canvas, but never into the caption zone."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    title = title.upper()
    font = _font(TITLE_FONT, font_size)
    # wrap within 940px wide and ~940px tall (stays clear of captions at ~y1430)
    while True:
        lines = _wrap([(w, False) for w in title.split()], font, d)
        widest = max(d.textlength(" ".join(w for w, _ in l), font=font) for l in lines)
        asc, desc = font.getmetrics()
        total = int((asc + desc) * 0.98) * len(lines)
        if (widest <= 940 and total <= 940) or font_size <= 100: break
        font_size -= 8
        font = _font(TITLE_FONT, font_size)
    ascent, descent = font.getmetrics()
    line_h = int((ascent + descent) * 0.98)
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
