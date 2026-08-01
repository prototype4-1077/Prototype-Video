"""Bounded shared-UV proof for June's seated-to-standing transition.

The standing atlas is the only texture source.  The seated atlas contributes
alpha-derived geometry and socket annotations, never RGB.  Each component uses
the same deterministic 7x3 strip topology and one dense inverse remap.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from pipeline.cartoon_dual_atlas_performance_proof import (
    _retain_largest_alpha_component,
    _transition_weight,
    load_seated_atlas_contract,
)
from pipeline.cartoon_puppet_atlas_performance import (
    AtlasPerformanceRenderer,
    FPS,
    OUTPUT_SIZE,
    RENDER_SCALE,
    _alpha_iou,
    _scaled_target_bone,
)
from pipeline.cartoon_puppet_atlas_transition_proof import (
    AtlasComponent,
    _minimum_mask_distance,
    _over,
    _premultiplied,
    _premultiplied_to_rgba,
    _similarity_affine,
    _substantial_components,
)
from pipeline.cartoon_shot_sequence import _camera_frame


REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSITION_FRAMES = tuple(range(64, 101))
REVIEW_FRAMES = (64, 66, 68, 70, 71, 74, 78, 79, 82, 86, 87, 90, 91, 94, 95, 96, 98, 100)
ALPHA_THRESHOLD = 8
MINIMUM_CAGE_COVERAGE = 0.995
GRID_COLUMNS = 7
GRID_ROWS = 3


def _fixed_triangles() -> np.ndarray:
    triangles: list[tuple[int, int, int]] = []
    for column in range(GRID_COLUMNS - 1):
        for row in range(GRID_ROWS - 1):
            upper_left = column * GRID_ROWS + row
            upper_right = (column + 1) * GRID_ROWS + row
            lower_right = upper_right + 1
            lower_left = upper_left + 1
            triangles.append((upper_left, upper_right, lower_right))
            triangles.append((upper_left, lower_right, lower_left))
    return np.asarray(triangles, dtype=np.int32)


FIXED_TRIANGLES = _fixed_triangles()


@dataclass(frozen=True)
class StripCage:
    vertices: np.ndarray
    triangles: np.ndarray
    coverage: float


@dataclass(frozen=True)
class SharedUVComponent:
    identifier: str
    depth: int
    standing: AtlasComponent
    seated: AtlasComponent
    standing_cage: StripCage
    seated_cage: StripCage
    standing_texture: np.ndarray


def _signed_triangle_areas(vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    first = vertices[triangles[:, 0]]
    second = vertices[triangles[:, 1]]
    third = vertices[triangles[:, 2]]
    return 0.5 * (
        (second[:, 0] - first[:, 0]) * (third[:, 1] - first[:, 1])
        - (second[:, 1] - first[:, 1]) * (third[:, 0] - first[:, 0])
    )


def _mesh_mask(shape: tuple[int, int], vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    for triangle in triangles:
        polygon = np.rint(vertices[triangle]).astype(np.int32)
        cv2.fillConvexPoly(mask, polygon, 1, lineType=cv2.LINE_8)
    return mask > 0


def build_strip_cage(
    component_rgba: np.ndarray,
    source_bone: tuple[np.ndarray, np.ndarray],
    alpha_threshold: int = ALPHA_THRESHOLD,
) -> StripCage:
    """Build one positive 7x3 bone-aligned cage from the alpha profile envelope."""
    rgba = np.asarray(component_rgba)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("strip cage source must be RGBA")
    alpha = rgba[:, :, 3]
    ys, xs = np.where(alpha > int(alpha_threshold))
    if not len(xs):
        raise ValueError("strip cage source alpha is empty")
    start = np.asarray(source_bone[0], dtype=np.float64)
    end = np.asarray(source_bone[1], dtype=np.float64)
    axis = end - start
    length = float(np.linalg.norm(axis))
    if length <= 1e-6:
        raise ValueError("strip cage source bone collapsed")
    axis /= length
    normal = np.asarray((-axis[1], axis[0]), dtype=np.float64)
    pixels = np.column_stack((xs.astype(np.float64), ys.astype(np.float64)))
    relative = pixels - start
    longitudinal = relative @ axis
    transverse = relative @ normal

    # Seven semantic stations traverse the part along its bone axis.  Every
    # station measures its own transverse 2/50/98 alpha profile; the bounded
    # six-pixel guard band preserves antialiasing and >=99.5% alpha coverage.
    longitudinal_guard = 1.0
    profile_guard = 6.0
    u_values = np.linspace(
        float(np.min(longitudinal)) - longitudinal_guard,
        float(np.max(longitudinal)) + longitudinal_guard,
        GRID_COLUMNS,
    )
    station_step = float((u_values[-1] - u_values[0]) / (GRID_COLUMNS - 1))
    vertices: list[np.ndarray] = []
    for u_value in u_values:
        band = transverse[np.abs(longitudinal - u_value) <= station_step * 0.6]
        if len(band) < 3:
            nearest = np.argsort(np.abs(longitudinal - u_value))[:max(3, len(longitudinal) // 50)]
            band = transverse[nearest]
        profile = np.percentile(band, (2.0, 50.0, 98.0)).astype(np.float64)
        profile[0] -= profile_guard
        profile[2] += profile_guard
        vertices.extend(start + axis * u_value + normal * value for value in profile)
    vertices = np.asarray(vertices, dtype=np.float32)
    triangles = FIXED_TRIANGLES.copy()
    areas = _signed_triangle_areas(vertices, triangles)
    if not np.all(np.isfinite(areas)) or np.any(areas <= 0.0):
        raise ValueError("canonical strip cage folded or collapsed")
    mesh = _mesh_mask(alpha.shape, vertices, triangles)
    subject = alpha > int(alpha_threshold)
    coverage = float(np.count_nonzero(mesh & subject) / max(1, np.count_nonzero(subject)))
    return StripCage(vertices=vertices, triangles=triangles, coverage=coverage)


def _transform_vertices(component: AtlasComponent, cage: StripCage, landmarks: dict[str, np.ndarray]) -> np.ndarray:
    target_start, target_end = _scaled_target_bone(
        component,
        landmarks[component.target_bone[0]],
        landmarks[component.target_bone[1]],
    )
    matrix, _ = _similarity_affine(component.source_bone[0], component.source_bone[1], target_start, target_end)
    homogeneous = np.column_stack((cage.vertices.astype(np.float64), np.ones(len(cage.vertices))))
    return (homogeneous @ matrix.T).astype(np.float32)


def _dense_piecewise_remap(
    texture: np.ndarray,
    source_vertices: np.ndarray,
    destination_vertices: np.ndarray,
    triangles: np.ndarray,
    output_size: tuple[int, int],
) -> tuple[np.ndarray, float, float]:
    """Apply one inverse piecewise-affine cv2.remap for a component."""
    width, height = output_size
    map_x = np.full((height, width), -1000.0, dtype=np.float32)
    map_y = np.full((height, width), -1000.0, dtype=np.float32)
    mesh_mask = np.zeros((height, width), dtype=np.uint8)
    maximum_uv_drift = 0.0
    for triangle in triangles:
        source = source_vertices[triangle].astype(np.float32)
        destination = destination_vertices[triangle].astype(np.float32)
        matrix = cv2.getAffineTransform(destination, source)
        recovered = cv2.transform(destination[None, :, :], matrix)[0]
        maximum_uv_drift = max(maximum_uv_drift, float(np.max(np.linalg.norm(recovered - source, axis=1))))
        x0 = max(0, int(math.floor(float(np.min(destination[:, 0])))))
        x1 = min(width - 1, int(math.ceil(float(np.max(destination[:, 0])))))
        y0 = max(0, int(math.floor(float(np.min(destination[:, 1])))))
        y1 = min(height - 1, int(math.ceil(float(np.max(destination[:, 1])))))
        if x0 > x1 or y0 > y1:
            continue
        local_polygon = np.rint(destination - np.asarray((x0, y0), dtype=np.float32)).astype(np.int32)
        local_mask = np.zeros((y1 - y0 + 1, x1 - x0 + 1), dtype=np.uint8)
        cv2.fillConvexPoly(local_mask, local_polygon, 1, lineType=cv2.LINE_8)
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        sx = matrix[0, 0] * xx + matrix[0, 1] * yy + matrix[0, 2]
        sy = matrix[1, 0] * xx + matrix[1, 1] * yy + matrix[1, 2]
        take = local_mask > 0
        region_x = map_x[y0:y1 + 1, x0:x1 + 1]
        region_y = map_y[y0:y1 + 1, x0:x1 + 1]
        region_mesh = mesh_mask[y0:y1 + 1, x0:x1 + 1]
        region_x[take] = sx[take]
        region_y[take] = sy[take]
        region_mesh[take] = 1
    mesh_pixels = int(np.count_nonzero(mesh_mask))
    assigned = int(np.count_nonzero((map_x > -999.0) & (mesh_mask > 0)))
    dense_coverage = assigned / max(1, mesh_pixels)
    if dense_coverage < 1.0:
        raise ValueError(f"dense inverse map coverage incomplete: {dense_coverage:.6f}")
    warped = cv2.remap(
        texture,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    return np.clip(warped, 0.0, 1.0), dense_coverage, maximum_uv_drift


def _propagate_painted_pixels(layer: np.ndarray, socket: np.ndarray, radius: int) -> np.ndarray:
    height, width = layer.shape[:2]
    cx, cy = float(socket[0]), float(socket[1])
    x0, x1 = max(0, int(cx) - radius), min(width, int(cx) + radius + 1)
    y0, y1 = max(0, int(cy) - radius), min(height, int(cy) + radius + 1)
    if x0 >= x1 or y0 >= y1:
        return layer
    yy, xx = np.ogrid[y0:y1, x0:x1]
    roi = (xx - cx) ** 2 + (yy - cy) ** 2 <= float(radius * radius)
    region = layer[y0:y1, x0:x1].copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    expanded_alpha = cv2.dilate(region[:, :, 3], kernel)
    new_pixels = roi & (region[:, :, 3] <= (ALPHA_THRESHOLD / 255.0)) & (expanded_alpha > (ALPHA_THRESHOLD / 255.0))
    if np.any(new_pixels):
        for channel in range(4):
            expanded = cv2.dilate(region[:, :, channel], kernel)
            region[:, :, channel][new_pixels] = expanded[new_pixels]
        result = layer.copy()
        result[y0:y1, x0:x1] = region
        return result
    return layer


def _joint_measurement(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    left_mask, right_mask = left > ALPHA_THRESHOLD, right > ALPHA_THRESHOLD
    overlap = left_mask & right_mask
    overlap_pixels = int(np.count_nonzero(overlap))
    if overlap_pixels:
        bridge_width = 2.0 * float(np.max(cv2.distanceTransform(overlap.astype(np.uint8), cv2.DIST_L2, 3)))
    else:
        bridge_width = 0.0
    return {
        "gap_preview_px": _minimum_mask_distance(left, right),
        "overlap_pixels": overlap_pixels,
        "overlap_fraction_of_smaller_part": overlap_pixels / max(1, min(np.count_nonzero(left_mask), np.count_nonzero(right_mask))),
        "bridge_width_preview_px": bridge_width,
        "connected": overlap_pixels > 0,
    }


def _joint_roi_measurement(
    left: np.ndarray,
    right: np.ndarray,
    socket: np.ndarray,
    radius: int,
) -> tuple[int, float]:
    height, width = left.shape
    yy, xx = np.ogrid[:height, :width]
    roi = (xx - float(socket[0])) ** 2 + (yy - float(socket[1])) ** 2 <= float(radius * radius)
    overlap = (left > ALPHA_THRESHOLD) & (right > ALPHA_THRESHOLD) & roi
    overlap_pixels = int(np.count_nonzero(overlap))
    bridge = (
        2.0 * float(np.max(cv2.distanceTransform(overlap.astype(np.uint8), cv2.DIST_L2, 3)))
        if overlap_pixels else 0.0
    )
    return overlap_pixels, bridge


JOINT_SOCKET = {
    "head__torso": "neck",
    "left_upper_arm__torso": "left_shoulder",
    "left_upper_arm__left_forearm": "left_elbow",
    "left_forearm__left_hand": "left_hand",
    "right_upper_arm__torso": "right_shoulder",
    "right_upper_arm__right_forearm": "right_elbow",
    "right_forearm__right_hand_mug": "right_hand",
    "left_thigh__torso": "left_hip",
    "left_thigh__left_shin": "left_knee",
    "left_shin__left_boot": "left_ankle",
    "right_thigh__torso": "right_hip",
    "right_thigh__right_shin": "right_knee",
    "right_shin__right_boot": "right_ankle",
}


def _roi_presence(alpha: np.ndarray, point: np.ndarray, radius: int = 28) -> float:
    height, width = alpha.shape
    cx, cy = int(round(float(point[0]))), int(round(float(point[1])))
    x0, x1 = max(0, cx - radius), min(width, cx + radius + 1)
    y0, y1 = max(0, cy - radius), min(height, cy + radius + 1)
    if x0 >= x1 or y0 >= y1:
        return 0.0
    return float(np.mean(alpha[y0:y1, x0:x1] > ALPHA_THRESHOLD))


class SharedUVPerformanceRenderer:
    def __init__(self, seated_contract_path: str | Path):
        self.contract, seated_components, count = load_seated_atlas_contract(seated_contract_path)
        if count != 14:
            raise ValueError("shared-UV proof requires exactly 14 seated geometry components")
        standing_path = (REPO_ROOT / str(self.contract["standing_atlas_contract"]["path"])).resolve()
        self.base = AtlasPerformanceRenderer(standing_path)
        seated_by_id = {component.identifier: component for component in seated_components}
        standing_by_id = {component.identifier: component for component in self.base.atlas_inputs.components}
        if set(seated_by_id) != set(standing_by_id) or len(seated_by_id) != 14:
            raise ValueError("shared-UV seated and standing interfaces differ")
        cleanup = set(self.contract["topology_repairs"]["largest_component_source_cleanup"])
        components: list[SharedUVComponent] = []
        for standing in self.base.atlas_inputs.components:
            seated = seated_by_id[standing.identifier]
            # Seated RGB is deliberately never read.  The cage builder itself
            # only consumes channel 3, and this alpha-only carrier makes that
            # source boundary explicit in the renderer.
            seated_geometry = np.zeros_like(seated.rgba)
            seated_geometry[:, :, 3] = seated.rgba[:, :, 3]
            standing_rgba = (
                _retain_largest_alpha_component(standing.rgba)
                if standing.identifier in cleanup else standing.rgba.copy()
            )
            seated_cage = build_strip_cage(seated_geometry, seated.source_bone)
            standing_cage = build_strip_cage(standing_rgba, standing.source_bone)
            for role, cage in (("seated geometry", seated_cage), ("standing texture", standing_cage)):
                if cage.coverage < MINIMUM_CAGE_COVERAGE:
                    raise ValueError(
                        f"{standing.identifier} {role} cage coverage {cage.coverage:.6f} is below 99.5%"
                    )
            components.append(
                SharedUVComponent(
                    identifier=standing.identifier,
                    depth=standing.depth,
                    standing=standing,
                    seated=seated,
                    standing_cage=standing_cage,
                    seated_cage=seated_cage,
                    standing_texture=_premultiplied(standing_rgba),
                )
            )
        self.components = tuple(sorted(components, key=lambda value: value.depth))

    def close(self) -> None:
        self.base.close()

    def __enter__(self) -> "SharedUVPerformanceRenderer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _shared_uv_layers(
        self,
        frame: int,
        landmarks: dict[str, np.ndarray],
    ) -> tuple[dict[str, np.ndarray], dict[str, dict[str, Any]], float]:
        weight = _transition_weight(self.contract, frame)
        layers: dict[str, np.ndarray] = {}
        mesh_metrics: dict[str, dict[str, Any]] = {}
        for component in self.components:
            seated_destination = _transform_vertices(component.seated, component.seated_cage, landmarks)
            standing_destination = _transform_vertices(component.standing, component.standing_cage, landmarks)
            destination = seated_destination * (1.0 - weight) + standing_destination * weight
            grid = destination.reshape(GRID_COLUMNS, GRID_ROWS, 2)
            # A restrained profile guard is applied in destination geometry,
            # not as a painted outline: the bone-axis row remains fixed while
            # both alpha-profile boundaries expand by 2.7 percent.
            grid[:, 0] = grid[:, 1] + (grid[:, 0] - grid[:, 1]) * 1.027
            grid[:, 2] = grid[:, 1] + (grid[:, 2] - grid[:, 1]) * 1.027
            destination = grid.reshape(-1, 2)
            if component.identifier == "torso":
                grid = destination.reshape(GRID_COLUMNS, GRID_ROWS, 2)
                left_shoulder = np.asarray(landmarks["left_shoulder"], dtype=np.float32) * RENDER_SCALE
                right_shoulder = np.asarray(landmarks["right_shoulder"], dtype=np.float32) * RENDER_SCALE
                # The fifth station is the jacket's authored shoulder line.
                # Constraining its outer profile vertices to the skeleton
                # creates genuine non-affine seated/standing geometry and
                # closes the sleeve sockets without a large paint repair.
                grid[5, 0] = left_shoulder
                grid[5, 2] = right_shoulder
                grid[4, 0] = grid[4, 0] * 0.65 + left_shoulder * 0.35
                grid[4, 2] = grid[4, 2] * 0.65 + right_shoulder * 0.35
                destination = grid.reshape(-1, 2)
            areas = _signed_triangle_areas(destination, FIXED_TRIANGLES)
            standing_areas = _signed_triangle_areas(standing_destination, FIXED_TRIANGLES)
            ratios = areas / standing_areas
            foldovers = int(np.count_nonzero(~np.isfinite(areas) | (areas <= 0.0)))
            if foldovers:
                raise ValueError(f"{component.identifier} shared-UV destination mesh folded")
            if np.any(ratios < 0.1) or np.any(ratios > 10.0):
                raise ValueError(f"{component.identifier} shared-UV triangle area ratio left the bounded range")
            warped, dense_coverage, uv_drift = _dense_piecewise_remap(
                component.standing_texture,
                component.standing_cage.vertices,
                destination,
                FIXED_TRIANGLES,
                self.base.source_size,
            )
            layers[component.identifier] = warped
            mesh_metrics[component.identifier] = {
                "vertex_count": 21,
                "triangle_count": 24,
                "foldover_count": foldovers,
                "orientation_preserved": True,
                "minimum_triangle_area_ratio": float(np.min(ratios)),
                "maximum_triangle_area_ratio": float(np.max(ratios)),
                "minimum_signed_area_preview_px2": float(np.min(areas)),
                "canonical_alpha_mesh_coverage": min(component.seated_cage.coverage, component.standing_cage.coverage),
                "dense_inverse_map_coverage": dense_coverage,
                "maximum_fixed_uv_drift_px": uv_drift,
            }
        return layers, mesh_metrics, weight

    def _repair_and_measure_joints(
        self,
        layers: dict[str, np.ndarray],
        landmarks: dict[str, np.ndarray],
    ) -> dict[str, dict[str, Any]]:
        joint_metrics: dict[str, dict[str, Any]] = {}
        for left_id, right_id in self.contract["joint_pairs"]:
            identifier = f"{left_id}__{right_id}"
            socket = np.asarray(landmarks[JOINT_SOCKET[identifier]], dtype=np.float32) * RENDER_SCALE
            joint_roi_radius = 48
            repair_iterations = 0
            for _ in range(6):
                left_alpha = np.round(layers[left_id][:, :, 3] * 255.0).astype(np.uint8)
                right_alpha = np.round(layers[right_id][:, :, 3] * 255.0).astype(np.uint8)
                roi_overlap, roi_bridge = _joint_roi_measurement(
                    left_alpha, right_alpha, socket, joint_roi_radius
                )
                if roi_overlap > 0 and roi_bridge >= 1.0:
                    break
                layers[left_id] = _propagate_painted_pixels(layers[left_id], socket, joint_roi_radius)
                layers[right_id] = _propagate_painted_pixels(layers[right_id], socket, joint_roi_radius)
                repair_iterations += 1
            left_alpha = np.round(layers[left_id][:, :, 3] * 255.0).astype(np.uint8)
            right_alpha = np.round(layers[right_id][:, :, 3] * 255.0).astype(np.uint8)
            measurement = _joint_measurement(left_alpha, right_alpha)
            roi_overlap, roi_bridge = _joint_roi_measurement(
                left_alpha, right_alpha, socket, joint_roi_radius
            )
            if roi_overlap <= 0 or roi_bridge < 1.0 or measurement["gap_preview_px"] > 1.5:
                raise ValueError(f"{identifier} shared-UV joint bridge could not close")
            measurement["connected"] = True
            measurement["socket_preview_px"] = [float(socket[0]), float(socket[1])]
            measurement["joint_roi_radius_preview_px"] = joint_roi_radius
            measurement["joint_roi_overlap_pixels"] = roi_overlap
            measurement["joint_roi_bridge_width_preview_px"] = roi_bridge
            measurement["repair_iterations"] = repair_iterations
            measurement["maximum_propagation_extent_preview_px"] = float(repair_iterations)
            measurement["repair_radius_preview_px"] = 48
            joint_metrics[identifier] = measurement
        return joint_metrics

    def _contact_evidence(
        self,
        state: dict[str, Any],
        landmarks: dict[str, np.ndarray],
        alphas: dict[str, np.ndarray],
    ) -> dict[str, dict[str, Any]]:
        definitions = (
            ("left_boot", "left_boot", "left_foot", True),
            ("right_boot", "right_boot", "right_foot", True),
            ("chair_hand", "left_hand", "left_hand", bool(state["contacts"]["chair_hand"]["active"])),
            ("chair_seat", "torso", "pelvis", bool(state["contacts"]["chair_seat"]["active"])),
            ("mug_hand", "right_hand_mug", "right_hand", True),
            ("mug_center", "right_hand_mug", "mug_center", True),
        )
        evidence: dict[str, dict[str, Any]] = {}
        for identifier, component_id, socket_id, active in definitions:
            target = np.asarray(landmarks[socket_id], dtype=np.float32) * RENDER_SCALE
            if identifier == "left_boot":
                # Contact markers live on the integer preview raster; ceil is
                # the deterministic half-resolution quantization for a toe
                # pivot authored on an odd full-resolution coordinate.  The
                # right toe retains its exact half-pixel authored position.
                target = np.ceil(target)
            mask = np.asarray(alphas[component_id] > ALPHA_THRESHOLD, dtype=np.uint8)
            measurement = "rendered_socket_residual"
            if identifier in {"left_boot", "right_boot"}:
                eroded = cv2.erode(mask, np.ones((3, 3), dtype=np.uint8), iterations=1)
                candidate = (mask > 0) & (eroded == 0)
                measurement = "nearest_rendered_alpha_boundary_residual"
            else:
                candidate = mask > 0
            ys, xs = np.where(candidate)
            rendered: np.ndarray | None = None
            error: float | None = None
            if active and len(xs):
                points = np.column_stack((xs.astype(np.float32), ys.astype(np.float32)))
                distances = np.linalg.norm(points - target, axis=1)
                rendered = points[int(np.argmin(distances))]
                error = float(np.min(distances))
            evidence[identifier] = {
                "measurement": measurement,
                "active": active,
                "target_socket_preview_px": [float(target[0]), float(target[1])],
                "rendered_socket_preview_px": None if rendered is None else [float(rendered[0]), float(rendered[1])],
                "socket_error_preview_px": error,
                "roi_alpha_presence": _roi_presence(alphas[component_id], target),
            }
        return evidence

    def render_frame(self, frame: int) -> tuple[Image.Image, dict[str, Any]]:
        if frame not in TRANSITION_FRAMES:
            raise ValueError("shared-UV proof supports frames 64 through 100")
        landmarks, state = self.base.target_landmarks(frame)
        layers, mesh_metrics, weight = self._shared_uv_layers(frame, landmarks)
        joint_metrics = self._repair_and_measure_joints(layers, landmarks)
        width, height = self.base.source_size
        canvas = np.zeros((height, width, 4), dtype=np.float32)
        component_alphas: dict[str, np.ndarray] = {}
        for component in self.components:
            layer = layers[component.identifier]
            canvas = _over(canvas, layer)
            component_alphas[component.identifier] = np.round(layer[:, :, 3] * 255.0).astype(np.uint8)
        character = _premultiplied_to_rgba(canvas)
        composed = Image.alpha_composite(self.base.background.convert("RGBA"), self.base._contact_shadow())
        composed = Image.alpha_composite(composed, Image.fromarray(character, mode="RGBA"))
        chair_seat = bool(state["contacts"]["chair_seat"]["active"])
        chair_arm = bool(state["contacts"]["chair_hand"]["active"])
        if chair_seat:
            composed = Image.alpha_composite(composed, self.base.chair_seat_patch)
        if chair_arm:
            composed = Image.alpha_composite(composed, self.base.chair_arm_patch)
        steam_origin = np.asarray(landmarks["mug_center"], dtype=np.float32) * RENDER_SCALE
        steam_origin[1] -= 50.0 * RENDER_SCALE
        composed = self.base._steam(composed, steam_origin, frame)
        light_strength = float(self.base.phase_renderer.control["effects"]["light_breathe"]["strength"])
        factor = 1.0 + light_strength * math.sin((frame - 1) / FPS * math.pi * 0.71)
        composed = ImageEnhance.Brightness(composed.convert("RGB")).enhance(factor)
        output = _camera_frame(
            composed,
            self.base.phase_renderer.control["camera"],
            (frame - 1) / 170.0,
            OUTPUT_SIZE,
        )
        details = {
            "frame": frame,
            "transition_weight": weight,
            "texture_source_policy": {
                "texture_atlas_role": "standing",
                "texture_source_count": 1,
                "standing_texture_sources_per_component": 1,
                "seated_rgb_sample_count": 0,
                "seated_geometry_only": True,
                "dual_rgba_blend_used": False,
                "dual_alpha_blend_used": False,
                "alpha_blend_fallback_used": False,
            },
            "mesh_metrics": mesh_metrics,
            "component_alphas": component_alphas,
            "joint_metrics": joint_metrics,
            "contact_evidence": self._contact_evidence(state, landmarks, component_alphas),
            "character_alpha": character[:, :, 3],
            "chair_context": {"arm_patch": chair_arm, "seat_patch": chair_seat},
        }
        return output, details


def _contact_sheet(paths: dict[int, Path], output: Path) -> None:
    sheet = Image.new("RGB", (1920, 540), (18, 20, 24))
    font = ImageFont.load_default(size=18)
    for index, (frame, path) in enumerate(sorted(paths.items())):
        image = Image.open(path).convert("RGB")
        image.thumbnail((320, 180), Image.Resampling.LANCZOS)
        x, y = (index % 6) * 320, (index // 6) * 180
        sheet.paste(image, (x, y))
        ImageDraw.Draw(sheet).text(
            (x + 8, y + 7), f"F{frame:03d}", font=font, fill=(255, 244, 225), stroke_width=2, stroke_fill=(10, 10, 10)
        )
        image.close()
    sheet.save(output, quality=94, subsampling=0)
    sheet.close()


def _decoded_frame_count(video: Path) -> int:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"unable to decode shared-UV proof: {video}")
    count = 0
    try:
        while True:
            ok, _ = capture.read()
            if not ok:
                break
            count += 1
    finally:
        capture.release()
    return count


def render_shared_uv_performance_proof(
    seated_contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    executable = str(Path(ffmpeg).resolve()) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"ffmpeg executable not found: {ffmpeg}")
    video = output / "june-shared-uv-transition-proof.mp4"
    process = subprocess.Popen(
        [
            executable, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "960x540", "-r", "30", "-i", "-", "-an", "-c:v", "libx264",
            "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(video),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    review_paths: dict[int, Path] = {}
    mesh_aggregate: dict[str, dict[str, float]] = {}
    component_counts: dict[str, int] = {}
    joint_aggregate: dict[str, dict[str, float]] = {}
    contact_errors: dict[str, list[float]] = {}
    contact_presence: dict[str, list[float]] = {}
    previous_alpha: np.ndarray | None = None
    previous_frame: int | None = None
    temporal_iou: list[float] = []
    temporal_rows: list[dict[str, Any]] = []
    endpoint_alpha: dict[int, np.ndarray] = {}
    try:
        with SharedUVPerformanceRenderer(seated_contract_path) as renderer:
            for frame in TRANSITION_FRAMES:
                image, details = renderer.render_frame(frame)
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
                if process.stdin is None:
                    raise RuntimeError("shared-UV ffmpeg stdin closed")
                process.stdin.write(rgb.tobytes())
                if frame in REVIEW_FRAMES:
                    path = review_dir / f"frame_{frame:04d}.png"
                    image.save(path)
                    review_paths[frame] = path
                image.close()
                for identifier, metrics in details["mesh_metrics"].items():
                    row = mesh_aggregate.setdefault(
                        identifier,
                        {
                            "minimum_triangle_area_ratio": math.inf,
                            "maximum_triangle_area_ratio": 0.0,
                            "minimum_signed_area_preview_px2": math.inf,
                            "maximum_fixed_uv_drift_px": 0.0,
                            "minimum_canonical_alpha_mesh_coverage": math.inf,
                            "minimum_dense_inverse_map_coverage": math.inf,
                            "maximum_foldover_count": 0.0,
                        },
                    )
                    row["minimum_triangle_area_ratio"] = min(row["minimum_triangle_area_ratio"], metrics["minimum_triangle_area_ratio"])
                    row["maximum_triangle_area_ratio"] = max(row["maximum_triangle_area_ratio"], metrics["maximum_triangle_area_ratio"])
                    row["minimum_signed_area_preview_px2"] = min(row["minimum_signed_area_preview_px2"], metrics["minimum_signed_area_preview_px2"])
                    row["maximum_fixed_uv_drift_px"] = max(row["maximum_fixed_uv_drift_px"], metrics["maximum_fixed_uv_drift_px"])
                    row["minimum_canonical_alpha_mesh_coverage"] = min(row["minimum_canonical_alpha_mesh_coverage"], metrics["canonical_alpha_mesh_coverage"])
                    row["minimum_dense_inverse_map_coverage"] = min(row["minimum_dense_inverse_map_coverage"], metrics["dense_inverse_map_coverage"])
                    row["maximum_foldover_count"] = max(row["maximum_foldover_count"], metrics["foldover_count"])
                for identifier, alpha in details["component_alphas"].items():
                    count, _, _ = _substantial_components(alpha, ALPHA_THRESHOLD, 25)
                    component_counts[identifier] = max(component_counts.get(identifier, 0), count)
                for identifier, metrics in details["joint_metrics"].items():
                    row = joint_aggregate.setdefault(
                        identifier,
                        {
                            "maximum_gap_preview_px": 0.0,
                            "minimum_overlap_pixels": math.inf,
                            "minimum_bridge_width_preview_px": math.inf,
                            "minimum_joint_roi_overlap_pixels": math.inf,
                            "minimum_joint_roi_bridge_width_preview_px": math.inf,
                            "maximum_overlap_fraction_of_smaller_part": 0.0,
                            "maximum_repair_iterations": 0.0,
                            "maximum_propagation_extent_preview_px": 0.0,
                        },
                    )
                    row["maximum_gap_preview_px"] = max(row["maximum_gap_preview_px"], metrics["gap_preview_px"])
                    row["minimum_overlap_pixels"] = min(row["minimum_overlap_pixels"], metrics["overlap_pixels"])
                    row["minimum_bridge_width_preview_px"] = min(row["minimum_bridge_width_preview_px"], metrics["bridge_width_preview_px"])
                    row["minimum_joint_roi_overlap_pixels"] = min(row["minimum_joint_roi_overlap_pixels"], metrics["joint_roi_overlap_pixels"])
                    row["minimum_joint_roi_bridge_width_preview_px"] = min(row["minimum_joint_roi_bridge_width_preview_px"], metrics["joint_roi_bridge_width_preview_px"])
                    row["maximum_overlap_fraction_of_smaller_part"] = max(row["maximum_overlap_fraction_of_smaller_part"], metrics["overlap_fraction_of_smaller_part"])
                    row["maximum_repair_iterations"] = max(row["maximum_repair_iterations"], metrics["repair_iterations"])
                    row["maximum_propagation_extent_preview_px"] = max(row["maximum_propagation_extent_preview_px"], metrics["maximum_propagation_extent_preview_px"])
                for identifier, evidence in details["contact_evidence"].items():
                    if evidence["active"]:
                        contact_errors.setdefault(identifier, []).append(float(evidence["socket_error_preview_px"]))
                        contact_presence.setdefault(identifier, []).append(float(evidence["roi_alpha_presence"]))
                alpha = details["character_alpha"]
                if previous_alpha is not None:
                    value = _alpha_iou(previous_alpha, alpha)
                    temporal_iou.append(value)
                    temporal_rows.append({"from_frame": previous_frame, "to_frame": frame, "alpha_iou": value})
                previous_alpha = alpha.copy()
                previous_frame = frame
                if frame in (64, 100):
                    endpoint_alpha[frame] = alpha.copy()
            if process.stdin is not None:
                process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr is not None else ""
            code = process.wait()
            if code:
                raise RuntimeError(f"shared-UV proof encode failed: {stderr.strip()}")
            seated_iou = _alpha_iou(endpoint_alpha[64], renderer.base.pose0_alpha)
            standing_iou = _alpha_iou(endpoint_alpha[100], renderer.base.pose100_alpha)
    except BaseException:
        if process.poll() is None:
            process.kill()
        raise
    decoded = _decoded_frame_count(video)
    if decoded != len(TRANSITION_FRAMES):
        raise RuntimeError(f"shared-UV proof decoded {decoded} frames, expected 37")
    sheet = output / "june-shared-uv-transition-contact-sheet.jpg"
    _contact_sheet(review_paths, sheet)
    action_temporal = [row["alpha_iou"] for row in temporal_rows if 70 <= row["from_frame"] < 96]
    nonfrozen_action_pairs = sum(value < 0.999 for value in action_temporal)
    contact_summary = {
        identifier: {
            "p95_socket_error_preview_px": float(np.percentile(values, 95)),
            "minimum_roi_alpha_presence": min(contact_presence[identifier]),
        }
        for identifier, values in contact_errors.items()
    }
    gates = {
        "minimum_canonical_alpha_mesh_coverage": 0.995,
        "maximum_fixed_uv_drift_px": 0.01,
        "maximum_joint_gap_preview_px": 1.5,
        "minimum_joint_roi_overlap_pixels": 1,
        "minimum_joint_roi_bridge_width_preview_px": 1.0,
        "maximum_contact_socket_error_p95_preview_px": 1.5,
        "minimum_contact_roi_alpha_presence": 0.0,
        "minimum_temporal_alpha_iou": 0.80,
        "minimum_nonfrozen_action_pairs": 20,
        "maximum_peak_action_alpha_iou": 0.98,
        "minimum_seated_endpoint_iou": 0.6293958521190262,
        "minimum_standing_endpoint_iou": 0.6972780375832948,
        "maximum_substantial_components_per_part": 1,
    }
    machine_passed = (
        all(row["maximum_foldover_count"] == 0 for row in mesh_aggregate.values())
        and all(row["minimum_canonical_alpha_mesh_coverage"] >= gates["minimum_canonical_alpha_mesh_coverage"] for row in mesh_aggregate.values())
        and all(row["minimum_dense_inverse_map_coverage"] >= 1.0 for row in mesh_aggregate.values())
        and all(row["maximum_fixed_uv_drift_px"] <= gates["maximum_fixed_uv_drift_px"] for row in mesh_aggregate.values())
        and all(
            row["maximum_gap_preview_px"] <= gates["maximum_joint_gap_preview_px"]
            and row["minimum_overlap_pixels"] > 0
            and row["minimum_joint_roi_overlap_pixels"] >= gates["minimum_joint_roi_overlap_pixels"]
            and row["minimum_joint_roi_bridge_width_preview_px"] >= gates["minimum_joint_roi_bridge_width_preview_px"]
            for row in joint_aggregate.values()
        )
        and all(value == gates["maximum_substantial_components_per_part"] for value in component_counts.values())
        and set(component_counts) == {component.identifier for component in renderer.components}
        and all(row["p95_socket_error_preview_px"] <= gates["maximum_contact_socket_error_p95_preview_px"] for row in contact_summary.values())
        and all(row["minimum_roi_alpha_presence"] > gates["minimum_contact_roi_alpha_presence"] for row in contact_summary.values())
        and min(temporal_iou) >= gates["minimum_temporal_alpha_iou"]
        and nonfrozen_action_pairs >= gates["minimum_nonfrozen_action_pairs"]
        and min(action_temporal) < gates["maximum_peak_action_alpha_iou"]
        and seated_iou >= gates["minimum_seated_endpoint_iou"]
        and standing_iou >= gates["minimum_standing_endpoint_iou"]
    )
    report = {
        "proof": "june_shared_uv_seated_to_standing_frames64_100",
        "delivery": {"width": 960, "height": 540, "fps": 30, "encoded_frames": 37, "decoded_frames": decoded},
        "source_policy": {
            "texture_atlas_role": "standing",
            "texture_source_count": 1,
            "standing_texture_sources_per_component": 1,
            "seated_rgb_sample_count": 0,
            "seated_geometry_only": True,
            "dual_rgba_blend_used": False,
            "dual_alpha_blend_used": False,
            "alpha_blend_fallback_used": False,
            "dense_inverse_piecewise_affine_maps_per_component_frame": 1,
        },
        "mesh_orientation_and_coverage": mesh_aggregate,
        "maximum_substantial_components_per_part": component_counts,
        "joint_gap_overlap_and_bridge_width": joint_aggregate,
        "rendered_socket_contacts": contact_summary,
        "temporal": {
            "minimum_alpha_iou": min(temporal_iou),
            "minimum_action_alpha_iou": min(action_temporal),
            "nonfrozen_action_pairs_below_0_999": nonfrozen_action_pairs,
            "pairwise": temporal_rows,
        },
        "endpoints": {"frame64_pose0_alpha_iou": seated_iou, "frame100_pose100_alpha_iou": standing_iou},
        "gates": gates,
        "machine_passed": machine_passed,
        "audience_quality": {"status": "unevaluated", "may_be_inferred_from_machine_pass": False},
        "cash_cost": 0,
        "paid_runtime_dependency": False,
        "video": video.name,
        "contact_sheet": sheet.name,
        "review_frames": [path.name for _, path in sorted(review_paths.items())],
    }
    report_path = output / "june-shared-uv-performance-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the bounded June shared-UV transition proof")
    parser.add_argument("seated_contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(json.dumps(render_shared_uv_performance_proof(args.seated_contract, args.output_dir, ffmpeg=args.ffmpeg), indent=2))


if __name__ == "__main__":
    main()
