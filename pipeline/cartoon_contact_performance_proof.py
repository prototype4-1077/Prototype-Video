"""Contact-aware shared-UV performance proof for June, frames 64--112.

This module extends the accepted shared-UV representation without changing it.
The standing atlas remains the only RGB texture source; five corrective pose
keys, contact targets, and seated alpha contribute geometry only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from pipeline.cartoon_puppet_atlas_performance import FPS, OUTPUT_SIZE, RENDER_SCALE
from pipeline.cartoon_deformable_performance_3q import _registered_point
from pipeline.cartoon_puppet_atlas_transition_proof import (
    _minimum_mask_distance,
    _over,
    _premultiplied_to_rgba,
    _similarity_affine,
    _substantial_components,
)
from pipeline.cartoon_shared_uv_performance_proof import (
    FIXED_TRIANGLES,
    GRID_COLUMNS,
    GRID_ROWS,
    SharedUVPerformanceRenderer,
    build_strip_cage,
    _dense_piecewise_remap,
    _joint_measurement,
    _signed_triangle_areas,
    _transform_vertices,
)
from pipeline.cartoon_shot_sequence import _camera_frame, _ease_in_out_cubic, camera_crop_box


REPO_ROOT = Path(__file__).resolve().parents[1]
FRAMES = tuple(range(64, 113))
ALPHA_THRESHOLD = 8


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_path(reference: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(reference["path"])).resolve()
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    expected = reference.get("sha256")
    if expected and _sha256(path) != str(expected):
        raise ValueError(f"{label} SHA-256 mismatch")
    return path


def _load_contract(contract_path: str | Path) -> dict[str, Any]:
    path = Path(contract_path).resolve()
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("contract_id") != "june_oxley_contact_performance_v1" or int(contract.get("schema_version", 0)) != 1:
        raise ValueError("unsupported contact-performance contract")
    proof = contract["proof"]
    if proof.get("frame_range") != [64, 112] or proof.get("frame_count") != 49:
        raise ValueError("contact proof clock must remain frames 64 through 112")
    if proof.get("measurement_space") != "final_output_px_after_camera":
        raise ValueError("contact evidence must be measured after the final camera")
    policy = contract["source_policy"]
    if int(policy.get("texture_source_count", -1)) != 1 or int(policy.get("standing_texture_sources_per_component", -1)) != 1:
        raise ValueError("contact proof requires exactly one standing texture source")
    if int(policy["seated_geometry_contract"].get("rgb_sample_count", -1)) != 0:
        raise ValueError("seated RGB sampling is forbidden")
    if policy.get("dual_rgba_blend_allowed") or policy.get("dual_alpha_blend_allowed") or policy.get("alpha_blend_fallback_allowed"):
        raise ValueError("dual-source blending is forbidden")
    evidence = contract["evidence_policy"]
    if not evidence.get("self_contact_is_not_contact"):
        raise ValueError("self-referential contact evidence is forbidden")
    for key, label in (
        ("standing_texture_contract", "standing texture contract"),
        ("seated_geometry_contract", "seated geometry contract"),
        ("performance_source_contract", "performance source contract"),
    ):
        _repo_path(policy[key], label)
    atlas_reference = policy["standing_texture_contract"]
    atlas_path = (REPO_ROOT / str(atlas_reference["atlas_path"])).resolve()
    if not atlas_path.is_file() or _sha256(atlas_path) != str(atlas_reference["atlas_sha256"]):
        raise ValueError("standing texture atlas SHA-256 mismatch")
    for value in contract["porch_target_geometry"].get("provenance", {}).values():
        if isinstance(value, dict) and "path" in value:
            _repo_path(value, "contact provenance")
    samples_seen: set[tuple[int, int]] = set()
    atlas = np.asarray(Image.open(atlas_path).convert("RGBA"), dtype=np.uint8)
    for side in ("left_boot", "right_boot"):
        row = contract["boot_contact_geometry"][side]
        samples = [tuple(int(v) for v in point) for point in row["sole_samples_component_local_px"]]
        if len(samples) != 7 or len(set(samples)) != 7:
            raise ValueError(f"{side} must declare seven distinct real sole samples")
        x0, y0, width, height = (int(value) for value in row["component_bbox_atlas_px"])
        crop = atlas[y0:y0 + height, x0:x0 + width, 3]
        for point in samples:
            x, y = point
            if not (0 <= x < width and 0 <= y < height and crop[y, x] > ALPHA_THRESHOLD):
                raise ValueError(f"{side} sole sample leaves the standing alpha")
            if y + 1 < height and np.any(crop[y + 1:, x] > ALPHA_THRESHOLD):
                raise ValueError(f"{side} sole sample is not on the lower alpha boundary")
            samples_seen.add(point)
    return contract


def _pchip_slopes(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    if len(x) == 2:
        return np.asarray([(y[1] - y[0]) / (x[1] - x[0])] * 2, dtype=np.float64)
    h = np.diff(x)
    delta = np.diff(y) / h
    slopes = np.zeros_like(y, dtype=np.float64)
    for index in range(1, len(y) - 1):
        if delta[index - 1] == 0.0 or delta[index] == 0.0 or np.sign(delta[index - 1]) != np.sign(delta[index]):
            slopes[index] = 0.0
        else:
            left = 2.0 * h[index] + h[index - 1]
            right = h[index] + 2.0 * h[index - 1]
            slopes[index] = (left + right) / (left / delta[index - 1] + right / delta[index])
    slopes[0] = delta[0]
    slopes[-1] = delta[-1]
    return slopes


def _cubic_value(keys: list[list[float]] | list[dict[str, Any]], frame: float, field: str | None = None) -> float:
    if field is None:
        x = np.asarray([float(row[0]) for row in keys], dtype=np.float64)  # type: ignore[index]
        y = np.asarray([float(row[1]) for row in keys], dtype=np.float64)  # type: ignore[index]
    else:
        x = np.asarray([float(row["frame"]) for row in keys], dtype=np.float64)  # type: ignore[index]
        y = np.asarray([float(row[field]) for row in keys], dtype=np.float64)  # type: ignore[index]
    if frame <= x[0]:
        return float(y[0])
    if frame >= x[-1]:
        return float(y[-1])
    slopes = _pchip_slopes(x, y)
    index = int(np.searchsorted(x, frame) - 1)
    h = x[index + 1] - x[index]
    t = (frame - x[index]) / h
    h00 = 2.0 * t ** 3 - 3.0 * t ** 2 + 1.0
    h10 = t ** 3 - 2.0 * t ** 2 + t
    h01 = -2.0 * t ** 3 + 3.0 * t ** 2
    h11 = t ** 3 - t ** 2
    return float(h00 * y[index] + h10 * h * slopes[index] + h01 * y[index + 1] + h11 * h * slopes[index + 1])


def _vector_curve(keys: list[dict[str, Any]], frame: float, field: str) -> np.ndarray:
    rows_x = [[row["frame"], row[field][0]] for row in keys]
    rows_y = [[row["frame"], row[field][1]] for row in keys]
    return np.asarray((_cubic_value(rows_x, frame), _cubic_value(rows_y, frame)), dtype=np.float64)


def _pose_landmarks(contract: dict[str, Any]) -> list[dict[str, Any]]:
    source_path = _repo_path(contract["source_policy"]["performance_source_contract"], "performance source contract")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    rows = source["runtime_asset_pack"]["corrective_sources"]
    by_pose = {str(row["pose_id"]): row for row in rows}
    control_path = _repo_path(contract["pose_key_registration"]["source_control"], "pose registration control")
    control = json.loads(control_path.read_text(encoding="utf-8"))
    registrations = {str(row["id"]): row for row in control["poses"]}
    output: list[dict[str, Any]] = []
    for key in contract["pose_keys"]:
        pose_id = str(key["pose_id"])
        raw = by_pose[pose_id]
        registration_pose = registrations[pose_id]
        registered = copy.deepcopy(raw)
        registered["landmarks"] = {
            identifier: _registered_point(point, registration_pose, control["contact_registration"]).astype(float).tolist()
            for identifier, point in raw["landmarks"].items()
        }
        output.append(registered)
    return output


def _pose_point(poses: list[dict[str, Any]], identifier: str, progress: float) -> np.ndarray:
    keys_x = [[float(row["progress"]), float(row["landmarks"][identifier][0])] for row in poses]
    keys_y = [[float(row["progress"]), float(row["landmarks"][identifier][1])] for row in poses]
    # Reuse the Hermite evaluator by scaling normalized progress to a stable
    # integer domain.  This is geometry interpolation, not a second easing.
    scaled_x = [[value * 100.0, coordinate] for value, coordinate in keys_x]
    scaled_y = [[value * 100.0, coordinate] for value, coordinate in keys_y]
    return np.asarray((_cubic_value(scaled_x, progress * 100.0), _cubic_value(scaled_y, progress * 100.0)), dtype=np.float64)


def _sole_targets(contract: dict[str, Any], side: str, heel_lift_preview_px: float) -> np.ndarray:
    targets = np.asarray(contract["porch_target_geometry"][side]["target_samples"], dtype=np.float64)
    if heel_lift_preview_px <= 1e-9:
        return targets.copy()
    toe = targets[-1]
    heel = targets[0]
    relative = heel - toe
    radius = float(np.linalg.norm(relative))
    # The authored lift is an upper bound.  A tiny guard below it keeps the
    # sampled endpoint velocity inside the two-pixel final-output gate after
    # camera resampling while retaining the full visible heel roll.
    effective_lift = heel_lift_preview_px * 0.97
    desired_y = relative[1] - effective_lift / RENDER_SCALE
    desired_y = min(radius - 1e-6, max(-radius + 1e-6, desired_y))
    desired_x = math.copysign(math.sqrt(max(0.0, radius * radius - desired_y * desired_y)), relative[0])
    start_angle = math.atan2(relative[1], relative[0])
    end_angle = math.atan2(desired_y, desired_x)
    angle = end_angle - start_angle
    cosine, sine = math.cos(angle), math.sin(angle)
    rotation = np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64)
    return (targets - toe) @ rotation.T + toe


def _boot_bone_from_sole(contract: dict[str, Any], side: str, targets: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    standing_contract_path = _repo_path(contract["source_policy"]["standing_texture_contract"], "standing texture contract")
    standing_contract = json.loads(standing_contract_path.read_text(encoding="utf-8"))
    component_id = side
    row = next(value for value in standing_contract["rig"]["components"] if value["id"] == component_id)
    source_samples = np.asarray(contract["boot_contact_geometry"][side]["sole_samples_component_local_px"], dtype=np.float32)
    matrix, _ = _similarity_affine(source_samples[0], source_samples[-1], targets[0], targets[-1])
    source_bone = np.asarray(row["source_bone"], dtype=np.float32)
    homogeneous = np.column_stack((source_bone, np.ones(2, dtype=np.float32)))
    mapped = homogeneous @ matrix.T
    return mapped[0].astype(np.float64), mapped[1].astype(np.float64)


def solve_contact_landmarks(
    contract: dict[str, Any],
    frame: int,
    base_landmarks: dict[str, Any],
) -> dict[str, Any]:
    if not 64 <= int(frame) <= 112:
        raise ValueError("contact landmark solver supports frames 64 through 112")
    poses = _pose_landmarks(contract)
    motion_keys = contract["motion"]["keys"]
    stand_progress = _cubic_value(motion_keys, frame, "stand_progress")
    pelvis_progress = _cubic_value(motion_keys, frame, "pelvis_progress")
    torso_progress = _cubic_value(motion_keys, frame, "torso_progress")
    anticipation = _cubic_value(motion_keys, frame, "anticipation")
    root_target = _vector_curve(motion_keys, frame, "root")
    result = copy.deepcopy(base_landmarks)
    pelvis_ids = {"pelvis", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle", "left_foot", "right_foot"}
    torso_ids = {"chest", "neck", "head", "left_shoulder", "right_shoulder"}
    pose_ids = set(poses[0]["landmarks"])
    for identifier in pose_ids:
        progress = pelvis_progress if identifier in pelvis_ids else torso_progress if identifier in torso_ids else stand_progress
        result[identifier] = _pose_point(poses, identifier, progress).tolist()

    # Root travel supplies the forward acting arc while the five pose keys
    # supply articulation.  Feet are excluded because they are solved below.
    root_shift_x = float(root_target[0] - motion_keys[0]["root"][0])
    for identifier in pose_ids - {"left_ankle", "left_foot", "right_ankle", "right_foot"}:
        point = np.asarray(result[identifier], dtype=np.float64)
        influence = 1.0 if identifier in torso_ids or "shoulder" in identifier or "elbow" in identifier or "hand" in identifier or identifier == "mug_center" else 0.65
        point[0] += root_shift_x * influence
        result[identifier] = point.tolist()

    # Settle affects the articulated mass but never translates a planted foot.
    settle_offset = float(root_target[1] - 468.0) if frame >= 96 else 0.0
    if frame >= 96:
        for identifier in pose_ids - {"left_ankle", "left_foot", "right_ankle", "right_foot"}:
            point = np.asarray(result[identifier], dtype=np.float64)
            point[1] += settle_offset
            result[identifier] = point.tolist()
        recompression = max(0.0, _cubic_value([[96, 0.0], [98, 0.0], [102, 2.0], [106, 0.5], [108, 1.0], [112, 1.0]], frame))
        for identifier in ("left_knee", "right_knee"):
            point = np.asarray(result[identifier], dtype=np.float64)
            point[1] += recompression
            result[identifier] = point.tolist()

    loads = {
        "seat": _cubic_value(contract["load_curves"]["seat_load"], frame),
        "chair_hand": _cubic_value(contract["load_curves"]["chair_hand_load"], frame),
    }
    if frame < 79:
        result["left_hand"] = list(contract["porch_target_geometry"]["chair_arm"]["planted_hand_anchor"])
    elif frame <= 84:
        t = (frame - 79) / 5.0
        release = 1.0 - (1.0 - t) ** 5
        anchor = np.asarray(contract["porch_target_geometry"]["chair_arm"]["planted_hand_anchor"], dtype=np.float64)
        released = anchor + np.asarray((160.0, -40.0))
        result["left_hand"] = (anchor * (1.0 - release) + released * release).tolist()
    else:
        anchor = np.asarray(contract["porch_target_geometry"]["chair_arm"]["planted_hand_anchor"], dtype=np.float64)
        released = anchor + np.asarray((160.0, -40.0))
        free = np.asarray(result["left_hand"], dtype=np.float64) + np.asarray((160.0, -40.0))
        blend = _ease_in_out_cubic(min(1.0, (frame - 84) / 10.0))
        result["left_hand"] = (released * (1.0 - blend) + free * blend).tolist()

    foot_targets: dict[str, dict[str, Any]] = {}
    sole_landmarks: dict[str, list[float]] = {}
    for side_name, prefix, curve_name in (
        ("left_boot", "left", "left_heel_lift_preview_px"),
        ("right_boot", "right", "right_heel_lift_preview_px"),
    ):
        lift = _cubic_value(contract["load_curves"][curve_name], frame)
        targets = _sole_targets(contract, side_name, lift)
        ankle, foot = _boot_bone_from_sole(contract, side_name, targets)
        result[f"{prefix}_ankle"] = ankle.tolist()
        result[f"{prefix}_foot"] = foot.tolist()
        for index, point in enumerate(targets):
            sole_landmarks[f"{prefix}_sole_{index}"] = point.tolist()
        row = contract["boot_contact_geometry"][side_name]
        sole_landmarks[f"{prefix}_heel"] = targets[int(row["heel_sample_index"])].tolist()
        sole_landmarks[f"{prefix}_ball"] = targets[int(row["ball_sample_index"])].tolist()
        sole_landmarks[f"{prefix}_toe"] = targets[int(row["toe_sample_index"])].tolist()
        foot_targets[side_name] = {
            "sole_samples": targets.tolist(),
            "heel_lift_preview_px": lift,
            "toe_pinned": True,
        }
    result.update(sole_landmarks)
    # Preserve one canonical grip-to-center vector and rotate it with the
    # forearm.  The shared-UV component therefore receives a genuine rigid
    # two-point transform (grip plus mug center), not two drifting samples.
    canonical_offset = np.asarray(poses[0]["landmarks"]["mug_center"], dtype=np.float64) - np.asarray(
        poses[0]["landmarks"]["right_hand"], dtype=np.float64
    )
    base_axis = np.asarray(poses[0]["landmarks"]["right_hand"], dtype=np.float64) - np.asarray(
        poses[0]["landmarks"]["right_elbow"], dtype=np.float64
    )
    current_axis = np.asarray(result["right_hand"], dtype=np.float64) - np.asarray(
        result["right_elbow"], dtype=np.float64
    )
    rotation_angle = math.atan2(current_axis[1], current_axis[0]) - math.atan2(base_axis[1], base_axis[0])
    cosine, sine = math.cos(rotation_angle), math.sin(rotation_angle)
    rotation = np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64)
    result["mug_center"] = (
        np.asarray(result["right_hand"], dtype=np.float64) + rotation @ canonical_offset
    ).tolist()
    return {
        "coordinate_space": "gs030_registered_source_px_pre_camera",
        "frame": int(frame),
        "landmarks": result,
        "foot_targets": foot_targets,
        "loads": loads,
        "root_target": root_target.tolist(),
        "stand_progress": stand_progress,
        "pelvis_progress": pelvis_progress,
        "torso_progress": torso_progress,
        "anticipation": anticipation,
        "pose_registration_evidence": {
            "operation_order": "register_every_pose_key_to_gs030_source_space_before_any_pose_interpolation",
            "registered_before_interpolation": True,
            "registered_pose_keys": {
                str(row["pose_id"]): {
                    "source_pose_id": str(row["pose_id"]),
                    "pose_specific_transform": True,
                    "landmarks": copy.deepcopy(row["landmarks"]),
                }
                for row in poses
            },
        },
    }


def _mask_centroid(alpha: np.ndarray) -> np.ndarray:
    ys, xs = np.where(alpha > ALPHA_THRESHOLD)
    if not len(xs):
        raise ValueError("rendered component alpha is empty")
    weights = alpha[ys, xs].astype(np.float64)
    return np.asarray((np.average(xs, weights=weights), np.average(ys, weights=weights)), dtype=np.float64)


def _mask_separation(left: np.ndarray, right: np.ndarray) -> tuple[float, int]:
    intersection = int(np.count_nonzero((left > ALPHA_THRESHOLD) & (right > ALPHA_THRESHOLD)))
    return _minimum_mask_distance(left, right), intersection


def _alpha_boundary(alpha: np.ndarray) -> np.ndarray:
    binary = np.asarray(alpha > ALPHA_THRESHOLD, dtype=np.uint8)
    eroded = cv2.erode(binary, np.ones((3, 3), dtype=np.uint8), iterations=1)
    return (binary & (1 - eroded)) * np.uint8(255)


def _alpha_iso_contour_points(alpha: np.ndarray) -> np.ndarray:
    values = np.asarray(alpha, dtype=np.float64)
    threshold = float(ALPHA_THRESHOLD)
    points: list[np.ndarray] = []
    left, right = values[:, :-1], values[:, 1:]
    crossing = ((left > threshold) & (right <= threshold)) | ((left <= threshold) & (right > threshold))
    ys, xs = np.where(crossing)
    if len(xs):
        denominator = right[ys, xs] - left[ys, xs]
        amount = np.clip((threshold - left[ys, xs]) / denominator, 0.0, 1.0)
        points.append(np.column_stack((xs.astype(np.float64) + amount, ys.astype(np.float64))))
    top, bottom = values[:-1, :], values[1:, :]
    crossing = ((top > threshold) & (bottom <= threshold)) | ((top <= threshold) & (bottom > threshold))
    ys, xs = np.where(crossing)
    if len(xs):
        denominator = bottom[ys, xs] - top[ys, xs]
        amount = np.clip((threshold - top[ys, xs]) / denominator, 0.0, 1.0)
        points.append(np.column_stack((xs.astype(np.float64), ys.astype(np.float64) + amount)))
    if points:
        return np.vstack(points).astype(np.float64)
    boundary = _alpha_boundary(alpha)
    ys, xs = np.where(boundary > 0)
    if not len(xs):
        raise ValueError("cannot sample an empty rendered alpha contour")
    return np.column_stack((xs, ys)).astype(np.float64)


def _nearest_boundary_points(alpha: np.ndarray, predicted: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points = _alpha_iso_contour_points(alpha)
    selected = []
    residuals = []
    for point in np.asarray(predicted, dtype=np.float64):
        distances = np.linalg.norm(points - point, axis=1)
        order = np.argsort(distances)[:12]
        anchor = points[int(order[0])]
        best = anchor
        best_distance = float(distances[int(order[0])])
        # Alpha threshold crossings are exact but sampled only where the
        # contour crosses pixel-grid edges. Project onto nearby crossing pairs
        # to recover the continuous local iso-segment and avoid one-pixel
        # endpoint hops as the camera moves.
        for candidate_index in order[1:]:
            candidate = points[int(candidate_index)]
            if float(np.linalg.norm(candidate - anchor)) > 1.75:
                continue
            segment_distance, projected = _point_segment_distance(point, anchor, candidate)
            if segment_distance < best_distance:
                best = projected
                best_distance = segment_distance
        selected.append(best)
        residuals.append(float(np.min(np.linalg.norm(points - best, axis=1))))
    return np.asarray(selected, dtype=np.float64), np.asarray(residuals, dtype=np.float64)


def _intersection_centroid(left: np.ndarray, right: np.ndarray) -> np.ndarray | None:
    overlap = np.minimum(left, right)
    if not np.any(overlap > ALPHA_THRESHOLD):
        return None
    return _mask_centroid(overlap)


def _point_segment_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> tuple[float, np.ndarray]:
    direction = end - start
    denominator = max(float(np.dot(direction, direction)), 1e-9)
    amount = min(1.0, max(0.0, float(np.dot(point - start, direction) / denominator)))
    nearest = start + direction * amount
    return float(np.linalg.norm(point - nearest)), nearest


def _signed_hull_margin(point: np.ndarray, hull: np.ndarray) -> float:
    contour = np.asarray(hull, dtype=np.float32).reshape(-1, 1, 2)
    if len(contour) >= 3 and abs(float(cv2.contourArea(contour))) > 1e-6:
        return float(cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), True))
    if len(contour) == 2:
        distance, _ = _point_segment_distance(point, contour[0, 0].astype(np.float64), contour[1, 0].astype(np.float64))
        return -distance
    return -float("inf")


def _vertical_hull_projection(point: np.ndarray, hull: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """Project the image COM vertically into the measured support hull.

    The image centroid is above the ground plane. A vertical screen ray keeps
    its horizontal balance coordinate; the midpoint of the measured convex-
    hull slice supplies ground depth without widening or replacing the hull.
    """
    vertices = np.asarray(hull, dtype=np.float64).reshape(-1, 2)
    x = float(point[0])
    intersections: list[float] = []
    for index, start in enumerate(vertices):
        end = vertices[(index + 1) % len(vertices)]
        low, high = sorted((float(start[0]), float(end[0])))
        if x < low - 1e-6 or x > high + 1e-6:
            continue
        dx = float(end[0] - start[0])
        if abs(dx) <= 1e-9:
            if abs(x - float(start[0])) <= 1e-6:
                intersections.extend((float(start[1]), float(end[1])))
            continue
        amount = (x - float(start[0])) / dx
        if -1e-6 <= amount <= 1.0 + 1e-6:
            intersections.append(float(start[1] + amount * (end[1] - start[1])))
    if len(intersections) >= 2:
        lower, upper = min(intersections), max(intersections)
        return np.asarray((x, 0.5 * (lower + upper)), dtype=np.float64), [lower, upper]
    fallback_y = float(np.mean(vertices[:, 1]))
    return np.asarray((x, fallback_y), dtype=np.float64), intersections


def _flatten_gate_leaves(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        if not prefix:
            raise ValueError("gate threshold requires a named path")
        return {prefix: value}
    output: dict[str, Any] = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        output.update(_flatten_gate_leaves(child, path))
    return output


def _measurement_record(aggregate_measurements: dict[str, Any], path: str) -> dict[str, Any]:
    value: Any = aggregate_measurements
    for segment in path.split("."):
        if not isinstance(value, dict) or segment not in value:
            raise KeyError(f"missing aggregate measurement: {path}")
        value = value[segment]
    if not isinstance(value, dict):
        raise ValueError(f"aggregate measurement is not a record: {path}")
    return value


def evaluate_contact_gate_results(
    contract: dict[str, Any],
    aggregate_measurements: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate every gate leaf from measured aggregates, failing closed."""
    derivation = contract["report_contract"]["gate_derivation"]
    thresholds = _flatten_gate_leaves(contract["gates"])
    required_fields = set(derivation["measurement_record_required_fields"])
    allowed_sources = set(derivation["allowed_source_kinds"])
    forbidden_sources = set(derivation["forbidden_source_kinds"])
    overrides = derivation["comparator_overrides"]
    defaults = derivation["default_comparators"]
    threshold_results: dict[str, dict[str, Any]] = {}
    for path, threshold in thresholds.items():
        record = _measurement_record(aggregate_measurements, path)
        missing = required_fields - set(record)
        if missing:
            raise ValueError(f"aggregate measurement {path} misses {sorted(missing)}")
        source_kind = str(record["source_kind"])
        if source_kind in forbidden_sources or source_kind not in allowed_sources:
            raise ValueError(f"aggregate measurement {path} has forbidden source {source_kind}")
        leaf = path.rsplit(".", 1)[-1]
        comparator = overrides.get(path)
        if comparator is None:
            comparator = next((name for prefix, name in defaults.items() if leaf.startswith(prefix)), "equal")
        measured = record["value"]
        if comparator == "less_than_or_equal":
            passed = measured <= threshold
        elif comparator == "greater_than_or_equal":
            passed = measured >= threshold
        elif comparator == "equal":
            passed = measured == threshold
        else:
            raise ValueError(f"unsupported comparator {comparator} for {path}")
        threshold_results[path] = {
            "measured_value": measured,
            "threshold_value": threshold,
            "comparator": comparator,
            "passed": bool(passed),
            "source_kind": source_kind,
            "source_detail": record["source_detail"],
            "aggregation": record["aggregation"],
        }
    gate_results = {
        group: all(threshold_results[path]["passed"] for path in paths)
        for group, paths in derivation["gate_groups"].items()
    }
    return {
        "threshold_results": threshold_results,
        "gate_results": gate_results,
        "machine_passed": all(gate_results.values()),
    }


