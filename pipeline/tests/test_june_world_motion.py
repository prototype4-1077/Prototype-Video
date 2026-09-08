import unittest
from pipeline.june_world_motion import sample, audit_evaluated, FRAMES, BEATS, STEP_WINDOWS

class WorldMotionTests(unittest.TestCase):
    def test_continuous_clock(self):
        self.assertEqual([f for a,b,_ in BEATS for f in range(a,b+1)], list(range(1,FRAMES+1)))

    def test_always_has_support(self):
        for f in range(1,FRAMES+1):
            self.assertTrue(any(c for p,c in sample(f)['feet'].values()), f)

    def test_contact_does_not_slide(self):
        for f in range(2,FRAMES+1):
            a,b=sample(f-1),sample(f)
            for side in ('L','R'):
                pa,ca=a['feet'][side];pb,cb=b['feet'][side]
                if ca and cb:self.assertEqual(pa,pb,(f,side))

    def test_four_steps_clear_floor_and_finish(self):
        for a,b,side,dest in STEP_WINDOWS:
            mid=sample((a+b)//2)['feet'][side]
            self.assertGreater(mid[0][2],.44)
            self.assertFalse(mid[1])
            self.assertAlmostEqual(sample(b)['feet'][side][0][1],dest)
            self.assertTrue(sample(b)['feet'][side][1])

    def test_pickup_binds_at_stationary_wrist(self):
        self.assertFalse(sample(464)['mug_attached'])
        self.assertTrue(sample(465)['mug_attached'])
        self.assertEqual(sample(450)['hand.R'],sample(465)['hand.R'])
        self.assertGreater(sample(510)['hand.R'][2],sample(465)['hand.R'][2])

    def test_address_turns_toward_viewer_left_camera(self):
        self.assertLess(sample(555)['head_yaw'],0)

    def test_final_hold(self):
        a,b=sample(690),sample(720)
        for key in ('pelvis_offset','feet','hand.R','hand.L','chuckle','head_yaw'):
            self.assertEqual(a[key],b[key])

    def test_reject_out_of_clock(self):
        for f in (0,721,1.5):
            with self.assertRaises(ValueError):sample(f)

class EvaluatedEvidenceTests(unittest.TestCase):
    def fixture(self):
        return [{'frame':f,'feet':{s:{'contact':True,'position':[0,0,.34],
                 'target_error':0.} for s in ('L','R')},
                 'hand_target_error':{'L':0.,'R':0.},
                 'sole_min_z':{'June_Boot_Sole_L':.0775,'June_Boot_Sole_R':.0775},
                 'boot_table_bbox_collisions':0,'mug_position':[.5,-1.,1.5]} for f in range(1,721)]

    def test_art_never_follows_mechanical_pass(self):
        r=audit_evaluated(self.fixture(),.0775)
        self.assertTrue(r['control_mechanics_passed'])
        self.assertFalse(r['production_approved'])

    def test_reject_measured_sliding_despite_perfect_targets(self):
        rows=self.fixture();rows[100]['feet']['L']['position'][0]=.04
        r=audit_evaluated(rows,.0775)
        self.assertFalse(r['checks']['planted_ankle_slide'])
        self.assertFalse(r['control_mechanics_passed'])

    def test_reject_furniture_collision(self):
        rows=self.fixture();rows[200]['boot_table_bbox_collisions']=1
        self.assertFalse(audit_evaluated(rows,.0775)['checks']['boot_table_clearance'])

    def test_reject_floor_penetration(self):
        rows=self.fixture();rows[100]['sole_min_z']['June_Boot_Sole_L']=.05
        self.assertFalse(audit_evaluated(rows,.0775)['checks']['floor_penetration'])

    def test_reject_missing_or_nonfinite_evidence(self):
        rows=self.fixture()
        with self.assertRaises(ValueError):audit_evaluated(rows[:-1],.0775)
        rows[0]['hand_target_error']['R']=float('nan')
        with self.assertRaises(ValueError):audit_evaluated(rows,.0775)

    def test_reject_pickup_teleport(self):
        rows=self.fixture();rows[464]['mug_position'][0]+=.1
        self.assertFalse(audit_evaluated(rows,.0775)['checks']['pickup_continuity'])

if __name__=='__main__':unittest.main()

