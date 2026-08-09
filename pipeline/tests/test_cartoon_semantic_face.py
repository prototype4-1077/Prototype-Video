from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
import json
import unittest

import numpy as np

import pipeline.cartoon_semantic_face as semantic


class SemanticFaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_path = semantic.REPO_ROOT / semantic.CONTRACT_RELATIVE_PATH
        cls.contract = semantic.load_semantic_contract(cls.contract_path)
        cls.prepared = semantic.prepare_semantic_face(cls.contract_path)
        cls.review_path = semantic.REPO_ROOT / cls.contract["preview"]["review_receipt"]
        cls.review = json.loads(cls.review_path.read_text(encoding="utf-8"))

    def test_contract_and_all_dependencies_are_locked(self) -> None:
        self.assertEqual(
            semantic._canonical_hash(self.contract),
            "981c6f44fe675619ca49b9840834ba6eafe782365ed512da59e11b2a3290130e",
        )
        for name, reference in self.contract["locks"].items():
            with self.subTest(name=name):
                path = semantic.REPO_ROOT / reference["path"]
                self.assertEqual(semantic._sha256(path), reference["sha256"])

    def test_contract_mutations_fail_closed(self) -> None:
        mutations = (
            ("representation", "complete_eye_or_mouth_photo_crossfades_allowed", True),
            ("representation", "foreign_atlas_pixels_allowed", True),
            ("representation", "head_motion_allowed", True),
            ("representation", "audio_allowed", True),
            ("failure_policy", "automatic_reencode_allowed", True),
            ("failure_policy", "caller_selected_output_directory_allowed", True),
            ("promotion_policy", "reinforcement_learning_allowed", True),
        )
        for section, key, value in mutations:
            changed = deepcopy(self.contract)
            changed[section][key] = value
            with self.subTest(section=section, key=key):
                with self.assertRaisesRegex(semantic.SemanticFaceError, "complete Phase33 v3 contract"):
                    semantic._validate_contract(changed)

    def test_neutral_frames_are_exact_authored_plate_pixels(self) -> None:
        for frame_number in self.contract["performance"]["exact_neutral_frames"]:
            with self.subTest(frame=frame_number):
                native, evidence = semantic._native_frame(self.prepared, frame_number)
                self.assertTrue(np.array_equal(native, self.prepared.plate))
                self.assertEqual(evidence.changed_pixels, 0)

    def test_blink_is_bilateral_semantic_occlusion(self) -> None:
        before = semantic._native_frame(self.prepared, 8)[1]
        peak = semantic._native_frame(self.prepared, 14)[1]
        after = semantic._native_frame(self.prepared, 19)[1]
        self.assertEqual(before.blink_closure, 0.0)
        self.assertEqual(after.blink_closure, 0.0)
        self.assertEqual(peak.blink_closure, 1.0)
        self.assertGreaterEqual(min(peak.iris_occlusion_ratios), 0.98)
        self.assertGreaterEqual(min(peak.lid_areas), 1700)
        self.assertIn("upper_lids", peak.final_owner_counts)
        self.assertIn("lower_lids", peak.final_owner_counts)

    def test_B_A_F_have_distinct_semantic_anatomy(self) -> None:
        b_pose = semantic._native_frame(self.prepared, 28)[1]
        a_pose = semantic._native_frame(self.prepared, 38)[1]
        f_pose = semantic._native_frame(self.prepared, 48)[1]
        self.assertLessEqual(b_pose.cavity_area, 650)
        self.assertGreaterEqual(a_pose.cavity_area, 2700)
        self.assertGreater(a_pose.tongue_area, 0)
        self.assertGreaterEqual(f_pose.upper_teeth_area, 420)
        self.assertEqual(f_pose.tongue_area, 0)
        self.assertGreater(a_pose.cavity_area, f_pose.cavity_area)

    def test_hair_owns_declared_oral_occlusions(self) -> None:
        a_pose = semantic._native_frame(self.prepared, 38)[1]
        self.assertGreaterEqual(a_pose.moustache_front_overlap, 260)
        self.assertGreaterEqual(a_pose.beard_front_overlap, 8)
        self.assertIn("moustache", a_pose.final_owner_counts)
        self.assertIn("beard_clearance", a_pose.final_owner_counts)
        self.assertEqual(a_pose.multiply_owned_final_pixels, 0)

    def test_all_frames_stay_inside_support_and_local_pop_gate(self) -> None:
        measurements = self.prepared.preflight_measurements
        self.assertEqual(measurements["frames_evaluated"], 60)
        self.assertEqual(measurements["maximum_changed_pixels_outside_feature_support"], 0)
        self.assertLessEqual(measurements["maximum_adjacent_feature_8x8_mean_delta"], 150.0)
        self.assertEqual(measurements["maximum_adjacent_feature_8x8_mean_delta_frame_pair"], [32, 33])

    def test_reviewed_frame_digest_binds_every_raw_frame(self) -> None:
        frame_hashes = []
        for frame_number in range(1, 61):
            with self.subTest(frame=frame_number):
                frame = np.asarray(semantic.compose_semantic_frame(self.prepared, frame_number), dtype=np.uint8)
                frame_hashes.append(semantic._raw_frame_hash(frame))
        digest = hashlib.sha256("".join(frame_hashes).encode("ascii")).hexdigest()
        self.assertEqual(digest, "bf54df3708a316847a33eaa97262d1f01555560f0c03fbc6a56d60b8008ccbfb")
        self.assertEqual(frame_hashes[0], frame_hashes[-1])

    def test_preview_review_receipt_is_commit_bound(self) -> None:
        review = self.review
        self.assertEqual(review["contract_raw_sha256"], semantic._sha256(self.contract_path))
        self.assertEqual(review["contract_canonical_sha256"], semantic._canonical_hash(self.contract))
        self.assertEqual(
            review["implementation_sha256"],
            semantic._sha256(semantic.REPO_ROOT / "pipeline/cartoon_semantic_face.py"),
        )
        self.assertEqual(review["manifest_sha256"], "f3289e31e22e883a4306296d69ebc4829e67e193b99bb19e79bba3bdfc8c65cb")
        self.assertEqual(review["all_60_contact_sheet_sha256"], "eac32f62efb43152fc9229ab33b7c7518562de6cfdd78ff92667c997a33b437f")
        self.assertEqual(review["raw_frame_count_reviewed"], 60)
        self.assertTrue(review["encode_authorization"]["allowed"])
        self.assertFalse(review["encode_authorization"]["automatic_retry_allowed"])

    def test_delivery_path_is_contract_pinned_and_has_no_caller_parameter(self) -> None:
        expected = (semantic.REPO_ROOT / self.contract["delivery"]["output_directory"]).resolve()
        self.assertEqual(semantic._delivery_output_path(self.contract), expected)
        parameters = inspect.signature(semantic.render_semantic_proof).parameters
        self.assertNotIn("output_dir", parameters)
        self.assertNotIn("preview_path", parameters)


if __name__ == "__main__":
    unittest.main()
