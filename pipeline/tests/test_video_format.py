import os
import sys
import tempfile
import unittest

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import assemble
import captions
import video_format


class VideoFormatTests(unittest.TestCase):
    def test_every_renderer_uses_the_canonical_9_16_canvas(self):
        self.assertTrue(video_format.is_portrait_9_16())
        self.assertEqual((video_format.WIDTH, video_format.HEIGHT), (1080, 1920))
        self.assertEqual((assemble.WIDTH, assemble.HEIGHT), (1080, 1920))
        self.assertEqual((captions.W, captions.H), (1080, 1920))

    def _assert_title_fits(self, title):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "title.png")
            captions.title_png(title, path)
            with Image.open(path) as image:
                self.assertEqual(image.size, (1080, 1920))
                bbox = image.getchannel("A").getbbox()
            self.assertIsNotNone(bbox)
            left, top, right, bottom = bbox
            self.assertGreaterEqual(left, 60)
            self.assertLessEqual(right, 1020)
            self.assertGreaterEqual(top, 540)
            self.assertLessEqual(bottom, 1380)

    def test_long_title_wraps_and_shrinks_inside_safe_area(self):
        self._assert_title_fits(
            "The Impossibly Complicated Conversation Between Every Version "
            "of Yourself That Ever Believed It Was Too Late"
        )

    def test_unbroken_title_token_cannot_overrun_canvas(self):
        self._assert_title_fits("CONSCIOUSNESS" * 12)


if __name__ == "__main__":
    unittest.main()
