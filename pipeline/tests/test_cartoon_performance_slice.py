import copy
import json
from pathlib import Path
import unittest

from pipeline.cartoon_performance_slice import (
    PERFORMANCE_SLICE_CLASSIFICATION,
    _pose_timing,
    load_performance_spec,
    performance_caption_events,
    render_performance_slice,
    validate_key_pose_timing,
)


ROOT = Path(__file__).resolve().parents[2]
SCENE_PATH = ROOT / "examples" / "june-golden-scene-twelve-dollar-mug.json"
MANIFEST_PATH = ROOT / "concept" / "style_frames" / "june_golden_scene_performance_slice_v1.json"


class CartoonPerformanceSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = json.loads(SCENE_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_pins_all_nine_key_poses_and_canonical_identity(self):
        scene, manifest, resolved = load_performance_spec(SCENE_PATH, MANIFEST_PATH)
        self.assertEqual(scene["production"], manifest["production"])
        self.assertEqual(list(resolved), ["GS030", "GS040", "GS050"])
        self.assertEqual(sum(len(paths) for paths in resolved.values()), 9)
        self.assertTrue(all(path.is_file() for paths in resolved.values() for path in paths))
        self.assertEqual(manifest["classification"], PERFORMANCE_SLICE_CLASSIFICATION)
        self.assertFalse(manifest["generator"]["paid_runtime_dependency"])

    def test_slice_is_exactly_453_frames_on_the_shared_clock(self):
        self.assertEqual(self.manifest["fps"], 30)
        self.assertEqual(self.manifest["duration_seconds"], 15.1)
        self.assertEqual(self.manifest["frame_count"], 453)
        self.assertEqual(
            [shot["frame_count"] for shot in self.manifest["shots"]],
            [171, 168, 114],
        )
        self.assertEqual(sum(shot["frame_count"] for shot in self.manifest["shots"]), 453)
        self.assertEqual(
            sum(float(shot["duration_seconds"]) for shot in self.manifest["shots"]),
            15.1,
        )

    def test_captions_are_shifted_into_the_slice_clock(self):
        events = performance_caption_events(self.scene, self.manifest)
        self.assertTrue(events)
        self.assertGreaterEqual(events[0]["start"], 0)
        self.assertLessEqual(events[-1]["end"], 15.1)
        self.assertTrue(all(event["start"] < event["end"] for event in events))
        text = " ".join(event["text"] for event in events)
        self.assertIn("Three years later", text)
        self.assertIn("watched his hand shake", text)
        self.assertNotIn("Keeping score", text)

    def test_missing_or_duplicate_key_pose_timing_is_rejected(self):
        missing = copy.deepcopy(self.manifest["shots"][0])
        missing["keyframes"].pop(1)
        with self.assertRaisesRegex(ValueError, "start, mid, end"):
            validate_key_pose_timing(missing)

        duplicate = copy.deepcopy(self.manifest["shots"][0])
        duplicate["keyframes"][1]["frame"] = 0
        with self.assertRaisesRegex(ValueError, "unique and increasing"):
            validate_key_pose_timing(duplicate)

    def test_accelerated_pose_animation_preserves_every_shot_frame_budget(self):
        for shot in self.manifest["shots"]:
            timing = _pose_timing(shot)
            self.assertEqual(len(timing), 5)
            self.assertTrue(all(frames > 0 for frames in timing))
            self.assertEqual(sum(timing), shot["frame_count"])

    def test_unknown_render_mode_fails_before_external_tools_are_needed(self):
        with self.assertRaisesRegex(ValueError, "render mode"):
            render_performance_slice(
                SCENE_PATH,
                MANIFEST_PATH,
                audio_source="missing.wav",
                output_dir="unused",
                mode="teleport",
            )


if __name__ == "__main__":
    unittest.main()
