from __future__ import annotations

import unittest

import numpy as np

from pipeline.cartoon_delivery_audit import hold_metrics, validate_contract


class CartoonDeliveryAuditTests(unittest.TestCase):
    def test_accepts_exact_source_contract(self) -> None:
        contract = {
            "width": 960,
            "height": 540,
            "fps": 30.0,
            "frame_count": 453,
            "duration_seconds": 15.1,
            "audio": False,
            "audio_sample_rate": 0,
            "audio_channels": 0,
        }
        validate_contract(
            contract,
            width=960,
            height=540,
            fps=30,
            frame_count=453,
            require_audio=False,
        )

    def test_rejects_delivery_without_required_audio(self) -> None:
        contract = {
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "frame_count": 453,
            "duration_seconds": 15.1,
            "audio": False,
            "audio_sample_rate": 0,
            "audio_channels": 0,
        }
        with self.assertRaisesRegex(ValueError, "missing required audio"):
            validate_contract(
                contract,
                width=1920,
                height=1080,
                fps=30,
                frame_count=453,
                require_audio=True,
            )

    def test_identical_hold_frames_are_perfectly_stable(self) -> None:
        frame = np.full((100, 120, 3), 128, dtype=np.uint8)
        metrics = hold_metrics([frame, frame.copy(), frame.copy()])
        self.assertAlmostEqual(metrics["upper_face_first_last_ssim"], 1.0)
        self.assertEqual(metrics["upper_face_adjacent_luma_mean"], 0.0)
        self.assertEqual(metrics["left_wall_adjacent_luma_max"], 0.0)


if __name__ == "__main__":
    unittest.main()
