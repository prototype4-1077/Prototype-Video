"""Check the optional longer ending without building a film."""

from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_coffee_payoff as payoff


PACKAGE = payoff.ROOT / "collab/june_coffee_payoff_v1"
PROOF = PACKAGE / "payoff-verification.json"


class CoffeePayoffTests(unittest.TestCase):
    def test_lead_shows_eleven_right_hand_reach_frames_with_fixed_mug(self):
        self.assertEqual((payoff.JOIN, payoff.LEAD, payoff.ADDED, payoff.TOTAL), (912, 11, 51, 1191))
        cues = [payoff.reach_cue(i) for i in range(payoff.LEAD + 1)]
        self.assertEqual(cues[0].june_release, 1.)
        self.assertGreater(cues[-2].june_release, 0.)
        self.assertTrue(all(a.june_release >= b.june_release for a, b in zip(cues, cues[1:])))
        self.assertTrue(all((cue.mug_dx, cue.guest_wrap, cue.guest_quiver) == (-112, 0., 0.) for cue in cues))
        self.assertEqual(cues[-1], payoff.handoff.cues(0))
        self.assertGreaterEqual(len(set(cues[:-1])), 9)

        def paint_only_cue(_, index):
            return index, payoff.handoff.cues(index)

        with patch.object(payoff.handoff, "paint", side_effect=paint_only_cue):
            self.assertEqual([payoff.frame(None, i) for i in range(payoff.LEAD)], [(0, c) for c in cues[:-1]])
            self.assertEqual(payoff.frame(None, payoff.LEAD), (0, cues[-1]))
            self.assertEqual(payoff.frame(None, payoff.ADDED-1), (39, payoff.handoff.cues(39)))
        for i in (-1, payoff.ADDED, True):
            with self.subTest(frame=i), self.assertRaisesRegex(ValueError, "outside added picture"):
                payoff.frame(None, i)

    def test_approved_pcm_is_identical_on_both_sides_of_the_insert(self):
        recipe, paths, contract = payoff.cut.load_plan()
        original, _ = payoff.cut.full_mix(recipe, paths, contract)
        original.setflags(write=False)
        result = payoff.extend_sound(original)
        split = 912 * 1600
        added = 51 * 1600
        self.assertEqual((result.shape, result.dtype), ((1191 * 1600, 2), original.dtype))
        self.assertFalse(np.shares_memory(original, result))
        np.testing.assert_array_equal(result[:split], original[:split])
        self.assertFalse(np.any(result[split:split + added]))
        np.testing.assert_array_equal(result[split + added:], original[split:])
        invalid = original.copy()
        invalid[split-1440, 0] = 1
        for pcm in (original[:-1], invalid):
            with self.assertRaisesRegex(ValueError, "not silent around the edit"):
                payoff.extend_sound(pcm)

    def test_caption_words_stay_exact_and_only_four_tail_cues_move(self):
        _, _, contract = payoff.cut.load_plan()
        unchanged = deepcopy(contract)
        mapped = payoff.extend_captions(contract)
        self.assertEqual(contract, unchanged)
        a, b = contract["dialogue_cues"], mapped["dialogue_cues"]
        self.assertEqual(len(a), 18)
        self.assertEqual(a[:14], b[:14])
        for old, new in zip(a[14:], b[14:]):
            with self.subTest(cue=old["id"]):
                expected = {**old, "start_frame": old["start_frame"] + 51, "end_frame": old["end_frame"] + 51}
                self.assertEqual(new, expected)
        self.assertEqual((a[13]["end_frame"], a[14]["start_frame"], b[14]["start_frame"]), (910, 937, 988))
        crossing = deepcopy(contract)
        crossing["dialogue_cues"][13].update(start_frame=911, end_frame=913)
        with self.assertRaisesRegex(ValueError, f'cannot interrupt spoken cue {a[13]["id"]}'):
            payoff.extend_captions(crossing)

    @unittest.skipUnless(PROOF.is_file() and shutil.which("ffprobe"), "published payoff proof or ffprobe unavailable")
    def test_published_payoff_receipt_and_both_playback_clocks(self):
        proof = json.loads(PROOF.read_text(encoding="utf-8"))
        digest = payoff.cut.beat.digest
        self.assertEqual(proof["builder_sha256"], digest(Path(payoff.__file__)))
        self.assertEqual(proof["source_sha256"], payoff.SOURCE_SHA)
        self.assertEqual(proof["clock"], [1920, 1080, 30, 1191])
        self.assertEqual(proof["inserted_span"], [912, 963])
        self.assertEqual(proof["right_hand_lead_in_frames"], 11)
        self.assertEqual(len(proof["new_native_rgb24_sha256"]), 51)
        handoff = json.loads(payoff.RAW_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(proof["new_native_rgb24_sha256"][11:], handoff["rgb24_native_frame_sha256"])
        self.assertEqual(proof["original_handoff_native_frames_exact"], 40)
        self.assertEqual(proof["original_picture_packets_preserved"], 1140)
        self.assertEqual(proof["original_decoded_frames_exact"], 1140)
        self.assertEqual((proof["closing_shift_frames"], proof["closing_shift_pcm_sample_pairs"]), (51, 81600))
        self.assertEqual(proof["caption_lines_retained"], 18)
        self.assertIs(proof["pcm_before_and_after_insertion_exact"], True)
        self.assertIs(proof["caption_text_and_cue_shift_verified"], True)
        self.assertIs(proof["preview_aac_reencoded"], True)
        self.assertIs(proof["human_accepted"], False)
        self.assertIs(proof["production_release"], False)
        for label, name, stop in (("base", "without", 1007), ("new", "with", 1058)):
            with self.subTest(variant=name):
                movie = PACKAGE / f"ending-{name}-handoff.mp4"
                self.assertEqual(proof[f"excerpt_{label}_span"], [868, stop])
                self.assertEqual(proof[f"excerpt_{label}_sha256"], digest(movie))
                v, a = payoff.cut.media._probe(movie, "ffprobe")["streams"]
                self.assertEqual((v["codec_type"], a["codec_type"]), ("video", "audio"))
                self.assertEqual((v["width"], v["height"], int(v["nb_read_frames"])), (1280, 720, stop-868))
                self.assertEqual(Fraction(v["avg_frame_rate"]), Fraction(30))
                self.assertEqual((a["sample_rate"], a["channels"]), ("48000", 2))
                for stream in (v, a):
                    self.assertAlmostEqual(float(stream["duration"]), (stop-868) / 30, places=3)


if __name__ == "__main__":
    unittest.main()
