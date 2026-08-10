"""Bounded semantic-part transition proof for June's GS030 frames 88--94.

The Phase 29 corrective drawings are whole-figure RGBA plates.  This module
tests a possible promotion path without pretending that those plates are
already a production puppet: it deterministically partitions the registered
POSE_50 and POSE_75 foregrounds, reconstructs each source pixel-exactly, then
warps and blends each semantic part independently in premultiplied RGBA.

Only foreground pixels participate.  The CLI places the transparent result on
a checkerboard *after* rendering for review; no porch/background pixels are
loaded, warped, or blended by the transition.
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
from PIL import Image, ImageDraw, ImageFont

from pipeline.cartoon_deformable_performance_3q import (
    _registered_point,
    load_deformable_performance_contract,
)
from pipeline.cartoon_pose_layers import load_pose_layer_contract, registered_pose_layer


PROOF_FRAMES = tuple(range(88, 95))
TRANSITION_MODES = (
    "canonical_single_texture_cage",
    "staggered_corrective_activation",
    "blended_corrective_crossfade",
)
PART_IDS = (
    "head_neck",
    "torso_pelvis",
    "left_arm",
    "left_hand",
    "right_arm",
    "right_hand",
    "left_leg",
    "left_boot",
    "right_leg",
    "right_boot",
    "mug",
    "residual",
)
CONTACT_PARTS = ("left_hand", "right_hand", "left_boot", "right_boot", "mug")
PART_BONES = {
    "head_neck": ("neck", "head"),
    "torso_pelvis": ("pelvis", "chest"),
    "left_arm": ("left_shoulder", "left_elbow"),
    "left_hand": ("left_elbow", "left_hand"),
    "right_arm": ("right_shoulder", "right_elbow"),
    "right_hand": ("right_elbow", "right_hand"),
    "left_leg": ("left_hip", "left_ankle"),
    "left_boot": ("left_ankle", "left_foot"),
    "right_leg": ("right_hip", "right_ankle"),
    "right_boot": ("right_ankle", "right_foot"),
    "mug": ("right_hand", "mug_center"),
    "residual": ("pelvis", "chest"),
}
PART_RADII = {
    "head_neck": 78.0,
    "torso_pelvis": 136.0,
    "left_arm": 68.0,
    "left_hand": 47.0,
    "right_arm": 65.0,
    "right_hand": 43.0,
    "left_leg": 76.0,
    "left_boot": 53.0,
    "right_leg": 74.0,
    "right_boot": 52.0,
    "mug": 48.0,
}
PART_Z_ORDER = (
    "residual",
    "left_leg",
    "right_leg",
    "left_boot",
    "right_boot",
    "torso_pelvis",
    "left_arm",
    "right_arm",
    "head_neck",
    "mug",
    "left_hand",
    "right_hand",
)
ADJACENT_PARTS = (
    ("head_neck", "torso_pelvis"),
    ("left_arm", "torso_pelvis"),
    ("right_arm", "torso_pelvis"),
    ("left_arm", "left_hand"),
    ("right_arm", "right_hand"),
    ("left_leg", "torso_pelvis"),
    ("right_leg", "torso_pelvis"),
    ("left_leg", "left_boot"),
    ("right_leg", "right_boot"),
    ("right_hand", "mug"),
)
STAGGERED_SWITCH_FRAME = {
    # Load-bearing feet travel as leg+boot units near the start of peak motion.
    "left_leg": 89,
    "left_boot": 89,
    "right_leg": 90,
    "right_boot": 90,
    # Residual includes chair/garment overlap pixels; move it with the core.
    "torso_pelvis": 91,
    "residual": 91,
    # Each arm/hand system changes as one anatomical unit.  The mug never
    # changes independently of the hand that holds it.
    "left_arm": 91,
    "left_hand": 91,
    "right_arm": 92,
    "right_hand": 92,
    "mug": 92,
    # Identity switches last, after the peak body motion.
    "head_neck": 93,
}
CAGE_PART_IDS = (
    "head_neck",
    "torso_pelvis",
    "left_upper_arm",
    "left_forearm_hand",
    "right_upper_arm",
    "right_forearm_hand",
    "left_thigh",
    "left_shin",
    "left_boot",
    "right_thigh",
    "right_shin",
    "right_boot",
    "mug",
    "residual",
)
CAGE_CONTACT_PARTS = ("left_forearm_hand", "right_forearm_hand", "left_boot", "right_boot", "mug")
CAGE_BONES = {
    "head_neck": ("neck", "head"),
    "torso_pelvis": ("pelvis", "chest"),
    "left_upper_arm": ("left_shoulder", "left_elbow"),
    "left_forearm_hand": ("left_elbow", "left_hand"),
    "right_upper_arm": ("right_shoulder", "right_elbow"),
    "right_forearm_hand": ("right_elbow", "right_hand"),
    "left_thigh": ("left_hip", "left_knee"),
    "left_shin": ("left_knee", "left_ankle"),
    "left_boot": ("left_ankle", "left_foot"),
    "right_thigh": ("right_hip", "right_knee"),
    "right_shin": ("right_knee", "right_ankle"),
    "right_boot": ("right_ankle", "right_foot"),
    "mug": ("right_hand", "mug_center"),
    "residual": ("pelvis", "chest"),
}
CAGE_RADII = {
    "head_neck": 78.0,
    "torso_pelvis": 136.0,
    "left_upper_arm": 68.0,
    "left_forearm_hand": 58.0,
    "right_upper_arm": 65.0,
    "right_forearm_hand": 55.0,
    "left_thigh": 78.0,
    "left_shin": 68.0,
    "left_boot": 53.0,
    "right_thigh": 76.0,
    "right_shin": 66.0,
    "right_boot": 52.0,
    "mug": 48.0,
}
CAGE_Z_ORDER = (
    "residual",
    "left_thigh",
    "right_thigh",
    "left_shin",
    "right_shin",
    "left_boot",
    "right_boot",
    "torso_pelvis",
    "left_upper_arm",
    "right_upper_arm",
    "head_neck",
    "left_forearm_hand",
    "right_forearm_hand",
    "mug",
)
CAGE_ADJACENCIES = (
    ("head_neck", "torso_pelvis"),
    ("left_upper_arm", "torso_pelvis"),
    ("left_upper_arm", "left_forearm_hand"),
    ("right_upper_arm", "torso_pelvis"),
    ("right_upper_arm", "right_forearm_hand"),
    ("left_thigh", "torso_pelvis"),
    ("left_thigh", "left_shin"),
    ("left_shin", "left_boot"),
    ("right_thigh", "torso_pelvis"),
    ("right_thigh", "right_shin"),
    ("right_shin", "right_boot"),
    ("right_forearm_hand", "mug"),
)


@dataclass(frozen=True)
class PoseTopology:
    pose_id: str
    rgba: np.ndarray
    landmarks: dict[str, np.ndarray]
    parts: dict[str, np.ndarray]


@dataclass(frozen=True)
class TransitionInputs:
    contract_path: Path
    width: int
    height: int
    landmark_order: tuple[str, ...]
    start: PoseTopology
    end: PoseTopology
    cage_start_parts: dict[str, np.ndarray]
    cage_underlap_layers: dict[str, np.ndarray]


def _distance_to_segment_squared(
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
) -> np.ndarray:
    vector = end - start
    denominator = max(float(np.dot(vector, vector)), 1e-6)
    amount = ((grid_x - float(start[0])) * float(vector[0]) + (grid_y - float(start[1])) * float(vector[1])) / denominator
    amount = np.clip(amount, 0.0, 1.0)
    nearest_x = float(start[0]) + amount * float(vector[0])
    nearest_y = float(start[1]) + amount * float(vector[1])
    return (grid_x - nearest_x) ** 2 + (grid_y - nearest_y) ** 2


def _keep_seed_component(
    labels: np.ndarray,
    alpha: np.ndarray,
    part_index: int,
    seed: np.ndarray,
    residual_index: int,
) -> None:
    binary = np.asarray((labels == part_index) & (alpha > 8), dtype=np.uint8)
    count, components, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 2:
        return
    candidates = list(range(1, count))
    seed_point = np.asarray(seed, dtype=np.float32)
    keeper = min(candidates, key=lambda value: float(np.linalg.norm(centroids[value] - seed_point)))
    for component in candidates:
        if component != keeper and int(stats[component, cv2.CC_STAT_AREA]) >= 3:
            labels[components == component] = residual_index


def partition_semantic_parts(
    rgba: np.ndarray,
    landmarks: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Assign every nonzero-alpha source pixel to exactly one semantic part."""
    if rgba.ndim != 3 or rgba.shape[2] != 4 or rgba.dtype != np.uint8:
        raise ValueError("semantic partition expects a uint8 RGBA image")
    height, width = rgba.shape[:2]
    alpha = rgba[:, :, 3]
    grid_y, grid_x = np.indices((height, width), dtype=np.float32)
    residual_index = PART_IDS.index("residual")
    labels = np.full((height, width), residual_index, dtype=np.int16)
    best = np.full((height, width), 1.18, dtype=np.float32)

    # The order only resolves exact score ties.  All ownership is based on
    # registered anatomy, not color, so lighting/texture cannot move a seam.
    for part_index, part_id in enumerate(PART_IDS[:-1]):
        first_id, second_id = PART_BONES[part_id]
        score = _distance_to_segment_squared(
            grid_x,
            grid_y,
            landmarks[first_id],
            landmarks[second_id],
        ) / (PART_RADII[part_id] ** 2)
        # Contact objects need compact ownership near the terminal socket.
        if part_id in {"left_hand", "right_hand", "mug"}:
            terminal = landmarks[second_id]
            radial = ((grid_x - terminal[0]) ** 2 + (grid_y - terminal[1]) ** 2) / (PART_RADII[part_id] ** 2)
            score = np.minimum(score + 0.12, radial)
        update = (alpha > 0) & (score < best)
        labels[update] = part_index
        best[update] = score[update]

    # Speckles that are geometrically close but disconnected from a contact
    # socket belong to residual artwork, not to the articulated contact part.
    for part_id, seed_id in (
        ("left_hand", "left_hand"),
        ("right_hand", "right_hand"),
        ("left_boot", "left_foot"),
        ("right_boot", "right_foot"),
        ("mug", "mug_center"),
    ):
        _keep_seed_component(labels, alpha, PART_IDS.index(part_id), landmarks[seed_id], residual_index)

    parts: dict[str, np.ndarray] = {}
    for part_index, part_id in enumerate(PART_IDS):
        owned = (labels == part_index) & (alpha > 0)
        part = np.zeros_like(rgba)
        part[owned] = rgba[owned]
        parts[part_id] = part
    return parts


