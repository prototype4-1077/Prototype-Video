"""Validate the layered GS060 pot exercise, not a human acting judgment."""
import json
from pathlib import Path
import unittest

import cv2
import numpy as np

from pipeline import cartoon_grounded_coffee as study


PACK=study.register.sources.ROOT/"collab/june_grounded_coffee_v1"


class GroundedCoffeeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=study.prepare()

    def test_grip_registered_to_handle_on_rise_and_return(self):
        names=("thumb","upper_loop","base","spout_tip","wrist_top")
        pts=np.asarray([study.ART_POINTS[n] for n in names],np.float32)-study.ROI[:2]
        for t in (.12,.25,.5,.75,.88):
            key=(1-t)*pts[:,0]+t*pts[:,1]
            x,y=(v.reshape(1,-1).astype(np.float32) for v in key.T)
            for index,(mx,my) in enumerate(self.p.area.maps(t)):
                warped=np.column_stack([cv2.remap(p,x,y,cv2.INTER_LINEAR).ravel() for p in (mx,my)])
                self.assertLess(np.linalg.norm(warped-pts[:,index],axis=1).max(),2.3)

    def test_contact_starts_and_ends_grounded_braced_mug_stays_exact(self):
        for n in range(8,34):
            self.assertLess(study.rise(n),study.rise(n+1))
        for n in range(49,77):
            self.assertGreater(study.rise(n),study.rise(n+1))
        for i in (0,8,77,89):
            self.assertEqual(study.rise(i),0)
        for i in (34,43,49):
            self.assertEqual(study.rise(i),1)
        for bad in (-1,90,True):
            with self.assertRaises(ValueError):
                study.rise(bad)
        x,y,r,b=study.ROI
        reference=self.p.lifted
        for t in (0,.18,.5,.82,.99,1):
            frame=study.frame(self.p,t)
            for zone in (np.s_[:y], np.s_[:,r:], np.s_[:,:x], np.s_[b:],
                         np.s_[712:880,934:1129], np.s_[823:910,380:530]):
                np.testing.assert_array_equal(frame[zone],reference[zone])
        np.testing.assert_array_equal(study.frame(self.p,1),reference)

    def test_render_is_deterministic_and_actual_published_proof_is_silent(self):
        np.testing.assert_array_equal(study.frame(self.p,.5),study.frame(self.p,.5))
        proof=json.loads((PACK/"lift-study-proof.json").read_text(encoding="utf-8"))
        preview=PACK/"grounded-lift-study.mp4"
        digest=study.register.cut.beat.digest
        self.assertEqual(proof["builder_sha256"],digest(Path(study.__file__)))
        self.assertEqual(proof["video_sha256"],digest(preview))
        self.assertEqual(proof["source_sha256"],study.HASHES)
        self.assertEqual(proof["clock"],[1920,1080,30,90])
        self.assertEqual(len(proof["native_rgb24_sha256"]),90)
        for optional_gate in ("human_accepted","production_release","full_film_integrated"):
            self.assertFalse(proof[optional_gate])
        video,=study.media._probe(preview,"ffprobe")["streams"]
        self.assertEqual((video["width"],video["height"],int(video["nb_read_frames"])),(1920,1080,90))
        self.assertEqual(video["duration"],"3.000000")


if __name__=="__main__":
    unittest.main()
