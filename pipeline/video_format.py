"""Canonical geometry for every rendered TikTok video.

Keep canvas dimensions here so rendering, captions, and review sheets cannot
silently drift to different aspect ratios.
"""

WIDTH = 1080
HEIGHT = 1920
FPS = 30

ASPECT_WIDTH = 9
ASPECT_HEIGHT = 16

# Default letterboxed picture area inside the portrait canvas.
BAND_WIDTH = WIDTH
BAND_HEIGHT = 608
BAND_Y = (HEIGHT - BAND_HEIGHT) // 2


def is_portrait_9_16(width=WIDTH, height=HEIGHT):
    """Return True when dimensions are an exact 9:16 display ratio."""
    return width * ASPECT_HEIGHT == height * ASPECT_WIDTH


assert is_portrait_9_16(), "Canonical video canvas must remain 9:16 portrait"
