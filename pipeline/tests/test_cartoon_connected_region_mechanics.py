from __future__ import annotations

import copy
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import cv2
import numpy as np

import pipeline.cartoon_connected_region_mechanics as mechanics
from pipeline.cartoon_reconstruction_locked_patch import (
    extract_locked_patches,
    load_reconstruction_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "concept/characters/june_oxley_connected_region_mechanics_v1.json"
REGION_IDS = {
    "lower_garment",
    "torso_shell",
    "left_sleeve",
    "right_sleeve",
    "head_neck",
    "left_hand",
    "right_hand_mug",
    "left_boot",
    "right_boot",
}
FORBIDDEN_SPLITS = {
    "left_upper_arm",
    "left_forearm",
    "right_upper_arm",
    "right_forearm",
    "left_thigh",
    "left_shin",
    "right_thigh",
    "right_shin",
    "mug",
    "right_hand",
}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _violations(contract: dict) -> list[str]:
    failures: list[str] = []
    lock = contract.get("phase30_lock", {})
    timing = contract.get("timing", {})
    clock = contract.get("motion_clock", {})
    mechanics = contract.get("region_mechanics", {})
    rows = mechanics.get("regions", [])
    row_by_id = {row.get("id"): row for row in rows}
    ids = set(row_by_id)
    render = contract.get("render_order", {})
    seams = contract.get("support_overlap_seams", {})
    gates = contract.get("contact_and_topology_gates", {})
    pixels = contract.get("diagnostic_render", {})
    delivery = contract.get("delivery", {})
    report = contract.get("report_schema", {})
    failure = contract.get("failure_policy", {})

    if any(
        not lock.get(key, {}).get("sha256")
        for key in ("contract", "implementation", "sole_character_source")
    ):
        failures.append("phase30_hash_lock")
    if timing.get("frame_count") != 49 or timing.get("fps") != 30 or timing.get("frame_end") != 49:
        failures.append("timing")
    if (
        clock.get("key_frames") != [1, 7, 13, 19, 25, 31, 37, 43, 49]
        or clock.get("interpolation") != "monotone_cubic_hermite_pchip_each_scalar"
        or clock.get("clamp_no_overshoot") is not True
        or clock.get("first_last_exact") is not True
    ):
        failures.append("motion_clock")
    if len(rows) != 9 or ids != REGION_IDS or ids & FORBIDDEN_SPLITS:
        failures.append("honest_region_inventory")
    if row_by_id.get("lower_garment", {}).get("mechanic") != "continuous_five_control_cage":
        failures.append("continuous_lower_garment")
    if row_by_id.get("lower_garment", {}).get("independent_leg_child_patch_count") != 0:
        failures.append("no_leg_splits")
    if any(
        row_by_id.get(identifier, {}).get("topology") != "continuous_shoulder_to_cuff"
        for identifier in ("left_sleeve", "right_sleeve")
    ):
        failures.append("continuous_sleeves")
    right_hand_mug = row_by_id.get("right_hand_mug", {})
    if right_hand_mug.get("atomic") is not True or right_hand_mug.get("mechanic") != "atomic_rigid_2d_transform":
        failures.append("atomic_right_hand_mug")
    for identifier in ("left_boot", "right_boot"):
        boot = row_by_id.get(identifier, {})
        if boot.get("mechanic") != "identity_contact_lock" or any(
            boot.get(key) != expected
            for key, expected in (
                ("dx_formula", "0"),
                ("dy_formula", "0"),
                ("rotation_deg_formula", "0"),
                ("scale_x_formula", "1"),
                ("scale_y_formula", "1"),
            )
        ):
            failures.append("planted_boots")
            break
    order = render.get("region_ids", [])
    if len(order) != 9 or set(order) != REGION_IDS or render.get("per_frame_reordering_allowed") is not False:
        failures.append("stable_render_order")
    if (
        len(seams.get("required_pairs", [])) != 8
        or seams.get("minimum_overlap_pixels_each_pair_each_frame") != 512
        or seams.get("minimum_overlap_retention_fraction_of_phase30") != 0.25
    ):
        failures.append("support_overlap_seams")
    if (
        gates.get("maximum_nonboot_centroid_step_preview_px_per_frame") != 4.0
        or gates.get("maximum_cage_vertex_step_preview_px_per_frame") != 4.0
        or gates.get("maximum_rotation_step_deg_per_frame") != 0.35
    ):
        failures.append("bounded_motion")
    if pixels.get("new_character_texture_allowed") is not False or pixels.get(
        "generated_character_texture_pixel_count_required"
    ) != 0:
        failures.append("no_new_character_texture")
    if pixels.get("procedural_diagnostic_flat_color_pixels_allowed") is not True:
        failures.append("diagnostic_flat_color_scope")
    if pixels.get("flat_color_scope") != "only_pixels_inside_transformed_phase30_region_support":
        failures.append("diagnostic_support_scope")
    video = delivery.get("video", {})
    if (video.get("width"), video.get("height"), video.get("fps"), video.get("frame_count")) != (
        960,
        540,
        30,
        49,
    ):
        failures.append("delivery")
    required_top = report.get("required_top_level_fields", [])
    if "diagnostic_pixel_policy" not in required_top or "gate_results" not in required_top:
        failures.append("report_schema")
    if failure.get("mode") != "fail_closed" or failure.get("fallback_allowed") is not False:
        failures.append("fail_closed")
    return failures


class ConnectedRegionMechanicsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _read_json(CONTRACT_PATH)

    def test_phase30_contract_module_and_source_are_hash_locked(self) -> None:
        lock = self.contract["phase30_lock"]
        self.assertEqual(lock["required_patch_count"], 9)
        self.assertEqual(set(lock["required_region_ids"]), REGION_IDS)
        self.assertTrue(lock["contract"]["required_machine_passed_before_phase31"])
        for key in ("contract", "implementation", "sole_character_source"):
            reference = lock[key]
            with self.subTest(reference=key):
                self.assertEqual(_sha256(ROOT / reference["path"]), reference["sha256"])
        for reference in lock["inherited_control_and_metadata"].values():
            self.assertEqual(_sha256(ROOT / reference["path"]), reference["sha256"])
        self.assertEqual(set(lock["expected_derived_patch_rgba_sha256"]), REGION_IDS)
        self.assertTrue(all(len(value) == 64 for value in lock["expected_derived_patch_rgba_sha256"].values()))
        self.assertEqual(lock["required_phase30_properties"]["lower_garment_semantic_owner_pixels"], 72560)
        self.assertEqual(lock["required_phase30_properties"]["semantic_overlap_pixels"], 82229)

    def test_clock_is_exactly_49_frames_at_30fps_and_closes(self) -> None:
        timing = self.contract["timing"]
        self.assertEqual((timing["frame_start"], timing["frame_end"], timing["frame_count"]), (1, 49, 49))
        self.assertEqual(timing["fps"], 30)
        self.assertAlmostEqual(timing["duration_seconds"], 49 / 30, places=12)
        keys = [1, 7, 13, 19, 25, 31, 37, 43, 49]
        self.assertEqual(timing["key_frames"], keys)
        self.assertEqual(timing["sample_frames"], keys)
        self.assertEqual(timing["scalar_interpolation"], "monotone_cubic_hermite_pchip")
        self.assertEqual(timing["interpolation_overshoot_policy"], "clamp_to_neighboring_key_values")
        clock = self.contract["motion_clock"]
        self.assertEqual(clock["key_frames"], keys)
        self.assertEqual(clock["interpolation"], "monotone_cubic_hermite_pchip_each_scalar")
        self.assertTrue(clock["clamp_no_overshoot"])
        self.assertTrue(clock["first_last_exact"])
        for track in clock["tracks"].values():
            self.assertEqual(len(track), 9)
            self.assertEqual(track[0], track[-1])

    def test_exact_region_transform_formulas_match_the_architecture_schedule(self) -> None:
        mechanics = self.contract["region_mechanics"]
        self.assertEqual(mechanics["coordinate_space"], "gs030_raw_source_pixels_before_phase27_registration")
        self.assertEqual(
            mechanics["transform_order"],
            "source_support_then_declared_deformation_then_stable_render_order_then_single_unchanged_phase27_registration_then_960x540",
        )
        self.assertEqual(mechanics["registration_application_count"], 1)
        rows = {row["id"]: row for row in mechanics["regions"]}
        self.assertEqual(rows["left_sleeve"]["mechanic"], "continuous_three_control_cage")
        self.assertEqual(rows["right_sleeve"]["mechanic"], "continuous_three_control_cage")
        self.assertEqual(set(rows), REGION_IDS)
        tracks = self.contract["motion_clock"]["tracks"]
        self.assertEqual(tracks["pelvis_translation_source_px"], [[0,0],[-3,2],[6,12],[10,18],[-2,-5],[2,4],[-1,-2],[0,1],[0,0]])
        self.assertEqual(tracks["left_knee_local_offset_source_px"], [[0,0],[-1,1],[-4,4],[-7,7],[2,-2],[-2,2],[1,-1],[-0.5,0.5],[0,0]])
        self.assertEqual(tracks["right_knee_local_offset_source_px"], [[0,0],[1,1],[3,4],[6,6],[-2,-2],[2,2],[-1,-1],[0.5,0.5],[0,0]])
        self.assertEqual(tracks["torso_translation_source_px"], [[0,0],[-4,1],[5,8],[9,12],[-2,-4],[1.5,3],[-0.75,-1.5],[0.25,0.75],[0,0]])
        self.assertEqual(tracks["torso_rotation_deg"], [0,-0.35,0.75,1.1,-0.3,0.22,-0.1,0.04,0])
        self.assertEqual(tracks["head_absolute_translation_source_px"], [[0,0],[-4.5,1.5],[5.5,9],[10,14],[-2.5,-5],[1.8,3.7],[-0.95,-1.9],[0.35,0.95],[0,0]])
        self.assertEqual(tracks["head_absolute_rotation_deg"], [0,-0.3575,0.6825,1.0075,-0.3575,0.2405,-0.117,0.0455,0])
        self.assertEqual(tracks["left_hand_absolute_translation_source_px"], [[0,0],[-1,1],[2,4],[5,7],[-1,-2],[1,2],[-0.5,-1],[0.25,0.5],[0,0]])
        self.assertEqual(tracks["left_hand_absolute_rotation_deg"], [0,-0.1,0.25,0.5,-0.2,0.12,-0.06,0.02,0])
        self.assertEqual(tracks["right_hand_mug_absolute_translation_source_px"], [[0,0],[-2,1],[4,5],[7,8],[-1,-2],[1,2],[-0.5,-1],[0.25,0.5],[0,0]])
        self.assertEqual(tracks["right_hand_mug_absolute_rotation_deg"], [0,0.1,-0.2,-0.35,0.15,-0.1,0.05,-0.02,0])
        self.assertEqual(rows["lower_garment"]["mechanic"], "continuous_five_control_cage")
        self.assertEqual(rows["lower_garment"]["left_ankle_fixed_source_xy"], [551.0, 802.0])
        self.assertEqual(rows["lower_garment"]["right_ankle_fixed_source_xy"], [674.0, 776.0])
        self.assertEqual(rows["torso_shell"]["pivot_source_xy"], [603.0, 468.0])
        self.assertEqual(rows["head_neck"]["pivot_source_xy"], [636.0, 195.0])
        for identifier in ("head_neck", "left_hand", "right_hand_mug"):
            self.assertEqual(rows[identifier]["composition"], "absolute_source_space_transform")
        self.assertEqual(rows["left_sleeve"]["control_source_xy"], [[519.0,234.0],[488.0,378.0],[482.0,518.0]])
        self.assertEqual(rows["right_sleeve"]["control_source_xy"], [[735.0,231.0],[767.0,307.0],[850.0,334.0]])
        self.assertEqual(rows["right_hand_mug"]["pivot_source_xy"], [818.0, 300.0])

    def test_boots_are_identity_locked_and_lower_body_is_not_split(self) -> None:
        rows = {row["id"]: row for row in self.contract["region_mechanics"]["regions"]}
        self.assertEqual(rows["left_boot"]["registered_anchor_source_xy"], [553.0, 915.0])
        self.assertEqual(rows["right_boot"]["registered_anchor_source_xy"], [737.0, 864.0])
        self.assertEqual(rows["left_boot"]["sole_receiver_source_xy"], [[537.0,915.0],[572.0,915.0]])
        self.assertEqual(rows["right_boot"]["sole_receiver_source_xy"], [[717.0,864.0],[752.0,864.0]])
        for identifier in ("left_boot", "right_boot"):
            boot = rows[identifier]
            self.assertEqual(boot["mechanic"], "identity_contact_lock")
            self.assertEqual(
                [boot["dx_formula"], boot["dy_formula"], boot["rotation_deg_formula"], boot["scale_x_formula"], boot["scale_y_formula"]],
                ["0", "0", "0", "1", "1"],
            )
        lower = rows["lower_garment"]
        self.assertEqual(lower["topology"], "one_connected_surface_from_waist_through_both_cuffs")
        self.assertEqual(lower["independent_leg_child_patch_count"], 0)
        self.assertFalse(set(rows) & FORBIDDEN_SPLITS)
        gates = self.contract["contact_and_topology_gates"]
        self.assertEqual(gates["boot_transform_matrices_required"], "exact_identity_all_frames")
        self.assertEqual(gates["maximum_registered_anchor_residual_preview_px"], 0.25)

    def test_sleeves_are_continuous_and_right_hand_mug_is_atomic(self) -> None:
        rows = {row["id"]: row for row in self.contract["region_mechanics"]["regions"]}
        self.assertEqual(rows["left_sleeve"]["topology"], "continuous_shoulder_to_cuff")
        self.assertEqual(rows["right_sleeve"]["topology"], "continuous_shoulder_to_cuff")
        self.assertTrue(rows["right_hand_mug"]["atomic"])
        self.assertEqual(rows["right_hand_mug"]["mechanic"], "atomic_rigid_2d_transform")
        self.assertEqual(rows["right_hand_mug"]["parent_region"], "right_sleeve")
        self.assertNotIn("right_hand", rows)
        self.assertNotIn("mug", rows)

    def test_render_order_is_stable_complete_and_unique(self) -> None:
        order = self.contract["render_order"]
        self.assertEqual(
            order["region_ids"],
            [
                "left_boot",
                "right_boot",
                "lower_garment",
                "left_sleeve",
                "right_sleeve",
                "torso_shell",
                "head_neck",
                "left_hand",
                "right_hand_mug",
            ],
        )
        self.assertEqual(order["diagnostic_non_region_layer_ids"], ["receiving_shadow"])
        self.assertEqual(order["layer_ids"][0], "receiving_shadow")
        self.assertEqual(order["layer_ids"][1:], order["region_ids"])
        self.assertEqual(len(order["region_ids"]), len(set(order["region_ids"])))
        self.assertEqual(set(order["region_ids"]), REGION_IDS)
        self.assertFalse(order["per_frame_reordering_allowed"])
        self.assertFalse(order["depth_crossfade_allowed"])

    def test_all_eight_support_overlap_seams_are_pinned(self) -> None:
        seams = self.contract["support_overlap_seams"]
        expected = {
            "head_neck__torso_shell": 10282,
            "left_sleeve__torso_shell": 18286,
            "right_sleeve__torso_shell": 6159,
            "left_hand__left_sleeve": 2677,
            "right_hand_mug__right_sleeve": 5547,
            "lower_garment__torso_shell": 27715,
            "left_boot__lower_garment": 7777,
            "right_boot__lower_garment": 7953,
        }
        actual = {f"{row['a']}__{row['b']}": row["phase30_overlap_pixels"] for row in seams["required_pairs"]}
        self.assertEqual(actual, expected)
        self.assertEqual(seams["minimum_overlap_pixels_each_pair_each_frame"], 512)
        self.assertEqual(seams["minimum_overlap_pixels_each_pair_each_frame_preview"], 160)
        self.assertEqual(seams["minimum_overlap_retention_fraction_of_phase30"], 0.25)
        self.assertEqual(seams["maximum_zero_alpha_seam_paths_each_frame"], 0)
        self.assertEqual(seams["maximum_socket_gap_p95_preview_px"], 1.0)
        self.assertEqual(seams["maximum_socket_gap_preview_px"], 2.0)
        self.assertEqual(seams["maximum_secondary_edge_fraction"], 0.005)
        self.assertTrue(all(value >= 512 for value in actual.values()))

    def test_motion_and_topology_gates_are_bounded(self) -> None:
        gates = self.contract["contact_and_topology_gates"]
        self.assertEqual(gates["required_connected_components_per_region_per_frame"], 1)
        self.assertEqual(gates["required_character_union_connected_components_per_frame"], 1)
        self.assertEqual(gates["topology_alpha_threshold_exclusive"], 16)
        self.assertEqual(gates["maximum_foldovers"], 0)
        self.assertEqual(gates["minimum_lower_garment_triangle_area_ratio"], 0.2)
        self.assertEqual(gates["minimum_lower_garment_silhouette_area_ratio_to_rest"], 0.9)
        self.assertEqual(gates["maximum_lower_garment_silhouette_area_ratio_to_rest"], 1.08)
        self.assertEqual(gates["maximum_right_hand_mug_alpha_area_change_fraction"], 0.0025)
        self.assertEqual(gates["maximum_nonboot_centroid_step_preview_px_per_frame"], 4.0)
        self.assertEqual(gates["maximum_cage_vertex_step_preview_px_per_frame"], 4.0)
        self.assertEqual(gates["maximum_rotation_step_deg_per_frame"], 0.35)
        self.assertEqual(gates["maximum_root_third_difference_preview_px_per_frame_cubed"], 2.0)
        self.assertEqual(gates["minimum_center_of_mass_horizontal_margin_in_two_sole_hull_preview_px"], 12.0)
        self.assertEqual(gates["first_last_transform_maximum_error"], 0.0)
        self.assertEqual(gates["final_speed_required"], 0.0)
        self.assertEqual(gates["decoded_first_last_minimum_alpha_iou"], 0.995)
        self.assertEqual(gates["decoded_first_last_minimum_psnr_db"], 45.0)
        self.assertEqual(gates["independent_leg_child_patch_count"], 0)
        self.assertTrue(gates["atomic_right_hand_mug_required"])
        self.assertTrue(gates["continuous_sleeves_required"])
        self.assertTrue(gates["continuous_lower_garment_required"])

    def test_diagnostic_pixels_are_allowed_but_new_character_texture_is_not(self) -> None:
        diagnostic = self.contract["diagnostic_render"]
        self.assertEqual(diagnostic["mode"], "flat_color_region_id_and_seam_diagnostics")
        self.assertEqual(set(diagnostic["palette"]), REGION_IDS)
        self.assertEqual(diagnostic["flat_color_scope"], "only_pixels_inside_transformed_phase30_region_support")
        self.assertTrue(diagnostic["procedural_diagnostic_flat_color_pixels_allowed"])
        self.assertTrue(diagnostic["procedural_background_and_guide_pixels_allowed"])
        self.assertFalse(diagnostic["phase30_character_texture_used"])
        self.assertFalse(diagnostic["new_character_texture_allowed"])
        self.assertEqual(diagnostic["generated_character_texture_pixel_count_required"], 0)
        self.assertFalse(diagnostic["ai_generated_pixels_allowed"])
        self.assertFalse(diagnostic["inpainted_character_pixels_allowed"])
        self.assertIn("must not claim that all generated pixels are zero", diagnostic["scope_note"])
        provenance = self.contract["provenance_policy"]
        self.assertEqual(provenance["character_texture_sources"], [])
        self.assertTrue(provenance["every_character_shaped_diagnostic_pixel_requires_phase30_region_support"])
        self.assertEqual(provenance["new_character_texture_pixel_count"], 0)

    def test_delivery_is_exact_and_authoring_step_renders_nothing(self) -> None:
        delivery = self.contract["delivery"]
        video = delivery["video"]
        self.assertEqual((video["width"], video["height"], video["fps"], video["frame_count"]), (960, 540, 30, 49))
        self.assertAlmostEqual(video["duration_seconds"], 49 / 30, places=12)
        self.assertEqual(video["codec"], "h264")
        self.assertEqual(video["pixel_format"], "yuv420p")
        self.assertEqual(video["audio"], "none")
        self.assertEqual(delivery["contact_sheet"]["review_frames"], [1, 7, 13, 19, 25, 31, 37, 43, 49])
        self.assertTrue(delivery["video"]["filename"].endswith(".mp4"))
        self.assertTrue(delivery["contact_sheet"]["filename"].endswith(".png"))
        self.assertTrue(delivery["report"]["filename"].endswith(".json"))
        self.assertFalse(delivery["this_contract_authoring_step_renders_media"])

    def test_report_schema_is_exact_and_auditable(self) -> None:
        schema = self.contract["report_schema"]
        self.assertEqual(
            set(schema["required_top_level_fields"]),
            {
                "proof", "contract_id", "phase30_lock", "timing", "region_inventory", "render_order",
                "mechanics", "boot_contacts", "seam_support", "topology", "motion_bounds",
                "balance", "diagnostic_pixel_policy", "provenance", "delivery", "gates", "gate_results",
                "machine_passed", "audience_quality", "cash_cost", "paid_runtime_dependency",
            },
        )
        self.assertIn("diagnostic_flat_color_pixel_count", schema["diagnostic_pixel_policy_fields"])
        self.assertIn("new_character_texture_pixel_count", schema["diagnostic_pixel_policy_fields"])
        self.assertIn("character_shaped_pixels_outside_phase30_support", schema["diagnostic_pixel_policy_fields"])
        self.assertIn("per_pair_minimum_overlap_pixels", schema["seam_support_fields"])
        self.assertIn("first_last_transform_error", schema["region_record_fields"])
        self.assertIn("maximum_cage_vertex_step_preview_px_per_frame", schema["region_record_fields"])
        self.assertIn("settle_extrema_magnitude_order", schema["motion_bounds_fields"])
        self.assertIn("decoded_first_last_alpha_iou", schema["motion_bounds_fields"])
        self.assertEqual(
            schema["balance_fields"],
            ["minimum_center_of_mass_horizontal_margin_in_two_sole_hull_preview_px", "passed"],
        )
        self.assertEqual(schema["gate_result_fields"], ["id", "measured", "operator", "threshold", "passed"])

    def test_failure_policy_is_closed(self) -> None:
        policy = self.contract["failure_policy"]
        self.assertEqual(policy["mode"], "fail_closed")
        self.assertFalse(policy["partial_success_allowed"])
        self.assertFalse(policy["fallback_allowed"])
        self.assertEqual(policy["machine_pass_rule"], "true_only_when_every_required_gate_and_report_section_passes")
        for key, value in policy.items():
            if key.startswith("on_"):
                self.assertEqual(value, "raise", key)
        self.assertEqual(policy["audience_quality_default"]["status"], "not_evaluated")

    def test_static_auditor_rejects_representative_mutations(self) -> None:
        self.assertEqual(_violations(self.contract), [])
        mutations: list[tuple[dict, str]] = []
        missing_hash = copy.deepcopy(self.contract)
        missing_hash["phase30_lock"]["implementation"]["sha256"] = ""
        mutations.append((missing_hash, "phase30_hash_lock"))
        wrong_timing = copy.deepcopy(self.contract)
        wrong_timing["timing"]["frame_count"] = 50
        mutations.append((wrong_timing, "timing"))
        wrong_clock = copy.deepcopy(self.contract)
        wrong_clock["motion_clock"]["interpolation"] = "linear"
        mutations.append((wrong_clock, "motion_clock"))
        split_leg = copy.deepcopy(self.contract)
        split_leg["region_mechanics"]["regions"].append({"id": "left_shin"})
        mutations.append((split_leg, "honest_region_inventory"))
        detached_garment = copy.deepcopy(self.contract)
        next(row for row in detached_garment["region_mechanics"]["regions"] if row["id"] == "lower_garment")[
            "independent_leg_child_patch_count"
        ] = 2
        mutations.append((detached_garment, "no_leg_splits"))
        moving_boot = copy.deepcopy(self.contract)
        next(row for row in moving_boot["region_mechanics"]["regions"] if row["id"] == "left_boot")["dx_formula"] = "1"
        mutations.append((moving_boot, "planted_boots"))
        split_mug = copy.deepcopy(self.contract)
        next(row for row in split_mug["region_mechanics"]["regions"] if row["id"] == "right_hand_mug")["atomic"] = False
        mutations.append((split_mug, "atomic_right_hand_mug"))
        reorder = copy.deepcopy(self.contract)
        reorder["render_order"]["region_ids"][-1] = "left_hand"
        mutations.append((reorder, "stable_render_order"))
        weak_seam = copy.deepcopy(self.contract)
        weak_seam["support_overlap_seams"]["minimum_overlap_pixels_each_pair_each_frame"] = 0
        mutations.append((weak_seam, "support_overlap_seams"))
        unbounded = copy.deepcopy(self.contract)
        unbounded["contact_and_topology_gates"]["maximum_nonboot_centroid_step_preview_px_per_frame"] = 5.0
        mutations.append((unbounded, "bounded_motion"))
        texture_generation = copy.deepcopy(self.contract)
        texture_generation["diagnostic_render"]["new_character_texture_allowed"] = True
        mutations.append((texture_generation, "no_new_character_texture"))
        no_diagnostic_scope = copy.deepcopy(self.contract)
        no_diagnostic_scope["diagnostic_render"]["procedural_diagnostic_flat_color_pixels_allowed"] = False
        mutations.append((no_diagnostic_scope, "diagnostic_flat_color_scope"))
        bad_delivery = copy.deepcopy(self.contract)
        bad_delivery["delivery"]["video"]["frame_count"] = 48
        mutations.append((bad_delivery, "delivery"))
        missing_report_field = copy.deepcopy(self.contract)
        missing_report_field["report_schema"]["required_top_level_fields"].remove("diagnostic_pixel_policy")
        mutations.append((missing_report_field, "report_schema"))
        fallback = copy.deepcopy(self.contract)
        fallback["failure_policy"]["fallback_allowed"] = True
        mutations.append((fallback, "fail_closed"))
        for mutated, expected in mutations:
            with self.subTest(expected=expected):
                self.assertIn(expected, _violations(mutated))


class ConnectedRegionMechanicsRuntimeTests(unittest.TestCase):
    """Adversarial checks for evidence produced by the real Phase 31 runtime."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = mechanics.load_connected_region_mechanics_contract(CONTRACT_PATH)
        phase30_path = mechanics._locked_path(cls.contract["phase30_lock"]["contract"], "Phase30 contract")
        cls.phase30_contract = load_reconstruction_contract(phase30_path)
        # Rendering needs the locked supports but not the more expensive Phase 30
        # reconstruction evaluation.  The full evaluator below performs that audit.
        cls.patches = extract_locked_patches(cls.phase30_contract)

    def test_runtime_rejects_any_canonical_contract_mutation(self) -> None:
        mutations: list[tuple[str, dict]] = []

        changed_track = copy.deepcopy(self.contract)
        changed_track["motion_clock"]["tracks"]["head_absolute_translation_source_px"][3][0] += 1
        mutations.append(("changed motion track", changed_track))

        loosened_gate = copy.deepcopy(self.contract)
        loosened_gate["quality_gates"]["motion"]["maximum_nonboot_centroid_step_preview_px_per_frame"] = 400.0
        mutations.append(("loosened quality gate", loosened_gate))

        deleted_delivery_gate = copy.deepcopy(self.contract)
        del deleted_delivery_gate["quality_gates"]["delivery"]["required_decoded_frame_count"]
        mutations.append(("deleted delivery gate", deleted_delivery_gate))

        empty_report_schema = copy.deepcopy(self.contract)
        empty_report_schema["report_schema"]["required_top_level_fields"] = []
        mutations.append(("empty report schema", empty_report_schema))

        for label, mutated in mutations:
            with self.subTest(label=label):
                with self.assertRaisesRegex(
                    mechanics.ConnectedRegionMechanicsError,
                    "complete Phase31 contract",
                ):
                    mechanics._validate_contract(mutated)

    def test_head_hands_and_mug_are_absolute_source_space_transforms(self) -> None:
        frame_number = 19
        rendered = mechanics.render_flat_mechanics_frame(
            self.contract,
            self.patches,
            frame_number,
        )
        try:
            state = rendered.motion_state["tracks"]
            rows = {row["id"]: row for row in self.contract["region_mechanics"]["regions"]}
            cases = (
                (
                    "head_neck",
                    "head_absolute_translation_source_px",
                    "head_absolute_rotation_deg",
                ),
                (
                    "left_hand",
                    "left_hand_absolute_translation_source_px",
                    "left_hand_absolute_rotation_deg",
                ),
                (
                    "right_hand_mug",
                    "right_hand_mug_absolute_translation_source_px",
                    "right_hand_mug_absolute_rotation_deg",
                ),
            )
            for identifier, translation_track, rotation_track in cases:
                with self.subTest(region=identifier):
                    pivot = np.asarray(rows[identifier]["pivot_source_xy"], dtype=np.float64)
                    expected = mechanics._affine_about(
                        pivot,
                        np.asarray(state[translation_track], dtype=np.float64),
                        float(state[rotation_track]),
                    )
                    np.testing.assert_allclose(
                        rendered.region_transforms[identifier],
                        expected,
                        rtol=0.0,
                        atol=1e-12,
                    )
                    actual_translation = mechanics._transform_point(expected, pivot) - pivot
                    np.testing.assert_allclose(
                        actual_translation,
                        np.asarray(state[translation_track], dtype=np.float64),
                        rtol=0.0,
                        atol=1e-12,
                    )
        finally:
            rendered.close()

    def test_boot_seam_shadow_and_balance_helpers_react_to_rendered_geometry(self) -> None:
        rendered = mechanics.render_flat_mechanics_frame(self.contract, self.patches, 1)
        try:
            base = mechanics._measure_boot_frame(self.contract, rendered, "left_boot")
            shifted_registered_boot = np.zeros_like(rendered.registered_region_masks["left_boot"])
            shifted_registered_boot[:-24] = rendered.registered_region_masks["left_boot"][24:]
            shifted_boot = cv2.resize(
                shifted_registered_boot.astype(np.uint8),
                mechanics.PREVIEW_SIZE,
                interpolation=cv2.INTER_NEAREST,
            ) > 0
            shifted_registered_masks = dict(rendered.registered_region_masks)
            shifted_registered_masks["left_boot"] = shifted_registered_boot
            shifted_masks = dict(rendered.preview_region_masks)
            shifted_masks["left_boot"] = shifted_boot
            shifted_frame = SimpleNamespace(
                registered_region_masks=shifted_registered_masks,
                preview_region_masks=shifted_masks,
                preview_shadow_mask=rendered.preview_shadow_mask,
            )
            shifted = mechanics._measure_boot_frame(self.contract, shifted_frame, "left_boot")
            self.assertGreater(shifted["anchor_residual"], base["anchor_residual"])
            self.assertGreater(shifted["sole_clearance"], base["sole_clearance"])
            self.assertGreater(
                float(np.max(np.linalg.norm(shifted["endpoints"] - base["endpoints"], axis=1))),
                10.0,
            )

            no_shadow_frame = SimpleNamespace(
                registered_region_masks=rendered.registered_region_masks,
                preview_region_masks=rendered.preview_region_masks,
                preview_shadow_mask=np.zeros_like(rendered.preview_shadow_mask),
            )
            self.assertTrue(
                math.isinf(
                    mechanics._measure_boot_frame(
                        self.contract,
                        no_shadow_frame,
                        "left_boot",
                    )["shadow_gap"]
                )
            )

            first = rendered.preview_region_masks["head_neck"]
            second = rendered.preview_region_masks["torso_shell"]
            actual_gap = mechanics._minimum_mask_distance(first, second)
            missing_support = np.zeros_like(second)
            self.assertGreater(
                mechanics._minimum_mask_distance(first, missing_support),
                actual_gap,
            )

            islanded = first.copy()
            islanded[0:3, 0:3] = True
            self.assertGreater(
                mechanics._secondary_component_fraction(islanded),
                mechanics._secondary_component_fraction(first),
            )

            preview_scale_x = mechanics.PREVIEW_SIZE[0] / 1672.0
            final_alpha = rendered.registered_flat_rgba[:, :, 3] > 16
            centroid_x = mechanics._centroid(final_alpha)[0] * preview_scale_x
            support_x = np.concatenate(
                [
                    mechanics._measure_boot_frame(self.contract, rendered, identifier)["endpoints"][:, 0]
                    for identifier in ("left_boot", "right_boot")
                ]
            )
            expected_margin = min(
                centroid_x - float(np.min(support_x)),
                float(np.max(support_x)) - centroid_x,
            )
            self.assertTrue(np.isfinite(expected_margin))
            shifted_alpha = np.zeros_like(final_alpha)
            shifted_alpha[:, 30:] = final_alpha[:, :-30]
            shifted_centroid_x = mechanics._centroid(shifted_alpha)[0] * preview_scale_x
            shifted_margin = min(
                shifted_centroid_x - float(np.min(support_x)),
                float(np.max(support_x)) - shifted_centroid_x,
            )
            self.assertNotAlmostEqual(shifted_margin, expected_margin, places=6)
        finally:
            rendered.close()

    def test_opaque_loop_frames_require_known_background_segmentation(self) -> None:
        rendered = mechanics.render_flat_mechanics_frame(self.contract, self.patches, 1)
        try:
            decoded_rgb = rendered.preview_rgba[:, :, :3]
            opaque_video_alpha = np.ones(decoded_rgb.shape[:2], dtype=bool)
            expected_character = cv2.resize(
                (rendered.registered_flat_rgba[:, :, 3] > 0).astype(np.uint8),
                mechanics.PREVIEW_SIZE,
                interpolation=cv2.INTER_NEAREST,
            ) > 0
            self.assertGreater(
                int(np.count_nonzero(opaque_video_alpha)),
                int(np.count_nonzero(expected_character)),
                "decoded H.264 alpha cannot be treated as character evidence",
            )

            background_rgb = np.asarray(
                self.contract["diagnostic_render"]["canvas_background_rgb"],
                dtype=np.uint8,
            )
            shadow_rgb = np.asarray((8, 9, 11), dtype=np.uint8)
            differs_from_background = np.any(decoded_rgb != background_rgb, axis=2)
            known_shadow_only = rendered.preview_shadow_mask & np.all(
                decoded_rgb == shadow_rgb,
                axis=2,
            )
            segmented_character = differs_from_background & ~known_shadow_only
            np.testing.assert_array_equal(segmented_character, expected_character)
        finally:
            rendered.close()

    def test_locked_patch_injection_rejects_mask_only_corruption(self) -> None:
        candidate = dict(self.patches)
        original = candidate["left_boot"]
        corrupted = original.semantic_support_mask.copy()
        corrupted[0, 0] = ~corrupted[0, 0]
        candidate["left_boot"] = replace(original, semantic_support_mask=corrupted)
        with self.assertRaisesRegex(
            mechanics.ConnectedRegionMechanicsError,
            "left_boot locked patch semantic_support_mask mismatch",
        ):
            mechanics._require_exact_locked_patches(self.patches, candidate)

    def test_decoded_delivery_rejects_a_corrupted_middle_frame(self) -> None:
        background = np.asarray((18, 20, 24), dtype=np.uint8)
        subject = np.asarray((216, 140, 74), dtype=np.uint8)
        reference = []
        masks = []
        for _ in range(49):
            frame = np.empty((48, 64, 3), dtype=np.uint8)
            frame[:] = background
            frame[12:40, 20:44] = subject
            mask = np.zeros((48, 64), dtype=bool)
            mask[12:40, 20:44] = True
            reference.append(frame)
            masks.append(mask)
        decoded = [frame.copy() for frame in reference]
        decoded[24][12:40, 20:44] = background
        audit = mechanics._audit_decoded_delivery(
            self.contract,
            reference,
            masks,
            decoded,
            {"decoded_frame_count_probe": 49},
        )
        self.assertFalse(audit["full_decode_passed"])
        self.assertFalse(audit["records"][24]["passed"])
        self.assertEqual(audit["records"][24]["character_mask_iou"], 0.0)

    def test_subject_roi_psnr_is_not_inflated_by_constant_background(self) -> None:
        reference = np.zeros((64, 64, 3), dtype=np.uint8)
        decoded = reference.copy()
        mask = np.zeros((64, 64), dtype=bool)
        mask[24:40, 24:40] = True
        reference[mask] = (200, 100, 50)
        decoded[mask] = (80, 180, 220)
        psnr, roi_pixels = mechanics._subject_roi_psnr(
            reference,
            decoded,
            mask,
            mask,
            2,
        )
        self.assertLess(psnr, 15.0)
        self.assertLess(roi_pixels, reference.shape[0] * reference.shape[1] // 4)

    def test_all_49_frames_use_final_registered_mask_and_matrix_evidence(self) -> None:
        seen_frames: list[int] = []
        component_counts = {identifier: [] for identifier in mechanics.REGION_IDS}
        union_components: list[int] = []
        centroids = {identifier: [] for identifier in mechanics.REGION_IDS}
        cages = {identifier: [] for identifier in ("lower_garment", "left_sleeve", "right_sleeve")}
        rigid_angles = {identifier: [] for identifier in ("torso_shell", "head_neck", "left_hand", "right_hand_mug")}
        head_magnitudes: list[float] = []
        boot_rows = {identifier: [] for identifier in ("left_boot", "right_boot")}
        seam_overlaps = {
            f"{row['a']}__{row['b']}": []
            for row in self.contract["support_overlap_seams"]["required_pairs"]
        }
        seam_gaps = {key: [] for key in seam_overlaps}
        secondary_fractions: list[float] = []
        balance_margins: list[float] = []
        original_render = mechanics.render_flat_mechanics_frame
        preview_scale = np.asarray(
            (mechanics.PREVIEW_SIZE[0] / 1672.0, mechanics.PREVIEW_SIZE[1] / 941.0),
            dtype=np.float64,
        )
        rows = {row["id"]: row for row in self.contract["region_mechanics"]["regions"]}

        def audited_render(*args, **kwargs):
            rendered = original_render(*args, **kwargs)
            seen_frames.append(rendered.frame)
            threshold = int(self.contract["contact_and_topology_gates"]["topology_alpha_threshold_exclusive"])
            union = rendered.registered_flat_rgba[:, :, 3] > threshold
            union_components.append(mechanics._components(union))
            for identifier in mechanics.REGION_IDS:
                final_mask = rendered.preview_region_masks[identifier]
                component_counts[identifier].append(mechanics._components(final_mask))
                centroids[identifier].append(mechanics._centroid(final_mask))
            for identifier in cages:
                cages[identifier].append(
                    rendered.cage_controls[identifier]["destination"].copy() * preview_scale
                )
            for identifier in rigid_angles:
                matrix = rendered.region_transforms[identifier]
                rigid_angles[identifier].append(float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))))
            head_pivot = np.asarray(rows["head_neck"]["pivot_source_xy"], dtype=np.float64)
            head_magnitudes.append(
                float(
                    np.linalg.norm(
                        mechanics._transform_point(rendered.region_transforms["head_neck"], head_pivot)
                        - head_pivot
                    )
                )
            )
            frame_boot_rows = {
                identifier: mechanics._measure_boot_frame(self.contract, rendered, identifier)
                for identifier in boot_rows
            }
            for identifier, row in frame_boot_rows.items():
                boot_rows[identifier].append(row)
            for row in self.contract["support_overlap_seams"]["required_pairs"]:
                key = f"{row['a']}__{row['b']}"
                first = rendered.registered_region_masks[row["a"]]
                second = rendered.registered_region_masks[row["b"]]
                seam_overlaps[key].append(int(np.count_nonzero(first & second)))
                first_preview = cv2.resize(
                    first.astype(np.uint8), mechanics.PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST
                ) > 0
                second_preview = cv2.resize(
                    second.astype(np.uint8), mechanics.PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST
                ) > 0
                seam_gaps[key].append(mechanics._minimum_mask_distance(first_preview, second_preview))
                secondary_fractions.append(
                    mechanics._secondary_component_fraction(first_preview & second_preview)
                )
            centroid_x = mechanics._centroid(union)[0] * preview_scale[0]
            support_x = np.concatenate(
                [row["endpoints"][:, 0] for row in frame_boot_rows.values()]
            )
            balance_margins.append(
                min(
                    centroid_x - float(np.min(support_x)),
                    float(np.max(support_x)) - centroid_x,
                )
            )
            return rendered

        with mock.patch.object(mechanics, "render_flat_mechanics_frame", side_effect=audited_render):
            try:
                envelope = mechanics.evaluate_connected_region_mechanics(self.contract)
            except mechanics.ConnectedRegionMechanicsError as exc:
                disconnected = {
                    identifier: [frame for frame, count in zip(seen_frames, counts) if count != 1]
                    for identifier, counts in component_counts.items()
                    if any(count != 1 for count in counts)
                }
                self.fail(
                    f"49-frame Phase31 preflight did not pass: {exc}; "
                    f"rendered_frames={len(seen_frames)}; disconnected_final_masks={disconnected}"
                )

        self.assertEqual(seen_frames, list(range(1, 50)))
        self.assertTrue(envelope["mechanics_passed"])
        self.assertFalse(envelope["machine_passed"])
        self.assertTrue(envelope["delivery_pending"])
        report = envelope["report"]

        self.assertEqual(max(union_components), 1)
        self.assertTrue(
            all(count == 1 for counts in component_counts.values() for count in counts),
            "every final registered region mask at alpha >16 must remain connected",
        )

        expected_centroid_step = max(
            float(np.linalg.norm(current - previous))
            for identifier, values in centroids.items()
            if identifier not in ("left_boot", "right_boot")
            for previous, current in zip(values, values[1:])
        )
        self.assertAlmostEqual(
            report["motion_bounds"]["maximum_nonboot_centroid_step_preview_px_per_frame"],
            expected_centroid_step,
            places=9,
        )
        expected_cage_step = max(
            float(np.max(np.linalg.norm(current - previous, axis=1)))
            for values in cages.values()
            for previous, current in zip(values, values[1:])
        )
        self.assertAlmostEqual(
            report["motion_bounds"]["maximum_cage_vertex_step_preview_px_per_frame"],
            expected_cage_step,
            places=9,
        )
        expected_rotation_step = max(
            abs(current - previous)
            for values in rigid_angles.values()
            for previous, current in zip(values, values[1:])
        )
        self.assertAlmostEqual(
            report["motion_bounds"]["maximum_rotation_step_deg_per_frame"],
            expected_rotation_step,
            places=9,
        )
        self.assertAlmostEqual(
            report["motion_bounds"]["maximum_head_total_translation_magnitude_source_px"],
            max(head_magnitudes),
            places=9,
        )

        all_boot_rows = [row for values in boot_rows.values() for row in values]
        self.assertAlmostEqual(
            report["boot_contacts"]["maximum_sole_distance_p95_preview_px"],
            max(row["sole_distance_p95"] for row in all_boot_rows),
            places=9,
        )
        self.assertAlmostEqual(
            report["boot_contacts"]["maximum_shadow_gap_preview_px"],
            max(row["shadow_gap"] for row in all_boot_rows),
            places=9,
        )
        endpoint_motion = max(
            float(np.max(np.linalg.norm(current["endpoints"] - previous["endpoints"], axis=1)))
            for values in boot_rows.values()
            for previous, current in zip(values, values[1:])
        )
        self.assertAlmostEqual(
            report["boot_contacts"]["maximum_endpoint_motion_preview_px_per_frame"],
            endpoint_motion,
            places=9,
        )

        self.assertEqual(
            report["seam_support"]["per_pair_minimum_overlap_pixels"],
            {key: min(values) for key, values in seam_overlaps.items()},
        )
        all_gaps = [value for values in seam_gaps.values() for value in values]
        self.assertAlmostEqual(
            report["seam_support"]["maximum_socket_gap_preview_px"],
            max(all_gaps),
            places=9,
        )
        self.assertAlmostEqual(
            report["seam_support"]["maximum_secondary_edge_fraction"],
            max(secondary_fractions),
            places=9,
        )
        self.assertAlmostEqual(
            report["balance"]["minimum_center_of_mass_horizontal_margin_in_two_sole_hull_preview_px"],
            min(balance_margins),
            places=9,
        )

    def test_require_delivery_true_fails_before_any_encode(self) -> None:
        with self.assertRaisesRegex(
            mechanics.ConnectedRegionMechanicsError,
            "delivery is required but has not been encoded and audited",
        ):
            mechanics.evaluate_connected_region_mechanics(
                self.contract,
                require_delivery=True,
            )


class ConnectedRegionMechanicsDeliveryTransactionTests(unittest.TestCase):
    """Fast mocked checks for the one-encode, all-or-nothing publisher."""

    def setUp(self) -> None:
        self.contract = _read_json(CONTRACT_PATH)
        self.reference_rgb = [np.zeros((2, 2, 3), dtype=np.uint8) for _ in range(49)]
        self.reference_masks = [np.ones((2, 2), dtype=bool) for _ in range(49)]

    @staticmethod
    def _report() -> dict:
        return {
            "proof": {
                "diagnostic_sequence_sha256": "reference-sequence",
                "in_memory_only": True,
                "media_rendered": False,
            },
            "motion_bounds": {
                "decoded_first_last_alpha_iou": None,
                "decoded_first_last_psnr_db": None,
                "passed": False,
            },
            "provenance": {},
            "delivery": {"passed": False},
            "gate_results": [],
            "machine_passed": False,
        }

    @staticmethod
    def _probe() -> dict:
        return {
            "width": 960,
            "height": 540,
            "codec": "h264",
            "pixel_format": "yuv420p",
            "stream_count": 1,
            "video_stream_count": 1,
            "audio_stream_count": 0,
            "r_frame_rate": "30/1",
            "avg_frame_rate": "30/1",
            "time_base": "1/90000",
            "duration_ts": 147000,
            "stream_duration_rational": "49/30",
            "duration_seconds": 49 / 30,
            "container_duration_seconds": 49 / 30,
            "container_duration_error_seconds": 0.0,
        }

    @staticmethod
    def _audit() -> dict:
        return {
            "loop_iou": 1.0,
            "loop_psnr": 99.0,
            "full_decode_passed": True,
            "decoded_sequence_sha256": "decoded-sequence",
            "background_candidates": [[18, 20, 24], [8, 9, 11]],
            "minimum_rgb_distance": 32.0,
            "dilation_px": 2,
            "minimum_iou": 1.0,
            "mean_iou": 1.0,
            "minimum_psnr": 99.0,
            "mean_psnr": 99.0,
            "records": [],
        }

    @staticmethod
    def _gate_results(_contract: dict, measured: dict) -> list[dict]:
        identifiers = (
            "provenance.required_phase31_contract_sha256_match",
            "provenance.required_phase31_implementation_sha256_match",
            "motion.minimum_decoded_first_last_alpha_iou",
            "delivery.required_video_file",
            "delivery.required_contact_sheet_file",
            "delivery.required_report_file",
        )
        return [
            {
                "id": identifier,
                "measured": measured[identifier],
                "operator": "equal",
                "threshold": True,
                "passed": bool(measured[identifier]),
            }
            for identifier in identifiers
        ]

    def _run_mocked_delivery(
        self,
        output_dir: Path,
        *,
        probe_side_effect: Exception | None = None,
    ) -> tuple[dict | None, list[Path], list[bool]]:
        contract = copy.deepcopy(self.contract)
        contract["delivery"]["output_directory"] = str(output_dir)
        encoded_paths: list[Path] = []
        report_states: list[bool] = []
        real_write_json = mechanics._write_json_atomically

        def encode(_ffmpeg, _frames, path, _contract) -> None:
            encoded_paths.append(path)
            path.write_bytes(b"one-encode")

        def write_contact_sheet(_frames, _keys, path) -> None:
            path.write_bytes(b"decoded-contact-sheet")

        def write_json(path, payload) -> None:
            report_states.append(bool(payload["machine_passed"]))
            real_write_json(path, payload)

        probe = mock.Mock(
            side_effect=probe_side_effect,
            return_value=self._probe(),
        )
        report = self._report()
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(mechanics, "_validate_contract"))
            stack.enter_context(
                mock.patch.object(
                    mechanics,
                    "evaluate_connected_region_mechanics",
                    return_value={
                        "mechanics_passed": True,
                        "machine_passed": False,
                        "delivery_pending": True,
                        "report": report,
                    },
                )
            )
            stack.enter_context(
                mock.patch.object(
                    mechanics,
                    "_collect_delivery_references",
                    return_value=(
                        self.reference_rgb,
                        self.reference_masks,
                        "reference-sequence",
                    ),
                )
            )
            stack.enter_context(mock.patch.object(mechanics, "_encode_h264_once", side_effect=encode))
            stack.enter_context(mock.patch.object(mechanics, "_probe_phase31_video", probe))
            stack.enter_context(
                mock.patch.object(
                    mechanics,
                    "_decode_exact_rgb_frames",
                    return_value=self.reference_rgb,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    mechanics,
                    "_audit_decoded_delivery",
                    return_value=self._audit(),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    mechanics,
                    "_write_decoded_keyframe_contact_sheet",
                    side_effect=write_contact_sheet,
                )
            )
            stack.enter_context(mock.patch.object(mechanics, "_gate_results", side_effect=self._gate_results))
            stack.enter_context(mock.patch.object(mechanics, "_validate_report_schema"))
            stack.enter_context(mock.patch.object(mechanics, "_write_json_atomically", side_effect=write_json))
            if probe_side_effect is not None:
                with self.assertRaises(type(probe_side_effect)):
                    mechanics.render_connected_region_mechanics(contract)
                return None, encoded_paths, report_states
            result = mechanics.render_connected_region_mechanics(contract)
            return result, encoded_paths, report_states

    def test_delivery_encodes_once_then_atomically_publishes_complete_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "phase31-delivery"
            report, encoded_paths, report_states = self._run_mocked_delivery(output_dir)
            self.assertEqual(len(encoded_paths), 1)
            self.assertNotEqual(encoded_paths[0].parent, output_dir)
            self.assertTrue(encoded_paths[0].parent.name.startswith(".phase31-delivery.staging-"))
            self.assertEqual(report_states, [False, True])
            self.assertTrue(report["machine_passed"])
            self.assertTrue(output_dir.is_dir())
            self.assertTrue((output_dir / self.contract["delivery"]["video"]["filename"]).is_file())
            self.assertTrue((output_dir / self.contract["delivery"]["contact_sheet"]["filename"]).is_file())
            final_report = _read_json(
                output_dir / self.contract["delivery"]["report"]["filename"]
            )
            self.assertTrue(final_report["machine_passed"])
            self.assertEqual(list(Path(temporary).glob(".*.staging-*")), [])

    def test_delivery_failure_removes_staging_and_leaves_no_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "phase31-delivery"
            report, encoded_paths, report_states = self._run_mocked_delivery(
                output_dir,
                probe_side_effect=mechanics.ConnectedRegionMechanicsError("probe failed"),
            )
            self.assertIsNone(report)
            self.assertEqual(len(encoded_paths), 1)
            self.assertEqual(report_states, [])
            self.assertFalse(output_dir.exists())
            self.assertEqual(list(Path(temporary).glob(".*.staging-*")), [])

    def test_existing_final_directory_blocks_before_evaluation_or_encode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "phase31-delivery"
            output_dir.mkdir()
            contract = copy.deepcopy(self.contract)
            contract["delivery"]["output_directory"] = str(output_dir)
            with mock.patch.object(mechanics, "_validate_contract"), mock.patch.object(
                mechanics, "evaluate_connected_region_mechanics"
            ) as evaluate, mock.patch.object(mechanics, "_encode_h264_once") as encode:
                with self.assertRaisesRegex(
                    mechanics.ConnectedRegionMechanicsError,
                    "delivery directory already exists",
                ):
                    mechanics.render_connected_region_mechanics(contract)
            evaluate.assert_not_called()
            encode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
