import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pipeline.blender import render_vertical_slice as blender_studio
from pipeline.cartoon_vertical_slice import _render_frames, compile_plan, validate_config


EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "june-porch-vertical-slice.json"


class _FakeLocation:
    def __init__(self):
        self.z = 0.0


class _FakeBone:
    def __init__(self):
        self.rotation_euler = [0.0, 0.0, 0.0]
        self.location = _FakeLocation()
        self.keyframes = []

    def keyframe_insert(self, *, data_path, frame):
        self.keyframes.append((data_path, int(frame)))


class _FakeTracks(list):
    def remove(self, track):
        super().remove(track)


class _FakeRig:
    def __init__(self):
        names = (
            "torso", "head", "upper_arm.L", "forearm.L", "hand.L",
            "upper_arm.R", "forearm.R", "hand.R",
            "thigh.L", "shin.L", "thigh.R", "shin.R",
        )
        self.pose = type("Pose", (), {"bones": {name: _FakeBone() for name in names}})()
        self.animation_data = type("AnimationData", (), {"nla_tracks": _FakeTracks(), "action": None})()

    def animation_data_create(self):
        return self.animation_data


class CartoonVerticalSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_compiles_contiguous_youtube_proof(self):
        plan = compile_plan(self.config, profile="youtube", quality="proof")
        self.assertEqual(plan["render"]["width"], 480)
        self.assertEqual(plan["render"]["height"], 270)
        self.assertEqual(plan["render"]["fps"], 30)
        self.assertEqual(plan["frame_end"], 390)
        self.assertEqual(plan["shots"][0]["frame_start"], 1)
        for previous, current in zip(plan["shots"], plan["shots"][1:]):
            self.assertEqual(current["frame_start"], previous["frame_end"] + 1)
        self.assertEqual(plan["mouth_cues"], [
            {
                "frame_start": 1,
                "frame_end": 390,
                "shape": "X",
                "start": 0.0,
                "end": 13.0,
            }
        ])

    def test_portrait_production_uses_shared_frame_clock(self):
        plan = compile_plan(self.config, profile="portrait", quality="production")
        self.assertEqual((plan["render"]["width"], plan["render"]["height"]), (1080, 1920))
        self.assertEqual(plan["render"]["fps"], 30)
        self.assertEqual(plan["frame_end"], 390)
        self.assertEqual(plan["render"]["engine"], "BLENDER_EEVEE_NEXT")

    def test_june_must_be_selected_explicitly(self):
        invalid = copy.deepcopy(self.config)
        invalid["character"]["id"] = "generic_host"
        with self.assertRaisesRegex(ValueError, "june_oxley"):
            validate_config(invalid)

    def test_three_shot_minimum_is_enforced(self):
        invalid = copy.deepcopy(self.config)
        invalid["shots"] = invalid["shots"][:2]
        with self.assertRaisesRegex(ValueError, "at least three"):
            validate_config(invalid)

    def test_eight_authored_shots_compile_and_drive_every_rig_section(self):
        expanded = copy.deepcopy(self.config)
        cameras = ("wide", "medium", "close")
        gestures = (
            "open hand", "measured point", "lean and nod", "small left shrug",
            "two-handed welcome", "thumb toward the gate", "quiet palm turn", "mug-sized circle",
        )
        moves = (
            "slow push", "gentle drift", "subtle push", "locked",
            "pan left", "pan right", "orbit-right reveal", "tilt up",
        )
        expanded["shots"] = [
            {
                "id": f"authored_{index}",
                "camera": cameras[index % len(cameras)],
                "duration_seconds": 1.0,
                "line": f"Line {index}",
                "performance": f"June performs beat {index} and looks {'left' if index % 2 else 'right'}.",
                "gesture": gestures[index],
                "camera_move": moves[index],
            }
            for index in range(8)
        ]
        plan = compile_plan(expanded, profile="youtube", quality="proof")
        self.assertEqual(len(plan["shots"]), 8)
        self.assertEqual(plan["frame_end"], 240)
        self.assertEqual(plan["shots"][6]["camera_move"], "orbit-right reveal")

        rig = _FakeRig()

        def execute_action(_bpy, _rig, _name, animator):
            animator()

        with mock.patch.object(blender_studio, "_stash_action", side_effect=execute_action):
            blender_studio._animate_rig(mock.sentinel.bpy, rig, plan)

        midpoints = {
            (int(shot["frame_start"]) + int(shot["frame_end"])) // 2
            for shot in plan["shots"]
        }
        head_frames = {frame for path, frame in rig.pose.bones["head"].keyframes if path == "rotation_euler"}
        self.assertTrue(midpoints.issubset(head_frames))
        for name in (
            "upper_arm.L", "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R",
            "thigh.L", "shin.L", "thigh.R", "shin.R",
        ):
            gesture_frames = {frame for path, frame in rig.pose.bones[name].keyframes if path == "rotation_euler"}
            self.assertTrue(midpoints.issubset(gesture_frames), name)

    def test_free_form_direction_is_deterministic_and_changes_performance(self):
        authored = {
            "camera": "medium",
            "performance": "June leans back, glances left, then lets the joke land.",
            "gesture": "draws a mug-sized circle with his right hand",
            "camera_move": "orbit-right reveal",
        }
        repeat = copy.deepcopy(authored)
        default = {"camera": "medium", "performance": "settles", "gesture": "open hand", "camera_move": "locked"}

        self.assertEqual(
            blender_studio._head_performance_poses(authored, 5),
            blender_studio._head_performance_poses(repeat, 5),
        )
        self.assertEqual(blender_studio._gesture_pose(authored, 5), blender_studio._gesture_pose(repeat, 5))
        self.assertNotEqual(blender_studio._gesture_pose(authored, 5), blender_studio._gesture_pose(default, 5))
        self.assertEqual(blender_studio._body_performance_pose(authored, 5), (-0.005, 2.4))
        self.assertEqual(
            blender_studio._leg_performance_pose(
                {"gesture": "seated to stand with mug", "performance": "weight forward"}, 0
            ),
            {"thigh.L": -24.0, "shin.L": 31.0, "thigh.R": -22.0, "shin.R": 29.0},
        )
        authored_move = blender_studio._camera_motion_delta(authored, 5)
        self.assertEqual(authored_move["target"], (0.0, 0.0, 0.0))
        self.assertAlmostEqual(authored_move["location"][0], 0.24)
        self.assertAlmostEqual(authored_move["location"][1], 0.056)
        self.assertEqual(
            blender_studio._camera_motion_delta(default, 5),
            {"location": (0.0, 0.0, 0.0), "target": (0.0, 0.0, 0.0)},
        )

    def test_blender_python_failures_propagate_to_the_caller(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch(
            "pipeline.cartoon_vertical_slice.subprocess.run"
        ) as run:
            _render_frames("blender", Path("plan.json"), Path(temp_dir) / "frames")
        command = run.call_args.args[0]
        self.assertIn("--python-exit-code", command)
        self.assertEqual(command[command.index("--python-exit-code") + 1], "1")
        self.assertTrue(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
