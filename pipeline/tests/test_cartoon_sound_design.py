from __future__ import annotations

import unittest

import numpy as np

from pipeline.cartoon_sound_design import render_stem, validate_profile


def _profile() -> dict:
    return {
        "contract_version": 1,
        "duration_seconds": 0.2,
        "sample_rate": 8000,
        "channels": 2,
        "seed": 17,
        "target_peak_dbfs": -12.0,
        "mix": {
            "dialogue_gain_db": 0.0,
            "foley_gain_db": 0.0,
            "limiter_peak": 0.95,
            "sample_rate": 8000,
        },
        "events": [
            {
                "id": "tone",
                "type": "room_tone",
                "time_seconds": 0.0,
                "duration_seconds": 0.2,
                "gain_db": -20.0,
                "pan": 0.0,
            }
        ],
    }


class CartoonSoundDesignTests(unittest.TestCase):
    def test_render_is_deterministic_stereo_and_bounded(self) -> None:
        first = render_stem(_profile())
        second = render_stem(_profile())
        self.assertEqual(first.shape, (1600, 2))
        self.assertTrue(np.array_equal(first, second))
        self.assertLessEqual(float(np.max(np.abs(first))), 10 ** (-12.0 / 20.0) + 1e-6)

    def test_rejects_out_of_clock_event(self) -> None:
        profile = _profile()
        profile["events"][0]["time_seconds"] = 0.1
        with self.assertRaisesRegex(ValueError, "outside the scene clock"):
            validate_profile(profile)

    def test_rejects_invalid_pan(self) -> None:
        profile = _profile()
        profile["events"][0]["pan"] = 1.1
        with self.assertRaisesRegex(ValueError, "pan"):
            validate_profile(profile)


if __name__ == "__main__":
    unittest.main()
