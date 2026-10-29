from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_dialogue_scene as new


RECIPE = new.ROOT / "concept/scenes/june-rest-your-hands-v1.json"


class DialogueSceneTests(unittest.TestCase):
    def compile_changed(self, change):
        import json
        config = json.loads(RECIPE.read_text(encoding="utf-8"))
        change(config)
        with tempfile.TemporaryDirectory() as folder:
            recipe = Path(folder) / "scene.json"
            recipe.write_text(json.dumps(config), encoding="utf-8")
            return new.compile_scene(recipe)

    def test_new_scene_uses_its_own_audio_clock_and_translated_mouth(self):
        plan = new.compile_scene(RECIPE)
        self.assertEqual(plan["frame_count"], 207)
        self.assertNotEqual(plan["frame_count"], 228)
        self.assertEqual(len(plan["visemes"]), 207)
        self.assertEqual(plan["keyframes"][-1]["frame"], 207)
        self.assertEqual(plan["blink_starts"], [100])
        self.assertTrue(all(row["to_shape"] == "X" for row in plan["visemes"][-30:]))
        self.assertTrue(all("rhubarb_to_shape" in row for row in plan["visemes"]))

    def test_changed_audio_or_cues_fail(self):
        for key in ("audio", "cues"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.compile_changed(lambda config: config[key].update(sha256="0"*64))

    def test_scene_recipe_cannot_grant_release(self):
        with self.assertRaisesRegex(ValueError, "release"):
            self.compile_changed(lambda config: config.update(production_release_allowed=True))

    def test_asset_escape_fails_without_reading_outside_project(self):
        with self.assertRaises(ValueError):
            new.locked_asset({"path": "../../outside.wav", "sha256": "0"*64})

    def test_dialogue_hint_mismatch_fails(self):
        with self.assertRaisesRegex(ValueError, "dialogue"):
            self.compile_changed(lambda config: config.update(dialogue="Different words"))

    def test_unapproved_new_hand_action_and_old_shoulder_warp_fail(self):
        with self.assertRaisesRegex(ValueError, "hand"):
            self.compile_changed(lambda config: config.update(hand_pose="wave"))
        with self.assertRaisesRegex(ValueError, "Torso|torso"):
            self.compile_changed(lambda config: config["motion_keys"][1].update(breath_y_px=1))

    def test_invalid_control_and_collapsed_keys_fail(self):
        for value in (10, float("nan")):
            with self.assertRaisesRegex(ValueError, "bounds"):
                self.compile_changed(lambda config: config["motion_keys"][1].update(head_tilt_deg=value))
        with self.assertRaisesRegex(ValueError, "collapse"):
            self.compile_changed(lambda config: config["motion_keys"][1].update(phase=.000001))

    def test_overlapping_or_outside_blink_fails(self):
        for starts in ([3.3, 3.4], [-.1], [6.8]):
            with self.assertRaisesRegex(ValueError, "Blink"):
                self.compile_changed(lambda config: config.update(blink_starts_seconds=starts))

    def test_nonquiet_tail_fails_before_render(self):
        samples, probe = new.scene.picture._read_pcm24_wave(new.locked_asset(new.compile_scene(RECIPE)["config"]["audio"]))
        samples[-1] = 1
        with patch.object(new.scene.picture, "_read_pcm24_wave", return_value=(samples, probe)), self.assertRaisesRegex(ValueError, "silence"):
            new.compile_scene(RECIPE)

    def test_existing_output_is_never_reused(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(new, "compile_scene") as compile:
            with self.assertRaises(FileExistsError):
                new.build(RECIPE, Path(folder))
            compile.assert_not_called()

    def test_real_rig_can_render_beyond_old_228_frame_limit_without_mutating_bank(self):
        source = new.scene.integration.prepare_repaired_acting()
        original = (source.integration.direct.contract, source.integration.direct.visemes, source.integration.body.states)
        plan = deepcopy(new.compile_scene(RECIPE))
        plan["frame_count"] = 300
        last = deepcopy(plan["visemes"][-1])
        plan["visemes"].extend({**last, "frame": n} for n in range(208,301))
        for key in plan["keyframes"]:
            key["frame"] = 1 + round((key["frame"]-1)/206*299)
        with tempfile.TemporaryDirectory() as folder:
            runtime = new.runtime_prepared(source, plan, Path(folder))
            self.assertEqual(len(runtime.integration.direct.motion), 300)
            self.assertEqual(len(runtime.integration.body.states), 300)
            with new.scene.integration.registered_lids(runtime), new.blink.shape_override(True):
                frame = new.acting.compose_integrated_frame(runtime.integration, 300)
            self.assertEqual(frame.candidate.shape, (1080,1920,3))
            self.assertEqual(frame.metrics["changed_pixels_in_transformed_mug_support"], 0)
            with self.assertRaises(new.acting.SynchronizedActingIntegrationError):
                new.acting.compose_integrated_frame(runtime.integration, 301)
        self.assertIs(source.integration.direct.contract, original[0])
        self.assertIs(source.integration.direct.visemes, original[1])
        self.assertIs(source.integration.body.states, original[2])
        self.assertEqual(len(source.integration.direct.visemes), 228)
        new.bank.approval()


if __name__ == "__main__":
    unittest.main()
