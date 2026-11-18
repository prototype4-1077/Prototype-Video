"""Real-pixel checks, independent of the compositor's planned displacement."""
import json
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from pipeline import cartoon_mug_action as action


def locate(image, template, origin):
    x, y = origin
    h, w = template.shape[:2]
    left, top = x-5, y-83
    window = np.ascontiguousarray(image[top:y+h+6, left:x+w+6])
    scores = cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, (px,py) = cv2.minMaxLoc(scores)
    return (left+px-x,top+py-y),confidence


def grip_track(frames, shape):
    """Follow a chip on the cup, the thumbnail and the bottom finger, not the rig."""
    height,width,channels = shape
    origins = [(259, 184), (405, 139), (439, 300)]  # grounded insert coordinates
    templates = None
    positions, min_confidence, worst_slip = [], 1., 0
    for image in frames:
        if image.shape != (height,width,channels):
            raise ValueError("bad decoded frame")
        if templates is None:
            templates = [np.ascontiguousarray(image[y:y+27,x:x+33]) for x,y in origins]
            if min(float(t.std()) for t in templates) < 9:
                raise ValueError("flat landmark is not trackable")
        matches = [locate(image, tpl, pt) for tpl,pt in zip(templates,origins)]
        offsets = np.array([m[0] for m in matches])
        min_confidence = min(min_confidence, *(m[1] for m in matches))
        worst_slip = max(worst_slip, int(np.abs(offsets-offsets[0]).max()))
        positions.append(offsets[0].tolist())
    return positions, min_confidence, worst_slip


class MugActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layers = action.prepare_action()

    def test_no_ambiguous_frames_or_implicit_retiming(self):
        fractions = [action.elevation(i) for i in range(action.COUNT)]
        self.assertEqual(fractions[:11], [0.]*11)
        self.assertEqual(fractions[34:44], [1.]*10)
        self.assertEqual(fractions[67:], [0.]*17)
        self.assertTrue(np.all(np.diff(fractions[10:35]) > 0))
        self.assertTrue(np.all(np.diff(fractions[43:68]) < 0))
        for i in (-1, 84, 2.5, True):
            with self.assertRaises(ValueError):
                action.elevation(i)

    def test_set_is_still_and_table_is_revealed(self):
        low, high = (action.render_frame(self.layers, i) for i in (0,36))
        np.testing.assert_array_equal(low, action.render_frame(self.layers,83))
        np.testing.assert_array_equal(low[:300,610:], high[:300,610:])
        # Low: enamel at old cup-base location. High: textured wood, not a hole.
        wood, enamel = high[347:375,208:326], low[347:375,208:326]
        self.assertGreater(float(enamel[...,0].mean()-wood[...,0].mean()), 65)
        self.assertGreater(float(wood[...,0].std()), 5)

    def test_accent_is_actual_painted_motion(self):
        frames = [action.render_frame(self.layers, i) for i in (0,23,35,54,83)]
        track, confidence, slip = grip_track(frames,frames[0].shape)
        self.assertGreater(confidence, .96)
        self.assertLessEqual(slip, 1)
        self.assertEqual(track[0],track[-1])
        self.assertEqual(track[2],[0,-78])

    def test_refuse_overwriting_an_existing_proof(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(FileExistsError):
            action.build(Path(d))


class PublishedMugTests(unittest.TestCase):
    def test_every_encoded_frame_holds_grip_without_drift(self):
        package = action.ROOT/"collab/june_left_handle_v2"
        movie = package/"june-left-handle-v2.mp4"
        verification = json.loads((package/"verification.json").read_text())
        self.assertEqual(hashlib.sha256(movie.read_bytes()).hexdigest(),verification["picture_sha256"])
        self.assertIs(verification["human_accepted"],False)
        shape = (450,800,3)
        with subprocess.Popen(["ffmpeg","-v","error","-i",str(movie),"-f","rawvideo",
                               "-pix_fmt","rgb24","pipe:1"],stdout=subprocess.PIPE) as proc:
            try:
                def frames():
                    for _ in range(84):
                        raw = proc.stdout.read(int(np.prod(shape)))
                        if len(raw) != int(np.prod(shape)):
                            raise ValueError("early EOF")
                        yield np.frombuffer(raw,np.uint8).reshape(shape)
                track, confidence, slip = grip_track(frames(),shape)
                self.assertEqual(proc.stdout.read(1), b"")
            finally:
                proc.stdout.close()
        self.assertEqual(proc.returncode,0)
        self.assertGreater(confidence,.94)
        self.assertLessEqual(slip,1)
        self.assertEqual(track[35],[0,-78])
        self.assertEqual(track[0],track[-1])


if __name__ == "__main__":
    unittest.main()
