import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


PIPELINE = Path(__file__).resolve().parents[1]
ROOT = PIPELINE.parent
sys.path.insert(0, str(ROOT))

from pipeline.cartoon_look_learner import (  # noqa: E402
    build_recommendation,
    canonical_sha256,
    contextual_features,
    load_reward_contract,
    rank_look_profiles,
    score_observation,
    validate_reward_contract,
)


CONTRACT_PATH = ROOT / "concept" / "style_frames" / "june_oxley_npr_reward_v1.json"
PROFILE_PATH = ROOT / "concept" / "style_frames" / "june_oxley_npr_look_v4.json"


class CartoonLookLearnerTest(unittest.TestCase):
    def setUp(self):
        self.contract = load_reward_contract(CONTRACT_PATH)
        self.profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        self.context = {
            "shot_scale": 0.85,
            "motion_intensity": 0.70,
            "emotion_intensity": 0.90,
            "background_complexity": 0.40,
        }

    def metrics(self, value=0.9, render_seconds=20.0):
        return {
            "identity": value,
            "expression_readability": value,
            "temporal_stability": value,
            "silhouette_readability": value,
            "palette_harmony": value,
            "human_preference": value,
            "render_seconds": render_seconds,
        }

    def test_contract_and_contextual_vector_are_complete(self):
        validate_reward_contract(self.contract)
        vector = contextual_features(self.contract, self.profile, self.context)
        look_count = len(self.contract["look_features"])
        context_count = len(self.contract["context_features"])
        self.assertEqual(len(vector), 1 + look_count + context_count + look_count * context_count)

    def test_contract_rejects_non_unit_reward_weights(self):
        invalid = copy.deepcopy(self.contract)
        invalid["objectives"][0]["weight"] += 0.01
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            validate_reward_contract(invalid)

    def test_hard_gate_prevents_bad_look_from_teaching_success(self):
        observation = {"metrics": self.metrics()}
        passed = score_observation(self.contract, observation)
        self.assertTrue(passed["hard_gate_pass"])
        self.assertGreater(passed["reward"], 0.8)

        observation["metrics"]["temporal_stability"] = 0.4
        failed = score_observation(self.contract, observation)
        self.assertFalse(failed["hard_gate_pass"])
        self.assertEqual(failed["reward"], 0.0)
        self.assertIn("temporal_stability", failed["gate_failures"])

    def test_learner_exploits_observed_visual_quality(self):
        low = copy.deepcopy(self.profile)
        low["style_version"] = "1.3.1"
        low["outlines"]["edge_strength"] = 0.30
        high = copy.deepcopy(self.profile)
        high["style_version"] = "1.3.2"
        high["outlines"]["edge_strength"] = 0.70
        contract = copy.deepcopy(self.contract)
        contract["bandit"]["exploration"] = 0.0
        observations = [
            {
                "look_profile_sha256": canonical_sha256(low),
                "context": self.context,
                "metrics": self.metrics(0.81, 30.0),
            },
            {
                "look_profile_sha256": canonical_sha256(high),
                "context": self.context,
                "metrics": self.metrics(0.97, 18.0),
            },
        ]
        ranking = rank_look_profiles(contract, [low, high], observations, self.context)
        self.assertEqual(ranking[0]["look_profile_sha256"], canonical_sha256(high))
        self.assertGreater(ranking[0]["predicted_reward"], ranking[1]["predicted_reward"])

    def test_recommendation_is_deterministic_and_advisory(self):
        result = build_recommendation(self.contract, [self.profile], [], self.context)
        replay = build_recommendation(self.contract, [self.profile], [], self.context)
        self.assertEqual(result, replay)
        self.assertEqual(result["recommended_experiment"]["look_profile_sha256"], canonical_sha256(self.profile))
        self.assertIn("Human approval", result["authority_boundary"])

    def test_unknown_observation_profile_is_rejected(self):
        observation = {
            "look_profile_sha256": "0" * 64,
            "context": self.context,
            "metrics": self.metrics(),
        }
        with self.assertRaisesRegex(ValueError, "unknown look profile"):
            rank_look_profiles(self.contract, [self.profile], [observation], self.context)


if __name__ == "__main__":
    unittest.main()
