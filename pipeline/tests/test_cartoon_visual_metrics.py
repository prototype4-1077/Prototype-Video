from __future__ import annotations

import unittest

import numpy as np

from pipeline.cartoon_visual_metrics import (
    _adjacent_luma_difference,
    _edge_density,
    _global_ssim,
)


class CartoonVisualMetricsTests(unittest.TestCase):
    def test_identical_images_have_perfect_ssim(self) -> None:
        image = np.arange(64, dtype=np.float32).reshape(1, 8, 8)
        self.assertAlmostEqual(_global_ssim(image, image), 1.0)

    def test_adjacent_luma_difference_measures_temporal_change(self) -> None:
        frames = np.stack([
            np.zeros((4, 4), dtype=np.float32),
            np.full((4, 4), 7.0, dtype=np.float32),
            np.full((4, 4), 10.0, dtype=np.float32),
        ])
        self.assertAlmostEqual(_adjacent_luma_difference(frames), 5.0)

    def test_edge_density_is_zero_for_flat_frame(self) -> None:
        image = np.full((1, 8, 8), 128.0, dtype=np.float32)
        self.assertEqual(_edge_density(image), 0.0)

    def test_edge_density_detects_a_step_edge(self) -> None:
        image = np.zeros((1, 8, 8), dtype=np.float32)
        image[:, :, 4:] = 255.0
        self.assertGreater(_edge_density(image), 0.0)


if __name__ == "__main__":
    unittest.main()
