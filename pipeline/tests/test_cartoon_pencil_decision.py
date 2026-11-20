"""Verify that the pencil settles before June finishes letting go."""

from fractions import Fraction
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch, sentinel

import numpy as np

from pipeline import cartoon_pencil_decision as decision


PACKAGE = decision.story.root / "collab/june_pencil_decision_v1"
PROOF = PACKAGE / "pencil-decision-proof.json"


class PencilDecisionTests(unittest.TestCase):
    def test_shaft_and_hand_have_separate_monotonic_timings(self):
        self.assertEqual((decision.START, decision.STOP, decision.ledger.TOTAL), (678, 789, 1191))
        self.assertEqual(decision.REVIEW, (670, 868))
        original = [decision.timing(i) for i in range(678, 745)]
        self.assertTrue(all(cue.stage == "pencil" for cue in original))
        for field in ("hand", "pencil"):
            curve = [getattr(cue, field) for cue in original]
            self.assertEqual((curve[0], curve[-1]), (0., 1.))
            self.assertTrue(all(a <= b for a, b in zip(curve, curve[1:])))
        self.assertGreater(decision.timing(716).hand, 0.)
        self.assertEqual(decision.timing(716).pencil, 0.)
        self.assertLess(decision.timing(734).pencil, 1.)
        self.assertEqual(decision.timing(735).pencil, 1.)
        self.assertLess(decision.timing(740).hand, 1.)
        self.assertEqual(decision.timing(741).hand, 1.)
        self.assertEqual(decision.timing(745), decision.Cue("reach", 0., 1.))
        self.assertGreater(decision.timing(746).hand, 0.)
        self.assertEqual(decision.timing(781), decision.Cue("lift", 1., 1.))
        self.assertTrue(all(decision.timing(i)==decision.Cue("original", 1., 1.) for i in range(782,789)))
        for i in (677, 789, True, 678.0):
            with self.subTest(frame=i), self.assertRaisesRegex(ValueError, "confined to the pre-pour shot"):
                decision.timing(i)

    def test_stationary_pencil_core_and_untouched_art_outside_moving_roi(self):
        setup = decision.acting.prepare()
        x, y, r, b = decision.acting.PEN_ROI
        parked = setup.park.copy()
        images = {}
        for i in (725, 735, 738, 741):
            cue = decision.timing(i)
            image = decision.independent_pencil(setup, cue.hand, cue.pencil)
            images[i] = image
            with self.subTest(frame=i):
                self.assertEqual((image.shape, image.dtype), ((941,1672,3), np.uint8))
                for area in (np.s_[:y], np.s_[b:], np.s_[y:b, :x], np.s_[y:b, r:]):
                    np.testing.assert_array_equal(image[area], parked[area])
        # Unoccluded painted eraser stays fixed while fingers ease open.
        core = np.s_[833:841, 425:446]
        self.assertFalse(np.array_equal(images[725][core], parked[core]))
        for i in (735, 738, 741):
            np.testing.assert_array_equal(images[i][core], parked[core])
        self.assertFalse(np.array_equal(images[735], images[738]))
        np.testing.assert_array_equal(images[741], parked)
        np.testing.assert_array_equal(setup.park, parked)

    def test_final_original_hold_and_smear_use_their_existing_cels(self):
        contract = decision.story.root / "concept/style_frames/june_golden_scene_gs060_layered_pour_v1.json"
        original = json.loads(contract.read_text(encoding="utf-8"))
        poses = {"POSE_45_POT_LIFT": sentinel.raised}
        smears = {111: sentinel.smear}
        for frame, layer in ((781, sentinel.raised), (782, sentinel.raised), (788, sentinel.smear)):
            with self.subTest(frame=frame), patch.object(decision.pour, "compose_pour_frame", return_value=sentinel.rgb) as render:
                self.assertIs(decision.picture(None,frame,original,sentinel.bg,poses,smears,None,None),sentinel.rgb)
                render.assert_called_once_with(sentinel.bg,layer,original,frame-677)

    @unittest.skipUnless(PROOF.is_file() and shutil.which("ffprobe"), "published pencil decision or ffprobe unavailable")
    def test_published_review_and_native_locked_lead_in(self):
        proof = json.loads(PROOF.read_text(encoding="utf-8"))
        movie = PACKAGE / "pencil-decision-review.mp4"
        self.assertEqual(proof["base_sha256"], decision.BASE_SHA)
        self.assertEqual(proof["builder_sha256"], decision.digest(Path(decision.__file__)))
        self.assertEqual(proof["review_sha256"], decision.digest(movie))
        self.assertEqual(proof["source_span"], [678,789])
        self.assertEqual(proof["review_span"], [670,868])
        self.assertEqual(proof["cue_frames"], {"pencil_fully_flat":735, "fingers_released":741,
                                              "reach_start":746, "pot_raised":781, "original_pour_leadin_start":782})
        self.assertEqual(proof["outside_picture_frames_exact"],1080)
        original = decision.story.previous.native_inventories("visitor")[1]
        self.assertEqual(set(proof["native_rgb_sha256"]), {str(i) for i in range(678,789)})
        for i in range(782,789):
            self.assertEqual(proof["native_rgb_sha256"][str(i)], original[i])
        self.assertIs(proof["approved_pour_clock_preserved"], True)
        self.assertIs(proof["audio_and_captions_unchanged"], True)
        self.assertIs(proof["human_accepted"],False)
        self.assertIs(proof["production_release"],False)
        video,audio = decision.cut.media._probe(movie,"ffprobe")["streams"]
        self.assertEqual((video["codec_type"],audio["codec_type"]),("video","audio"))
        self.assertEqual((video["width"],video["height"],int(video["nb_read_frames"])),(1536,432,198))
        self.assertEqual(Fraction(video["avg_frame_rate"]), Fraction(30))
        self.assertEqual((audio["sample_rate"],audio["channels"]),("48000",2))
        for stream in (video,audio):
            self.assertAlmostEqual(float(stream["duration"]),6.6,places=3)


if __name__=="__main__":
    unittest.main()
