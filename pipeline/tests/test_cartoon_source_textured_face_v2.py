from __future__ import annotations

import inspect
import unittest

import pipeline.cartoon_source_textured_face as candidate08
import pipeline.cartoon_source_textured_face_v2 as candidate09


class Candidate09SourceTexturedFaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v1_contract = candidate08.load_contract()
        cls.v2_contract = candidate09.load_contract()

    def test_v2_contract_and_candidate08_provenance_are_pinned(self) -> None:
        self.assertEqual(self.v2_contract["contract_version"], 2)
        self.assertEqual(
            candidate09._canonical_hash(self.v2_contract),
            candidate09.EXPECTED_CONTRACT_CANONICAL_SHA256,
        )
        locks = self.v2_contract["locks"]
        self.assertEqual(locks["candidate08_manifest"]["sha256"], candidate09._locked_source_hash(locks["candidate08_manifest"]))
        self.assertEqual(locks["candidate08_archive"]["sha256"], candidate09._locked_source_hash(locks["candidate08_archive"]))
        self.assertEqual(locks["candidate08_renderer"]["sha256"], candidate09._locked_source_hash(locks["candidate08_renderer"]))
        self.assertEqual(locks["candidate08_attempt_report"]["sha256"], candidate09._locked_source_hash(locks["candidate08_attempt_report"]))
        self.assertEqual(locks["candidate08_attempt_video"]["sha256"], candidate09._locked_source_hash(locks["candidate08_attempt_video"]))

    def test_candidate08_renderer_remains_byte_exact(self) -> None:
        self.assertEqual(
            candidate09._sha256(candidate09.REPO_ROOT / "pipeline/cartoon_source_textured_face.py"),
            "73cd8ab14a474019160ed88a321caaf2164cec35c370dec21c32afba1354c95e",
        )

    def test_candidate09_blink_curve_is_explicit_linear_and_symmetric(self) -> None:
        expected = [0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0]
        actual = [candidate09.blink_closure(self.v2_contract, frame) for frame in range(4, 13)]
        self.assertEqual(actual, expected)
        self.assertEqual(actual, list(reversed(actual)))
        self.assertEqual(candidate09.blink_closure(self.v2_contract, 3), 0.0)
        self.assertEqual(candidate09.blink_closure(self.v2_contract, 13), 0.0)

    def test_only_four_closure_samples_change_from_candidate08(self) -> None:
        changed = [
            frame for frame in range(1, 97)
            if candidate08.blink_closure(self.v1_contract, frame)
            != candidate09.blink_closure(self.v2_contract, frame)
        ]
        self.assertEqual(changed, [5, 7, 9, 11])
        self.assertEqual(self.v2_contract["preencode_gates"]["required_candidate08_changed_frames"], changed)
        self.assertEqual(self.v2_contract["preencode_gates"]["required_candidate08_preserved_frame_hashes"], 92)

    def test_all_96_mouth_controls_are_unchanged(self) -> None:
        for frame in range(1, 97):
            with self.subTest(frame=frame):
                v1_pose, v1_weights = candidate08.mouth_controls(self.v1_contract, frame)
                v2_pose, v2_weights = candidate09.mouth_controls(self.v2_contract, frame)
                self.assertEqual(v1_pose, v2_pose)
                self.assertEqual(v1_weights, v2_weights)

    def test_source_and_future_decoded_temporal_ceilings_are_tightened(self) -> None:
        gates = self.v2_contract["preencode_gates"]
        self.assertEqual(gates["maximum_adjacent_feature_8x8_mean_delta"], 145.0)
        self.assertEqual(gates["maximum_output_adjacent_face_8x8_mean_delta"], 145.0)
        self.assertEqual(gates["maximum_output_blink_adjacent_face_8x8_mean_delta"], 130.0)
        self.assertEqual(self.v2_contract["decoded_gates"]["maximum_decoded_adjacent_face_8x8_mean_delta"], 145.0)

    def test_v2_is_preview_only_and_has_no_encoder(self) -> None:
        source = inspect.getsource(candidate09)
        self.assertNotIn("subprocess.Popen", source)
        self.assertNotIn("ffmpeg", source.lower())
        self.assertIn("final_encode_allowed_without_bound_review_receipt", source)
        self.assertNotEqual(candidate09.IMPLEMENTATION_RELATIVE_PATH, candidate08.IMPLEMENTATION_RELATIVE_PATH)

    def test_candidate09_preview_label_is_pinned(self) -> None:
        with self.assertRaises(candidate09.SourceTexturedFaceError):
            candidate09._preview_output_path(self.v2_contract, None)
        with self.assertRaises(candidate09.SourceTexturedFaceError):
            candidate09._preview_output_path(self.v2_contract, "candidate-10")
        self.assertTrue(
            candidate09._preview_output_path(self.v2_contract, "candidate-09").name.endswith("candidate-09")
        )


if __name__ == "__main__":
    unittest.main()
