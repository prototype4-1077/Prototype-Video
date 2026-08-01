from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from pipeline.cartoon_golden_master import (
    SHOT_CLOCK,
    compose_plate_frame,
    load_master_contract,
    segment_for_frame,
    shot_for_frame,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/style_frames/june_golden_scene_master_v1.json"


class CartoonGoldenMasterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.plate_paths = load_master_contract(CONTRACT)

    def test_contract_locks_exact_seven_shot_1164_frame_clock(self) -> None:
        output = self.contract["output"]
        self.assertEqual(
            (output["width"], output["height"], output["fps"], output["frame_count"]),
            (1920, 1080, 30, 1164),
        )
        self.assertEqual(output["duration_seconds"], 38.8)
        self.assertEqual([shot["id"] for shot in self.contract["shots"]], list(SHOT_CLOCK))
        self.assertEqual(
            [shot["end_frame"] - shot["start_frame"] + 1 for shot in self.contract["shots"]],
            [129, 96, 171, 168, 114, 258, 228],
        )

    def test_every_master_frame_resolves_to_one_declared_source(self) -> None:
        shots = self.contract["shots"]
        for frame in range(1, 1165):
            shot = shot_for_frame(shots, frame)
            if shot["source"]["type"] == "plate_sequence":
                segment = segment_for_frame(shot["segments"], frame)
                self.assertIn(segment["plate_id"], self.plate_paths)
            else:
                self.assertEqual(shot["source"]["source_id"], shot["id"])
        with self.assertRaisesRegex(ValueError, "not covered"):
            shot_for_frame(shots, 1165)

    def test_rendered_motion_shots_are_one_to_one_and_never_retimed(self) -> None:
        for shot_id in ("GS030", "GS060", "GS070"):
            shot = next(shot for shot in self.contract["shots"] if shot["id"] == shot_id)
            source = self.contract["rendered_sources"][shot_id]
            output_frames = shot["end_frame"] - shot["start_frame"] + 1
            self.assertEqual(output_frames, source["frame_count"])
            self.assertEqual(shot["segments"], [])
        invariants = " ".join(self.contract["continuity_invariants"])
        self.assertIn("one-to-one", invariants)
        self.assertIn("no optical flow", invariants)

    def test_plate_shots_use_declared_hard_action_cuts(self) -> None:
        gs040 = shot_for_frame(self.contract["shots"], 500)
        self.assertEqual(
            [(segment["start_frame"], segment["end_frame"]) for segment in gs040["segments"]],
            [(397, 452), (453, 508), (509, 564)],
        )
        gs050 = shot_for_frame(self.contract["shots"], 600)
        self.assertEqual(gs050["minimum_post_dialogue_hold_frames"], 24)
        self.assertEqual(gs050["segments"][-1]["plate_id"], "gs050_compassion_end")
        self.assertEqual(gs050["segments"][-1]["end_frame"], 678)

    def test_plate_compositor_produces_full_hd_motion_and_distinct_action_cuts(self) -> None:
        gs010 = self.contract["shots"][0]["segments"][0]
        with Image.open(self.plate_paths["gs010_establishing"]) as plate:
            first = compose_plate_frame(plate.convert("RGB"), gs010, 1)
            last = compose_plate_frame(plate.convert("RGB"), gs010, 129)
        self.assertEqual(first.size, (1920, 1080))
        self.assertIsNotNone(ImageChops.difference(first, last).getbbox())

        gs040 = self.contract["shots"][3]
        before_segment = gs040["segments"][0]
        after_segment = gs040["segments"][1]
        with Image.open(self.plate_paths[before_segment["plate_id"]]) as source:
            before = compose_plate_frame(source.convert("RGB"), before_segment, 452)
        with Image.open(self.plate_paths[after_segment["plate_id"]]) as source:
            after = compose_plate_frame(source.convert("RGB"), after_segment, 453)
        self.assertIsNotNone(ImageChops.difference(before, after).getbbox())

    def test_contract_rejects_wrong_shot_span_and_tampered_plate(self) -> None:
        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        broken = copy.deepcopy(payload)
        broken["shots"][3]["end_frame"] = 565
        with patch("pipeline.cartoon_golden_master.json.loads", return_value=broken):
            with self.assertRaisesRegex(ValueError, "GS040"):
                load_master_contract(CONTRACT)

        original_digest = __import__("hashlib").sha256

        def digest(path: Path) -> str:
            if path.name == "june-golden-scene-gs020-style-target-v2.png":
                return "0" * 64
            return original_digest(path.read_bytes()).hexdigest()

        with patch("pipeline.cartoon_shot_sequence._sha256", side_effect=digest):
            with self.assertRaisesRegex(ValueError, "gs020_mug_chip hash does not match"):
                load_master_contract(CONTRACT)


if __name__ == "__main__":
    unittest.main()
