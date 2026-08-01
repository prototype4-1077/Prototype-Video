from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image

from pipeline.cartoon_shot_sequence import (
    apply_shot_effects,
    camera_crop_box,
    load_multishot_contract,
    shot_for_frame,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "concept" / "style_frames" / "june_golden_scene_multishot_v1.json"


class CartoonShotSequenceTests(unittest.TestCase):
    def test_current_contract_loads_and_covers_exact_clock(self) -> None:
        contract, plates = load_multishot_contract(CONTRACT_PATH)
        self.assertEqual(contract["sequence_id"], "june_golden_scene_multishot_v1")
        self.assertEqual(contract["output"]["frame_count"], 453)
        self.assertEqual(len(contract["shots"]), 6)
        self.assertEqual(contract["shots"][0]["start_frame"], 1)
        self.assertEqual(contract["shots"][-1]["end_frame"], 453)
        self.assertEqual(set(plates), {"mug_held_insert", "ledger_insert"})
        self.assertTrue(all(path.is_file() for path in plates.values()))

    def test_contract_rejects_a_tampered_plate_hash(self) -> None:
        def digest(path: Path) -> str:
            if path.name == "june_oxley_mug_held_insert_v1.png":
                return "0" * 64
            return hashlib.sha256(path.read_bytes()).hexdigest()

        with patch("pipeline.cartoon_shot_sequence._sha256", side_effect=digest):
            with self.assertRaisesRegex(ValueError, "plate mug_held_insert hash does not match"):
                load_multishot_contract(CONTRACT_PATH)

    def test_contract_rejects_a_gap_in_the_edit(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["shots"] = copy.deepcopy(broken["shots"])
        broken["shots"][1]["start_frame"] = 52
        with patch("pipeline.cartoon_shot_sequence.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "contiguous"):
                load_multishot_contract(CONTRACT_PATH)

    def test_contract_rejects_a_meaningless_encode_quality_floor(self) -> None:
        broken = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        broken["encoded_quality_gate"]["minimum_review_frame_psnr_db"] = 12.0
        with patch("pipeline.cartoon_shot_sequence.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "quality gate"):
                load_multishot_contract(CONTRACT_PATH)

    def test_shot_lookup_resolves_every_cut_side(self) -> None:
        contract, _ = load_multishot_contract(CONTRACT_PATH)
        shots = contract["shots"]
        self.assertEqual(shot_for_frame(shots, 50)["id"], "GS010_HERO_SETUP_AND_MUG_LIFT")
        self.assertEqual(shot_for_frame(shots, 51)["id"], "GS020_MUG_CHIP_INSERT")
        self.assertEqual(shot_for_frame(shots, 392)["id"], "GS045_HERO_PENCIL_RETURN")
        self.assertEqual(shot_for_frame(shots, 393)["id"], "GS050_IDENTITY_LOCKED_COMPASSION_CLOSEUP")
        with self.assertRaisesRegex(ValueError, "not covered"):
            shot_for_frame(shots, 454)

    def test_camera_crop_is_bounded_and_preserves_delivery_shape(self) -> None:
        self.assertEqual(camera_crop_box((1920, 1080), (1920, 1080), 1.0, (0.5, 0.5)), (0, 0, 1920, 1080))
        left, top, right, bottom = camera_crop_box((1920, 1080), (1920, 1080), 1.5, (0.44, 0.335))
        self.assertEqual((right - left, bottom - top), (1280, 720))
        self.assertGreaterEqual(left, 0)
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(right, 1920)
        self.assertLessEqual(bottom, 1080)

    def test_procedural_insert_effects_are_deterministic(self) -> None:
        image = Image.new("RGB", (320, 180), (82, 58, 38))
        effects = {"steam": {"origin": [0.66, 0.3], "strength": 0.6}, "light_breathe": {"strength": 0.006}}
        first = apply_shot_effects(image, effects, 21, 30)
        second = apply_shot_effects(image, effects, 21, 30)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertNotEqual(first.tobytes(), image.tobytes())


if __name__ == "__main__":
    unittest.main()
