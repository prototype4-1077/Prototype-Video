import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import expand_submission


class ExpandSubmissionTests(unittest.TestCase):
    def test_voice_tag_moves_to_audio_and_family_follows_visual(self):
        with tempfile.TemporaryDirectory() as td:
            build = Path(td)
            (build / "submission.json").write_text(json.dumps({
                "title": "A Test",
                "scenes": [{
                    "text": "[with quiet intensity] Two eyes create one depth.",
                    "visual": "close-up of two eyes reflecting the same street",
                }],
            }), encoding="utf-8")

            expand_submission.expand("a-test", build)
            script = json.loads((build / "script.json").read_text(encoding="utf-8"))
            scene = script["scenes"][0]

            self.assertEqual(scene["text"], "Two eyes create one depth.")
            self.assertEqual(scene["audio_tags"], ["with quiet intensity"])
            self.assertEqual(scene["semantic_anchor"], "close-up of two eyes reflecting the same street")
            self.assertEqual(scene["visual_function"], "literal_anchor")
            self.assertEqual(scene["narrative_mode"], "stock_ok")
            self.assertNotIn("symbol_family", scene)
            self.assertEqual(script["visual_policy"]["max_family_run"], 6)
            self.assertEqual(script["visual_policy"]["min_families"], 4)
            self.assertEqual(script["max_still_source_ratio"], 0.50)
            self.assertNotIn("[with quiet intensity]", (build / "source-script.txt").read_text())

    def test_motion_graphics_profile_routes_scenes_and_preserves_intent(self):
        with tempfile.TemporaryDirectory() as td:
            build = Path(td)
            (build / "submission.json").write_text(json.dumps({
                "title": "A Graphic Test",
                "visual_style": "literal_motion_graphics",
                "scenes": [
                    {
                        "text": "Your belief filters the evidence.",
                        "visual": "a filter settings panel hides half the evidence cards",
                        "keywords": ["BELIEF", "EVIDENCE"],
                        "semantic_anchor": "belief filters visible evidence",
                        "visual_function": "mechanism",
                        "graphic_kind": "filter",
                    },
                    {
                        "text": "Then your phone camera does the same thing.",
                        "visual": "a real phone camera locking focus",
                        "visual_mode": "stock",
                    },
                    {
                        "text": "The conclusion becomes a luminous doorway.",
                        "visual": "a luminous doorway opening in deep space",
                        "visual_mode": "hero",
                    },
                    {
                        "text": "Let the planner decide this beat.",
                        "visual": "a balance scale moving between two choices",
                        "visual_mode": "auto",
                    },
                ],
            }), encoding="utf-8")

            expand_submission.expand("a-graphic-test", build)
            script = json.loads((build / "script.json").read_text(encoding="utf-8"))
            scenes = script["scenes"]

            self.assertEqual(script["visual_style"], "literal_motion_graphics")
            self.assertEqual(scenes[0]["narrative_mode"], "storyboard")
            self.assertEqual(scenes[0]["semantic_anchor"], "belief filters visible evidence")
            self.assertEqual(scenes[0]["visual_function"], "mechanism")
            self.assertEqual(scenes[0]["keywords"], ["BELIEF", "EVIDENCE"])
            self.assertEqual(scenes[0]["graphic_kind"], "filter")
            self.assertEqual(script["graphic_backend"], "blender_3d")
            self.assertEqual(scenes[0]["graphic_backend"], "blender_3d")
            self.assertEqual(
                script["graphic_backend_policy"],
                "prefer_3d_with_2d_fallback",
            )
            self.assertEqual(script["graphic_policy"]["min_kinds"], 9)
            self.assertEqual(scenes[1]["narrative_mode"], "stock_ok")
            self.assertEqual(scenes[2]["narrative_mode"], "hero")
            self.assertNotIn("narrative_mode", scenes[3])

    def test_unknown_visual_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            build = Path(td)
            (build / "submission.json").write_text(json.dumps({
                "title": "A Broken Test",
                "scenes": [{"text": "A line.", "visual_mode": "mystery"}],
            }), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unknown visual_mode"):
                expand_submission.expand("a-broken-test", build)

    def test_unknown_graphic_backend_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            build = Path(td)
            (build / "submission.json").write_text(json.dumps({
                "title": "A Broken Backend",
                "visual_style": "literal_motion_graphics",
                "graphic_backend": "imaginary_4d",
                "scenes": [{"text": "A line.", "graphic_kind": "generic"}],
            }), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unknown graphic_backend"):
                expand_submission.expand("a-broken-backend", build)


if __name__ == "__main__":
    unittest.main()
