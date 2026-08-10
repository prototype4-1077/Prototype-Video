from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from pipeline.cartoon_deformable_rig import (
    DeformableRigRenderer,
    EXPECTED_ACTIONS,
    load_deformable_rig_contract,
    solve_pose_state,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/characters/june_oxley_deformable_rig_v1.json"


class CartoonDeformableRigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.assets = load_deformable_rig_contract(CONTRACT)

    def test_contract_locks_exact_zero_cash_production_clock(self) -> None:
        output = self.contract["output"]
        self.assertEqual(
            (output["width"], output["height"], output["fps"], output["frame_count"], output["duration_seconds"]),
            (1920, 1080, 30, 360, 12.0),
        )
        self.assertEqual(self.contract["cash_cost"], 0)
        self.assertFalse(self.contract["paid_runtime_dependency"])
        identity = self.contract["identity_invariants"]
        self.assertEqual(identity["sex"], "male")
        self.assertEqual(identity["build"], "lean_wiry")
        self.assertEqual(identity["facial_hair"], "trimmed_white_beard_and_mustache")
        self.assertIn("female", identity["prohibited_interpretations"])

    def test_contract_covers_all_five_required_body_actions(self) -> None:
        self.assertEqual({action["id"] for action in self.contract["actions"]}, EXPECTED_ACTIONS)
        self.assertEqual([(action["start_frame"], action["end_frame"]) for action in self.contract["actions"]], [
            (31, 90), (91, 150), (151, 210), (211, 270), (271, 330)
        ])
        self.assertEqual([layer["id"] for layer in self.contract["layers"]], ["body_base", "right_arm_foreground"])
        self.assertEqual(self.contract["layers"][1]["depth"], 1)

    def test_source_art_background_and_alpha_provenance_are_hash_pinned(self) -> None:
        self.assertEqual(set(self.assets), {"source_art", "alpha_source", "background"})
        self.assertTrue(all(path.is_file() for path in self.assets.values()))
        self.assertEqual(self.contract["source_art"]["mode"], "RGBA")
        self.assertFalse(self.contract["source_art"]["alpha_derivation"]["runtime_required"])

    def test_pose_solver_keeps_both_feet_pinned_and_moves_required_landmarks(self) -> None:
        for frame in range(1, 361):
            state = solve_pose_state(self.contract, frame)
            self.assertEqual(state["deltas"]["screen_left_foot"], (0.0, 0.0))
            self.assertEqual(state["deltas"]["screen_right_foot"], (0.0, 0.0))
        reach = solve_pose_state(self.contract, 165)
        sit = solve_pose_state(self.contract, 270)
        self.assertGreater(reach["deltas"]["screen_right_hand"][0], 180.0)
        self.assertLess(reach["deltas"]["screen_right_hand"][1], -170.0)
        self.assertGreater(sit["deltas"]["root"][1], 115.0)

    def test_pose_solver_is_continuous_at_every_frame_boundary(self) -> None:
        nodes = [node["id"] for node in self.contract["skeleton"]["nodes"]]
        previous = solve_pose_state(self.contract, 1)["deltas"]
        maximum_step = 0.0
        for frame in range(2, 361):
            current = solve_pose_state(self.contract, frame)["deltas"]
            maximum_step = max(maximum_step, max(
                ((current[node][0] - previous[node][0]) ** 2 + (current[node][1] - previous[node][1]) ** 2) ** 0.5
                for node in nodes
            ))
            previous = current
        # The source is placed at 1000/1672 scale in the 1080p master, so a
        # 13-source-pixel ceiling remains below the eight-output-pixel gate.
        self.assertLess(maximum_step, 13.0)

    def test_draft_renderer_produces_continuous_rgba_composite(self) -> None:
        renderer = DeformableRigRenderer(self.contract, self.assets, render_scale=0.125)
        neutral, neutral_metrics = renderer.render_frame(1)
        reach, reach_metrics = renderer.render_frame(165)
        sit, sit_metrics = renderer.render_frame(270)
        self.assertEqual(neutral.shape, (135, 240, 3))
        self.assertEqual(reach.shape, neutral.shape)
        self.assertEqual(sit.shape, neutral.shape)
        self.assertGreater(abs(reach_metrics["landmarks"]["screen_right_hand"][0] - neutral_metrics["landmarks"]["screen_right_hand"][0]), 10.0)
        self.assertGreater(sit_metrics["landmarks"]["root"][1] - neutral_metrics["landmarks"]["root"][1], 8.0)
        self.assertGreater(neutral_metrics["alpha_area_ratio"], 0.9)

    def test_contract_rejects_tampered_source_and_missing_action(self) -> None:
        path = REPO_ROOT / "build" / "broken-deformable-rig.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            broken = copy.deepcopy(self.contract)
            broken["source_art"]["sha256"] = "0" * 64
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_deformable_rig_contract(path)
            broken = copy.deepcopy(self.contract)
            broken["actions"] = broken["actions"][:-1]
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "action coverage"):
                load_deformable_rig_contract(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
