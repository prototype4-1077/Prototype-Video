import unittest

import numpy as np

from pipeline import cartoon_audio_noise_proxy as proxy


class AudibleNoiseProxyTests(unittest.TestCase):
    sample_rate = 48_000

    def _pcm(self, values: np.ndarray) -> np.ndarray:
        mono = np.clip(values, -1.0, 1.0)
        stereo = np.column_stack([mono, mono])
        return np.round(stereo * proxy.PCM24_MAX).astype(np.int32)

    def test_full_mix_coverage_includes_non_hop_aligned_tail(self) -> None:
        time = np.arange(48_123, dtype=np.float64) / self.sample_rate
        measured = proxy.audible_noise_proxy(self._pcm(0.002 * np.sin(2.0 * np.pi * 440.0 * time)))
        self.assertTrue(measured["coverage_complete"])
        self.assertEqual(measured["coverage_start_sample"], 0)
        self.assertEqual(measured["coverage_end_sample_exclusive"], 48_123)

    def test_broadband_static_is_detected_outside_historical_focus(self) -> None:
        count = round(10.1 * self.sample_rate)
        time = np.arange(count, dtype=np.float64) / self.sample_rate
        values = 0.001 * np.sin(2.0 * np.pi * 310.0 * time)
        rng = np.random.default_rng(20260811)
        start, end = round(6.0 * self.sample_rate), round(6.8 * self.sample_rate)
        values[start:end] += rng.normal(0.0, 0.013, end - start)
        measured = proxy.audible_noise_proxy(self._pcm(values))
        static = measured["broadband_static"]
        self.assertGreater(static["maximum_static_like_run_seconds"], 0.70)
        self.assertGreaterEqual(static["first_static_like_start_seconds"], 5.95)
        self.assertLessEqual(static["first_static_like_start_seconds"], 6.05)

    def test_band_limited_wind_is_not_classified_as_broadband_static(self) -> None:
        count = round(0.9 * self.sample_rate)
        rng = np.random.default_rng(7)
        white = rng.normal(0.0, 0.01, count + 256)
        kernel = np.ones(257, dtype=np.float64) / 257.0
        wind = np.convolve(white, kernel, mode="valid")[:count]
        measured = proxy.audible_noise_proxy(self._pcm(wind))
        self.assertEqual(measured["broadband_static"]["static_like_frame_count"], 0)

    def test_impulsive_crackle_is_reported(self) -> None:
        count = round(1.0 * self.sample_rate)
        time = np.arange(count, dtype=np.float64) / self.sample_rate
        values = 0.001 * np.sin(2.0 * np.pi * 220.0 * time)
        values[31_000] += 0.6
        measured = proxy.audible_noise_proxy(self._pcm(values))
        self.assertGreaterEqual(measured["crackle"]["impulsive_crackle_event_count"], 1)

    def test_interval_proxy_binds_declared_sample_span(self) -> None:
        values = self._pcm(np.zeros(8_000, dtype=np.float64))
        measured = proxy.interval_noise_proxy(values, 1_000, 7_000)
        self.assertEqual(measured["source_interval"]["start_sample"], 1_000)
        self.assertEqual(measured["source_interval"]["end_sample_exclusive"], 7_000)

    def test_float_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(proxy.AudioNoiseProxyError, "signed integer PCM"):
            proxy.audible_noise_proxy(np.zeros((4_096, 2), dtype=np.float64))


if __name__ == "__main__":
    unittest.main()
