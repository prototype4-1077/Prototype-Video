import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops

from pipeline.cartoon_gesture_atlas import (
    apply_gesture_pose,
    gesture_performance_plan,
    gesture_pose_amount,
    load_gesture_atlas_contract,
    prepare_gesture_sources,
)


class CartoonGestureAtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.atlas_path = cls.repo_root / "concept/style_frames/june_oxley_porch_gesture_atlas_v1.json"
        cls.cue_path = cls.repo_root / "concept/style_frames/june_golden_scene_gesture_cues_v1.json"
        cls.contract, cls.paths = load_gesture_atlas_contract(cls.atlas_path)
        cls.prepared = prepare_gesture_sources(
            cls.atlas_path,
            expected_plate_id="june_oxley_porch_hero_plate",
            expected_base_sha256="a6ed59b3ed26d4ac242828fb173386cd19796dd03ed21ed8dd871676b1ada908",
        )

    def test_contract_locks_two_anatomical_pose_sources(self):
        self.assertEqual(set(self.contract["poses"]), {"mug_lift", "pencil_hold"})
        self.assertEqual(self.contract["generation"]["cash_cost"], 0)
        self.assertFalse(self.contract["generation"]["paid_runtime_dependency"])
        self.assertTrue(self.paths["neutral"].is_file())
        self.assertEqual(len(self.paths["mug_lift"]), 3)
        self.assertEqual(len(self.paths["pencil_hold"]), 2)
        self.assertTrue(all(path.is_file() for state in ("mug_lift", "pencil_hold") for path in self.paths[state]))

    def test_gesture_plan_covers_exact_clock_and_all_states(self):
        metadata, plan = gesture_performance_plan(
            self.cue_path,
            expected_atlas_id=self.contract["atlas_id"],
        )
        self.assertEqual(metadata["frame_count"], 453)
        self.assertEqual(metadata["cue_count"], 5)
        self.assertEqual(metadata["states"], ["mug_lift", "neutral", "pencil_hold"])
        self.assertEqual(len(plan), 453)
        self.assertEqual(plan[0]["frame"], 1)
        self.assertEqual(plan[-1]["frame"], 453)

    def test_pose_amount_handles_lift_hold_and_return(self):
        self.assertEqual(
            gesture_pose_amount({"from_state": "neutral", "to_state": "mug_lift", "blend": 0.25}),
            ("mug_lift", 0.25),
        )
        self.assertEqual(
            gesture_pose_amount({"from_state": "mug_lift", "to_state": "mug_lift", "blend": 1.0}),
            ("mug_lift", 1.0),
        )
        self.assertEqual(
            gesture_pose_amount({"from_state": "pencil_hold", "to_state": "neutral", "blend": 0.75}),
            ("pencil_hold", 0.25),
        )

    def test_registered_pose_changes_only_local_plate_region(self):
        _, plan = gesture_performance_plan(self.cue_path, expected_atlas_id=self.contract["atlas_id"])
        entry = next(item for item in plan if item["to_state"] == "mug_lift" and item["blend"] == 1.0)
        with Image.open(self.paths["neutral"]) as source:
            base = source.convert("RGB")
        frame = base.copy()
        state, amount, origin = apply_gesture_pose(frame, self.prepared, entry)
        self.assertEqual(state, "mug_lift")
        self.assertEqual(amount, 1.0)
        self.assertEqual(origin, (626.0, 465.0))
        difference = ImageChops.difference(base, frame)
        self.assertIsNotNone(difference.getbbox())
        changed_box = difference.getbbox()
        patch_box = tuple(self.contract["poses"]["mug_lift"]["patch_box"])
        self.assertGreaterEqual(changed_box[0], patch_box[0])
        self.assertGreaterEqual(changed_box[1], patch_box[1])
        self.assertLessEqual(changed_box[2], patch_box[2])
        self.assertLessEqual(changed_box[3], patch_box[3])

    def test_registered_inbetweens_render_intermediate_mug_frame(self):
        _, plan = gesture_performance_plan(self.cue_path, expected_atlas_id=self.contract["atlas_id"])
        entry = next(
            item
            for item in plan
            if item["to_state"] == "mug_lift" and 0.2 < float(item["blend"]) < 0.8
        )
        with Image.open(self.paths["neutral"]) as source:
            frame = source.convert("RGB")
        state, amount, origin = apply_gesture_pose(frame, self.prepared, entry)
        self.assertEqual(state, "mug_lift")
        self.assertGreater(amount, 0.2)
        self.assertLess(amount, 0.8)
        self.assertIsNotNone(origin)
        self.assertEqual(frame.size, (1672, 941))

    def test_gesture_cues_reject_timeline_gap(self):
        payload = json.loads(self.cue_path.read_text(encoding="utf-8"))
        payload["cues"][2]["start"] += 0.1
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad-gesture-cues.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contiguous"):
                gesture_performance_plan(path, expected_atlas_id=self.contract["atlas_id"])


if __name__ == "__main__":
    unittest.main()
