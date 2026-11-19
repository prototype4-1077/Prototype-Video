"""Pinned story, sample clock and decoded cut regression gates."""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from pipeline import cartoon_story_beat as story


PUBLISHED = story.ROOT/"collab/june_rest_your_hands_story_v1"


def read_frame(path, i):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES,i)
        ok,frame=cap.read()
        if not ok:
            raise ValueError(f"no frame {i}: {path}")
        return frame
    finally:
        cap.release()


class StoryPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan,cls.assets,cls.offsets=story.plan_from(story.RECIPE)

    def test_face_and_voice_resume_on_same_clock(self):
        self.assertEqual(self.offsets,[(0,38),(38,124),(124,223)])
        self.assertEqual(self.plan["shots"][2]["span"],[108,207])
        self.assertEqual(self.plan["voice_pause"]["insert_frames"],16)

    def test_reject_cut_outside_verified_gap(self):
        # Keep the hand-contact frame and durations unchanged, then push the
        # first cut into the spoken onset instead of changing the total clock.
        changed=json.loads(story.RECIPE.read_text(encoding="utf-8"))
        changed["shots"][0]["span"][1]=44
        changed["shots"][1]["span"][0]=41
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"unsafe.json"
            path.write_text(json.dumps(changed),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"too close to speech"):
                story.plan_from(path)

    def test_single_recorded_cue_and_exact_dialogue_contribution(self):
        mixed,fx,spoken,receipt=story.sound(self.plan,self.assets)
        self.assertEqual(mixed.shape,(356800,2))
        np.testing.assert_array_equal(mixed.astype(np.int64)-fx,spoken)
        source,_=story.foley.audio.ledger_pour._read_pcm24_wave(self.assets["voice"])
        source=np.rint(source[:,0].astype(float)*10**(-2/20)).astype(np.int32)
        np.testing.assert_array_equal(spoken[:168000,0],source[:168000])
        np.testing.assert_array_equal(spoken[193600:,0],source[168000:])
        self.assertFalse(spoken[168000:193600].any())
        self.assertEqual(int(np.argmax(abs(fx[:,0]))),101*1600)
        start,stop=receipt["event_sample_span_half_open"]
        self.assertEqual(stop-start,6480)
        self.assertFalse(fx[:start+1].any() or fx[stop-1:].any())


class PublishedStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.voice_plan,cls.assets,_=story.plan_from(story.RECIPE)
        cls.report=json.loads((PUBLISHED/"verification.json").read_text(encoding="utf-8"))

    def test_delivered_movie_bytes_and_approval_boundaries(self):
        for name in ("story.mov","story.mp4"):
            self.assertEqual(sha256((PUBLISHED/name).read_bytes()).hexdigest(),self.report["sha256"][name])
        self.assertEqual(story.digest(story.RECIPE),self.report["recipe_sha256"])
        self.assertEqual(story.digest(Path(story.__file__)),self.report["renderer_sha256"])
        self.assertIs(self.report["human_accepted"],False)
        self.assertIs(self.report["production_release"],False)

    def test_published_streams_have_exact_picture_and_sample_clock(self):
        mp4,mov=PUBLISHED/"story.mp4",PUBLISHED/"story.mov"
        self.assertEqual(story.media._video_hash(mp4,"ffmpeg"),story.media._video_hash(mov,"ffmpeg"))
        expected,_,_,_=story.sound(self.voice_plan,self.assets)
        np.testing.assert_array_equal(story.decoded_audio(mov,"s32le","<i4")//256,expected)
        streams=story.media._probe(mp4,"ffprobe")["streams"]
        self.assertEqual([int(s["duration_ts"])*Fraction(s["time_base"]) for s in streams],[Fraction(223,30)]*2)
        self.assertEqual(int(streams[0]["nb_read_frames"]),223)
        self.assertLessEqual(story.true_peak(mp4),-1)

    def test_picture_source_mapping_at_joins_and_during_lift(self):
        # Compare actual published RGB picture content, not just declared spans.
        checks=((37,"dialogue",37),(38,"mug",35),(64,"mug",61),
                (101,"mug",98),(123,"mug",120),(124,"dialogue",108),(222,"dialogue",206))
        for output,source,i in checks:
            with self.subTest(output=output,source=source,source_frame=i):
                a=read_frame(PUBLISHED/"story.mp4",output)
                b=cv2.resize(read_frame(self.assets[source],i),(1280,720),interpolation=cv2.INTER_LANCZOS4)
                self.assertGreater(cv2.PSNR(a,b),33)


if __name__=="__main__":
    unittest.main()
