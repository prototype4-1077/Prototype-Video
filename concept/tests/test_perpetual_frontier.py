import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "perpetual_frontier.py"
SPEC = importlib.util.spec_from_file_location("perpetual_frontier", MODULE_PATH)
perpetual_frontier = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(perpetual_frontier)


class PerpetualFrontierTests(unittest.TestCase):
    def _root(self, temp: str) -> Path:
        root = Path(temp)
        (root / "concept").mkdir(parents=True)
        (root / "build" / "alpha").mkdir(parents=True)
        (root / "build" / "beta").mkdir(parents=True)
        fixtures = {
            "evolution_constitution.json": {
                "immutable_principles": ["Invitation", "Science fidelity", "Grounding"],
                "authority_boundary": {"may_not": ["create render.request"]},
                "surprise_budget": {"proven": 0.7, "uncertainty": 0.2, "wild": 0.1},
                "quality_diversity": {"dimensions": ["pillars", "fidelity", "hook", "narration", "human_band", "generation_band"]},
                "cognitive_selves": [
                    {"id": "scientist", "mission": "test evidence", "weights": {"scientific": 2, "ethical": 1}},
                    {"id": "ordinary", "mission": "land in ordinary", "weights": {"channel": 2, "audience": 1}}
                ]
            },
            "patterns.json": {
                "pillars": [
                    {"id": "grounding", "label": "The ordinary", "weight": 100},
                    {"id": "attention", "label": "Attention", "weight": 70},
                    {"id": "memory", "label": "Memory", "weight": 60}
                ]
            },
            "frontier.json": {
                "frontier": [
                    {"id": "fresh", "title": "Fresh", "fidelity": "emerging", "science": "memory attention", "hook": "Fresh hook", "metaphor": "a map"}
                ]
            },
            "catalog.json": {
                "videos": {
                    "alpha": {"pillars": ["attention"], "narration": "guided", "hook": "plunge", "frontier": "used"},
                    "beta": {"pillars": ["grounding"], "narration": "guided", "hook": "confessional"}
                }
            },
            "provisional_rules.json": {
                "rules": [
                    {"id": "permanent", "kind": "constitutional", "statement": "keep ethos"},
                    {"id": "old", "kind": "provisional", "statement": "old rule", "confidence": 0.5, "last_evidence": "2020-01-01", "half_life_days": 30}
                ]
            },
            "capability_constitution.json": {
                "capabilities": [
                    {"id": "loop", "statement": "run loop", "evidence_paths": ["concept/perpetual_frontier.py"], "minimum_evidence": 1}
                ]
            },
            "expedition_library.json": {
                "domains": [
                    {"name": "ecology", "mechanisms": ["niche construction"], "visual_languages": ["a forest redirecting water"], "analogy_warning": "metaphor only"}
                ]
            }
        }
        for name, payload in fixtures.items():
            (root / "concept" / name).write_text(json.dumps(payload), encoding="utf-8")
        shutil.copy(MODULE_PATH, root / "concept" / "perpetual_frontier.py")

        alpha = {
            "title": "Alpha", "slug": "alpha", "fidelity": "emerging",
            "scenes": [
                {"text": "Attention is a gate.", "image_prompt": "one gate moving", "hero": True},
                {"text": "Feel the chair. What changes when you look again?"}
            ]
        }
        beta = {
            "title": "Beta", "slug": "beta", "fidelity": "established",
            "scenes": [
                {"text": "The room returns.", "query": "empty room sunlight"},
                {"text": "Notice one breath. What is here?"}
            ]
        }
        (root / "build" / "alpha" / "script.json").write_text(json.dumps(alpha), encoding="utf-8")
        (root / "build" / "beta" / "script.json").write_text(json.dumps(beta), encoding="utf-8")
        (root / "build" / "alpha" / "yt_stats.json").write_text(json.dumps({"views": 10000, "avg_view_pct": 55}), encoding="utf-8")
        (root / "build" / "beta" / "yt_stats.json").write_text(json.dumps({"views": 100, "avg_view_pct": 20}), encoding="utf-8")
        feedback = {
            "overall": {"decision": "revise"},
            "scenes": [
                {"scene_index": 0, "decision": "revise", "comments": "The hand has extra fingers and looks fused."},
                {"scene_index": 1, "decision": "approved", "comments": "keep"}
            ]
        }
        (root / "build" / "alpha" / "scene-feedback.request.json").write_text(json.dumps(feedback), encoding="utf-8")
        (root / "build" / "alpha" / "telemetry-summary.json").write_text(json.dumps({"stages": {"hero": {"total_duration_s": 100}, "assemble": {"total_duration_s": 10}}}), encoding="utf-8")
        return root

    def test_cycle_writes_only_evolution_state_and_covers_all_loops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            script_before = (root / "build" / "alpha" / "script.json").read_bytes()
            frontier_before = (root / "concept" / "frontier.json").read_bytes()
            state = perpetual_frontier.run_cycle(root, perpetual_frontier.dt.date(2026, 7, 23))
            self.assertFalse(state["production_files_modified"])
            self.assertTrue(state["requires_human_selection"])
            self.assertTrue(state["hypotheses"])
            self.assertTrue(state["diversity_atlas"]["cells"])
            self.assertTrue(state["curiosity_queue"])
            self.assertTrue(state["dreams"])
            self.assertTrue(state["experiments"])
            self.assertTrue(state["disagreement_observatory"])
            self.assertTrue(state["lineage"]["nodes"])
            self.assertTrue(state["negative_space"]["rejected_scene_ideas"])
            self.assertTrue(state["rule_review"]["retest_queue"])
            self.assertTrue(state["multiple_selves"]["crossovers"])
            self.assertEqual(state["surprise_portfolio"]["allocation"]["wild"], 0.1)
            self.assertEqual((root / "build" / "alpha" / "script.json").read_bytes(), script_before)
            self.assertEqual((root / "concept" / "frontier.json").read_bytes(), frontier_before)
            self.assertFalse((root / "build" / "alpha" / "render.request").exists())
            self.assertTrue((root / "concept" / "evolution_state" / "BRIEF.md").exists())

    def test_dreams_are_metaphor_labeled_and_questions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            state = perpetual_frontier.run_cycle(root, perpetual_frontier.dt.date(2026, 7, 23))
            for dream in state["dreams"]:
                self.assertEqual(dream["fidelity"], "metaphor")
                self.assertTrue(dream["invitation"].endswith("?"))
                self.assertEqual(dream["status"], "dream_only")

    def test_constitution_rules_do_not_decay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self._root(temp)
            state = perpetual_frontier.run_cycle(root, perpetual_frontier.dt.date(2026, 7, 23))
            rules = {item["id"]: item for item in state["rule_review"]["rules"]}
            self.assertEqual(rules["permanent"]["status"], "permanent")
            self.assertEqual(rules["permanent"]["effective_confidence"], 1.0)
            self.assertIn(rules["old"]["status"], {"retest", "retire_candidate"})


if __name__ == "__main__":
    unittest.main()