def reconstruct_parts(parts: dict[str, np.ndarray]) -> np.ndarray:
    if set(parts) == set(PART_IDS):
        order = PART_IDS
    elif set(parts) == set(CAGE_PART_IDS):
        order = CAGE_PART_IDS
    else:
        raise ValueError("semantic parts are incomplete")
    shape = parts[order[0]].shape
    result = np.zeros(shape, dtype=np.uint16)
    occupancy = np.zeros(shape[:2], dtype=np.uint8)
    for part_id in order:
        part = parts[part_id]
        if part.shape != shape or part.dtype != np.uint8:
            raise ValueError("semantic part dimensions or dtype changed")
        present = part[:, :, 3] > 0
        if np.any(occupancy[present]):
            raise ValueError("semantic part ownership overlaps")
        occupancy[present] = 1
        result += part.astype(np.uint16)
    if int(result.max()) > 255:
        raise ValueError("semantic part channel sum overflowed")
    return result.astype(np.uint8)


def partition_canonical_cage_parts(
    rgba: np.ndarray,
    landmarks: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """Losslessly split the canonical plate into articulated cage segments."""
    height, width = rgba.shape[:2]
    alpha = rgba[:, :, 3]
    grid_y, grid_x = np.indices((height, width), dtype=np.float32)
    residual_index = CAGE_PART_IDS.index("residual")
    labels = np.full((height, width), residual_index, dtype=np.int16)
    best = np.full((height, width), 1.18, dtype=np.float32)
    for part_index, part_id in enumerate(CAGE_PART_IDS[:-1]):
        first_id, second_id = CAGE_BONES[part_id]
        score = _distance_to_segment_squared(
            grid_x,
            grid_y,
            landmarks[first_id],
            landmarks[second_id],
        ) / (CAGE_RADII[part_id] ** 2)
        if part_id in {"left_forearm_hand", "right_forearm_hand", "mug"}:
            terminal = landmarks[second_id]
            radial = ((grid_x - terminal[0]) ** 2 + (grid_y - terminal[1]) ** 2) / (CAGE_RADII[part_id] ** 2)
            score = np.minimum(score + 0.10, radial)
        update = (alpha > 0) & (score < best)
        labels[update] = part_index
        best[update] = score[update]
    for part_id, seed_id in (
        ("left_forearm_hand", "left_hand"),
        ("right_forearm_hand", "right_hand"),
        ("left_boot", "left_foot"),
        ("right_boot", "right_foot"),
        ("mug", "mug_center"),
    ):
        _keep_seed_component(labels, alpha, CAGE_PART_IDS.index(part_id), landmarks[seed_id], residual_index)
    result: dict[str, np.ndarray] = {}
    for part_index, part_id in enumerate(CAGE_PART_IDS):
        part = np.zeros_like(rgba)
        owned = (labels == part_index) & (alpha > 0)
        part[owned] = rgba[owned]
        result[part_id] = part
    return result


def canonical_cage_underlap_layers(
    rgba: np.ndarray,
    parts: dict[str, np.ndarray],
    *,
    underlap_px: int = 4,
) -> dict[str, np.ndarray]:
    """Grow same-texture joint coverage without introducing new art pixels."""
    if not 3 <= underlap_px <= 5:
        raise ValueError("canonical cage joint underlap must remain 3 through 5 pixels")
    source_present = rgba[:, :, 3] > 0
    kernel_size = underlap_px * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    layers: dict[str, np.ndarray] = {}
    for part_id in CAGE_PART_IDS:
        owner = np.asarray(parts[part_id][:, :, 3] > 0, dtype=np.uint8)
        if part_id == "residual":
            expanded = owner > 0
        else:
            expanded = (cv2.dilate(owner, kernel, iterations=1) > 0) & source_present
        layer = np.zeros_like(rgba)
        layer[expanded] = rgba[expanded]
        layers[part_id] = layer
    return layers


def load_transition_inputs(contract_path: str | Path) -> TransitionInputs:
    contract_file = Path(contract_path).resolve()
    contract, assets = load_deformable_performance_contract(contract_file)
    control, _, _ = load_pose_layer_contract(assets["gs030_control"])
    pose_by_id = {str(pose["id"]): pose for pose in control["poses"]}
    anchors = {float(row["progress"]): row for row in contract["runtime_asset_pack"]["corrective_sources"]}
    landmark_order = tuple(str(value) for value in contract["runtime_asset_pack"]["landmark_order"])

    def load_pose(progress: float) -> PoseTopology:
        anchor = anchors[progress]
        pose_id = str(anchor["pose_id"])
        pose = pose_by_id[pose_id]
        source = Image.open(assets[str(anchor["source_role"])]).convert("RGBA")
        try:
            registered, _ = registered_pose_layer(source, pose, control["contact_registration"])
        finally:
            source.close()
        rgba = np.asarray(registered, dtype=np.uint8).copy()
        registered.close()
        landmarks = {
            identifier: _registered_point(anchor["landmarks"][identifier], pose, control["contact_registration"])
            for identifier in landmark_order
        }
        parts = partition_semantic_parts(rgba, landmarks)
        if not np.array_equal(reconstruct_parts(parts), rgba):
            raise RuntimeError(f"{pose_id} semantic partition is not lossless")
        return PoseTopology(pose_id=pose_id, rgba=rgba, landmarks=landmarks, parts=parts)

    start = load_pose(0.5)
    end = load_pose(0.75)
    cage_parts = partition_canonical_cage_parts(start.rgba, start.landmarks)
    if not np.array_equal(reconstruct_parts(cage_parts), start.rgba):
        raise RuntimeError("canonical cage partition is not lossless")
    return TransitionInputs(
        contract_path=contract_file,
        width=int(contract["source_canvas"]["width"]),
        height=int(contract["source_canvas"]["height"]),
        landmark_order=landmark_order,
        start=start,
        end=end,
        cage_start_parts=cage_parts,
        cage_underlap_layers=canonical_cage_underlap_layers(start.rgba, cage_parts, underlap_px=4),
    )


def _ease_in_out(value: float) -> float:
    value = min(1.0, max(0.0, float(value)))
    return value * value * (3.0 - 2.0 * value)


def _similarity_affine(
    source_start: np.ndarray,
    source_end: np.ndarray,
    target_start: np.ndarray,
    target_end: np.ndarray,
) -> tuple[np.ndarray, float]:
    source_vector = np.asarray(source_end - source_start, dtype=np.float64)
    target_vector = np.asarray(target_end - target_start, dtype=np.float64)
    source_norm = float(np.linalg.norm(source_vector))
    target_norm = float(np.linalg.norm(target_vector))
    if source_norm < 1e-4 or target_norm < 1e-4:
        raise ValueError("semantic bone collapsed while building affine")
    scale = target_norm / source_norm
    cosine = float(np.dot(source_vector, target_vector) / (source_norm * target_norm))
    sine = float((source_vector[0] * target_vector[1] - source_vector[1] * target_vector[0]) / (source_norm * target_norm))
    linear = scale * np.asarray([[cosine, -sine], [sine, cosine]], dtype=np.float64)
    translation = np.asarray(target_start, dtype=np.float64) - linear @ np.asarray(source_start, dtype=np.float64)
    matrix = np.concatenate((linear, translation[:, None]), axis=1).astype(np.float32)
    return matrix, float(np.linalg.det(linear))


def semantic_part_affines(
    source_landmarks: dict[str, np.ndarray],
    target_landmarks: dict[str, np.ndarray],
) -> dict[str, tuple[np.ndarray, float]]:
    result: dict[str, tuple[np.ndarray, float]] = {}
    for part_id in PART_IDS:
        first_id, second_id = PART_BONES[part_id]
        result[part_id] = _similarity_affine(
            source_landmarks[first_id],
            source_landmarks[second_id],
            target_landmarks[first_id],
            target_landmarks[second_id],
        )
    return result


def canonical_cage_affines(
    source_landmarks: dict[str, np.ndarray],
    target_landmarks: dict[str, np.ndarray],
) -> dict[str, tuple[np.ndarray, float]]:
    result: dict[str, tuple[np.ndarray, float]] = {}
    for part_id in CAGE_PART_IDS:
        first_id, second_id = CAGE_BONES[part_id]
        result[part_id] = _similarity_affine(
            source_landmarks[first_id],
            source_landmarks[second_id],
            target_landmarks[first_id],
            target_landmarks[second_id],
        )
    return result


def _premultiplied(part: np.ndarray) -> np.ndarray:
    result = part.astype(np.float32) / 255.0
    result[:, :, :3] *= result[:, :, 3:4]
    return result


def _warp_part(part: np.ndarray, matrix: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return cv2.warpAffine(
        _premultiplied(part),
        matrix,
        size,
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )


def _premultiplied_to_rgba(data: np.ndarray) -> np.ndarray:
    alpha = np.clip(data[:, :, 3:4], 0.0, 1.0)
    rgb = np.zeros_like(data[:, :, :3])
    np.divide(data[:, :, :3], np.maximum(alpha, 1e-6), out=rgb, where=alpha > 1e-6)
    return np.round(np.concatenate((np.clip(rgb, 0.0, 1.0), alpha), axis=2) * 255.0).astype(np.uint8)


def _over(destination: np.ndarray, source: np.ndarray) -> np.ndarray:
    result = np.empty_like(destination)
    inverse = 1.0 - np.clip(source[:, :, 3:4], 0.0, 1.0)
    result[:, :, :3] = source[:, :, :3] + destination[:, :, :3] * inverse
    result[:, :, 3:4] = source[:, :, 3:4] + destination[:, :, 3:4] * inverse
    return result


def _transform_point(matrix: np.ndarray, point: np.ndarray) -> np.ndarray:
    return matrix[:, :2] @ np.asarray(point, dtype=np.float32) + matrix[:, 2]


def _render_canonical_cage_frame(
    inputs: TransitionInputs,
    frame: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    linear_amount = (frame - PROOF_FRAMES[0]) / (PROOF_FRAMES[-1] - PROOF_FRAMES[0])
    amount = _ease_in_out(linear_amount)
    target_landmarks = {
        identifier: inputs.start.landmarks[identifier] * (1.0 - amount) + inputs.end.landmarks[identifier] * amount
        for identifier in inputs.landmark_order
    }
    if frame == PROOF_FRAMES[0]:
        return reconstruct_parts(inputs.cage_start_parts), {
            "frame": frame,
            "amount": 0.0,
            "part_alphas": {part_id: inputs.cage_start_parts[part_id][:, :, 3].copy() for part_id in CAGE_PART_IDS},
            "affine_determinants": {part_id: [1.0] for part_id in CAGE_PART_IDS},
            "part_source_weights": {part_id: {"start": 1.0, "end": 0.0} for part_id in CAGE_PART_IDS},
            "socket_errors_px": {part_id: [0.0, 0.0] for part_id in CAGE_PART_IDS},
        }

    affines = canonical_cage_affines(inputs.start.landmarks, target_landmarks)
    canvas = np.zeros((inputs.height, inputs.width, 4), dtype=np.float32)
    warped_parts: dict[str, np.ndarray] = {}
    part_alphas: dict[str, np.ndarray] = {}
    determinants: dict[str, list[float]] = {}
    socket_errors: dict[str, list[float]] = {}
    for part_id in CAGE_PART_IDS:
        matrix, determinant = affines[part_id]
        warped = np.clip(
            _warp_part(inputs.cage_underlap_layers[part_id], matrix, (inputs.width, inputs.height)),
            0.0,
            1.0,
        )
        warped_parts[part_id] = warped
        part_alphas[part_id] = np.round(warped[:, :, 3] * 255.0).astype(np.uint8)
        determinants[part_id] = [determinant]
        first_id, second_id = CAGE_BONES[part_id]
        socket_errors[part_id] = [
            float(np.linalg.norm(_transform_point(matrix, inputs.start.landmarks[identifier]) - target_landmarks[identifier]))
            for identifier in (first_id, second_id)
        ]
    for part_id in CAGE_Z_ORDER:
        canvas = _over(canvas, warped_parts[part_id])
    return _premultiplied_to_rgba(canvas), {
        "frame": frame,
        "amount": amount,
        "part_alphas": part_alphas,
        "affine_determinants": determinants,
        "part_source_weights": {part_id: {"start": 1.0, "end": 0.0} for part_id in CAGE_PART_IDS},
        "socket_errors_px": socket_errors,
    }


def render_transition_frame(
    inputs: TransitionInputs,
    frame: int,
    *,
    mode: str = "staggered_corrective_activation",
) -> tuple[np.ndarray, dict[str, Any]]:
    if frame not in PROOF_FRAMES:
        raise ValueError("topology proof frame must be 88 through 94")
    if mode not in TRANSITION_MODES:
        raise ValueError(f"unsupported topology transition mode: {mode}")
    if mode == "canonical_single_texture_cage":
        return _render_canonical_cage_frame(inputs, frame)
    linear_amount = (frame - PROOF_FRAMES[0]) / (PROOF_FRAMES[-1] - PROOF_FRAMES[0])
    amount = _ease_in_out(linear_amount)
    if frame == PROOF_FRAMES[0]:
        return reconstruct_parts(inputs.start.parts), {
            "frame": frame,
            "amount": 0.0,
            "part_alphas": {part_id: inputs.start.parts[part_id][:, :, 3].copy() for part_id in PART_IDS},
            "alignment_alphas": {},
            "affine_determinants": {part_id: [1.0, 1.0] for part_id in PART_IDS},
            "part_source_weights": {part_id: {"start": 1.0, "end": 0.0} for part_id in PART_IDS},
        }
    if frame == PROOF_FRAMES[-1]:
        return reconstruct_parts(inputs.end.parts), {
            "frame": frame,
            "amount": 1.0,
            "part_alphas": {part_id: inputs.end.parts[part_id][:, :, 3].copy() for part_id in PART_IDS},
            "alignment_alphas": {},
            "affine_determinants": {part_id: [1.0, 1.0] for part_id in PART_IDS},
            "part_source_weights": {part_id: {"start": 0.0, "end": 1.0} for part_id in PART_IDS},
        }

    target_landmarks = {
        identifier: inputs.start.landmarks[identifier] * (1.0 - amount) + inputs.end.landmarks[identifier] * amount
        for identifier in inputs.landmark_order
    }
    start_affines = semantic_part_affines(inputs.start.landmarks, target_landmarks)
    end_affines = semantic_part_affines(inputs.end.landmarks, target_landmarks)
    canvas = np.zeros((inputs.height, inputs.width, 4), dtype=np.float32)
    part_alphas: dict[str, np.ndarray] = {}
    alignment_alphas: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    determinants: dict[str, list[float]] = {}
    source_weights: dict[str, dict[str, float]] = {}
    warped_parts: dict[str, np.ndarray] = {}
    for part_id in PART_IDS:
        start_matrix, start_determinant = start_affines[part_id]
        end_matrix, end_determinant = end_affines[part_id]
        warped_start = _warp_part(inputs.start.parts[part_id], start_matrix, (inputs.width, inputs.height))
        warped_end = _warp_part(inputs.end.parts[part_id], end_matrix, (inputs.width, inputs.height))
        if mode == "staggered_corrective_activation":
            use_end = frame >= STAGGERED_SWITCH_FRAME[part_id]
            selected = warped_end if use_end else warped_start
            source_weights[part_id] = {
                "start": 0.0 if use_end else 1.0,
                "end": 1.0 if use_end else 0.0,
            }
        else:
            selected = warped_start * (1.0 - amount) + warped_end * amount
            source_weights[part_id] = {"start": 1.0 - amount, "end": amount}
        selected = np.clip(selected, 0.0, 1.0)
        warped_parts[part_id] = selected
        part_alphas[part_id] = np.round(selected[:, :, 3] * 255.0).astype(np.uint8)
        alignment_alphas[part_id] = (
            np.round(np.clip(warped_start[:, :, 3], 0.0, 1.0) * 255.0).astype(np.uint8),
            np.round(np.clip(warped_end[:, :, 3], 0.0, 1.0) * 255.0).astype(np.uint8),
        )
        determinants[part_id] = [start_determinant, end_determinant]
    for part_id in PART_Z_ORDER:
        canvas = _over(canvas, warped_parts[part_id])
    return _premultiplied_to_rgba(canvas), {
        "frame": frame,
        "amount": amount,
        "part_alphas": part_alphas,
        "alignment_alphas": alignment_alphas,
        "affine_determinants": determinants,
        "part_source_weights": source_weights,
    }


def _alpha_iou(left: np.ndarray, right: np.ndarray, threshold: int = 8) -> float:
    left_mask = left > threshold
    right_mask = right > threshold
    union = int(np.count_nonzero(left_mask | right_mask))
    if union == 0:
        return 1.0
    return int(np.count_nonzero(left_mask & right_mask)) / union


def _component_metrics(alpha: np.ndarray) -> dict[str, Any]:
    binary = np.asarray(alpha > 8, dtype=np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    areas = sorted((int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, count)), reverse=True)
    significant = [area for area in areas if area >= 12]
    total = sum(areas)
    return {
        "significant_count": len(significant),
        "dominant_fraction": (areas[0] / total) if total and areas else 0.0,
        "alpha_area": total,
    }


def _centroid(alpha: np.ndarray) -> np.ndarray | None:
    ys, xs = np.where(alpha > 8)
    if not len(xs):
        return None
    weights = alpha[ys, xs].astype(np.float64)
    return np.asarray([np.average(xs, weights=weights), np.average(ys, weights=weights)], dtype=np.float64)


def _minimum_mask_distance(left: np.ndarray, right: np.ndarray) -> float:
    left_mask = left > 8
    right_mask = right > 8
    if not np.any(left_mask) or not np.any(right_mask):
        return math.inf
    if np.any(left_mask & right_mask):
        return 0.0
    distance = cv2.distanceTransform(np.asarray(~left_mask, dtype=np.uint8), cv2.DIST_L2, 3)
    return float(np.min(distance[right_mask]))


def _frame_change_metrics(left: np.ndarray, right: np.ndarray) -> dict[str, Any]:
    delta = np.abs(right.astype(np.int16) - left.astype(np.int16))
    changed = np.any(delta > 4, axis=2)
    subject_union = (left[:, :, 3] > 8) | (right[:, :, 3] > 8)
    return {
        "changed_pixels": int(np.count_nonzero(changed)),
        "changed_pixel_fraction_full_canvas": float(np.mean(changed)),
        "changed_pixel_fraction_subject_union": float(np.mean(changed[subject_union])) if np.any(subject_union) else 0.0,
        "mean_absolute_error_full_canvas": float(np.mean(delta)),
        "mean_absolute_error_subject_union": float(np.mean(delta[subject_union])) if np.any(subject_union) else 0.0,
        "maximum_channel_error": int(np.max(delta)),
    }


def _evaluate_canonical_cage(
    inputs: TransitionInputs,
) -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    frames: dict[int, np.ndarray] = {}
    details: dict[int, dict[str, Any]] = {}
    for frame in PROOF_FRAMES:
        rendered, detail = render_transition_frame(inputs, frame, mode="canonical_single_texture_cage")
        frames[frame] = rendered
        details[frame] = detail

    start_delta = np.abs(frames[88].astype(np.int16) - inputs.start.rgba.astype(np.int16))
    end_delta = np.abs(frames[94].astype(np.int16) - inputs.end.rgba.astype(np.int16))
    determinants = [
        value
        for detail in details.values()
        for values in detail["affine_determinants"].values()
        for value in values
    ]
    socket_errors = [
        value
        for detail in details.values()
        for values in detail["socket_errors_px"].values()
        for value in values
    ]
    components: dict[str, dict[str, Any]] = {}
    maximum_gap = 0.0
    overlap_rows: list[dict[str, Any]] = []
    for frame in PROOF_FRAMES:
        part_alphas = details[frame]["part_alphas"]
        for part_id in CAGE_CONTACT_PARTS:
            metric = _component_metrics(part_alphas[part_id])
            previous = components.get(part_id)
            if previous is None:
                components[part_id] = {
                    "maximum_significant_count": metric["significant_count"],
                    "minimum_dominant_fraction": metric["dominant_fraction"],
                    "minimum_alpha_area": metric["alpha_area"],
                }
            else:
                previous["maximum_significant_count"] = max(previous["maximum_significant_count"], metric["significant_count"])
                previous["minimum_dominant_fraction"] = min(previous["minimum_dominant_fraction"], metric["dominant_fraction"])
                previous["minimum_alpha_area"] = min(previous["minimum_alpha_area"], metric["alpha_area"])
        adjacent_overlap = 0
        adjacent_union = 0
        for left_id, right_id in CAGE_ADJACENCIES:
            left = part_alphas[left_id] > 8
            right = part_alphas[right_id] > 8
            maximum_gap = max(maximum_gap, _minimum_mask_distance(part_alphas[left_id], part_alphas[right_id]))
            adjacent_overlap += int(np.count_nonzero(left & right))
            adjacent_union += int(np.count_nonzero(left | right))
        stack = np.stack([part_alphas[part_id] > 8 for part_id in CAGE_PART_IDS], axis=0)
        subject = np.any(stack, axis=0)
        multiply_covered = np.sum(stack, axis=0) > 1
        overlap_rows.append(
            {
                "frame": frame,
                "multi_part_overlap_fraction_of_subject": float(np.mean(multiply_covered[subject])) if np.any(subject) else 0.0,
                "adjacent_joint_overlap_fraction": adjacent_overlap / max(1, adjacent_union),
            }
        )

    frame_changes = []
    temporal_iou = []
    for left, right in zip(PROOF_FRAMES, PROOF_FRAMES[1:]):
        row = _frame_change_metrics(frames[left], frames[right])
        row["from_frame"] = left
        row["to_frame"] = right
        frame_changes.append(row)
        temporal_iou.append(_alpha_iou(frames[left][:, :, 3], frames[right][:, :, 3]))
    final_alpha = frames[94][:, :, 3]
    target_alpha = inputs.end.rgba[:, :, 3]
    final_area = int(np.count_nonzero(final_alpha > 8))
    target_area = int(np.count_nonzero(target_alpha > 8))
    silhouette = {
        "frame94_alpha_iou_to_pose75": _alpha_iou(final_alpha, target_alpha),
        "frame94_alpha_area_ratio_to_pose75": final_area / max(1, target_area),
        "frame94_changed_pixel_fraction_from_pose75": float(np.mean(np.any(end_delta > 4, axis=2))),
        "human_visual_review_status": "unevaluated",
    }
    thresholds = {
        "maximum_start_mismatched_pixels": 0,
        "maximum_landmark_socket_error_px": 0.05,
        "maximum_seam_gap_px": 1.5,
        "minimum_adjacent_joint_overlap_fraction": 0.002,
        "maximum_multi_part_overlap_fraction_of_subject": 0.22,
        "maximum_contact_significant_components": 1,
        "minimum_contact_dominant_component_fraction": 0.95,
        "minimum_affine_determinant": 0.50,
        "minimum_adjacent_frame_alpha_iou": 0.82,
        "minimum_frame94_silhouette_iou_to_pose75": 0.68,
        "maximum_end_source_pixel_contribution": 0,
    }
    machine_passed = (
        int(np.count_nonzero(np.any(start_delta > 0, axis=2))) <= thresholds["maximum_start_mismatched_pixels"]
        and max(socket_errors) <= thresholds["maximum_landmark_socket_error_px"]
        and maximum_gap <= thresholds["maximum_seam_gap_px"]
        and min(row["adjacent_joint_overlap_fraction"] for row in overlap_rows) >= thresholds["minimum_adjacent_joint_overlap_fraction"]
        and max(row["multi_part_overlap_fraction_of_subject"] for row in overlap_rows) <= thresholds["maximum_multi_part_overlap_fraction_of_subject"]
        and max(value["maximum_significant_count"] for value in components.values()) <= thresholds["maximum_contact_significant_components"]
        and min(value["minimum_dominant_fraction"] for value in components.values()) >= thresholds["minimum_contact_dominant_component_fraction"]
        and min(determinants) >= thresholds["minimum_affine_determinant"]
        and min(temporal_iou) >= thresholds["minimum_adjacent_frame_alpha_iou"]
        and silhouette["frame94_alpha_iou_to_pose75"] >= thresholds["minimum_frame94_silhouette_iou_to_pose75"]
    )
    report = {
        "proof": "phase29_semantic_part_transition_pose50_to_pose75",
        "mode": "canonical_single_texture_cage",
        "frame_range": [88, 94],
        "canonical_texture_source_pose": inputs.start.pose_id,
        "target_landmark_pose": inputs.end.pose_id,
        "background_pixels_loaded_or_blended": False,
        "end_source_pixel_contribution": 0,
        "transition_method": "pose50-only segmented similarity cage with four-pixel same-texture joint underlaps",
        "parts": list(CAGE_PART_IDS),
        "underlap_pixels": 4,
        "start_reconstruction": {
            "mismatched_pixels": int(np.count_nonzero(np.any(start_delta > 0, axis=2))),
            "maximum_channel_error": int(np.max(start_delta)),
        },
        "frame94_is_required_to_match_pose75_pixels": False,
        "landmark_socket_integrity": {
            "maximum_error_px": max(socket_errors),
            "mean_error_px": float(np.mean(socket_errors)),
        },
        "seam_integrity": {
            "maximum_gap_px": maximum_gap,
            "per_frame_overlap": overlap_rows,
            "maximum_multi_part_overlap_fraction_of_subject": max(row["multi_part_overlap_fraction_of_subject"] for row in overlap_rows),
            "minimum_adjacent_joint_overlap_fraction": min(row["adjacent_joint_overlap_fraction"] for row in overlap_rows),
        },
        "contact_component_integrity": components,
        "minimum_affine_determinant": min(determinants),
        "temporal_continuity": {
            "minimum_adjacent_frame_alpha_iou": min(temporal_iou),
            "per_frame_changed_pixel_and_mae": frame_changes,
            "maximum_changed_pixel_fraction_subject_union": max(row["changed_pixel_fraction_subject_union"] for row in frame_changes),
            "maximum_mean_absolute_error_subject_union": max(row["mean_absolute_error_subject_union"] for row in frame_changes),
        },
        "visual_silhouette": silhouette,
        "thresholds": thresholds,
        "machine_passed": machine_passed,
        "promotion_scope": "bounded single-texture cage feasibility evidence; human visual silhouette review remains separate",
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }
    return report, frames


def evaluate_transition(
    inputs: TransitionInputs,
    *,
    mode: str = "staggered_corrective_activation",
) -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    if mode == "canonical_single_texture_cage":
        return _evaluate_canonical_cage(inputs)
    frames: dict[int, np.ndarray] = {}
    details: dict[int, dict[str, Any]] = {}
    for frame in PROOF_FRAMES:
        rendered, detail = render_transition_frame(inputs, frame, mode=mode)
        frames[frame] = rendered
        details[frame] = detail

    endpoint_errors = {
        str(PROOF_FRAMES[0]): {
            "mismatched_pixels": int(np.count_nonzero(np.any(frames[PROOF_FRAMES[0]] != inputs.start.rgba, axis=2))),
            "maximum_channel_error": int(np.max(np.abs(frames[PROOF_FRAMES[0]].astype(np.int16) - inputs.start.rgba.astype(np.int16)))),
        },
        str(PROOF_FRAMES[-1]): {
            "mismatched_pixels": int(np.count_nonzero(np.any(frames[PROOF_FRAMES[-1]] != inputs.end.rgba, axis=2))),
            "maximum_channel_error": int(np.max(np.abs(frames[PROOF_FRAMES[-1]].astype(np.int16) - inputs.end.rgba.astype(np.int16)))),
        },
    }

    alignment: dict[str, list[float]] = {part_id: [] for part_id in PART_IDS}
    determinants: list[float] = []
    components: dict[str, dict[str, Any]] = {}
    mixed_source_parts: list[dict[str, Any]] = []
    maximum_junction_gap = 0.0
    hole_fractions: list[float] = []
    centroids: dict[str, list[np.ndarray | None]] = {part_id: [] for part_id in CONTACT_PARTS}
    for frame in PROOF_FRAMES:
        detail = details[frame]
        determinants.extend(value for pair in detail["affine_determinants"].values() for value in pair)
        for part_id, weights in detail["part_source_weights"].items():
            nonzero = sum(float(value) > 1e-8 for value in weights.values())
            unit_sum = abs(sum(float(value) for value in weights.values()) - 1.0) <= 1e-8
            unit_value = all(abs(float(value) - round(float(value))) <= 1e-8 for value in weights.values())
            if nonzero != 1 or not unit_sum or not unit_value:
                mixed_source_parts.append({"frame": frame, "part": part_id, "weights": weights})
        if detail["alignment_alphas"]:
            for part_id, (left, right) in detail["alignment_alphas"].items():
                alignment[part_id].append(_alpha_iou(left, right))
        for part_id in CONTACT_PARTS:
            metric = _component_metrics(detail["part_alphas"][part_id])
            previous = components.get(part_id)
            if previous is None:
                components[part_id] = {
                    "maximum_significant_count": metric["significant_count"],
                    "minimum_dominant_fraction": metric["dominant_fraction"],
                    "minimum_alpha_area": metric["alpha_area"],
                }
            else:
                previous["maximum_significant_count"] = max(previous["maximum_significant_count"], metric["significant_count"])
                previous["minimum_dominant_fraction"] = min(previous["minimum_dominant_fraction"], metric["dominant_fraction"])
                previous["minimum_alpha_area"] = min(previous["minimum_alpha_area"], metric["alpha_area"])
            centroids[part_id].append(_centroid(detail["part_alphas"][part_id]))
        for left_id, right_id in ADJACENT_PARTS:
            maximum_junction_gap = max(
                maximum_junction_gap,
                _minimum_mask_distance(detail["part_alphas"][left_id], detail["part_alphas"][right_id]),
            )
        total_alpha = frames[frame][:, :, 3]
        binary = np.asarray(total_alpha > 8, dtype=np.uint8)
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8))
        holes = int(np.count_nonzero((closed > 0) & (binary == 0)))
        hole_fractions.append(holes / max(1, int(np.count_nonzero(binary))))

    temporal_iou = [
        _alpha_iou(frames[left][:, :, 3], frames[right][:, :, 3])
        for left, right in zip(PROOF_FRAMES, PROOF_FRAMES[1:])
    ]
    frame_changes = []
    for left, right in zip(PROOF_FRAMES, PROOF_FRAMES[1:]):
        change = _frame_change_metrics(frames[left], frames[right])
        change["from_frame"] = left
        change["to_frame"] = right
        change["switched_parts"] = [
            part_id
            for part_id in PART_IDS
            if details[left]["part_source_weights"][part_id] != details[right]["part_source_weights"][part_id]
        ]
        frame_changes.append(change)
    maximum_centroid_step = 0.0
    for part_id, points in centroids.items():
        for left, right in zip(points, points[1:]):
            if left is not None and right is not None:
                maximum_centroid_step = max(maximum_centroid_step, float(np.linalg.norm(right - left)))

    per_part_iou = {part_id: min(values) if values else 1.0 for part_id, values in alignment.items()}
    thresholds = {
        "endpoint_mismatched_pixels": 0,
        "minimum_contact_part_alignment_iou": 0.70,
        "maximum_contact_significant_components": 1,
        "minimum_contact_dominant_component_fraction": 0.95,
        "minimum_affine_determinant": 0.50,
        "maximum_junction_gap_px": 1.5,
        "maximum_micro_hole_fraction": 0.002,
        "minimum_adjacent_frame_alpha_iou": 0.87,
        # Same bounded action-step ceiling as the Phase 29 mechanical gate.
        "maximum_contact_centroid_step_px": 24.0,
        "maximum_mixed_source_parts": 0,
    }
    machine_passed = (
        all(value["mismatched_pixels"] == 0 for value in endpoint_errors.values())
        and min(per_part_iou[part_id] for part_id in CONTACT_PARTS) >= thresholds["minimum_contact_part_alignment_iou"]
        and max(value["maximum_significant_count"] for value in components.values()) <= thresholds["maximum_contact_significant_components"]
        and min(value["minimum_dominant_fraction"] for value in components.values()) >= thresholds["minimum_contact_dominant_component_fraction"]
        and min(determinants) >= thresholds["minimum_affine_determinant"]
        and maximum_junction_gap <= thresholds["maximum_junction_gap_px"]
        and max(hole_fractions) <= thresholds["maximum_micro_hole_fraction"]
        and min(temporal_iou) >= thresholds["minimum_adjacent_frame_alpha_iou"]
        and maximum_centroid_step <= thresholds["maximum_contact_centroid_step_px"]
        and len(mixed_source_parts) <= thresholds["maximum_mixed_source_parts"]
    )
    report = {
        "proof": "phase29_semantic_part_transition_pose50_to_pose75",
        "mode": mode,
        "frame_range": [PROOF_FRAMES[0], PROOF_FRAMES[-1]],
        "source_pose_ids": [inputs.start.pose_id, inputs.end.pose_id],
        "background_pixels_loaded_or_blended": False,
        "partition_method": "hard alpha ownership by registered landmark and bone-distance masks; disconnected contact speckles reassigned to residual",
        "transition_method": (
            "one-source-per-part positive-determinant similarity warp to shared interpolated sockets with staggered corrective activation"
            if mode == "staggered_corrective_activation"
            else "per-part positive-determinant similarity warp to shared interpolated sockets plus per-part premultiplied RGBA blend"
        ),
        "staggered_switch_frame": STAGGERED_SWITCH_FRAME if mode == "staggered_corrective_activation" else None,
        "parts": list(PART_IDS),
        "endpoint_reconstruction": endpoint_errors,
        "per_part_minimum_source_alignment_alpha_iou": per_part_iou,
        "contact_component_integrity": components,
        "minimum_affine_determinant": min(determinants),
        "source_purity": {
            "mixed_source_part_count": len(mixed_source_parts),
            "mixed_source_parts": mixed_source_parts,
            "every_part_uses_exactly_one_source_per_frame": len(mixed_source_parts) == 0,
        },
        "continuity": {
            "maximum_junction_gap_px": maximum_junction_gap,
            "maximum_micro_hole_fraction": max(hole_fractions),
            "minimum_adjacent_frame_alpha_iou": min(temporal_iou),
            "maximum_contact_centroid_step_px": maximum_centroid_step,
            "per_frame_changed_pixel_and_mae": frame_changes,
            "maximum_changed_pixel_fraction_subject_union": max(row["changed_pixel_fraction_subject_union"] for row in frame_changes),
            "maximum_mean_absolute_error_subject_union": max(row["mean_absolute_error_subject_union"] for row in frame_changes),
        },
        "thresholds": thresholds,
        "machine_passed": machine_passed,
        "promotion_scope": "bounded topology feasibility evidence only; not a production-rig or audience-quality pass",
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }
    return report, frames


def _checkerboard(size: tuple[int, int], cell: int = 28) -> Image.Image:
    width, height = size
    y, x = np.indices((height, width))
    tiles = ((x // cell + y // cell) % 2).astype(np.uint8)
    light = np.asarray([68, 72, 78], dtype=np.uint8)
    dark = np.asarray([43, 46, 51], dtype=np.uint8)
    rgb = np.where(tiles[:, :, None] == 0, light, dark)
    return Image.fromarray(rgb, mode="RGB")


def _review_frame(
    rgba: np.ndarray,
    frame: int,
    mode: str,
    size: tuple[int, int] = (1920, 1080),
) -> Image.Image:
    foreground = Image.fromarray(rgba, mode="RGBA")
    matte = _checkerboard(foreground.size).convert("RGBA")
    composed = Image.alpha_composite(matte, foreground).convert("RGB").resize(size, Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(composed)
    font = ImageFont.load_default(size=26)
    if mode == "canonical_single_texture_cage":
        mode_label = "CANONICAL POSE50 CAGE"
    elif mode == "staggered_corrective_activation":
        mode_label = "STAGGERED SINGLE-SOURCE"
    else:
        mode_label = "PART CROSSFADE"
    label = f"FRAME {frame}  |  {mode_label}  |  TRANSPARENT FOREGROUND ONLY"
    box = draw.textbbox((0, 0), label, font=font)
    draw.rectangle((30, 25, 54 + box[2], 42 + box[3]), fill=(12, 14, 18))
    draw.text((42, 32), label, fill=(244, 238, 220), font=font)
    return composed


def _contact_sheet(review_frames: dict[int, Image.Image], output: Path) -> None:
    thumbnails: list[tuple[int, Image.Image]] = []
    for frame, image in review_frames.items():
        thumb = image.copy()
        thumb.thumbnail((480, 270), Image.Resampling.LANCZOS)
        thumbnails.append((frame, thumb))
    sheet = Image.new("RGB", (1920, 540), (18, 20, 24))
    for index, (_, image) in enumerate(thumbnails):
        x = (index % 4) * 480
        y = (index // 4) * 270
        sheet.paste(image, (x, y))
    sheet.save(output, quality=94, subsampling=0)
    for _, image in thumbnails:
        image.close()
    sheet.close()


def render_transition_proof(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    mode: str = "staggered_corrective_activation",
) -> dict[str, Any]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    inputs = load_transition_inputs(contract_path)
    report, frames = evaluate_transition(inputs, mode=mode)
    review_frames: dict[int, Image.Image] = {}
    for frame, rgba in frames.items():
        review = _review_frame(rgba, frame, mode)
        review_frames[frame] = review
        review.save(output / f"topology-transition-{frame:03d}.png")
    sheet = output / "june-phase29-topology-transition-contact-sheet.jpg"
    _contact_sheet(review_frames, sheet)

    executable = str(Path(ffmpeg).resolve()) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"ffmpeg executable not found: {ffmpeg}")
    video = output / "june-phase29-topology-transition-proof.mp4"
    command = [
        executable,
        "-y",
        "-v",
        "error",
        "-framerate",
        "5",
        "-start_number",
        str(PROOF_FRAMES[0]),
        "-i",
        str(output / "topology-transition-%03d.png"),
        "-vf",
        "fps=30",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        str(video),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"topology proof encode failed: {result.stderr.strip()}")
    for image in review_frames.values():
        image.close()
    report["contact_sheet"] = sheet.name
    report["video"] = video.name
    report["review_frames"] = [f"topology-transition-{frame:03d}.png" for frame in PROOF_FRAMES]
    report_path = output / "june-phase29-topology-transition-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the bounded Phase 29 semantic-part transition proof")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--mode", choices=TRANSITION_MODES, default="staggered_corrective_activation")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_transition_proof(args.contract, args.output_dir, ffmpeg=args.ffmpeg, mode=args.mode)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
