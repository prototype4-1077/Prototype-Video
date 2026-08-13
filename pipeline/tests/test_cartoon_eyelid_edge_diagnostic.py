from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import cv2
import numpy as np

from pipeline import cartoon_eyelid_edge_diagnostic as diagnostic


def _independent_masks(prepared, sclera, contract):
    """Recompute V4 masks from only the public contract and locked V3 inputs."""
    right = sclera["viewer_right_eye"]
    plate = prepared.face.plate
    hsv = cv2.cvtColor(plate, cv2.COLOR_RGB2HSV)
    probe = contract["diagnostic"]["residual_band_probe"]
    threshold = (
        (hsv[:, :, 1] <= int(probe["maximum_saturation_u8"]))
        & (hsv[:, :, 2] >= int(probe["minimum_value_u8"]))
    )
    support = diagnostic.v3._dilate_chebyshev(
        right["core"], int(probe["threshold_probe_support_radius_px"]),
    ) & right["registered_patch"]
    delta = threshold & support & ~right["core"]
    seed = tuple(int(value) for value in probe["seed_xy"])
    hard = right["leak"] | delta
    hard_subject = diagnostic._connected_seed_component(hard, seed)
    extended_core = right["core"] | delta
    edge = contract["diagnostic"]["edge_corridor"]
    x1, y1, x2, y2 = (int(value) for value in edge["bbox_xyxy"])
    corridor = np.zeros(plate.shape[:2], dtype=bool)
    corridor[y1:y2, x1:x2] = True
    corridor &= right["registered_patch"]
    _, lower, _ = diagnostic.v3.phase35.phase34_candidate09._semantic_lid_alpha_masks(
        plate.shape[:2], right["center"], right["radius"], 1.0,
    )
    ring1 = diagnostic.v3._dilate_chebyshev(hard_subject, 1) & ~hard & ~extended_core & corridor
    ring2 = diagnostic.v3._dilate_chebyshev(hard_subject, 2) & ~hard & ~extended_core & corridor
    feather1 = ring1 & (lower < int(edge["feather_1px"]["alpha_u8"]))
    feather2_inner = ring1 & (lower < int(edge["feather_2px_inner"]["alpha_u8"]))
    feather2_outer = (
        ring2 & ~ring1 & (lower < int(edge["feather_2px_outer"]["alpha_u8"]))
    )
    return {
        "threshold": threshold,
        "support": support,
        "delta": delta,
        "hard": hard,
        "hard_subject": hard_subject,
        "extended_core": extended_core,
        "corridor": corridor,
        "ring1": ring1,
        "ring2": ring2,
        "ring2_only": ring2 & ~ring1,
        "feather_1px": feather1,
        "feather_2px_inner": feather2_inner,
        "feather_2px_outer": feather2_outer,
    }


class EyelidEdgeDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = diagnostic.load_contract()
        cls.prepared = diagnostic.v3.phase35.prepare_direct_address()
        cls.sclera = diagnostic.v3._classified_sclera_masks(
            cls.prepared, diagnostic.v3.load_contract(),
        )
        cls.independent = _independent_masks(cls.prepared, cls.sclera, cls.contract)
        _, cls.masks = diagnostic._edge_masks(cls.prepared, cls.contract)

    def test_contract_is_still_only_and_binds_full_public_head(self) -> None:
        self.assertEqual(
            self.contract["predecessor"]["public_head"],
            "a3d48ad2d1576202cac0adcf7345156570bbd0da",
        )
        self.assertFalse(self.contract["diagnostic"]["video_encode_allowed"])
        self.assertFalse(self.contract["diagnostic"]["accepted_source_mutation_allowed"])
        self.assertTrue(self.contract["diagnostic"]["human_review_required"])

    def test_contract_formula_reproduces_every_mask_hash_without_v4_helper(self) -> None:
        probe = self.contract["diagnostic"]["residual_band_probe"]
        edge = self.contract["diagnostic"]["edge_corridor"]
        expected = {
            "delta": probe["expected_delta_mask_sha256"],
            "hard": edge["extended_hard_write"]["expected_mask_sha256"],
            "hard_subject": edge["seed_connected_hard_subject"]["expected_mask_sha256"],
            "corridor": edge["expected_mask_sha256"],
            "ring1": edge["exterior_ring1_geometric"]["expected_mask_sha256"],
            "ring2": edge["exterior_ring2_geometric"]["expected_mask_sha256"],
            "ring2_only": edge["exterior_ring2_only"]["expected_mask_sha256"],
            "feather_1px": edge["feather_1px"]["expected_mask_sha256"],
            "feather_2px_inner": edge["feather_2px_inner"]["expected_mask_sha256"],
            "feather_2px_outer": edge["feather_2px_outer"]["expected_mask_sha256"],
        }
        for name, expected_hash in expected.items():
            self.assertEqual(diagnostic._mask_hash(self.independent[name]), expected_hash, name)
        module_names = {
            "hard": "hard_by_eye",
            "ring1": "ring1_geometric",
            "ring2": "ring2_geometric",
            "ring2_only": "ring2_only",
        }
        for name in expected:
            module_name = module_names.get(name, name)
            actual = self.masks[module_name]["viewer_right_eye"] if name == "hard" else self.masks[module_name]
            self.assertTrue(np.array_equal(self.independent[name], actual), name)

    def test_probe_relations_exterior_ring_disjointness_and_union_locks(self) -> None:
        mask = self.independent
        seed_x, seed_y = self.contract["diagnostic"]["residual_band_probe"]["seed_xy"]
        self.assertTrue(mask["delta"][seed_y, seed_x])
        self.assertEqual(int((mask["delta"] & ~mask["threshold"]).sum()), 0)
        self.assertEqual(int((mask["delta"] & ~mask["support"]).sum()), 0)
        self.assertEqual(diagnostic.v3._component_count(mask["delta"]), 1)
        self.assertEqual(int((mask["ring1"] & (mask["hard"] | mask["extended_core"])).sum()), 0)
        self.assertEqual(int((mask["ring2"] & (mask["hard"] | mask["extended_core"])).sum()), 0)
        self.assertEqual(int((mask["feather_2px_inner"] & mask["feather_2px_outer"]).sum()), 0)
        edge = self.contract["diagnostic"]["edge_corridor"]
        unions = {
            "extended_hard_plus_feather_1px": mask["hard"] | mask["feather_1px"],
            "feather_2px_inner_plus_outer": mask["feather_2px_inner"] | mask["feather_2px_outer"],
            "extended_hard_plus_feather_2px": mask["hard"] | mask["feather_2px_inner"] | mask["feather_2px_outer"],
        }
        for name, union in unions.items():
            self.assertEqual(diagnostic._mask_hash(union), edge["union_locks"][name]["expected_mask_sha256"])

    def test_predecessor_overrides_are_explicit_and_geometric_guard_is_disclosed(self) -> None:
        right_protected = self.sclera["viewer_right_eye"]["protected_non_candidate"]
        for name in ("delta", "feather_1px", "feather_2px_inner", "feather_2px_outer"):
            self.assertTrue(np.array_equal(self.independent[name] & right_protected, self.independent[name]))
        protected = self.masks["declared_geometric_no_write_guard"]
        spec = self.contract["diagnostic"]["declared_viewer_right_geometric_no_write_guard"]
        self.assertEqual(spec["status"], "DECLARED_GEOMETRIC_NO_WRITE_GUARD_BEFORE_CORRECTED_PREVIEW")
        self.assertIn("x=719..724", spec["human_adjudication_required"])
        self.assertEqual(int(protected.sum()), spec["expected_area"])
        self.assertEqual(diagnostic._mask_hash(protected), spec["expected_mask_sha256"])
        writes = self.independent["delta"] | self.independent["hard_subject"] | self.independent["ring1"] | self.independent["ring2"]
        self.assertEqual(int((protected & writes).sum()), 0)

    def test_evidence_builder_draws_exact_bands_tan_point_and_geometric_guard(self) -> None:
        box = diagnostic.v3._bbox(
            diagnostic.v3.phase35._native_eye_support_mask(self.prepared), 16,
        )
        original_overlay = diagnostic.v3._overlay
        with mock.patch.object(diagnostic.v3, "_overlay", wraps=original_overlay) as overlay:
            evidence = diagnostic._classification_overlay(
                self.prepared.face.plate,
                self.prepared.face.phase33_base.lid_texture,
                self.masks,
                box,
                self.contract,
            )
        received = [call.args[1] for call in overlay.call_args_list]
        received_hashes = {diagnostic._mask_hash(mask) for mask in received}
        self.assertIn(diagnostic._mask_hash(self.masks["feather_2px_inner"]), received_hashes)
        self.assertIn(diagnostic._mask_hash(self.masks["feather_2px_outer"]), received_hashes)
        self.assertIn(diagnostic._mask_hash(self.masks["declared_geometric_no_write_guard"]), received_hashes)
        tan_marker = np.zeros(self.prepared.face.plate.shape[:2], dtype=bool)
        tan_marker[275, 722] = True
        self.assertIn(diagnostic._mask_hash(tan_marker), received_hashes)

        pixels = np.asarray(evidence)
        x1, y1, x2, y2 = box
        panel_width = (x2 - x1) * 3
        panel_height = (y2 - y1) * 3 + 24
        tan_panel_xy = ((722 - x1) * 3 + 1, panel_height + 24 + (275 - y1) * 3 + 1)
        base = self.prepared.face.plate[275, 722].astype(np.float32)
        outer = np.clip(base * 0.35 + np.asarray([180, 65, 255]) * 0.65, 0, 255).astype(np.uint8)
        expected_tan = np.clip(outer.astype(np.float32) * 0.35 + np.asarray([255, 0, 255]) * 0.65, 0, 255).astype(np.uint8)
        self.assertTrue(np.array_equal(pixels[tan_panel_xy[1], tan_panel_xy[0]], expected_tan))

        guard_x, guard_y = 735, 260
        self.assertTrue(self.masks["declared_geometric_no_write_guard"][guard_y, guard_x])
        guard_panel_xy = (
            panel_width + (guard_x - x1) * 3 + 1,
            panel_height + 24 + (guard_y - y1) * 3 + 1,
        )
        guard_base = self.prepared.face.plate[guard_y, guard_x].astype(np.float32)
        expected_guard = np.clip(
            guard_base * 0.35 + np.asarray([25, 235, 80]) * 0.65, 0, 255,
        ).astype(np.uint8)
        self.assertTrue(np.array_equal(pixels[guard_panel_xy[1], guard_panel_xy[0]], expected_guard))

    def test_actual_full_closure_alpha_and_provenance_match_contract(self) -> None:
        specs = diagnostic._variant_specs(
            self.sclera, self.masks, self.prepared.face.plate.shape[:2],
        )
        locks = self.contract["diagnostic"]["actual_compositor_alpha_locks"]
        alpha_audits = {}
        frames = {}
        audits = {}
        right = self.sclera["viewer_right_eye"]
        phase33 = diagnostic.v3.phase35.phase34_candidate09.phase33
        for name in diagnostic.VARIANT_ORDER:
            spec = specs[name]
            canvas = self.prepared.face.plate.copy()
            owner = np.zeros(canvas.shape[:2], dtype=np.uint8)
            with diagnostic._edge_variant(
                self.sclera, spec["hard"], spec["soft"],
                suppress_crease=bool(spec["suppress_crease"]),
            ) as audit:
                phase33._compose_eye_lids(
                    canvas, self.prepared.face.plate,
                    self.prepared.face.phase33_base.lid_texture,
                    owner, right["center"], right["radius"], 1.0,
                )
            call = diagnostic._right_eye_call(audit)
            frames[name] = canvas
            audits[name] = audit
            lower_hash = hashlib.sha256(call["lower_alpha_map"].tobytes()).hexdigest()
            combined = diagnostic.v3._combined_lid_alpha(call["upper_alpha_map"], call["lower_alpha_map"])
            self.assertEqual(lower_hash, locks["viewer_right_lower_alpha_sha256"][name])
            self.assertEqual(
                hashlib.sha256(combined.tobytes()).hexdigest(),
                locks["viewer_right_combined_lid_alpha_sha256"][name],
            )
            self.assertEqual(int((call["lower_alpha_map"] < call["lower_input_alpha_map"]).sum()), 0)
            self.assertTrue(all(row["source_matches_registered_texture"] for row in call["source_coordinate_rows"]))
            self.assertFalse(any(row["neutral_plate_fallback"] for row in call["source_coordinate_rows"]))
        alpha_audits = diagnostic._audit_actual_focus_writes(
            self.contract, self.masks, frames, audits,
        )
        self.assertEqual(alpha_audits["boundary_jumps_u8"]["feather_2px_hard_to_first_exterior"], 85)
        self.assertEqual(alpha_audits["boundary_jumps_u8"]["feather_2px_first_to_second_exterior"], 85)

    def test_partial_closures_are_byte_and_owner_identical(self) -> None:
        right = self.sclera["viewer_right_eye"]
        phase33 = diagnostic.v3.phase35.phase34_candidate09.phase33
        specs = diagnostic._variant_specs(
            self.sclera, self.masks, self.prepared.face.plate.shape[:2],
        )
        for closure in (0.0, 0.25, 0.5, 0.75):
            expected = self.prepared.face.plate.copy()
            expected_owner = np.zeros(expected.shape[:2], dtype=np.uint8)
            expected_result = phase33._compose_eye_lids(
                expected, self.prepared.face.plate,
                self.prepared.face.phase33_base.lid_texture,
                expected_owner, right["center"], right["radius"], closure,
            )
            for name in diagnostic.VARIANT_ORDER[1:]:
                spec = specs[name]
                actual = self.prepared.face.plate.copy()
                actual_owner = np.zeros(actual.shape[:2], dtype=np.uint8)
                with diagnostic._edge_variant(
                    self.sclera, spec["hard"], spec["soft"],
                    suppress_crease=bool(spec["suppress_crease"]),
                ):
                    result = phase33._compose_eye_lids(
                        actual, self.prepared.face.plate,
                        self.prepared.face.phase33_base.lid_texture,
                        actual_owner, right["center"], right["radius"], closure,
                    )
                self.assertEqual(result, expected_result)
                self.assertTrue(np.array_equal(actual, expected), name)
                self.assertTrue(np.array_equal(actual_owner, expected_owner), name)

    def test_prospective_supports_are_locked_and_negative_injection_fails(self) -> None:
        phase36_contract = diagnostic.v3._strict_json(
            diagnostic._repo_path(self.contract["locks"]["phase36_picture_contract"]["path"]),
            "Phase36 contract",
        )
        camera = next(row["camera"] for row in phase36_contract["shots"] if row["id"] == "LP030_COMPASSION_PUNCH")
        supports, audit = diagnostic._prospective_variant_supports(
            self.contract, self.prepared, self.sclera, self.masks, camera,
        )
        self.assertEqual(audit["feather_2px"]["native_rgb"]["area"], 495)
        self.assertEqual(audit["feather_2px"]["native_owner"]["area"], 437)
        support = supports["feather_2px"]["phase36_rgb"]
        injected = np.zeros_like(support)
        y, x = np.argwhere(support)[0]
        injected[y, x] = True
        diagnostic.v3._require_prospective_containment(injected, support, "positive control")
        outside = np.argwhere(~support)[0]
        injected[outside[0], outside[1]] = True
        with self.assertRaises(diagnostic.v3.EyelidDiagnosticError):
            diagnostic.v3._require_prospective_containment(
                injected, support, "one-pixel-outside-bound negative injection",
            )

    def test_v4_files_are_lf_pinned_and_source_has_no_encoder_or_subprocess(self) -> None:
        for relative in (
            diagnostic.CONTRACT_RELATIVE_PATH,
            diagnostic.IMPLEMENTATION_RELATIVE_PATH,
            diagnostic.TEST_RELATIVE_PATH,
        ):
            payload = (diagnostic.REPO_ROOT / relative).read_bytes()
            self.assertNotIn(b"\r\n", payload, relative)
            result = subprocess.run(
                ["git", "check-attr", "text", "eol", "--", relative],
                cwd=diagnostic.REPO_ROOT,
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout
            self.assertIn("text: set", result)
            self.assertIn("eol: lf", result)
        tree = ast.parse((diagnostic.REPO_ROOT / diagnostic.IMPLEMENTATION_RELATIVE_PATH).read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertTrue({"subprocess", "ffmpeg", "moviepy"}.isdisjoint(imported))


if __name__ == "__main__":
    unittest.main()
