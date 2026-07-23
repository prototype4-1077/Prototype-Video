from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


visual_risk = load_module("visual_risk", ROOT / "pipeline" / "visual_risk.py")
prompt_assertions = load_module(
    "prompt_assertions", ROOT / "intelligence_stack" / "promptfoo" / "assertions.py"
)
reach_collect = load_module(
    "reach_collect", ROOT / "intelligence_stack" / "reach" / "collect.py"
)
comfy_render = load_module(
    "comfy_render", ROOT / "intelligence_stack" / "comfy" / "render.py"
)
visual_memory = load_module(
    "visual_memory", ROOT / "intelligence_stack" / "fiftyone" / "export_visual_memory.py"
)


class PromptfooContractTests(unittest.TestCase):
    def fixture(self, name: str) -> str:
        return (
            ROOT / "intelligence_stack" / "promptfoo" / "fixtures" / f"{name}.json"
        ).read_text(encoding="utf-8")

    def test_script_baseline_passes(self):
        result = prompt_assertions.validate(
            self.fixture("script_baseline"), {"vars": {"task_type": "script"}}
        )
        self.assertTrue(result["pass"], result["reason"])

    def test_visual_plan_baseline_passes(self):
        result = prompt_assertions.validate(
            self.fixture("visual_plan_baseline"),
            {"vars": {"task_type": "visual_plan"}},
        )
        self.assertTrue(result["pass"], result["reason"])

    def test_revision_preserves_narration(self):
        narration = (
            "Then I lift a hammer over the rubber one — and you flinch. "
            "For something made of silicone."
        )
        result = prompt_assertions.validate(
            self.fixture("revision_baseline"),
            {"vars": {"task_type": "revision", "original_narration": narration}},
        )
        self.assertTrue(result["pass"], result["reason"])


class VisualRiskTests(unittest.TestCase):
    def test_complex_hand_contact_is_blocked(self):
        scene = {
            "hero": True,
            "image_prompt": "two hands touching while one hand holds a hammer and fingers merge",
        }
        report = visual_risk.assess_scene(scene)
        self.assertFalse(report["passes_enforcement"])
        self.assertGreaterEqual(report["effective_risk_score"], 7)

    def test_constrained_comfy_scene_passes(self):
        contract = json.loads(
            (
                ROOT
                / "intelligence_stack"
                / "comfy"
                / "examples"
                / "prosthetic_shadow.json"
            ).read_text(encoding="utf-8")
        )
        comfy_render.validate_contract(contract)
        resolved = comfy_render.resolve(contract)
        self.assertEqual(resolved["4"]["inputs"]["ckpt_name"], contract["checkpoint"])
        self.assertEqual(resolved["3"]["inputs"]["seed"], contract["seed"])


class ReachTests(unittest.TestCase):
    def test_signal_scoring_and_deduplication(self):
        topics = [{"id": "prediction", "terms": ["prediction", "perception"]}]
        first = reach_collect.base_record(
            source="test",
            title="Prediction and perception",
            url="https://example.com/a",
            excerpt="A perception study",
        )
        second = dict(first)
        second["excerpt"] = "duplicate"
        reach_collect.score_and_tag(first, topics)
        reach_collect.score_and_tag(second, topics)
        records = reach_collect.dedupe([first, second])
        self.assertEqual(len(records), 1)
        self.assertIn("prediction", records[0]["topic_matches"])


class VisualMemoryTests(unittest.TestCase):
    def test_failure_tags_preserve_human_feedback_priority(self):
        tags = visual_memory.failure_tags(
            "The hand has fused fingers and looks deformed.",
            {},
            {"findings": [{"code": "hand_contact"}]},
        )
        self.assertIn("extra_or_fused_fingers", tags)
        self.assertIn("deformed_anatomy", tags)
        self.assertIn("hand_contact", tags)


if __name__ == "__main__":
    unittest.main()
