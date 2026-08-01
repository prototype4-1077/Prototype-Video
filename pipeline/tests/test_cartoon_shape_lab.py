import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.cartoon_shape_lab import (
    default_parameters,
    dominates,
    load_search_space,
    main,
    objective_directions,
    pareto_frontier,
    sample_candidates,
    validate_candidate,
    validate_search_space,
    write_candidate_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
SEARCH_SPACE_PATH = ROOT / "concept" / "characters" / "june_oxley_shape_search_v1.json"


class CartoonShapeLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.search_space = load_search_space(SEARCH_SPACE_PATH)

    def test_search_space_has_eighteen_bounded_artist_parameters(self):
        self.assertEqual(self.search_space["search_space_version"], "1.0.0")
        self.assertEqual(len(self.search_space["parameters"]), 18)
        self.assertEqual(self.search_space["asset_version"], "3.0.0")
        self.assertIn("nose.projection", default_parameters(self.search_space))
        self.assertIn("torso.width_scale", default_parameters(self.search_space))

    def test_sampling_is_seeded_and_candidate_zero_is_the_baseline(self):
        first = sample_candidates(self.search_space, seed=90210, count=4)
        replay = sample_candidates(self.search_space, seed=90210, count=4)
        different = sample_candidates(self.search_space, seed=90211, count=4)
        self.assertEqual(first, replay)
        self.assertEqual(first[0]["parameters"], default_parameters(self.search_space))
        self.assertTrue(first[0]["generator"]["baseline"])
        self.assertNotEqual(first[1]["parameters"], different[1]["parameters"])
        for candidate in first:
            validate_candidate(self.search_space, candidate)

    def test_out_of_range_and_tampered_candidates_are_rejected(self):
        candidate = sample_candidates(self.search_space, seed=11, count=1)[0]
        invalid_value = copy.deepcopy(candidate)
        invalid_value["parameters"]["head.width"] = 99.0
        with self.assertRaisesRegex(ValueError, "head.width"):
            validate_candidate(self.search_space, invalid_value)

        invalid_id = copy.deepcopy(candidate)
        invalid_id["candidate_id"] = "june-shape-0000000000000000"
        with self.assertRaisesRegex(ValueError, "candidate_id"):
            validate_candidate(self.search_space, invalid_id)

    def test_bad_search_space_grid_is_rejected(self):
        invalid = copy.deepcopy(self.search_space)
        invalid["parameters"][0]["step"] = 0.004
        with self.assertRaisesRegex(ValueError, "divisible by step"):
            validate_search_space(invalid)

    def test_pareto_frontier_supports_mixed_directions(self):
        directions = objective_directions(self.search_space)
        records = [
            {"candidate_id": "balanced", "scores": {"identity": 0.90, "silhouette": 0.80, "expression_readability": 0.72, "render_seconds": 8.0}},
            {"candidate_id": "expressive", "scores": {"identity": 0.86, "silhouette": 0.78, "expression_readability": 0.91, "render_seconds": 7.0}},
            {"candidate_id": "dominated", "scores": {"identity": 0.80, "silhouette": 0.70, "expression_readability": 0.65, "render_seconds": 9.0}},
        ]
        self.assertTrue(dominates(records[0], records[2], directions))
        self.assertFalse(dominates(records[0], records[1], directions))
        self.assertEqual(
            [record["candidate_id"] for record in pareto_frontier(records, directions)],
            ["balanced", "expressive"],
        )

    def test_identical_scores_remain_as_distinct_frontier_candidates(self):
        directions = {"identity": "maximize", "render_seconds": "minimize"}
        records = [
            {"candidate_id": "a", "scores": {"identity": 0.8, "render_seconds": 4}},
            {"candidate_id": "b", "scores": {"identity": 0.8, "render_seconds": 4}},
        ]
        self.assertEqual(pareto_frontier(records, directions), records)

    def test_manifest_writes_are_append_only_but_idempotent(self):
        candidate = sample_candidates(self.search_space, seed=22, count=1)[0]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_candidate_manifest(candidate, temp_dir)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), candidate)
            self.assertEqual(write_candidate_manifest(candidate, temp_dir), path)
            tampered = copy.deepcopy(candidate)
            tampered["state"] = "secretly-replaced"
            with self.assertRaisesRegex(ValueError, "immutable candidate payload"):
                write_candidate_manifest(tampered, temp_dir)
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "immutable"):
                write_candidate_manifest(candidate, temp_dir)

    def test_cli_creates_replayable_candidate_manifests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with redirect_stdout(io.StringIO()):
                result = main([
                    str(SEARCH_SPACE_PATH),
                    "--output-dir", temp_dir,
                    "--seed", "73",
                    "--count", "3",
                ])
            self.assertEqual(result, 0)
            manifests = sorted(Path(temp_dir).glob("june-shape-*/candidate.json"))
            self.assertEqual(len(manifests), 3)
            first = json.loads(manifests[0].read_text(encoding="utf-8"))
            validate_candidate(self.search_space, first)


if __name__ == "__main__":
    unittest.main()
