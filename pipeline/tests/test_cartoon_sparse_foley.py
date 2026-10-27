from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from pipeline import cartoon_sparse_foley as foley


class SparseFoleyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="phase42-foley-test-")
        cls.output = Path(cls.temporary.name) / "package"
        cls.report = foley.build(cls.output)
        read = foley.isolation.predecessor.ledger_pour._read_pcm24_wave
        cls.mix = read(cls.output / cls.report["artifacts"]["sparse-foley"]["file"])[0]
        cls.effects = read(cls.output / cls.report["artifacts"]["sparse-effects-only"]["file"])[0]
        cls.voice = read(foley.VOICE_PATH)[0]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_clean_voice_is_an_exact_unchanged_additive_component(self) -> None:
        self.assertTrue(np.array_equal(self.mix.astype(np.int64) - self.effects.astype(np.int64), self.voice.astype(np.int64)))
        self.assertEqual(foley._hash(foley.VOICE_PATH), foley.VOICE_SHA256)
        self.assertFalse(np.any(self.voice[:158400]))
        self.assertTrue(self.report["voice"]["pcm_contribution_preserved_exactly"])

    def test_noise_based_effects_and_continuous_bed_are_excluded(self) -> None:
        self.assertTrue({"breath", "cloth_rustle", "porch_ambience"}.issubset(self.report["omitted_types"]))
        self.assertEqual({event["type"] for event in self.report["events"]}, foley.SYNTHETIC_TYPES)
        tree = ast.parse(Path(foley.__file__).read_text(encoding="utf-8"))
        self.assertFalse(any(isinstance(node, ast.Attribute) and node.attr == "normal" for node in ast.walk(tree)))
        self.assertTrue(np.any(self.effects))

    def test_same_clock_safe_headroom_and_click_free_edit_samples(self) -> None:
        self.assertEqual(self.mix.shape, (484800, 2))
        for artifact in self.report["artifacts"].values():
            self.assertEqual(artifact["probe"]["sample_rate"], 48000)
            self.assertEqual(artifact["probe"]["bits_per_sample"], 24)
            self.assertLess(artifact["peak_dbfs"], -1.0)
        for boundary in (120000, 158400):
            jump = np.abs(self.mix[boundary].astype(np.int64) - self.mix[boundary - 1].astype(np.int64)) / foley.isolation.MAX_PCM
            self.assertLessEqual(float(jump.max()), 0.005)

    def test_fresh_build_matches_published_candidate_and_remains_pending(self) -> None:
        package = foley.REPO_ROOT / "collab/phase42_sparse_foley_v2"
        frozen = json.loads((package / "phase42-sparse-foley-report-v2.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen["implementation_sha256"], foley._hash(Path(foley.__file__)))
        self.assertFalse(frozen["human_accepted"])
        self.assertFalse(frozen["promotion_allowed"])
        for name, entry in frozen["artifacts"].items():
            self.assertEqual(foley._hash(package / entry["file"]), entry["sha256"])
            self.assertEqual(self.report["artifacts"][name]["sha256"], entry["sha256"])

    def test_output_is_immutable(self) -> None:
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            foley.build(self.output)


if __name__ == "__main__":
    unittest.main()
