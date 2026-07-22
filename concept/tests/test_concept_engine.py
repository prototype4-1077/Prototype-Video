import json
import os
import sys
import tempfile
import unittest
from unittest import mock


CONCEPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(CONCEPT_DIR)
if CONCEPT_DIR not in sys.path:
    sys.path.insert(0, CONCEPT_DIR)

import daily_brief
import mine_corpus
import script_gate


class CorpusTests(unittest.TestCase):
    def write_json(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)

    def test_term_counts_respect_word_boundaries(self):
        self.assertEqual(mine_corpus.count_term("I know this; knowledge changes.", "know"), 1)

    def test_canonical_scripts_prefer_published_version(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_json(
                os.path.join(root, "pipeline", "published_videos.json"),
                {"idea-v1": {"youtube_id": "x"}},
            )
            base = {"title": "Same Idea", "scenes": [{"text": "word " * 45}]}
            self.write_json(
                os.path.join(root, "build", "idea-draft", "script.json"),
                dict(base, slug="idea-draft"),
            )
            self.write_json(
                os.path.join(root, "build", "idea-v1", "script.json"),
                dict(base, slug="idea-v1"),
            )
            scripts, meta = mine_corpus.canonical_scripts(root)
            self.assertEqual([item["slug"] for item in scripts], ["idea-v1"])
            self.assertEqual(meta["deduplicated_files"], 1)

    def test_emergent_phrases_require_multiple_scripts(self):
        phrases = mine_corpus.discover_phrases([
            "golden doorway opens slowly",
            "golden doorway closes softly",
            "unrelated ocean movement",
        ])
        self.assertIn("golden doorway", [item["phrase"] for item in phrases])


class BriefTests(unittest.TestCase):
    def test_frontier_selection_prefers_unused_evidence_ready_concept(self):
        concepts = [
            {"id": "used", "evidence_id": "used"},
            {"id": "fresh", "evidence_id": "fresh"},
        ]
        evidence = {"claims": {
            "used": {"status": "established", "source_ids": ["a"]},
            "fresh": {"status": "established", "source_ids": ["a"]},
        }}
        with mock.patch.object(daily_brief, "concept_usage", return_value={"used": ["video"]}), mock.patch.object(daily_brief, "recent_ids", return_value=set()):
            choice = daily_brief.choose_frontier(
                daily_brief.dt.date(2026, 7, 22), concepts, evidence, {"concepts": {}}
            )
        self.assertEqual(choice["id"], "fresh")

    def test_every_frontier_concept_has_a_reviewed_claim_and_source(self):
        frontier = daily_brief.load(os.path.join(CONCEPT_DIR, "frontier.json"))["frontier"]
        evidence = daily_brief.load(os.path.join(CONCEPT_DIR, "evidence.json"))
        for concept in frontier:
            claim = evidence["claims"].get(concept["evidence_id"])
            self.assertIsNotNone(claim, concept["id"])
            self.assertTrue(claim.get("source_ids"), concept["id"])
            for source_id in claim["source_ids"]:
                self.assertIn(source_id, evidence["sources"])


class ScriptGateTests(unittest.TestCase):
    def test_where_you_end_passes_integrity_gate(self):
        report = script_gate.validate(
            os.path.join(REPO_ROOT, "build", "where-you-end", "script.json"),
            os.path.join(CONCEPT_DIR, "evidence.json"),
        )
        self.assertTrue(report["passed"], report["failures"])
        self.assertLessEqual(report["hero_count"], 4)

    def test_duplicate_narration_fails(self):
        with tempfile.TemporaryDirectory() as root:
            script_path = os.path.join(root, "script.json")
            evidence_path = os.path.join(root, "evidence.json")
            repeated = "This repeated sentence contains enough words to trigger detection."
            with open(script_path, "w", encoding="utf-8") as handle:
                json.dump({"title": "x", "slug": "x", "scenes": [{"text": repeated}, {"text": repeated}]}, handle)
            with open(evidence_path, "w", encoding="utf-8") as handle:
                json.dump({"sources": {}, "claims": {}}, handle)
            report = script_gate.validate(script_path, evidence_path)
        self.assertFalse(report["passed"])
        self.assertTrue(any("near-duplicate" in item for item in report["failures"]))


if __name__ == "__main__":
    unittest.main()
