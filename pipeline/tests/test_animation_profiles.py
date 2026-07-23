import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import animation_profiles
import governed_build
import profiles


def script(profile_name, character=None):
    value = {
        "title": "Animation Fixture",
        "slug": "animation-fixture",
        "animation_profile": profile_name,
        "scenes": [
            {
                "text": "A belief turns like a gear.",
                "query": "interlocking gears turning under warm light",
                "duration": 5.0,
            },
            {
                "text": "The room changes when attention moves.",
                "query": "ordinary room transforming as a beam of light moves",
                "image_prompt": "ordinary room transforming around a moving beam",
                "hero": True,
                "duration": 5.0,
            },
        ],
    }
    if character:
        value["profile"] = character
    return value


class AnimationProfileTests(unittest.TestCase):
    def test_three_profiles_are_available(self):
        self.assertEqual(
            set(animation_profiles.profiles()),
            {
                animation_profiles.ANIMATED_TIER1,
                animation_profiles.JUNE_TIER1,
                animation_profiles.JUNE_STANDARD,
            },
        )

    def test_aliases_canonicalize(self):
        self.assertEqual(
            animation_profiles.resolve({"animation_style": "premium animated"}, strict=True),
            animation_profiles.ANIMATED_TIER1,
        )
        self.assertEqual(
            animation_profiles.resolve({"animation_style": "tier1 june oxley"}, strict=True),
            animation_profiles.JUNE_TIER1,
        )
        self.assertEqual(
            animation_profiles.resolve({"animation_style": "regular june oxley animated"}, strict=True),
            animation_profiles.JUNE_STANDARD,
        )

    def test_tier1_contract_sets_real_motion_floor(self):
        value = script(animation_profiles.ANIMATED_TIER1)
        self.assertTrue(animation_profiles.apply_defaults(value))
        self.assertEqual(value["animation_contract_version"], 1)
        self.assertEqual(value["max_still_source_ratio"], 0.2)
        self.assertEqual(value["minimum_true_motion_ratio"], 0.8)
        self.assertEqual(value["caption_policy"], "minimal_keywords_only")
        self.assertIn("premium cinematic animation", value["scenes"][0]["animation_query"])
        self.assertIn("interlocking gears", value["scenes"][0]["animation_base_query"])
        self.assertEqual(animation_profiles.validate(value), [])

    def test_june_tier1_locks_character_identity(self):
        value = script(animation_profiles.JUNE_TIER1)
        animation_profiles.apply_defaults(value)
        self.assertEqual(value["profile"], profiles.JUNE_OXLEY)
        self.assertEqual(value["animation_character_reference_id"], "june_oxley_v1")
        self.assertIn("same original June Oxley character", value["scenes"][0]["animation_query"])
        self.assertIn("no political imagery", value["scenes"][0]["animation_query"])
        self.assertEqual(animation_profiles.validate(value, profiles.JUNE_OXLEY), [])

    def test_standard_june_is_lighter_but_not_template_grade(self):
        value = script(animation_profiles.JUNE_STANDARD, profiles.JUNE_OXLEY)
        animation_profiles.apply_defaults(value, profiles.JUNE_OXLEY)
        self.assertEqual(value["animation_quality_tier"], 2)
        self.assertEqual(value["max_still_source_ratio"], 0.3)
        self.assertEqual(value["minimum_true_motion_ratio"], 0.7)
        query = value["scenes"][0]["animation_query"]
        self.assertIn("polished stylized 2D or 2.5D", query)
        self.assertIn("no low-grade template graphics", query)

    def test_june_animation_rejects_other_character_profile(self):
        value = script(animation_profiles.JUNE_TIER1, "someone_else")
        with self.assertRaises(ValueError):
            animation_profiles.apply_defaults(value, "someone_else")

    def test_unprofiled_script_is_unchanged(self):
        value = {"title": "Plain", "slug": "plain", "scenes": [{"text": "Still plain."}]}
        before = json.dumps(value, sort_keys=True)
        self.assertFalse(animation_profiles.apply_defaults(value))
        self.assertEqual(json.dumps(value, sort_keys=True), before)

    def test_governed_preflight_persists_styled_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = script(animation_profiles.JUNE_STANDARD)
            (root / "script.json").write_text(json.dumps(value), encoding="utf-8")
            prepared = governed_build._apply_animation_contract(root)
            saved = json.loads((root / "script.json").read_text(encoding="utf-8"))
            self.assertEqual(prepared["profile"], profiles.JUNE_OXLEY)
            self.assertEqual(saved["scenes"][0]["query"], saved["scenes"][0]["animation_query"])
            self.assertIn("animation_base_query", saved["scenes"][0])
            self.assertEqual(animation_profiles.validate(saved, profiles.JUNE_OXLEY), [])


if __name__ == "__main__":
    unittest.main()
