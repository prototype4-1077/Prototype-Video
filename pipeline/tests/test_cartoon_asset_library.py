import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pipeline.cartoon_asset_library import (
    build_asset_library,
    load_asset_manifest,
    shot_quality_frames,
    validate_asset_manifest,
)
from pipeline.cartoon_vertical_slice import compile_plan


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v1.json"
CONFIG_PATH = ROOT / "examples" / "june-porch-vertical-slice.json"


class CartoonAssetLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_asset_manifest(MANIFEST_PATH)
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_canonical_manifest_covers_full_biped_face_and_both_profiles(self):
        self.assertEqual(self.manifest["asset_version"], "1.0.0")
        self.assertIn("foot.L", self.manifest["rig"]["required_bones"])
        self.assertEqual(set(self.manifest["face"]["visemes"]), set("ABCDEFGHX"))
        self.assertEqual(set(self.manifest["quality_gate"]["profiles"]), {"youtube", "portrait"})

    def test_proxy_body_and_cowboy_regressions_are_rejected(self):
        invalid = copy.deepcopy(self.manifest)
        invalid["design_lock"]["body"] = "round spherical proxy"
        invalid["design_lock"]["forbidden"].remove("cowboy hat")
        with self.assertRaisesRegex(ValueError, "lean"):
            validate_asset_manifest(invalid)

    def test_quality_frames_select_the_middle_of_each_authored_shot(self):
        plan = compile_plan(self.config, profile="youtube", quality="production")
        self.assertEqual(shot_quality_frames(plan), [54, 179, 320])

    def test_builder_propagates_blender_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "june.blend"
            def create_output(_command, *, check):
                self.assertTrue(check)
                output.touch()

            with mock.patch(
                "pipeline.cartoon_asset_library._executable", return_value="blender"
            ), mock.patch("pipeline.cartoon_asset_library.subprocess.run", side_effect=create_output) as run:
                build_asset_library(MANIFEST_PATH, output, blender="blender")
        command = run.call_args.args[0]
        self.assertIn("--python-exit-code", command)
        self.assertEqual(command[command.index("--python-exit-code") + 1], "1")
        self.assertTrue(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
