"""Regression guards for the alternate GS020 offer; not an acting verdict."""
import unittest
from functools import lru_cache

import numpy as np

from pipeline import cartoon_mug_offer as shot


class OfferClockTests(unittest.TestCase):
    def test_slide_release_and_pickup_have_ordered_boundaries(self):
        clock = [shot.cues(i) for i in range(shot.loan.N)]
        self.assertEqual(shot.SPAN, (129, 225))
        slide, release, withdraw, wrap, rise = np.array([
            (q.slide, q.release, q.withdrawn, q.borrow.wrap, q.borrow.rise)
            for q in clock
        ]).T
        self.assertLess(slide[0], 0)
        self.assertEqual(slide[-1], 0)
        self.assertTrue(np.all(np.diff(slide) >= 0))
        for phase in (release, withdraw, wrap, rise):
            self.assertEqual((phase[0], phase[-1]), (0, 1))
            self.assertTrue(np.all(np.diff(phase) >= 0))
            self.assertGreater(np.count_nonzero((0 < phase) & (phase < 1)), 1)
        # Insist on the story beats, rather than the precise duration of each ease.
        self.assertTrue(np.all(slide[release > 0] == 0))
        self.assertTrue(np.all(release[withdraw > 0] > 0))
        self.assertTrue(np.all(wrap[rise > 0] == 1))
        self.assertTrue(np.all(withdraw[rise > 0] == 1))
        for i in (-1, shot.loan.N, True, 3.0):
            with self.subTest(i=i), self.assertRaises(ValueError):
                shot.cues(i)

    def test_donor_keeps_chirality_and_no_source_crop_edge_crosses_screen(self):
        # x=0 cuts across both drawn denim sleeves.  Project the whole edge,
        # not just its center: a positive determinant alone misses a cut cuff.
        h = shot.layer.LEFT[3]-shot.layer.LEFT[1]
        edge = np.array([[0,0,1], [0,h-1,1]])
        for i in range(shot.loan.N):
            q = shot.cues(i)
            if q.withdrawn == 1:
                continue
            m = shot.donor_warp(q)
            linear = m[:,:2].astype(float)
            self.assertGreater(np.linalg.det(linear), 0, "reflected donor")
            np.testing.assert_allclose(linear.T @ linear, np.eye(2)*np.linalg.det(linear),
                                       atol=1e-5, err_msg="squashed hand")
            view_y = (edge @ m.T)[:,1] + shot.FRONT[1]
            self.assertGreater(view_y.min(), shot.loan.H, "the source crop cuts into the frame")


class OfferPixelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stage = shot.prepare()
        cls.offer = staticmethod(lru_cache(maxsize=12)(lambda i: shot.paint(cls.stage,i)))
        cls.original = staticmethod(lru_cache(maxsize=12)(lambda i: shot.loan.paint(cls.stage.loan,i)))

    @classmethod
    def tearDownClass(cls):
        cls.offer.cache_clear()
        cls.original.cache_clear()
        del cls.stage

    def test_cash_hand_and_face_are_protected_like_in_original_loan(self):
        reference = self.original(0)
        # Check every frame with a visible donor, including the transitioning
        # alpha/shadow, not just the pose endpoints. The retained shot already
        # has its own cash guard; spot-check it after the foreground withdraws.
        visible = [i for i in range(shot.loan.N) if shot.cues(i).withdrawn < 1]
        for i in dict.fromkeys([*visible, visible[-1]+1, 48, 95]):
            with self.subTest(i=i):
                out = shot.paint(self.stage,i)
                # Original loan's protected cash-hand window includes the fingers,
                # not only the bills. A shifted cup or new hand may not cover it.
                for box in (np.s_[540:785,302:545], np.s_[:390,530:880]):
                    np.testing.assert_array_equal(out[box], reference[box])

    def test_same_empty_cup_slides_then_stays_put_as_june_releases(self):
        ref = self.original(0)
        # Distinctive rim and chip, left of the handle and above June's fingers.
        y, b, x, r = 615, 685, 676, 758
        for i in (0, 16, 24, 32):
            dx = shot.cues(i).slide
            self.assertEqual(dx, int(dx))
            dx = int(dx)
            np.testing.assert_array_equal(self.offer(i)[y:b,x+dx:r+dx], ref[y:b,x:r])
        # A renderer that merely delays the old shot must not pass as an offer.
        region = np.s_[800:932,325:548]
        changed = np.any(self.offer(0)[region] != ref[region], axis=2)
        self.assertGreater(changed.mean(), .1)

    def test_right_hand_performs_original_wrap_and_lift_after_a_delay(self):
        # Keep these tests tied to a visible feature: the visitor's fingertips
        # and knuckles on screen right, not the dramatically still far shoulder.
        box = np.s_[508:786,919:1125]
        first_wrap = next(i for i in range(shot.loan.N) if shot.cues(i).borrow.wrap > 0)
        old_wrap = next(i for i in range(shot.loan.N) if shot.loan.cues(i).wrap > 0)
        delay = first_wrap-old_wrap
        self.assertGreater(delay, 0)
        for t in (12, 20, 27, 34, 44):
            with self.subTest(original_index=t):
                np.testing.assert_array_equal(self.offer(t+delay)[box], self.original(t)[box])
        self.assertFalse(np.array_equal(self.offer(old_wrap+delay)[box], self.offer(27+delay)[box]))

    def test_last_held_frames_rejoin_the_exact_original_shot(self):
        for i in (82, 88, 95):
            with self.subTest(i=i):
                np.testing.assert_array_equal(self.offer(i), self.original(i))


if __name__ == "__main__":
    unittest.main()
