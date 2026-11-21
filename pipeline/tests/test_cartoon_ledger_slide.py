"""Verify a single ledger slide and exact parked endpoint without encoding."""

from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import unittest

import cv2
import numpy as np

from pipeline import cartoon_ledger_slide as slide


PACKAGE = slide.story.root / "collab/june_ledger_slide_v1"
PROOF = Path(os.environ.get("JUNE_LEDGER_SLIDE_PROOF",PACKAGE/"ledger-slide-proof.json"))
MOVIE = PROOF.with_name("ledger-slide-review.mp4")


class LedgerSlideTests(unittest.TestCase):
    def test_contact_precedes_single_slide_and_release(self):
        self.assertEqual((slide.START, slide.STOP, slide.CONTEXT, slide.TRAVEL), (678, 789, (538, 868), 58))
        self.assertEqual(slide.CONTEXT[1]-slide.CONTEXT[0], 330)
        self.assertLess(slide.beat(708).shaft, 1.)
        self.assertEqual(slide.beat(709).shaft, 1.)
        self.assertEqual(slide.beat(721).contact_y, 12.)
        self.assertEqual(slide.beat(722).book_x, -58.)
        self.assertGreater(slide.beat(723).book_x, -58.)
        self.assertLess(slide.beat(738).book_x, 0.)
        self.assertEqual(slide.beat(739).book_x, 0.)
        self.assertGreater(slide.beat(744).contact_y, 0.)
        self.assertEqual(slide.beat(745), slide.Beat(1., 1., 0., 0.))
        cues = [slide.beat(i) for i in range(slide.START, slide.STOP)]
        self.assertTrue(all(a.book_x <= b.book_x for a, b in zip(cues, cues[1:])))
        self.assertTrue(all(-58. <= q.book_x <= 0. for q in cues))
        for i in range(723, 740):
            self.assertEqual((slide.beat(i).shaft, slide.beat(i).contact_y), (1., 12.))
        for i in (677, 789, 721.0, True):
            with self.subTest(frame=i), self.assertRaisesRegex(ValueError, "outside ledger slide study"):
                slide.beat(i)

    def test_single_rigid_book_only_changes_local_plate_and_rejoins_exact(self):
        p = slide.acting.prepare()
        staged = slide.stage(p)
        bare, with_pencil, book_alpha = staged[4], staged[5], staged[7]
        np.testing.assert_array_equal(bare[..., 3], book_alpha)
        np.testing.assert_array_equal(with_pencil[..., 3], book_alpha)
        self.assertEqual(cv2.connectedComponents((book_alpha > .5).astype(np.uint8))[0], 2)
        self.assertFalse(np.array_equal(bare[..., :3], with_pencil[..., :3]))
        park = p.park.copy()
        left, top, right, bottom = slide.BOX
        fixed = (np.s_[:top], np.s_[bottom:], np.s_[top:bottom,:left], np.s_[top:bottom,right:])
        images = {}
        for i in (678,709,730,739,745):
            q = slide.beat(i)
            image = images[i] = slide.art(staged,i)
            inherited = slide.previous.independent_pencil(p,q.finger,q.shaft)
            with self.subTest(frame=i):
                self.assertEqual((image.shape,image.dtype), ((941,1672,3),np.uint8))
                # The inherited pencil pose has its own mask; the ledger
                # compositor must not write beyond its declared BOX.
                for region in fixed:
                    np.testing.assert_array_equal(image[region], inherited[region])
        # Verify actual unoccluded grain and pencil texture are carried
        # by the same shift, not redrawn or left behind as a second prop.
        d = slide.TRAVEL
        np.testing.assert_array_equal(images[709][888:900,527-d:546-d], images[739][888:900,527:546])
        np.testing.assert_array_equal(images[709][837:846,425-d:445-d], images[739][837:846,425:445])
        self.assertFalse(np.array_equal(images[730],images[739]))
        np.testing.assert_array_equal(images[745],park)
        np.testing.assert_array_equal(p.park,park)

    def test_registered_replacement_overwrites_the_core_of_the_swept_book_region(self):
        p = slide.acting.prepare()
        staged = slide.stage(p)
        legacy = p.lift.lifted.copy()
        legacy[:,:-16] = p.lift.lifted[:,16:]
        at = np.s_[856:871,690-16:706-16]
        legacy[at] = 255
        rgb = slide.registered_layer(p,staged,legacy,721)
        native = slide.art(staged,721)
        np.testing.assert_array_equal(rgb[at],native[856:871,690:706])
        # The original pre-pour renderer substitutes the pot/arm via a
        # registered delta. The ledger-only overwrite must not affect it.
        inherited = np.clip(legacy[:610,:-16].astype(np.int16)+
            native[:610,16:].astype(np.int16)-p.lift.lifted[:610,16:],0,255).astype(np.uint8)
        np.testing.assert_array_equal(rgb[:610,:-16],inherited)

    @unittest.skipUnless(PROOF.is_file() and MOVIE.is_file() and shutil.which("ffprobe"),
                         "local draft movie or ffprobe unavailable")
    def test_published_review_clock_and_protected_native_approach(self):
        evidence = json.loads(PROOF.read_text(encoding="utf-8"))
        review = MOVIE
        self.assertEqual(evidence["baseline_sha256"],slide.previous.BASE_SHA)
        self.assertEqual(evidence["builder_sha256"],slide.digest(Path(slide.__file__)))
        self.assertEqual(evidence["review_sha256"],slide.digest(review))
        self.assertEqual(evidence["source_span"],[678,789])
        self.assertEqual(evidence["review_span"],[538,868])
        self.assertEqual(evidence["screen_space_displacement"],58)
        self.assertEqual(evidence["timing"],{"shaft_flat":709,"contact":721,"slide_start":723,
                                             "slide_end":739,"release":745})
        for key, flag in (("comparison_only",True),("human_accepted",False),("production_release",False)):
            self.assertIs(evidence[key],flag)
        raw = evidence["native_rgb_sha256"]
        self.assertEqual(set(raw),{str(i) for i in range(678,789)})
        locked = slide.story.previous.native_inventories("visitor")[1]
        for i in range(782,789):
            self.assertEqual(raw[str(i)],locked[i])
        video,audio = slide.cut.media._probe(review,"ffprobe")["streams"]
        self.assertEqual((video["codec_type"],audio["codec_type"]),("video","audio"))
        self.assertEqual((video["width"],video["height"],int(video["nb_read_frames"])),(1536,432,330))
        self.assertEqual(Fraction(video["avg_frame_rate"]),Fraction(30))
        self.assertEqual((audio["sample_rate"],audio["channels"]),("48000",2))
        for stream in (video,audio):
            self.assertAlmostEqual(float(stream["duration"]),11.0,places=3)


if __name__=="__main__":
    unittest.main()
