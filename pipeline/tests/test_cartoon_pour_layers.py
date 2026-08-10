from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from pipeline.cartoon_pour_layers import (
    directional_smear,
    liquid_state,
    load_pour_layer_contract,
    registered_pose_layer,
    registration_offset,
    render_liquid_layer,
    timeline_entry_for_frame,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "concept" / "style_frames" / "june_golden_scene_gs060_layered_pour_v1.json"


class CartoonPourLayerTests(unittest.TestCase):
    def test_current_contract_loads_six_registered_drawings_and_exact_clock(self) -> None:
        contract, background, poses = load_pour_layer_contract(CONTRACT_PATH)
        self.assertEqual(contract["performance_id"], "june_golden_scene_gs060_layered_pour_v1")
        self.assertEqual(contract["output"]["frame_count"], 258)
        self.assertEqual(contract["output"]["duration_seconds"], 8.6)
        self.assertEqual(len(poses), 6)
        self.assertTrue(background.is_file())
        self.assertTrue(all(path.is_file() for path in poses.values()))
        self.assertEqual(contract["timeline"][0]["start_frame"], 1)
        self.assertEqual(contract["timeline"][-1]["end_frame"], 258)
        self.assertFalse(contract["liquid_reference"]["runtime_consumed"])

    def test_contract_rejects_tampered_foreground_hash(self) -> None:
        def digest(path: Path) -> str:
            if path.name == "june_gs060_pose_70_foreground_v1.png":
                return "0" * 64
            return hashlib.sha256(path.read_bytes()).hexdigest()

        with patch("pipeline.cartoon_pour_layers._sha256", side_effect=digest):
            with self.assertRaisesRegex(ValueError, "foreground POSE_70_FULL_TILT hash does not match"):
                load_pour_layer_contract(CONTRACT_PATH)

    def test_contract_rejects_timeline_gap(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["timeline"] = copy.deepcopy(broken["timeline"])
        broken["timeline"][1]["start_frame"] = 32
        with patch("pipeline.cartoon_pour_layers.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "contiguous"):
                load_pour_layer_contract(CONTRACT_PATH)

    def test_contract_rejects_landing_outside_mug(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["liquid"] = copy.deepcopy(broken["liquid"])
        broken["liquid"]["landing_point"] = [1070.0, 700.0]
        with patch("pipeline.cartoon_pour_layers.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "safely inside"):
                load_pour_layer_contract(CONTRACT_PATH)

    def test_contract_retains_honest_support_foot_exception(self) -> None:
        contract, _, _ = load_pour_layer_contract(CONTRACT_PATH)
        visibility = contract["visibility_audit"]
        self.assertFalse(visibility["support_foot"])
        self.assertIn("GS030", visibility["support_foot_remediation"])
        self.assertIn("false support-foot visibility claim", contract["prohibited_methods"])

    def test_timeline_lookup_covers_forward_pour_and_reverse_set_down(self) -> None:
        contract, _, _ = load_pour_layer_contract(CONTRACT_PATH)
        timeline = contract["timeline"]
        self.assertEqual(timeline_entry_for_frame(timeline, 30)["pose_id"], "POSE_00_PENCIL_POISED")
        self.assertEqual(timeline_entry_for_frame(timeline, 31)["type"], "smear")
        self.assertEqual(timeline_entry_for_frame(timeline, 128)["pose_id"], "POSE_70_FULL_TILT")
        self.assertEqual(timeline_entry_for_frame(timeline, 185)["to_pose_id"], "POSE_55_PRE_POUR")
        self.assertEqual(timeline_entry_for_frame(timeline, 230)["to_pose_id"], "POSE_15_PENCIL_DOWN")
        self.assertEqual(timeline_entry_for_frame(timeline, 258)["pose_id"], "POSE_15_PENCIL_DOWN")
        with self.assertRaisesRegex(ValueError, "not covered"):
            timeline_entry_for_frame(timeline, 259)

    def test_every_pose_registers_mug_inside_translation_bound(self) -> None:
        contract, _, paths = load_pour_layer_contract(CONTRACT_PATH)
        registration = contract["contact_registration"]
        target = tuple(registration["target_mug_rim_center"])
        for pose in contract["poses"]:
            dx, dy = registration_offset(pose, registration)
            self.assertLessEqual((dx * dx + dy * dy) ** 0.5, registration["maximum_translation_px_source"])
            with Image.open(paths[pose["id"]]) as source:
                registered, report = registered_pose_layer(source, pose, registration)
            self.assertEqual(report["mug_rim_residual_px_source"], 0.0)
            self.assertEqual(tuple(report["transformed_contacts"]["mug_rim_center"]), target)
            registered.close()

    def test_pre_lift_drawings_keep_the_pot_grounded_without_teleporting(self) -> None:
        contract, _, paths = load_pour_layer_contract(CONTRACT_PATH)
        registration = contract["contact_registration"]
        pot_gate = registration["grounded_pot_contact"]
        target_x, target_y = pot_gate["target_registered_point"]
        self.assertEqual(pot_gate["pose_ids"], [pose["id"] for pose in contract["poses"][:3]])
        residuals = []
        for pose in contract["poses"][:3]:
            with Image.open(paths[pose["id"]]) as source:
                registered, report = registered_pose_layer(source, pose, registration)
            point_x, point_y = report["transformed_contacts"]["pot_table_contact"]
            residuals.append(((point_x - target_x) ** 2 + (point_y - target_y) ** 2) ** 0.5)
            registered.close()
        self.assertAlmostEqual(max(residuals), 20.396078, places=5)
        self.assertLessEqual(max(residuals), pot_gate["maximum_residual_px_source"])

    def test_contract_rejects_missing_pre_lift_pot_contact(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["poses"] = copy.deepcopy(broken["poses"])
        del broken["poses"][1]["source_contacts"]["pot_table_contact"]
        with patch("pipeline.cartoon_pour_layers.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "pot-table contact"):
                load_pour_layer_contract(CONTRACT_PATH)

    def test_liquid_state_has_authored_onset_hold_taper_and_cutoff(self) -> None:
        contract, _, _ = load_pour_layer_contract(CONTRACT_PATH)
        liquid = contract["liquid"]
        self.assertEqual(liquid_state(liquid, 127)["phase"], "none")
        self.assertEqual(liquid_state(liquid, 128)["phase"], "onset")
        self.assertFalse(liquid_state(liquid, 128)["connected"])
        self.assertTrue(liquid_state(liquid, 135)["connected"])
        self.assertEqual(liquid_state(liquid, 136)["phase"], "continuous")
        self.assertEqual(liquid_state(liquid, 176)["phase"], "continuous")
        self.assertTrue(liquid_state(liquid, 177)["connected"])
        self.assertTrue(liquid_state(liquid, 184)["droplet_mode"])
        self.assertEqual(liquid_state(liquid, 185)["phase"], "none")

    def test_liquid_is_deterministic_starts_at_spout_and_renders_zero_spill(self) -> None:
        contract, _, _ = load_pour_layer_contract(CONTRACT_PATH)
        liquid = contract["liquid"]
        first, first_report = render_liquid_layer(liquid, 156, (1672, 941))
        second, second_report = render_liquid_layer(liquid, 156, (1672, 941))
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertEqual(first_report, second_report)
        self.assertEqual(first_report["spout_start_error_px_source"], 0.0)
        self.assertEqual(first_report["rendered_spill_pixels_source"], 0)
        self.assertLess(first_report["landing_ellipse_value"], 0.8)
        alpha = np.asarray(first.getchannel("A"))
        spout_x, spout_y = (int(value) for value in liquid["registered_spout_tip"])
        self.assertGreater(int(alpha[spout_y, spout_x]), 0)
        self.assertGreater(int(np.count_nonzero(alpha)), 300)

    def test_onset_partial_stream_does_not_teleport_to_mug(self) -> None:
        contract, _, _ = load_pour_layer_contract(CONTRACT_PATH)
        liquid = contract["liquid"]
        early, early_report = render_liquid_layer(liquid, 128, (1672, 941))
        connected, connected_report = render_liquid_layer(liquid, 135, (1672, 941))
        early_alpha = np.asarray(early.getchannel("A"))
        connected_alpha = np.asarray(connected.getchannel("A"))
        self.assertFalse(early_report["connected"])
        self.assertTrue(connected_report["connected"])
        self.assertLess(np.nonzero(early_alpha)[0].max(), 640)
        self.assertGreater(np.nonzero(connected_alpha)[0].max(), 690)

    def test_directional_smear_is_deterministic_and_not_a_dissolve(self) -> None:
        image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((24, 16, 72, 82), radius=9, fill=(78, 98, 116, 255))
        first = directional_smear(image, [12, -3])
        second = directional_smear(image, [12, -3])
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertNotEqual(image.tobytes(), first.tobytes())
        with self.assertRaisesRegex(ValueError, "eighteen"):
            directional_smear(image, [19, 0])


if __name__ == "__main__":
    unittest.main()
