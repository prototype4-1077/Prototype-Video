from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from pipeline.cartoon_reconstruction_locked_patch import (
    ReconstructionLockError,
    evaluate_reconstruction_lock,
    extract_locked_patches,
    load_reconstruction_contract,
    recompose_locked_patches,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "concept/characters/june_oxley_reconstruction_locked_patch_v1.json"
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
FORBIDDEN_INDEPENDENT_IDS = {
    "residual",
    "mug",
    "right_hand",
    "left_upper_arm",
    "left_forearm",
    "left_forearm_hand",
    "right_upper_arm",
    "right_forearm",
    "right_forearm_hand",
    "left_thigh",
    "left_shin",
    "right_thigh",
    "right_shin",
    "lower_body_stitched_region",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_with_contract_document(contract: dict):
    """Exercise the public loader against an in-memory mutated contract document."""
    target = CONTRACT_PATH.resolve()
    payload = json.dumps(contract)
    original_read_text = Path.read_text

    def routed_read_text(path: Path, *args, **kwargs):
        if path.resolve() == target:
            return payload
        return original_read_text(path, *args, **kwargs)

    with patch.object(Path, "read_text", new=routed_read_text):
        return load_reconstruction_contract(target)


def _static_fail_closed_violations(contract: dict) -> list[str]:
    """Minimal independent audit of the non-negotiable representation locks."""
    violations: list[str] = []
    source_lock = contract.get("source_lock", {})
    source = source_lock.get("sole_rgba_source", {})
    extraction = contract.get("patch_extraction", {})
    rest = contract.get("rest_reconstruction", {})
    registered = contract.get("registered_rest_equivalence", {})
    lower = contract.get("lower_body_stitched_region", {})
    gates = contract.get("quality_gates", {})
    failure = contract.get("failure_policy", {})

    if source_lock.get("source_count") != 1 or source.get("sole_rgba_source") is not True:
        violations.append("sole_rgba_source")
    if not source.get("sha256") or not source_lock.get("control_contract", {}).get("sha256"):
        violations.append("pinned_hashes")
    forbidden_false = (
        "generated_atlas_allowed",
        "atlas_repack_allowed",
        "resize_allowed",
        "resampling_allowed",
        "rotation_allowed",
        "warp_allowed",
        "color_transform_allowed",
        "alpha_reestimation_allowed",
        "inpainting_allowed",
    )
    if any(extraction.get(key) is not False for key in forbidden_false):
        violations.append("native_source_pixels_only")
    if extraction.get("fallback_policy") != "raise":
        violations.append("extraction_fallback")
    ownership = extraction.get("ownership", {})
    patch_rows = extraction.get("patches", [])
    patch_ids = [row.get("id") for row in patch_rows]
    if (
        extraction.get("algorithm_id")
        != "native_rgba_connected_region_polygons_with_hard_owner_partition_v1"
        or ownership.get("method") != "alpha_clipped_declared_region_polygons_then_stable_priority_first_claim"
        or any(not row.get("polygon_xy") or "bone" in row or "radius_px" in row for row in patch_rows)
    ):
        violations.append("declared_region_polygons")
    if (
        extraction.get("low_alpha_fringe_rule")
        != "stable_8_connected_geodesic_expand_from_semantic_owners_into_native_pixels_where_0_lt_alpha_lte_8"
        or ownership.get("low_alpha_fringe_assignment")
        != "stable_priority_geodesic_expansion_from_semantic_owner_masks"
    ):
        violations.append("stable_geodesic_fringe")
    if len(patch_ids) != 9 or set(patch_ids) != REGION_IDS or set(patch_ids) & FORBIDDEN_INDEPENDENT_IDS:
        violations.append("honest_nine_region_inventory")
    if set(ownership.get("stable_priority_order", [])) != REGION_IDS:
        violations.append("region_priority")
    if any(row.get("required_connected_components") != 1 for row in patch_rows):
        violations.append("connected_regions")
    hand_mug = next((row for row in patch_rows if row.get("id") == "right_hand_mug"), {})
    if hand_mug.get("must_remain_atomic") is not True or hand_mug.get("kind") != "atomic_rigid_source_region":
        violations.append("atomic_right_hand_mug")
    sleeve_kinds = {
        row.get("id"): row.get("kind") for row in patch_rows if row.get("id") in {"left_sleeve", "right_sleeve"}
    }
    if sleeve_kinds != {
        "left_sleeve": "continuous_shoulder_to_cuff_source_region",
        "right_sleeve": "continuous_shoulder_to_cuff_source_region",
    }:
        violations.append("continuous_sleeves")
    if ownership.get("every_foreground_pixel_has_exactly_one_semantic_owner") is not True:
        violations.append("semantic_ownership")
    if rest.get("owner_masks_form_exact_partition") is not True:
        violations.append("rest_partition")
    if rest.get("alpha_over_between_overlapping_patches") is not False:
        violations.append("overlap_alpha_over")
    if rest.get("identity_transform_only") is not True:
        violations.append("identity_rest_transform")
    if registered.get("required") is not True or registered.get("fallback_policy") != "raise":
        violations.append("registered_rest_equivalence")
    if registered.get("comparison") != (
        "apply_reference_operation_independently_to_raw_source_and_raw_reconstruction_then_compare_full_canvas_rgba"
    ):
        violations.append("registered_rest_comparison")
    if lower.get("patch_id") not in patch_ids or lower.get("rest_authority") is not True:
        violations.append("lower_body_stitched_region")
    if (
        lower.get("patch_id") != "lower_garment"
        or lower.get("independent_leg_child_patch_count_required") != 0
        or lower.get("independent_leg_strip_reconstruction_allowed_at_rest") is not False
        or rest.get("authoritative_lower_body_patch") != "lower_garment"
    ):
        violations.append("continuous_lower_garment")
    pairs = extraction.get("overlap", {}).get("required_adjacent_pairs", [])
    if len(pairs) != 8 or len({tuple(pair) for pair in pairs}) != 8:
        violations.append("eight_regional_overlaps")
    rgba_gates = gates.get("rest_rgba", {})
    exact_zero = (
        "maximum_rgba_mismatched_pixels",
        "maximum_alpha_mismatched_pixels",
        "maximum_rgb_mismatched_pixels_where_source_alpha_nonzero",
        "maximum_channel_error",
        "maximum_rgba_mean_absolute_error",
    )
    if any(rgba_gates.get(key) != 0 for key in exact_zero):
        violations.append("exact_rest_reconstruction")
    if rgba_gates.get("minimum_alpha_iou") != 1.0:
        violations.append("exact_alpha_iou")
    registered_gates = gates.get("registered_rest", {})
    registered_exact_zero = (
        "maximum_rgba_mismatched_pixels",
        "maximum_alpha_mismatched_pixels",
        "maximum_rgb_mismatched_pixels_where_reference_alpha_nonzero",
        "maximum_channel_error",
        "maximum_rgba_mean_absolute_error",
    )
    if any(registered_gates.get(key) != 0 for key in registered_exact_zero):
        violations.append("exact_registered_rest_reconstruction")
    if registered_gates.get("minimum_alpha_iou") != 1.0:
        violations.append("exact_registered_alpha_iou")
    if failure.get("mode") != "fail_closed" or failure.get("fallback_allowed") is not False:
        violations.append("fail_closed")
    if failure.get("machine_pass_rule") != "true_only_when_every_gate_result_passes":
        violations.append("machine_pass_derivation")
    return violations


class ReconstructionLockedPatchContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _read_json(CONTRACT_PATH)
        cls.source_lock = cls.contract["source_lock"]
        cls.source = cls.source_lock["sole_rgba_source"]
        cls.source_path = ROOT / cls.source["path"]
        cls.control_path = ROOT / cls.source_lock["control_contract"]["path"]
        cls.metadata_path = ROOT / cls.source_lock["accepted_source_metadata"]["path"]

    def test_contract_is_valid_json_and_declares_no_render(self) -> None:
        self.assertEqual(self.contract["contract_id"], "june_oxley_reconstruction_locked_patch_v1")
        self.assertEqual(self.contract["phase"], "phase30_reconstruction_lock")
        self.assertFalse(self.contract["promotion_rule"]["this_contract_authorizes_media_render"])
        self.assertEqual(self.contract["cash_cost"], 0)
        self.assertFalse(self.contract["paid_runtime_dependency"])

    def test_accepted_pose_100_is_the_only_rgba_source_and_hashes_are_pinned(self) -> None:
        self.assertEqual(self.source_lock["source_count"], 1)
        self.assertTrue(self.source["sole_rgba_source"])
        self.assertEqual(self.source["pose_id"], "POSE_100_STANDING")
        self.assertEqual(_sha256(self.source_path), self.source["sha256"])
        self.assertEqual(
            _sha256(self.control_path),
            self.source_lock["control_contract"]["sha256"],
        )
        self.assertEqual(
            _sha256(self.metadata_path),
            self.source_lock["accepted_source_metadata"]["sha256"],
        )
        self.assertGreaterEqual(len(self.source_lock["forbidden_rgba_sources"]), 10)

    def test_source_pixels_match_declared_canvas_alpha_and_connectivity(self) -> None:
        with Image.open(self.source_path) as image:
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.size, (self.source["width"], self.source["height"]))
            rgba = np.asarray(image)
        alpha = rgba[:, :, 3]
        observations = self.contract["source_observations"]
        preservation = alpha > 0
        ys, xs = np.nonzero(preservation)
        self.assertEqual(int(np.count_nonzero(preservation)), observations["expected_nontransparent_pixels"])
        self.assertEqual(
            [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            observations["expected_nontransparent_bbox_xyxy_half_open"],
        )
        self.assertFalse(np.any(rgba[:, :, :3][alpha == 0]))
        semantic = alpha > 8
        ys, xs = np.nonzero(semantic)
        self.assertEqual(int(np.count_nonzero(semantic)), observations["expected_semantic_foreground_pixels"])
        self.assertEqual(
            [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
            observations["expected_semantic_foreground_bbox_xyxy_half_open"],
        )
        try:
            import cv2
        except ImportError:  # pragma: no cover - OpenCV is a declared project dependency.
            self.skipTest("OpenCV unavailable")
        components, _ = cv2.connectedComponents(semantic.astype(np.uint8), connectivity=8)
        self.assertEqual(components - 1, observations["expected_semantic_foreground_components_8_connected"])

    def test_control_and_deformable_metadata_agree_on_the_accepted_source(self) -> None:
        control = _read_json(self.control_path)
        pose = next(row for row in control["poses"] if row["id"] == "POSE_100_STANDING")
        self.assertEqual(pose["progress"], 1.0)
        self.assertEqual(pose["foreground"]["path"], self.source["path"])
        self.assertEqual(pose["foreground"]["sha256"], self.source["sha256"])
        self.assertEqual(pose["foreground"]["mode"], self.source["mode"])
        metadata = _read_json(self.metadata_path)
        endpoint = metadata["accepted_sources"]["standing_endpoint"]
        self.assertEqual(endpoint["path"], self.source["path"])
        self.assertEqual(endpoint["sha256"], self.source["sha256"])
        self.assertEqual(endpoint["role"], "runtime_registered_endpoint")
        corrective = next(
            row
            for row in metadata["runtime_asset_pack"]["corrective_sources"]
            if row["pose_id"] == "POSE_100_STANDING"
        )
        self.assertEqual(corrective["landmarks"], self.contract["source_landmarks"]["points"])

    def test_patch_extraction_is_deterministic_native_and_overlapping(self) -> None:
        extraction = self.contract["patch_extraction"]
        self.assertTrue(extraction["deterministic"])
        self.assertEqual(
            extraction["algorithm_id"],
            "native_rgba_connected_region_polygons_with_hard_owner_partition_v1",
        )
        self.assertEqual(extraction["coordinate_space"], "gs030_source_pixels")
        self.assertEqual(extraction["pixel_sampling"], "integer_coordinate_direct_copy")
        self.assertEqual(extraction["source_alpha_threshold_exclusive"], 8)
        self.assertEqual(extraction["pixel_preservation_alpha_threshold_exclusive"], 0)
        self.assertEqual(
            extraction["low_alpha_fringe_rule"],
            "stable_8_connected_geodesic_expand_from_semantic_owners_into_native_pixels_where_0_lt_alpha_lte_8",
        )
        self.assertEqual(
            extraction["ownership"]["low_alpha_fringe_assignment"],
            "stable_priority_geodesic_expansion_from_semantic_owner_masks",
        )
        self.assertEqual(
            extraction["ownership"]["unmatched_semantic_foreground_rule"],
            "raise",
        )
        self.assertEqual(
            extraction["ownership"]["eligibility_rule"],
            "source_alpha_greater_than_8_and_cv2_fillPoly_inclusive_integer_polygon_raster_is_nonzero",
        )
        self.assertEqual(extraction["fallback_policy"], "raise")
        for key in (
            "generated_atlas_allowed",
            "atlas_repack_allowed",
            "resize_allowed",
            "resampling_allowed",
            "rotation_allowed",
            "warp_allowed",
            "color_transform_allowed",
            "alpha_reestimation_allowed",
            "inpainting_allowed",
        ):
            self.assertFalse(extraction[key], key)
        overlap = extraction["overlap"]
        self.assertEqual(overlap["method"], "native_source_alpha_clipped_declared_region_polygons")
        self.assertFalse(overlap["overlap_pixels_are_double_composited_at_rest"])
        self.assertEqual(len(overlap["required_adjacent_pairs"]), 8)
        self.assertEqual(len({tuple(pair) for pair in overlap["required_adjacent_pairs"]}), 8)

    def test_declared_inclusive_polygon_rasters_match_stats_and_cover_semantic_alpha(self) -> None:
        import cv2

        expected_stats = {
            "lower_garment": ([496, 395, 726, 851], 92851),
            "torso_shell": ([482, 145, 749, 521], 87441),
            "left_sleeve": ([452, 177, 571, 529], 25573),
            "right_sleeve": ([690, 165, 827, 405], 14457),
            "head_neck": ([575, 7, 738, 221], 26295),
            "left_hand": ([455, 486, 537, 605], 8667),
            "right_hand_mug": ([760, 287, 875, 395], 10045),
            "left_boot": ([496, 776, 618, 928], 14424),
            "right_boot": ([600, 776, 764, 885], 12639),
        }
        with Image.open(self.source_path) as source_image:
            alpha = np.asarray(source_image.convert("RGBA"), dtype=np.uint8)[:, :, 3]
        semantic = alpha > 8
        cover = np.zeros(semantic.shape, dtype=np.uint8)
        support_by_id: dict[str, np.ndarray] = {}
        for row in self.contract["patch_extraction"]["patches"]:
            polygon = np.asarray(row["polygon_xy"], dtype=np.int32)
            raster = np.zeros(semantic.shape, dtype=np.uint8)
            cv2.fillPoly(raster, [polygon], 1)
            support = (raster > 0) & semantic
            support_by_id[row["id"]] = support
            cover += support.astype(np.uint8)
            ys, xs = np.nonzero(support)
            components, _ = cv2.connectedComponents(support.astype(np.uint8), connectivity=8)
            with self.subTest(region=row["id"]):
                self.assertEqual(
                    (row["expected_semantic_bbox_xyxy_half_open"], row["expected_semantic_pixels"]),
                    expected_stats[row["id"]],
                )
                self.assertEqual(int(np.count_nonzero(support)), row["expected_semantic_pixels"])
                self.assertEqual(
                    [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                    row["expected_semantic_bbox_xyxy_half_open"],
                )
                self.assertEqual(components - 1, row["required_connected_components"])

        self.assertFalse(np.any(semantic & (cover == 0)))
        overlap = self.contract["patch_extraction"]["overlap"]
        self.assertEqual(overlap["expected_semantic_overlap_pixels"], 82229)
        self.assertEqual(overlap["expected_maximum_cover_count"], 4)
        self.assertEqual(int(np.count_nonzero(semantic & (cover > 1))), overlap["expected_semantic_overlap_pixels"])
        self.assertEqual(int(np.max(cover[semantic])), overlap["expected_maximum_cover_count"])
        for left, right in overlap["required_adjacent_pairs"]:
            with self.subTest(overlap=f"{left}__{right}"):
                self.assertGreaterEqual(
                    int(np.count_nonzero(support_by_id[left] & support_by_id[right])),
                    self.contract["quality_gates"]["coverage_and_overlap"][
                        "minimum_overlap_pixels_per_required_adjacent_pair"
                    ],
                )

    def test_patch_inventory_is_exactly_nine_honest_connected_regions(self) -> None:
        patches = self.contract["patch_extraction"]["patches"]
        patch_ids = [row["id"] for row in patches]
        self.assertEqual(len(patch_ids), len(set(patch_ids)))
        self.assertEqual(len(patch_ids), 9)
        self.assertEqual(set(patch_ids), REGION_IDS)
        self.assertFalse(set(patch_ids) & FORBIDDEN_INDEPENDENT_IDS)
        self.assertTrue(all(row["required"] for row in patches))
        self.assertTrue(all(len(row["polygon_xy"]) >= 3 for row in patches))
        self.assertTrue(all(row["required_connected_components"] == 1 for row in patches))
        self.assertTrue(all("bone" not in row and "radius_px" not in row for row in patches))
        self.assertEqual(
            set(self.contract["patch_extraction"]["ownership"]["stable_priority_order"]),
            REGION_IDS,
        )

    def test_visible_regions_do_not_overclaim_hidden_articulation(self) -> None:
        rows = {row["id"]: row for row in self.contract["patch_extraction"]["patches"]}
        self.assertEqual(rows["lower_garment"]["kind"], "continuous_authoritative_source_region")
        self.assertEqual(rows["torso_shell"]["kind"], "continuous_source_region")
        self.assertEqual(rows["left_sleeve"]["kind"], "continuous_shoulder_to_cuff_source_region")
        self.assertEqual(rows["right_sleeve"]["kind"], "continuous_shoulder_to_cuff_source_region")
        self.assertEqual(rows["right_hand_mug"]["kind"], "atomic_rigid_source_region")
        self.assertTrue(rows["right_hand_mug"]["must_remain_atomic"])
        self.assertNotIn("right_hand", rows)
        self.assertNotIn("mug", rows)
        self.assertFalse(any("thigh" in identifier or "shin" in identifier for identifier in rows))
        self.assertFalse(any("upper_arm" in identifier or "forearm" in identifier for identifier in rows))

    def test_rest_composition_uses_exact_hard_ownership_not_overlap_blending(self) -> None:
        ownership = self.contract["patch_extraction"]["ownership"]
        rest = self.contract["rest_reconstruction"]
        self.assertTrue(ownership["every_foreground_pixel_has_exactly_one_semantic_owner"])
        self.assertTrue(rest["owner_masks_form_exact_partition"])
        self.assertEqual(rest["method"], "hard_source_pixel_ownership_direct_copy")
        self.assertFalse(rest["alpha_over_between_overlapping_patches"])
        self.assertFalse(rest["premultiplied_blend_between_overlapping_patches"])
        self.assertTrue(rest["identity_transform_only"])
        self.assertEqual(rest["resampling_fallback"], "forbidden_raise")
        self.assertEqual(rest["generated_atlas_fallback"], "forbidden_raise")

    def test_registered_rest_uses_the_pinned_phase27_operation_and_contacts(self) -> None:
        registered = self.contract["registered_rest_equivalence"]
        operation = registered["reference_operation"]
        operation_path = ROOT / operation["module_path"]
        self.assertTrue(registered["required"])
        self.assertEqual(operation["function"], "registered_pose_layer")
        self.assertEqual(_sha256(operation_path), operation["module_sha256"])
        control = _read_json(self.control_path)
        pose = next(row for row in control["poses"] if row["id"] == "POSE_100_STANDING")
        self.assertEqual(pose["source_contacts"], registered["pinned_pose_contacts"])
        self.assertEqual(control["contact_registration"], registered["pinned_registration"])
        self.assertEqual(
            registered["comparison"],
            "apply_reference_operation_independently_to_raw_source_and_raw_reconstruction_then_compare_full_canvas_rgba",
        )
        self.assertEqual(registered["fallback_policy"], "raise")

        from pipeline.cartoon_pose_layers import registered_pose_layer

        with Image.open(self.source_path) as image:
            reference, report = registered_pose_layer(
                image.convert("RGBA"),
                pose,
                control["contact_registration"],
            )
        self.assertEqual(hashlib.sha256(reference.tobytes()).hexdigest(), registered["reference_rgba_bytes_sha256"])
        expected = registered["expected_transform_report"]
        for field in (
            "translation",
            "right_leg_correction",
            "left_support_boot_residual_px",
            "right_boot_residual_px",
            "steam_origin",
        ):
            self.assertEqual(report[field], expected[field])

    def test_lower_body_is_one_authoritative_stitched_rest_region(self) -> None:
        lower = self.contract["lower_body_stitched_region"]
        self.assertTrue(lower["required"])
        self.assertTrue(lower["rest_authority"])
        self.assertEqual(lower["patch_id"], "lower_garment")
        self.assertEqual(lower["connected_components_required"], 1)
        self.assertEqual(lower["independent_leg_child_patch_count_required"], 0)
        self.assertFalse(lower["independent_leg_strip_reconstruction_allowed_at_rest"])
        self.assertEqual(set(lower["boot_overlap_patch_ids"]), {"left_boot", "right_boot"})
        self.assertNotIn("child_owner_ids", lower)
        required_anatomy = set(lower["required_anatomy"])
        self.assertTrue({"pelvis", "both_cuffs", "both_thighs", "both_shins"}.issubset(required_anatomy))
        self.assertNotIn("both_boots", required_anatomy)
        self.assertEqual(
            self.contract["rest_reconstruction"]["authoritative_lower_body_patch"],
            lower["patch_id"],
        )
        self.assertFalse(self.contract["rest_reconstruction"]["lower_body_animation_children_enabled_at_rest"])

    def test_reconstruction_alpha_rgb_edge_and_detail_gates_are_exact(self) -> None:
        gates = self.contract["quality_gates"]
        coverage = gates["coverage_and_overlap"]
        self.assertEqual(coverage["minimum_foreground_coverage_fraction"], 1.0)
        self.assertEqual(coverage["maximum_uncovered_foreground_pixels"], 0)
        self.assertEqual(coverage["minimum_rest_owner_count_per_foreground_pixel"], 1)
        self.assertEqual(coverage["maximum_rest_owner_count_per_foreground_pixel"], 1)
        topology = gates["topology"]
        self.assertEqual(topology["required_patch_count"], 9)
        self.assertEqual(topology["required_semantic_support_components_per_patch"], 1)
        self.assertEqual(topology["required_ownership_components_per_patch"], 1)
        self.assertEqual(topology["required_atomic_patch_ids"], ["right_hand_mug"])
        self.assertEqual(
            set(topology["required_continuous_patch_ids"]),
            {"lower_garment", "left_sleeve", "right_sleeve"},
        )
        self.assertEqual(
            set(topology["forbidden_independent_limb_patch_ids"]),
            {
                "left_upper_arm",
                "left_forearm",
                "right_upper_arm",
                "right_forearm",
                "left_thigh",
                "left_shin",
                "right_thigh",
                "right_shin",
                "mug",
            },
        )
        self.assertEqual(topology["maximum_zero_ownership_patches"], 0)
        rgba = gates["rest_rgba"]
        self.assertEqual(rgba["maximum_rgba_mismatched_pixels"], 0)
        self.assertEqual(rgba["maximum_alpha_mismatched_pixels"], 0)
        self.assertEqual(rgba["maximum_rgb_mismatched_pixels_where_source_alpha_nonzero"], 0)
        self.assertEqual(rgba["maximum_channel_error"], 0)
        self.assertEqual(rgba["maximum_rgba_mean_absolute_error"], 0.0)
        self.assertEqual(rgba["minimum_alpha_iou"], 1.0)
        registered = gates["registered_rest"]
        self.assertEqual(registered["maximum_rgba_mismatched_pixels"], 0)
        self.assertEqual(registered["maximum_alpha_mismatched_pixels"], 0)
        self.assertEqual(registered["maximum_rgb_mismatched_pixels_where_reference_alpha_nonzero"], 0)
        self.assertEqual(registered["maximum_channel_error"], 0)
        self.assertEqual(registered["maximum_rgba_mean_absolute_error"], 0.0)
        self.assertEqual(registered["minimum_alpha_iou"], 1.0)
        self.assertEqual(registered["maximum_left_support_boot_residual_px"], 0.0)
        self.assertEqual(registered["maximum_right_boot_residual_px"], 0.0)
        self.assertTrue(registered["required_reference_rgba_bytes_sha256_match"])
        edge = gates["edge_and_detail"]
        self.assertEqual(edge["maximum_alpha_edge_mismatched_pixels"], 0)
        self.assertEqual(edge["maximum_bidirectional_edge_chamfer_p95_px"], 0.0)
        self.assertEqual(edge["minimum_rgba_ssim"], 1.0)
        self.assertLessEqual(edge["minimum_laplacian_variance_ratio"], 1.0)
        self.assertGreaterEqual(edge["maximum_laplacian_variance_ratio"], 1.0)

    def test_report_schema_pins_exact_auditable_fields(self) -> None:
        schema = self.contract["report_schema"]
        self.assertEqual(
            set(schema["required_top_level_fields"]),
            {
                "proof",
                "contract_id",
                "source_lock",
                "extraction_policy",
                "patch_inventory",
                "topology",
                "coverage",
                "overlap",
                "rest_reconstruction",
                "registered_rest_equivalence",
                "lower_body_stitched_region",
                "edge_detail",
                "provenance",
                "gates",
                "gate_results",
                "machine_passed",
                "audience_quality",
                "cash_cost",
                "paid_runtime_dependency",
            },
        )
        self.assertIn("region_polygon_count", schema["extraction_policy_fields"])
        self.assertIn("low_alpha_fringe_rule", schema["extraction_policy_fields"])
        self.assertIn("semantic_support_pixels", schema["patch_record_fields"])
        self.assertIn("ownership_connected_components", schema["patch_record_fields"])
        self.assertIn("patch_rgba_sha256", schema["patch_record_fields"])
        self.assertEqual(
            set(schema["topology_fields"]),
            {
                "patch_count",
                "disconnected_semantic_support_patches",
                "disconnected_ownership_patches",
                "zero_ownership_patches",
                "atomic_patch_ids",
                "continuous_patch_ids",
                "forbidden_patch_ids_present",
                "passed",
            },
        )
        self.assertIn("source_coordinate_hash", schema["patch_record_fields"])
        self.assertIn("required_pair_overlap_pixels", schema["overlap_fields"])
        self.assertIn("rgba_mismatched_pixels", schema["rest_reconstruction_fields"])
        self.assertIn("operation_module_sha256_actual", schema["registered_rest_equivalence_fields"])
        self.assertIn("source_registered_rgba_bytes_sha256", schema["registered_rest_equivalence_fields"])
        self.assertIn("reconstruction_registered_rgba_bytes_sha256", schema["registered_rest_equivalence_fields"])
        self.assertIn("rgba_mismatched_pixels_in_region", schema["lower_body_stitched_region_fields"])
        self.assertEqual(
            schema["gate_result_fields"],
            ["id", "measured", "operator", "threshold", "passed"],
        )

    def test_runtime_every_region_is_connected_owned_and_schema_exact(self) -> None:
        import cv2

        contract = load_reconstruction_contract(CONTRACT_PATH)
        report, patches, reconstruction = evaluate_reconstruction_lock(contract)
        try:
            self.assertTrue(report["machine_passed"])
            self.assertEqual(set(patches), REGION_IDS)
            self.assertEqual(report["topology"]["patch_count"], 9)
            self.assertEqual(report["topology"]["disconnected_semantic_support_patches"], [])
            self.assertEqual(report["topology"]["disconnected_ownership_patches"], [])
            self.assertEqual(report["topology"]["zero_ownership_patches"], [])
            self.assertEqual(report["topology"]["forbidden_patch_ids_present"], [])
            self.assertEqual(report["topology"]["atomic_patch_ids"], ["right_hand_mug"])
            self.assertEqual(
                set(report["topology"]["continuous_patch_ids"]),
                {"lower_garment", "left_sleeve", "right_sleeve"},
            )
            inventory = {row["id"]: row for row in report["patch_inventory"]}
            with Image.open(self.source_path) as source_image:
                semantic_alpha = np.asarray(source_image.convert("RGBA"))[:, :, 3] > 8
            for identifier, locked_patch in patches.items():
                semantic_support = locked_patch.source_mask & semantic_alpha
                support_components, _ = cv2.connectedComponents(
                    semantic_support.astype(np.uint8), connectivity=8
                )
                owner_components, _ = cv2.connectedComponents(
                    locked_patch.rest_owner_mask.astype(np.uint8), connectivity=8
                )
                with self.subTest(region=identifier):
                    self.assertEqual(support_components - 1, 1)
                    self.assertEqual(owner_components - 1, 1)
                    self.assertGreater(np.count_nonzero(locked_patch.rest_owner_mask), 0)
                    self.assertEqual(inventory[identifier]["connected_components"], 1)
                    self.assertEqual(inventory[identifier]["ownership_connected_components"], 1)
                    self.assertGreater(inventory[identifier]["ownership_pixels"], 0)
                    self.assertTrue(inventory[identifier]["passed"])

            schema = contract["report_schema"]
            self.assertEqual(set(report), set(schema["required_top_level_fields"]))
            section_fields = {
                "source_lock": "source_lock_fields",
                "extraction_policy": "extraction_policy_fields",
                "topology": "topology_fields",
                "coverage": "coverage_fields",
                "overlap": "overlap_fields",
                "rest_reconstruction": "rest_reconstruction_fields",
                "registered_rest_equivalence": "registered_rest_equivalence_fields",
                "lower_body_stitched_region": "lower_body_stitched_region_fields",
                "edge_detail": "edge_detail_fields",
                "provenance": "provenance_fields",
            }
            for section, schema_key in section_fields.items():
                with self.subTest(report_section=section):
                    self.assertEqual(set(report[section]), set(schema[schema_key]))
            self.assertTrue(
                all(set(row) == set(schema["patch_record_fields"]) for row in report["patch_inventory"])
            )
            self.assertTrue(
                all(set(row) == set(schema["gate_result_fields"]) for row in report["gate_results"])
            )
        finally:
            reconstruction.close()

    def test_runtime_reconstruction_consumes_patch_local_rgba_and_detects_corruption(self) -> None:
        import pipeline.cartoon_reconstruction_locked_patch as implementation

        contract = load_reconstruction_contract(CONTRACT_PATH)
        patches = extract_locked_patches(contract)
        with Image.open(self.source_path) as source_image:
            source_rgba = np.asarray(source_image.convert("RGBA"), dtype=np.uint8).copy()
        reconstruction = recompose_locked_patches(patches, source_rgba.shape)
        self.assertTrue(np.array_equal(reconstruction, source_rgba))

        target = patches["right_hand_mug"]
        global_y, global_x = np.argwhere(target.rest_owner_mask)[0]
        x0, y0, _, _ = target.bbox_xyxy
        local_y, local_x = int(global_y - y0), int(global_x - x0)
        target.rgba[local_y, local_x, 0] ^= np.uint8(255)
        corrupted = recompose_locked_patches(patches, source_rgba.shape)
        self.assertFalse(np.array_equal(corrupted, source_rgba))
        self.assertNotEqual(
            corrupted[int(global_y), int(global_x), 0],
            source_rgba[int(global_y), int(global_x), 0],
        )

        original_extract = implementation._extract_state

        def corrupt_after_extraction(contract_value: dict, source_value: np.ndarray):
            extracted, state = original_extract(contract_value, source_value)
            patch_value = extracted["right_hand_mug"]
            owned_y, owned_x = np.argwhere(patch_value.rest_owner_mask)[0]
            bx0, by0, _, _ = patch_value.bbox_xyxy
            patch_value.rgba[int(owned_y - by0), int(owned_x - bx0), 1] ^= np.uint8(255)
            return extracted, state

        with patch.object(implementation, "_extract_state", side_effect=corrupt_after_extraction):
            with self.assertRaisesRegex(ReconstructionLockError, "reconstruction gates failed"):
                evaluate_reconstruction_lock(contract)

    def test_runtime_rejects_missing_mandatory_gate_before_machine_pass(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["registered_rest_equivalence"]["reference_rgba_bytes_sha256"] = "0" * 64
        del mutated["quality_gates"]["registered_rest"]["required_reference_rgba_bytes_sha256_match"]
        with self.assertRaises(ReconstructionLockError):
            _load_with_contract_document(mutated)

    def test_runtime_rejects_empty_report_schema(self) -> None:
        mutated = copy.deepcopy(self.contract)
        mutated["report_schema"]["required_top_level_fields"] = []
        mutated["report_schema"]["patch_record_fields"] = []
        with self.assertRaises(ReconstructionLockError):
            _load_with_contract_document(mutated)

    def test_runtime_revalidates_post_load_policy_mutation(self) -> None:
        contract = load_reconstruction_contract(CONTRACT_PATH)
        contract["patch_extraction"]["resampling_allowed"] = True
        with self.assertRaises(ReconstructionLockError):
            evaluate_reconstruction_lock(contract)

    def test_failure_policy_rejects_every_fallback_and_separates_audience_review(self) -> None:
        failure = self.contract["failure_policy"]
        self.assertEqual(failure["mode"], "fail_closed")
        self.assertFalse(failure["partial_success_allowed"])
        self.assertFalse(failure["fallback_allowed"])
        for key in (
            "on_contract_violation",
            "on_missing_required_field",
            "on_missing_source",
            "on_hash_or_metadata_mismatch",
            "on_extra_rgba_source",
            "on_generated_or_resampled_pixel",
            "on_incomplete_ownership",
            "on_missing_required_overlap",
            "on_lower_body_stitch_failure",
            "on_reconstruction_gate_failure",
            "on_registered_rest_equivalence_failure",
        ):
            self.assertEqual(failure[key], "raise", key)
        audience = failure["audience_quality_default"]
        self.assertEqual(audience["status"], "not_evaluated")
        self.assertTrue(audience["machine_gate_is_not_audience_approval"])

    def test_static_auditor_is_fail_closed_under_representative_mutations(self) -> None:
        self.assertEqual(_static_fail_closed_violations(self.contract), [])
        mutations = []
        second_source = copy.deepcopy(self.contract)
        second_source["source_lock"]["source_count"] = 2
        mutations.append((second_source, "sole_rgba_source"))
        generated = copy.deepcopy(self.contract)
        generated["patch_extraction"]["generated_atlas_allowed"] = True
        mutations.append((generated, "native_source_pixels_only"))
        resampled = copy.deepcopy(self.contract)
        resampled["patch_extraction"]["resampling_allowed"] = True
        mutations.append((resampled, "native_source_pixels_only"))
        double_blended = copy.deepcopy(self.contract)
        double_blended["rest_reconstruction"]["alpha_over_between_overlapping_patches"] = True
        mutations.append((double_blended, "overlap_alpha_over"))
        missing_stitch = copy.deepcopy(self.contract)
        missing_stitch["patch_extraction"]["patches"] = [
            row
            for row in missing_stitch["patch_extraction"]["patches"]
            if row["id"] != "lower_garment"
        ]
        mutations.append((missing_stitch, "lower_body_stitched_region"))
        capsule = copy.deepcopy(self.contract)
        capsule["patch_extraction"]["algorithm_id"] = "capsules"
        mutations.append((capsule, "declared_region_polygons"))
        residual_fringe = copy.deepcopy(self.contract)
        residual_fringe["patch_extraction"]["low_alpha_fringe_rule"] = "assign_to_residual"
        mutations.append((residual_fringe, "stable_geodesic_fringe"))
        invented_shin = copy.deepcopy(self.contract)
        invented_shin["patch_extraction"]["patches"].append(
            {
                "id": "left_shin",
                "kind": "invented_limb",
                "polygon_xy": [[0, 0], [1, 0], [1, 1]],
                "required_connected_components": 1,
                "required": True,
            }
        )
        mutations.append((invented_shin, "honest_nine_region_inventory"))
        split_mug = copy.deepcopy(self.contract)
        right_hand_mug = next(
            row for row in split_mug["patch_extraction"]["patches"] if row["id"] == "right_hand_mug"
        )
        right_hand_mug["must_remain_atomic"] = False
        mutations.append((split_mug, "atomic_right_hand_mug"))
        disconnected = copy.deepcopy(self.contract)
        disconnected["patch_extraction"]["patches"][0]["required_connected_components"] = 2
        mutations.append((disconnected, "connected_regions"))
        seven_overlaps = copy.deepcopy(self.contract)
        seven_overlaps["patch_extraction"]["overlap"]["required_adjacent_pairs"].pop()
        mutations.append((seven_overlaps, "eight_regional_overlaps"))
        lossy_rest = copy.deepcopy(self.contract)
        lossy_rest["quality_gates"]["rest_rgba"]["maximum_rgba_mismatched_pixels"] = 1
        mutations.append((lossy_rest, "exact_rest_reconstruction"))
        drifted_registered = copy.deepcopy(self.contract)
        drifted_registered["registered_rest_equivalence"]["comparison"] = "raw_only"
        mutations.append((drifted_registered, "registered_rest_comparison"))
        fallback = copy.deepcopy(self.contract)
        fallback["failure_policy"]["fallback_allowed"] = True
        mutations.append((fallback, "fail_closed"))

        for mutated, expected in mutations:
            with self.subTest(expected=expected):
                self.assertIn(expected, _static_fail_closed_violations(mutated))


if __name__ == "__main__":
    unittest.main()
