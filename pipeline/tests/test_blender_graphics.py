import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import blender_graphics
import storyboard


class BlenderGraphicsTests(unittest.TestCase):
    def _scene(self, kind):
        return {
            "text": f"A test narration for {kind}.",
            "duration": 1.0,
            "narrative_mode": "storyboard",
            "graphic_kind": kind,
            "graphic_backend": "blender_3d",
            "semantic_anchor": f"A physical {kind} mechanism explains the idea.",
            "visual_function": "mechanism",
            "symbol_family": "object_tool",
            "visual_revision": "test-3d-v1",
        }

    def test_all_nine_graphic_families_produce_valid_3d_plans(self):
        for index, kind in enumerate(blender_graphics.GRAPHIC_KINDS):
            scene = self._scene(kind)
            plan = blender_graphics.plan_for(
                {"graphic_backend": "blender_3d"},
                scene,
                index,
                ["ONE", "TWO", "THREE", "FOUR"],
            )
            blender_graphics.validate_plan(plan)
            self.assertEqual(plan["kind"], kind)
            self.assertEqual(plan["backend"], "blender_3d")
            self.assertEqual(plan["render"]["width"], storyboard.W)
            self.assertEqual(plan["render"]["height"], storyboard.H)
            self.assertEqual(plan["render"]["work_fps"], 15)
            self.assertEqual(plan["render"]["work_resolution_percentage"], 75)

    def test_scene_variant_is_deterministic_and_meaning_sensitive(self):
        scene = self._scene("path")
        first = blender_graphics.plan_for({}, scene, 2, ["A"])
        second = blender_graphics.plan_for({}, scene, 2, ["A"])
        changed = dict(scene, semantic_anchor="A different route changes the composition.")
        third = blender_graphics.plan_for({}, changed, 2, ["A"])
        self.assertEqual(first["seed"], second["seed"])
        self.assertNotEqual(first["seed"], third["seed"])

    def test_storyboard_records_successful_blender_backend(self):
        script = {
            "graphic_backend": "blender_3d",
            "scenes": [self._scene("evidence")],
        }
        evidence = {
            "passes": True,
            "active_region_ratio": 0.18,
            "frame_difference": 4.2,
        }
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "clip_00.mp4"

            def fake_render(_build, _script, _index, _labels):
                output.write_bytes(b"3" * 150_000)
                return {
                    "output": output,
                    "audit_path": Path(td) / "blender_graphic_00.json",
                    "plan": {
                        "schema_version": 1,
                        "variant": 4,
                    },
                }

            with mock.patch.object(
                storyboard.blender_graphics, "render_scene", side_effect=fake_render,
            ), mock.patch.object(
                storyboard.motion, "temporal_evidence", return_value=evidence,
            ):
                result = storyboard.render_scene(td, script, 0)

            self.assertEqual(result["graphic_backend"], "blender_3d")
            self.assertEqual(result["graphic_dimension"], "3d")
            self.assertEqual(result["graphic_variant"], 4)
            self.assertEqual(script["scenes"][0]["motion_source"], "blender_3d_storyboard")
            self.assertTrue(script["scenes"][0]["motion_verified"])

    def test_unknown_kind_is_rejected_before_blender_launch(self):
        scene = self._scene("unknown")
        with self.assertRaisesRegex(ValueError, "unsupported Blender graphic kind"):
            blender_graphics.plan_for({}, scene, 0, ["A"])

    def test_clip_scene_writes_to_proof_directory(self):
        script = {"scenes": [dict(self._scene("path"), keywords=["A", "B"])]}
        with tempfile.TemporaryDirectory() as td:
            build = Path(td) / "build"
            output_dir = Path(td) / "proof"
            build.mkdir()
            (build / "script.json").write_text(json.dumps(script), encoding="utf-8")
            with mock.patch.object(
                blender_graphics, "_invoke", side_effect=lambda _plan, output, **_: output,
            ) as invoke:
                output = blender_graphics.clip_scene(build, 0, output_dir)

            self.assertEqual(output, output_dir / "scene-01-path.mp4")
            self.assertEqual(invoke.call_args.args[0]["kind"], "path")

    def test_optimized_render_is_normalized_to_delivery_dimensions(self):
        plan = blender_graphics.plan_for(
            {}, self._scene("path"), 0, ["A", "B", "C", "D"],
        )
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "clip.mp4"

            def fake_run(command, **_kwargs):
                target = Path(command[-1])
                target.write_bytes(b"3" * 150_000)
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch.object(
                blender_graphics, "find_blender", return_value=sys.executable,
            ), mock.patch.object(
                blender_graphics.subprocess, "run", side_effect=fake_run,
            ) as run:
                result = blender_graphics._invoke(plan, output)

            self.assertEqual(result, output)
            self.assertTrue(output.exists())
            self.assertFalse(output.with_name("clip.blender.mp4").exists())
            ffmpeg_command = run.call_args_list[1].args[0]
            filters = ffmpeg_command[ffmpeg_command.index("-vf") + 1]
            self.assertIn("fps=30", filters)
            self.assertNotIn("setpts", filters)
            self.assertIn("scale=1080:608", filters)

    def test_cached_2d_fallback_is_reused_within_one_visual_revision(self):
        scene = self._scene("path")
        scene.update({
            "narrative_mode": "literal_graphic",
            "graphic_backend_requested": "blender_3d",
            "graphic_backend": "pil_2d",
            "graphic_dimension": "2d",
            "graphic_plan_version": blender_graphics.PLAN_VERSION,
            "graphic_backend_fallback_reason": "prior render failed",
            "storyboard_generated": True,
            "motion_evidence": {
                "passes": True,
                "active_region_ratio": 0.2,
                "frame_difference": 3.0,
            },
        })
        scene["clip_fingerprint"] = storyboard.motion.scene_visual_fingerprint(scene)
        script = {"graphic_backend": "blender_3d", "scenes": [scene]}
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "clip_00.mp4").write_bytes(b"2" * 150_000)
            with mock.patch.object(
                storyboard.blender_graphics, "render_scene",
            ) as render:
                result = storyboard.render_scene(td, script, 0)

            render.assert_not_called()
            self.assertTrue(result["cached"])
            self.assertEqual(result["graphic_backend"], "pil_2d")


if __name__ == "__main__":
    unittest.main()
