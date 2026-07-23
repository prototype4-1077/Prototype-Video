import json, os, sys, tempfile, unittest, hashlib
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # pipeline/
ROOT = os.path.dirname(HERE)                                          # repo root
sys.path.insert(0, HERE)
import animation_profiles as AP, cartoon_renderer as CR, cartoon_budget as CB, cartoon_continuity as CC

EMO = os.path.join(ROOT, "build/the-emotion-scam-cartoon-v2")
JUNE = os.path.join(ROOT, "build/june-oxley-folks-aint-roadblocks-cartoon-v2")
def load(slug): return json.load(open(os.path.join(ROOT, "build", slug, "script.json")))
def fp(d): return hashlib.sha256("\n".join(s["text"] for s in d["scenes"]).encode()).hexdigest()[:16]
def man(mov=3, kinds=("subtle_breath","sway","steam_rise")):
    return {"background":"bg.png","layers":[{"id":f"l{i}","depth":4+i,"motion":kinds[i%len(kinds)],"asset":"a.png"} for i in range(mov)]}

class CartoonBackend(unittest.TestCase):
    def test01_cartoon_only_rejects_stock(self):
        s={"animation_profile":"animated_tier1","animation_contract_version":1,"cartoon_only":True,
           "generated_temporal_video_required":True,"max_still_source_ratio":0.2,
           "scenes":[{"text":"x","animation_profile":"animated_tier1","animation_query":"q","motion_kind":"video","pexels_id":9}]}
        self.assertTrue(any("cartoon_only" in e for e in AP.validate(s)))
    def test02_limited_2_5d_satisfies(self):
        self.assertEqual(CR.validate(man(3)), [])
    def test03_pan_zoom_alone_fails(self):
        self.assertTrue(CR.validate({"background":"b","layers":[]}))
    def test04_three_layers_pass(self):
        self.assertEqual(CR.validate(man(3)), [])
    def test05_character_needs_subject_motion(self):
        m=man(3, kinds=("steam_rise","slide_in","object_rotate"))
        self.assertTrue(any("character scene" in e for e in CR.validate(m, scene_kind="character")))
    def test06_object_needs_object_motion(self):
        m=man(3, kinds=("subtle_breath","sway","nod_and_turn"))
        self.assertTrue(any("object scene" in e for e in CR.validate(m, scene_kind="object")))
    def test07_paid_blocked_without_budget(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(CB.BudgetError): CB.assert_paid_allowed(d,"replicate","wan",3,5)
    def test08_paid_scene_count_capped(self):
        with tempfile.TemporaryDirectory() as d:
            json.dump({"approved":True,"provider":"replicate","model":"wan","estimated_total_cost":2.0,
                       "scenes":[1,2,3,4,5,6,7,8]}, open(os.path.join(d,"generation-budget.json"),"w"))
            with self.assertRaises(CB.BudgetError): CB.assert_paid_allowed(d,"replicate","wan",8,5)
    def test09_master_sequence_serves_multiple(self):
        self.assertTrue(CC.serves_multiple("june-oxley-folks-aint-roadblocks-cartoon-v2","june-diner"))
    def test10_continuity_group_preserves_ids(self):
        self.assertEqual(CC.group_consistency([{"location_id":"diner"},{"location_id":"diner"}]), [])
        self.assertTrue(CC.group_consistency([{"location_id":"diner"},{"location_id":"porch"}]))
    def test11_emotion_no_reality_machine(self):
        d=load("the-emotion-scam-cartoon-v2")
        self.assertIsNone(d["series_label"]); self.assertNotIn("reality machine", json.dumps(d).lower())
    def test12_june_keeps_series_label(self):
        self.assertEqual(load("june-oxley-folks-aint-roadblocks-cartoon-v2")["series_label"], "JUNE OXLEY")
    def test13_june_voice_id_preserved(self):
        self.assertEqual(load("june-oxley-folks-aint-roadblocks-cartoon-v2")["elevenlabs_voice_id"], "NOpBlnGInO9m6vDvFkFC")
    def test14_narration_fingerprints_unchanged(self):
        for slug,tier in [("the-emotion-scam-cartoon-v2","the-emotion-scam-tier1"),
                          ("june-oxley-folks-aint-roadblocks-cartoon-v2","june-oxley-folks-aint-roadblocks-tier1")]:
            self.assertEqual(fp(load(slug)), fp(load(tier)))
    def test15_audio_deviation_documented(self):
        for slug in ("the-emotion-scam-cartoon-v2","june-oxley-folks-aint-roadblocks-cartoon-v2"):
            self.assertIn("voiceover_regenerated_reason", load(slug))  # not silently ignored
    def test16_no_render_request(self):
        for base in (EMO, JUNE):
            self.assertFalse(os.path.exists(os.path.join(base,"render.request")))

if __name__ == "__main__":
    unittest.main()
