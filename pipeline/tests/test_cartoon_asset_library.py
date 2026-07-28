import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pipeline.cartoon_asset_library import (
    build_asset_library,
    facial_performance_plan,
    load_asset_manifest,
    shot_quality_frames,
    validate_asset_manifest,
)
from pipeline.cartoon_vertical_slice import compile_plan


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v3.json"
V2_MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v2.json"
V1_MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v1.json"
CONFIG_PATH = ROOT / "examples" / "june-porch-vertical-slice.json"
BLENDER_SOURCE = ROOT / "pipeline" / "blender" / "render_vertical_slice.py"


class CartoonAssetLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_asset_manifest(MANIFEST_PATH)
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_canonical_manifest_covers_full_biped_face_and_both_profiles(self):
        self.assertEqual(self.manifest["asset_version"], "3.0.0")
        self.assertIn("foot.L", self.manifest["rig"]["required_bones"])
        self.assertEqual(set(self.manifest["face"]["visemes"]), set("ABCDEFGHX"))
        self.assertEqual(set(self.manifest["quality_gate"]["profiles"]), {"youtube", "portrait"})

    def test_v1_manifest_remains_valid_for_reproducible_phase3_builds(self):
        self.assertEqual(load_asset_manifest(V1_MANIFEST_PATH)["asset_version"], "1.0.0")

    def test_v2_manifest_remains_valid_for_reproducible_phase4_builds(self):
        self.assertEqual(load_asset_manifest(V2_MANIFEST_PATH)["asset_version"], "2.0.0")

    def test_v2_requires_smooth_modeling_correctives_and_independent_lids(self):
        self.assertEqual(self.manifest["delivery"]["generation"], "artist_directed_runtime_build")
        self.assertIn("smooth", self.manifest["modeling"]["surface_standard"])
        self.assertEqual(
            set(self.manifest["modeling"]["corrective_shapes"]),
            {"brow_raise", "brow_knit", "squint", "cheek_raise"},
        )
        self.assertTrue(self.manifest["hands"]["segmented_digits"])
        self.assertTrue(self.manifest["quality_gate"]["human_art_approval_required"])

    def test_v2_builder_preserves_legacy_asset_and_never_scales_eyes_for_new_blinks(self):
        source = BLENDER_SOURCE.read_text(encoding="utf-8")
        self.assertIn("def _make_june_v1", source)
        self.assertIn("def _make_june_v2", source)
        self.assertIn("def _make_june_v3", source)
        self.assertIn('upper.location.z -= 0.038 * blend', source)
        self.assertIn('rig["ce_surface_standard"]', source)

    def test_v3_requires_unified_surfaces_and_a_complete_facial_matrix(self):
        self.assertEqual(self.manifest["modeling"]["head_topology"], "single_sculpted_surface")
        self.assertEqual(
            set(self.manifest["modeling"]["unified_surfaces"]),
            {"head", "plaid_torso", "open_denim_shell", "beard_patch"},
        )
        self.assertTrue(self.manifest["quality_gate"]["facial_performance_matrix_required"])
        plan, entries = facial_performance_plan(self.config)
        self.assertEqual([entry["label"] for entry in entries[:9]], list("ABCDEFGHX"))
        self.assertEqual(len(entries), 16)
        self.assertTrue(all(shot["camera"] == "close" for shot in plan["shots"]))
        self.assertEqual(plan["render"]["width"], plan["render"]["height"])

    def test_v3_without_single_head_surface_is_rejected(self):
        invalid = copy.deepcopy(self.manifest)
        invalid["modeling"]["head_topology"] = "separate cheek spheres"
        with self.assertRaisesRegex(ValueError, "one sculpted head"):
            validate_asset_manifest(invalid)

    def test_proxy_body_and_cowboy_regressions_are_rejected(self):
        invalid = copy.deepcopy(self.manifest)
        invalid["design_lock"]["body"] = "round spherical proxy"
        invalid["design_lock"]["forbidden"].remove("cowboy hat")
        with self.assertRaisesRegex(ValueError, "lean"):
            validate_asset_manifest(invalid)

    def test_v2_without_corrective_shapes_is_rejected(self):
        invalid = copy.deepcopy(self.manifest)
        invalid["modeling"]["corrective_shapes"] = ["brow_raise"]
        with self.assertRaisesRegex(ValueError, "corrective"):
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
