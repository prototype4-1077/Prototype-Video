from __future__ import annotations

import ast
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_repaired_acting as repaired


class RepairedActingControlTests(unittest.TestCase):
    def test_editorial_and_audio_windows_share_the_actual_edit_clock(self) -> None:
        cases = ((1, 76, 120000), (24, 99, 156800), (25, 100, 158400), (81, 156, 248000), (163, 238, 379200), (228, 303, 483200))
        for source, output, start in cases:
            window = repaired.editorial_window(source)
            self.assertEqual(window["output_frame"], output)
            self.assertEqual(window["audio_start_sample"], start)
            self.assertEqual(window["audio_end_sample_exclusive"], start + 1600)
        for value in (0, 229, True, 1.5, "81"):
            with self.assertRaises(ValueError):
                repaired.editorial_window(value)

    def test_source_drift_fails_before_expensive_renderer_preparation(self) -> None:
        with patch.object(repaired, "_sha256", return_value="0" * 64), patch.object(repaired.acting, "prepare_integration") as prepare:
            with self.assertRaisesRegex(repaired.RepairedActingError, "report hash mismatch"):
                repaired.prepare_repaired_acting()
            prepare.assert_not_called()

    def test_existing_evidence_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.object(repaired, "prepare_repaired_acting") as prepare:
            with self.assertRaisesRegex(repaired.RepairedActingError, "refusing to overwrite"):
                repaired.build_evidence(Path(temporary))
            prepare.assert_not_called()

    def test_context_restores_texture_cache_and_global_functions_after_failure(self) -> None:
        shape = (120, 180, 3)
        texture = np.arange(np.prod(shape), dtype=np.uint8).reshape(shape)
        original = texture.copy()
        sentinel = object()
        cache = {"legacy": sentinel}
        geometry = {"viewer_left_eye": {"center": [50, 50], "radius": [20, 16]}, "viewer_right_eye": {"center": [120, 60], "radius": [20, 17]}}
        direct = SimpleNamespace(face=SimpleNamespace(
            phase33_base=SimpleNamespace(lid_texture=texture), plate=np.zeros(shape, dtype=np.uint8),
            contract={"semantic_geometry_native_xy": geometry},
        ), native_cache=cache)
        prepared = SimpleNamespace(integration=SimpleNamespace(direct=direct), texture=np.full(shape, 180, dtype=np.uint8))
        phase34 = repaired.eyes.v4.v3.phase35.phase34_candidate09
        prior_compose, prior_masks = phase34.phase33._compose_eye_lids, phase34._semantic_lid_alpha_masks
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with repaired.registered_lids(prepared):
                self.assertTrue(np.array_equal(texture, prepared.texture))
                self.assertEqual(cache, {})
                cache["candidate"] = object()
                raise RuntimeError("injected")
        self.assertTrue(np.array_equal(texture, original))
        self.assertEqual(cache, {"legacy": sentinel})
        self.assertIs(direct.native_cache, cache)
        self.assertIs(phase34.phase33._compose_eye_lids, prior_compose)
        self.assertIs(phase34._semantic_lid_alpha_masks, prior_masks)

    def test_builder_has_no_process_network_or_full_scene_route(self) -> None:
        tree = ast.parse(Path(repaired.__file__).read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".")[0])
        self.assertTrue({"subprocess", "socket", "requests", "urllib", "moviepy"}.isdisjoint(roots))
        self.assertEqual(repaired.REVIEW_FRAMES, (70, 79, 81, 82, 148, 173))


class RepairedActingLiveRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = repaired.prepare_repaired_acting()
        cls.frames = {number: repaired.compose_repaired_frame(cls.prepared, number) for number in (70, 81, 173)}

    def test_first_full_blink_survives_while_body_and_hand_are_moving(self) -> None:
        metrics = self.frames[81].metrics
        self.assertTrue(metrics["body_active"])
        self.assertEqual(metrics["blink_closure"], 1.0)
        self.assertGreater(metrics["body_changed_pixels"], 0)
        self.assertGreater(metrics["eye_repair_changed_pixels"], 0)
        for key in ("eye_repair_changes_outside_prospective_eye_support", "body_changes_inside_repaired_face_support", "body_changes_inside_mug_support", "body_changes_outside_body_support"):
            self.assertEqual(metrics[key], 0)

    def test_open_eyes_are_byte_identical_to_existing_body_render(self) -> None:
        frame = self.frames[70]
        self.assertTrue(frame.metrics["body_active"])
        self.assertGreater(frame.metrics["body_changed_pixels"], 0)
        self.assertEqual(frame.metrics["blink_closure"], 0.0)
        self.assertTrue(np.array_equal(frame.body_only, frame.repaired))

    def test_late_blink_matches_the_exact_reviewed_eye_frame_after_camera(self) -> None:
        frame = self.frames[173]
        self.assertFalse(frame.metrics["body_active"])
        self.assertEqual(frame.metrics["body_changed_pixels"], 0)
        self.assertEqual(frame.metrics["repaired_rgb_sha256"], "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40")

    def test_support_checker_detects_a_deliberately_invalid_projection(self) -> None:
        empty = np.zeros(self.frames[81].repaired.shape[:2], dtype=bool)
        with patch.object(repaired.eyes.v4.v3, "_prospective_support_to_phase35", return_value=(empty, {})):
            with self.assertRaisesRegex(repaired.RepairedActingError, "outside its declared support"):
                repaired.compose_repaired_frame(self.prepared, 81)

    def test_lost_eye_repair_fails_instead_of_passing_old_body_metrics(self) -> None:
        with patch.object(repaired, "registered_lids", return_value=nullcontext()):
            with self.assertRaisesRegex(repaired.RepairedActingError, "eye repair was lost"):
                repaired.compose_repaired_frame(self.prepared, 81)


class RepairedActingPublishedProofTests(unittest.TestCase):
    def test_sampled_evidence_binds_renderer_artifacts_audio_and_pending_review(self) -> None:
        package = repaired.REPO_ROOT / "collab/phase42_repaired_acting_integration_v1"
        report = json.loads((package / "phase42-repaired-acting-integration-report-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(report["implementation_sha256"], repaired._sha256(Path(repaired.__file__)))
        self.assertFalse(report["full_scene_rendered"])
        self.assertFalse(report["human_accepted"])
        self.assertFalse(report["promotion_allowed"])
        self.assertEqual(report["sampled_source_frames"], list(repaired.REVIEW_FRAMES))
        self.assertEqual(report["audio_binding"]["sample_count"], 484800)
        self.assertFalse(report["audio_binding"]["human_listening_accepted"])
        self.assertEqual(repaired._sha256(repaired.REPO_ROOT / report["audio_binding"]["file"]), report["audio_binding"]["wav_sha256"])
        for name, entry in report["artifacts"].items():
            data = (package / name).read_bytes()
            self.assertEqual(len(data), entry["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])


if __name__ == "__main__":
    unittest.main()
