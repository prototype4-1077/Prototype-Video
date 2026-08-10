from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import numpy as np

import pipeline.cartoon_reconstruction_locked_textured_mechanics as phase32

from pipeline.cartoon_reconstruction_locked_textured_mechanics import (
    CONTRACT_RELATIVE_PATH,
    REGION_IDS,
    REPO_ROOT,
    ReconstructionLockedTexturedMechanicsError,
    _assert_locked_frame_inputs,
    _canonical_hash,
    _flatten_quality_gates,
    _gate_results,
    _linear_premultiplied_to_rgba,
    _occupied_alpha,
    _prepare_dependencies,
    _deformation_gradient_metrics,
    _registered_character,
    _remove_registration_ringing_speckles,
    _resolve_transported_ownership,
    _rgba_to_linear_premultiplied,
    _sha256,
    _visible_seam_metrics,
    _validate_contract,
    _warp_binary_lower,
    load_reconstruction_locked_textured_contract,
    render_textured_mechanics_frame,
    render_reconstruction_locked_textured_mechanics,
)


class ReconstructionLockedTexturedMechanicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_reconstruction_locked_textured_contract(
            REPO_ROOT / CONTRACT_RELATIVE_PATH
        )
        (
            cls.phase30_contract,
            cls.phase31_contract,
            cls.patches,
            cls.source,
            cls.environment,
        ) = _prepare_dependencies(cls.contract)
        cls.reference_registered, _, _ = _registered_character(
            cls.source, cls.phase31_contract
        )

    def test_contract_hash_locks_and_gate_inventory_are_exact(self) -> None:
        self.assertEqual(
            _canonical_hash(self.contract),
            "08c455de7b6f3511d15b19886606cc22d977b2397aaa81bf7d32fa41fc635535",
        )
        for identifier in (
            "phase30_contract",
            "phase30_implementation",
            "phase31_contract",
            "phase31_implementation",
            "phase31_acceptance_receipt",
            "phase32_rejected_delivery_receipt",
            "phase32_superseded_delivery_receipt",
            "accepted_character_source",
            "clean_environment",
        ):
            reference = self.contract["locks"][identifier]
            self.assertEqual(
                _sha256((REPO_ROOT / reference["path"]).resolve()),
                reference["sha256"],
            )
        self.assertEqual(len(_flatten_quality_gates(self.contract)), 76)
        self.assertEqual(set(self.patches), set(REGION_IDS))

    def test_contract_rejects_gate_and_retry_mutations(self) -> None:
        mutations = []
        changed_gate = deepcopy(self.contract)
        changed_gate["quality_gates"]["geometry"][
            "minimum_registered_character_alpha_iou_to_phase31"
        ] = 0.5
        mutations.append(changed_gate)
        changed_retry = deepcopy(self.contract)
        changed_retry["delivery"]["one_encode_without_retry"] = False
        mutations.append(changed_retry)
        changed_failure = deepcopy(self.contract)
        changed_failure["failure_policy"]["automatic_reencode_allowed"] = True
        mutations.append(changed_failure)
        for value in mutations:
            with self.subTest(value=value["contract_id"]):
                with self.assertRaisesRegex(
                    ReconstructionLockedTexturedMechanicsError,
                    "complete Phase32 contract",
                ):
                    _validate_contract(value)

    def test_premultiplied_roundtrip_and_transparent_rgb_zeroing(self) -> None:
        random = np.random.default_rng(32)
        rgba = random.integers(0, 256, size=(32, 64, 4), dtype=np.uint8)
        rgba[:, :8, 3] = 0
        decoded = _linear_premultiplied_to_rgba(
            _rgba_to_linear_premultiplied(rgba)
        )
        opaque_or_translucent = rgba[:, :, 3] > 0
        self.assertTrue(np.array_equal(decoded[:, :, 3], rgba[:, :, 3]))
        self.assertTrue(
            np.array_equal(
                decoded[:, :, :3][opaque_or_translucent],
                rgba[:, :, :3][opaque_or_translucent],
            )
        )
        self.assertFalse(np.any(decoded[:, :, :3][~opaque_or_translucent]))
        invalid = np.zeros((1, 1, 4), dtype=np.float32)
        invalid[0, 0, 0] = np.nan
        with self.assertRaises(ReconstructionLockedTexturedMechanicsError):
            _linear_premultiplied_to_rgba(invalid)

    def test_owner_resolution_is_single_priority_and_fail_closed(self) -> None:
        first = REGION_IDS[0]
        second = REGION_IDS[1]
        supports = {
            identifier: np.zeros((3, 4), dtype=bool) for identifier in REGION_IDS
        }
        transported = {
            identifier: np.zeros((3, 4), dtype=bool) for identifier in REGION_IDS
        }
        supports[first][1, 1:3] = True
        supports[second][1, 2:4] = True
        transported[first][1, 1:3] = True
        transported[second][1, 2:4] = True
        desired = supports[first] | supports[second]
        owner, fallback, metrics = _resolve_transported_ownership(
            supports,
            transported,
            [first, second, *REGION_IDS[2:]],
            desired_geometry=desired,
        )
        self.assertEqual(owner[1, 2], REGION_IDS.index(first))
        self.assertFalse(np.any(fallback))
        self.assertEqual(metrics["selected_owners_per_occupied_pixel_minimum"], 1)
        self.assertEqual(metrics["selected_owners_per_occupied_pixel_maximum"], 1)
        self.assertEqual(metrics["multiply_composited_character_pixels"], 0)
        self.assertEqual(metrics["phase31_geometry_pixels_uncovered"], 0)

    def test_registration_cleanup_removes_only_one_pixel_ringing(self) -> None:
        rgba = np.zeros((20, 24, 4), dtype=np.uint8)
        rgba[4:16, 5:18] = (80, 90, 100, 255)
        rgba[1, 1] = (40, 50, 60, 17)
        rgba[1, 20:22] = (40, 50, 60, 17)
        cleaned, removed = _remove_registration_ringing_speckles(rgba, 1)
        self.assertEqual(removed, 1)
        self.assertTrue(np.array_equal(cleaned[1, 1], np.zeros(4, dtype=np.uint8)))
        self.assertTrue(np.all(cleaned[1, 20:22, 3] == 17))
        self.assertTrue(np.all(cleaned[4:16, 5:18, 3] == 255))

    def test_lower_owner_roi_covers_translation_beyond_old_margin(self) -> None:
        mask = np.zeros((160, 180), dtype=bool)
        mask[35:105, 40:130] = True
        controls = np.asarray(
            ((45, 40), (85, 70), (120, 45), (55, 100), (120, 100)),
            dtype=np.float64,
        )
        destination = controls + np.asarray((40.0, 20.0))
        moved = _warp_binary_lower(mask, mask, controls, destination)
        expected = np.zeros_like(mask)
        expected[55:125, 80:170] = True
        self.assertTrue(np.array_equal(moved, expected))

    def test_gate_evaluator_has_exact_fail_closed_schema(self) -> None:
        measurements: dict[str, dict[str, object]] = {}
        for section, gates in self.contract["quality_gates"].items():
            measurements[section] = {}
            for gate, threshold in gates.items():
                if gate.startswith("minimum_"):
                    metric = gate[len("minimum_") :]
                    if f"maximum_{metric}" in gates:
                        metric += "__minimum"
                elif gate.startswith("maximum_"):
                    metric = gate[len("maximum_") :]
                    if f"minimum_{metric}" in gates:
                        metric += "__maximum"
                else:
                    metric = gate[len("required_") :]
                measurements[section][metric] = threshold
        rows = _gate_results(self.contract, measurements)
        self.assertEqual(len(rows), 76)
        self.assertTrue(all(row["passed"] for row in rows))
        self.assertTrue(
            all(
                set(row) == {"id", "measured", "operator", "threshold", "passed"}
                for row in rows
            )
        )
        measurements["geometry"][
            "registered_character_alpha_iou_to_phase31"
        ] = None
        failed = _gate_results(self.contract, measurements)
        self.assertFalse(
            next(
                row
                for row in failed
                if row["id"]
                == "geometry.minimum_registered_character_alpha_iou_to_phase31"
            )["passed"]
        )

    def test_alpha_occupancy_boundary_is_exact_and_shared(self) -> None:
        alpha = np.asarray([0, 1, 16, 17, 255], dtype=np.uint8)
        self.assertTrue(
            np.array_equal(
                _occupied_alpha(alpha),
                np.asarray([False, False, False, True, True]),
            )
        )
        premultiplied = alpha.astype(np.float32) / 255.0
        self.assertTrue(
            np.array_equal(
                _occupied_alpha(premultiplied),
                np.asarray([False, False, False, True, True]),
            )
        )

    def test_empty_required_seam_band_is_not_reported_as_zero_error(self) -> None:
        first, second = REGION_IDS[:2]
        owner = np.full((8, 12), -1, dtype=np.int16)
        owner[:, :6] = REGION_IDS.index(first)
        owner[:, 6:] = REGION_IDS.index(second)
        candidates = {
            identifier: np.zeros((8, 12, 4), dtype=np.float32)
            for identifier in REGION_IDS
        }
        candidates[first][:, :6, 3] = 1.0
        candidates[second][:, 6:, 3] = 1.0
        source_masks = {
            identifier: np.zeros((8, 12), dtype=bool)
            for identifier in REGION_IDS
        }
        source_masks[first][:, :6] = True
        source_masks[second][:, 6:] = True
        transforms = {
            identifier: np.eye(3, dtype=np.float64)
            for identifier in REGION_IDS
        }
        phase31_frame = SimpleNamespace(
            source_region_masks=source_masks,
            region_transforms=transforms,
            cage_controls={},
        )
        rows, disagreement, divergence = _visible_seam_metrics(
            owner, candidates, phase31_frame, [[first, second]]
        )
        row = rows[f"{first}__{second}"]
        self.assertFalse(row["evaluable"])
        self.assertEqual(row["boundary_band_pixels"], 0)
        self.assertIsNone(row["candidate_rgb_disagreement_p95"])
        self.assertIsNone(
            row["cross_owner_source_coordinate_divergence_p95_px"]
        )
        self.assertEqual(disagreement, 0.0)
        self.assertEqual(divergence, 0.0)

    def test_lower_garment_jacobian_evidence_covers_every_support_pixel(self) -> None:
        phase31_frame = phase32.render_flat_mechanics_frame(
            self.phase31_contract, self.patches, 19
        )
        try:
            evidence = _deformation_gradient_metrics(
                self.patches, phase31_frame
            )["jacobian_evidence"]["lower_garment"]
            self.assertGreater(evidence["eligible_jacobian_count"], 256)
            self.assertEqual(
                evidence["evaluated_jacobian_count"],
                evidence["eligible_jacobian_count"],
            )
            self.assertEqual(evidence["coverage_fraction"], 1.0)
        finally:
            phase31_frame.close()

    def test_contract_loading_does_not_require_external_media(self) -> None:
        original = phase32._locked_path
        labels: list[str] = []

        def capture(reference: dict[str, object], label: str) -> Path:
            labels.append(label)
            return original(reference, label)

        with mock.patch.object(phase32, "_locked_path", side_effect=capture):
            loaded = load_reconstruction_locked_textured_contract(
                REPO_ROOT / CONTRACT_RELATIVE_PATH
            )
        self.assertEqual(loaded["contract_id"], self.contract["contract_id"])
        self.assertFalse(
            any(
                label.startswith("accepted Phase31 report")
                or label.startswith("accepted Phase31 video")
                or label.startswith("rejected Phase32 report")
                or label.startswith("rejected Phase32 video")
                for label in labels
            )
        )

    def test_endpoints_are_byte_exact_and_injected_patch_is_rejected(self) -> None:
        frames = []
        for frame_number in (1, 49):
            rendered = render_textured_mechanics_frame(
                self.contract,
                self.patches,
                frame_number,
                phase31_contract=self.phase31_contract,
                source_reconstruction=self.source,
                environment_rgb=self.environment,
                reference_registered=self.reference_registered,
                _prepared_dependencies_verified=True,
            )
            frames.append(rendered)
        try:
            for rendered in frames:
                self.assertTrue(np.array_equal(rendered.raw_character_rgba, self.source))
                self.assertEqual(
                    hashlib.sha256(rendered.registered_character_rgba.tobytes()).hexdigest(),
                    self.contract["locks"][
                        "phase30_registered_rest_rgba_bytes_sha256"
                    ],
                )
                self.assertEqual(
                    rendered.texture_metrics[
                        "endpoint_registered_rgba_mismatched_pixels"
                    ],
                    0,
                )
            self.assertTrue(
                np.array_equal(
                    frames[0].registered_character_rgba,
                    frames[1].registered_character_rgba,
                )
            )
        finally:
            for rendered in frames:
                rendered.close()
        corrupt = dict(self.patches)
        rgba = corrupt["left_sleeve"].rgba.copy()
        rgba[0, 0, 0] ^= np.uint8(1)
        corrupt["left_sleeve"] = replace(corrupt["left_sleeve"], rgba=rgba)
        with self.assertRaisesRegex(
            ReconstructionLockedTexturedMechanicsError, "differs from the locked Phase30 patch"
        ):
            _assert_locked_frame_inputs(
                self.contract, corrupt, self.source, self.environment
            )

    def test_delivery_transaction_calls_encoder_once_and_publishes_atomically(self) -> None:
        contract = deepcopy(self.contract)
        contract["delivery"]["output_directory"] = "phase32-test-output"
        gate_rows = [
            {
                "id": identifier,
                "measured": threshold,
                "operator": "==",
                "threshold": threshold,
                "passed": True,
            }
            for identifier, threshold in _flatten_quality_gates(contract).items()
        ]
        report = {
            "contract_id": contract["contract_id"],
            "proof": {},
            "dependencies": {},
            "geometry": {},
            "premultiplication": {},
            "ownership": {},
            "deformation": {},
            "texture": {},
            "delivery": {},
            "gate_results": gate_rows,
            "preflight_passed": True,
            "machine_passed": False,
            "audience_quality": {},
            "cash_cost": 0,
            "paid_runtime_dependency": False,
        }
        cache = {
            "beauty_frames": [],
            "subject_masks_output": [],
            "face_boxes_source": [],
            "review_metadata": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def fake_encode(
                frames: list[np.ndarray],
                path: Path,
                executable: str,
                delivery_contract: dict[str, object],
            ) -> None:
                self.assertFalse(path.exists())
                self.assertEqual(delivery_contract["delivery_attempt_version"], 3)
                path.write_bytes(b"phase32-test-video")

            with (
                mock.patch.object(phase32, "REPO_ROOT", root),
                mock.patch.object(phase32, "_validate_contract"),
                mock.patch.object(phase32, "_resolve_executable", return_value="tool"),
                mock.patch.object(
                    phase32,
                    "_run_textured_preflight",
                    return_value=(deepcopy(report), cache),
                ),
                mock.patch.object(
                    phase32, "_encode_h264_once", side_effect=fake_encode
                ) as encode,
                mock.patch.object(phase32, "_probe_video", return_value={}),
                mock.patch.object(
                    phase32,
                    "_probe_measurements",
                    return_value={"width": 1920, "height": 1080},
                ),
                mock.patch.object(
                    phase32,
                    "_decode_and_audit",
                    return_value=({"decoded_frame_count": 49}, {}),
                ),
                mock.patch.object(
                    phase32, "_write_decoded_review_artifacts", return_value={}
                ),
                mock.patch.object(phase32, "_gate_results", return_value=gate_rows),
            ):
                delivered = render_reconstruction_locked_textured_mechanics(contract)
            self.assertEqual(encode.call_count, 1)
            final = root / "phase32-test-output"
            self.assertTrue(final.is_dir())
            self.assertTrue((final / contract["delivery"]["video_filename"]).is_file())
            self.assertTrue((final / contract["delivery"]["report_filename"]).is_file())
            self.assertTrue(delivered["machine_passed"])


if __name__ == "__main__":
    unittest.main()
