import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import profiles


class ProfileTests(unittest.TestCase):
    def test_default_is_unchanged(self):
        self.assertIsNone(profiles.resolve({"title": "Ordinary"}))
        self.assertEqual(profiles.query_variants("rain on window", None), ["rain on window"])
        self.assertEqual(profiles.semantic_query("rain on window", None), "rain on window")

    def test_june_aliases_canonicalize(self):
        for script in (
            {"profile": "june_oxley"},
            {"profile": "June Oxley"},
            {"character": "Papa June"},
            {"character_style": "Grandpa June"},
        ):
            self.assertEqual(profiles.resolve(script, strict=True), profiles.JUNE_OXLEY)

    def test_unknown_profile_fails_strict_validation(self):
        with self.assertRaises(ValueError):
            profiles.resolve({"profile": "someone_else"}, strict=True)

    def test_issue_detection_requires_explicit_name(self):
        self.assertEqual(profiles.detect_from_text("Make a June Oxley video about bills"),
                         profiles.JUNE_OXLEY)
        self.assertEqual(profiles.detect_from_text("Papa June talks to his neighbor"),
                         profiles.JUNE_OXLEY)
        self.assertIsNone(profiles.detect_from_text("Make this Southern and funny"))

    def test_query_keeps_literal_meaning_and_adds_world(self):
        variants = profiles.query_variants("unpaid bills on kitchen table", profiles.JUNE_OXLEY)
        self.assertIn("unpaid bills on kitchen table", variants)
        self.assertIn("rural Southern", variants[0])
        self.assertIn("warm daylight", variants[0])

    def test_visionary_query_uses_folk_surreal_contrast(self):
        variants = profiles.query_variants("universe inside an old mirror", profiles.JUNE_OXLEY)
        self.assertIn("folk surrealism", variants[0])
        self.assertNotIn("warm daylight", variants[0])

    def test_june_has_a_rural_fallback_bank(self):
        bank = profiles.fallback_queries(profiles.JUNE_OXLEY)
        self.assertGreaterEqual(len(bank), 16)
        self.assertTrue(any("front porch" in q for q in bank))
        self.assertTrue(any("old white man" in q for q in bank))

    def test_stale_june_identity_is_repaired(self):
        variants = profiles.query_variants("older Black man sitting on porch",
                                           profiles.JUNE_OXLEY)
        self.assertTrue(all("Black man" not in q for q in variants))
        self.assertTrue(all("old white Southern man" in q for q in variants))

    def test_generic_june_human_shot_gets_character_identity(self):
        variants = profiles.query_variants("man driving an old pickup",
                                           profiles.JUNE_OXLEY)
        self.assertIn("old white Southern man", variants[0])
        self.assertNotIn("old white", profiles.query_variants(
            "woman standing in a country church", profiles.JUNE_OXLEY)[0])


if __name__ == "__main__":
    unittest.main()
