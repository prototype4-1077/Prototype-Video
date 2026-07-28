import copy
import json
from pathlib import Path
import unittest

from pipeline.cartoon_vertical_slice import compile_plan, validate_config


EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "june-porch-vertical-slice.json"


class CartoonVerticalSliceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_example_compiles_contiguous_youtube_proof(self):
        plan = compile_plan(self.config, profile="youtube", quality="proof")
        self.assertEqual(plan["render"]["width"], 480)
        self.assertEqual(plan["render"]["height"], 270)
        self.assertEqual(plan["render"]["fps"], 30)
        self.assertEqual(plan["frame_end"], 390)
        self.assertEqual(plan["shots"][0]["frame_start"], 1)
        for previous, current in zip(plan["shots"], plan["shots"][1:]):
            self.assertEqual(current["frame_start"], previous["frame_end"] + 1)
        self.assertEqual(plan["mouth_cues"], [
            {
                "frame_start": 1,
                "frame_end": 390,
                "shape": "X",
                "start": 0.0,
                "end": 13.0,
            }
        ])

    def test_portrait_production_uses_shared_frame_clock(self):
        plan = compile_plan(self.config, profile="portrait", quality="production")
        self.assertEqual((plan["render"]["width"], plan["render"]["height"]), (1080, 1920))
        self.assertEqual(plan["render"]["fps"], 30)
        self.assertEqual(plan["frame_end"], 390)
        self.assertEqual(plan["render"]["engine"], "BLENDER_EEVEE_NEXT")

    def test_june_must_be_selected_explicitly(self):
        invalid = copy.deepcopy(self.config)
        invalid["character"]["id"] = "generic_host"
        with self.assertRaisesRegex(ValueError, "june_oxley"):
            validate_config(invalid)

    def test_three_shot_minimum_is_enforced(self):
        invalid = copy.deepcopy(self.config)
        invalid["shots"] = invalid["shots"][:2]
        with self.assertRaisesRegex(ValueError, "at least three"):
            validate_config(invalid)


if __name__ == "__main__":
    unittest.main()
