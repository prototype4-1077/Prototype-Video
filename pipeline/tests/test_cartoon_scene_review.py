from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from pipeline import cartoon_scene_review as scene


class SceneReviewControlTests(unittest.TestCase):
    def test_exact_human_components_are_accepted_but_unseen_performance_is_not(self) -> None:
        accepted = scene.accepted_components()
        self.assertEqual(accepted["exact_message"], "both are good and pass. continue")
        self.assertTrue(accepted["audio"]["human_accepted"])
        self.assertTrue(accepted["blink"]["human_accepted"])
        self.assertTrue(accepted["scope"]["integrated_303_frame_review_allowed"])
        self.assertFalse(accepted["scope"]["integrated_performance_human_accepted"])
        self.assertFalse(accepted["scope"]["production_release_allowed"])
        self.assertFalse(accepted["scope"]["main_branch_merge_allowed"])

    def test_approval_or_source_drift_fails_before_renderer_preparation(self) -> None:
        with patch.object(scene, "_hash", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "acceptance binding changed"):
                scene.accepted_components()
        real_hash = scene._hash
        with patch.object(scene, "_hash", side_effect=lambda path: "0" * 64 if path.suffix == ".wav" else real_hash(path)):
            with self.assertRaisesRegex(ValueError, "accepted audio artifact changed"):
                scene.accepted_components()

    def test_existing_outputs_are_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(scene.integration, "prepare_repaired_acting") as prepare:
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                scene.build(Path(temporary))
            prepare.assert_not_called()

    def test_exact_shot_and_audio_clock_have_no_gaps_or_implicit_retiming(self) -> None:
        frames = [frame for start, end in scene.SHOTS for frame in range(start, end + 1)]
        self.assertEqual(frames, list(range(1, 304)))
        self.assertEqual(scene.SHOTS, ((1, 75), (76, 237), (238, 303)))
        self.assertEqual(303 * 1600, 484800)
        for source in range(1, 229):
            window = scene.integration.editorial_window(source)
            self.assertEqual(window["output_frame"], source + 75)
            self.assertEqual(window["audio_start_sample"], (source + 74) * 1600)

    def test_encoder_uses_verified_frame_metadata_not_stream_flags_alone(self) -> None:
        command = scene.encoder_command("ffmpeg", Path("review.mp4"))
        filters = command[command.index("-vf") + 1]
        self.assertIn("out_color_matrix=bt709", filters)
        self.assertIn("setsar=1", filters)
        self.assertIn("setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709", filters)
        self.assertEqual(command[command.index("-x264-params") + 1], scene.X264_PARAMS)
        self.assertNotIn("h264_metadata", " ".join(command))


class SceneReviewLiveRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = scene.integration.prepare_repaired_acting()
        with scene.accepted_lids(cls.prepared):
            cls.frames = {frame: scene.compose_direct_frame(cls.prepared, frame) for frame in (70, 81, 169, 173)}

    def test_original_early_blink_is_removed_without_removing_body_acting(self) -> None:
        for number in (70, 81):
            pixels, metrics = self.frames[number]
            self.assertEqual(pixels.shape, (1080, 1920, 3))
            self.assertEqual(metrics["blink_closure"], 0.0)
            self.assertTrue(metrics["body_active"])
            self.assertGreater(metrics["body_changed_pixels"], 0)
            self.assertEqual(metrics["protected_region_violations"], 0)

    def test_refined_partial_and_full_closure_survive_head_and_editorial_camera(self) -> None:
        self.assertAlmostEqual(self.frames[169][1]["blink_closure"], 0.352)
        pixels, metrics = self.frames[173]
        self.assertEqual(metrics["blink_closure"], 1.0)
        self.assertEqual(scene.acting._rgb_hash(pixels), "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40")

    def test_context_restores_contract_texture_cache_and_mask_function_on_exception(self) -> None:
        direct = self.prepared.integration.direct
        contract, cache = direct.contract, direct.native_cache.copy()
        texture = direct.face.phase33_base.lid_texture.copy()
        prior_masks = scene.blink.continuous.lid_alpha_masks
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with scene.accepted_lids(self.prepared):
                self.assertIsNot(direct.contract, contract)
                self.assertEqual(scene.acting.phase35.production_blink_closure(direct.contract, 81), 0.0)
                raise RuntimeError("injected")
        self.assertIs(direct.contract, contract)
        self.assertEqual(set(direct.native_cache), set(cache))
        for key in cache:
            self.assertIs(direct.native_cache[key], cache[key])
        self.assertTrue(np.array_equal(direct.face.phase33_base.lid_texture, texture))
        self.assertIs(scene.blink.continuous.lid_alpha_masks, prior_masks)

    def test_missing_override_cannot_silently_restore_the_old_blink(self) -> None:
        with self.assertRaisesRegex(ValueError, "accepted blink schedule"):
            scene.compose_direct_frame(self.prepared, 81)


class SceneReviewPublishedProofTests(unittest.TestCase):
    def test_review_is_bound_to_exact_components_and_stays_unpromoted(self) -> None:
        package = scene.REPO_ROOT / "collab/phase42_integrated_scene_review_v1"
        report = json.loads((package / "phase42-integrated-scene-review-report-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(report["implementation_sha256"], scene._hash(Path(scene.__file__)))
        self.assertEqual(report["component_acceptance_sha256"], scene.ACCEPTANCE_SHA256)
        self.assertEqual(report["frame_count"], 303)
        self.assertEqual(report["rendered_blink_full_close_frames"], [247, 248])
        self.assertTrue(report["audit"]["mov_audio_bit_exact"])
        self.assertTrue(report["audit"]["all_303_frame_timestamps_exact"])
        self.assertTrue(report["all_75_pour_frames_match_original_pixels"])
        self.assertGreaterEqual(report["audit"]["aac_preview_snr_db"], 40)
        self.assertFalse(report["integrated_performance_human_accepted"])
        self.assertFalse(report["production_release_allowed"])
        self.assertEqual(report["cash_cost"], 0)
        for name, entry in report["artifacts"].items():
            self.assertTrue((package / name).is_file(), name)
            self.assertEqual(scene._hash(package / name), entry["sha256"])
        self.assertEqual(scene._hash(package / "ATTRIBUTION.md"), scene.foley.CREDITS_SHA256)
        for probe in report["audit"]["probes"].values():
            video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
            for field in ("color_space", "color_transfer", "color_primaries"):
                self.assertEqual(video[field], "bt709")
            self.assertEqual(video["color_range"], "tv")
            self.assertEqual(video["sample_aspect_ratio"], "1:1")
        inventory = json.loads((package / "source-frame-inventory-v1.json").read_text(encoding="utf-8"))
        for frame in (145, 244, 248):
            with Image.open(package / f"reference-f{frame:03d}.png") as image:
                self.assertEqual(scene.acting._rgb_hash(np.asarray(image.convert("RGB"))), inventory[frame - 1]["rgb_sha256"])


if __name__ == "__main__":
    unittest.main()
