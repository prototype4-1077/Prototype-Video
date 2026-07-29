import json
from pathlib import Path
import tempfile
import unittest

from PIL import ImageChops

from pipeline.cartoon_expression_atlas import expression_performance_plan
from pipeline.cartoon_hero_scene import (
    atlas_box_to_plate,
    compose_hero_frame,
    load_body_motion_contract,
    load_hero_plate_contract,
    prepare_hero_sources,
)
from pipeline.cartoon_viseme_atlas import performance_viseme_plan


class CartoonHeroSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.hero_contract_path = cls.repo_root / "concept/style_frames/june_oxley_porch_hero_plate_v1.json"
        cls.viseme_contract_path = cls.repo_root / "concept/style_frames/june_oxley_viseme_atlas_v1.json"
        cls.expression_contract_path = cls.repo_root / "concept/style_frames/june_oxley_expression_atlas_v1.json"
        cls.viseme_cues = cls.repo_root / "concept/style_frames/june_golden_scene_rhubarb_lipsync_v1.json"
        cls.expression_cues = cls.repo_root / "concept/style_frames/june_golden_scene_expression_cues_v1.json"
        cls.motion_cues = cls.repo_root / "concept/style_frames/june_golden_scene_body_motion_v1.json"

    def test_hero_contract_locks_widescreen_plate_and_zero_cash(self):
        contract, image_path = load_hero_plate_contract(self.hero_contract_path)
        self.assertEqual((contract["output"]["width"], contract["output"]["height"]), (1920, 1080))
        self.assertEqual(contract["generation"]["cash_cost"], 0)
        self.assertFalse(contract["generation"]["paid_runtime_dependency"])
        self.assertTrue(image_path.is_file())

    def test_atlas_registration_maps_both_patch_boxes(self):
        contract, _ = load_hero_plate_contract(self.hero_contract_path)
        self.assertEqual(atlas_box_to_plate((65, 45, 353, 230), contract), (532, 106, 906, 346))
        self.assertEqual(atlas_box_to_plate((88, 150, 330, 310), contract), (561, 242, 876, 450))

    def test_body_motion_compiles_exact_bounded_frame_clock(self):
        contract, _ = load_hero_plate_contract(self.hero_contract_path)
        metadata, plan = load_body_motion_contract(self.motion_cues, hero_contract=contract)
        self.assertEqual(metadata["frame_count"], 453)
        self.assertEqual(metadata["keyframe_count"], 14)
        self.assertEqual(len(plan), 453)
        self.assertEqual(plan[0]["frame"], 1.0)
        self.assertEqual(plan[-1]["frame"], 453.0)
        for entry in plan:
            for channel, (low, high) in contract["motion_bounds"].items():
                self.assertGreaterEqual(entry[channel], low)
                self.assertLessEqual(entry[channel], high)

    def test_body_motion_rejects_out_of_bounds_head_move(self):
        contract, _ = load_hero_plate_contract(self.hero_contract_path)
        payload = json.loads(self.motion_cues.read_text(encoding="utf-8"))
        payload["keyframes"][2]["head_x_px"] = 80.0
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad-motion.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exceeds"):
                load_body_motion_contract(path, hero_contract=contract)

    def test_compositor_produces_distinct_full_hd_frames(self):
        sources = prepare_hero_sources(
            self.hero_contract_path,
            self.viseme_contract_path,
            self.expression_contract_path,
        )
        _, visemes = performance_viseme_plan(self.viseme_cues)
        _, expressions = expression_performance_plan(
            self.expression_cues,
            expected_atlas_id=sources["expression_contract"]["atlas_id"],
        )
        _, motion = load_body_motion_contract(self.motion_cues, hero_contract=sources["hero_contract"])
        first = compose_hero_frame(
            sources, visemes[0], expressions[0], motion[0], secondary={}, frame_index=1, fps=30
        )
        compassion = compose_hero_frame(
            sources, visemes[409], expressions[409], motion[409], secondary={}, frame_index=410, fps=30
        )
        self.assertEqual(first.size, (1920, 1080))
        self.assertEqual(compassion.size, (1920, 1080))
        self.assertIsNotNone(ImageChops.difference(first, compassion).getbbox())


if __name__ == "__main__":
    unittest.main()
