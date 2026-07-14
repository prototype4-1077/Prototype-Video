import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import motion


class MotionBudgetTests(unittest.TestCase):
    def test_pan_and_zoom_remain_static(self):
        for mode in ("pan", "zoom", "ken_burns", "static"):
            self.assertEqual(motion.motion_kind({"motion_mode": mode}), motion.STATIC)

    def test_depth_keyframes_and_hero_are_animated(self):
        self.assertEqual(
            motion.motion_kind({"motion_mode": "depth"}), motion.ANIMATED,
        )
        self.assertEqual(
            motion.motion_kind({"motion_mode": "keyframes"}), motion.ANIMATED,
        )
        self.assertEqual(motion.motion_kind({"hero": True}), motion.ANIMATED)

    def test_literal_search_defaults_to_true_video(self):
        self.assertEqual(
            motion.motion_kind({"query": "hands writing in notebook"}), motion.VIDEO,
        )

    def test_budget_is_calculated_by_duration_not_scene_count(self):
        script = {
            "max_still_source_ratio": .35,
            "scenes": [
                {"duration": 3.5, "motion_kind": motion.ANIMATED},
                {"duration": 6.5, "motion_kind": motion.VIDEO},
            ],
        }
        result = motion.validate_budget(script)
        self.assertAlmostEqual(result.still_source_ratio, .35)
        self.assertAlmostEqual(result.video_ratio, .65)

    def test_animated_stills_count_in_full_toward_the_still_cap(self):
        script = {
            "max_still_source_ratio": .35,
            "scenes": [
                {"duration": 6.5, "motion_kind": motion.ANIMATED},
                {"duration": 3.5, "motion_kind": motion.VIDEO},
            ],
        }
        with self.assertRaisesRegex(
                motion.MotionBudgetError, "animated stills count toward this cap"):
            motion.validate_budget(script)

    def test_budget_rejects_even_one_long_static_scene(self):
        script = {
            "max_still_source_ratio": .35,
            "scenes": [
                {"duration": 5, "motion_kind": motion.STATIC},
                {"duration": 5, "motion_kind": motion.VIDEO},
                {"duration": 1, "motion_kind": motion.ANIMATED},
            ],
        }
        with self.assertRaisesRegex(motion.MotionBudgetError, "still-derived shots are"):
            motion.validate_budget(script)

    def test_defaults_upgrade_explicit_static_stills_but_keep_video_sources(self):
        script = {
            "scenes": [
                {"duration": 1, "source_image": "still.png",
                 "motion_mode": "pan", "motion_kind": motion.STATIC},
                {"duration": 1, "query": "walking", "motion_kind": motion.VIDEO},
                {"duration": 1, "hero": True},
            ],
        }
        self.assertTrue(motion.apply_motion_defaults(script))
        self.assertEqual(script["max_still_source_ratio"], .35)
        self.assertEqual(script["scenes"][0]["motion_kind"], motion.ANIMATED)
        self.assertEqual(script["scenes"][0]["motion_mode"], "cinemagraph")
        self.assertEqual(script["scenes"][1]["motion_kind"], motion.VIDEO)
        self.assertEqual(script["scenes"][2]["motion_kind"], motion.ANIMATED)

    def test_true_motion_requires_temporal_verification(self):
        script = {
            "scenes": [
                {"duration": 2, "motion_kind": motion.VIDEO},
                {"duration": 1, "motion_kind": motion.ANIMATED},
            ],
        }
        with self.assertRaisesRegex(
                motion.MotionBudgetError, "lack temporal verification"):
            motion.validate_video_evidence(script)
        script["scenes"][0]["motion_verified"] = True
        self.assertTrue(motion.validate_video_evidence(script))

    def test_recipe_inference_follows_the_literal_action(self):
        self.assertEqual(motion.infer_recipe({"text": "The seed opens under soil."}),
                         "organic")
        self.assertEqual(motion.infer_recipe({"text": "She watches herself in a mirror."}),
                         "reflection")
        self.assertEqual(motion.infer_recipe({"text": "A phone records the room."}),
                         "screen")


class MotionRenderTests(unittest.TestCase):
    @unittest.skipUnless(__import__("importlib").util.find_spec("cv2"),
                         "OpenCV is installed by pipeline requirements")
    def test_depth_animation_is_a_real_band_sized_video(self):
        with tempfile.TemporaryDirectory() as td:
            source = os.path.join(td, "source.png")
            output = os.path.join(td, "motion.mp4")
            image = Image.new("RGB", (480, 270), (58, 66, 72))
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 150, 480, 270), fill=(78, 61, 45))
            draw.ellipse((175, 45, 305, 240), fill=(188, 155, 112))
            image.save(source)
            yy, xx = np.mgrid[0:270, 0:480]
            depth = np.exp(-(((xx - 240) / 120) ** 2 + ((yy - 145) / 125) ** 2))
            motion.render_depth_animation(
                source, depth.astype(np.float32), .3, output,
                recipe="human", strength=.7, seed=4,
            )
            probe = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,nb_frames",
                "-of", "csv=p=0", output,
            ], check=True, capture_output=True, text=True)
            width, height, frames = probe.stdout.strip().split(",")
            self.assertEqual((int(width), int(height)),
                             (motion.W, motion.H))
            self.assertGreaterEqual(int(frames), 8)


if __name__ == "__main__":
    unittest.main()
