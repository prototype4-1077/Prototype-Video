"""Guard the picture-only correction and its published review evidence."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_reaction_continuity as repair


PACK = repair.acting.sources.ROOT / "collab/june_pencil_continuity_v1"


class ReactionContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prepared = repair.acting.prepare()

    def test_crop_contains_whole_face_support_and_excludes_wrong_hand(self):
        x, y, r, b = repair.CROP
        hx, hy, hr, hb = repair.acting.HEAD_ROI
        self.assertTrue(x < hx < hr < r and y < hy < hb < b)
        self.assertEqual((r - x) * 9, (b - y) * 16)
        self.assertLess(b, repair.acting.HAND_ROI[1])
        self.assertEqual(repair.PENCIL["GS040_out"], repair.PENCIL["GS060_in"])
        self.assertEqual(repair.PENCIL["GS050_new"], "offscreen")

    def test_same_visible_acting_and_no_hand_computation(self):
        x, y, r, b = repair.CROP
        frames = (0, 31, 40, 49, 54, 68, 82, 113)
        expected = [repair.acting.plate(self.prepared, i)[y:b, x:r] for i in frames]
        with patch.object(repair.acting, "pencil", side_effect=AssertionError("pencil used")):
            for i, ref in zip(frames, expected):
                np.testing.assert_array_equal(repair.source_frame(self.prepared, i), ref)
        self.assertGreater(np.abs(expected[0].astype(int) - expected[-1]).mean(), 2)

    def test_ab_audio_edit_edges_are_silent_with_fade_room(self):
        cut = repair.review.cut
        read = cut.foley.audio.ledger_pour._read_pcm24_wave
        pcm, meta = read(repair.review.PACKAGE / "mix.wav")
        self.assertEqual(meta["sample_rate"], 48000)
        for frame in repair.CONTEXT:
            sample = frame * cut.STEP
            self.assertFalse(np.any(pcm[sample - 1440:sample + 1440]))

    def test_frozen_receipt_and_video(self):
        cert = json.loads((PACK / "continuity-reviewed-window.json").read_text(encoding="utf-8"))
        digest = repair.review.cut.beat.digest
        clip = PACK / "pencil-continuity-review.mp4"
        self.assertEqual(digest(Path(repair.__file__)), cert["repair_source_sha256"])
        self.assertEqual(digest(clip), cert["ab_sha256"])
        self.assertEqual(cert["previous_staged_sha256"], repair.BEFORE_SHA256)
        self.assertEqual(tuple(cert["ab_full_cut_span_half_open"]), repair.CONTEXT)
        self.assertEqual(cert["replaced_span_half_open"], [564, 678])
        self.assertEqual(cert["strictly_copied_video_packets"], 1026)
        self.assertTrue(cert["audio_subtitle_packets_exact"])
        self.assertEqual(cert["audit"]["decoded_repaired_frames_exact"], 303)
        self.assertTrue(cert["audit"]["mov_pcm_exact"])
        self.assertFalse(cert["human_accepted"])
        self.assertFalse(cert["production_release"])
        video, audio = repair.review.cut.media._probe(clip, "ffprobe")["streams"]
        self.assertEqual((video["width"], video["height"]), (1536, 432))
        count = repair.CONTEXT[1] - repair.CONTEXT[0]
        self.assertEqual(int(video["nb_read_frames"]), count)
        for stream in (video, audio):
            self.assertAlmostEqual(float(stream["duration"]), count / 30, places=3)


if __name__ == "__main__":
    unittest.main()
