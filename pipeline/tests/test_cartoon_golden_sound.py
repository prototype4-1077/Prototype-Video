from __future__ import annotations

import copy
from pathlib import Path
import unittest

import numpy as np

from pipeline.cartoon_golden_sound import (
    STEM_CHANNELS,
    load_sound_contract,
    render_procedural_stems,
    write_captions,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/style_frames/june_golden_scene_master_sound_v1.json"


class CartoonGoldenSoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, _ = load_sound_contract(CONTRACT, require_dialogue_source=False)

    def test_contract_locks_full_1164_frame_audio_clock(self) -> None:
        master = self.contract["master"]
        self.assertEqual(
            (master["fps"], master["frame_count"], master["sample_rate"], master["samples_per_frame"], master["sample_count"]),
            (30, 1164, 48000, 1600, 1862400),
        )
        self.assertEqual(master["duration_seconds"], 38.8)
        self.assertEqual(len(self.contract["dialogue_cues"]), 18)
        self.assertEqual(self.contract["mix"]["aac_true_peak_headroom_db"], 0.3)
        self.assertLess(min(cue["gain_db"] for cue in self.contract["dialogue_cues"]), -3.0)
        self.assertGreater(max(cue["gain_db"] for cue in self.contract["dialogue_cues"]), 0.0)

    def test_public_domain_dialogue_source_is_pinned(self) -> None:
        contract, source = load_sound_contract(CONTRACT, require_dialogue_source=True)
        self.assertIsNotNone(source)
        self.assertEqual(contract["voice"]["dataset"], "LibriVox")
        self.assertEqual(contract["voice"]["dataset_license"], "public domain")
        self.assertEqual(
            contract["voice"]["source"]["sha256"],
            "2cb1fc40d7c03d726e6f7310dda957014ce2bc6c692df41b8ef5c26f0c6171ce",
        )

    def test_every_required_stem_and_foley_category_is_present(self) -> None:
        self.assertEqual(
            {stem["id"]: stem["channels"] for stem in self.contract["stems"]},
            STEM_CHANNELS,
        )
        self.assertEqual(
            set(self.contract["required_foley"]),
            {"mug_thumb_rub", "mug_place_and_slide", "chair_creak", "clothing", "boot_plant", "ledger", "pencil", "coffee_pot", "coffee_pour"},
        )
        event_ids = {event["id"] for event in self.contract["events"]}
        for identifiers in self.contract["required_foley"].values():
            self.assertTrue(set(identifiers).issubset(event_ids))

    def test_procedural_stems_are_deterministic_exact_clock_and_nonempty(self) -> None:
        first = render_procedural_stems(self.contract)
        second = render_procedural_stems(self.contract)
        self.assertEqual(set(first), {"FOLEY_PROP_MONO", "FOLEY_BODY_STEREO", "AMB_PORCH_STEREO", "MUSIC_EMPTY"})
        for stem_id, channels in (("FOLEY_PROP_MONO", 1), ("FOLEY_BODY_STEREO", 2), ("AMB_PORCH_STEREO", 2), ("MUSIC_EMPTY", 2)):
            self.assertEqual(first[stem_id].shape, (1862400, channels))
            self.assertTrue(np.array_equal(first[stem_id], second[stem_id]))
        self.assertGreater(float(np.max(np.abs(first["FOLEY_PROP_MONO"]))), 0.0)
        self.assertGreater(float(np.max(np.abs(first["FOLEY_BODY_STEREO"]))), 0.0)
        self.assertGreater(float(np.max(np.abs(first["AMB_PORCH_STEREO"]))), 0.0)
        self.assertEqual(float(np.max(np.abs(first["MUSIC_EMPTY"]))), 0.0)

    def test_caption_clock_uses_exact_output_frame_offsets(self) -> None:
        temporary = REPO_ROOT / "build" / "test-golden-sound-captions.srt"
        try:
            write_captions(self.contract, temporary)
            text = temporary.read_text(encoding="utf-8")
            self.assertIn("00:00:00,100 --> 00:00:01,833", text)
            self.assertIn("00:00:34,667 --> 00:00:35,933", text)
            self.assertEqual(text.count(" --> "), 18)
        finally:
            temporary.unlink(missing_ok=True)

    def test_contract_rejects_missing_foley_and_overlapping_dialogue(self) -> None:
        missing = copy.deepcopy(self.contract)
        del missing["required_foley"]["coffee_pour"]
        path = REPO_ROOT / "build" / "broken-golden-sound.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(__import__("json").dumps(missing), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Foley map"):
                load_sound_contract(path, require_dialogue_source=False)
            overlap = copy.deepcopy(self.contract)
            overlap["dialogue_cues"][1]["start_frame"] = 50
            path.write_text(__import__("json").dumps(overlap), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not ordered"):
                load_sound_contract(path, require_dialogue_source=False)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
