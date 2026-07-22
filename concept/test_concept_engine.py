"""Stdlib tests for Concept Engine v3."""
from __future__ import annotations

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import comment_mining
import decision_brief
import influence_guard
import intelligence


class ConceptEngineV3Tests(unittest.TestCase):
    def test_graph_covers_frontier(self):
        frontier = intelligence.load("frontier.json", {})["frontier"]
        graph = intelligence.load("concept_graph.json", {})["nodes"]
        missing = [item["id"] for item in frontier if item["id"] not in graph]
        self.assertEqual(missing, [])

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(intelligence.WEIGHTS.values()), 1.0, places=6)

    def test_guard_passes_well_formed_candidate(self):
        result = influence_guard.assess({
            "fidelity": "established",
            "invitation": "What evidence would change this belief?",
            "grounding": "Feel the chair and name one observable fact.",
            "evidence_boundary": "This test reveals an inference, not metaphysical truth.",
            "desired_movement": "From verdict to hypothesis.",
            "optimization_target": "belief_analysis",
            "risk_mitigations": ["Return to the ordinary room."],
        })
        self.assertEqual(result["decision"], "PASS")

    def test_guard_blocks_verdict_installation(self):
        result = influence_guard.assess({
            "fidelity": "emerging",
            "invitation": "What do you notice?",
            "grounding": "Return to the room.",
            "evidence_boundary": "The model is emerging.",
            "desired_movement": "From certainty to examination.",
        }, text="The truth is this proves that reality is fake.")
        self.assertEqual(result["decision"], "BLOCK")
        self.assertTrue(any(i["code"] == "verdict_installation" for i in result["issues"]))

    def test_comment_classifier_separates_reflection_from_agreement(self):
        tags = comment_mining.classify("I disagree, but this made me think and I checked my assumption.")
        self.assertIn("constructive_disagreement", tags)
        self.assertIn("reflection", tags)
        self.assertIn("application", tags)
        self.assertNotIn("certainty_transfer", tags)

    def test_ranked_candidates_are_scored_and_safe(self):
        ranked = intelligence.rank_candidates()
        self.assertGreater(len(ranked), 5)
        self.assertTrue(all(0 <= item["score"] <= 100 for item in ranked))
        self.assertTrue(all(set(item["components"]) == set(intelligence.WEIGHTS) for item in ranked))
        self.assertNotEqual(ranked[0]["guard"]["decision"], "BLOCK")

    def test_decision_brief_contains_help_and_safety(self):
        brief = decision_brief.build_brief("constructed_emotion", "2026-07-22")
        self.assertEqual(brief["selected"]["id"], "constructed_emotion")
        self.assertIn("science_ledger", brief)
        self.assertIn("transformation_ladder", brief)
        self.assertIn("success_hypothesis", brief)
        self.assertEqual(brief["influence_review"]["decision"], "PASS")


if __name__ == "__main__":
    unittest.main()
