from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from pipeline import cartoon_fullmix_audio_successor as successor


class FullMixAudioSuccessorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = Path(tempfile.mkdtemp(prefix="phase42-audio-test-"))
        cls.output = cls.temporary / "package"
        cls.rejected_hash = hashlib.sha256(successor.REJECTED_WAV.read_bytes()).hexdigest()
        cls.report = successor.build(cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.temporary)

    def test_rejected_predecessor_is_immutable_and_still_fails_full_mix_proxy(self) -> None:
        self.assertEqual(
            hashlib.sha256(successor.REJECTED_WAV.read_bytes()).hexdigest(),
            self.rejected_hash,
        )
        rejected = self.report["rejected_measurements"]
        self.assertGreater(
            rejected["noise_proxy"]["broadband_static"]["static_like_window_ratio_all_frames"],
            0.25,
        )
        self.assertGreater(rejected["transient_audit"]["quiet_fixed_threshold_event_count"], 0)

    def test_successors_remove_static_and_quiet_impulses(self) -> None:
        expected_hashes = {
            "balanced_air": "d25975e13d1b1fc873214b342e8abb5065ef7409a2a98b523eee846523ba4357",
            "clean_warm": "518c4f80091b24538fa06dd7679107ff488a311095f2d5327c2cec8738d22eff",
        }
        for name, expected_hash in expected_hashes.items():
            artifact = self.report["variants"][name]
            measured = artifact["measurements"]
            self.assertEqual(artifact["wav_sha256"], expected_hash)
            self.assertEqual(
                measured["noise_proxy"]["broadband_static"]["static_like_window_ratio_all_frames"],
                0.0,
            )
            self.assertEqual(
                measured["noise_proxy"]["broadband_static"]["maximum_static_like_run_seconds"],
                0.0,
            )
            self.assertEqual(measured["transient_audit"]["quiet_fixed_threshold_event_count"], 0)
            self.assertEqual(measured["transient_audit"]["transition_fixed_threshold_event_count"], 0)
            self.assertGreater(measured["transient_audit"]["dialogue_active_fixed_threshold_event_count"], 0)
            self.assertEqual(measured["clipped_channel_values"], 0)

    def test_edit_boundaries_are_not_impulsive(self) -> None:
        for artifact in self.report["variants"].values():
            boundaries = artifact["measurements"]["transient_audit"]["edit_boundaries"]
            self.assertLessEqual(boundaries["pour_to_bridge"]["immediate_adjacent_sample_delta_fs"], 0.001)
            self.assertLessEqual(
                boundaries["bridge_to_direct_address"]["immediate_adjacent_sample_delta_fs"],
                0.005,
            )

    def test_build_is_atomic_and_refuses_overwrite(self) -> None:
        self.assertTrue((self.output / "phase42-fullmix-audio-successor-report-v1.json").is_file())
        with self.assertRaises(successor.FullMixSuccessorError):
            successor.build(self.output)


if __name__ == "__main__":
    unittest.main()
