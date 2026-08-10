from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import ImageChops

import pipeline.cartoon_close_facial_acting_v2 as phase33v2


class CorrectiveFacialActingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract_path = phase33v2.REPO_ROOT / phase33v2.CONTRACT_RELATIVE_PATH
        cls.contract = phase33v2.load_corrective_contract(cls.contract_path)
        cls.prepared = phase33v2.prepare_corrective_shot(cls.contract_path)

    def test_complete_v2_contract_and_rejected_v1_are_locked(self) -> None:
        self.assertEqual(
            phase33v2._canonical_hash(self.contract),
            "00d127a19db8f7ee9fadb4559ab4d4401e8f324e138dfd40049a28c61de03c59",
        )
        for name, reference in self.contract["locks"].items():
            with self.subTest(name=name):
                path = phase33v2.REPO_ROOT / reference["path"]
                self.assertEqual(phase33v2._sha256(path), reference["sha256"])
        rejected = json.loads(
            (phase33v2.REPO_ROOT / self.contract["locks"]["rejected_delivery_v1"]["path"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(rejected["status"], "machine_passed_ai_visual_review_rejected")

    def test_neutral_and_x_are_exact_authored_plate_pixels(self) -> None:
        metrics = self.prepared.preflight_measurements
        self.assertEqual(metrics["neutral_source_changed_pixels"], 0)
        self.assertEqual(metrics["x_source_changed_pixels"], 0)

    def test_overlap_has_one_declared_owner_and_no_out_of_scope_pixels(self) -> None:
        metrics = self.prepared.preflight_measurements
        self.assertGreater(metrics["feature_overlap_pixel_count"], 10000)
        self.assertEqual(metrics["multiply_owned_overlap_pixels"], 0)
        self.assertEqual(metrics["maximum_changed_pixels_outside_owned_feature_support"], 0)
        self.assertGreater(metrics["stable_identity_pixels"], 200000)

    def test_corrective_pixels_prove_blink_mouth_motion_and_bounded_steps(self) -> None:
        metrics = self.prepared.preflight_measurements
        self.assertGreater(metrics["bilateral_blink_mean_absolute_delta"], 8.0)
        self.assertGreater(metrics["non_x_observed_frame_count"], 40)
        self.assertLessEqual(metrics["maximum_adjacent_mouth_corrective_mean_absolute_delta"], 11.0)
        self.assertLessEqual(metrics["maximum_adjacent_expression_corrective_mean_absolute_delta"], 18.0)

    def test_corrective_contract_mutations_fail_closed(self) -> None:
        for section, key, value in (
            ("corrective_compositing", "mouth_owns_expression_overlap", False),
            ("corrective_compositing", "rgb_crop_painter_order_allowed", True),
            ("promotion_policy", "accepted_delivery_publication_allowed", True),
            ("failure_policy", "automatic_reencode_allowed", True),
        ):
            changed = deepcopy(self.contract)
            changed[section][key] = value
            with self.subTest(section=section, key=key):
                with self.assertRaisesRegex(
                    phase33v2.CorrectiveFacialActingError,
                    "complete Phase33 v2 contract",
                ):
                    phase33v2._validate_contract(changed)

    def test_corrective_frame_differs_during_speech_and_settles(self) -> None:
        neutral = phase33v2.compose_corrective_frame(self.prepared, 1)
        speech = phase33v2.compose_corrective_frame(self.prepared, 82)
        settle = phase33v2.compose_corrective_frame(self.prepared, 228)
        self.assertIsNotNone(ImageChops.difference(neutral, speech).getbbox())
        self.assertEqual(settle.size, (1920, 1080))

    def test_missing_preview_blocks_encoder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate"
            missing = Path(directory) / "missing.png"
            with mock.patch.object(phase33v2, "_encode_once") as encoder:
                with self.assertRaisesRegex(
                    phase33v2.CorrectiveFacialActingError,
                    "preview must exist",
                ):
                    phase33v2.render_corrective_shot(
                        self.contract_path,
                        output,
                        preview_path=missing,
                        baseline_v1=missing,
                    )
            encoder.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
