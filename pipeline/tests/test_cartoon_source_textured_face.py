from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path
import tempfile
import unittest

import numpy as np

import pipeline.cartoon_source_textured_face as phase34


class SourceTexturedFaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_path = phase34.REPO_ROOT / phase34.CONTRACT_RELATIVE_PATH
        cls.contract = phase34.load_contract(cls.contract_path)
        cls.source, cls.triangles = phase34._cage(cls.contract)

    def test_identity_source_and_representation_are_fail_closed(self) -> None:
        representation = self.contract["representation"]
        self.assertTrue(representation["source_plate_is_only_identity_texture"])
        self.assertTrue(representation["piecewise_affine_texture_deformation"])
        self.assertTrue(representation["neutral_bypass_is_exact_source_plate"])
        self.assertFalse(representation["complete_eye_mouth_or_face_photo_crossfades_allowed"])
        self.assertFalse(representation["foreign_atlas_identity_pixels_allowed"])
        self.assertFalse(representation["procedural_lip_color_slabs_allowed"])
        self.assertFalse(representation["audio_allowed"])
        self.assertTrue(representation["registered_authored_oral_interior_atlas_allowed"])
        self.assertFalse(representation["generated_lip_pixels_allowed_in_final_composite"])
        self.assertFalse(representation["runtime_ai_generation_allowed"])

    def test_all_locked_sources_match_their_declared_hashes(self) -> None:
        for name, reference in self.contract["locks"].items():
            with self.subTest(name=name):
                self.assertEqual(
                    phase34._locked_source_hash(reference),
                    reference["sha256"],
                )

    def test_lf_normalized_text_lock_is_cross_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lf = Path(directory) / "lf.py"
            crlf = Path(directory) / "crlf.py"
            lf.write_bytes(b"one\ntwo\n")
            crlf.write_bytes(b"one\r\ntwo\r\n")
            self.assertEqual(
                phase34._sha256_lf_normalized_text(lf),
                phase34._sha256_lf_normalized_text(crlf),
            )

    def test_cage_has_fixed_topology_and_neutral_is_an_exact_bypass(self) -> None:
        self.assertEqual(self.source.shape, (100, 2))
        self.assertEqual(self.triangles.shape, (162, 3))
        neutral = self.contract["pose_geometry_native_px"]["X"]
        np.testing.assert_array_equal(
            phase34._destination_points(self.contract, self.source, neutral),
            self.source,
        )

    def test_every_non_neutral_pose_preserves_safe_topology(self) -> None:
        gates = self.contract["preencode_gates"]
        for name, pose in self.contract["pose_geometry_native_px"].items():
            if name == "X":
                continue
            destination = phase34._destination_points(self.contract, self.source, pose)
            metrics = phase34._triangle_metrics(self.source, destination, self.triangles)
            with self.subTest(pose=name):
                self.assertEqual(metrics["folded_triangles"], gates["required_folded_triangles"])
                self.assertGreaterEqual(metrics["minimum_triangle_area_ratio"], gates["minimum_triangle_area_ratio"])
                self.assertLessEqual(metrics["maximum_triangle_area_ratio"], gates["maximum_triangle_area_ratio"])
                self.assertLessEqual(metrics["maximum_triangle_condition_number"], gates["maximum_triangle_condition_number"])

    def test_pose_clock_has_exact_neutral_endpoints_and_distinct_keys(self) -> None:
        self.assertEqual(self.contract["clock"]["fps"], 24)
        self.assertEqual(self.contract["clock"]["frame_count"], 96)
        self.assertEqual(self.contract["performance"]["maximum_transition_frames"], 2)
        neutral = self.contract["pose_geometry_native_px"]["X"]
        for frame in self.contract["performance"]["exact_neutral_frames"]:
            controls, weights = phase34.mouth_controls(self.contract, frame)
            self.assertEqual(controls, neutral)
            self.assertEqual(weights["X"], 1.0)
        vectors = []
        for name, frame in self.contract["performance"]["key_pose_frames"].items():
            controls, weights = phase34.mouth_controls(self.contract, frame)
            self.assertEqual(weights[name], 1.0)
            if name != "X":
                vectors.append(tuple(controls[field] for field in phase34.POSE_FIELDS))
        self.assertEqual(len(set(vectors)), 8)

    def test_contract_mutations_reject_identity_geometry_gates_paths_and_policy(self) -> None:
        mutations = (
            ("representation", "complete_eye_mouth_or_face_photo_crossfades_allowed", True),
            ("representation", "foreign_atlas_identity_pixels_allowed", True),
            ("representation", "audio_allowed", True),
            ("representation", "registered_authored_oral_interior_atlas_allowed", False),
            ("representation", "runtime_ai_generation_allowed", True),
            ("representation", "oral_interior_interpolation", "crossfade"),
            ("failure_policy", "automatic_reencode_allowed", True),
            ("failure_policy", "caller_selected_output_directory_allowed", True),
            ("promotion_policy", "reinforcement_learning_allowed", True),
        )
        for section, key, value in mutations:
            changed = deepcopy(self.contract)
            changed[section][key] = value
            with self.subTest(section=section, key=key):
                with self.assertRaisesRegex(phase34.SourceTexturedFaceError, "complete Phase34 v1 contract"):
                    phase34._validate_contract(changed)
        direct_mutations = (
            ("preencode_gates", "maximum_adjacent_feature_8x8_mean_delta", 999999.0),
            ("preencode_gates", "require_all_96_raw_frame_hashes", False),
            ("preencode_gates", "require_lossless_review_frame_archive", False),
            ("preencode_gates", "require_preview_review_receipt", False),
            ("preview", "directory", "../../outputs/edit/redirected"),
        )
        for section, key, value in direct_mutations:
            changed = deepcopy(self.contract)
            changed[section][key] = value
            with self.subTest(section=section, key=key):
                with self.assertRaisesRegex(phase34.SourceTexturedFaceError, "complete Phase34 v1 contract"):
                    phase34._validate_contract(changed)
        changed = deepcopy(self.contract)
        changed["pose_geometry_native_px"]["A"]["opening"] = 1.0
        with self.assertRaisesRegex(phase34.SourceTexturedFaceError, "complete Phase34 v1 contract"):
            phase34._validate_contract(changed)

    def test_preview_path_is_contract_pinned_and_immutable(self) -> None:
        expected = (phase34.REPO_ROOT / self.contract["preview"]["directory"]).resolve()
        self.assertEqual(phase34._preview_output_path(self.contract, None), expected)
        with self.assertRaisesRegex(phase34.SourceTexturedFaceError, "development label"):
            phase34._preview_output_path(self.contract, "../escape")
        parameters = inspect.signature(phase34.write_unencoded_preview).parameters
        self.assertNotIn("output_dir", parameters)

    def test_renderer_has_no_encode_or_atlas_swap_path(self) -> None:
        source = inspect.getsource(phase34)
        self.assertNotIn("cv2.VideoWriter", source)
        self.assertNotIn("ffmpeg", source.lower())
        self.assertNotIn("Image.blend", source)
        self.assertIn("Phase34 v1 is preview-only", source)
        self.assertIn("_compose_authored_oral_anatomy", inspect.getsource(phase34._native_frame))
        self.assertNotIn("_legacy_procedural_oral_anatomy_for_rejected_01(", inspect.getsource(phase34._native_frame))

    def test_oral_cells_are_independently_registered_and_boundary_safe(self) -> None:
        path = phase34.REPO_ROOT / self.contract["locks"]["oral_interior_atlas"]["path"]
        cells = phase34._load_oral_cells(path)
        self.assertEqual(set(cells), set("XABCDEFGH"))
        for name, cell in cells.items():
            with self.subTest(cell=name):
                alpha = cell.rgba[:, :, 3]
                if name == "X":
                    self.assertEqual(int((alpha >= 16).sum()), 0)
                else:
                    self.assertGreater(int((alpha >= 16).sum()), 0)
                self.assertFalse((alpha[0] >= 16).any())
                self.assertFalse((alpha[-1] >= 16).any())
                self.assertFalse((alpha[:, 0] >= 16).any())
                self.assertFalse((alpha[:, -1] >= 16).any())
                self.assertEqual(int(((alpha > 8) & (cell.excluded_outer_ring > 8)).sum()), 0)
                if name != "X":
                    self.assertGreater(int((cell.upper_dentition_rgba[:, :, 3] >= 16).sum()), 0)
                    self.assertEqual(cell.upper_dentition_forbidden_source_pixels, 0)
                    dental_alpha = cell.upper_dentition_rgba[:, :, 3].astype(np.float64)
                    yy, xx = np.indices(dental_alpha.shape, dtype=np.float64)
                    self.assertLessEqual(
                        abs(float((yy * dental_alpha).sum() / dental_alpha.sum()) - (dental_alpha.shape[0] - 1) * 0.5),
                        0.51,
                    )
                    self.assertLessEqual(
                        abs(float((xx * dental_alpha).sum() / dental_alpha.sum()) - (dental_alpha.shape[1] - 1) * 0.5),
                        0.51,
                    )

    def test_premultiplied_warp_cannot_pull_hidden_green_into_transparency(self) -> None:
        cell = np.zeros((24, 24, 4), dtype=np.uint8)
        cell[:, :, :3] = np.asarray([0, 255, 0], dtype=np.uint8)
        cell[8:16, 8:16, :3] = np.asarray([180, 60, 50], dtype=np.uint8)
        cell[8:16, 8:16, 3] = 255
        oral_cell = phase34.OralCell(
            rgba=cell,
            excluded_outer_ring=np.zeros(cell.shape[:2], dtype=np.uint8),
            upper_dentition_rgba=np.zeros((1, 1, 4), dtype=np.uint8),
            upper_dentition_forbidden_source_pixels=0,
        )
        premultiplied, alpha, excluded = phase34._warp_oral_cell(
            oral_cell, (96, 96), (48.0, 48.0), 42.0, 28.0, 5.0,
        )
        transparent = alpha <= 1e-6
        self.assertTrue(np.allclose(premultiplied[transparent], 0.0, atol=1e-4))
        visible_rgb = premultiplied[alpha > 0.5] / alpha[alpha > 0.5][:, None]
        self.assertLess(float(visible_rgb[:, 1].max()), 100.0)
        self.assertEqual(int((excluded > 0).sum()), 0)

    def test_lossless_frame_archive_round_trips_exact_rgb_bytes(self) -> None:
        frames = []
        for value in (0, 31, 31, 255):
            frame = np.full((9, 13, 3), value, dtype=np.uint8)
            frame[2:5, 4:8, 1] = 177
            frames.append(phase34.Image.fromarray(frame, "RGB"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.gz"
            written = phase34._write_lossless_frame_archive(frames, path)
            read, restored = phase34._read_lossless_frame_archive(path)
            self.assertEqual(read, written)
            for expected, actual in zip(frames, restored, strict=True):
                np.testing.assert_array_equal(np.asarray(expected), actual)

    def test_depth_order_gate_checks_containment_and_final_owner(self) -> None:
        coverage = np.zeros((4, 4), dtype=np.uint16)
        owner = np.zeros((4, 4), dtype=np.uint8)
        coverage[0, 0] = phase34.LAYER_BITS["source_warp"] | phase34.LAYER_BITS["cavity"]
        owner[0, 0] = 2
        coverage[1, 1] = phase34.LAYER_BITS["cavity"] | phase34.LAYER_BITS["eyelids"]
        owner[1, 1] = 10
        coverage[2, 2] = phase34.LAYER_BITS["oral_interior"]
        owner[2, 2] = 3
        self.assertEqual(phase34._depth_order_violation_pixels(owner, coverage), 2)

    def test_single_alpha_write_enters_depth_coverage(self) -> None:
        coverage = np.zeros((2, 2), dtype=np.uint16)
        alpha = np.zeros((2, 2), dtype=np.uint8)
        alpha[0, 1] = phase34.LAYER_WRITE_ALPHA_THRESHOLD_U8
        phase34._record_layer(coverage, alpha, "oral_interior")
        self.assertNotEqual(int(coverage[0, 1] & phase34.LAYER_BITS["oral_interior"]), 0)
        self.assertEqual(int(coverage[0, 0]), 0)

    def test_oral_activation_is_semantic_and_smooth_at_neutral_boundaries(self) -> None:
        activations = []
        for frame in (16, 17, 18, 19, 80, 81, 82, 83):
            pose, weights = phase34.mouth_controls(self.contract, frame)
            activations.append(phase34._oral_activation(pose, weights))
        self.assertEqual(activations[0], 0.0)
        self.assertEqual(activations[3], 1.0)
        self.assertEqual(activations[4], 1.0)
        self.assertEqual(activations[-1], 0.0)
        self.assertLessEqual(max(abs(b - a) for a, b in zip(activations, activations[1:])), 0.5)
        self.assertLessEqual(activations[-2], 0.27)

    def test_blink_is_native_24fps_and_returns_to_exact_neutral(self) -> None:
        expected = {4: 0.0, 5: 0.15625, 6: 0.5, 7: 0.84375, 8: 1.0, 9: 0.84375, 10: 0.5, 11: 0.15625, 12: 0.0, 13: 0.0}
        for frame, closure in expected.items():
            with self.subTest(frame=frame):
                self.assertAlmostEqual(phase34.blink_closure(self.contract, frame), closure)


if __name__ == "__main__":
    unittest.main()
