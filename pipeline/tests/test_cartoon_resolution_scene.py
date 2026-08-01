from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import ImageChops

from pipeline.cartoon_expression_atlas import expression_performance_plan
from pipeline.cartoon_hero_scene import load_body_motion_contract
from pipeline.cartoon_resolution_scene import (
    _load_resolution_contract,
    compose_resolution_frame,
    prepare_resolution_sources,
)
from pipeline.cartoon_viseme_atlas import performance_viseme_plan


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/style_frames/june_golden_scene_gs070_resolution_v1.json"
VISEME_ATLAS = REPO_ROOT / "concept/style_frames/june_oxley_viseme_atlas_v1.json"
EXPRESSION_ATLAS = REPO_ROOT / "concept/style_frames/june_oxley_expression_atlas_v1.json"
VISEME_CUES = REPO_ROOT / "concept/style_frames/june_golden_scene_gs070_rhubarb_v1.json"
EXPRESSION_CUES = REPO_ROOT / "concept/style_frames/june_golden_scene_gs070_expression_v1.json"
MOTION_CUES = REPO_ROOT / "concept/style_frames/june_golden_scene_gs070_body_motion_v1.json"


class CartoonResolutionSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = prepare_resolution_sources(CONTRACT, VISEME_ATLAS, EXPRESSION_ATLAS)
        cls.viseme_metadata, cls.visemes = performance_viseme_plan(VISEME_CUES)
        cls.expression_metadata, cls.expressions = expression_performance_plan(EXPRESSION_CUES)
        cls.motion_metadata, cls.motion = load_body_motion_contract(
            MOTION_CUES,
            hero_contract=cls.sources["contract"],
        )

    def test_contract_locks_two_authored_sources_and_exact_gs070_clock(self) -> None:
        contract, plate, insert = _load_resolution_contract(CONTRACT)
        self.assertEqual(contract["shot_id"], "GS070")
        self.assertEqual(contract["output"]["frame_count"], 228)
        self.assertEqual(contract["output"]["duration_seconds"], 7.6)
        self.assertTrue(plate.is_file())
        self.assertTrue(insert.is_file())
        self.assertEqual(contract["generation"]["cash_cost"], 0)
        self.assertFalse(contract["generation"]["paid_runtime_dependency"])

    def test_affine_registration_is_feature_scoped_and_inside_plate(self) -> None:
        mouth = self.sources["plate_mouth_box"]
        eyes = self.sources["plate_expression_box"]
        self.assertEqual(mouth, (468, 252, 820, 501))
        self.assertEqual(eyes, (479, 127, 846, 357))
        self.assertLess((mouth[2] - mouth[0]) * (mouth[3] - mouth[1]), 90_000)
        self.assertLess((eyes[2] - eyes[0]) * (eyes[3] - eyes[1]), 90_000)
        self.assertEqual(set(self.sources["viseme_patches"]), set("ABCDEFGHX"))

    def test_contract_rejects_shifted_cut_and_bad_affine_scale(self) -> None:
        broken = json.loads(CONTRACT.read_text(encoding="utf-8"))
        shifted = copy.deepcopy(broken)
        shifted["sequence"]["direct_address_start_frame"] = 47
        with patch("pipeline.cartoon_hero_scene.json.loads", return_value=shifted):
            with self.assertRaisesRegex(ValueError, "direct_address_start_frame"):
                _load_resolution_contract(CONTRACT)
        unsafe = copy.deepcopy(broken)
        unsafe["atlas_registration"]["affine_matrix"] = [[8.0, 0.0, 0.0], [0.0, 8.0, 0.0]]
        with patch("pipeline.cartoon_hero_scene.json.loads", return_value=unsafe):
            with self.assertRaisesRegex(ValueError, "unsafe scale"):
                _load_resolution_contract(CONTRACT)

    def test_all_performance_tracks_share_one_exact_228_frame_clock(self) -> None:
        self.assertEqual(self.viseme_metadata["duration_seconds"], 7.6)
        self.assertEqual(self.expression_metadata["duration_seconds"], 7.6)
        self.assertEqual(self.motion_metadata["duration_seconds"], 7.6)
        self.assertEqual({len(self.visemes), len(self.expressions), len(self.motion)}, {228})
        self.assertEqual(self.visemes[-1]["to_shape"], "X")

    def test_compact_nod_completes_before_locked_final_hold(self) -> None:
        y_positions = [float(entry["head_y_px"]) for entry in self.motion[156:188]]
        self.assertLess(min(y_positions), -1.0)
        self.assertGreater(max(y_positions), 3.0)
        for entry in self.motion[201:]:
            self.assertEqual(entry["head_x_px"], 0.0)
            self.assertEqual(entry["head_y_px"], 0.0)
            self.assertEqual(entry["head_tilt_deg"], 0.0)
            self.assertEqual(entry["shoulder_x_px"], 0.0)
            self.assertEqual(entry["breath_y_px"], 0.0)

    def test_hard_cut_switches_sources_without_interpolated_frame(self) -> None:
        secondary = self.motion_metadata["secondary_motion"]
        cut_out = compose_resolution_frame(
            self.sources,
            self.visemes[44],
            self.expressions[44],
            self.motion[44],
            frame_index=45,
            fps=30,
            secondary=secondary,
        )
        cut_in = compose_resolution_frame(
            self.sources,
            self.visemes[45],
            self.expressions[45],
            self.motion[45],
            frame_index=46,
            fps=30,
            secondary=secondary,
        )
        self.assertEqual(cut_out.size, (1920, 1080))
        self.assertEqual(cut_in.size, (1920, 1080))
        self.assertIsNotNone(ImageChops.difference(cut_out, cut_in).getbbox())

    def test_final_hold_locks_body_but_keeps_porch_alive(self) -> None:
        secondary = self.motion_metadata["secondary_motion"]
        first = compose_resolution_frame(
            self.sources,
            self.visemes[201],
            self.expressions[201],
            self.motion[201],
            frame_index=202,
            fps=30,
            secondary=secondary,
        )
        last = compose_resolution_frame(
            self.sources,
            self.visemes[227],
            self.expressions[227],
            self.motion[227],
            frame_index=228,
            fps=30,
            secondary=secondary,
        )
        self.assertIsNotNone(ImageChops.difference(first, last).getbbox())


if __name__ == "__main__":
    unittest.main()
