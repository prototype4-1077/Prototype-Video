"""Check grounded source motion for the 129-frame opening porch shot."""

from fractions import Fraction
import json
from pathlib import Path
import shutil
import unittest

import numpy as np

from pipeline import cartoon_porch_life as porch


PACKAGE = porch.LAB.ROOT / "collab/june_porch_life_v1"
PROOF = PACKAGE / "porch-life-proof.json"


class PorchLifeTests(unittest.TestCase):
    def test_motion_is_bounded_on_original_shot_clock(self):
        self.assertEqual(porch.N, 129)
        self.assertEqual(porch.WINDOW, (1,172))
        self.assertEqual(porch.WINDOW[1]-porch.WINDOW[0], 171)
        self.assertEqual(porch.cues(0), porch.Beat(0.,0.,0.))
        all_cues = [porch.cues(i) for i in range(129)]
        self.assertEqual(max(abs(q.chest_y) for q in all_cues), 1.9)
        self.assertEqual(max(q.nod_deg for q in all_cues), 2.15)
        self.assertEqual(max(abs(q.tag_deg) for q in all_cues), 5.6)
        self.assertEqual(porch.cues(38).tag_deg, -5.6)
        self.assertEqual(porch.cues(63).tag_deg, 5.1)
        self.assertEqual(porch.cues(128).tag_deg, 0.)
        self.assertAlmostEqual(porch.cues(128).chest_y, 0.)
        self.assertAlmostEqual(porch.cues(128).nod_deg, 1.77)
        for i in (-1,129,2.0,True):
            with self.subTest(frame=i), self.assertRaisesRegex(ValueError,"outside the 129-frame porch clock"):
                porch.cues(i)

    def test_pose_and_breeze_leave_all_contact_pixels_and_tag_hook_exact(self):
        prepared = porch.prepare()
        original = prepared.plate.copy()
        self.assertEqual((original.shape,original.dtype),((941,1672,3),np.uint8))
        segment = prepared.segment
        self.assertEqual((segment["start_frame"],segment["end_frame"],segment["plate_id"]),(1,129,porch.PLATE))
        self.assertEqual((segment["camera"]["start_zoom"],segment["camera"]["end_zoom"]),(1.,1.03))
        fixed = np.ones(original.shape[:2],dtype=bool)
        fixed[porch.window(porch.ACTOR)] = False
        fixed[porch.window(porch.TAG)] = False
        expected_fixed = original[fixed]
        left, top, right, _ = porch.TAG
        pin = np.s_[top:top+8,left:right]
        fixed_contacts = (
            np.s_[361:464,647:765],  # mug and the same left gripping hand
            np.s_[456:535,412:532],  # right resting hand and chair arm
            np.s_[793:840,416:505],  # runner and floor contact
            np.s_[765:872,585:798],  # boots and nearby floor shadows
            pin,
        )
        for i in range(porch.N):
            frame = porch.frame(prepared,i)
            self.assertTrue(np.array_equal(frame[fixed],expected_fixed),f"changed pixels outside motion support at F{i}")
            for region in fixed_contacts:
                np.testing.assert_array_equal(frame[region],original[region])
        np.testing.assert_array_equal(porch.frame(prepared,0),original)
        self.assertFalse(np.array_equal(porch.frame(prepared,98)[104:156,525:606],original[104:156,525:606]))
        chime = porch.window(porch.TAG)
        self.assertFalse(np.array_equal(porch.frame(prepared,38)[chime],original[chime]))
        np.testing.assert_array_equal(porch.frame(prepared,128)[chime],original[chime])
        np.testing.assert_array_equal(prepared.plate,original)

    @unittest.skipUnless(PROOF.is_file() and shutil.which("ffprobe"),"published porch study or ffprobe unavailable")
    def test_published_comparison_receipt_and_exact_clock(self):
        record = json.loads(PROOF.read_text(encoding="utf-8"))
        comparison = PACKAGE / "porch-life-review.mp4"
        self.assertEqual(record["baseline_sha256"],porch.reviewed.BASE_SHA)
        self.assertEqual(record["source_plate_sha256"],porch.PLATE_SHA)
        self.assertEqual(record["builder_sha256"],porch.digest(Path(porch.__file__)))
        self.assertEqual(record["review_sha256"],porch.digest(comparison))
        self.assertEqual(record["source_span"],[0,129])
        self.assertEqual(record["review_span"],[1,172])
        self.assertEqual(len(record["native_rgb_sha256"]),129)
        self.assertGreater(len(set(record["native_rgb_sha256"])),10)
        for key,value in (("actor_box",porch.ACTOR),("tag_box",porch.TAG),("tag_pivot",porch.PIVOT)):
            self.assertEqual(record[key],list(value))
        for gate in ("no_new_audio","comparison_only"):
            self.assertIs(record[gate],True)
        for gate in ("human_accepted","production_release"):
            self.assertIs(record[gate],False)
        video,audio = porch.cut.media._probe(comparison,"ffprobe")["streams"]
        self.assertEqual((video["codec_type"],audio["codec_type"]),("video","audio"))
        self.assertEqual((video["width"],video["height"],int(video["nb_read_frames"])),(1536,432,171))
        self.assertEqual(Fraction(video["avg_frame_rate"]),Fraction(30))
        self.assertEqual((audio["sample_rate"],audio["channels"]),("48000",2))
        for stream in (video,audio):
            self.assertAlmostEqual(float(stream["duration"]),5.7,places=3)


if __name__=="__main__":
    unittest.main()
