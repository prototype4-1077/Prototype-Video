from __future__ import annotations

from copy import deepcopy
import inspect
import json
import unittest

import pipeline.cartoon_semantic_face_v4 as v4


class SemanticFaceV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_path = v4.REPO_ROOT / v4.CONTRACT_RELATIVE_PATH
        cls.contract = v4.load_contract(cls.contract_path)
        cls.prepared = v4.prepare_v4(cls.contract_path)

    def test_contract_and_rejected_v3_are_locked(self) -> None:
        self.assertEqual(
            v4._canonical_hash(self.contract),
            "cd7c3dda9c6b33b54d458ecb7b354a7a29e8181aee11edcb827f8ddb31dd51cf",
        )
        for name, reference in self.contract["locks"].items():
            with self.subTest(name=name):
                self.assertEqual(v4._sha256(v4.REPO_ROOT / reference["path"]), reference["sha256"])
        receipt = json.loads(
            (v4.REPO_ROOT / self.contract["locks"]["v3_rejection_receipt"]["path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["status"], "encoded_once_full_decode_one_locked_gate_failed_rejected")
        self.assertFalse(receipt["promotion_allowed"])

    def test_all_60_frames_are_byte_identical_to_reviewed_v3(self) -> None:
        required = self.contract["pixel_policy"]["required_exact_rgb_frame_hashes"]
        self.assertEqual(self.prepared.frame_hashes, required)
        self.assertEqual(len(set(required[:8])), 1)
        self.assertEqual(required[0], required[-1])

    def test_preencode_local_motion_is_bounded_before_encoder(self) -> None:
        metrics = self.prepared.preencode_measurements
        self.assertEqual(metrics["maximum_adjacent_face_8x8_mean_delta_frame_pair"], [32, 33])
        self.assertAlmostEqual(metrics["maximum_adjacent_face_8x8_mean_delta"], 139.84375)
        self.assertLessEqual(metrics["maximum_adjacent_face_8x8_mean_delta"], 150.0)
        self.assertLess(150.0, metrics["full_replacement_reference"])

    def test_contract_mutations_fail_closed(self) -> None:
        mutations = (
            ("pixel_policy", "visual_changes_from_reviewed_v3_allowed", True),
            ("motion_evidence", "v4_predeclared_decoded_threshold", 151.0),
            ("failure_policy", "automatic_reencode_allowed", True),
            ("failure_policy", "caller_selected_output_directory_allowed", True),
            ("promotion_policy", "voiced_reencode_allowed", True),
            ("promotion_policy", "reinforcement_learning_allowed", True),
        )
        for section, key, value in mutations:
            changed = deepcopy(self.contract)
            changed[section][key] = value
            with self.subTest(section=section, key=key):
                with self.assertRaisesRegex(v4.SemanticFaceV4Error, "complete Phase33 v4 contract"):
                    v4._validate_contract(changed)

    def test_preview_manifest_and_review_bind_current_v4(self) -> None:
        manifest, review, manifest_path = v4._verify_review(self.prepared)
        self.assertTrue(manifest["pixels_byte_identical_to_reviewed_v3"])
        self.assertEqual(len(manifest["frames"]), 60)
        self.assertEqual(review["manifest_sha256"], v4._sha256(manifest_path))
        self.assertEqual(review["all_60_contact_sheet_sha256"], "eac32f62efb43152fc9229ab33b7c7518562de6cfdd78ff92667c997a33b437f")
        self.assertTrue(review["encode_authorization"]["allowed"])
        self.assertFalse(review["encode_authorization"]["automatic_retry_allowed"])

    def test_decoded_threshold_accepts_prior_intended_motion_but_rejects_over_ceiling(self) -> None:
        base_metrics = {
            "decoded_frame_count": 60,
            "worst_full_frame_psnr_db": 42.0,
            "worst_face_psnr_db": 41.0,
            "worst_face_ssim": 0.99,
            "worst_eye_psnr_db": 41.0,
            "worst_mouth_psnr_db": 41.0,
            "minimum_encoded_laplacian_variance": 280.0,
            "maximum_decoded_adjacent_face_8x8_mean_delta": 141.359375,
        }
        probe = {"streams": [{
            "codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
            "width": 1920, "height": 1080, "nb_frames": "60",
        }]}
        gates = v4._decoded_gates(self.contract, base_metrics, probe)
        self.assertTrue(all(gate["passed"] for gate in gates))
        failed = dict(base_metrics)
        failed["maximum_decoded_adjacent_face_8x8_mean_delta"] = 150.01
        gates = v4._decoded_gates(self.contract, failed, probe)
        local = next(gate for gate in gates if gate["name"] == "decoded_local_temporal_pop")
        self.assertFalse(local["passed"])

    def test_output_is_contract_pinned_and_api_has_no_output_argument(self) -> None:
        expected = (v4.REPO_ROOT / self.contract["delivery"]["output_directory"]).resolve()
        self.assertEqual(v4._output_path(self.contract), expected)
        parameters = inspect.signature(v4.render_v4).parameters
        self.assertNotIn("output_dir", parameters)
        self.assertNotIn("preview_path", parameters)

    def test_acceptance_receipt_is_evidence_bound_and_scope_limited(self) -> None:
        receipt = json.loads(
            (v4.REPO_ROOT / "concept/characters/june_oxley_phase33_acceptance_v4.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["contract"]["raw_sha256"], v4._sha256(self.contract_path))
        self.assertEqual(receipt["contract"]["canonical_sha256"], v4._canonical_hash(self.contract))
        self.assertEqual(receipt["implementation"]["sha256"], v4._sha256(v4.REPO_ROOT / "pipeline/cartoon_semantic_face_v4.py"))
        self.assertEqual(receipt["preview_review"]["sha256"], v4._sha256(v4.REPO_ROOT / self.contract["preview"]["review_receipt"]))
        self.assertTrue(receipt["promotion"]["technical_semantic_proof_candidate"])
        self.assertFalse(receipt["promotion"]["human_full_size_review_completed"])
        self.assertFalse(receipt["promotion"]["accepted_production_delivery"])
        self.assertFalse(receipt["promotion"]["voiced_reencode_allowed"])
        self.assertFalse(receipt["promotion"]["phase32_adapter_allowed"])


if __name__ == "__main__":
    unittest.main()
