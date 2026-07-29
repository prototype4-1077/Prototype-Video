import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pipeline.cartoon_asset_library import (
    build_asset_library,
    deformation_pose_plan,
    facial_performance_plan,
    golden_performance_plan,
    load_asset_manifest,
    load_look_profile,
    render_performance_look_gate,
    render_quality_gate,
    shot_quality_frames,
    temporal_review_entries,
    validate_asset_manifest,
    validate_look_profile,
)
from pipeline.cartoon_vertical_slice import compile_plan


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v4.json"
V5_MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v5.json"
V3_MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v3.json"
V2_MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v2.json"
V1_MANIFEST_PATH = ROOT / "concept" / "characters" / "june_oxley_asset_v1.json"
CONFIG_PATH = ROOT / "examples" / "june-porch-vertical-slice.json"
GOLDEN_CONFIG_PATH = ROOT / "examples" / "june-golden-scene-twelve-dollar-mug.json"
PERFORMANCE_PATH = ROOT / "concept" / "style_frames" / "june_golden_scene_performance_slice_v1.json"
LOOK_PROFILE_PATH = ROOT / "concept" / "style_frames" / "june_oxley_npr_look_v1.json"
LOOK_PROFILE_V2_PATH = ROOT / "concept" / "style_frames" / "june_oxley_npr_look_v2.json"
LOOK_PROFILE_V3_PATH = ROOT / "concept" / "style_frames" / "june_oxley_npr_look_v3.json"
LOOK_PROFILE_V4_PATH = ROOT / "concept" / "style_frames" / "june_oxley_npr_look_v4.json"
BLENDER_SOURCE = ROOT / "pipeline" / "blender" / "render_vertical_slice.py"


class CartoonAssetLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_asset_manifest(MANIFEST_PATH)
        cls.v5_manifest = load_asset_manifest(V5_MANIFEST_PATH)
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.golden_config = json.loads(GOLDEN_CONFIG_PATH.read_text(encoding="utf-8"))

    def test_canonical_manifest_covers_full_biped_face_and_both_profiles(self):
        self.assertEqual(self.manifest["asset_version"], "4.0.0")
        self.assertIn("foot.L", self.manifest["rig"]["required_bones"])
        self.assertEqual(set(self.manifest["face"]["visemes"]), set("ABCDEFGHX"))
        self.assertEqual(set(self.manifest["quality_gate"]["profiles"]), {"youtube", "portrait"})

    def test_v1_manifest_remains_valid_for_reproducible_phase3_builds(self):
        self.assertEqual(load_asset_manifest(V1_MANIFEST_PATH)["asset_version"], "1.0.0")

    def test_v2_manifest_remains_valid_for_reproducible_phase4_builds(self):
        self.assertEqual(load_asset_manifest(V2_MANIFEST_PATH)["asset_version"], "2.0.0")

    def test_v3_manifest_remains_valid_for_reproducible_phase5_builds(self):
        self.assertEqual(load_asset_manifest(V3_MANIFEST_PATH)["asset_version"], "3.0.0")

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
        self.assertIn("def _make_june_v4", source)
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
        self.assertTrue(plan["disable_blinks"])
        self.assertTrue(all(shot["camera"] == "close" for shot in plan["shots"]))
        self.assertEqual(plan["render"]["width"], plan["render"]["height"])
        self.assertEqual(self.manifest["quality_gate"]["continuous_engine"], "BLENDER_WORKBENCH")
        self.assertEqual(self.manifest["quality_gate"]["review_engine"], "BLENDER_EEVEE_NEXT")
        self.assertEqual(self.manifest["quality_gate"]["promotion_engine"], "CYCLES")

    def test_v3_without_tiered_render_engines_is_rejected(self):
        invalid = copy.deepcopy(self.manifest)
        invalid["quality_gate"]["review_engine"] = "CYCLES"
        with self.assertRaisesRegex(ValueError, "lookdev review engine"):
            validate_asset_manifest(invalid)

    def test_facial_gate_can_run_as_a_fast_geometry_matrix(self):
        plan, entries = facial_performance_plan(
            self.config,
            size=480,
            engine="BLENDER_WORKBENCH",
            samples=1,
        )
        self.assertEqual(len(entries), 16)
        self.assertEqual((plan["render"]["width"], plan["render"]["height"]), (480, 480))
        self.assertEqual(plan["render"]["engine"], "BLENDER_WORKBENCH")

    def test_v4_deformation_gate_exercises_elbows_knees_and_weight_transfer(self):
        plan, entries = deformation_pose_plan(self.config)
        self.assertEqual(len(entries), 4)
        self.assertEqual([entry["frame"] for entry in entries], [10, 30, 50, 70])
        self.assertEqual((plan["render"]["width"], plan["render"]["height"]), (960, 540))
        self.assertIn("two handed", plan["shots"][1]["gesture"])
        self.assertIn("seated to stand", plan["shots"][2]["gesture"])
        self.assertIn("weight transfer", plan["shots"][3]["gesture"])

    def test_v3_without_single_head_surface_is_rejected(self):
        invalid = copy.deepcopy(self.manifest)
        invalid["modeling"]["head_topology"] = "separate cheek spheres"
        with self.assertRaisesRegex(ValueError, "one sculpted head"):
            validate_asset_manifest(invalid)

    def test_v4_pins_identity_and_requires_weighted_deformation(self):
        self.assertEqual(
            self.manifest["canonical_identity_reference"]["sha256"],
            "c5c32fb5a5c3739e7e87fab8a8d228ddec0b31044fcd6a029851bb9b67b30aa9",
        )
        self.assertTrue(self.manifest["quality_gate"]["deformation_pose_matrix_required"])
        self.assertEqual(
            set(self.manifest["modeling"]["weighted_surfaces"]),
            {"jacket_sleeve.L", "jacket_sleeve.R", "overall_leg.L", "overall_leg.R"},
        )
        source = BLENDER_SOURCE.read_text(encoding="utf-8")
        self.assertIn('armature.use_deform_preserve_volume = True', source)
        self.assertIn('corrective = obj.modifiers.new("CE_Joint_Corrective", "CORRECTIVE_SMOOTH")', source)

    def test_v5_pins_the_exact_performance_clock_and_production_controls(self):
        manifest = self.v5_manifest
        self.assertEqual(manifest["asset_version"], "5.0.0")
        self.assertEqual(manifest["performance_contract"]["shots"], ["GS030", "GS040", "GS050"])
        self.assertEqual(manifest["performance_contract"]["frame_count"], 453)
        self.assertEqual(manifest["performance_contract"]["duration_seconds"], 15.1)
        self.assertEqual(
            manifest["performance_contract"]["sha256"],
            "173f83177095799d5b72e0888718b2a55fdf9bd0b187652983a4e17c439272c9",
        )
        controls = manifest["rig"]["production_controls"]
        self.assertEqual(
            set(controls["ik_targets"]),
            {"hand_ik.L", "hand_ik.R", "foot_ik.L", "foot_ik.R"},
        )
        self.assertEqual(len(controls["finger_controls"]), 10)
        self.assertTrue(manifest["hands"]["articulated_digits"])
        self.assertTrue(manifest["quality_gate"]["performance_slice_full_frame_render"])

    def test_v5_golden_performance_plan_maps_all_nine_poses_frame_exactly(self):
        plan, entries = golden_performance_plan(self.golden_config, PERFORMANCE_PATH)
        self.assertEqual(plan["performance_contract"], "june_golden_scene_performance_v1")
        self.assertEqual(plan["frame_end"], 453)
        self.assertEqual(plan["duration_seconds"], 15.1)
        self.assertEqual((plan["render"]["width"], plan["render"]["height"]), (960, 540))
        self.assertEqual(plan["render"]["engine"], "BLENDER_WORKBENCH")
        self.assertEqual(
            [(entry["shot"], entry["phase"], entry["frame"]) for entry in entries],
            [
                ("GS030", "start", 1), ("GS030", "mid", 93), ("GS030", "end", 171),
                ("GS040", "start", 172), ("GS040", "mid", 260), ("GS040", "end", 339),
                ("GS050", "start", 340), ("GS050", "mid", 398), ("GS050", "end", 453),
            ],
        )
        self.assertEqual(plan["mouth_cues"][0]["frame_start"], 1)
        self.assertEqual(plan["mouth_cues"][-1]["frame_end"], 453)
        self.assertTrue(all(cue["shape"] in set("ABCDEFGHX") for cue in plan["mouth_cues"]))
        self.assertEqual(plan["facial_performance_cues"][-1]["frame_end"], 453)

    def test_v5_builder_contains_true_performance_controls_and_prop_animation(self):
        source = BLENDER_SOURCE.read_text(encoding="utf-8")
        for marker in (
            "def _make_june_v5",
            "def _make_mouth_v5",
            "June_Mouth_Lip_Rim",
            "MOUTH_V5_SHAPE_SCALE",
            "CE_Arm_IK_",
            "CE_Leg_IK_",
            "CE_Eye_Aim_",
            "def _animate_golden_performance",
            "June_Golden_Performance_v1",
            "def _animate_performance_props",
            'item.name.startswith("Chair_")',
            "brow_lifts",
            "lid_shapes",
        ):
            self.assertIn(marker, source)

    def test_performance_gate_mode_rejects_unknown_render_tiers_before_build(self):
        with self.assertRaisesRegex(ValueError, "performance_gate_mode"):
            render_quality_gate(
                GOLDEN_CONFIG_PATH,
                V5_MANIFEST_PATH,
                output_dir=ROOT / "build" / "invalid-performance-gate",
                performance_gate_mode="sometimes",
            )

    def test_phase11_storybook_look_is_versioned_and_renderer_complete(self):
        profile = load_look_profile(LOOK_PROFILE_PATH)
        self.assertEqual(profile["look_id"], "june_oxley_storybook_npr")
        self.assertEqual(profile["engine"], "BLENDER_EEVEE_NEXT")
        self.assertEqual(len(profile["toon"]["levels"]), 3)
        self.assertTrue(profile["outlines"]["enabled"])
        self.assertIn("rim", profile["lighting"])
        source = BLENDER_SOURCE.read_text(encoding="utf-8")
        for marker in (
            "CE_NPR_Toon_Light",
            "CE_NPR_Lantern_Glow",
            "Cool_Story_Rim",
            "scene.render.use_freestyle = True",
            "_configure_npr_cameras",
        ):
            self.assertIn(marker, source)

    def test_phase11_look_rejects_unsafe_line_weight(self):
        invalid = copy.deepcopy(load_look_profile(LOOK_PROFILE_PATH))
        invalid["outlines"]["thickness_px"] = 8.0
        with self.assertRaisesRegex(ValueError, "0.5-3px"):
            validate_look_profile(invalid)

    def test_phase11_temporal_outline_profile_uses_focused_gate(self):
        profile = load_look_profile(LOOK_PROFILE_V2_PATH)
        self.assertEqual(profile["style_version"], "1.1.0")
        self.assertEqual(profile["outlines"]["mode"], "compositor_sobel")
        self.assertLessEqual(profile["render"]["performance_samples"], 12)
        source = BLENDER_SOURCE.read_text(encoding="utf-8")
        self.assertIn("CE_NPR_Temporal_Sobel", source)
        self.assertIn("CE_NPR_Screen_Ink", source)

    def test_focused_look_gate_rejects_unknown_mode_before_build(self):
        with self.assertRaisesRegex(ValueError, "performance_gate_mode"):
            render_performance_look_gate(
                GOLDEN_CONFIG_PATH,
                V5_MANIFEST_PATH,
                look_profile_path=LOOK_PROFILE_V2_PATH,
                output_dir=ROOT / "build" / "invalid-focused-gate",
                performance_gate_mode="previewish",
            )

    def test_phase11_neutral_temporal_profile_locks_focus_and_motion_window(self):
        profile = load_look_profile(LOOK_PROFILE_V3_PATH)
        self.assertEqual(profile["style_version"], "1.2.0")
        self.assertTrue(profile["outlines"]["neutral_luminance"])
        self.assertEqual(profile["render"]["temporal_window_frames"], 30)
        self.assertGreaterEqual(profile["camera"]["f_stop"], 5.6)
        source = BLENDER_SOURCE.read_text(encoding="utf-8")
        self.assertIn("CE_NPR_Neutral_Ink", source)
        self.assertIn("camera_obj.data.dof.focus_object = focus", source)

    def test_phase11_crisp_promotion_profile_targets_the_closeup_window(self):
        profile = load_look_profile(LOOK_PROFILE_V4_PATH)
        render = profile["render"]
        self.assertEqual(profile["style_version"], "1.3.0")
        self.assertFalse(render["motion_blur"])
        self.assertEqual(render["temporal_window_start"], 340)
        self.assertEqual(render["temporal_window_frames"], 30)

    def test_golden_performance_uses_audio_derived_rhubarb_cues(self):
        plan, _ = golden_performance_plan(self.golden_config, PERFORMANCE_PATH)
        contract = plan["lip_sync_contract"]
        self.assertEqual(contract["generator"], "Rhubarb Lip Sync 1.14.0")
        self.assertEqual(contract["cue_count"], 77)
        self.assertEqual(contract["transition_frames"], 2)
        self.assertEqual(plan["mouth_cues"][0]["shape"], "X")
        self.assertEqual(plan["mouth_cues"][1]["shape"], "B")
        self.assertEqual(plan["mouth_cues"][-1]["shape"], "X")
        self.assertEqual(plan["mouth_cues"][-1]["frame_end"], 453)
        source = BLENDER_SOURCE.read_text(encoding="utf-8")
        self.assertIn("anticipation_frame", source)
        self.assertIn('interpolation = "LINEAR" if transition_frames else "CONSTANT"', source)

    def test_temporal_review_matrix_samples_only_rendered_window(self):
        entries = temporal_review_entries(340, 30)
        frames = [entry["frame"] for entry in entries]
        self.assertEqual(len(entries), 9)
        self.assertEqual(frames[0], 340)
        self.assertEqual(frames[-1], 369)
        self.assertEqual(frames, sorted(set(frames)))
        self.assertTrue(all(340 <= frame <= 369 for frame in frames))
        self.assertTrue(all(entry["phase"] == "temporal_review" for entry in entries))

    def test_performance_engine_rejects_unknown_renderer_before_build(self):
        with self.assertRaisesRegex(ValueError, "performance_engine"):
            render_quality_gate(
                GOLDEN_CONFIG_PATH,
                V5_MANIFEST_PATH,
                output_dir=ROOT / "build" / "invalid-performance-engine",
                performance_engine="PAINTBOX",
            )

    def test_v5_without_a_full_performance_gate_is_rejected(self):
        invalid = copy.deepcopy(self.v5_manifest)
        invalid["quality_gate"]["performance_slice_full_frame_render"] = False
        with self.assertRaisesRegex(ValueError, "full-frame deformation performance gate"):
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
