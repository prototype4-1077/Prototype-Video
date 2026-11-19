"""Check the authored eyes-first beat and its published evidence."""
from pathlib import Path
import json
import unittest

import cv2
import numpy as np

from pipeline import cartoon_compassion_acting as acting
from pipeline import cartoon_compassion_review as review


PACKAGE=acting.sources.ROOT/"collab/june_compassion_reaction_v1"


class CompassionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=acting.prepare()

    def test_notice_then_yield_with_exact_earlier_hand_and_stable_final_face(self):
        start,noticed,settled=(acting.plate(self.source,i) for i in (0,54,82))
        face,hand=acting.window(acting.HEAD_ROI),acting.window(acting.HAND_ROI)
        np.testing.assert_array_equal(start[hand],noticed[hand])
        np.testing.assert_array_equal(noticed[face],settled[face])
        self.assertGreater(np.abs(start[face].astype(float)-noticed[face]).mean(),9)
        self.assertGreater(np.abs(start[hand].astype(float)-settled[hand]).mean(),6)
        self.assertEqual(acting.cues(57),(1,0))
        self.assertEqual(acting.cues(82),(1,1))

    def test_prop_and_porch_protected_through_intermediate_poses(self):
        for frame in (37,43,49,63,68,73,78,113):
            result=acting.plate(self.source,frame)
            np.testing.assert_array_equal(result[:,943:],self.source.start[:,943:])
            np.testing.assert_array_equal(result[560:710],self.source.start[560:710])
        for i in (-1,114,True):
            with self.assertRaises(ValueError):
                acting.cues(i)

    def test_single_moving_pencil_has_constant_artwork_length(self):
        measured=[]
        for fraction in (.35,.5,.65,.82,.97):
            alpha=acting.pencil(self.source,fraction)[...,3]
            points=np.column_stack(np.where(alpha>.75))[...,::-1].astype(np.float32)
            measured.append(max(cv2.minAreaRect(points)[1]))
        self.assertLess(max(measured)-min(measured),1)
        self.assertGreater(min(measured),205)

    def test_manifest_binds_to_video_source_geometry_and_verdict(self):
        receipt=json.loads((PACKAGE/"reaction-proof.json").read_text(encoding="utf-8"))
        inv=json.loads((PACKAGE/"gs050-native-frames.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["acting_source_sha256"],review.cut.beat.digest(Path(acting.__file__)))
        self.assertEqual(receipt["wrapper_source_sha256"],review.cut.beat.digest(Path(review.__file__)))
        self.assertEqual(receipt["strictly_copied_video_packets"],1026)
        self.assertEqual(receipt["audit"]["decoded_repaired_frames_exact"],303)
        self.assertIs(receipt["human_accepted"],False)
        self.assertEqual((inv["start_frame_zero_based"],len(inv["rgb24_sha256"])),(564,114))
        self.assertEqual(len(set(inv["rgb24_sha256"])),receipt["motion"]["native_frames_changed"])
        self.assertEqual(len(review.locked_base()),1140)

    def test_side_by_side_is_full_length_with_shared_sound(self):
        probe=review.cut.media._probe(PACKAGE/"reaction-side-by-side.mp4","ffprobe")
        video,audio=probe["streams"]
        self.assertEqual(int(video["nb_read_frames"]),114)
        self.assertEqual((video["width"],video["height"]),(1536,432))
        self.assertEqual((video["duration"],audio["duration"]),("3.800000","3.800000"))


if __name__=="__main__":
    unittest.main()
