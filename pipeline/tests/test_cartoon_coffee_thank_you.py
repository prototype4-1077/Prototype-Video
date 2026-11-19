"""Verify the isolated coffee handoff without encoding media."""

from dataclasses import asdict
from fractions import Fraction
import json
from pathlib import Path
import shutil
import unittest

import cv2
import numpy as np

from pipeline import cartoon_coffee_thank_you as handoff


PACKAGE = handoff.ROOT / "collab/june_coffee_thank_you_motion_v1"
PROOF = PACKAGE / "handoff-proof.json"


class CoffeeThankYouTests(unittest.TestCase):
    def test_40_frame_slide_and_contact_then_release(self):
        self.assertEqual((handoff.N, handoff.SLIDE), (40, 112))
        cues = [handoff.cues(frame) for frame in range(40)]
        self.assertEqual(cues[0].mug_dx, -112)
        self.assertEqual(cues[-1].mug_dx, 0)
        self.assertTrue(all(a.mug_dx <= b.mug_dx for a, b in zip(cues, cues[1:])))
        self.assertTrue(all(cue.mug_dx == -112 for cue in cues[:5]))
        self.assertTrue(all(cue.mug_dx == 0 for cue in cues[16:]))
        self.assertEqual(next(i for i, cue in enumerate(cues) if cue.guest_wrap == 1), 23)
        self.assertEqual(next(i for i, cue in enumerate(cues) if cue.june_release > 0), 24)
        self.assertTrue(all(cue.guest_wrap == 1 and cue.mug_dx == 0
                            for cue in cues if cue.june_release > 0))
        self.assertTrue(any(cue.guest_quiver != 0 for cue in cues[:23]))
        self.assertTrue(all(cue.guest_quiver == 0 for cue in cues[23:]))
        self.assertTrue(all(cue.june_release == 1 for cue in cues[30:]))
        for bad in (-1, 40, 23.0, True):
            with self.subTest(frame=bad), self.assertRaisesRegex(ValueError, "outside coffee exchange"):
                handoff.cues(bad)

    def test_single_filled_mug_with_open_handle_and_fixed_table(self):
        setup = handoff.prepare()
        self.assertEqual(setup.spec["preview_clock"], {"fps": 30, "frames": 40, "new_audio": False})
        x, y, _, _ = handoff.COFFEE
        alpha = setup.mug[..., 3]
        # One connected porcelain silhouette including its handle. The
        # center of that loop is transparent; ceramic on its right is not.
        self.assertEqual(cv2.connectedComponents((alpha > 0.5).astype(np.uint8))[0], 2)
        self.assertEqual(alpha[470-y, 982-x], 0)
        self.assertEqual(alpha[470-y, 1029-x], 1)
        self.assertEqual(alpha[584-y, 771-x], 1)
        _, art = handoff.load_art()
        coffee = np.s_[354:367, 724:859]
        start_coffee = np.s_[354:367, 724-handoff.SLIDE:859-handoff.SLIDE]
        self.assertFalse(np.array_equal(art["approach"][coffee], art["receiving"][coffee]))
        fixed = (np.s_[:61, 729:936], np.s_[800:, :])
        for frame in (0, 9, 16, 23, 30, 39):
            with self.subTest(frame=frame):
                picture = handoff.paint(setup, frame)
                self.assertEqual((picture.shape, picture.dtype), ((941, 1672, 3), np.uint8))
                for region in fixed:
                    np.testing.assert_array_equal(picture[region], setup.table[region])
                if frame == 0 or frame >= 16:
                    np.testing.assert_array_equal(picture[start_coffee if frame == 0 else coffee],
                                                  art["receiving"][coffee])

    @unittest.skipUnless(PROOF.is_file() and shutil.which("ffprobe"), "published handoff proof or ffprobe unavailable")
    def test_published_handoff_receipt_and_silent_clock(self):
        proof = json.loads(PROOF.read_text(encoding="utf-8"))
        movie = PACKAGE / "coffee-handoff.mp4"
        digest = handoff.registration.cut.beat.digest
        self.assertEqual(proof["state"], "isolated_silent_motion_test")
        self.assertEqual(proof["clock"], [1920, 1080, 30, 40])
        self.assertEqual(proof["renderer_sha256"], digest(Path(handoff.__file__)))
        self.assertEqual(proof["movie_sha256"], digest(movie))
        self.assertEqual(len(proof["rgb24_native_frame_sha256"]), 40)
        self.assertEqual(proof["handoff_contact_frame"], 23)
        self.assertEqual((proof["mug_slide_px_native"], proof["mug_lift_px_native"]), (112, 0))
        self.assertEqual(proof["cues"], [asdict(handoff.cues(i)) for i in range(40)])
        for flag in ("integrated_into_full_cut", "human_accepted", "production_release"):
            self.assertIs(proof[flag], False)
        video, = handoff.media._probe(movie, "ffprobe")["streams"]
        self.assertEqual((video["codec_type"], video["width"], video["height"]), ("video", 1920, 1080))
        self.assertEqual(int(video["nb_read_frames"]), 40)
        self.assertEqual(Fraction(video["avg_frame_rate"]), Fraction(30))
        self.assertEqual(int(video["duration_ts"]) * Fraction(video["time_base"]), Fraction(40, 30))

    @unittest.skipUnless(PROOF.is_file(), "published handoff proof unavailable")
    def test_decoded_chip_moves_only_horizontally_and_stops_before_touch(self):
        movie = PACKAGE / "coffee-handoff.mp4"
        decoder = cv2.VideoCapture(str(movie))
        frames = []
        try:
            for i in range(40):
                ok, frame = decoder.read()
                self.assertTrue(ok, f"no decoded F{i}")
                frames.append(cv2.cvtColor(frame[400:510, 676:961], cv2.COLOR_BGR2GRAY))
        finally:
            decoder.release()
        template = frames[-1][22:92, 177:252]
        tracked = [cv2.minMaxLoc(cv2.matchTemplate(frame, template, cv2.TM_SQDIFF_NORMED))
                   for frame in frames]
        tx, ty = tracked[-1][2]
        offsets = [(row[2][0]-tx, row[2][1]-ty) for row in tracked]
        self.assertTrue(all(row[0] < .008 for row in tracked))
        self.assertAlmostEqual(offsets[0][0], -129, delta=2)
        self.assertLessEqual(max(abs(y) for _, y in offsets), 1)
        self.assertTrue(all(abs(x) <= 1 for x, _ in offsets[16:]))


if __name__ == "__main__":
    unittest.main()
