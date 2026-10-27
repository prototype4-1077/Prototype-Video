"""Continuous, subpixel eyelid coverage for the registered GS070 blink source.

This is a local deterministic compositor control, not generated imagery.  The
same warm closed-lid source is revealed as the upper and lower margins travel;
there is no full-closure threshold and no full-face frame crossfade.
"""
from __future__ import annotations

import math

import cv2
import numpy as np


def lid_alpha_masks(
    shape: tuple[int, int],
    center: tuple[int, int],
    radius: tuple[int, int],
    closure: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return upper/lower coverage and an empty synthetic-crease channel.

    Coverage is monotone and continuous in ``closure`` (within 8-bit alpha
    quantization).  The upper margin performs most of the travel.  The feathered
    socket is revealed by those same moving margins rather than switched on at
    one special closure value.  Consumers must blend the maximum of the two
    masks once, not repeatedly blend overlapping fractional alpha.
    """
    if not math.isfinite(closure) or not 0.0 <= closure <= 1.0:
        raise ValueError("blink closure must be finite and inside [0, 1]")
    height, width = shape
    cx, cy = center
    rx, ry = radius
    if min(height, width, rx, ry) <= 0:
        raise ValueError("blink dimensions and radii must be positive")
    x1, y1 = cx - rx - 5, cy - ry - 12
    x2, y2 = cx + rx + 6, cy + ry + 12
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("blink socket must fit inside the source plate")
    upper = np.zeros(shape, dtype=np.uint8)
    lower = np.zeros(shape, dtype=np.uint8)
    crease = np.zeros(shape, dtype=np.uint8)
    if closure == 0.0:
        return upper, lower, crease

    local_shape = (y2 - y1, x2 - x1)
    local_center = (cx - x1, cy - y1)
    socket = np.zeros(local_shape, dtype=np.uint8)
    # These are the same full-close +3/+4/+5 socket rings as Phase42 v1.
    # Draw outside-in so the 255 core owns overlaps exactly once.
    for expansion, alpha in ((5, 85), (4, 170), (3, 255)):
        raw = np.zeros(local_shape, dtype=np.uint8)
        cv2.ellipse(
            raw, local_center, (rx + expansion, ry + expansion),
            0.0, 0.0, 360.0, 255, -1, lineType=cv2.LINE_AA,
        )
        socket[raw > 128] = alpha

    yy = np.indices(local_shape, dtype=np.float64)[0]
    meeting_y = local_center[1] + 0.30 * ry
    # Start beyond the feather plus the blur footprint, so the limit at zero
    # matches the exact neutral bypass instead of exposing the top pole early.
    upper_start = local_center[1] - ry - 9.0
    lower_start = local_center[1] + ry + 9.0
    # A six-pixel meeting overlap is enough for at least one softened margin
    # to be fully opaque at every row.  The single max-alpha blend avoids a
    # second opacity application inside that overlap.
    upper_edge = upper_start + closure * (meeting_y + 3.0 - upper_start)
    lower_edge = lower_start - closure * (lower_start - (meeting_y - 3.0))
    # A one-pixel analytic coverage ramp gives true subpixel motion instead of
    # integer-row steps followed by blur.  Blur only softens the moving edge;
    # multiplying afterwards cannot escape the declared socket write support.
    upper_coverage = np.clip(upper_edge - yy + 0.5, 0.0, 1.0)
    lower_coverage = np.clip(yy - lower_edge + 0.5, 0.0, 1.0)
    for output, coverage in ((upper, upper_coverage), (lower, lower_coverage)):
        softened = cv2.GaussianBlur(coverage, (0, 0), sigmaX=0.7, sigmaY=0.7)
        output[y1:y2, x1:x2] = np.rint(softened * socket).astype(np.uint8)
    return upper, lower, crease
