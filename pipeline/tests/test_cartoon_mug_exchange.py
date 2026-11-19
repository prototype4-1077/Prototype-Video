"""Contact gates use independent painted features in the exported movie."""
import json
from hashlib import sha256
from pathlib import Path
import subprocess
import unittest

import numpy as np

from pipeline import cartoon_mug_exchange as scene
from pipeline.tests.test_cartoon_mug_action import grip_track, locate


PACKAGE = scene.lift.ROOT / "collab/june_left_handle_exchange_v3"
GROUND = list(range(42)) + list(range(98,147))


class NativeExchangeTests(unittest.TestCase):
    def test_exchange_preserves_the_entire_existing_lift(self):
        a = json.loads(scene.V2.read_text(encoding="utf-8"))["sha256_rgb24"]
        b = json.loads((PACKAGE/"source-frames.json").read_text(encoding="utf-8"))["sha256_rgb24"]
        self.assertEqual(len(b),147)
        self.assertEqual(a[4:71],b[35:102])
        self.assertEqual(b[34],b[35])
        self.assertEqual(b[101],b[102])
        self.assertEqual(b[0],b[-1])

    def test_fingers_wait_for_the_cup_to_touch_down(self):
        self.assertTrue(all(scene.closure(i)==1 for i in range(30,103)))
        self.assertTrue(all(scene.closure(i)==0 for i in list(range(7))+list(range(117,147))))
        self.assertGreater(scene.closure(22),scene.closure(15))
        self.assertLess(scene.closure(113),scene.closure(106))
        for i in (-1,147,True,2.2):
            with self.assertRaises(ValueError):
                scene.closure(i)

    def test_source_paint_and_table_not_morphed_by_fingers(self):
        p = scene.prepare()
        for i in (0,13,17,20,23,29,105,110,113,117,146):
            image = scene.render_frame(p,i)
            np.testing.assert_array_equal(p.ground[184:369,177:395], image[184:369,177:395])
            np.testing.assert_array_equal(p.ground[:,635:], image[:,635:])
        receipt = json.loads((PACKAGE/"verification.json").read_text(encoding="utf-8"))
        self.assertEqual(sha256(Path(scene.__file__).read_bytes()).hexdigest(),receipt["source_sha256"])


class DecodedExchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        movie = PACKAGE/"june-left-handle-exchange-v3.mp4"
        receipt = json.loads((PACKAGE/"verification.json").read_text(encoding="utf-8"))
        assert sha256(movie.read_bytes()).hexdigest() == receipt["movie_sha256"]
        assert receipt["human_accepted"] is False
        raw = subprocess.check_output(["ffmpeg","-v","error","-i",str(movie),"-f","rawvideo","-pix_fmt","rgb24","pipe:1"])
        cls.frames = np.frombuffer(raw,np.uint8).reshape(147,450,800,3)

    def test_chip_stays_put_until_gripped_and_after_setdown(self):
        frames=self.frames
        patch=frames[0,184:211,259:292].copy()
        track=[locate(f,patch,(259,184)) for f in frames]
        self.assertGreater(min(c for _,c in track),.94)
        self.assertTrue(all(track[i][0]==(0,0) for i in GROUND))
        self.assertEqual(min(p[1] for p,_ in track),-78)
        _,confidence,slip=grip_track(frames[35:102],(450,800,3))
        self.assertGreater(confidence,.94)
        self.assertLessEqual(slip,1)

    def test_handle_hole_is_occluded_and_reopens(self):
        frames=self.frames
        # As knuckles pass through the hole, skin replaces blurred green foliage.
        hole = frames[:,215:275,416:448,:2].astype(np.int16)
        occupancy_color = (hole[...,0] - hole[...,1]).mean(axis=(1,2))
        self.assertLess(float(occupancy_color[0]),30)
        self.assertGreater(float(occupancy_color[30]),40)
        self.assertGreater(float(occupancy_color[102]),40)
        self.assertLess(float(occupancy_color[117]),30)
        self.assertLess(abs(float(occupancy_color[0]-occupancy_color[-1])),1)

    def test_no_cut_at_attachment_or_release_seams(self):
        f = self.frames[:,100:330,393:565].astype(np.int16)
        for before,after in [(34,35),(101,102)]:
            self.assertLess(float(np.abs(f[before]-f[after]).mean()),.8)
        self.assertGreater(float(np.abs(f[0]-f[34]).mean()),18)


if __name__ == "__main__":
    unittest.main()
