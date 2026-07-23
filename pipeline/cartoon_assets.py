"""Derive limited_2_5d layer assets from committed cartoon reference art.

Auto chroma-keys character cutouts (samples the actual corner background colour so
imperfect generated greens still key), derives an eye band for blinks, and makes a
procedural steam wisp. Never uses stock; only committed/derived cartoon art.
"""
from __future__ import annotations
import numpy as np
from PIL import Image, ImageFilter, ImageDraw


def auto_key(path, tol=78, feather=1.5, opaque=False):
    im = Image.open(path).convert("RGBA"); a = np.asarray(im).astype(np.int16)
    h, w = a.shape[:2]
    corners = np.concatenate([a[:8,:8,:3].reshape(-1,3), a[:8,-8:,:3].reshape(-1,3),
                              a[-8:,:8,:3].reshape(-1,3), a[-8:,-8:,:3].reshape(-1,3)])
    bg = np.median(corners, axis=0)
    dist = np.sqrt(((a[:,:,:3]-bg)**2).sum(axis=2))
    alpha = (np.where(dist>tol,255,0) if opaque else np.clip((dist-tol)*4,0,255)).astype(np.uint8)
    out = np.dstack([a[:,:,:3].astype(np.uint8), alpha])
    im2 = Image.fromarray(out, "RGBA")
    im2.putalpha(im2.split()[3].filter(ImageFilter.GaussianBlur(0.4 if opaque else feather)))
    return _autocrop(im2)


def _autocrop(im):
    bb = im.split()[3].getbbox()
    return im.crop(bb) if bb else im


def eye_band(cutout, y_frac=0.30, h_frac=0.07):
    w, h = cutout.size
    return cutout.crop((0, int(h*y_frac), w, int(h*(y_frac+h_frac))))


def procedural_steam(size=(120, 260)):
    w, h = size; im = Image.new("RGBA", size, (0,0,0,0)); d = ImageDraw.Draw(im)
    import math
    for i in range(3):
        for y in range(0, h, 6):
            t = y/h; x = w/2 + math.sin(y/22.0 + i*2)*w*0.22*(1-t)
            r = max(1, int(10*(1-t))); a = int(120*(1-t))
            d.ellipse([x-r, y-r, x+r, y+r], fill=(255,255,255,a))
    return im.filter(ImageFilter.GaussianBlur(3))
