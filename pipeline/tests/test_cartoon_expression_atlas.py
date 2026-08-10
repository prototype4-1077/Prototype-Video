import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from PIL import Image, ImageChops

from pipeline.cartoon_expression_atlas import (
    REQUIRED_EXPRESSIONS,
    expression_cells,
    expression_patch_mask,
    expression_performance_plan,
    load_expression_atlas_contract,
)
from pipeline.cartoon_viseme_atlas import render_lipsync_performance


ROOT = Path(__file__).resolve().parents[2]
EXPRESSION_CONTRACT = ROOT / "concept" / "style_frames" / "june_oxley_expression_atlas_v1.json"
EXPRESSION_CUES = ROOT / "concept" / "style_frames" / "june_golden_scene_expression_cues_v1.json"
VISEME_CONTRACT = ROOT / "concept" / "style_frames" / "june_oxley_viseme_atlas_v1.json"


class CartoonExpressionAtlasTests(unittest.TestCase):
    def test_canonical_expression_atlas_is_registered_and_identity_locked(self):
        contract, image_path = load_expression_atlas_contract(EXPRESSION_CONTRACT)
        self.assertEqual(tuple(contract["grid"]["order"]), REQUIRED_EXPRESSIONS)
        self.assertEqual(contract["neutral_expression"], "neutral")
        self.assertEqual(contract["generation"]["cash_cost"], 0)
        self.assertEqual(
            contract["image"]["sha256"],
            "23a1e4fd24ca13ada1c34722905528b052993c0f37477195f13d2a5b6bcf462b",
        )
        with Image.open(image_path) as atlas:
            self.assertEqual(atlas.size, (1254, 1254))
            cells = expression_cells(atlas, contract)
        self.assertEqual(set(cells), set(REQUIRED_EXPRESSIONS))
        self.assertTrue(all(cell.size == (418, 418) for cell in cells.values()))
        self.assertTrue(all(
            ImageChops.difference(cells[state], cells["neutral"]).getbbox()
            for state in REQUIRED_EXPRESSIONS[1:]
        ))

    def test_expression_patch_mask_is_feathered_and_bounded(self):
        contract, _ = load_expression_atlas_contract(EXPRESSION_CONTRACT)
        mask = expression_patch_mask(contract)
        self.assertEqual(mask.size, (288, 185))
        self.assertEqual(mask.getpixel((0, 0)), 0)
        self.assertEqual(mask.getpixel((mask.width - 1, mask.height - 1)), 0)
        self.assertGreaterEqual(mask.getpixel((mask.width // 2, mask.height // 2)), 250)

    def test_authored_expression_clock_covers_all_states_and_453_frames(self):
        metadata, plan = expression_performance_plan(EXPRESSION_CUES)
        self.assertEqual(metadata["performance_id"], "june_golden_scene_expression_v1")
        self.assertEqual(metadata["frame_count"], 453)
        self.assertEqual(metadata["duration_seconds"], 15.1)
        self.assertEqual(metadata["cue_count"], 14)
        self.assertEqual(set(metadata["states"]), set(REQUIRED_EXPRESSIONS))
        self.assertEqual(plan[0]["to_state"], "neutral")
        self.assertEqual(plan[-1]["to_state"], "compassion")
        first_blink = next(item for item in plan if item["to_state"] == "blink")
        self.assertEqual(first_blink["blend"], 0.5)

    def test_expression_cues_reject_gap_unknown_state_and_wrong_clock(self):
        source = json.loads(EXPRESSION_CUES.read_text(encoding="utf-8"))
        mutations = (
            lambda payload: payload["cues"][1].update(start=1.4),
            lambda payload: payload["cues"][1].update(state="wink"),
            lambda payload: payload.update(frame_count=452),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp_dir:
                invalid = copy.deepcopy(source)
                mutation(invalid)
                path = Path(temp_dir) / "cues.json"
                path.write_text(json.dumps(invalid), encoding="utf-8")
                with self.assertRaises(ValueError):
                    expression_performance_plan(path)

    def test_short_performance_composes_expression_before_mouth_and_reports_both(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            mouth_cues = root / "mouth.json"
            mouth_cues.write_text(json.dumps({
                "metadata": {"duration": 0.2},
                "mouthCues": [
                    {"start": 0.0, "end": 0.1, "value": "X"},
                    {"start": 0.1, "end": 0.2, "value": "B"},
                ],
            }), encoding="utf-8")
            expression_cues = root / "expression.json"
            expression_cues.write_text(json.dumps({
                "contract_version": 1,
                "performance_id": "test_expression",
                "character_id": "june_oxley",
                "atlas_id": "june_oxley_canonical_expressions",
                "fps": 30,
                "duration_seconds": 0.2,
                "frame_count": 6,
                "default_transition_frames": 2,
                "cues": [
                    {"start": 0.0, "end": 0.1, "state": "neutral"},
                    {"start": 0.1, "end": 0.2, "state": "blink"},
                ],
            }), encoding="utf-8")
            output = root / "edit" / "expression-performance"

            def create_video(command, *, check):
                self.assertTrue(check)
                Path(command[-1]).write_bytes(b"expression-performance-video")

            with mock.patch(
                "pipeline.cartoon_viseme_atlas.subprocess.run",
                side_effect=create_video,
            ):
                report = render_lipsync_performance(
                    VISEME_CONTRACT,
                    mouth_cues,
                    output,
                    expression_contract_path=EXPRESSION_CONTRACT,
                    expression_cue_path=expression_cues,
                    ffmpeg=sys.executable,
                    output_scale=1,
                )
        self.assertEqual(report["frame_count"], 6)
        self.assertEqual(report["expression"]["atlas_id"], "june_oxley_canonical_expressions")
        self.assertEqual(report["expression"]["cue_count"], 2)
        self.assertEqual(report["expression"]["states"], ["blink", "neutral"])


if __name__ == "__main__":
    unittest.main()