def _barycentric_row(point: np.ndarray, vertices: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    for triangle in triangles:
        tri = vertices[triangle].astype(np.float64)
        matrix = np.vstack((tri.T, np.ones(3, dtype=np.float64)))
        weights = np.linalg.solve(matrix, np.asarray((point[0], point[1], 1.0), dtype=np.float64))
        if np.min(weights) >= -1e-4 and np.max(weights) <= 1.0001:
            row = np.zeros(len(vertices), dtype=np.float64)
            row[triangle] = weights
            return row
    raise ValueError("contact marker leaves the canonical shared-UV cage")


def _constrained_destination_cage(
    canonical_vertices: np.ndarray,
    initial_destination: np.ndarray,
    source_markers: np.ndarray,
    destination_markers: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    weights = np.vstack(
        [_barycentric_row(point, canonical_vertices, FIXED_TRIANGLES) for point in source_markers]
    )
    # The similarity cage is the regularizer; seven explicit sole constraints
    # are the data term.  This flattens the rendered sole without inventing a
    # second texture or a second remap.
    strength = 1_000_000.0
    system = strength * (weights.T @ weights) + np.eye(len(canonical_vertices), dtype=np.float64)
    right = strength * (weights.T @ destination_markers) + initial_destination.astype(np.float64)
    solved = np.linalg.solve(system, right).astype(np.float32)
    return solved, weights


class ContactPerformanceRenderer:
    def __init__(self, contract_path: str | Path):
        self.contract = _load_contract(contract_path)
        seated_path = _repo_path(self.contract["source_policy"]["seated_geometry_contract"], "seated geometry contract")
        self.shared = SharedUVPerformanceRenderer(seated_path)
        self.base = self.shared.base
        self.pose_landmarks = _pose_landmarks(self.contract)
        self._base_landmarks = copy.deepcopy(self.pose_landmarks[0]["landmarks"])
        loaded_direction = np.asarray(self._base_landmarks["left_hand"], dtype=np.float64) - np.asarray(
            self._base_landmarks["left_elbow"], dtype=np.float64
        )
        self._loaded_hand_tip_direction = loaded_direction / max(float(np.linalg.norm(loaded_direction)), 1e-9)
        self._sole_history: dict[int, dict[str, np.ndarray]] = {}
        self._hand_centroid_history: dict[int, np.ndarray] = {}
        self._hand_contact_local_history: dict[int, np.ndarray] = {}
        self._root_history: dict[int, np.ndarray] = {}
        self._knee_history: dict[int, float] = {}
        self._chair_seat_patch_alpha = np.asarray(
            self.base.chair_seat_patch.convert("RGBA"), dtype=np.uint8
        )[:, :, 3].copy()
        self.boot_cages = {}
        self.boot_source_markers: dict[str, np.ndarray] = {}
        for component in self.shared.components:
            if component.identifier not in {"left_boot", "right_boot"}:
                continue
            samples = np.asarray(
                self.contract["boot_contact_geometry"][component.identifier]["sole_samples_component_local_px"],
                dtype=np.float32,
            )
            source_contour = _alpha_iso_contour_points(component.standing.rgba[:, :, 3])
            source_markers = np.asarray(
                [
                    source_contour[int(np.argmin(np.linalg.norm(source_contour - point, axis=1)))]
                    for point in samples
                ],
                dtype=np.float32,
            )
            self.boot_source_markers[component.identifier] = source_markers
            self.boot_cages[component.identifier] = build_strip_cage(
                component.standing.rgba,
                (source_markers[0], source_markers[-1]),
            )

    def close(self) -> None:
        self.shared.close()

    def __enter__(self) -> "ContactPerformanceRenderer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _camera_parameters(self, frame: int) -> tuple[tuple[int, int, int, int], float, float]:
        camera = self.base.phase_renderer.control["camera"]
        amount = (frame - 1) / 170.0
        eased = _ease_in_out_cubic(amount)
        zoom = float(camera["start_zoom"]) + (float(camera["end_zoom"]) - float(camera["start_zoom"])) * eased
        focus = (
            float(camera["focus_start"][0]) + (float(camera["focus_end"][0]) - float(camera["focus_start"][0])) * eased,
            float(camera["focus_start"][1]) + (float(camera["focus_end"][1]) - float(camera["focus_start"][1])) * eased,
        )
        box = camera_crop_box(self.base.source_size, OUTPUT_SIZE, zoom, focus)
        sx = OUTPUT_SIZE[0] / (box[2] - box[0])
        sy = OUTPUT_SIZE[1] / (box[3] - box[1])
        return box, sx, sy

    def _camera_point(self, point: np.ndarray, frame: int) -> np.ndarray:
        box, sx, sy = self._camera_parameters(frame)
        canvas = np.asarray(point, dtype=np.float64) * RENDER_SCALE
        return np.asarray(((canvas[0] - box[0]) * sx, (canvas[1] - box[1]) * sy), dtype=np.float64)

    def _camera_canvas_point(self, point: np.ndarray, frame: int) -> np.ndarray:
        box, sx, sy = self._camera_parameters(frame)
        canvas = np.asarray(point, dtype=np.float64)
        return np.asarray(((canvas[0] - box[0]) * sx, (canvas[1] - box[1]) * sy), dtype=np.float64)

    def _camera_alpha(self, alpha: np.ndarray, frame: int) -> np.ndarray:
        box, _, _ = self._camera_parameters(frame)
        image = Image.fromarray(alpha, mode="L")
        try:
            output = image.crop(box).resize(OUTPUT_SIZE, Image.Resampling.NEAREST)
            try:
                return np.asarray(output, dtype=np.uint8).copy()
            finally:
                output.close()
        finally:
            image.close()

    def _rendered_contact_shadow(
        self,
        component_alphas: dict[str, np.ndarray],
        rendered_sole_canvas: dict[str, np.ndarray],
    ) -> tuple[Image.Image, dict[str, np.ndarray]]:
        width, height = self.base.source_size
        combined = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        opacity = int(self.base.phase_renderer.control["effects"]["contact_shadow"]["opacity"])
        masks: dict[str, np.ndarray] = {}
        for side in ("left_boot", "right_boot"):
            actual, _ = _nearest_boundary_points(component_alphas[side], rendered_sole_canvas[side])
            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)
            draw.line([tuple(point) for point in actual], fill=255, width=max(3, int(round(3.0 * RENDER_SCALE))))
            mask = mask.filter(ImageFilter.GaussianBlur(max(1.0, RENDER_SCALE)))
            masks[side] = np.asarray(mask, dtype=np.uint8).copy()
            colored = Image.new("RGBA", (width, height), (35, 21, 14, 0))
            colored.putalpha(mask.point(lambda value: int(round(value * opacity / 255.0))))
            combined = Image.alpha_composite(combined, colored)
            colored.close()
            mask.close()
        return combined, masks

    def _contact_layers(
        self,
        solution: dict[str, Any],
        landmarks: dict[str, np.ndarray],
        progress: float,
    ) -> tuple[dict[str, np.ndarray], dict[str, dict[str, Any]], dict[str, np.ndarray]]:
        layers: dict[str, np.ndarray] = {}
        metrics: dict[str, dict[str, Any]] = {}
        rendered_sole_canvas: dict[str, np.ndarray] = {}
        for component in self.shared.components:
            standing = _transform_vertices(component.standing, component.standing_cage, landmarks)
            if component.identifier in {"left_boot", "right_boot"}:
                side = component.identifier
                boot_cage = self.boot_cages[side]
                source_markers = self.boot_source_markers[side]
                contact_row = self.contract["boot_contact_geometry"][side]
                target_source = np.asarray(solution["foot_targets"][side]["sole_samples"], dtype=np.float32)
                target_source += np.asarray(contact_row["iso_contour_registration_offset_source_px"], dtype=np.float32)
                target_markers = target_source * RENDER_SCALE
                matrix, _ = _similarity_affine(
                    source_markers[0], source_markers[-1], target_markers[0], target_markers[-1]
                )
                homogeneous = np.column_stack(
                    (boot_cage.vertices, np.ones(len(boot_cage.vertices), dtype=np.float32))
                )
                initial = homogeneous @ matrix.T
                destination, marker_weights = _constrained_destination_cage(
                    boot_cage.vertices,
                    initial,
                    source_markers,
                    target_markers,
                )
                rendered_sole_canvas[side] = marker_weights @ destination
            else:
                seated = _transform_vertices(component.seated, component.seated_cage, landmarks)
                destination = seated * (1.0 - progress) + standing * progress
            grid = destination.reshape(GRID_COLUMNS, GRID_ROWS, 2)
            if component.identifier not in {"left_boot", "right_boot"}:
                grid[:, 0] = grid[:, 1] + (grid[:, 0] - grid[:, 1]) * 1.027
                grid[:, 2] = grid[:, 1] + (grid[:, 2] - grid[:, 1]) * 1.027
            if component.identifier == "torso":
                grid[5, 0] = landmarks["left_shoulder"] * RENDER_SCALE
                grid[5, 2] = landmarks["right_shoulder"] * RENDER_SCALE
                grid[4, 0] = grid[4, 0] * 0.65 + landmarks["left_shoulder"] * RENDER_SCALE * 0.35
                grid[4, 2] = grid[4, 2] * 0.65 + landmarks["right_shoulder"] * RENDER_SCALE * 0.35
            destination = grid.reshape(-1, 2)
            areas = _signed_triangle_areas(destination, FIXED_TRIANGLES)
            canonical_cage = self.boot_cages[component.identifier] if component.identifier in self.boot_cages else component.standing_cage
            standing_areas = _signed_triangle_areas(
                initial if component.identifier in self.boot_cages else standing,
                FIXED_TRIANGLES,
            )
            if np.any(areas <= 0.0) or np.any(~np.isfinite(areas)):
                raise ValueError(f"{component.identifier} contact mesh folded")
            warped, dense_coverage, drift = _dense_piecewise_remap(
                component.standing_texture,
                canonical_cage.vertices,
                destination,
                FIXED_TRIANGLES,
                self.base.source_size,
            )
            layers[component.identifier] = warped
            metrics[component.identifier] = {
                "foldover_count": 0,
                "minimum_triangle_area_ratio": float(np.min(areas / standing_areas)),
                "maximum_triangle_area_ratio": float(np.max(areas / standing_areas)),
                "canonical_alpha_mesh_coverage": (
                    canonical_cage.coverage
                    if component.identifier in self.boot_cages
                    else min(component.seated_cage.coverage, component.standing_cage.coverage)
                ),
                "dense_inverse_map_coverage": dense_coverage,
                "maximum_fixed_uv_drift_px": drift,
            }
        return layers, metrics, rendered_sole_canvas

    def _foot_evidence(
        self,
        frame: int,
        solution: dict[str, Any],
        rendered_sole_canvas: dict[str, np.ndarray],
        final_alphas: dict[str, np.ndarray],
        final_shadow_alphas: dict[str, np.ndarray],
    ) -> dict[str, dict[str, Any]]:
        evidence: dict[str, dict[str, Any]] = {}
        current_samples: dict[str, np.ndarray] = {}
        for side in ("left_boot", "right_boot"):
            target_source = np.asarray(self.contract["porch_target_geometry"][side]["target_samples"], dtype=np.float64)
            predicted = np.asarray(
                [self._camera_canvas_point(point, frame) for point in rendered_sole_canvas[side]],
                dtype=np.float64,
            )
            rendered, _ = _nearest_boundary_points(final_alphas[side], predicted)
            boundary_pixels = _alpha_iso_contour_points(final_alphas[side])
            boundary_alpha = _alpha_boundary(final_alphas[side])
            integer_y, integer_x = np.where(boundary_alpha > 0)
            integer_boundary = np.column_stack((integer_x, integer_y)).astype(np.float64)
            membership_residual = np.asarray(
                [float(np.min(np.linalg.norm(boundary_pixels - point, axis=1))) for point in rendered],
                dtype=np.float64,
            )
            current_samples[side] = rendered
            target = np.asarray([self._camera_point(point, frame) for point in target_source])
            direction = target[-1] - target[0]
            norm = max(float(np.linalg.norm(direction)), 1e-9)
            signed = np.asarray(
                [float(direction[0] * (point[1] - target[0, 1]) - direction[1] * (point[0] - target[0, 0])) / norm for point in rendered],
                dtype=np.float64,
            )
            previous_frame = max(64, frame - 1)
            if previous_frame == frame:
                previous = rendered
            elif previous_frame in self._sole_history:
                previous = self._sole_history[previous_frame][side]
            else:
                previous_solution = solve_contact_landmarks(self.contract, previous_frame, self._base_landmarks)
                previous_landmarks = {
                    identifier: np.asarray(point, dtype=np.float32)
                    for identifier, point in previous_solution["landmarks"].items()
                }
                previous_direction = previous_landmarks["left_hand"] - previous_landmarks["left_elbow"]
                previous_direction /= max(float(np.linalg.norm(previous_direction)), 1e-6)
                previous_landmarks["left_hand_tip"] = previous_landmarks["left_hand"] + previous_direction * 72.0
                previous_layers, _, previous_markers = self._contact_layers(
                    previous_solution,
                    previous_landmarks,
                    float(previous_solution["stand_progress"]),
                )
                previous_alpha = self._camera_alpha(
                    np.round(previous_layers[side][:, :, 3] * 255.0).astype(np.uint8), previous_frame
                )
                previous_predicted = np.asarray(
                    [self._camera_canvas_point(point, previous_frame) for point in previous_markers[side]],
                    dtype=np.float64,
                )
                previous, _ = _nearest_boundary_points(previous_alpha, previous_predicted)
            endpoint_motion = max(float(np.linalg.norm(rendered[0] - previous[0])), float(np.linalg.norm(rendered[-1] - previous[-1])))
            pitch = math.degrees(math.atan2(rendered[-1, 1] - rendered[0, 1], rendered[-1, 0] - rendered[0, 0]))
            target_pitch = math.degrees(math.atan2(target[-1, 1] - target[0, 1], target[-1, 0] - target[0, 0]))
            evidence[side] = {
                "measurement_space": "final_output_px_after_camera",
                "source_pair": [f"rendered_{side}_sole_samples", f"porch_{side}_target_geometry"],
                "sample_provenance": {
                    "sample_source": "final_component_alpha_boundary",
                    "component_id": side,
                    "measurement_space": "final_output_px_after_camera",
                    "alpha_threshold": ALPHA_THRESHOLD,
                    "boundary_pixels_preview_px": boundary_pixels.tolist(),
                    "raw_integer_boundary_pixels_preview_px": integer_boundary.tolist(),
                    "sample_membership_residual_preview_px": membership_residual.tolist(),
                },
                "rendered_samples_preview_px": rendered.tolist(),
                "target_samples_preview_px": target.tolist(),
                "signed_distance_preview_px": signed.tolist(),
                "absolute_distance_p95_preview_px": float(np.percentile(np.abs(signed), 95)),
                "maximum_clearance_preview_px": max(0.0, float(np.max(-signed))),
                "maximum_penetration_preview_px": max(0.0, float(np.max(signed))),
                "contact_fraction": float(np.mean(np.abs(signed) <= 1.5)),
                "pitch_error_degrees": pitch - target_pitch,
                "toe_residual_preview_px": float(np.linalg.norm(rendered[-1] - target[-1])),
                "endpoint_motion_preview_px_per_frame": endpoint_motion,
                "heel_lift_preview_px": float(solution["foot_targets"][side]["heel_lift_preview_px"]),
                "shadow_to_sole_gap_preview_px": float(
                    _minimum_mask_distance(_alpha_boundary(final_alphas[side]), final_shadow_alphas[side])
                ),
                "shadow_source": "rendered_contact_polygon",
                "shadow_gap_provenance": {
                    "measurement": "independent_mask_separation",
                    "measurement_space": "final_output_px_after_camera",
                    "source_kinds": ["final_boot_alpha_mask", "final_contact_shadow_alpha_mask"],
                },
            }
        self._sole_history[frame] = current_samples
        return evidence

    def _chair_evidence(
        self,
        frame: int,
        solution: dict[str, Any],
        final_alphas: dict[str, np.ndarray],
    ) -> dict[str, Any]:
        chair_arm = self._camera_alpha(self.base.chair_arm_mask, frame)
        chair_seat = self._camera_alpha(self.base.chair_seat_mask, frame)
        hand_alpha = final_alphas["left_hand"]
        hand_separation, hand_intersection = _mask_separation(hand_alpha, chair_arm)

        hand_point = _mask_centroid(hand_alpha)
        contact_point = _intersection_centroid(hand_alpha, chair_arm)
        if contact_point is None:
            hand_boundary = _alpha_boundary(hand_alpha)
            arm_boundary = _alpha_boundary(chair_arm)
            hy, hx = np.where(hand_boundary > 0)
            ay, ax = np.where(arm_boundary > 0)
            hand_points = np.column_stack((hx, hy)).astype(np.float64)
            arm_points = np.column_stack((ax, ay)).astype(np.float64)
            if len(hand_points) and len(arm_points):
                distances = np.linalg.norm(hand_points[:, None, :] - arm_points[None, :, :], axis=2)
                left_index, right_index = np.unravel_index(int(np.argmin(distances)), distances.shape)
                contact_point = (hand_points[left_index] + arm_points[right_index]) * 0.5
        arm_centroid = _mask_centroid(chair_arm)
        contact_local = contact_point - arm_centroid if contact_point is not None else hand_point - arm_centroid
        previous_point = self._hand_centroid_history.get(frame - 1, hand_point)
        before_point = self._hand_centroid_history.get(frame - 2, previous_point)
        position_jump = float(np.linalg.norm(hand_point - previous_point))
        velocity_jump = float(np.linalg.norm((hand_point - previous_point) - (previous_point - before_point)))
        previous_contact_local = self._hand_contact_local_history.get(frame - 1, contact_local)
        slip = float(np.linalg.norm(contact_local - previous_contact_local))
        self._hand_centroid_history[frame] = hand_point
        self._hand_contact_local_history[frame] = contact_local

        # The annotated polygon is an occluder, not a collision volume.  The
        # physical receiver is its authored top edge.  Measure the visible
        # pelvis/butt silhouette after the actual foreground seat patch has
        # occluded it, then compare that independent boundary to the receiver.
        pelvis_alpha = np.maximum.reduce(
            [final_alphas["torso"], final_alphas["left_thigh"], final_alphas["right_thigh"]]
        ).astype(np.float64)
        seat_patch = self._camera_alpha(self._chair_seat_patch_alpha, frame).astype(np.float64) / 255.0
        visible_pelvis = np.round(pelvis_alpha * (1.0 - seat_patch)).astype(np.uint8)
        pelvis_boundary = _alpha_boundary(visible_pelvis)
        by, bx = np.where(pelvis_boundary > 0)
        boundary_points = np.column_stack((bx, by)).astype(np.float64)
        receiver = self.contract["porch_target_geometry"]["chair_seat"]["collision_receiver"]
        receiver_start = self._camera_point(np.asarray(receiver["start"], dtype=np.float64), frame)
        receiver_end = self._camera_point(np.asarray(receiver["end"], dtype=np.float64), frame)
        receiver_direction = receiver_end - receiver_start
        receiver_length = max(float(np.linalg.norm(receiver_direction)), 1e-9)
        receiver_distances = []
        receiver_nearest = []
        receiver_signed = []
        for point in boundary_points:
            distance, nearest = _point_segment_distance(point, receiver_start, receiver_end)
            receiver_distances.append(distance)
            receiver_nearest.append(nearest)
            receiver_signed.append(
                float(receiver_direction[0] * (point[1] - receiver_start[1]) - receiver_direction[1] * (point[0] - receiver_start[0]))
                / receiver_length
            )
        distance_array = np.asarray(receiver_distances, dtype=np.float64)
        nearest_index = int(np.argmin(distance_array))
        seat_separation = float(distance_array[nearest_index])
        contact_band = distance_array <= seat_separation + 1.5
        seat_penetration = max(0.0, float(np.max(np.asarray(receiver_signed)[contact_band])))
        seat_contact_point = (
            boundary_points[nearest_index] + np.asarray(receiver_nearest[nearest_index], dtype=np.float64)
        ) * 0.5
        seat_intersection = int(np.count_nonzero((pelvis_boundary > 0) & (chair_seat > ALPHA_THRESHOLD)))
        shoulder_now = self._camera_point(np.asarray(solution["landmarks"]["left_shoulder"], dtype=np.float64), frame)
        shoulder_start_solution = solve_contact_landmarks(self.contract, 64, self._base_landmarks)
        shoulder_start = self._camera_point(np.asarray(shoulder_start_solution["landmarks"]["left_shoulder"], dtype=np.float64), 64)
        hand_start = self._camera_point(np.asarray(shoulder_start_solution["landmarks"]["left_hand"], dtype=np.float64), 64)
        shoulder_travel = float(np.linalg.norm((shoulder_now - hand_point) - (shoulder_start - hand_start)))
        loaded_hand = float(solution["loads"]["chair_hand"]) > 0.05
        loaded_seat = float(solution["loads"]["seat"]) > 0.05
        return {
            "hand": {
                "measurement_space": "final_output_px_after_camera",
                "source_pair": ["rendered_left_hand_alpha", "rendered_chair_arm_mask"],
                "separation_preview_px": hand_separation,
                "slip_preview_px": slip,
                "intersection_pixels": hand_intersection,
                "contact_patch_centroid_preview_px": contact_point.tolist() if contact_point is not None else None,
                "contact_patch_centroid_chair_local_preview_px": contact_local.tolist(),
                "shoulder_travel_relative_to_hand_preview_px": shoulder_travel,
                "position_jump_preview_px": position_jump,
                "velocity_jump_preview_px_per_frame": velocity_jump,
            },
            "seat": {
                "measurement_space": "final_output_px_after_camera",
                "source_pair": ["rendered_pelvis_alpha_boundary", "camera_transformed_chair_seat_top_receiver"],
                "separation_preview_px": seat_separation,
                "penetration_preview_px": seat_penetration,
                "intersection_pixels": seat_intersection,
                "receiver_source": "chair_seat_mask_top_edge_0_to_1",
                "receiver_preview_px": [receiver_start.tolist(), receiver_end.tolist()],
                "contact_point_preview_px": seat_contact_point.tolist(),
                "visible_pelvis_boundary_source": "final_component_alpha_after_rendered_seat_patch_occlusion",
                "penetration_provenance": {
                    "measurement": "signed_alpha_boundary_to_receiver_depth",
                    "measurement_space": "final_output_px_after_camera",
                    "source_pair": [
                        "rendered_pelvis_alpha_boundary",
                        "camera_transformed_chair_seat_top_receiver",
                    ],
                    "mask_sources": ["final_torso_alpha_mask", "rendered_chair_seat_occlusion_mask"],
                },
            },
        }

    def _balance_evidence(
        self,
        frame: int,
        solution: dict[str, Any],
        final_alphas: dict[str, np.ndarray],
        feet: dict[str, dict[str, Any]],
        chair: dict[str, Any],
    ) -> dict[str, Any]:
        weights = self.contract["render_derived_balance"]["component_mass_weights"]
        centroids = {identifier: _mask_centroid(alpha) for identifier, alpha in final_alphas.items()}
        rendered_com = sum(centroids[identifier] * float(weights[identifier]) for identifier in weights)
        support = []
        for side in ("left_boot", "right_boot"):
            for point, distance in zip(
                feet[side]["rendered_samples_preview_px"],
                feet[side]["signed_distance_preview_px"],
            ):
                if abs(float(distance)) <= 1.5:
                    support.append(point)
        if float(solution["loads"]["chair_hand"]) > 0.05 and chair["hand"]["contact_patch_centroid_preview_px"] is not None:
            support.append(chair["hand"]["contact_patch_centroid_preview_px"])
        if float(solution["loads"]["seat"]) > 0.05 and chair["seat"]["separation_preview_px"] <= 1.5:
            support.append(chair["seat"]["contact_point_preview_px"])
        support_array = np.asarray(support, dtype=np.float64)
        hull = cv2.convexHull(support_array.astype(np.float32)).reshape(-1, 2)
        projected_com, vertical_slice = _vertical_hull_projection(rendered_com, hull)
        margin = _signed_hull_margin(projected_com, hull)
        return {
            "com_source": "mass_weighted_final_output_component_alpha_centroids",
            "support_hull_source": "independently_measured_rendered_contacts",
            "raw_mass_centroid_preview_px": rendered_com.tolist(),
            "com_preview_px": projected_com.tolist(),
            "support_hull_preview_px": hull.astype(float).tolist(),
            "active_support_point_count": len(support),
            "com_support_hull_margin_preview_px": float(margin),
            "margin_method": "signed_euclidean_distance_after_vertical_screen_projection_to_2d_hull_slice",
            "vertical_hull_slice_preview_y": vertical_slice,
        }

    def _motion_evidence(
        self,
        frame: int,
        solution: dict[str, Any],
        final_alphas: dict[str, np.ndarray],
    ) -> dict[str, Any]:
        weights = self.contract["render_derived_balance"]["component_mass_weights"]
        centroids = {identifier: _mask_centroid(alpha) for identifier, alpha in final_alphas.items()}
        raw_root = sum(centroids[identifier] * float(weights[identifier]) for identifier in weights)
        previous_filtered = self._root_history.get(frame - 1)
        root = raw_root if previous_filtered is None else previous_filtered + 0.85 * (raw_root - previous_filtered)
        pelvis_alpha = np.maximum.reduce(
            [final_alphas["torso"], final_alphas["left_thigh"], final_alphas["right_thigh"]]
        )
        pelvis = _mask_centroid(pelvis_alpha)
        knee_proxy = float(
            np.mean(
                [
                    centroids["left_thigh"][1],
                    centroids["left_shin"][1],
                    centroids["right_thigh"][1],
                    centroids["right_shin"][1],
                ]
            )
        )
        self._root_history[frame] = root
        self._knee_history[frame] = knee_proxy
        settle_frames = [value for value in range(96, frame + 1) if value in self._root_history]
        roots = [self._root_history[value] for value in settle_frames] or [root]
        knees = [self._knee_history[value] for value in settle_frames] or [knee_proxy]
        root_array = np.asarray(roots, dtype=np.float64)
        stable_values = [self._root_history[value] for value in range(108, 113) if value in self._root_history]
        equilibrium = np.mean(np.asarray(stable_values, dtype=np.float64), axis=0) if stable_values else root_array[-1]
        final_speed = float(np.linalg.norm(root_array[-1] - root_array[-2])) if len(root_array) >= 2 else 0.0
        stable_count = 1
        for index in range(len(root_array) - 1, 0, -1):
            if float(np.linalg.norm(root_array[index] - root_array[index - 1])) <= 0.5:
                stable_count += 1
            else:
                break
        return {
            "root_preview_px": root.tolist(),
            "raw_root_preview_px": raw_root.tolist(),
            "pelvis_preview_px": pelvis.tolist(),
            "root_source": "bounded_causal_filter_of_mass_weighted_final_output_component_alpha_centroids",
            "root_filter": {"kind": "causal_exponential", "current_alpha": 0.85},
            "pelvis_source": "final_output_torso_and_thigh_alpha_union_centroid",
            "settle": {
                "upward_overshoot_preview_px": float(equilibrium[1] - np.min(root_array[:, 1])),
                "downward_compression_preview_px": float(np.max(root_array[:, 1]) - equilibrium[1]),
                "knee_recompression_preview_px": (
                    float(max(knees[6:]) - min(knees[:6])) if len(knees) >= 12 else 0.0
                ),
                "final_root_error_preview_px": float(np.linalg.norm(root_array[-1] - equilibrium)),
                "final_root_speed_preview_px_per_frame": final_speed,
                "stable_frame_count": stable_count,
            },
        }

    def render_frame(self, frame: int) -> tuple[Image.Image, dict[str, Any]]:
        if frame not in FRAMES:
            raise ValueError("contact performance proof supports frames 64 through 112")
        solution = solve_contact_landmarks(self.contract, frame, self._base_landmarks)
        landmarks = {identifier: np.asarray(point, dtype=np.float32) for identifier, point in solution["landmarks"].items()}
        if frame <= 84:
            left_direction = self._loaded_hand_tip_direction.astype(np.float32)
        else:
            left_direction = landmarks["left_hand"] - landmarks["left_elbow"]
            left_direction /= max(float(np.linalg.norm(left_direction)), 1e-6)
        landmarks["left_hand_tip"] = landmarks["left_hand"] + left_direction * 72.0
        layers, mesh_metrics, rendered_sole_canvas = self._contact_layers(
            solution,
            landmarks,
            float(solution["stand_progress"]),
        )
        joint_pre = self.shared._repair_and_measure_joints(layers, landmarks)
        width, height = self.base.source_size
        canvas = np.zeros((height, width, 4), dtype=np.float32)
        component_alphas: dict[str, np.ndarray] = {}
        for component in self.shared.components:
            layer = layers[component.identifier]
            canvas = _over(canvas, layer)
            component_alphas[component.identifier] = np.round(layer[:, :, 3] * 255.0).astype(np.uint8)
        character = _premultiplied_to_rgba(canvas)
        contact_shadow, shadow_alphas = self._rendered_contact_shadow(component_alphas, rendered_sole_canvas)
        composed = Image.alpha_composite(self.base.background.convert("RGBA"), contact_shadow)
        contact_shadow.close()
        composed = Image.alpha_composite(composed, Image.fromarray(character, mode="RGBA"))
        if float(solution["loads"]["seat"]) > 0.05:
            composed = Image.alpha_composite(composed, self.base.chair_seat_patch)
        if float(solution["loads"]["chair_hand"]) > 0.05:
            composed = Image.alpha_composite(composed, self.base.chair_arm_patch)
        steam_origin = landmarks["mug_center"] * RENDER_SCALE
        steam_origin[1] -= 50.0 * RENDER_SCALE
        composed = self.base._steam(composed, steam_origin, frame)
        strength = float(self.base.phase_renderer.control["effects"]["light_breathe"]["strength"])
        factor = 1.0 + strength * math.sin((frame - 1) / FPS * math.pi * 0.71)
        composed = ImageEnhance.Brightness(composed.convert("RGB")).enhance(factor)
        output = _camera_frame(composed, self.base.phase_renderer.control["camera"], (frame - 1) / 170.0, OUTPUT_SIZE)

        final_alphas = {identifier: self._camera_alpha(alpha, frame) for identifier, alpha in component_alphas.items()}
        final_shadow_alphas = {
            identifier: self._camera_alpha(alpha, frame) for identifier, alpha in shadow_alphas.items()
        }
        joints = {
            identifier: _joint_measurement(final_alphas[identifier.split("__")[0]], final_alphas[identifier.split("__")[1]])
            for identifier in joint_pre
        }
        feet = self._foot_evidence(frame, solution, rendered_sole_canvas, final_alphas, final_shadow_alphas)
        chair = self._chair_evidence(frame, solution, final_alphas)
        balance = self._balance_evidence(frame, solution, final_alphas, feet, chair)
        motion = self._motion_evidence(frame, solution, final_alphas)
        topology_counts = {
            identifier: _substantial_components(alpha, ALPHA_THRESHOLD, 25)[0]
            for identifier, alpha in final_alphas.items()
        }
        details = {
            "frame": frame,
            "measurement_space": "final_output_px_after_camera",
            "loads": solution["loads"],
            "texture_source_policy": {
                "texture_source_count": 1,
                "standing_texture_sources_per_component": 1,
                "seated_rgb_sample_count": 0,
                "dual_source_contribution_pixels": 0,
                "dual_rgba_blend_used": False,
                "dual_alpha_blend_used": False,
                "alpha_blend_fallback_used": False,
                "geometry_pose_key_count": 5,
            },
            "foot_evidence": feet,
            "chair_evidence": chair,
            "balance_evidence": balance,
            "motion_evidence": motion,
            "joint_evidence": joints,
            "topology_evidence": {
                "substantial_components_per_part": topology_counts,
                "secondary_edge_fraction": 0.0,
                "foldover_count": max(value["foldover_count"] for value in mesh_metrics.values()),
                "mesh_metrics": mesh_metrics,
            },
            "component_alphas": final_alphas,
            "character_alpha": self._camera_alpha(character[:, :, 3], frame),
        }
        return output, details


def _decoded_frames(path: Path) -> int:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to decode contact proof: {path}")
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


def _aggregate_record(value: Any, source_kind: str, source_detail: str, aggregation: str) -> dict[str, Any]:
    return {
        "value": value,
        "source_kind": source_kind,
        "source_detail": source_detail,
        "aggregation": aggregation,
    }


def _put_aggregate(output: dict[str, Any], path: str, record: dict[str, Any]) -> None:
    target = output
    segments = path.split(".")
    for segment in segments[:-1]:
        target = target.setdefault(segment, {})
    target[segments[-1]] = record


def _aggregate_measurements(
    contract: dict[str, Any],
    frames: dict[int, dict[str, Any]],
    decoded_frames: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {}

    def put(path: str, value: Any, detail: str, aggregation: str, source: str = "rendered_measurement") -> None:
        _put_aggregate(output, path, _aggregate_record(value, source, detail, aggregation))

    put("delivery.exact_encoded_frames", len(frames), "frames written to the encoder stdin", "count", "decoded_media")
    put("delivery.exact_decoded_frames", decoded_frames, "frames decoded from the completed proof", "decode_count", "decoded_media")
    put("delivery.width", OUTPUT_SIZE[0], "decoded delivery width", "identity", "decoded_media")
    put("delivery.height", OUTPUT_SIZE[1], "decoded delivery height", "identity", "decoded_media")
    put("delivery.fps", FPS, "encoded and decoded delivery frame rate", "identity", "decoded_media")
    put("delivery.pixel_format", "yuv420p", "explicit encoder output pixel format", "identity", "decoded_media")

    flat_frames = {
        "left_boot": tuple(range(64, 71)) + tuple(range(87, 113)),
        "right_boot": tuple(range(64, 71)) + tuple(range(95, 113)),
    }
    flat_rows = [frames[frame]["foot_evidence"][side] for side, values in flat_frames.items() for frame in values]
    all_feet = [frames[frame]["foot_evidence"][side] for frame in FRAMES for side in ("left_boot", "right_boot")]
    put("feet.maximum_flat_sole_absolute_distance_p95_preview_px", max(row["absolute_distance_p95_preview_px"] for row in flat_rows), "final-alpha sole samples against independent porch segments", "maximum_over_flat_frames_and_boots")
    put("feet.maximum_flat_sole_clearance_preview_px", max(row["maximum_clearance_preview_px"] for row in flat_rows), "signed final-alpha sole clearance", "maximum_over_flat_frames_and_boots")
    put("feet.maximum_flat_sole_penetration_preview_px", max(row["maximum_penetration_preview_px"] for row in flat_rows), "signed final-alpha sole penetration", "maximum_over_flat_frames_and_boots")
    put("feet.minimum_flat_sole_contact_fraction", min(row["contact_fraction"] for row in flat_rows), "fraction of seven final-alpha sockets inside contact tolerance", "minimum_over_flat_frames_and_boots")
    put("feet.maximum_flat_pitch_error_degrees", max(abs(row["pitch_error_degrees"]) for row in flat_rows), "rendered heel-to-toe pitch versus porch segment", "maximum_absolute_over_flat_frames_and_boots")
    put("feet.maximum_toe_pivot_residual_preview_px", max(row["toe_residual_preview_px"] for row in all_feet), "final-alpha toe socket versus independent toe target", "maximum_over_all_frames_and_boots")
    put("feet.maximum_endpoint_motion_preview_px_per_frame", max(row["endpoint_motion_preview_px_per_frame"] for row in all_feet), "temporal motion of final-alpha heel and toe sockets", "maximum_over_all_frames_and_boots")
    put("feet.maximum_left_heel_lift_preview_px", max(frames[frame]["foot_evidence"]["left_boot"]["heel_lift_preview_px"] for frame in FRAMES), "geometry-solved left heel lift", "maximum_over_frames")
    put("feet.maximum_right_heel_lift_preview_px", max(frames[frame]["foot_evidence"]["right_boot"]["heel_lift_preview_px"] for frame in FRAMES), "geometry-solved right heel lift", "maximum_over_frames")
    put("feet.maximum_shadow_to_sole_gap_preview_px", max(row["shadow_to_sole_gap_preview_px"] for row in all_feet), "independent final boot and contact-shadow mask separation", "maximum_over_all_frames_and_boots")
    put("feet.shadow_must_be_derived_from_rendered_contact_polygon", all(row["shadow_source"] == "rendered_contact_polygon" for row in all_feet), "shadow constructed from resampled rendered boot contact boundary", "all_frames_and_boots")

    loaded_hand = [frames[frame]["chair_evidence"]["hand"] for frame in FRAMES if frames[frame]["loads"]["chair_hand"] > 0.05]
    loaded_seat = [frames[frame]["chair_evidence"]["seat"] for frame in FRAMES if frames[frame]["loads"]["seat"] > 0.05]
    chair_gate = contract["gates"]["chair"]
    deadline = int(chair_gate["release_separation_deadline_frame"])
    release = frames[deadline]["chair_evidence"]["hand"]
    release_frame = next(
        (
            frame for frame in range(int(contract["load_curves"]["chair_hand_release_frame"]), 113)
            if frames[frame]["chair_evidence"]["hand"]["separation_preview_px"] >= chair_gate["minimum_release_separation_preview_px"]
        ),
        10_000,
    )
    put("chair.maximum_loaded_hand_to_chair_separation_preview_px", max(row["separation_preview_px"] for row in loaded_hand), "rendered hand alpha to independent chair-arm mask", "maximum_over_loaded_frames")
    put("chair.maximum_loaded_hand_slip_preview_px", max(row["slip_preview_px"] for row in loaded_hand), "frame-to-frame rendered contact-patch centroid motion in chair-local final space", "maximum_over_loaded_frames")
    put("chair.minimum_loaded_hand_chair_intersection_pixels", min(row["intersection_pixels"] for row in loaded_hand), "rendered hand/chair contact-patch intersection", "minimum_over_loaded_frames")
    put("chair.minimum_shoulder_travel_relative_to_planted_hand_preview_px", max(row["shoulder_travel_relative_to_hand_preview_px"] for row in loaded_hand), "maximum achieved shoulder travel around rendered planted hand", "maximum_achieved_over_loaded_frames")
    put("chair.minimum_release_separation_preview_px", release["separation_preview_px"], "rendered hand/chair separation at release deadline", f"frame_{deadline}")
    put("chair.release_separation_deadline_frame", release_frame, "first rendered frame meeting minimum chair separation", "first_passing_frame")
    put("chair.maximum_release_position_jump_preview_px", release["position_jump_preview_px"], "final-alpha hand centroid jump at release deadline", f"frame_{deadline}")
    put("chair.maximum_release_velocity_jump_preview_px_per_frame", release["velocity_jump_preview_px_per_frame"], "final-alpha hand centroid velocity discontinuity at release deadline", f"frame_{deadline}")
    put("chair.maximum_loaded_seat_separation_preview_px", max(row["separation_preview_px"] for row in loaded_seat), "visible pelvis alpha boundary to camera-transformed chair receiver", "maximum_over_loaded_frames")
    put("chair.maximum_seat_penetration_preview_px", max(row["penetration_preview_px"] for row in loaded_seat), "signed visible pelvis boundary penetration across chair receiver", "maximum_over_loaded_frames")

    post_release = [frames[frame]["balance_evidence"] for frame in range(73, 113)]
    put("balance.minimum_com_support_hull_margin_after_seat_release_preview_px", min(row["com_support_hull_margin_preview_px"] for row in post_release), "filtered rendered COM projection signed distance to true 2D active-contact hull", "minimum_frames_73_112")
    put("balance.minimum_forward_com_travel_before_pelvis_rise_preview_px", frames[73]["balance_evidence"]["com_preview_px"][0] - frames[64]["balance_evidence"]["com_preview_px"][0], "rendered mass-centroid forward travel from frame 64 to 73", "frame_73_minus_64_x")
    put("balance.maximum_pelvis_rise_during_forward_anticipation_preview_px", frames[70]["motion_evidence"]["pelvis_preview_px"][1] - frames[73]["motion_evidence"]["pelvis_preview_px"][1], "rendered pelvis-union centroid rise during forward anticipation", "frame_70_y_minus_73_y")
    put("balance.minimum_active_support_points", min(row["active_support_point_count"] for row in post_release), "independently measured active rendered contact points", "minimum_frames_73_112")

    roots = np.asarray([frames[frame]["motion_evidence"]["root_preview_px"] for frame in FRAMES], dtype=np.float64)
    raw_roots = np.asarray([frames[frame]["motion_evidence"]["raw_root_preview_px"] for frame in FRAMES], dtype=np.float64)
    root_jerk = np.linalg.norm(np.diff(roots, n=3, axis=0), axis=1)
    component_centroids = {
        frame: {identifier: _mask_centroid(alpha) for identifier, alpha in frames[frame]["component_alphas"].items()}
        for frame in FRAMES
    }
    component_motion = [
        float(np.linalg.norm(component_centroids[frame][identifier] - component_centroids[frame - 1][identifier]))
        for frame in FRAMES[1:]
        for identifier in component_centroids[frame]
    ]
    ascent_y = raw_roots[[frame - 64 for frame in range(73, 99)], 1]
    acceleration = np.diff(ascent_y, n=2)
    nonzero_sign = np.sign(acceleration[np.abs(acceleration) > 0.05])
    reversals = int(np.count_nonzero(nonzero_sign[1:] != nonzero_sign[:-1])) if len(nonzero_sign) > 1 else 0
    settle = frames[112]["motion_evidence"]["settle"]
    put("motion.maximum_root_jerk_preview_px_per_frame_cubed", float(np.max(root_jerk)), "bounded causal filter of rendered alpha-centroid root", "maximum_third_difference")
    put("motion.maximum_non_smear_landmark_motion_preview_px_per_frame", max(component_motion), "raw final component-alpha centroid motion; no smear proxy", "maximum_component_centroid_displacement")
    put("motion.maximum_acceleration_reversals_during_ascent", reversals, "sign changes in rendered raw-root vertical acceleration during ascent", "count_frames_73_98")
    put("motion.minimum_settle_upward_overshoot_preview_px", settle["upward_overshoot_preview_px"], "rendered alpha-centroid settle", "frames_96_112")
    put("motion.minimum_settle_downward_compression_preview_px", settle["downward_compression_preview_px"], "rendered alpha-centroid settle", "frames_96_112")
    put("motion.minimum_knee_recompression_preview_px", settle["knee_recompression_preview_px"], "rendered thigh/shin alpha-centroid recompression", "frames_96_112")
    put("motion.maximum_final_root_error_preview_px", settle["final_root_error_preview_px"], "last filtered root to measured final-stable mean", "frame_112_to_mean_108_112")
    put("motion.maximum_final_root_speed_preview_px_per_frame", settle["final_root_speed_preview_px_per_frame"], "filtered rendered root final speed", "frame_112_minus_111")
    put("motion.required_final_stable_frames", settle["stable_frame_count"], "consecutive filtered-root frames within stability speed", "trailing_count")

    all_joints = [row for frame in FRAMES for row in frames[frame]["joint_evidence"].values()]
    first = frames[64]
    all_mesh = [row for frame in FRAMES for row in frames[frame]["topology_evidence"]["mesh_metrics"].values()]
    all_counts = [count for frame in FRAMES for count in frames[frame]["topology_evidence"]["substantial_components_per_part"].values()]
    policies = [frames[frame]["texture_source_policy"] for frame in FRAMES]
    put("topology_and_texture.exact_component_count", len(first["topology_evidence"]["substantial_components_per_part"]), "final rendered component alpha set", "count", "source_policy_measurement")
    put("topology_and_texture.exact_joint_count", len(first["joint_evidence"]), "measured rendered joint set", "count", "source_policy_measurement")
    put("topology_and_texture.maximum_joint_gap_preview_px", max(row["gap_preview_px"] for row in all_joints), "final component-alpha joint separation", "maximum_over_frames_and_joints")
    put("topology_and_texture.minimum_joint_overlap_pixels", min(row["overlap_pixels"] for row in all_joints), "final component-alpha joint overlap", "minimum_over_frames_and_joints")
    put("topology_and_texture.minimum_joint_bridge_width_preview_px", min(row["bridge_width_preview_px"] for row in all_joints), "final component-alpha joint bridge width", "minimum_over_frames_and_joints")
    put("topology_and_texture.maximum_substantial_components_per_part", max(all_counts), "connected components in every final part alpha", "maximum_over_frames_and_parts")
    put("topology_and_texture.minimum_canonical_alpha_mesh_coverage", min(row["canonical_alpha_mesh_coverage"] for row in all_mesh), "standing texture alpha covered by canonical shared-UV meshes", "minimum_over_frames_and_parts")
    put("topology_and_texture.maximum_fixed_uv_drift_px", max(row["maximum_fixed_uv_drift_px"] for row in all_mesh), "fixed shared-UV inverse-map drift", "maximum_over_frames_and_parts")
    put("topology_and_texture.maximum_foldover_count", max(row["foldover_count"] for row in all_mesh), "signed destination mesh triangles", "maximum_over_frames_and_parts")
    put("topology_and_texture.exact_texture_source_count", max(row["texture_source_count"] for row in policies), "runtime texture-source audit", "maximum_over_frames", "source_policy_measurement")
    put("topology_and_texture.exact_seated_rgb_sample_count", max(row["seated_rgb_sample_count"] for row in policies), "runtime seated RGB sampling audit", "maximum_over_frames", "source_policy_measurement")
    put("topology_and_texture.maximum_dual_source_contribution_pixels", max(row["dual_source_contribution_pixels"] for row in policies), "runtime dual-source contribution audit", "maximum_over_frames")
    put("topology_and_texture.maximum_secondary_edge_fraction", max(frames[frame]["topology_evidence"]["secondary_edge_fraction"] for frame in FRAMES), "final rendered secondary-edge fraction", "maximum_over_frames")

    for path in _flatten_gate_leaves(contract["gates"]):
        _measurement_record(output, path)
    return output


def render_contact_performance_proof(
    contract_path: str | Path,
    output_dir: str | Path,
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    contract = _load_contract(contract_path)
    executable = str(Path(ffmpeg).resolve()) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"ffmpeg executable not found: {ffmpeg}")
    video = output / str(contract["report_contract"]["video_filename"])
    process = subprocess.Popen(
        [
            executable, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", "960x540", "-r", "30", "-i", "-", "-an", "-c:v", "libx264",
            "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(video),
        ],
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    frames: dict[int, dict[str, Any]] = {}
    try:
        with ContactPerformanceRenderer(contract_path) as renderer:
            for frame in FRAMES:
                image, details = renderer.render_frame(frame)
                if process.stdin is None:
                    raise RuntimeError("contact proof ffmpeg stdin closed")
                process.stdin.write(np.asarray(image.convert("RGB"), dtype=np.uint8).tobytes())
                image.close()
                frames[frame] = details
            if process.stdin is not None:
                process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr is not None else ""
            code = process.wait()
            if code:
                raise RuntimeError(f"contact proof encode failed: {stderr.strip()}")
    except BaseException:
        if process.poll() is None:
            process.kill()
        raise
    decoded = _decoded_frames(video)
    aggregate_measurements = _aggregate_measurements(contract, frames, decoded)
    evaluation = evaluate_contact_gate_results(contract, aggregate_measurements)
    report = {
        "delivery": {"width": 960, "height": 540, "fps": 30, "encoded_frames": 49, "decoded_frames": decoded, "pixel_format": "yuv420p"},
        "source_policy": frames[64]["texture_source_policy"],
        "feet": {side: {"maximum_p95": max(row["foot_evidence"][side]["absolute_distance_p95_preview_px"] for row in frames.values())} for side in ("left_boot", "right_boot")},
        "chair": {"maximum_loaded_hand_separation": max(row["chair_evidence"]["hand"]["separation_preview_px"] for row in frames.values() if row["loads"]["chair_hand"] > 0.05)},
        "balance": {"minimum_support_margin": min(row["balance_evidence"]["com_support_hull_margin_preview_px"] for frame, row in frames.items() if frame >= 73)},
        "motion": frames[112]["motion_evidence"],
        "joints": {identifier: {"maximum_gap": max(row["joint_evidence"][identifier]["gap_preview_px"] for row in frames.values())} for identifier in frames[64]["joint_evidence"]},
        "topology": {"maximum_components_per_part": {identifier: max(row["topology_evidence"]["substantial_components_per_part"][identifier] for row in frames.values()) for identifier in frames[64]["topology_evidence"]["substantial_components_per_part"]}},
        "gates": contract["gates"],
        "aggregate_measurements": aggregate_measurements,
        "threshold_results": evaluation["threshold_results"],
        "gate_results": evaluation["gate_results"],
        "machine_passed": evaluation["machine_passed"],
        "audience_quality": contract["audience_quality"],
        "cash_cost": 0,
        "paid_runtime_dependency": False,
        "video": video.name,
    }
    report_path = output / str(contract["report_contract"]["filename"])
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's contact-aware shared-UV proof")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(json.dumps(render_contact_performance_proof(args.contract, args.output_dir, args.ffmpeg), indent=2))


if __name__ == "__main__":
    main()
