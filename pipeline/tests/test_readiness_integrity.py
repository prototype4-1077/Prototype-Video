from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import motion
import preflight
import source_policy
import supplied_media
import still_reference
import tts
import narrative_fidelity
import storyline_footage
import quality_gate
from exact_audio import ExactAudioError
from governor import PipelineGovernor, classify_failure
from governor_report import aggregate, collect_summaries


class ProductionPolicyTests(unittest.TestCase):
    def test_package_cannot_raise_the_house_limit(self):
        script = {"max_still_source_ratio": .60, "scenes": [
            {"duration": 51.7, "motion_kind": "animated_still"},
            {"duration": 48.3, "motion_kind": "video"},
        ]}
        self.assertEqual(preflight._still_budget(script)["cap"], .35)
        self.assertFalse(preflight._still_budget(script)["passed"])
        with self.assertRaises(motion.MotionBudgetError):
            motion.validate_budget(script)

    def test_zero_cap_and_invalid_caps_cannot_be_falsy_bypasses(self):
        self.assertEqual(source_policy.still_source_cap({"max_still_source_ratio": 0}), 0)
        for value in (float("nan"), float("inf"), -1, True, "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source_policy.still_source_cap({"max_still_source_ratio": value})

    def test_source_provenance_overrides_video_label(self):
        for extra in ({"source_image": "a.png"}, {"keyframes": ["a.png", "b.png"]},
                      {"motion_source": "blender_3d_storyboard"}):
            scene = {"motion_kind": "video", "duration": 10, **extra}
            self.assertEqual(motion.motion_kind(scene), motion.ANIMATED)
            self.assertTrue(preflight._planned_still(scene, {}))

    def test_3d_keyframes_are_budgeted_before_rendering(self):
        scene = {"narrative_mode": "storyboard", "duration": 10}
        report = preflight._still_budget({"graphic_backend": "blender_3d", "scenes": [scene]})
        self.assertFalse(report["passed"])
        self.assertEqual(report["estimated_ratio"], 1)

    def test_procedural_keyframes_count_as_stills_without_becoming_photo_inputs(self):
        scene = {"motion_source": "blender_3d_storyboard", "motion_kind": "animated_still", "motion_mode": "keyframes"}
        self.assertEqual(motion.motion_kind(scene), motion.ANIMATED)
        self.assertFalse(still_reference.is_active_still(scene))
        script = {"scenes": [scene]}
        motion.apply_motion_defaults(script)
        self.assertEqual(scene["motion_mode"], "keyframes")

    def test_invalid_auth_does_not_get_transient_retries(self):
        for error in ("api_key_id_used_as_api_key", "HTTP Error 401: Unauthorized network request", "disabled_client"):
            self.assertEqual(classify_failure(error), "deterministic")
        self.assertEqual(classify_failure("HTTP Error 503: Service unavailable"), "transient")


class NarrativePolicyTests(unittest.TestCase):
    def test_stock_ok_cannot_exempt_literal_scenes_even_at_the_end(self):
        scene = {"narrative_mode": "stock_ok", "visual_function": "mechanism",
                 "semantic_anchor": "hand opens refrigerator"}
        self.assertTrue(narrative_fidelity.direct_match_required(scene, 23, 24))
        ok, coverage, _ = narrative_fidelity.acceptable(scene, {"title": "ocean waves"}, 23, 24)
        self.assertFalse(ok)
        self.assertEqual(coverage, 0)

    def test_zero_coverage_is_not_accepted_as_atmosphere(self):
        scene = {"narrative_mode": "atmosphere", "semantic_anchor": "apple rotating on table"}
        self.assertFalse(narrative_fidelity.acceptable(scene, {"title": "mountain path"}, 10, 24)[0])

    def test_human_role_cannot_lower_the_literal_match_floor(self):
        scene = {"human_role": "observer", "visual_function": "mechanism", "semantic_anchor": "physical action"}
        with mock.patch.object(narrative_fidelity, "anchor_coverage", return_value=.15), mock.patch.object(narrative_fidelity, "rejected_context", return_value=None), mock.patch.object(narrative_fidelity, "rules", return_value={"minimum_anchor_coverage": .01}):
            self.assertFalse(narrative_fidelity.acceptable(scene, {"title": "anything"}, 23, 24)[0])

    def test_concrete_visual_anchor_outranks_abstract_caption_words(self):
        scene = {"keywords": ["grief", "love"], "semantic_anchor": "wooden chair rocking on porch",
                 "visual_function": "literal_anchor"}
        self.assertTrue(narrative_fidelity.acceptable(scene, {"title": "wooden chair rocking on porch"}, 4, 24)[0])

    def test_pinned_or_cached_stock_is_audited_without_ranking(self):
        scene = {"stock_id": 1, "source_title": "Ocean waves", "semantic_anchor": "hand opens refrigerator", "visual_function": "literal_anchor"}
        storyline_footage._CURRENT["decisions"] = []
        with self.assertRaises(storyline_footage.NoNarrativeMatch):
            storyline_footage._audit_selected(scene, 0, 24)
        self.assertFalse(storyline_footage._CURRENT["decisions"][-1]["accepted"])

    def test_hero_disk_roundtrip_preserves_the_generated_source(self):
        script = {"scenes": [{"text": "A doorway glows", "semantic_anchor": "door opening"}]}
        with tempfile.TemporaryDirectory() as temp:
            def generate(build, index):
                path = Path(build) / "script.json"
                saved = json.loads(path.read_text())
                self.assertEqual(saved["scenes"][0]["image_prompt"], "door opening")
                saved["scenes"][0].update({"hero_generated": True, "motion_kind": "animated_still", "clip": "generated.mp4"})
                path.write_text(json.dumps(saved))
            with mock.patch.object(storyline_footage.hero, "main", side_effect=generate):
                self.assertTrue(storyline_footage._try_effects_still(temp, script, 0))
            self.assertEqual(script["scenes"][0]["clip"], "generated.mp4")
            self.assertEqual(script["scenes"][0]["motion_kind"], "animated_still")

    def test_stock_first_video_does_not_fall_back_to_plain_2d(self):
        script = {"scenes": [{"text": "A doorway opens"}]}
        with mock.patch.object(storyline_footage, "_try_effects_still", return_value=False), mock.patch.object(storyline_footage.storyboard, "render_scene") as render:
            with self.assertRaisesRegex(RuntimeError, "plain 2D"):
                storyline_footage._render_storyboard("unused", script, 0, "no stock")
            render.assert_not_called()

    def test_failed_graphic_does_not_relax_literal_intent(self):
        script = {"scenes": [{"text": "A door opens", "narrative_mode": "literal"}]}
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(storyline_footage.storyboard, "render_scene", side_effect=RuntimeError("lacks sufficient motion")), mock.patch.object(storyline_footage, "_try_effects_still", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "will not be relaxed"):
                storyline_footage._render_storyboard(temp, script, 0, "no literal stock", prefer_storyboard=True)
        self.assertEqual(script["scenes"][0]["narrative_mode"], "literal")


class SuppliedNarrationTests(unittest.TestCase):
    def test_short_small_mp3_survives_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "script.json").write_text('{"user_vo":true}')
            voice = root / "vo.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3", str(voice)], check=True)
            before = voice.read_bytes()
            result = supplied_media.validate(root)
            self.assertLess(result["duration_seconds"], 1)
            self.assertLess(result["size_bytes"], 1_000_000)
            self.assertEqual(voice.read_bytes(), before)
            self.assertEqual(result["sha256"], hashlib.sha256(before).hexdigest())

    def test_missing_attachment_blocks_before_tts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "script.json").write_text('{"user_vo":true}')
            with self.assertRaises(ExactAudioError):
                supplied_media.validate(root)
            with mock.patch.object(tts, "_call_elevenlabs") as call, self.assertRaisesRegex(RuntimeError, "must not replace"):
                tts.tts(root)
            call.assert_not_called()

    def test_changed_verified_attachment_is_rejected_without_deletion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "script.json").write_text('{"user_vo":true}')
            (root / "vo.mp3").write_bytes(b"changed")
            (root / "audio-verification.json").write_text(json.dumps({"sha256": "0" * 64}))
            with mock.patch.object(supplied_media, "probe_audio", return_value=("mp3", .3)), self.assertRaises(ExactAudioError):
                supplied_media.validate(root)
            self.assertEqual((root / "vo.mp3").read_bytes(), b"changed")


