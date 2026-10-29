from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_working_model as model


@dataclass
class FixtureDirect:
    visemes: list
    native_cache: dict
    adapter_cache: dict


class WorkingModelTests(unittest.TestCase):
    def test_component_pass_is_provisional_not_a_production_or_main_release(self) -> None:
        accepted = model.approval()
        self.assertEqual(accepted["exact_answer"], "Both mouth and hand pass")
        self.assertTrue(accepted["scope"]["source_built_full_prototype_allowed"])
        self.assertTrue(accepted["scope"]["artistic_polish_deferred"])
        self.assertFalse(accepted["scope"]["production_release_allowed"])
        self.assertFalse(accepted["scope"]["main_branch_merge_allowed"])

    def test_changed_approved_adapter_fails_without_renderer_or_encoder(self) -> None:
        real_hash = model.scene._hash
        with patch.object(model.scene, "_hash", side_effect=lambda path: "0" * 64 if Path(path).name == "cartoon_hand_motion_refinement.py" else real_hash(path)):
            with self.assertRaisesRegex(ValueError, "hand_adapter"):
                model.approval()

    def test_modified_acceptance_binding_fails_before_reading_scope(self) -> None:
        with patch.object(model.scene, "_hash", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "component binding changed"):
                model.approval()

    def test_existing_output_is_rejected_before_preflight_or_render(self) -> None:
        with tempfile.TemporaryDirectory() as path, patch.object(model, "preflight") as check, patch.object(model.scene, "build") as render:
            with self.assertRaises(FileExistsError):
                model.build(Path(path))
            check.assert_not_called()
            render.assert_not_called()

    def test_builder_context_injects_only_source_and_name_and_restores_on_failure(self) -> None:
        original_source, original_name = model.scene.scene_frames, model.scene.NAME
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with model.source_build_context():
                self.assertIs(model.scene.scene_frames, model.working_frames)
                self.assertEqual(model.scene.NAME, model.NAME)
                raise RuntimeError("injected")
        self.assertIs(model.scene.scene_frames, original_source)
        self.assertEqual(model.scene.NAME, original_name)

    def test_fresh_source_primary_check_needs_no_old_cache_reader(self) -> None:
        with patch.object(model.scene.integration.eyes.v4.v3, "_read_picture_archive", side_effect=AssertionError("external cache prohibited")):
            checked = model.preflight()
        self.assertFalse(checked["external_prior_scene_cache_required"])
        self.assertFalse(checked["api_keys_required"])
        self.assertEqual(checked["clock"]["frame_count"], 303)

    def test_complete_frame_iterator_uses_source_art_then_passed_adapters_without_cache(self) -> None:
        from contextlib import nullcontext
        pixel = np.zeros((1, 1, 3), np.uint8)
        direct = FixtureDirect([{"frame": 1, "from_shape": "X", "to_shape": "X", "blend": 1.0}], {}, {})
        # Dataclass replacements stay real; only expensive renderer preparation
        # and composition are replaced to test routing/clock/cleanup in isolation.
        real = model.scene.integration.PreparedRepairedActing
        integration_type = model.scene.acting.PreparedIntegration
        dummy = real(integration_type({}, Path("unused"), direct, object()), pixel, {}, {}, {}, Path("unused.wav"))
        seen = []
        closed = []
        def source():
            try:
                for number in range(1, 76):
                    yield number, pixel, {"source_frame": number + 111}
            finally:
                closed.append(True)
        def compose(prepared, frame):
            seen.append((frame, prepared.integration.direct.visemes[0]["to_shape"]))
            return pixel, {"output_frame": frame + 75}
        with patch.object(model.opening, "frames", side_effect=source), patch.object(model.scene, "accepted_lids", side_effect=lambda prepared: nullcontext()), patch.object(
            model.hand, "hand_override", side_effect=lambda rig, frame: nullcontext()
        ), patch.object(model.scene, "compose_direct_frame", side_effect=compose), patch.object(
            model.scene.integration.eyes.v4.v3, "_read_picture_archive", side_effect=AssertionError("external cache prohibited")
        ):
            rows = list(model.working_frames(dummy))
        self.assertEqual([number for number, _, _ in rows], list(range(1, 304)))
        self.assertEqual([frame for frame, _ in seen], list(range(1, 229)))
        self.assertEqual(closed, [True])
        self.assertTrue(all(row[2]["built_from_tracked_source"] for row in rows))


if __name__ == "__main__":
    unittest.main()
