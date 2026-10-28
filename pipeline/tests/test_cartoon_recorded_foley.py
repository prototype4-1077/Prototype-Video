from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from pipeline import cartoon_recorded_foley as foley


class RecordedFoleyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="phase42-recorded-test-")
        cls.output = Path(cls.temporary.name) / "package"
        # Reusing PCM helpers must not accidentally regenerate the old stems.
        with patch.object(foley.audio, "_dialogue_and_stems", side_effect=AssertionError("legacy synth path")):
            cls.report = foley.build(cls.output)
        cls.read = staticmethod(foley.audio.ledger_pour._read_pcm24_wave)
        cls.mix = cls.read(cls.output / cls.report["artifacts"]["recorded-foley"]["file"])[0]
        cls.effects = cls.read(cls.output / cls.report["artifacts"]["recorded-effects-only"]["file"])[0]
        cls.voice = cls.read(foley.VOICE_PATH)[0]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_clean_voice_is_unchanged_even_under_the_recorded_contact(self) -> None:
        self.assertTrue(np.array_equal(self.mix.astype(np.int64) - self.effects.astype(np.int64), self.voice.astype(np.int64)))
        self.assertEqual(foley._hash(foley.VOICE_PATH), foley.VOICE_SHA256)
        self.assertFalse(np.any(self.voice[:158400]))
        self.assertTrue(self.report["voice"]["pcm_contribution_preserved_exactly"])

    def test_only_two_sample_mapped_cues_with_exact_silence_elsewhere(self) -> None:
        windows = [(25600, 120000), (209600, 235200)]
        self.assertEqual([event["output_sample_range_half_open"] for event in self.report["events"]], [list(window) for window in windows])
        self.assertEqual({event["event_type"] for event in self.report["events"]}, {"coffee_pour", "mug_place"})
        support = np.zeros(foley.COUNT, dtype=bool)
        for start, end in windows:
            support[start:end] = True
            self.assertTrue(np.any(self.effects[start:end]))
            self.assertFalse(np.any(self.effects[start]))
            self.assertFalse(np.any(self.effects[end - 1]))
        self.assertFalse(np.any(self.effects[~support]))
        self.assertTrue(np.array_equal(self.mix[~support], self.voice[~support]))

    def test_rate_duration_headroom_and_real_cut_samples(self) -> None:
        self.assertEqual(self.mix.shape, (484800, 2))
        for artifact in self.report["artifacts"].values():
            self.assertEqual(artifact["probe"]["sample_rate"], 48000)
            self.assertEqual(artifact["probe"]["bits_per_sample"], 24)
            self.assertLess(artifact["peak_dbfs"], -1.0)
            self.assertEqual(artifact["edit_boundary_max_sample_delta"], {"120000": 0.0, "158400": 0.0})
        for boundary in (120000, 158400):
            self.assertFalse(np.any(self.mix[boundary] - self.mix[boundary - 1]))

    def test_sources_and_required_attribution_travel_with_the_audio(self) -> None:
        manifest = foley._sources(foley.SOURCE_ROOT)
        self.assertEqual(len(manifest["sources"]), 2)
        for name, digest in (("sources.json", foley.MANIFEST_SHA256), ("ATTRIBUTION.md", foley.CREDITS_SHA256)):
            self.assertEqual(foley._hash(self.output / name), digest)
        cup = next(source for source in manifest["sources"] if source["id"] == "cup_contact")
        self.assertEqual(cup["license"], "CC BY 4.0")
        self.assertEqual(cup["credit"], "Sound Effect By Nicole Marie T")
        self.assertEqual(cup["license_url"], "https://creativecommons.org/licenses/by/4.0/")
        for event in self.report["events"]:
            self.assertEqual(foley._hash(foley.SOURCE_ROOT / event["file"]), event["sha256"])
            self.assertEqual(event["fade_samples_each_edge"], 1440)
            self.assertTrue(event["source_page"].startswith("https://"))
            self.assertTrue(event["license_url"].startswith("https://"))

    def test_changed_recordings_manifest_and_missing_credits_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase42-source-test-") as temporary:
            root = Path(temporary) / "sources"
            shutil.copytree(foley.SOURCE_ROOT, root)
            raw = root / "nicole_marie_t_cup_on_table_cc_by_4.wav"
            original = raw.read_bytes()
            raw.write_bytes(original[:-1])
            with self.assertRaisesRegex(ValueError, "recorded source bytes changed"):
                foley._sources(root)
            raw.write_bytes(original)
            credits = root / "ATTRIBUTION.md"
            saved = credits.read_bytes()
            credits.write_bytes(b"missing credit")
            with self.assertRaisesRegex(ValueError, "attribution changed"):
                foley._sources(root)
            credits.write_bytes(saved)
            (root / "sources.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "manifest changed"):
                foley._sources(root)

    def test_excerpt_range_and_30ms_edges_are_enforced(self) -> None:
        source = {"decoded_start_sample": 100, "decoded_sample_count": 4000, "mono_peak_dbfs": -25.0}
        signal = foley._faded_excerpt(np.ones((5000, 1)), source)
        self.assertEqual(signal[0], 0.0)
        self.assertEqual(signal[-1], 0.0)
        self.assertLess(signal[500], signal[1440])
        self.assertLess(signal[-500], signal[-1441])
        self.assertAlmostEqual(float(abs(signal).max()), foley.audio._db(-25.0))
        with self.assertRaisesRegex(ValueError, "outside its source"):
            foley._faded_excerpt(np.ones((1000, 1)), source)
        with self.assertRaisesRegex(ValueError, "empty or non-finite"):
            foley._faded_excerpt(np.zeros((5000, 1)), source)

    def test_fresh_build_matches_frozen_candidate_without_claiming_human_acceptance(self) -> None:
        package = foley.REPO_ROOT / "collab/phase42_recorded_foley_v3"
        frozen = json.loads((package / "phase42-recorded-foley-report-v3.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["implementation_sha256"], foley._hash(Path(foley.__file__)))
        for name, artifact in frozen["artifacts"].items():
            self.assertEqual(foley._hash(package / artifact["file"]), artifact["sha256"])
            self.assertEqual(self.report["artifacts"][name]["sha256"], artifact["sha256"])
        self.assertEqual(self.report["network_calls_during_build"], 0)
        self.assertEqual(self.report["video_encoder_processes"], 0)
        self.assertFalse(self.report["human_accepted"])
        self.assertFalse(self.report["promotion_allowed"])
        self.assertIn("not naturalness", self.report["note"])

    def test_existing_audition_cannot_be_overwritten(self) -> None:
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            foley.build(self.output)


if __name__ == "__main__":
    unittest.main()
