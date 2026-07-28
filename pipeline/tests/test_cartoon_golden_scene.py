import hashlib
import json
from pathlib import Path
import struct
import unittest

from pipeline.cartoon_vertical_slice import compile_plan, validate_config
from pipeline.cartoon_story_reel import (
    _parse_loudnorm_output,
    caption_chunks,
    caption_events,
    style_frames_for_profile,
)


ROOT = Path(__file__).resolve().parents[2]
SCENE_PATH = ROOT / "examples" / "june-golden-scene-twelve-dollar-mug.json"
STYLE_MANIFEST_PATH = ROOT / "concept" / "style_frames" / "june_golden_scene_style_targets_v1.json"


def _png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n" or payload[12:16] != b"IHDR":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", payload[16:24])


class GoldenSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = json.loads(SCENE_PATH.read_text(encoding="utf-8"))
        cls.styles = json.loads(STYLE_MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_scene_is_a_seven_shot_38_8_second_benchmark(self):
        validate_config(self.scene)
        plan = compile_plan(self.scene, profile="youtube", quality="proof")
        self.assertEqual(len(plan["shots"]), 7)
        self.assertEqual(plan["frame_start"], 1)
        self.assertEqual(plan["frame_end"], 1164)
        self.assertEqual(plan["duration_seconds"], 38.8)
        self.assertEqual([shot["id"] for shot in plan["shots"]], [f"GS0{i}0" for i in range(1, 8)])
        for previous, current in zip(plan["shots"], plan["shots"][1:]):
            self.assertEqual(current["frame_start"], previous["frame_end"] + 1)

    def test_every_shot_has_independent_landscape_and_portrait_direction(self):
        for shot in self.scene["shots"]:
            self.assertEqual(set(shot["framing"]), {"youtube", "portrait"})
            for profile in ("youtube", "portrait"):
                framing = shot["framing"][profile]
                self.assertGreater(framing["lens_mm"], 0)
                self.assertEqual(len(framing["subject_anchor"]), 2)
                self.assertIn("caption_zone", framing)

    def test_gestures_are_declared_actions_and_the_scene_exercises_contacts(self):
        actions = set(self.scene["animation"]["action_library"])
        gestures = {shot["gesture"] for shot in self.scene["shots"]}
        self.assertEqual(actions, gestures)
        self.assertIn("seated_to_stand_with_mug", actions)
        self.assertIn("pencil_down_coffee_pour", actions)
        self.assertIn("offer_mug_and_question", actions)
        self.assertGreaterEqual(self.scene["animation"]["minimum_active_regions"], 5)
        self.assertEqual(self.scene["quality_gates"]["max_contact_drift_px_1080"], 2)

    def test_story_props_sound_and_human_quality_gates_are_explicit(self):
        prop_ids = {prop["id"] for prop in self.scene["props"]}
        self.assertTrue({"returned_enamel_mug", "small_ledger", "short_pencil", "coffee_pot"}.issubset(prop_ids))
        self.assertEqual(self.scene["sound"]["music"], "none_intentional")
        self.assertEqual(self.scene["sound"]["target_lufs_i"], -16)
        self.assertEqual(self.scene["quality_gates"]["human_scores_minimum"], 4)
        self.assertIn("emotional_clarity", self.scene["quality_gates"]["human_score_dimensions"])

    def test_style_targets_are_versioned_and_byte_exact(self):
        self.assertEqual(self.styles["status"], "provisional_art_direction_targets")
        self.assertTrue(self.styles["approval_required"])
        self.assertFalse(self.styles["generator"]["paid_runtime_dependency"])
        self.assertEqual(
            {frame["shot"] for frame in self.styles["frames"]},
            {f"GS0{index}0" for index in range(1, 8)},
        )
        youtube = [frame for frame in self.styles["frames"] if frame["profile"] == "youtube"]
        portrait = [frame for frame in self.styles["frames"] if frame["profile"] == "portrait"]
        self.assertEqual(len(youtube), 7)
        self.assertEqual([frame["shot"] for frame in portrait], ["GS070"])
        for frame in self.styles["frames"]:
            path = STYLE_MANIFEST_PATH.parent / frame["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), frame["sha256"])
            self.assertEqual(_png_dimensions(path), (frame["width"], frame["height"]))

    def test_story_reel_has_one_verified_landscape_target_per_shot(self):
        frames = style_frames_for_profile(
            self.styles,
            profile="youtube",
            manifest_path=STYLE_MANIFEST_PATH,
        )
        self.assertEqual(set(frames), {f"GS0{index}0" for index in range(1, 8)})

    def test_captions_respect_phrase_and_profile_limits(self):
        chunks = caption_chunks(
            "Keeping score tells you what you're owed.",
            max_words=6,
            max_chars=42,
        )
        self.assertEqual(" ".join(chunks), "Keeping score tells you what you're owed.")
        events = caption_events(self.scene, profile="youtube")
        self.assertTrue(events)
        self.assertTrue(all(len(event["text"].split()) <= 6 for event in events))
        self.assertTrue(all(len(event["text"]) <= 42 for event in events))
        self.assertTrue(all(event["start"] < event["end"] for event in events))
        self.assertLessEqual(events[-1]["end"], 38.8 - 27 / 30)

    def test_loudness_measurements_are_parsed_from_ffmpeg_json(self):
        measurements = _parse_loudnorm_output(
            'prefix\n{"input_i":"-15.8","input_tp":"-2.1","input_lra":"4.6"}\nsuffix'
        )
        self.assertEqual(
            measurements,
            {"integrated_lufs": -15.8, "true_peak_dbtp": -2.1, "loudness_range_lu": 4.6},
        )


if __name__ == "__main__":
    unittest.main()
