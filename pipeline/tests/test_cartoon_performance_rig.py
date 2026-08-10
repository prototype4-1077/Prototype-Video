from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from pipeline.cartoon_performance_rig import (
    EXPECTED_ACTION_CLASSES,
    EXPECTED_CHANNELS,
    compile_action_spans,
    compile_caption_cues,
    load_performance_rig_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "concept/characters/june_oxley_performance_rig_v1.json"


class CartoonPerformanceRigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract, cls.assets = load_performance_rig_contract(CONTRACT)

    def test_rig_locks_exact_three_action_output_clock(self) -> None:
        output = self.contract["output"]
        self.assertEqual(
            (output["width"], output["height"], output["fps"], output["frame_count"], output["duration_seconds"]),
            (1920, 1080, 30, 657, 21.9),
        )
        spans = compile_action_spans(self.contract)
        self.assertEqual([span["frame_count"] for span in spans], [171, 258, 228])
        self.assertEqual(
            [(span["output_start_frame"], span["output_end_frame"]) for span in spans],
            [(1, 171), (172, 429), (430, 657)],
        )
        self.assertEqual(self.contract["sequence"]["cut_frames"], [172, 430])

    def test_rig_exposes_complete_semantic_and_action_coverage(self) -> None:
        self.assertEqual({channel["id"] for channel in self.contract["semantic_channels"]}, EXPECTED_CHANNELS)
        self.assertEqual({action["action_class"] for action in self.contract["actions"]}, EXPECTED_ACTION_CLASSES)
        self.assertEqual(
            {view["adapter"] for view in self.contract["views"]},
            {"registered_pose_layers", "registered_pour_layers", "registered_feature_atlases"},
        )
        self.assertEqual(len(self.contract["views"]), 3)
        self.assertEqual(len(self.contract["actions"]), 3)

    def test_every_nested_contract_and_identity_asset_is_hash_pinned(self) -> None:
        self.assertEqual(len(self.assets), 10)
        self.assertTrue(all(path.is_file() for path in self.assets.values()))
        self.assertIn("WIDE_BODY_3Q:contract", self.assets)
        self.assertIn("TABLE_MEDIUM_3Q:contract", self.assets)
        self.assertIn("CLOSE_HERO_FRONT:viseme_atlas", self.assets)
        self.assertIn("sound_contract", self.assets)

    def test_phase26_captions_rebase_to_the_action_reel_clock(self) -> None:
        cues = compile_caption_cues(self.contract)
        self.assertEqual(len(cues), 11)
        self.assertEqual((cues[0]["id"], cues[0]["start_frame"], cues[0]["end_frame"]), ("DX_005", 5, 33))
        self.assertEqual((cues[-1]["id"], cues[-1]["start_frame"], cues[-1]["end_frame"]), ("DX_018", 534, 571))
        self.assertEqual({cue["action_id"] for cue in cues}, {"STAND_UP", "POUR_COFFEE", "DIRECT_ADDRESS"})

    def test_excerpt_loudness_gate_is_explicit(self) -> None:
        loudness = self.contract["sound"]["delivery_loudness"]
        self.assertEqual(loudness["target_lufs_i"], -16.0)
        self.assertEqual(loudness["tolerance_lu"], 1.0)
        self.assertEqual(loudness["maximum_true_peak_dbtp"], -1.0)
        self.assertTrue(loudness["lra_is_informational_for_excerpt"])

    def test_contract_rejects_missing_channel_and_tampered_adapter(self) -> None:
        path = REPO_ROOT / "build" / "broken-performance-rig.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            missing = copy.deepcopy(self.contract)
            missing["semantic_channels"] = missing["semantic_channels"][:-1]
            path.write_text(json.dumps(missing), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "semantic channel"):
                load_performance_rig_contract(path)

            tampered = copy.deepcopy(self.contract)
            tampered["views"][0]["contract"]["sha256"] = "0" * 64
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                load_performance_rig_contract(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
