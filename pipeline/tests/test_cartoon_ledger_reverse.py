"""Verify the ledger reverse can only replace its authorized picture span."""

from fractions import Fraction
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_ledger_reverse as reverse


PACKAGE = reverse.prior.payoff.ROOT / "collab/june_ledger_reverse_v1"
PROOF = PACKAGE / "ledger-reverse-proof.json"


class LedgerReverseTests(unittest.TestCase):
    def test_single_existing_shot_same_length_and_safe_aperture(self):
        self.assertEqual((reverse.START, reverse.STOP, reverse.TOTAL), (396, 452, 1191))
        self.assertEqual(reverse.STOP-reverse.START, 56)
        self.assertEqual(reverse.PREVIEW, (312, 538))
        self.assertEqual(reverse.PREVIEW[1]-reverse.PREVIEW[0], 226)
        width, height, left, top = reverse.CROP
        self.assertEqual(reverse.CROP, (1280, 720, 120, 4))
        self.assertEqual(Fraction(width, height), Fraction(16, 9))
        self.assertTrue(all(i % 2 == 0 for i in reverse.CROP))
        self.assertTrue(0 <= left < left+width <= 1920 and 0 <= top < top+height <= 1080)
        self.assertEqual(reverse.TOTAL - (reverse.STOP-reverse.START), 1135)
        previous = PACKAGE.parent / "june_visitor_return_v1/visitor-return-integration.json"
        self.assertEqual(reverse.BASE_SHA, json.loads(previous.read_text(encoding="utf-8"))["movie_sha256"])

    def test_real_narration_is_zero_at_both_review_edges_and_noisy_edges_fail(self):
        recipe, paths, contract = reverse.cut.load_plan()
        original, _ = reverse.cut.full_mix(recipe, paths, contract)
        samples = reverse.prior.payoff.extend_sound(original)
        reverse.quiet(samples, "WAV")
        self.assertGreater(np.count_nonzero(samples[312*1600:538*1600]), 0)
        for frame in reverse.PREVIEW:
            with self.subTest(frame=frame):
                position = frame*1600-1440
                self.assertEqual(int(samples[position, 0]), 0)
                samples[position, 0] = 1
                with self.assertRaisesRegex(ValueError, "WAV review edges are not digitally silent"):
                    reverse.quiet(samples, "WAV")
                samples[position, 0] = 0
        with self.assertRaisesRegex(ValueError, "review edges are not digitally silent"):
            reverse.quiet(samples[:-1], "short PCM")

    def test_picture_audit_rejects_packet_or_decoded_drift_beyond_the_reverse(self):
        first, stop, total = reverse.START, reverse.STOP, reverse.TOTAL

        def row(i, prefix, edges):
            return dict(pts=i*1000, dts=i*1000, duration=1000, data_hash=f"{prefix}-{i}",
                        flags="K__" if i in edges else "___")

        original = [row(i, "old", {0, first, stop}) for i in range(total)]
        isolated = [row(i, "new", {0}) for i in range(stop-first)]
        moved = [{**r, "pts": r["pts"]+first*1000, "dts": r["dts"]+first*1000} for r in isolated]
        alternate = original[:first] + moved + original[stop:]
        packets = {"before": original, "after": alternate, "new": isolated}
        old_frames = [f"decode-old-{i}" for i in range(total)]
        new_frames = [f"decode-new-{i}" for i in range(stop-first)]
        edited_frames = old_frames[:first] + new_frames + old_frames[stop:]
        frames = {"before": old_frames, "after": edited_frames, "new": new_frames}
        with patch.object(reverse.probe, "packet_info", side_effect=lambda p, _: packets[p]), \
                patch.object(reverse, "frame_hashes", side_effect=frames.__getitem__):
            reverse.check_picture("before", "after", "new")
            for i in (first-1, stop):
                with self.subTest(packet=i):
                    saved = alternate[i]
                    alternate[i] = {**saved, "data_hash": "edited another GOP"}
                    with self.assertRaisesRegex(ValueError, "packets moved or changed beyond the one reverse"):
                        reverse.check_picture("before", "after", "new")
                    alternate[i] = saved
                with self.subTest(decoded=i):
                    saved_frame = edited_frames[i]
                    edited_frames[i] = "decoded another GOP differently"
                    with self.assertRaisesRegex(ValueError, "decoded frame audit failed"):
                        reverse.check_picture("before", "after", "new")
                    edited_frames[i] = saved_frame
            new_frames[0] = edited_frames[first] = old_frames[first]
            with self.assertRaisesRegex(ValueError, "decoded frame audit failed"):
                reverse.check_picture("before", "after", "new")

    @unittest.skipUnless(PROOF.is_file() and shutil.which("ffprobe"), "published ledger reverse or ffprobe unavailable")
    def test_published_review_has_frozen_evidence_and_exact_clock(self):
        proof = json.loads(PROOF.read_text(encoding="utf-8"))
        movie = PACKAGE / "ledger-reverse-review.mp4"
        self.assertEqual(proof["builder_sha256"], reverse.digest(Path(reverse.__file__)))
        self.assertEqual(proof["base_sha256"], reverse.BASE_SHA)
        self.assertEqual(proof["source_pcm_sha256"], reverse.SOURCE_PCM_SHA)
        self.assertEqual(proof["review_sha256"], reverse.digest(movie))
        self.assertEqual(proof["picture_change_frames"], [396, 452])
        self.assertEqual(proof["review_frames"], [312, 538])
        self.assertEqual(proof["crop_xywh"], [120, 4, 1280, 720])
        self.assertEqual(proof["identical_picture_frames"], 1135)
        self.assertEqual(proof["identical_audio_stereo_pairs"], 1_905_600)
        self.assertEqual(proof["duration_seconds"], 39.7)
        self.assertIs(proof["same_audio_and_caption_packets"], True)
        self.assertIs(proof["human_accepted"], False)
        self.assertIs(proof["production_release"], False)
        video, audio = reverse.cut.media._probe(movie, "ffprobe")["streams"]
        self.assertEqual((video["codec_type"], audio["codec_type"]), ("video", "audio"))
        self.assertEqual((video["width"], video["height"], int(video["nb_read_frames"])), (1536, 432, 226))
        self.assertEqual(Fraction(video["avg_frame_rate"]), Fraction(30))
        self.assertEqual((audio["sample_rate"], audio["channels"]), ("48000", 2))
        for stream in (video, audio):
            self.assertAlmostEqual(float(stream["duration"]), 226/30, places=3)


if __name__ == "__main__":
    unittest.main()
