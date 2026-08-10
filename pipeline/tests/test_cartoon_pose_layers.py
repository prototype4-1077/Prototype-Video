from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from pipeline.cartoon_pose_layers import (
    directional_smear,
    load_pose_layer_contract,
    registered_pose_layer,
    registration_offsets,
    timeline_entry_for_frame,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "concept" / "style_frames" / "june_golden_scene_gs030_layered_stand_v1.json"


class CartoonPoseLayerTests(unittest.TestCase):
    def test_current_contract_loads_five_registered_drawings(self) -> None:
        contract, background, poses = load_pose_layer_contract(CONTRACT_PATH)
        self.assertEqual(contract["performance_id"], "june_golden_scene_gs030_layered_stand_v1")
        self.assertEqual(contract["output"]["frame_count"], 171)
        self.assertEqual(len(poses), 5)
        self.assertTrue(background.is_file())
        self.assertTrue(all(path.is_file() for path in poses.values()))
        self.assertEqual(contract["timeline"][0]["start_frame"], 1)
        self.assertEqual(contract["timeline"][-1]["end_frame"], 171)

    def test_contract_rejects_tampered_foreground_hash(self) -> None:
        def digest(path: Path) -> str:
            if path.name == "june_gs030_pose_50_foreground_v1.png":
                return "0" * 64
            return hashlib.sha256(path.read_bytes()).hexdigest()

        with patch("pipeline.cartoon_pose_layers._sha256", side_effect=digest):
            with self.assertRaisesRegex(ValueError, "foreground POSE_50_WEIGHT_TRANSFER hash does not match"):
                load_pose_layer_contract(CONTRACT_PATH)

    def test_contract_rejects_timeline_gap(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["timeline"] = copy.deepcopy(broken["timeline"])
        broken["timeline"][1]["start_frame"] = 72
        with patch("pipeline.cartoon_pose_layers.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "contiguous"):
                load_pose_layer_contract(CONTRACT_PATH)

    def test_contract_rejects_loose_contact_gate(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["contact_registration"]["maximum_contact_drift_px_source"] = 3.0
        with patch("pipeline.cartoon_pose_layers.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "two source pixels"):
                load_pose_layer_contract(CONTRACT_PATH)

    def test_timeline_lookup_resolves_pose_and_smear_boundaries(self) -> None:
        contract, _, _ = load_pose_layer_contract(CONTRACT_PATH)
        self.assertEqual(timeline_entry_for_frame(contract["timeline"], 70)["type"], "pose")
        self.assertEqual(timeline_entry_for_frame(contract["timeline"], 71)["type"], "smear")
        self.assertEqual(timeline_entry_for_frame(contract["timeline"], 72)["pose_id"], "POSE_25_LEVERAGE")
        self.assertEqual(timeline_entry_for_frame(contract["timeline"], 95)["type"], "smear")
        self.assertEqual(timeline_entry_for_frame(contract["timeline"], 96)["pose_id"], "POSE_100_STANDING")
        with self.assertRaisesRegex(ValueError, "not covered"):
            timeline_entry_for_frame(contract["timeline"], 172)

    def test_every_pose_correction_stays_bounded_and_locks_contacts(self) -> None:
        contract, _, _ = load_pose_layer_contract(CONTRACT_PATH)
        registration = contract["contact_registration"]
        target_left = tuple(registration["target_left_support_boot"])
        target_right = tuple(registration["target_right_boot"])
        maximum = float(registration["right_leg_warp"]["maximum_correction_px"])
        for pose in contract["poses"]:
            offsets = registration_offsets(pose, registration)
            source_left = tuple(pose["source_contacts"]["left_support_boot"])
            source_right = tuple(pose["source_contacts"]["right_boot"])
            translation = offsets["translation"]
            correction = offsets["right_leg_correction"]
            self.assertEqual(
                (source_left[0] + translation[0], source_left[1] + translation[1]),
                target_left,
            )
            self.assertEqual(
                (
                    source_right[0] + translation[0] + correction[0],
                    source_right[1] + translation[1] + correction[1],
                ),
                target_right,
            )
            self.assertLessEqual((correction[0] ** 2 + correction[1] ** 2) ** 0.5, maximum)

    def test_registered_layer_and_smear_are_deterministic(self) -> None:
        image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((28, 12, 68, 80), fill=(68, 91, 112, 255))
        pose = {
            "id": "TEST",
            "source_contacts": {"left_support_boot": [38.0, 80.0], "right_boot": [60.0, 76.0]},
            "steam_origin": [60.0, 20.0],
        }
        registration = {
            "target_left_support_boot": [40.0, 82.0],
            "target_right_boot": [64.0, 78.0],
            "right_leg_warp": {
                "x_falloff_start": 48.0,
                "x_falloff_end": 58.0,
                "y_falloff_start": 42.0,
                "y_falloff_end": 70.0,
                "maximum_correction_px": 10.0,
            },
        }
        first, first_report = registered_pose_layer(image, pose, registration)
        second, second_report = registered_pose_layer(image, pose, registration)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertEqual(first_report, second_report)
        smear_a = directional_smear(first, 8)
        smear_b = directional_smear(first, 8)
        self.assertEqual(smear_a.tobytes(), smear_b.tobytes())
        self.assertNotEqual(first.tobytes(), smear_a.tobytes())


if __name__ == "__main__":
    unittest.main()
