"""Verify two staged visitor prop returns without rendering the full film."""

from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from pipeline import cartoon_visitor_return as story
from pipeline import cartoon_visitor_return_review as integrated


PACKAGE = story.ROOT / "collab/june_visitor_return_v1"
PROOF = Path(os.environ.get("JUNE_VISITOR_RETURN_PROOF", PACKAGE / "visitor-return-proof.json"))
if PROOF.is_dir():
    PROOF /= "visitor-return-proof.json"


class VisitorReturnTests(unittest.TestCase):
    def test_shot_clock_and_separate_contact_beats(self):
        self.assertEqual((story.SPAN, story.N, story.W, story.H), ((225, 396), 171, 1672, 940))
        cues = [story.cues(i) for i in range(story.N)]
        for channel in ("mug_progress", "right_release", "pie_progress", "left_release", "glance"):
            curve = [getattr(cue, channel) for cue in cues]
            with self.subTest(channel=channel):
                self.assertEqual((curve[0], curve[-1]), (0., 1.))
                self.assertTrue(all(a <= b for a, b in zip(curve, curve[1:])))
        self.assertLess(cues[65].mug_progress, 1.)
        self.assertEqual((cues[66].mug_progress, cues[66].right_release), (1., 0.))
        self.assertGreater(cues[67].right_release, 0.)
        self.assertEqual((cues[84].right_release, cues[88].pie_progress), (1., 0.))
        self.assertGreater(cues[89].pie_progress, 0.)
        self.assertLess(cues[118].pie_progress, 1.)
        self.assertEqual(cues[119].pie_progress, 1.)
        self.assertLess(cues[119].left_release, 1.)
        self.assertEqual(cues[135].left_release, 1.)
        self.assertEqual(cues[134].glance, 0.)
        self.assertEqual(cues[155].glance, 1.)
        for i in (-1, story.N, 66.0, True):
            with self.subTest(frame=i), self.assertRaisesRegex(ValueError, "visitor shot clock"):
                story.cues(i)

    def test_rigid_prop_cores_settle_separately_on_a_fixed_set(self):
        prep = story.prepare()
        self.assertFalse(np.shares_memory(prep.mug, prep.right))
        self.assertFalse(np.shares_memory(prep.pie, prep.left))
        for name, prop in (("mug", prep.mug), ("pie", prep.pie)):
            with self.subTest(prop=name):
                alpha = prop[..., 3]
                self.assertEqual(cv2.connectedComponents((alpha > .5).astype(np.uint8))[0], 2)
                self.assertEqual((float(alpha.min()), float(alpha.max())), (0., 1.))
        immutable = (prep.still, prep.table, prep.mug, prep.pie, prep.right, prep.left)
        before = [sha256(art.tobytes()).hexdigest() for art in immutable]
        start, cup_down, pie_down, end = [story.paint(prep, i) for i in (0, 66, 119, 170)]
        for image in (start, cup_down, pie_down, end):
            self.assertEqual((image.shape, image.dtype), ((940, 1672, 3), np.uint8))
            for region in (np.s_[:140, 400:800], np.s_[906:, :]):
                np.testing.assert_array_equal(image[region], prep.table[region])
        m = story.MUG_DROP
        np.testing.assert_array_equal(start[715-m:745-m, 650:700], cup_down[715:745, 650:700])
        np.testing.assert_array_equal(cup_down[715:745, 650:700], end[715:745, 650:700])
        dx, dy = story.PIE_TRAVEL_X, story.PIE_DROP
        np.testing.assert_array_equal(start[750-dy:790-dy, 972+dx:982+dx], pie_down[750:790, 972:982])
        np.testing.assert_array_equal(pie_down[750:790, 972:982], end[750:790, 972:982])
        self.assertFalse(np.array_equal(start, end))
        np.testing.assert_array_equal(story.paint(prep, 66), cup_down)
        self.assertEqual([sha256(art.tobytes()).hexdigest() for art in immutable], before)

    def test_existing_output_is_refused_before_preparing_or_encoding(self):
        with patch.object(story, "prepare", side_effect=AssertionError("existing destination reached rendering")):
            with self.assertRaises(FileExistsError):
                story.build(story.ROOT)

    def test_replacement_clock_rejects_frames_crossing_either_cut(self):
        packets = [{"pts": i*1000, "flags": "K" if i in (0, 3, 6) else "_"}
                   for i in range(9)]
        packets[1], packets[2] = packets[2], packets[1]
        integrated.validate_gops(packets, (0, 3, 6, 9))
        packets[5]["pts"], packets[7]["pts"] = packets[7]["pts"], packets[5]["pts"]
        with self.assertRaisesRegex(ValueError, "3:6"):
            integrated.validate_gops(packets, (0, 3, 6, 9))

    @unittest.skipUnless((PACKAGE / "visitor-return-integration.json").is_file(),
                         "published integration receipt unavailable")
    def test_review_packet_has_pinned_evidence_without_claiming_acceptance(self):
        receipt = json.loads((PACKAGE / "visitor-return-integration.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["base_sha256"], integrated.BASE_SHA)
        self.assertEqual(receipt["builder_sha256"], integrated.digest(Path(integrated.__file__)))
        self.assertEqual(receipt["shot_receipt_sha256"], integrated.digest(PACKAGE / "visitor-return-proof.json"))
        self.assertEqual(receipt["before_after_sha256"], integrated.digest(PACKAGE / "visitor-return-review.mp4"))
        self.assertEqual(receipt["pictures_unchanged"], 1020)
        self.assertEqual(receipt["pictures_replaced"], 171)
        self.assertEqual(receipt["audio_stereo_pairs_identical"], 1905600)
        self.assertEqual(receipt["zero_aac_padding_pairs"], 64)
        self.assertIs(receipt["captions_packets_identical"], True)
        self.assertIs(receipt["human_accepted"], False)
        self.assertIs(receipt["production_release"], False)

    @unittest.skipUnless(PROOF.is_file() and shutil.which("ffprobe"), "published visitor return or ffprobe unavailable")
    def test_isolated_study_receipt_and_silent_playback(self):
        receipt = json.loads(PROOF.read_text(encoding="utf-8"))
        film = PROOF.with_name("visitor-return.mp4")
        digest = story.reg.cut.beat.digest
        self.assertEqual(receipt["clock"], [1920, 1080, 30, 171])
        self.assertEqual(receipt["source_span"], [225, 396])
        self.assertEqual(receipt["source_art"], {key: list(asset) for key, asset in story.ART.items()})
        for image, expected in story.ART.values():
            self.assertEqual(digest(story.ROOT / "concept/style_frames" / image), expected)
        self.assertEqual(receipt["source_builder_sha256"], digest(Path(story.__file__)))
        self.assertEqual(receipt["movie_sha256"], digest(film))
        self.assertEqual(set(receipt["native_rgb24_sha256"]), {str(i) for i in range(171)})
        self.assertEqual(receipt["global_event_frames"], {
            "mug_settles": 291, "mug_release_done": 309, "pie_settles": 344,
            "left_release_done": 360, "looks_to_june": 380,
        })
        self.assertIs(receipt["no_audio_in_study"], True)
        for gate in ("integrated", "human_accepted", "production_release"):
            self.assertIs(receipt[gate], False)
        video, = story.media._probe(film, "ffprobe")["streams"]
        self.assertEqual((video["codec_type"], video["width"], video["height"]), ("video", 1920, 1080))
        self.assertEqual(int(video["nb_read_frames"]), 171)
        self.assertEqual(Fraction(video["avg_frame_rate"]), Fraction(30))
        self.assertEqual(int(video["duration_ts"]) * Fraction(video["time_base"]), Fraction(171, 30))


if __name__ == "__main__":
    unittest.main()
