from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import narrative_fidelity
import storyboard
import storyline_footage


class NarrativeFidelityTests(unittest.TestCase):
    def test_rejected_context_is_blocked(self):
        scene = {
            "query": "four physical rubber stamps mark papers success failure normal impossible",
            "keywords": ["success", "failure", "normal", "impossible"],
            "visual_function": "contrast",
        }
        video = {
            "id": 5963494,
            "url": "https://www.pexels.com/video/a-person-making-a-leather-wallet-5963494/",
        }
        ok, coverage, reason = narrative_fidelity.acceptable(scene, video, 3, 26)
        self.assertFalse(ok)
        self.assertEqual(coverage, 0.0)
        self.assertIn("wallet", reason)

    def test_exact_phone_camera_candidate_survives(self):
        scene = {
            "query": "smartphone camera interface fills frame",
            "keywords": ["mind", "camera", "phone"],
            "visual_function": "mechanism",
        }
        video = {
            "id": 4181136,
            "url": "https://www.pexels.com/video/close-up-shot-of-a-mobile-phone-s-camera-menu-4181136/",
        }
        ok, coverage, _reason = narrative_fidelity.acceptable(scene, video, 11, 26)
        self.assertTrue(ok)
        self.assertGreaterEqual(coverage, 0.5)

    def test_literal_mechanism_prefers_storyboard(self):
        scene = {
            "text": "This is success. This is failure. This is normal. This is impossible.",
            "query": "four physical rubber stamps mark papers success failure normal impossible",
            "keywords": ["success", "failure", "normal", "impossible"],
            "symbol_family": "language",
            "visual_function": "contrast",
        }
        self.assertTrue(storyboard.preferred(scene, 3, 26))

    def test_simple_phone_line_keeps_stock(self):
        scene = {
            "text": "Your mind became like the camera on your phone.",
            "query": "smartphone camera interface fills the frame as autofocus box locks onto one familiar object",
            "keywords": ["mind", "camera", "phone"],
            "symbol_family": "object_tool",
            "visual_function": "mechanism",
        }
        self.assertFalse(storyboard.preferred(scene, 11, 26))

    def test_storyboard_frame_has_expected_size(self):
        scene = {
            "query": "receipt printer records selfish acts while kindness passes unnoticed",
            "keywords": ["selfish", "collects", "receipts"],
            "semantic_anchor": "belief gathers confirming evidence",
        }
        image = storyboard.frame(scene, 0.5)
        self.assertEqual(image.size, (storyboard.W, storyboard.H))

    def test_explicit_graphic_kind_overrides_keyword_router(self):
        scene = {
            "query": "filter settings panel",
            "graphic_kind": "path",
        }
        self.assertEqual(storyboard.graphic_kind(scene), "path")

    def test_graphic_diversity_rejects_repeated_compositions(self):
        script = {
            "visual_style": "literal_motion_graphics",
            "graphic_policy": {
                "require_explicit": True,
                "min_kinds": 3,
                "max_kind_count": 1,
                "max_kind_run": 1,
            },
            "scenes": [
                {"narrative_mode": "storyboard", "graphic_kind": "labels"},
                {"narrative_mode": "storyboard", "graphic_kind": "labels"},
                {"narrative_mode": "storyboard", "graphic_kind": "path"},
            ],
        }
        report = storyboard.graphic_diversity(script)
        self.assertFalse(report["passed"])
        self.assertEqual(report["counts"], {"labels": 2, "path": 1})
        self.assertTrue(any("only 2 graphic compositions" in item for item in report["violations"]))

    def test_graphic_motion_gate_accepts_local_interface_motion(self):
        evidence = storyboard._graphic_motion_evidence({
            "passes": False,
            "active_region_ratio": 0.07,
            "frame_difference": 0.9,
        })
        self.assertTrue(evidence["passes"])
        self.assertFalse(evidence["stock_motion_gate_passed"])
        self.assertTrue(evidence["graphic_motion_gate_passed"])

    def test_preferred_storyboard_runs_before_effects_still(self):
        with tempfile.TemporaryDirectory() as td:
            script = {"scenes": [{"text": "Belief filters evidence."}]}
            with mock.patch.object(
                storyline_footage.storyboard, "render_scene",
                return_value={"scene_index": 0, "output": "clip_00.mp4"},
            ) as render, mock.patch.object(
                storyline_footage, "_try_effects_still", return_value=True,
            ) as effects:
                plan = storyline_footage._render_storyboard(
                    td, script, 0, "literal mechanism preferred",
                    prefer_storyboard=True,
                )

            render.assert_called_once()
            effects.assert_not_called()
            self.assertEqual(plan["output"], "clip_00.mp4")

    def test_generic_no_stock_fallback_keeps_effects_still_first(self):
        with tempfile.TemporaryDirectory() as td:
            script = {"scenes": [{"text": "An atmospheric line."}]}
            with mock.patch.object(
                storyline_footage.storyboard, "render_scene",
            ) as render, mock.patch.object(
                storyline_footage, "_try_effects_still", return_value=True,
            ) as effects:
                plan = storyline_footage._render_storyboard(
                    td, script, 0, "no stock match",
                )

            effects.assert_called_once()
            render.assert_not_called()
            self.assertEqual(plan["result"], "effects_still")


if __name__ == "__main__":
    unittest.main()
