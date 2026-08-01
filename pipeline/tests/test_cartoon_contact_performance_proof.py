from __future__ import annotations

import copy
import hashlib
import inspect
import json
import math
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np
from PIL import Image

from pipeline.cartoon_deformable_performance_3q import _registered_point


try:
    from pipeline.cartoon_contact_performance_proof import (
        ContactPerformanceRenderer,
        render_contact_performance_proof,
        solve_contact_landmarks,
    )
except ImportError as exc:  # The red TDD state must still collect contract tests.
    ContactPerformanceRenderer = None  # type: ignore[assignment,misc]
    render_contact_performance_proof = None  # type: ignore[assignment]
    solve_contact_landmarks = None  # type: ignore[assignment]
    API_IMPORT_FAILURE = repr(exc)
else:
    API_IMPORT_FAILURE = ""

try:
    from pipeline.cartoon_contact_performance_proof import evaluate_contact_gate_results
except ImportError as exc:
    evaluate_contact_gate_results = None  # type: ignore[assignment]
    EVALUATOR_IMPORT_FAILURE = repr(exc)
else:
    EVALUATOR_IMPORT_FAILURE = ""


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "concept/characters/june_oxley_contact_performance_v1.json"
SOURCE_PERFORMANCE_PATH = REPO_ROOT / "concept/characters/june_oxley_deformable_performance_3q_v1.json"
FRAMES = tuple(range(64, 113))
FLAT_LEFT_FRAMES = tuple(range(64, 71)) + tuple(range(87, 113))
FLAT_RIGHT_FRAMES = tuple(range(64, 71)) + tuple(range(95, 113))
LOADED_HAND_FRAMES = tuple(range(64, 79))

COMPONENT_IDS = {
    "head", "torso", "left_upper_arm", "right_upper_arm", "left_forearm",
    "right_forearm", "left_hand", "right_hand_mug", "left_thigh", "right_thigh",
    "left_shin", "right_shin", "left_boot", "right_boot",
}
JOINT_IDS = {
    "head__torso",
    "left_upper_arm__torso",
    "left_upper_arm__left_forearm",
    "left_forearm__left_hand",
    "right_upper_arm__torso",
    "right_upper_arm__right_forearm",
    "right_forearm__right_hand_mug",
    "left_thigh__torso",
    "left_thigh__left_shin",
    "left_shin__left_boot",
    "right_thigh__torso",
    "right_thigh__right_shin",
    "right_shin__right_boot",
}
SOLE_LANDMARKS = {
    f"{side}_{name}"
    for side in ("left", "right")
    for name in ("heel", "ball", "toe")
} | {
    f"{side}_sole_{index}"
    for side in ("left", "right")
    for index in range(7)
}


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _curve_value(keys: list[list[float]], frame: int) -> float:
    """Reference only exact keys; the renderer owns cubic interpolation."""
    row = next((row for row in keys if int(row[0]) == frame), None)
    if row is None:
        raise AssertionError(f"frame {frame} is not an authored curve key")
    return float(row[1])


def _line_residual(point: np.ndarray, origin: np.ndarray, direction: np.ndarray) -> float:
    offset = point - origin
    cross = float(direction[0] * offset[1] - direction[1] * offset[0])
    return abs(cross) / float(np.linalg.norm(direction))


def _flatten_leaves(value: object, prefix: str = "") -> dict[str, object]:
    if not isinstance(value, dict):
        if not prefix:
            raise AssertionError("a gate leaf requires a path")
        return {prefix: value}
    leaves: dict[str, object] = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        leaves.update(_flatten_leaves(child, path))
    return leaves


def _nested_measurement_fixture(gates: dict[str, object]) -> dict[str, object]:
    def convert(value: object, path: str) -> object:
        if isinstance(value, dict):
            return {
                key: convert(child, f"{path}.{key}" if path else str(key))
                for key, child in value.items()
            }
        source_kind = "decoded_media" if path.startswith("delivery.") else "rendered_measurement"
        return {
            "value": value,
            "source_kind": source_kind,
            "source_detail": f"synthetic boundary measurement for {path}",
            "aggregation": "identity_at_threshold",
        }

    return convert(gates, "")  # type: ignore[return-value]


def _measurement_at(aggregates: dict[str, object], path: str) -> dict[str, object]:
    value: object = aggregates
    for part in path.split("."):
        value = value[part]  # type: ignore[index]
    if not isinstance(value, dict):
        raise AssertionError(f"measurement {path} is not a record")
    return value


class ContactPerformanceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _load_json(CONTRACT_PATH)

    def test_contract_is_zero_cash_and_locks_exact_49_frame_delivery(self) -> None:
        self.assertEqual(self.contract["cash_cost"], 0)
        self.assertFalse(self.contract["paid_runtime_dependency"])
        self.assertFalse(self.contract["network_runtime_required"])
        proof = self.contract["proof"]
        self.assertEqual(proof["frame_range"], [64, 112])
        self.assertEqual(proof["frame_count"], 49)
        self.assertEqual(len(FRAMES), 49)
        self.assertEqual((proof["width"], proof["height"], proof["fps"]), (960, 540, 30))
        self.assertEqual(proof["measurement_space"], "final_output_px_after_camera")
        self.assertEqual(self.contract["gates"]["delivery"]["exact_decoded_frames"], 49)
        authored = self.contract["coordinate_spaces"]["authored_targets"]
        self.assertEqual(authored["id"], "gs030_registered_source_px_pre_camera")
        self.assertEqual((authored["width"], authored["height"]), (1672, 941))

    def test_shared_uv_policy_has_one_standing_texture_and_zero_seated_rgb_samples(self) -> None:
        policy = self.contract["source_policy"]
        self.assertEqual(policy["representation"], "shared_uv_piecewise_affine")
        self.assertEqual(policy["texture_source_count"], 1)
        self.assertEqual(policy["standing_texture_sources_per_component"], 1)
        self.assertEqual(policy["standing_texture_contract"]["texture_role"], "only_rgb_texture_source")
        self.assertEqual(policy["seated_geometry_contract"]["rgb_sample_count"], 0)
        self.assertEqual(
            policy["seated_geometry_contract"]["role"],
            "alpha_geometry_and_component_annotations_only",
        )
        self.assertFalse(policy["dual_rgba_blend_allowed"])
        self.assertFalse(policy["dual_alpha_blend_allowed"])
        self.assertFalse(policy["alpha_blend_fallback_allowed"])

    def test_every_referenced_source_is_hash_locked(self) -> None:
        policy = self.contract["source_policy"]
        references = (
            policy["standing_texture_contract"],
            policy["seated_geometry_contract"],
            policy["performance_source_contract"],
        )
        for reference in references:
            path = REPO_ROOT / reference["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), reference["sha256"])
        atlas = policy["standing_texture_contract"]
        atlas_path = REPO_ROOT / atlas["atlas_path"]
        self.assertEqual(hashlib.sha256(atlas_path.read_bytes()).hexdigest(), atlas["atlas_sha256"])
        for reference in self.contract["porch_target_geometry"]["provenance"].values():
            if not isinstance(reference, dict) or "path" not in reference:
                continue
            path = REPO_ROOT / reference["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), reference["sha256"])
            with Image.open(path) as image:
                self.assertEqual(image.size, (reference["width"], reference["height"]))
        registration = self.contract["pose_key_registration"]["source_control"]
        registration_path = REPO_ROOT / registration["path"]
        self.assertEqual(hashlib.sha256(registration_path.read_bytes()).hexdigest(), registration["sha256"])

    def test_exact_five_pose_keys_are_0_25_50_75_100(self) -> None:
        keys = self.contract["pose_keys"]
        self.assertEqual([row["progress"] for row in keys], [0.0, 0.25, 0.5, 0.75, 1.0])
        self.assertEqual(
            [row["pose_id"] for row in keys],
            [
                "POSE_00_SEATED",
                "POSE_25_LEVERAGE",
                "POSE_50_WEIGHT_TRANSFER",
                "POSE_75_RELEASE",
                "POSE_100_STANDING",
            ],
        )
        registration = self.contract["pose_key_registration"]
        self.assertEqual(registration["required_pose_ids"], [row["pose_id"] for row in keys])
        self.assertEqual(
            registration["point_registration_semantics"],
            "pipeline.cartoon_deformable_performance_3q._registered_point",
        )
        self.assertEqual(
            registration["required_operations"],
            ["pose_specific_translation", "pose_specific_right_leg_warp_when_declared"],
        )
        self.assertEqual(
            registration["right_leg_landmarks"],
            ["right_hip", "right_knee", "right_ankle", "right_foot"],
        )
        self.assertTrue(registration["register_before_interpolation"])
        self.assertFalse(registration["interpolate_unregistered_pose_points_allowed"])
        self.assertFalse(registration["shared_transform_for_all_pose_keys_allowed"])

    def test_every_boot_has_distinct_heel_ball_toe_and_exactly_seven_real_sole_samples(self) -> None:
        geometry = self.contract["boot_contact_geometry"]
        self.assertEqual(geometry["sample_order"], "heel_to_toe")
        self.assertEqual(geometry["sample_count_per_boot"], 7)
        atlas_contract = _load_json(
            REPO_ROOT / self.contract["source_policy"]["standing_texture_contract"]["path"]
        )
        atlas = np.asarray(
            Image.open(REPO_ROOT / atlas_contract["atlas"]["path"]).convert("RGBA"),
            dtype=np.uint8,
        )
        for side in ("left_boot", "right_boot"):
            row = geometry[side]
            samples = row["sole_samples_component_local_px"]
            self.assertEqual(len(samples), 7)
            self.assertEqual(len({tuple(point) for point in samples}), 7)
            indices = [row["heel_sample_index"], row["ball_sample_index"], row["toe_sample_index"]]
            self.assertEqual(len(set(indices)), 3)
            x0, y0, width, height = row["component_bbox_atlas_px"]
            crop = atlas[y0 : y0 + height, x0 : x0 + width, 3]
            for index, point in enumerate(samples):
                x, y = map(int, point)
                with self.subTest(side=side, sample=index):
                    self.assertGreater(crop[y, x], 8)
                    # Each socket is on the lower alpha boundary, not an arbitrary
                    # interior point that can pass by measuring the boot against itself.
                    self.assertFalse(np.any(crop[y + 1 :, x] > 8))

    def test_porch_targets_are_independent_seven_sample_contact_segments(self) -> None:
        porch = self.contract["porch_target_geometry"]
        self.assertEqual(porch["coordinate_space"], "gs030_registered_source_px_pre_camera")
        self.assertEqual(porch["kind"], "independently_measured_depth_specific_projected_contact_segments")
        mean_depths = []
        for side in ("left_boot", "right_boot"):
            samples = np.asarray(porch[side]["target_samples"], dtype=np.float64)
            self.assertEqual(samples.shape, (7, 2))
            self.assertEqual(len({tuple(point) for point in samples}), 7)
            segment = porch[side]["target_segment"]
            origin = np.asarray(segment["heel"], dtype=np.float64)
            direction = np.asarray(segment["toe"], dtype=np.float64) - origin
            for point in samples:
                self.assertLessEqual(
                    _line_residual(point, origin, direction),
                    segment["maximum_target_sample_line_residual_px"],
                )
            tangent = abs(math.degrees(math.atan2(float(direction[1]), float(direction[0]))))
            tangent = min(tangent, abs(180.0 - tangent))
            self.assertLessEqual(tangent, segment["maximum_absolute_tangent_degrees"])
            envelope = porch[side]["receiver_geometry_bounds"]
            self.assertGreaterEqual(float(np.min(samples[:, 0])), envelope["x_interval"][0])
            self.assertLessEqual(float(np.max(samples[:, 0])), envelope["x_interval"][1])
            self.assertGreaterEqual(float(np.min(samples[:, 1])), envelope["y_interval"][0])
            self.assertLessEqual(float(np.max(samples[:, 1])), envelope["y_interval"][1])
            mean_depths.append(float(np.mean(samples[:, 1])))
        # The near and far boots deliberately do not share a cross-depth tangent.
        self.assertGreater(abs(mean_depths[0] - mean_depths[1]), 40.0)
        self.assertIn("receiver geometry", porch["provenance"]["measurement_method"])
        self.assertIn("not claims about a raw observed", porch["provenance"]["measurement_method"])
        self.assertIn("No tangent is inferred", porch["provenance"]["measurement_method"])
        self.assertIn("independent rendered hand-alpha", porch["chair_arm"]["evidence_rule"])
        self.assertIn("pelvis/torso alpha-boundary", porch["chair_seat"]["evidence_rule"])
        self.assertIn("independent chair occlusion mask", porch["chair_seat"]["evidence_rule"])

    def test_chair_masks_are_bounded_clean_background_annotations(self) -> None:
        porch = self.contract["porch_target_geometry"]
        source = porch["provenance"]["clean_background"]
        self.assertEqual(source["role"], "chair_mask_and_porch_surface_review")
        for identifier in ("chair_arm", "chair_seat"):
            polygon_key = "mask_polygon" if identifier == "chair_arm" else "occlusion_mask_polygon"
            polygon = np.asarray(porch[identifier][polygon_key], dtype=np.float32)
            self.assertEqual(polygon.shape[1], 2)
            self.assertGreaterEqual(float(np.min(polygon[:, 0])), 0.0)
            self.assertLess(float(np.max(polygon[:, 0])), source["width"])
            self.assertGreaterEqual(float(np.min(polygon[:, 1])), 0.0)
            self.assertLess(float(np.max(polygon[:, 1])), source["height"])
            self.assertGreater(cv2.contourArea(polygon), 1000.0)
        arm = np.asarray(porch["chair_arm"]["mask_polygon"], dtype=np.float32)
        anchor = tuple(map(float, porch["chair_arm"]["planted_hand_anchor"]))
        self.assertGreaterEqual(cv2.pointPolygonTest(arm, anchor, False), 0.0)
        seat = porch["chair_seat"]
        self.assertEqual(seat["collision_receiver"], {
            "kind": "projected_line_segment",
            "start": [272.0, 592.0],
            "end": [603.0, 582.0],
        })
        self.assertEqual(seat["occlusion_mask_polygon"][:2], [seat["collision_receiver"]["start"], seat["collision_receiver"]["end"]])

    def test_motion_checkpoint_uses_one_cubic_curve_without_late_progress_snap(self) -> None:
        motion = self.contract["motion"]
        self.assertEqual(motion["interpolation"], "time_weighted_cubic_hermite_c1")
        self.assertFalse(motion["double_easing_allowed"])
        keys = motion["keys"]
        self.assertEqual(keys[0]["frame"], 64)
        self.assertEqual(keys[-1]["frame"], 112)
        self.assertEqual(
            [(row["frame"], row["stand_progress"]) for row in keys if row["frame"] in (94, 96, 98)],
            [(94, 0.92), (96, 0.985), (98, 1.0)],
        )
        progresses = [float(row["stand_progress"]) for row in keys]
        self.assertTrue(all(left <= right for left, right in zip(progresses, progresses[1:])))
        self.assertLessEqual(max(right - left for left, right in zip(progresses, progresses[1:])), 0.2)
        roots = {row["frame"]: row["root"] for row in keys}
        self.assertEqual(roots[70], [610.0, 648.0])
        self.assertEqual(roots[73], [624.0, 644.0])
        self.assertEqual(roots[98], [633.0, 463.0])
        self.assertEqual(roots[112], [633.0, 468.0])

    def test_loads_and_heel_roll_are_continuous_numeric_curves_not_boolean_modes(self) -> None:
        curves = self.contract["load_curves"]
        self.assertEqual(curves["interpolation"], "time_weighted_cubic_hermite_c1")
        self.assertEqual(curves["chair_hand_load"], [[64, 0.55], [70, 1.0], [74, 0.8], [77, 0.35], [79, 0.0], [112, 0.0]])
        self.assertEqual(curves["seat_load"], [[64, 0.95], [68, 1.0], [70, 0.7], [73, 0.0], [112, 0.0]])
        for name in ("seat_load", "chair_hand_load"):
            values = [float(row[1]) for row in curves[name]]
            self.assertTrue(all(0.0 <= value <= 1.0 for value in values))
            self.assertTrue(any(0.0 < value < 1.0 for value in values))
        left_maximum = max(value for _, value in curves["left_heel_lift_preview_px"])
        self.assertGreater(left_maximum, 0.0)
        self.assertLessEqual(left_maximum, self.contract["gates"]["feet"]["maximum_left_heel_lift_preview_px"])
        right_maximum = max(value for _, value in curves["right_heel_lift_preview_px"])
        self.assertGreater(right_maximum, 0.0)
        self.assertLessEqual(right_maximum, self.contract["gates"]["feet"]["maximum_right_heel_lift_preview_px"])
        self.assertEqual(curves["chair_hand_release_frame"], 79)
        self.assertEqual(curves["seat_release_complete_frame"], 73)

    def test_com_is_render_derived_and_declared_proxy_cannot_satisfy_gate(self) -> None:
        balance = self.contract["render_derived_balance"]
        self.assertEqual(balance["method"], "mass_weighted_final_output_component_alpha_centroids")
        self.assertFalse(balance["declared_proxy_may_satisfy_gate"])
        self.assertEqual(set(balance["component_mass_weights"]), COMPONENT_IDS)
        self.assertAlmostEqual(sum(balance["component_mass_weights"].values()), 1.0, places=8)
        self.assertIn("rendered", balance["support_hull_rule"])
        self.assertIn("rendered_com_to_rendered_support_hull", self.contract["evidence_policy"]["required_independent_pairs"])

    def test_full_settle_and_physical_thresholds_are_mandatory(self) -> None:
        settle = self.contract["motion"]["settle"]
        self.assertEqual(settle["vertical_offset_source_px_keys"], [[96, -2.0], [98, -5.0], [102, 3.0], [106, -1.0], [108, 0.0], [112, 0.0]])
        self.assertTrue(settle["requires_knee_recompression"])
        self.assertFalse(settle["feet_may_translate_with_settle"])
        gates = self.contract["gates"]
        self.assertLessEqual(gates["feet"]["maximum_flat_sole_absolute_distance_p95_preview_px"], 1.5)
        self.assertLessEqual(gates["feet"]["maximum_flat_sole_penetration_preview_px"], 1.0)
        self.assertGreaterEqual(gates["feet"]["minimum_flat_sole_contact_fraction"], 0.7)
        self.assertLessEqual(gates["chair"]["maximum_loaded_hand_to_chair_separation_preview_px"], 1.0)
        self.assertGreaterEqual(gates["balance"]["minimum_com_support_hull_margin_after_seat_release_preview_px"], 4.0)
        self.assertLessEqual(gates["motion"]["maximum_root_jerk_preview_px_per_frame_cubed"], 2.0)
        self.assertGreaterEqual(gates["motion"]["required_final_stable_frames"], 4)

    def test_all_13_joint_one_texture_and_no_ghost_gates_are_explicit(self) -> None:
        topology = self.contract["component_topology"]
        self.assertEqual(set(topology["component_ids"]), COMPONENT_IDS)
        self.assertEqual(
            {"__".join(pair) for pair in topology["joint_pairs"]},
            JOINT_IDS,
        )
        self.assertEqual(topology["expected_component_count"], 14)
        self.assertEqual(topology["expected_joint_count"], 13)
        gates = self.contract["gates"]["topology_and_texture"]
        self.assertEqual(gates["exact_texture_source_count"], 1)
        self.assertEqual(gates["exact_seated_rgb_sample_count"], 0)
        self.assertEqual(gates["maximum_dual_source_contribution_pixels"], 0)
        self.assertEqual(gates["maximum_foldover_count"], 0)
        self.assertEqual(gates["maximum_substantial_components_per_part"], 1)

    def test_audience_status_is_separate_and_cannot_be_inferred(self) -> None:
        audience = self.contract["audience_quality"]
        self.assertEqual(audience["status"], "unevaluated")
        self.assertFalse(audience["may_be_inferred_from_machine_pass"])
        self.assertTrue(audience["requires_separate_blinded_review"])
        self.assertFalse(audience["promotion_allowed"])
        self.assertTrue(self.contract["report_contract"]["machine_pass_requires_every_gate"])
        self.assertEqual(
            set(self.contract["evidence_policy"]["forbidden_metric_sources"]),
            {
                "nearest_pixel_on_same_component_to_its_own_socket",
                "authored_com_proxy_inside_authored_rectangle",
                "declared_contact_mode_without_rendered_geometry",
                "pre_camera_contact_residual",
                "alpha_iou_as_motion_quality",
            },
        )

    def test_every_gate_threshold_has_one_aggregate_binding(self) -> None:
        thresholds = set(_flatten_leaves(self.contract["gates"]))
        derivation = self.contract["report_contract"]["gate_derivation"]
        groups = derivation["gate_groups"]
        self.assertEqual(set(groups), set(self.contract["report_contract"]["required_gate_results"]))
        bindings = [path for paths in groups.values() for path in paths]
        self.assertEqual(len(bindings), len(set(bindings)), "a threshold is bound to multiple gate results")
        self.assertEqual(set(bindings), thresholds, "every named threshold must have aggregate evidence")
        self.assertEqual(derivation["missing_measurement_policy"], "raise")
        self.assertEqual(derivation["unmeasured_or_forbidden_source_policy"], "raise")
        self.assertIn("cannot be initialized independently", derivation["machine_pass_rule"])

    def test_contact_evidence_schema_requires_final_alpha_and_independent_masks(self) -> None:
        required = self.contract["evidence_policy"]["required_detail_evidence"]
        foot = required["foot_sole_samples"]
        self.assertEqual(foot["sample_source"], "final_component_alpha_boundary")
        self.assertEqual(foot["measurement_space"], "final_output_px_after_camera")
        self.assertIn("boundary_pixels_preview_px", foot["required_fields"])
        self.assertIn("sample_membership_residual_preview_px", foot["required_fields"])
        self.assertIn("transformed_cage_coordinates", foot["forbidden_sample_sources"])
        self.assertIn("solver_markers_without_alpha_resampling", foot["forbidden_sample_sources"])
        seat = required["chair_seat_penetration"]
        self.assertEqual(seat["measurement"], "signed_alpha_boundary_to_receiver_depth")
        self.assertEqual(seat["required_source_pair"], ["rendered_pelvis_alpha_boundary", "camera_transformed_chair_seat_top_receiver"])
        self.assertEqual(seat["required_mask_sources"], ["final_torso_alpha_mask", "rendered_chair_seat_occlusion_mask"])
        shadow = required["shadow_to_sole_gap"]
        self.assertEqual(shadow["measurement"], "independent_mask_separation")
        self.assertEqual(shadow["required_source_kinds"], ["final_boot_alpha_mask", "final_contact_shadow_alpha_mask"])


class ContactGateEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _load_json(CONTRACT_PATH)

    def _require_evaluator(self) -> None:
        self.assertIsNotNone(
            evaluate_contact_gate_results,
            f"aggregate gate evaluator is not implemented: {EVALUATOR_IMPORT_FAILURE}",
        )

    def test_gate_results_are_derived_from_every_aggregate_measurement(self) -> None:
        self._require_evaluator()
        aggregates = _nested_measurement_fixture(self.contract["gates"])
        evaluation = evaluate_contact_gate_results(self.contract, aggregates)
        required = set(self.contract["report_contract"]["required_gate_results"])
        thresholds = set(_flatten_leaves(self.contract["gates"]))
        self.assertEqual(set(evaluation["gate_results"]), required)
        self.assertTrue(all(evaluation["gate_results"].values()))
        self.assertTrue(evaluation["machine_passed"])
        self.assertEqual(set(evaluation["threshold_results"]), thresholds)
        for path, result in evaluation["threshold_results"].items():
            self.assertEqual(result["measured_value"], _measurement_at(aggregates, path)["value"])
            self.assertEqual(result["threshold_value"], _flatten_leaves(self.contract["gates"])[path])
            self.assertTrue(result["passed"])
            self.assertIn("comparator", result)
            self.assertIn("source_kind", result)

    def test_one_failing_measurement_cannot_be_masked_by_prefilled_true_gates(self) -> None:
        self._require_evaluator()
        aggregates = _nested_measurement_fixture(self.contract["gates"])
        path = "feet.maximum_flat_sole_penetration_preview_px"
        record = _measurement_at(aggregates, path)
        record["value"] = float(self.contract["gates"]["feet"]["maximum_flat_sole_penetration_preview_px"]) + 0.25
        evaluation = evaluate_contact_gate_results(self.contract, aggregates)
        self.assertFalse(evaluation["threshold_results"][path]["passed"])
        self.assertFalse(evaluation["gate_results"]["feet"])
        self.assertFalse(evaluation["machine_passed"])
        self.assertTrue(all(value for key, value in evaluation["gate_results"].items() if key != "feet"))

    def test_missing_or_declared_only_aggregate_evidence_fails_closed(self) -> None:
        self._require_evaluator()
        missing = _nested_measurement_fixture(self.contract["gates"])
        del missing["chair"]["maximum_seat_penetration_preview_px"]
        with self.assertRaises((ValueError, KeyError)):
            evaluate_contact_gate_results(self.contract, missing)

        forbidden = _nested_measurement_fixture(self.contract["gates"])
        _measurement_at(forbidden, "feet.maximum_shadow_to_sole_gap_preview_px")["source_kind"] = "declared_value"
        with self.assertRaises(ValueError):
            evaluate_contact_gate_results(self.contract, forbidden)


class ContactPoseRegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _load_json(CONTRACT_PATH)
        cls.performance = _load_json(SOURCE_PERFORMANCE_PATH)
        control_path = REPO_ROOT / cls.contract["pose_key_registration"]["source_control"]["path"]
        cls.control = _load_json(control_path)

    def test_solver_registers_every_pose_key_before_interpolation(self) -> None:
        self.assertIsNotNone(solve_contact_landmarks, f"contact solver is not implemented: {API_IMPORT_FAILURE}")
        source_rows = self.performance["runtime_asset_pack"]["corrective_sources"]
        base = copy.deepcopy(source_rows[0]["landmarks"])
        solution = solve_contact_landmarks(self.contract, 64, base)
        evidence = solution["pose_registration_evidence"]
        self.assertEqual(
            evidence["operation_order"],
            "register_every_pose_key_to_gs030_source_space_before_any_pose_interpolation",
        )
        self.assertTrue(evidence["registered_before_interpolation"])
        pose_by_id = {str(row["id"]): row for row in self.control["poses"]}
        registered = evidence["registered_pose_keys"]
        self.assertEqual(set(registered), {row["pose_id"] for row in source_rows})
        registration = self.control["contact_registration"]
        for row in source_rows:
            pose_id = row["pose_id"]
            pose = pose_by_id[pose_id]
            actual_landmarks = registered[pose_id]["landmarks"]
            self.assertEqual(set(actual_landmarks), set(row["landmarks"]))
            self.assertEqual(registered[pose_id]["source_pose_id"], pose_id)
            self.assertTrue(registered[pose_id]["pose_specific_transform"])
            for identifier, point in row["landmarks"].items():
                with self.subTest(pose=pose_id, landmark=identifier):
                    expected = _registered_point(point, pose, registration)
                    np.testing.assert_allclose(actual_landmarks[identifier], expected, atol=1e-5)


class ContactPerformanceAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _load_json(CONTRACT_PATH)
        cls.source = _load_json(SOURCE_PERFORMANCE_PATH)
        cls.frames: dict[int, dict[str, object]] = {}
        cls.images: dict[int, tuple[int, int]] = {}
        if ContactPerformanceRenderer is None:
            return
        with ContactPerformanceRenderer(CONTRACT_PATH) as renderer:
            for frame in FRAMES:
                image, details = renderer.render_frame(frame)
                try:
                    cls.images[frame] = image.size
                    cls.frames[frame] = details
                finally:
                    image.close()

    def _require_api(self) -> None:
        self.assertIsNotNone(
            ContactPerformanceRenderer,
            f"contact-performance API is not implemented: {API_IMPORT_FAILURE}",
        )
        self.assertIsNotNone(solve_contact_landmarks)
        self.assertIsNotNone(render_contact_performance_proof)
        self.assertIsNotNone(evaluate_contact_gate_results)

    def _temporary_contract(self, mutation) -> Path:
        contract = copy.deepcopy(self.contract)
        mutation(contract)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "contract.json"
        path.write_text(json.dumps(contract), encoding="utf-8")
        return path

    def test_public_api_signatures_are_explicit(self) -> None:
        self._require_api()
        renderer_signature = inspect.signature(ContactPerformanceRenderer)
        self.assertEqual(list(renderer_signature.parameters)[:1], ["contract_path"])
        solver_signature = inspect.signature(solve_contact_landmarks)
        self.assertEqual(list(solver_signature.parameters)[:3], ["contract", "frame", "base_landmarks"])
        render_signature = inspect.signature(render_contact_performance_proof)
        self.assertEqual(list(render_signature.parameters)[:2], ["contract_path", "output_dir"])
        self.assertEqual(render_signature.parameters["ffmpeg"].default, "ffmpeg")
        evaluator_signature = inspect.signature(evaluate_contact_gate_results)
        self.assertEqual(list(evaluator_signature.parameters)[:2], ["contract", "aggregate_measurements"])

    def test_solver_returns_inspectable_contact_landmarks_without_mutating_input(self) -> None:
        self._require_api()
        base = copy.deepcopy(self.source["runtime_asset_pack"]["corrective_sources"][0]["landmarks"])
        original = copy.deepcopy(base)
        for frame in (70, 78, 82, 95, 108):
            solution = solve_contact_landmarks(self.contract, frame, base)
            self.assertEqual(solution["coordinate_space"], "gs030_registered_source_px_pre_camera")
            self.assertEqual(solution["frame"], frame)
            self.assertTrue(SOLE_LANDMARKS.issubset(solution["landmarks"]))
            self.assertEqual(set(solution["foot_targets"]), {"left_boot", "right_boot"})
            self.assertEqual(len(solution["foot_targets"]["left_boot"]["sole_samples"]), 7)
            self.assertEqual(len(solution["foot_targets"]["right_boot"]["sole_samples"]), 7)
            self.assertEqual(set(solution["loads"]), {"seat", "chair_hand"})
            self.assertEqual(len(solution["root_target"]), 2)
        self.assertEqual(base, original)

    def test_solver_pins_toes_and_moves_real_heels_during_roll(self) -> None:
        self._require_api()
        base = copy.deepcopy(self.source["runtime_asset_pack"]["corrective_sources"][0]["landmarks"])
        flat = solve_contact_landmarks(self.contract, 70, base)
        porch = self.contract["porch_target_geometry"]
        for side in ("left_boot", "right_boot"):
            flat_samples = np.asarray(flat["foot_targets"][side]["sole_samples"], dtype=np.float64)
            np.testing.assert_allclose(flat_samples, porch[side]["target_samples"], atol=1e-6)
            pivot_frame = 78 if side == "left_boot" else 90
            pivot = solve_contact_landmarks(self.contract, pivot_frame, base)
            pivot_samples = np.asarray(pivot["foot_targets"][side]["sole_samples"], dtype=np.float64)
            np.testing.assert_allclose(pivot_samples[-1], porch[side]["target_samples"][-1], atol=1e-6)
            self.assertGreater(
                float(np.linalg.norm(pivot_samples[0] - np.asarray(porch[side]["target_samples"][0]))),
                0.0,
            )
        self.assertEqual(flat["loads"]["chair_hand"], _curve_value(self.contract["load_curves"]["chair_hand_load"], 70))

    def test_renderer_locks_frames_size_and_final_measurement_space(self) -> None:
        self._require_api()
        self.assertEqual(set(self.frames), set(FRAMES))
        self.assertEqual(set(self.images), set(FRAMES))
        for frame in FRAMES:
            with self.subTest(frame=frame):
                self.assertEqual(self.images[frame], (960, 540))
                self.assertEqual(self.frames[frame]["frame"], frame)
                self.assertEqual(self.frames[frame]["measurement_space"], "final_output_px_after_camera")

    def test_foot_gates_measure_all_rendered_sole_samples_against_porch_geometry(self) -> None:
        self._require_api()
        gates = self.contract["gates"]["feet"]
        for frame, details in self.frames.items():
            feet = details["foot_evidence"]
            self.assertEqual(set(feet), {"left_boot", "right_boot"})
            for side, evidence in feet.items():
                with self.subTest(frame=frame, side=side):
                    self.assertEqual(evidence["measurement_space"], "final_output_px_after_camera")
                    self.assertEqual(
                        evidence["source_pair"],
                        [f"rendered_{side}_sole_samples", f"porch_{side}_target_geometry"],
                    )
                    self.assertNotEqual(evidence["source_pair"][0], evidence["source_pair"][1])
                    self.assertEqual(np.asarray(evidence["rendered_samples_preview_px"]).shape, (7, 2))
                    self.assertEqual(np.asarray(evidence["target_samples_preview_px"]).shape, (7, 2))
                    self.assertEqual(len(evidence["signed_distance_preview_px"]), 7)
                    provenance = evidence["sample_provenance"]
                    self.assertEqual(provenance["sample_source"], "final_component_alpha_boundary")
                    self.assertEqual(provenance["component_id"], side)
                    self.assertEqual(provenance["measurement_space"], "final_output_px_after_camera")
                    self.assertGreaterEqual(provenance["alpha_threshold"], 1)
                    boundary = np.asarray(provenance["boundary_pixels_preview_px"], dtype=np.float64)
                    self.assertEqual(boundary.ndim, 2)
                    self.assertEqual(boundary.shape[1], 2)
                    self.assertGreater(len(boundary), 7)
                    membership = np.asarray(provenance["sample_membership_residual_preview_px"], dtype=np.float64)
                    self.assertEqual(membership.shape, (7,))
                    measured_membership = np.asarray([
                        np.min(np.linalg.norm(boundary - point, axis=1))
                        for point in np.asarray(evidence["rendered_samples_preview_px"], dtype=np.float64)
                    ])
                    np.testing.assert_allclose(membership, measured_membership, atol=0.05)
                    self.assertLessEqual(float(np.max(membership)), 0.75)
                    self.assertLessEqual(evidence["toe_residual_preview_px"], gates["maximum_toe_pivot_residual_preview_px"])
                    self.assertLessEqual(evidence["endpoint_motion_preview_px_per_frame"], gates["maximum_endpoint_motion_preview_px_per_frame"])
                    self.assertLessEqual(evidence["shadow_to_sole_gap_preview_px"], gates["maximum_shadow_to_sole_gap_preview_px"])
                    self.assertEqual(evidence["shadow_source"], "rendered_contact_polygon")
                    shadow = evidence["shadow_gap_provenance"]
                    self.assertEqual(shadow["measurement"], "independent_mask_separation")
                    self.assertEqual(shadow["measurement_space"], "final_output_px_after_camera")
                    self.assertEqual(
                        shadow["source_kinds"],
                        ["final_boot_alpha_mask", "final_contact_shadow_alpha_mask"],
                    )
                    if (side == "left_boot" and frame in FLAT_LEFT_FRAMES) or (
                        side == "right_boot" and frame in FLAT_RIGHT_FRAMES
                    ):
                        self.assertLessEqual(evidence["absolute_distance_p95_preview_px"], gates["maximum_flat_sole_absolute_distance_p95_preview_px"])
                        self.assertLessEqual(evidence["maximum_clearance_preview_px"], gates["maximum_flat_sole_clearance_preview_px"])
                        self.assertLessEqual(evidence["maximum_penetration_preview_px"], gates["maximum_flat_sole_penetration_preview_px"])
                        self.assertGreaterEqual(evidence["contact_fraction"], gates["minimum_flat_sole_contact_fraction"])
                        self.assertLessEqual(abs(evidence["pitch_error_degrees"]), gates["maximum_flat_pitch_error_degrees"])

    def test_chair_contact_uses_independent_masks_continuous_load_and_real_release(self) -> None:
        self._require_api()
        gates = self.contract["gates"]["chair"]
        for frame in LOADED_HAND_FRAMES:
            hand = self.frames[frame]["chair_evidence"]["hand"]
            self.assertEqual(hand["measurement_space"], "final_output_px_after_camera")
            self.assertEqual(hand["source_pair"], ["rendered_left_hand_alpha", "rendered_chair_arm_mask"])
            self.assertLessEqual(hand["separation_preview_px"], gates["maximum_loaded_hand_to_chair_separation_preview_px"])
            self.assertLessEqual(hand["slip_preview_px"], gates["maximum_loaded_hand_slip_preview_px"])
            self.assertGreaterEqual(hand["intersection_pixels"], gates["minimum_loaded_hand_chair_intersection_pixels"])
            self.assertGreater(self.frames[frame]["loads"]["chair_hand"], 0.0)
        release = self.frames[gates["release_separation_deadline_frame"]]["chair_evidence"]["hand"]
        self.assertGreaterEqual(release["separation_preview_px"], gates["minimum_release_separation_preview_px"])
        self.assertLessEqual(release["position_jump_preview_px"], gates["maximum_release_position_jump_preview_px"])
        self.assertLessEqual(release["velocity_jump_preview_px_per_frame"], gates["maximum_release_velocity_jump_preview_px_per_frame"])
        self.assertGreaterEqual(
            self.frames[78]["chair_evidence"]["hand"]["shoulder_travel_relative_to_hand_preview_px"],
            gates["minimum_shoulder_travel_relative_to_planted_hand_preview_px"],
        )

    def test_seat_contact_is_independent_and_load_releases_continuously(self) -> None:
        self._require_api()
        gates = self.contract["gates"]["chair"]
        loaded_values = []
        for frame in range(64, 74):
            seat = self.frames[frame]["chair_evidence"]["seat"]
            load = float(self.frames[frame]["loads"]["seat"])
            loaded_values.append(load)
            self.assertEqual(seat["source_pair"], ["rendered_pelvis_alpha_boundary", "camera_transformed_chair_seat_top_receiver"])
            penetration = seat["penetration_provenance"]
            self.assertEqual(penetration["measurement"], "signed_alpha_boundary_to_receiver_depth")
            self.assertEqual(penetration["measurement_space"], "final_output_px_after_camera")
            self.assertEqual(penetration["source_pair"], seat["source_pair"])
            self.assertEqual(penetration["mask_sources"], ["final_torso_alpha_mask", "rendered_chair_seat_occlusion_mask"])
            if load > 0.05:
                self.assertLessEqual(seat["separation_preview_px"], gates["maximum_loaded_seat_separation_preview_px"])
                self.assertLessEqual(seat["penetration_preview_px"], gates["maximum_seat_penetration_preview_px"])
        self.assertTrue(any(0.0 < value < 1.0 for value in loaded_values))
        self.assertEqual(loaded_values[-1], 0.0)

    def test_com_is_computed_from_rendered_parts_and_stays_in_rendered_support_hull(self) -> None:
        self._require_api()
        gates = self.contract["gates"]["balance"]
        for frame in range(73, 113):
            balance = self.frames[frame]["balance_evidence"]
            self.assertEqual(balance["com_source"], "mass_weighted_final_output_component_alpha_centroids")
            self.assertEqual(balance["support_hull_source"], "independently_measured_rendered_contacts")
            self.assertGreaterEqual(balance["active_support_point_count"], gates["minimum_active_support_points"])
            self.assertGreaterEqual(balance["com_support_hull_margin_preview_px"], gates["minimum_com_support_hull_margin_after_seat_release_preview_px"])
            self.assertEqual(len(balance["com_preview_px"]), 2)
            self.assertGreaterEqual(len(balance["support_hull_preview_px"]), 2)
        forward = self.frames[73]["balance_evidence"]["com_preview_px"][0] - self.frames[64]["balance_evidence"]["com_preview_px"][0]
        pelvis_rise = self.frames[70]["motion_evidence"]["pelvis_preview_px"][1] - self.frames[73]["motion_evidence"]["pelvis_preview_px"][1]
        self.assertGreaterEqual(forward, gates["minimum_forward_com_travel_before_pelvis_rise_preview_px"])
        self.assertLessEqual(pelvis_rise, gates["maximum_pelvis_rise_during_forward_anticipation_preview_px"])

    def test_motion_has_bounded_jerk_and_complete_settle(self) -> None:
        self._require_api()
        gates = self.contract["gates"]["motion"]
        roots = np.asarray([self.frames[frame]["motion_evidence"]["root_preview_px"] for frame in FRAMES], dtype=np.float64)
        jerk = np.linalg.norm(np.diff(roots, n=3, axis=0), axis=1)
        self.assertLessEqual(float(np.max(jerk)), gates["maximum_root_jerk_preview_px_per_frame_cubed"])
        settle = self.frames[112]["motion_evidence"]["settle"]
        self.assertGreaterEqual(settle["upward_overshoot_preview_px"], gates["minimum_settle_upward_overshoot_preview_px"])
        self.assertGreaterEqual(settle["downward_compression_preview_px"], gates["minimum_settle_downward_compression_preview_px"])
        self.assertGreaterEqual(settle["knee_recompression_preview_px"], gates["minimum_knee_recompression_preview_px"])
        self.assertLessEqual(settle["final_root_error_preview_px"], gates["maximum_final_root_error_preview_px"])
        self.assertLessEqual(settle["final_root_speed_preview_px_per_frame"], gates["maximum_final_root_speed_preview_px_per_frame"])
        self.assertGreaterEqual(settle["stable_frame_count"], gates["required_final_stable_frames"])

    def test_all_13_joints_one_texture_and_no_ghost_metrics_pass_every_frame(self) -> None:
        self._require_api()
        gates = self.contract["gates"]["topology_and_texture"]
        for frame, details in self.frames.items():
            policy = details["texture_source_policy"]
            self.assertEqual(policy["texture_source_count"], 1)
            self.assertEqual(policy["standing_texture_sources_per_component"], 1)
            self.assertEqual(policy["seated_rgb_sample_count"], 0)
            self.assertEqual(policy["dual_source_contribution_pixels"], 0)
            self.assertFalse(policy["dual_rgba_blend_used"])
            self.assertFalse(policy["dual_alpha_blend_used"])
            self.assertFalse(policy["alpha_blend_fallback_used"])
            topology = details["topology_evidence"]
            self.assertEqual(set(topology["substantial_components_per_part"]), COMPONENT_IDS)
            self.assertTrue(all(count == 1 for count in topology["substantial_components_per_part"].values()))
            self.assertLessEqual(topology["secondary_edge_fraction"], gates["maximum_secondary_edge_fraction"])
            self.assertEqual(topology["foldover_count"], 0)
            joints = details["joint_evidence"]
            self.assertEqual(set(joints), JOINT_IDS)
            for metrics in joints.values():
                self.assertLessEqual(metrics["gap_preview_px"], gates["maximum_joint_gap_preview_px"])
                self.assertGreaterEqual(metrics["overlap_pixels"], gates["minimum_joint_overlap_pixels"])
                self.assertGreaterEqual(metrics["bridge_width_preview_px"], gates["minimum_joint_bridge_width_preview_px"])

    def test_renderer_fails_closed_on_missing_or_self_referential_contact_evidence(self) -> None:
        self._require_api()
        mutations = (
            lambda row: row["boot_contact_geometry"]["left_boot"].update({"sole_samples_component_local_px": [[1, 1]] * 7}),
            lambda row: row["proof"].update({"measurement_space": "registered_source_px_pre_camera"}),
            lambda row: row["source_policy"]["seated_geometry_contract"].update({"rgb_sample_count": 1}),
            lambda row: row["source_policy"].update({"texture_source_count": 2}),
            lambda row: row["evidence_policy"].update({"self_contact_is_not_contact": False}),
        )
        for index, mutation in enumerate(mutations):
            path = self._temporary_contract(mutation)
            with self.subTest(mutation=index):
                with self.assertRaises((ValueError, AssertionError)):
                    ContactPerformanceRenderer(path)

    def test_entrypoint_encodes_and_decodes_exactly_49_frames_with_separate_audience_status(self) -> None:
        self._require_api()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            render_contact_performance_proof(CONTRACT_PATH, output, ffmpeg="ffmpeg")
            report = _load_json(output / self.contract["report_contract"]["filename"])
            video = output / self.contract["report_contract"]["video_filename"]
            self.assertTrue(video.is_file())
            capture = cv2.VideoCapture(str(video))
            self.assertTrue(capture.isOpened())
            decoded = 0
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                self.assertEqual(image.shape[:2], (540, 960))
                decoded += 1
            fps = capture.get(cv2.CAP_PROP_FPS)
            capture.release()
            self.assertEqual(decoded, 49)
            self.assertAlmostEqual(fps, 30.0, delta=0.01)
            self.assertEqual(report["delivery"]["encoded_frames"], 49)
            self.assertEqual(report["delivery"]["decoded_frames"], 49)
            self.assertEqual(
                set(report["gate_results"]),
                set(self.contract["report_contract"]["required_gate_results"]),
            )
            recomputed = evaluate_contact_gate_results(self.contract, report["aggregate_measurements"])
            self.assertEqual(report["threshold_results"], recomputed["threshold_results"])
            self.assertEqual(report["gate_results"], recomputed["gate_results"])
            self.assertEqual(report["machine_passed"], recomputed["machine_passed"])
            self.assertTrue(all(report["gate_results"].values()))
            self.assertTrue(report["machine_passed"])
            self.assertEqual(report["audience_quality"]["status"], "unevaluated")
            self.assertFalse(report["audience_quality"]["may_be_inferred_from_machine_pass"])

    def test_renderer_rejects_frames_outside_bounded_proof(self) -> None:
        self._require_api()
        with ContactPerformanceRenderer(CONTRACT_PATH) as renderer:
            with self.assertRaisesRegex(ValueError, "64 through 112"):
                renderer.render_frame(63)
            with self.assertRaisesRegex(ValueError, "64 through 112"):
                renderer.render_frame(113)


if __name__ == "__main__":
    unittest.main()
