from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

import numpy as np

from pipeline import cartoon_acting_motion_audit as audit
from pipeline.cartoon_hero_scene import load_body_motion_contract


class ActingMotionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.contract = audit.load_contract()
        cls.scene = json.loads(
            (cls.repo_root / cls.contract["locks"]["gs070_scene"]["path"]).read_text(encoding="utf-8")
        )
        cls.body_path = cls.repo_root / cls.contract["locks"]["phase33_body_motion"]["path"]
        cls.body = json.loads(cls.body_path.read_text(encoding="utf-8"))
        _, cls.motion = load_body_motion_contract(cls.body_path, hero_contract=cls.scene)

    def test_contract_is_zero_cash_still_only_and_fail_closed(self) -> None:
        self.assertEqual(self.contract["cash_cost"], 0)
        self.assertFalse(self.contract["paid_runtime_dependency"])
        self.assertFalse(self.contract["network_runtime_required"])
        diagnostic = self.contract["diagnostic"]
        self.assertFalse(diagnostic["source_mutation_allowed"])
        self.assertFalse(diagnostic["picture_rebuild_allowed"])
        self.assertFalse(diagnostic["video_encode_allowed"])
        self.assertFalse(diagnostic["promotion_allowed"])
        self.assertFalse(diagnostic["human_acting_acceptance_claim_allowed"])

    def test_archive_and_frame_mapping_are_exact(self) -> None:
        picture = self.contract["immutable_picture"]
        self.assertEqual(picture["frame_count"], 303)
        self.assertEqual(picture["width"], 1920)
        self.assertEqual(picture["height"], 1080)
        self.assertEqual(picture["fps"], 30)
        self.assertEqual(
            self.contract["diagnostic"]["phase36_direct_address_output_frames_inclusive"],
            [76, 237],
        )
        self.assertEqual(self.contract["diagnostic"]["phase35_local_frames_inclusive"], [1, 162])

    def test_camera_geometry_matches_declared_renderer_rounding(self) -> None:
        first = audit._camera_geometry(0.0, self.scene)
        self.assertAlmostEqual(first["base_scale"], 1920 / 1672)
        self.assertEqual(first["relative_scale_from_zero_push"], 1.0)
        self.assertEqual(first["resized_width"], 1920)
        self.assertEqual(first["resized_height"], 1081)
        self.assertEqual(first["crop_left"], 0)
        self.assertEqual(first["crop_top"], 0)
        pushed = audit._camera_geometry(0.02, self.scene)
        self.assertEqual(pushed["resized_width"], round(1672 * (1920 / 1672) * 1.02))
        self.assertEqual(pushed["resized_height"], round(941 * (1920 / 1672) * 1.02))
        self.assertGreaterEqual(pushed["crop_left"], 0)
        self.assertGreaterEqual(pushed["crop_top"], 0)

    def test_identity_camera_normalization_is_pixel_exact(self) -> None:
        y, x = np.indices((64, 96))
        frame = np.stack((x % 256, y % 256, (x + y) % 256), axis=2).astype(np.uint8)
        scene = {
            "output": {"width": 96, "height": 64},
            "image": {"width": 96, "height": 64},
            "rig_regions": {"camera_anchor": [0.4, 0.5]},
        }
        aligned, valid, geometry = audit._camera_normalize(frame, 0.0, scene)
        np.testing.assert_array_equal(aligned, frame)
        self.assertTrue(np.all(valid))
        self.assertEqual(geometry["crop_left"], 0)

    def test_identical_region_pair_has_zero_motion(self) -> None:
        frame = np.full((120, 160, 3), 127, dtype=np.uint8)
        valid = np.ones((120, 160), dtype=bool)
        metrics = audit._pair_region_metrics(
            frame, frame.copy(), valid, valid, [20, 20, 140, 100],
            self.contract["diagnostic"]["pair_metrics"],
        )
        self.assertEqual(metrics["mean_rgb_delta_u8"], 0.0)
        self.assertEqual(metrics["p95_rgb_delta_u8"], 0.0)
        self.assertEqual(metrics["median_flow_px"], 0.0)
        self.assertEqual(metrics["p95_flow_px"], 0.0)

    def test_source_structure_proves_missing_independent_acting_controls(self) -> None:
        structure = audit._source_structure(self.contract, self.body, self.scene, self.motion)
        self.assertEqual(structure["independent_hand_controls"], [])
        self.assertEqual(structure["independent_arm_controls"], [])
        self.assertEqual(structure["authored_gesture_events"], [])
        self.assertEqual(structure["maximum_absolute_shoulder_x_px"], 0.4)
        self.assertEqual(structure["maximum_absolute_breath_y_px"], 1.3)
        self.assertTrue(structure["final_hold_all_declared_body_controls_zero"])
        self.assertTrue(structure["final_hold_camera_push_constant"])

    def test_plan_has_bounded_events_and_preserves_final_stillness(self) -> None:
        plan = self.contract["proposed_next_acting_slice"]
        self.assertEqual(plan["classification"], "PLAN_ONLY_NOT_APPLIED")
        events = plan["performance_events"]
        self.assertEqual(events, sorted(events, key=lambda row: row["local_frames"][0]))
        self.assertTrue(all(1 <= row["local_frames"][0] < row["local_frames"][1] <= 162 for row in events))
        self.assertIn("no cyclic idle bobbing", plan["hard_safety_rules"])
        self.assertIn("final stillness is intentional and atmosphere remains alive", plan["hard_safety_rules"])

    def test_output_allowlist_is_png_plus_lf_json_only(self) -> None:
        allowlist = self.contract["output"]["allowlist"]
        self.assertEqual(len(allowlist), 4)
        self.assertEqual(sum(name.endswith(".json") for name in allowlist), 1)
        self.assertEqual(sum(name.endswith(".png") for name in allowlist), 3)
        self.assertFalse(any(name.endswith((".mp4", ".mov", ".mkv", ".wav")) for name in allowlist))
        self.assertEqual(self.contract["output"]["report_newline"], "LF")
        self.assertFalse(self.contract["output"]["overwrite_allowed"])

    def test_implementation_has_no_process_network_or_encoder_route(self) -> None:
        source_path = self.repo_root / audit.IMPLEMENTATION_RELATIVE_PATH
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("subprocess", imported)
        self.assertNotIn("socket", imported)
        self.assertNotIn("requests", imported)
        lowered = source.lower()
        self.assertNotIn("ffmpeg", lowered)
        self.assertNotIn("moviepy", lowered)


if __name__ == "__main__":
    unittest.main()
