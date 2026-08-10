from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from pipeline.cartoon_dual_atlas_performance_proof import load_seated_atlas_contract
from pipeline.cartoon_puppet_atlas_transition_proof import load_puppet_atlas_contract
from pipeline.cartoon_shared_uv_performance_proof import (
    SharedUVPerformanceRenderer,
    build_strip_cage,
    render_shared_uv_performance_proof,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
SEATED_CONTRACT = REPO_ROOT / "concept/characters/june_oxley_puppet_atlas_seated_v1.json"
TRANSITION_FRAMES = tuple(range(64, 101))

COMPONENT_IDS = {
    "head",
    "torso",
    "left_upper_arm",
    "right_upper_arm",
    "left_forearm",
    "right_forearm",
    "left_hand",
    "right_hand_mug",
    "left_thigh",
    "right_thigh",
    "left_shin",
    "right_shin",
    "left_boot",
    "right_boot",
}

JOINT_PAIRS = {
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

CONTACT_IDS = {
    "left_boot",
    "right_boot",
    "chair_hand",
    "chair_seat",
    "mug_hand",
    "mug_center",
}

JOINT_COMPONENTS = {
    identifier: tuple(identifier.split("__", 1))
    for identifier in JOINT_PAIRS
}

CONTACT_COMPONENTS = {
    "left_boot": "left_boot",
    "right_boot": "right_boot",
    "chair_hand": "left_hand",
    "chair_seat": "torso",
    "mug_hand": "right_hand_mug",
    "mug_center": "right_hand_mug",
}

# These are the accepted dual-atlas endpoint results.  A new representation
# must not gain cleaner internals by giving away the endpoint silhouettes.
SEATED_ENDPOINT_IOU_BASELINE = 0.6293958521190262
STANDING_ENDPOINT_IOU_BASELINE = 0.6972780375832948


def _substantial_component_count(alpha: np.ndarray) -> int:
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        np.asarray(alpha > 8, dtype=np.uint8),
        8,
    )
    return sum(
        int(stats[index, cv2.CC_STAT_AREA]) >= 25
        for index in range(1, count)
    )


def _triangle_signed_areas(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    first = vertices[triangles[:, 0]]
    second = vertices[triangles[:, 1]]
    third = vertices[triangles[:, 2]]
    cross = (
        (second[:, 0] - first[:, 0]) * (third[:, 1] - first[:, 1])
        - (second[:, 1] - first[:, 1]) * (third[:, 0] - first[:, 0])
    )
    return cross * 0.5


def _alpha_iou(left: np.ndarray, right: np.ndarray) -> float:
    left_mask = left > 8
    right_mask = right > 8
    union = int(np.count_nonzero(left_mask | right_mask))
    return int(np.count_nonzero(left_mask & right_mask)) / union if union else 1.0


def _nearest_alpha_boundary(
    alpha: np.ndarray,
    target: np.ndarray,
) -> tuple[np.ndarray, float]:
    mask = np.asarray(alpha > 8, dtype=np.uint8)
    eroded = cv2.erode(mask, np.ones((3, 3), dtype=np.uint8), iterations=1)
    boundary = (mask > 0) & (eroded == 0)
    ys, xs = np.where(boundary)
    if not len(xs):
        raise AssertionError("contact component has no independently measurable alpha boundary")
    points = np.column_stack((xs, ys)).astype(np.float64)
    distances = np.linalg.norm(points - np.asarray(target, dtype=np.float64), axis=1)
    index = int(np.argmin(distances))
    return points[index], float(distances[index])


def _joint_roi_measurement(
    left: np.ndarray,
    right: np.ndarray,
    socket: np.ndarray,
    radius: int,
) -> tuple[int, float]:
    height, width = left.shape
    yy, xx = np.ogrid[:height, :width]
    roi = (
        (xx - float(socket[0])) ** 2 + (yy - float(socket[1])) ** 2
        <= float(radius * radius)
    )
    overlap = (left > 8) & (right > 8) & roi
    overlap_pixels = int(np.count_nonzero(overlap))
    bridge = (
        2.0 * float(np.max(cv2.distanceTransform(overlap.astype(np.uint8), cv2.DIST_L2, 3)))
        if overlap_pixels
        else 0.0
    )
    return overlap_pixels, bridge


class CartoonSharedUVPerformanceProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seated_contract, seated_components, cls.seated_component_count = load_seated_atlas_contract(
            SEATED_CONTRACT
        )
        standing_path = REPO_ROOT / cls.seated_contract["standing_atlas_contract"]["path"]
        cls.standing_inputs = load_puppet_atlas_contract(standing_path)
        cls.seated_by_id = {component.identifier: component for component in seated_components}
        cls.standing_by_id = {
            component.identifier: component for component in cls.standing_inputs.components
        }
        cls.seated_cages = {
            identifier: build_strip_cage(component.rgba, component.source_bone)
            for identifier, component in cls.seated_by_id.items()
        }
        cls.standing_cages = {
            identifier: build_strip_cage(component.rgba, component.source_bone)
            for identifier, component in cls.standing_by_id.items()
        }

        # Exercise the full bounded proof in memory, but retain only scalar QA
        # evidence so the test suite does not cache hundreds of megabytes of
        # per-component alpha planes.
        cls.frames: dict[int, dict[str, object]] = {}
        cls.character_alphas: dict[int, np.ndarray] = {}
        cls.representative_component_alphas: dict[int, dict[str, np.ndarray]] = {}
        cls.frame82_rgb: np.ndarray | None = None
        with SharedUVPerformanceRenderer(SEATED_CONTRACT) as renderer:
            cls.renderer_contract = renderer.contract
            cls.pose0_alpha = renderer.base.pose0_alpha.copy()
            cls.pose100_alpha = renderer.base.pose100_alpha.copy()
            for frame in TRANSITION_FRAMES:
                image, details = renderer.render_frame(frame)
                try:
                    right_forearm_components = _substantial_component_count(
                        details["component_alphas"]["right_forearm"]
                    )
                    cls.frames[frame] = {
                        "image_size": image.size,
                        "texture_source_policy": dict(details["texture_source_policy"]),
                        "mesh_metrics": {
                            identifier: dict(metrics)
                            for identifier, metrics in details["mesh_metrics"].items()
                        },
                        "joint_metrics": {
                            identifier: dict(metrics)
                            for identifier, metrics in details["joint_metrics"].items()
                        },
                        "contact_evidence": {
                            identifier: dict(metrics)
                            for identifier, metrics in details["contact_evidence"].items()
                        },
                        "right_forearm_components": right_forearm_components,
                        "character_alpha_area": int(
                            np.count_nonzero(details["character_alpha"] > 8)
                        ),
                        "transition_weight": float(details["transition_weight"]),
                    }
                    cls.character_alphas[frame] = details["character_alpha"].copy()
                    if frame in (70, 82, 100):
                        cls.representative_component_alphas[frame] = {
                            identifier: alpha.copy()
                            for identifier, alpha in details["component_alphas"].items()
                        }
                    if frame == 82:
                        cls.frame82_rgb = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
                finally:
                    image.close()
        if cls.frame82_rgb is None:
            raise AssertionError("representative frame 82 was not captured")

    def test_contract_locks_exact_bounded_delivery_clock(self) -> None:
        proof = self.renderer_contract["proof"]
        self.assertEqual(proof["transition_frame_range"], [64, 100])
        self.assertEqual((proof["width"], proof["height"], proof["fps"]), (960, 540, 30))
        self.assertEqual(len(TRANSITION_FRAMES), 37)
        self.assertEqual(set(self.frames), set(TRANSITION_FRAMES))
        self.assertTrue(all(row["image_size"] == (960, 540) for row in self.frames.values()))
        self.assertTrue(all(row["character_alpha_area"] > 0 for row in self.frames.values()))

    def test_exactly_fourteen_components_share_one_fixed_topology_each(self) -> None:
        self.assertEqual(self.seated_component_count, 14)
        self.assertEqual(set(self.seated_by_id), COMPONENT_IDS)
        self.assertEqual(set(self.standing_by_id), COMPONENT_IDS)
        self.assertEqual(set(self.seated_cages), COMPONENT_IDS)
        self.assertEqual(set(self.standing_cages), COMPONENT_IDS)
        for identifier in sorted(COMPONENT_IDS):
            with self.subTest(component=identifier):
                seated = self.seated_cages[identifier]
                standing = self.standing_cages[identifier]
                self.assertEqual(seated.vertices.shape, (21, 2))
                self.assertEqual(standing.vertices.shape, (21, 2))
                self.assertEqual(seated.triangles.shape, (24, 3))
                self.assertEqual(standing.triangles.shape, (24, 3))
                np.testing.assert_array_equal(seated.triangles, standing.triangles)

    def test_canonical_cages_have_positive_orientation_and_995_alpha_coverage(self) -> None:
        for endpoint, cages in (
            ("seated_geometry", self.seated_cages),
            ("standing_texture", self.standing_cages),
        ):
            for identifier, cage in cages.items():
                with self.subTest(endpoint=endpoint, component=identifier):
                    areas = _triangle_signed_areas(cage.vertices, cage.triangles)
                    self.assertTrue(np.all(np.isfinite(areas)))
                    self.assertTrue(np.all(areas > 0.0), "canonical cage triangle folded or collapsed")
                    self.assertGreaterEqual(cage.coverage, 0.995)

    def test_renderer_fails_closed_if_canonical_alpha_coverage_is_below_995(self) -> None:
        valid = self.standing_cages["torso"]
        insufficient = replace(valid, coverage=0.994)
        with patch(
            "pipeline.cartoon_shared_uv_performance_proof.build_strip_cage",
            return_value=insufficient,
        ):
            with self.assertRaisesRegex(ValueError, "coverage|99.5"):
                SharedUVPerformanceRenderer(SEATED_CONTRACT)

    def test_only_standing_pixels_supply_texture_and_seated_atlas_is_geometry_only(self) -> None:
        for frame, row in self.frames.items():
            policy = row["texture_source_policy"]
            with self.subTest(frame=frame):
                self.assertEqual(policy["texture_atlas_role"], "standing")
                self.assertEqual(policy["texture_source_count"], 1)
                self.assertEqual(policy["standing_texture_sources_per_component"], 1)
                self.assertEqual(policy["seated_rgb_sample_count"], 0)
                self.assertTrue(policy["seated_geometry_only"])
                self.assertFalse(policy["dual_rgba_blend_used"])
                self.assertFalse(policy["dual_alpha_blend_used"])
                self.assertFalse(policy["alpha_blend_fallback_used"])

    def test_seated_rgb_recolor_is_pixel_invariant_at_representative_frame(self) -> None:
        original_loader = load_seated_atlas_contract

        def recolored_geometry_loader(path: str | Path):
            contract, components, count = original_loader(path)
            recolored = []
            for component in components:
                rgba = component.rgba.copy()
                # Deliberately extreme colors; alpha and every geometric field
                # remain byte-identical.
                rgba[:, :, 0] = 255
                rgba[:, :, 1] = 0
                rgba[:, :, 2] = 255
                recolored.append(replace(component, rgba=rgba))
            return contract, tuple(recolored), count

        with patch(
            "pipeline.cartoon_shared_uv_performance_proof.load_seated_atlas_contract",
            side_effect=recolored_geometry_loader,
        ):
            with SharedUVPerformanceRenderer(SEATED_CONTRACT) as renderer:
                image, _ = renderer.render_frame(82)
                try:
                    recolored = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
                finally:
                    image.close()
        np.testing.assert_array_equal(recolored, self.frame82_rgb)

    def test_standing_rgb_recolor_materially_changes_representative_frame(self) -> None:
        with SharedUVPerformanceRenderer(SEATED_CONTRACT) as renderer:
            for component in renderer.components:
                texture = component.standing_texture
                alpha = texture[:, :, 3]
                texture[:, :, 0] = alpha
                texture[:, :, 1] = alpha * 0.03
                texture[:, :, 2] = alpha * 0.03
            image, _ = renderer.render_frame(82)
            try:
                recolored = np.asarray(image.convert("RGB"), dtype=np.uint8).copy()
            finally:
                image.close()
        changed = np.any(recolored != self.frame82_rgb, axis=2)
        self.assertGreater(np.count_nonzero(changed), 1000)

    def test_every_frame_preserves_triangle_orientation_and_bounded_area(self) -> None:
        for frame, row in self.frames.items():
            metrics_by_component = row["mesh_metrics"]
            self.assertEqual(set(metrics_by_component), COMPONENT_IDS)
            for identifier, metrics in metrics_by_component.items():
                with self.subTest(frame=frame, component=identifier):
                    self.assertEqual(metrics["vertex_count"], 21)
                    self.assertEqual(metrics["triangle_count"], 24)
                    self.assertEqual(metrics["foldover_count"], 0)
                    self.assertTrue(metrics["orientation_preserved"])
                    self.assertGreaterEqual(metrics["minimum_triangle_area_ratio"], 0.1)
                    self.assertLessEqual(metrics["maximum_triangle_area_ratio"], 10.0)
                    self.assertGreater(metrics["minimum_signed_area_preview_px2"], 0.0)
                    self.assertGreaterEqual(metrics["canonical_alpha_mesh_coverage"], 0.995)

    def test_right_forearm_remains_exactly_one_substantial_component(self) -> None:
        self.assertEqual(
            {frame: row["right_forearm_components"] for frame, row in self.frames.items()},
            {frame: 1 for frame in TRANSITION_FRAMES},
        )

    def test_all_thirteen_joints_report_gap_overlap_and_bridge_width(self) -> None:
        ankle_and_wrist_pairs = {
            "left_shin__left_boot",
            "right_shin__right_boot",
            "left_forearm__left_hand",
            "right_forearm__right_hand_mug",
        }
        self.assertTrue(ankle_and_wrist_pairs.issubset(JOINT_PAIRS))
        for frame, row in self.frames.items():
            metrics_by_joint = row["joint_metrics"]
            self.assertEqual(set(metrics_by_joint), JOINT_PAIRS)
            for identifier, metrics in metrics_by_joint.items():
                with self.subTest(frame=frame, joint=identifier):
                    self.assertTrue(np.isfinite(metrics["gap_preview_px"]))
                    self.assertLessEqual(metrics["gap_preview_px"], 1.5)
                    self.assertGreater(metrics["overlap_pixels"], 0)
                    self.assertGreaterEqual(metrics["bridge_width_preview_px"], 1.0)
                    self.assertTrue(metrics["connected"])

    def test_joint_overlap_and_bridge_are_local_to_the_declared_socket(self) -> None:
        for frame in (70, 82, 100):
            alphas = self.representative_component_alphas[frame]
            metrics_by_joint = self.frames[frame]["joint_metrics"]
            for identifier, (left_id, right_id) in JOINT_COMPONENTS.items():
                metrics = metrics_by_joint[identifier]
                with self.subTest(frame=frame, joint=identifier):
                    socket = np.asarray(metrics["socket_preview_px"], dtype=np.float64)
                    radius = int(metrics["joint_roi_radius_preview_px"])
                    self.assertGreaterEqual(radius, 8)
                    self.assertLessEqual(radius, 48)
                    overlap, bridge = _joint_roi_measurement(
                        alphas[left_id],
                        alphas[right_id],
                        socket,
                        radius,
                    )
                    self.assertEqual(metrics["joint_roi_overlap_pixels"], overlap)
                    self.assertAlmostEqual(
                        metrics["joint_roi_bridge_width_preview_px"],
                        bridge,
                        delta=0.05,
                    )
                    self.assertGreater(overlap, 0)
                    self.assertGreaterEqual(bridge, 1.0)

    def test_contacts_use_rendered_socket_residuals_not_alpha_centroids(self) -> None:
        for frame, row in self.frames.items():
            evidence_by_contact = row["contact_evidence"]
            self.assertEqual(set(evidence_by_contact), CONTACT_IDS)
            for identifier, evidence in evidence_by_contact.items():
                with self.subTest(frame=frame, contact=identifier):
                    expected_measurement = (
                        "nearest_rendered_alpha_boundary_residual"
                        if identifier in {"left_boot", "right_boot"}
                        else "rendered_socket_residual"
                    )
                    self.assertEqual(evidence["measurement"], expected_measurement)
                    self.assertIn("active", evidence)
                    if evidence["active"]:
                        self.assertIsNotNone(evidence["socket_error_preview_px"])
                        self.assertLessEqual(evidence["socket_error_preview_px"], 1.5)
                        self.assertGreater(evidence["roi_alpha_presence"], 0.0)
                        target = np.asarray(evidence["target_socket_preview_px"], dtype=np.float64)
                        rendered = np.asarray(evidence["rendered_socket_preview_px"], dtype=np.float64)
                        self.assertAlmostEqual(
                            evidence["socket_error_preview_px"],
                            float(np.linalg.norm(rendered - target)),
                            delta=0.05,
                        )
                    else:
                        self.assertIsNone(evidence["socket_error_preview_px"])
        self.assertTrue(all(self.frames[frame]["contact_evidence"]["chair_seat"]["active"] for frame in range(64, 71)))
        self.assertTrue(all(not self.frames[frame]["contact_evidence"]["chair_seat"]["active"] for frame in range(71, 101)))
        self.assertTrue(all(self.frames[frame]["contact_evidence"]["chair_hand"]["active"] for frame in range(64, 79)))
        self.assertTrue(all(not self.frames[frame]["contact_evidence"]["chair_hand"]["active"] for frame in range(79, 101)))

    def test_active_boot_contacts_are_independently_measured_from_alpha_boundaries(self) -> None:
        for frame in (70, 82, 100):
            for identifier in ("left_boot", "right_boot"):
                evidence = self.frames[frame]["contact_evidence"][identifier]
                alpha = self.representative_component_alphas[frame][CONTACT_COMPONENTS[identifier]]
                target = np.asarray(evidence["target_socket_preview_px"], dtype=np.float64)
                independent_point, independent_error = _nearest_alpha_boundary(alpha, target)
                rendered = np.asarray(evidence["rendered_socket_preview_px"], dtype=np.float64)
                with self.subTest(frame=frame, contact=identifier):
                    self.assertTrue(evidence["active"])
                    self.assertEqual(
                        evidence["measurement"],
                        "nearest_rendered_alpha_boundary_residual",
                    )
                    np.testing.assert_allclose(rendered, independent_point, atol=0.75)
                    self.assertAlmostEqual(
                        evidence["socket_error_preview_px"],
                        independent_error,
                        delta=0.75,
                    )
                    self.assertFalse(np.array_equal(rendered, target))
                    self.assertLessEqual(independent_error, 1.5)

    def test_temporal_alpha_is_continuous_but_the_action_does_not_freeze(self) -> None:
        temporal = {
            (left, right): _alpha_iou(self.character_alphas[left], self.character_alphas[right])
            for left, right in zip(TRANSITION_FRAMES, TRANSITION_FRAMES[1:])
        }
        self.assertGreaterEqual(min(temporal.values()), 0.80)
        action_values = [
            temporal[(frame, frame + 1)]
            for frame in range(70, 96)
        ]
        self.assertGreaterEqual(sum(value < 0.999 for value in action_values), 20)
        self.assertLess(min(action_values), 0.98)

    def test_shared_uv_endpoints_do_not_regress_from_accepted_dual_atlas_silhouettes(self) -> None:
        seated_iou = _alpha_iou(self.character_alphas[64], self.pose0_alpha)
        standing_iou = _alpha_iou(self.character_alphas[100], self.pose100_alpha)
        self.assertGreaterEqual(seated_iou, SEATED_ENDPOINT_IOU_BASELINE)
        self.assertGreaterEqual(standing_iou, STANDING_ENDPOINT_IOU_BASELINE)

    def test_transition_weight_is_bounded_monotone_and_has_exact_endpoint_holds(self) -> None:
        weights = [self.frames[frame]["transition_weight"] for frame in TRANSITION_FRAMES]
        self.assertTrue(all(0.0 <= weight <= 1.0 for weight in weights))
        self.assertTrue(all(left <= right for left, right in zip(weights, weights[1:])))
        self.assertTrue(all(self.frames[frame]["transition_weight"] == 0.0 for frame in range(64, 71)))
        self.assertTrue(all(self.frames[frame]["transition_weight"] == 1.0 for frame in range(96, 101)))

    def test_renderer_rejects_frames_outside_the_bounded_proof(self) -> None:
        with SharedUVPerformanceRenderer(SEATED_CONTRACT) as renderer:
            with self.assertRaisesRegex(ValueError, "64 through 100"):
                renderer.render_frame(63)
            with self.assertRaisesRegex(ValueError, "64 through 100"):
                renderer.render_frame(101)

    def test_render_entrypoint_has_an_explicit_output_and_ffmpeg_boundary(self) -> None:
        signature = inspect.signature(render_shared_uv_performance_proof)
        self.assertEqual(list(signature.parameters)[:2], ["seated_contract_path", "output_dir"])
        self.assertIn("ffmpeg", signature.parameters)
        self.assertEqual(signature.parameters["ffmpeg"].default, "ffmpeg")


if __name__ == "__main__":
    unittest.main()
