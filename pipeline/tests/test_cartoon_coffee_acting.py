"""Check the multi-stage action on the source clock before encoding."""
import unittest

import numpy as np

from pipeline import cartoon_coffee_acting as acting


class CoffeeActingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=acting.prepare()

    def test_one_common_stationary_pot_before_contact_and_after_release(self):
        p=self.p
        for t in (0,.25,.5,.75,1):
            for render in (acting.pen_pose,acting.moving_arm):
                art=render(p,t)
                np.testing.assert_array_equal(art[646:873,761:910],p.ground[646:873,761:910])
                np.testing.assert_array_equal(art[689:881,936:1157],p.ground[689:881,936:1157])
                np.testing.assert_array_equal(art[:335],p.ground[:335])

    def test_stage_boundaries_share_exact_key_paintings(self):
        p=self.p
        for a,b in ((("pencil",1.),("reach",0.)), (("reach",1.),("lift",0.))):
            np.testing.assert_array_equal(acting.raw_frame(p,*a),acting.raw_frame(p,*b))
        self.assertEqual(acting.timing(900),("lift",0.))
        self.assertEqual(acting.timing(901),("reach",1.))
        self.assertEqual(acting.timing(911),("reach",0.))

    def test_timing_has_grounded_contact_holds_and_reuses_the_legacy_pour(self):
        keys=({678:("pencil",0),721:("pencil",1),722:("reach",0),738:("reach",1),
               739:("lift",0),761:("lift",1),762:("original",0),
               789:("original",0),864:("original",0),882:("lift",1)})
        for index,key in keys.items():
            self.assertEqual(acting.timing(index),key)
        for i in (-1,677,912,True):
            with self.assertRaises(ValueError):
                acting.timing(i)


if __name__=="__main__":
    unittest.main()
