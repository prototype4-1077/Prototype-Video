from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from pipeline import cartoon_audio_stem_isolation as isolation


class AudioStemIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="phase42-isolation-test-")
        cls.output = Path(cls.temporary.name) / "package"
        cls.report = isolation.build(cls.output)
        cls.pcm = {
            name: isolation.predecessor.ledger_pour._read_pcm24_wave(cls.output / entry["file"])[0]
            for name, entry in cls.report["artifacts"].items()
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_reconstruction_matches_exact_human_rejected_reference(self) -> None:
        self.assertEqual(isolation._hash(isolation.REFERENCE), isolation.REFERENCE_SHA256)
        self.assertEqual(self.report["source_audit"]["maximum_reconstruction_error_pcm24_units"], 0)
        reference, _ = isolation.predecessor.ledger_pour._read_pcm24_wave(isolation.REFERENCE)
        recombined = self.pcm["porch_bed_removed"].astype(np.int64) + self.pcm["porch_bed_only"].astype(np.int64)
        self.assertLessEqual(int(np.abs(recombined - reference.astype(np.int64)).max()), 2)

    def test_voice_is_isolated_without_retiming_or_new_normalization(self) -> None:
        voice = self.pcm["voice_only"]
        self.assertFalse(np.any(voice[:158400]))
        self.assertTrue(np.any(voice[158400:]))
        self.assertTrue(np.array_equal(voice[:, 0], voice[:, 1]))
        self.assertEqual(self.report["source_audit"]["dialogue_start_sample"], 158400)
        components, _, audit = isolation._components()
        self.assertTrue(np.array_equal(voice, isolation.predecessor._to_pcm24(components["voice"])))
        self.assertEqual(audit["shared_reference_gain"], self.report["source_audit"]["shared_reference_gain"])

    def test_bed_is_present_before_speech_and_in_every_output_frame_despite_old_proxy_zero(self) -> None:
        bed = self.report["artifacts"]["porch_bed_only"]
        self.assertEqual(bed["nonzero_output_frames"], 303)
        self.assertGreater(bed["opening_rms_dbfs"], -60.0)
        self.assertEqual(bed["measurements"]["noise_proxy"]["broadband_static"]["static_like_window_ratio_all_frames"], 0.0)
        self.assertFalse(self.report["human_accepted"])
        self.assertFalse(self.report["promotion_allowed"])
        self.assertEqual(self.report["reviewed_reference"]["human_verdict"], "STATIC_REMAINS_THROUGHOUT")

    def test_all_files_keep_the_same_pcm_clock_and_no_clipping(self) -> None:
        for name, entry in self.report["artifacts"].items():
            self.assertEqual(self.pcm[name].shape, (484800, 2))
            self.assertEqual(entry["probe"]["sample_rate"], 48000)
            self.assertEqual(entry["probe"]["bits_per_sample"], 24)
            self.assertEqual(entry["measurements"]["clipped_channel_values"], 0)
            self.assertLess(float(np.max(np.abs(self.pcm[name].astype(np.int64)))), isolation.MAX_PCM)

    def test_fresh_build_matches_frozen_proof_and_actual_implementation(self) -> None:
        package = isolation.REPO_ROOT / "collab/phase42_audio_source_isolation_v1"
        frozen = json.loads((package / "phase42-audio-source-isolation-report-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["implementation_sha256"], isolation._hash(Path(isolation.__file__)))
        for name, entry in frozen["artifacts"].items():
            data = (package / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
            self.assertEqual(len(data), entry["bytes"])
            self.assertEqual(self.report["artifacts"][name]["sha256"], entry["sha256"])

    def test_existing_output_refuses_overwrite(self) -> None:
        with self.assertRaisesRegex(isolation.AudioIsolationError, "refusing to overwrite"):
            isolation.build(self.output)


if __name__ == "__main__":
    unittest.main()
