"""Check the visitor's insert, without rendering or promoting a full film."""

from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "collab/june_visitor_turn_v1"
PREVIOUS = ROOT / "collab/june_coffee_continuity_v1/verification.json"
ART = ROOT / "concept/style_frames/june-gs050-visitor-knee-v1.png"
INSERT = (608, 628)
REPLACEMENT = (564, 678)
REVIEW = (538, 678)
ROI = (238, 301, 891, 815)
UNCHANGED_PACKETS = 1026
UNCHANGED_SHOT_FRAMES = 94


class VisitorInsertTests(unittest.TestCase):
    def test_spans_and_sources_match_the_current_full_film(self):
        from pipeline import cartoon_visitor_insert as visitor

        self.assertEqual(tuple(visitor.INSERT), INSERT)
        self.assertEqual(tuple(visitor.REPLACEMENT), REPLACEMENT)
        self.assertEqual(tuple(visitor.REVIEW), REVIEW)
        self.assertEqual(tuple(visitor.ROI), ROI)
        whole = json.loads(PREVIOUS.read_text(encoding="utf-8"))
        self.assertEqual(visitor.SHA_SOURCE, whole["candidate_sha256"])
        self.assertEqual(visitor.ART_SHA, sha256(ART.read_bytes()).hexdigest())
        self.assertEqual(REVIEW[1] - REVIEW[0], 140)
        self.assertEqual(whole["clock"][3] - (REPLACEMENT[1] - REPLACEMENT[0]), UNCHANGED_PACKETS)
        self.assertEqual((REPLACEMENT[1] - REPLACEMENT[0]) - (INSERT[1] - INSERT[0]), UNCHANGED_SHOT_FRAMES)

    def test_tremor_moves_the_local_art_but_not_the_surrounding_plate(self):
        from pipeline import cartoon_visitor_insert as visitor

        art = visitor.load_art()
        self.assertEqual(art.shape, (941, 1672, 3))
        self.assertEqual(art.dtype, np.uint8)
        still = art.copy()
        x, y, right, bottom = ROI
        outside = (np.s_[:y], np.s_[bottom:], np.s_[y:bottom, :x], np.s_[y:bottom, right:])
        hashes = set()
        for frame in range(*INSERT):
            with self.subTest(frame=frame):
                image = visitor.visitor_frame(art, frame)
                self.assertEqual(image.shape, art.shape)
                self.assertEqual(image.dtype, np.uint8)
                for region in outside:
                    np.testing.assert_array_equal(image[region], still[region])
                hashes.add(sha256(image[y:bottom, x:right].tobytes()).hexdigest())
        self.assertGreater(len(hashes), 1)
        np.testing.assert_array_equal(art, still)
        middle = sum(INSERT) // 2
        np.testing.assert_array_equal(visitor.visitor_frame(art, middle), visitor.visitor_frame(still, middle))

    def test_receipt_records_preserved_frames_and_no_approval(self):
        from pipeline import cartoon_visitor_insert as visitor

        proof = json.loads((PACKAGE / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(proof["insert_span"], list(INSERT))
        self.assertEqual(proof["replaced_span"], list(REPLACEMENT))
        self.assertEqual(proof["unchanged_video_packets"], UNCHANGED_PACKETS)
        self.assertEqual(proof["unchanged_other_native_frames"], UNCHANGED_SHOT_FRAMES)
        self.assertIs(proof["audio_subtitle_packets_exact"], True)
        self.assertIs(proof["human_accepted"], False)
        self.assertIs(proof["production_release"], False)
        self.assertEqual(proof["decoded_repaired_frames_exact"], 303)
        self.assertEqual(proof["review_sha256"], sha256((PACKAGE / "visitor-turn-review.mp4").read_bytes()).hexdigest())
        self.assertEqual(proof["builder_sha256"], sha256(Path(visitor.__file__).read_bytes()).hexdigest())
        new = json.loads((PACKAGE / "visitor-gs050-native-frames.json").read_text(encoding="utf-8"))
        self.assertEqual(new["start_frame_zero_based"], REPLACEMENT[0])
        original = visitor.native_reference()
        self.assertEqual(len(new["rgb24_sha256"]), len(original))
        changed = [i for i,(before,after) in enumerate(zip(original, new["rgb24_sha256"]), REPLACEMENT[0])
                   if before != after]
        self.assertEqual(changed, list(range(*INSERT)))

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is unavailable")
    def test_published_comparison_media_clock(self):
        local = os.environ.get("JUNE_VISITOR_TEST_PROOF")
        if local:
            path = Path(local)
        else:
            path, = sorted(PACKAGE.glob("*.mp4"))
        data = subprocess.check_output([
            "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(path),
        ], text=True)
        streams = {s["codec_type"]: s for s in json.loads(data)["streams"]}
        video, audio = streams["video"], streams["audio"]
        self.assertEqual((video["width"], video["height"], int(video["nb_read_frames"])), (1536, 432, 140))
        self.assertEqual(Fraction(video["avg_frame_rate"]), Fraction(30))
        self.assertEqual((int(audio["sample_rate"]), audio["channels"]), (48000, 2))
        for stream in (video, audio):
            self.assertAlmostEqual(float(stream["duration"]), 140 / 30, places=3)


if __name__ == "__main__":
    unittest.main()
