"""Check the visitor reaction and untouched ending without encoding media."""

from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import shutil
import unittest

import numpy as np

from pipeline import cartoon_coffee_reaction as reaction


PACKAGE = reaction.art.ROOT / "collab/june_coffee_reaction_v1"
PROOF = PACKAGE / "coffee-reaction-proof.json"


class CoffeeReactionTests(unittest.TestCase):
    def test_one_second_eye_lift_uses_a_prop_free_aperture(self):
        self.assertEqual((reaction.JOIN, reaction.N, reaction.BASE_TOTAL, reaction.TOTAL), (963, 30, 1191, 1221))
        self.assertEqual(reaction.REVIEW, (868, 1131))
        self.assertEqual(reaction.CROP, (416, 0, 1376, 540))
        x, y, r, b = reaction.CROP
        self.assertEqual(Fraction(r-x, b-y), Fraction(16, 9))
        # Both prop envelopes begin below the bottom of this crop even
        # at their highest carry position in the original GS030 scene.
        self.assertLess(b, reaction.art.MUG[1]-reaction.art.MUG_DROP)
        self.assertLess(b, reaction.art.PIE[1]-reaction.art.PIE_DROP)
        curve = [reaction.expression(i) for i in range(reaction.N)]
        self.assertEqual(curve[:7], [0.] * 7)
        self.assertTrue(all(a < b for a, b in zip(curve[6:19], curve[7:20])))
        self.assertEqual(curve[19:], [.87] * 11)
        for i in (-1, 30, 7.0, True):
            with self.subTest(frame=i), self.assertRaisesRegex(ValueError, "visitor reaction clock"):
                reaction.expression(i)

        plate, eye = reaction.scene()
        before = sha256(plate.tobytes()).hexdigest()
        reference = plate[y:b, x:r]
        framed = [reaction.frame(plate, eye, i) for i in (0, 12, 19, 29)]
        np.testing.assert_array_equal(framed[0], reference)
        np.testing.assert_array_equal(framed[-2], framed[-1])
        self.assertFalse(np.array_equal(framed[1], framed[-1]))
        ex, ey, er, eb = reaction.art.E
        for take in framed:
            self.assertEqual((take.shape, take.dtype), ((540, 960, 3), np.uint8))
            for outside in (np.s_[:ey-y], np.s_[eb-y:], np.s_[ey-y:eb-y, :ex-x], np.s_[ey-y:eb-y, er-x:]):
                np.testing.assert_array_equal(take[outside], reference[outside])
        self.assertEqual(sha256(plate.tobytes()).hexdigest(), before)

    def test_only_new_pcm_pairs_are_zero_and_a_noisy_boundary_is_refused(self):
        recipe, paths, contract = reaction.cut.load_plan()
        mix, _ = reaction.cut.full_mix(recipe, paths, contract)
        original = reaction.payoff.extend_sound(mix)
        original.setflags(write=False)
        shifted = reaction.pad_silence(original)
        split, added = 963*1600, 30*1600
        self.assertEqual((shifted.shape, shifted.dtype), ((1221*1600, 2), original.dtype))
        self.assertFalse(np.shares_memory(shifted, original))
        np.testing.assert_array_equal(shifted[:split], original[:split])
        self.assertFalse(np.any(shifted[split:split+added]))
        np.testing.assert_array_equal(shifted[split+added:], original[split:])
        invalid = original.copy()
        for sample in (split-1440, split+1439):
            with self.subTest(sample=sample):
                self.assertEqual(int(invalid[sample, 1]), 0)
                invalid[sample, 1] = -1
                with self.assertRaisesRegex(ValueError, "overlaps non-silent sound"):
                    reaction.pad_silence(invalid)
                invalid[sample, 1] = 0
        with self.assertRaisesRegex(ValueError, "unexpected source soundtrack clock"):
            reaction.pad_silence(original[:-1])

    def test_caption_shift_changes_only_four_timestamps_not_words(self):
        _, _, original = reaction.cut.load_plan()
        timing = reaction.payoff.extend_captions(original)
        snapshot = deepcopy(timing)
        revised = reaction.shift_captions(timing)
        self.assertEqual(timing, snapshot)
        source, output = timing["dialogue_cues"], revised["dialogue_cues"]
        self.assertEqual((len(source), len(output)), (18, 18))
        self.assertEqual(source[:14], output[:14])
        for old, shifted in zip(source[14:], output[14:]):
            with self.subTest(cue=old["id"]):
                self.assertEqual(shifted, {**old, "start_frame": old["start_frame"]+30,
                                          "end_frame": old["end_frame"]+30})
        self.assertEqual((source[14]["start_frame"], output[14]["start_frame"]), (988, 1018))
        crossing = deepcopy(timing)
        crossing["dialogue_cues"][13].update(start_frame=962, end_frame=964)
        with self.assertRaisesRegex(ValueError, "would interrupt a caption mid-line"):
            reaction.shift_captions(crossing)

    @unittest.skipUnless(PROOF.is_file() and shutil.which("ffprobe"), "published coffee reaction or ffprobe unavailable")
    def test_published_receipt_and_separate_review_media(self):
        proof = json.loads(PROOF.read_text(encoding="utf-8"))
        self.assertEqual(proof["builder_sha256"], reaction.digest(Path(reaction.__file__)))
        self.assertEqual(proof["base_sha256"], reaction.BASE_SHA)
        self.assertEqual(proof["source_pcm_sha256"], reaction.ledger.SOURCE_PCM_SHA)
        self.assertEqual(proof["source_art"], {key: list(values) for key, values in reaction.art.ART.items()})
        self.assertEqual(proof["crop_xyxy"], [416, 0, 1376, 540])
        self.assertEqual(proof["insert_frames"], [963, 993])
        self.assertEqual(proof["duration_seconds"], 40.7)
        self.assertEqual(proof["original_frames_retained"], 1191)
        self.assertEqual(proof["added_pcm_zero_pairs"], 48_000)
        self.assertIs(proof["original_audio_samples_exact_around_insertion"], True)
        self.assertEqual((proof["caption_lines"], proof["caption_lines_shifted"], proof["closing_time_shift_frames"]), (18, 4, 30))
        self.assertEqual(len(proof["native_picture_sha256"]), 30)
        self.assertGreaterEqual(len(set(proof["native_picture_sha256"])), 12)
        self.assertIs(proof["human_accepted"], False)
        self.assertIs(proof["production_release"], False)
        for i, (clip, stop, key) in enumerate((
            ("ending-handoff-only.mp4", 1131, "old_excerpt_frames"),
            ("ending-with-visitor-reaction.mp4", 1161, "new_excerpt_frames"),
        )):
            with self.subTest(clip=clip):
                movie = PACKAGE / clip
                self.assertEqual(proof[key], [868, stop])
                self.assertEqual(proof["excerpt_sha256"][i], reaction.digest(movie))
                v, a = reaction.cut.media._probe(movie, "ffprobe")["streams"]
                self.assertEqual((v["codec_type"], a["codec_type"]), ("video", "audio"))
                self.assertEqual((v["width"], v["height"], int(v["nb_read_frames"])), (1280, 720, stop-868))
                self.assertEqual(Fraction(v["avg_frame_rate"]), Fraction(30))
                self.assertEqual((a["sample_rate"], a["channels"]), ("48000", 2))
                for stream in (v, a):
                    self.assertAlmostEqual(float(stream["duration"]), (stop-868)/30, places=3)


if __name__ == "__main__":
    unittest.main()
