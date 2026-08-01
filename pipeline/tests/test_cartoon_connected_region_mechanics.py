from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path


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
        self.assertEqual(tracks["head_absolute_rotation_deg"], [0,-0.55,1.05,1.55,-0.55,0.37,-0.18,0.07,0])
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
        self.assertEqual(rows["left_boot"]["sole_receiver_source_xy"], [[600.0,915.0],[510.0,918.0]])
        self.assertEqual(rows["right_boot"]["sole_receiver_source_xy"], [[692.0,866.0],[782.0,864.0]])
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
        self.assertEqual(delivery["contact_sheet"]["review_frames"], [1, 13, 25, 37, 49])
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


if __name__ == "__main__":
    unittest.main()