class ImmutableOutcomeTests(unittest.TestCase):
    def test_failed_then_successful_render_keeps_both_outcomes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build = root / "build/video"
            build.mkdir(parents=True)
            for github_run, state, code in (("1", "failed", 1), ("2", "done", 0)):
                with mock.patch.dict(os.environ, {"GITHUB_RUN_ID": github_run, "GOVERNOR_RUN_ID": github_run * 32, "PIPELINE_TELEMETRY_DISABLED": "1"}):
                    governor = PipelineGovernor(build, repo_root=root)
                    governor.run([sys.executable, "-c", f"import sys;sys.exit({code})"], stage_override="general", timeout=10)
                    governor.finalize(state)
            summaries = collect_summaries(root)
            report = aggregate(summaries)
            self.assertEqual(len(summaries), 2)
            self.assertEqual(report["statuses"], {"done": 1, "failed": 1})
            self.assertEqual(report["stages"]["general"]["failures"], 1)


class ExactDurationTests(unittest.TestCase):
    def test_explicit_150_seconds_rejects_131_seconds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "script.json").write_text(json.dumps({"duration_mode": "exact", "target_duration_seconds": 150, "scenes": [{"duration": 131.425}]}))
            output = {"failures": [], "warnings": [], "probe": {"duration_s": 131.425}}
            with mock.patch.object(quality_gate, "check_output", return_value=output):
                report = quality_gate.run_quality_gate(root, deep=False)
            self.assertFalse(report["passed"])
            self.assertIn("exact_duration_mismatch", {item["code"] for item in report["failures"]})


if __name__ == "__main__":
    unittest.main()
