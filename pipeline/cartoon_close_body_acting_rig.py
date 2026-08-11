"""Phase39: source-textured close-body acting rig and silent performance proof.

The accepted close shot is a single authored plate.  This module adds bounded
torso, viewer-left arm, and table-hand controls as one source-resolution
inverse-remap field.  It never encodes video, opens a network connection, or
mutates the accepted Phase36 picture archive.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = Path(
    "concept/characters/june_oxley_phase39_close_body_acting_rig_v1.json"
)
IMPLEMENTATION_RELATIVE_PATH = Path("pipeline/cartoon_close_body_acting_rig.py")
TEST_RELATIVE_PATH = Path("pipeline/tests/test_cartoon_close_body_acting_rig.py")


class CloseBodyActingRigError(RuntimeError):
    """Raised when the Phase39 proof cannot satisfy its declared contract."""


@dataclass(frozen=True)
class RegionBasis:
    name: str
    names: tuple[str, ...]
    points: np.ndarray
    bbox: tuple[int, int, int, int]
    alpha: np.ndarray
    weights: np.ndarray


@dataclass
class PreparedRig:
    contract: dict[str, Any]
    contract_path: Path
    plate: np.ndarray
    regions: dict[str, RegionBasis]
    protected: dict[str, np.ndarray]
    states: list[dict[str, float]]


@dataclass
class RenderedFrame:
    frame_number: int
    image: np.ndarray
    state: dict[str, float]
    landmarks: dict[str, tuple[float, float]]
    displacement: np.ndarray
    prospective_support: np.ndarray
    metrics: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rgb_hash(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array, dtype=np.uint8).tobytes()).hexdigest()


def _repo_path(relative: str | Path) -> Path:
    resolved = (REPO_ROOT / Path(relative)).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise CloseBodyActingRigError(f"path escapes repository: {relative}") from exc
    return resolved


def _require(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise CloseBodyActingRigError(f"{label}: {actual!r} != {expected!r}")


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = _repo_path(str(reference.get("path", "")))
    if not path.is_file():
        raise CloseBodyActingRigError(f"{label} missing: {path}")
    actual = _sha256(path)
    expected = str(reference.get("sha256", ""))
    if actual != expected:
        raise CloseBodyActingRigError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def load_contract(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> tuple[dict[str, Any], Path]:
    source = Path(path).resolve()
    contract = json.loads(source.read_text(encoding="utf-8"))
    _require(contract.get("contract_version"), 1, "contract version")
    _require(contract.get("contract_id"), "june_oxley_phase39_close_body_acting_rig_v1", "contract id")
    _require(contract.get("cash_cost"), 0, "cash cost")
    _require(contract.get("paid_service_calls_allowed"), 0, "paid services")
    _require(contract.get("network_calls_allowed"), 0, "network calls")
    _require(contract.get("video_encode_allowed"), False, "video encode policy")
    _require(contract.get("picture_master_mutation_allowed"), False, "master mutation policy")
    _require(contract.get("promotion_allowed"), False, "promotion policy")
    _require(contract["clock"]["frame_count"], 162, "frame count")
    _require(contract["clock"]["final_hold_frames_inclusive"], [149, 162], "final hold")
    _require(contract["deformation"]["moving_source_resample_count"], 1, "resample count")
    _require(
        contract["deformation"]["region_priority_back_to_front"],
        ["torso", "viewer_left_arm", "table_hand"],
        "region priority",
    )
    _require(len(contract.get("authored_beats") or []), 4, "authored beat count")
    channels = [str(value) for value in contract.get("motion_channels") or []]
    if len(channels) != 12 or len(set(channels)) != len(channels):
        raise CloseBodyActingRigError("motion channels must contain twelve unique controls")
    keyframes = contract.get("motion_keyframes") or []
    frames = [int(row["frame"]) for row in keyframes]
    if frames != sorted(set(frames)) or frames[0] != 1 or frames[-1] != 162:
        raise CloseBodyActingRigError("motion keyframes must be unique, ordered, and span F001-F162")
    expected_keys = {"frame", *channels}
    for row in keyframes:
        if set(row) != expected_keys:
            raise CloseBodyActingRigError(f"incomplete motion keyframe F{int(row['frame']):03d}")
    for label, reference in contract["locks"].items():
        _locked_path(reference, label)
    phase38 = json.loads(_locked_path(contract["locks"]["phase38_machine_report"], "Phase38 report").read_text(encoding="utf-8"))
    _require(phase38.get("status"), "MACHINE_DIAGNOSTIC_PASSED_ACTING_RIG_GAP_CONFIRMED_PLAN_ONLY", "Phase38 status")
    _require(phase38.get("machine_passed"), True, "Phase38 machine pass")
    _require(phase38.get("picture_rebuild_authorized"), False, "Phase38 rebuild authority")
    return contract, source


def _rect_mask(shape: tuple[int, int], xyxy: list[int]) -> np.ndarray:
    height, width = shape
    left, top, right, bottom = (int(value) for value in xyxy)
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise CloseBodyActingRigError(f"invalid protected rectangle: {xyxy}")
    mask = np.zeros(shape, dtype=bool)
    mask[top:bottom, left:right] = True
    return mask


def _soft_polygon(
    shape: tuple[int, int],
    polygon: list[list[int]],
    sigma: float,
    protected_union: np.ndarray,
) -> np.ndarray:
    hard = np.zeros(shape, dtype=np.uint8)
    points = np.asarray(polygon, dtype=np.int32)
    cv2.fillPoly(hard, [points], 255, lineType=cv2.LINE_8)
    alpha = cv2.GaussianBlur(hard.astype(np.float32) / 255.0, (0, 0), sigmaX=sigma, sigmaY=sigma)
    alpha[alpha < 1.0 / 1024.0] = 0.0
    alpha[protected_union] = 0.0
    return np.clip(alpha, 0.0, 1.0).astype(np.float32)


def _region_basis(
    name: str,
    definition: dict[str, Any],
    shape: tuple[int, int],
    sigma: float,
    protected_union: np.ndarray,
) -> RegionBasis:
    alpha_full = _soft_polygon(shape, definition["polygon_xy"], sigma, protected_union)
    ys, xs = np.where(alpha_full > 0.0)
    if xs.size == 0:
        raise CloseBodyActingRigError(f"{name} has empty support")
    left, right = max(0, int(xs.min()) - 1), min(shape[1], int(xs.max()) + 2)
    top, bottom = max(0, int(ys.min()) - 1), min(shape[0], int(ys.max()) + 2)
    alpha = alpha_full[top:bottom, left:right]
    names = tuple(str(value) for value in definition["controls"])
    points = np.asarray([definition["controls"][control] for control in names], dtype=np.float32)
    yy, xx = np.mgrid[top:bottom, left:right].astype(np.float32)
    radius = float(definition["control_radius_px"])
    weight_rows = []
    for point in points:
        distance2 = (xx - point[0]) ** 2 + (yy - point[1]) ** 2
        weight_rows.append(np.exp(-distance2 / (2.0 * radius * radius)))
    weights = np.stack(weight_rows, axis=2).astype(np.float32)
    denominator = np.sum(weights, axis=2, keepdims=True)
    weights /= np.maximum(denominator, 1e-12)
    return RegionBasis(name, names, points, (left, top, right, bottom), alpha, weights)


def _smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def _motion_states(contract: dict[str, Any]) -> list[dict[str, float]]:
    keyframes = contract["motion_keyframes"]
    channels = [str(value) for value in contract["motion_channels"]]
    result: list[dict[str, float]] = []
    right = 1
    for frame in range(1, int(contract["clock"]["frame_count"]) + 1):
        while right < len(keyframes) - 1 and frame > int(keyframes[right]["frame"]):
            right += 1
        left = max(0, right - 1)
        first, second = keyframes[left], keyframes[right]
        span = max(1, int(second["frame"]) - int(first["frame"]))
        t = _smoothstep((frame - int(first["frame"])) / span)
        state = {
            channel: float(first[channel]) * (1.0 - t) + float(second[channel]) * t
            for channel in channels
        }
        result.append(state)
    return result


def prepare_rig(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> PreparedRig:
    contract, contract_path = load_contract(path)
    plate_path = _locked_path(contract["locks"]["gs070_plate"], "GS070 plate")
    plate = np.asarray(Image.open(plate_path).convert("RGB"), dtype=np.uint8)
    expected_shape = (int(contract["clock"]["source_height"]), int(contract["clock"]["source_width"]), 3)
    if plate.shape != expected_shape:
        raise CloseBodyActingRigError(f"plate shape changed: {plate.shape} != {expected_shape}")
    protected = {
        name: _rect_mask(plate.shape[:2], values)
        for name, values in (
            ("face_head", contract["protected_source_regions"]["face_head_rect_xyxy"]),
            ("mug", contract["protected_source_regions"]["mug_rect_xyxy"]),
        )
    }
    protected_union = np.logical_or.reduce(list(protected.values()))
    sigma = float(contract["deformation"]["mask_feather_sigma_px"])
    regions = {
        name: _region_basis(name, definition, plate.shape[:2], sigma, protected_union)
        for name, definition in contract["rig_regions"].items()
    }
    return PreparedRig(contract, contract_path, plate, regions, protected, _motion_states(contract))


def _rotate_delta(point: np.ndarray, pivot: np.ndarray, degrees: float) -> np.ndarray:
    radians = math.radians(float(degrees))
    cosine, sine = math.cos(radians), math.sin(radians)
    relative = point - pivot
    rotated = np.asarray(
        [relative[0] * cosine - relative[1] * sine, relative[0] * sine + relative[1] * cosine],
        dtype=np.float32,
    )
    return rotated - relative


def _torso_delta(point: np.ndarray, state: dict[str, float], pivot: np.ndarray) -> np.ndarray:
    return (
        _rotate_delta(point, pivot, state["torso_rotation_deg"])
        + np.asarray([state["torso_x_px"], state["torso_y_px"]], dtype=np.float32)
    )


def _torso_offsets(prepared: PreparedRig, state: dict[str, float]) -> np.ndarray:
    region = prepared.regions["torso"]
    pivot = np.asarray(prepared.contract["rig_regions"]["torso"]["pivot_xy"], dtype=np.float32)
    return np.stack([_torso_delta(point, state, pivot) for point in region.points]).astype(np.float32)


def _arm_offsets(prepared: PreparedRig, state: dict[str, float]) -> np.ndarray:
    region = prepared.regions["viewer_left_arm"]
    pivot = np.asarray(prepared.contract["rig_regions"]["torso"]["pivot_xy"], dtype=np.float32)
    elbow = np.asarray([state["left_elbow_x_px"], state["left_elbow_y_px"]], dtype=np.float32)
    forearm = np.asarray([state["left_forearm_x_px"], state["left_forearm_y_px"]], dtype=np.float32)
    fractions = {
        "shoulder": (0.0, 0.0),
        "upper_arm": (0.45, 0.0),
        "elbow": (1.0, 0.0),
        "forearm": (0.55, 0.65),
        "cuff": (0.15, 1.0),
    }
    rows = []
    for name, point in zip(region.names, region.points):
        elbow_fraction, forearm_fraction = fractions[name]
        rows.append(
            _torso_delta(point, state, pivot) * 0.55
            + elbow * elbow_fraction
            + forearm * forearm_fraction
        )
    return np.stack(rows).astype(np.float32)


def _hand_offsets(prepared: PreparedRig, state: dict[str, float]) -> np.ndarray:
    region = prepared.regions["table_hand"]
    index = {name: offset for offset, name in enumerate(region.names)}
    wrist = region.points[index["wrist"]]
    palm = region.points[index["palm"]]
    translation = np.asarray([state["palm_x_px"], state["palm_y_px"]], dtype=np.float32)
    spread_vectors = {
        "thumb_tip": (-2.2, -0.1),
        "index_tip": (-1.0, 0.10),
        "middle_tip": (0.0, 0.08),
        "ring_tip": (1.05, -0.05),
        "pinky_tip": (2.25, -0.25),
        "index_knuckle": (-0.45, 0.0),
        "middle_knuckle": (0.0, 0.0),
        "ring_knuckle": (0.45, 0.0),
        "pinky_knuckle": (0.9, -0.05),
    }
    # Fingers slide/compress on the tabletop instead of curling upward into a
    # fake hover.  These source-plane vectors keep the nail beds in contact
    # while narrowing the hand silhouette toward the palm.
    compression_vectors = {
        "thumb_tip": (1.8, -0.10),
        "index_tip": (1.2, -0.22),
        "middle_tip": (0.65, -0.28),
        "ring_tip": (0.0, -0.22),
        "pinky_tip": (-0.75, -0.12),
    }
    tip_names = {"thumb_tip", "index_tip", "middle_tip", "ring_tip", "pinky_tip"}
    rows = []
    for name, point in zip(region.names, region.points):
        if name == "wrist":
            amount = 0.28
        elif name.endswith("knuckle"):
            amount = 0.72
        else:
            amount = 1.0
        delta = _rotate_delta(point, wrist, state["wrist_rotation_deg"]) + translation * amount
        if name in spread_vectors:
            delta += np.asarray(spread_vectors[name], dtype=np.float32) * float(state["finger_spread"])
        if name in tip_names:
            delta += np.asarray(compression_vectors[name], dtype=np.float32) * float(
                state["finger_compress"]
            )
        elif name.endswith("knuckle"):
            direction = palm - point
            direction /= max(1e-6, float(np.linalg.norm(direction)))
            delta += direction * (0.8 * float(state["finger_compress"]))
        rows.append(delta)
    return np.stack(rows).astype(np.float32)


def _region_offsets(prepared: PreparedRig, state: dict[str, float]) -> dict[str, np.ndarray]:
    return {
        "torso": _torso_offsets(prepared, state),
        "viewer_left_arm": _arm_offsets(prepared, state),
        "table_hand": _hand_offsets(prepared, state),
    }


def _compose_displacement(
    prepared: PreparedRig,
    offsets: dict[str, np.ndarray],
) -> np.ndarray:
    height, width = prepared.plate.shape[:2]
    result = np.zeros((height, width, 2), dtype=np.float32)
    for name in prepared.contract["deformation"]["region_priority_back_to_front"]:
        region = prepared.regions[name]
        left, top, right, bottom = region.bbox
        local = np.tensordot(region.weights, offsets[name], axes=(2, 0)).astype(np.float32)
        alpha = region.alpha[:, :, None]
        destination = result[top:bottom, left:right]
        destination[:] = destination * (1.0 - alpha) + local * alpha
    protected_union = np.logical_or.reduce(list(prepared.protected.values()))
    result[protected_union] = 0.0
    return result


def _landmarks(
    prepared: PreparedRig,
    offsets: dict[str, np.ndarray],
) -> dict[str, tuple[float, float]]:
    output: dict[str, tuple[float, float]] = {}
    for region_name, region in prepared.regions.items():
        for name, point, delta in zip(region.names, region.points, offsets[region_name]):
            target = point + delta
            output[f"{region_name}.{name}"] = (float(target[0]), float(target[1]))
    return output


def render_frame(prepared: PreparedRig, frame_number: int) -> RenderedFrame:
    frame_count = int(prepared.contract["clock"]["frame_count"])
    if not 1 <= int(frame_number) <= frame_count:
        raise CloseBodyActingRigError(f"frame outside F001-F{frame_count:03d}: {frame_number}")
    state = prepared.states[int(frame_number) - 1]
    offsets = _region_offsets(prepared, state)
    displacement = _compose_displacement(prepared, offsets)
    magnitude = np.linalg.norm(displacement, axis=2)
    support = magnitude > 1e-5
    guard = int(prepared.contract["deformation"]["prospective_kernel_guard_px"])
    if np.any(support):
        kernel = np.ones((guard * 2 + 1, guard * 2 + 1), dtype=np.uint8)
        prospective = cv2.dilate(support.astype(np.uint8), kernel, iterations=1) > 0
    else:
        prospective = support.copy()
    height, width = prepared.plate.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    map_x = xx - displacement[:, :, 0]
    map_y = yy - displacement[:, :, 1]
    warped = cv2.remap(
        prepared.plate,
        map_x,
        map_y,
        interpolation=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    warped[~prospective] = prepared.plate[~prospective]
    for mask in prepared.protected.values():
        warped[mask] = prepared.plate[mask]
    changed = np.any(warped != prepared.plate, axis=2)
    protected_changed = {
        name: int(np.count_nonzero(changed & mask)) for name, mask in prepared.protected.items()
    }
    metrics = {
        "rgb_sha256": _rgb_hash(warped),
        "changed_pixel_count": int(np.count_nonzero(changed)),
        "changed_pixels_outside_prospective_support": int(np.count_nonzero(changed & ~prospective)),
        "protected_changed_pixels": protected_changed,
        "maximum_displacement_px": float(np.max(magnitude)),
        "prospective_support_area": int(np.count_nonzero(prospective)),
    }
    return RenderedFrame(
        int(frame_number),
        warped,
        dict(state),
        _landmarks(prepared, offsets),
        displacement,
        prospective,
        metrics,
    )


def _finger_span(landmarks: dict[str, tuple[float, float]]) -> float:
    thumb = np.asarray(landmarks["table_hand.thumb_tip"], dtype=np.float64)
    pinky = np.asarray(landmarks["table_hand.pinky_tip"], dtype=np.float64)
    return float(np.linalg.norm(pinky - thumb))


def _gate(identifier: str, actual: Any, comparator: str, expected: Any, passed: bool) -> dict[str, Any]:
    return {
        "id": identifier,
        "actual": actual,
        "comparator": comparator,
        "expected": expected,
        "passed": bool(passed),
    }


def _measure(prepared: PreparedRig) -> tuple[dict[str, Any], dict[int, RenderedFrame]]:
    retained_numbers = {1, 24, 50, 66, 72, 82, 98, 110, 115, 126, 138, 148, 149, 162}
    retained: dict[int, RenderedFrame] = {}
    frame_hashes: list[str] = []
    changed_counts: list[int] = []
    max_displacements: list[float] = []
    max_outside = 0
    max_face = 0
    max_mug = 0
    all_landmarks: list[dict[str, tuple[float, float]]] = []
    for frame_number in range(1, int(prepared.contract["clock"]["frame_count"]) + 1):
        frame = render_frame(prepared, frame_number)
        frame_hashes.append(frame.metrics["rgb_sha256"])
        changed_counts.append(int(frame.metrics["changed_pixel_count"]))
        max_displacements.append(float(frame.metrics["maximum_displacement_px"]))
        max_outside = max(max_outside, int(frame.metrics["changed_pixels_outside_prospective_support"]))
        max_face = max(max_face, int(frame.metrics["protected_changed_pixels"]["face_head"]))
        max_mug = max(max_mug, int(frame.metrics["protected_changed_pixels"]["mug"]))
        all_landmarks.append(frame.landmarks)
        if frame_number in retained_numbers:
            retained[frame_number] = frame
    maximum_step = 0.0
    maximum_step_landmark = ""
    maximum_step_frame = 0
    for index in range(1, len(all_landmarks)):
        for name in all_landmarks[index]:
            before = np.asarray(all_landmarks[index - 1][name], dtype=np.float64)
            after = np.asarray(all_landmarks[index][name], dtype=np.float64)
            step = float(np.linalg.norm(after - before))
            if step > maximum_step:
                maximum_step = step
                maximum_step_landmark = name
                maximum_step_frame = index + 1
    baseline_span = _finger_span(all_landmarks[0])
    opening_span = _finger_span(all_landmarks[71])
    compression_span = _finger_span(all_landmarks[114])
    fingertip_names = [
        "table_hand.thumb_tip",
        "table_hand.index_tip",
        "table_hand.middle_tip",
        "table_hand.ring_tip",
        "table_hand.pinky_tip",
    ]
    fingertip_vertical_excursion = max(
        abs(all_landmarks[index][name][1] - all_landmarks[0][name][1])
        for index in range(len(all_landmarks))
        for name in fingertip_names
    )
    final_start, final_end = prepared.contract["clock"]["final_hold_frames_inclusive"]
    baseline_hash = frame_hashes[0]
    final_identical = sum(
        frame_hashes[index - 1] == baseline_hash for index in range(int(final_start), int(final_end) + 1)
    )
    metrics = {
        "frame_count": len(frame_hashes),
        "combined_rgb_sha256": hashlib.sha256("".join(frame_hashes).encode("ascii")).hexdigest(),
        "baseline_rgb_sha256": baseline_hash,
        "maximum_changed_pixel_count": max(changed_counts),
        "maximum_source_displacement_px": max(max_displacements),
        "maximum_changed_pixels_outside_prospective_support": max_outside,
        "maximum_changed_pixels_in_face_head": max_face,
        "maximum_changed_pixels_in_mug": max_mug,
        "maximum_adjacent_landmark_step_px": maximum_step,
        "maximum_adjacent_landmark_step_landmark": maximum_step_landmark,
        "maximum_adjacent_landmark_step_frame": maximum_step_frame,
        "baseline_thumb_to_pinky_span_px": baseline_span,
        "opening_thumb_to_pinky_span_px": opening_span,
        "compression_thumb_to_pinky_span_px": compression_span,
        "opening_finger_span_gain_px": opening_span - baseline_span,
        "compression_span_recovery_from_open_px": opening_span - compression_span,
        "maximum_fingertip_vertical_excursion_px": fingertip_vertical_excursion,
        "final_identical_frame_count": final_identical,
        "opening_overshoot": {
            "F066": prepared.states[65]["finger_spread"],
            "F072": prepared.states[71]["finger_spread"],
            "F082": prepared.states[81]["finger_spread"],
        },
        "compression_overshoot": {
            "F110": prepared.states[109]["finger_compress"],
            "F115": prepared.states[114]["finger_compress"],
            "F126": prepared.states[125]["finger_compress"],
        },
        "frame_hashes": frame_hashes,
        "landmark_tracks": {
            name: [list(map(float, row[name])) for row in all_landmarks]
            for name in (
                "torso.sternum",
                "viewer_left_arm.elbow",
                "table_hand.palm",
                "table_hand.index_tip",
                "table_hand.pinky_tip",
            )
        },
    }
    return metrics, retained


def _gates(prepared: PreparedRig, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    quality = prepared.contract["quality_gates"]
    opening = metrics["opening_overshoot"]
    compression = metrics["compression_overshoot"]
    return [
        _gate("frame_count", metrics["frame_count"], "==", quality["required_frame_count"], metrics["frame_count"] == quality["required_frame_count"]),
        _gate("maximum_source_displacement_px", metrics["maximum_source_displacement_px"], "<=", quality["maximum_source_displacement_px"], metrics["maximum_source_displacement_px"] <= quality["maximum_source_displacement_px"]),
        _gate("maximum_adjacent_landmark_step_px", metrics["maximum_adjacent_landmark_step_px"], "<=", quality["maximum_adjacent_landmark_step_px"], metrics["maximum_adjacent_landmark_step_px"] <= quality["maximum_adjacent_landmark_step_px"]),
        _gate("face_head_pixels_preserved", metrics["maximum_changed_pixels_in_face_head"], "==", 0, metrics["maximum_changed_pixels_in_face_head"] == 0),
        _gate("mug_pixels_preserved", metrics["maximum_changed_pixels_in_mug"], "==", 0, metrics["maximum_changed_pixels_in_mug"] == 0),
        _gate("prospective_support_containment", metrics["maximum_changed_pixels_outside_prospective_support"], "==", 0, metrics["maximum_changed_pixels_outside_prospective_support"] == 0),
        _gate("opening_finger_span_gain_px", metrics["opening_finger_span_gain_px"], ">=", quality["minimum_opening_finger_span_gain_px"], metrics["opening_finger_span_gain_px"] >= quality["minimum_opening_finger_span_gain_px"]),
        _gate("compression_span_recovery_from_open_px", metrics["compression_span_recovery_from_open_px"], ">=", quality["minimum_compression_span_recovery_px"], metrics["compression_span_recovery_from_open_px"] >= quality["minimum_compression_span_recovery_px"]),
        _gate("maximum_fingertip_vertical_excursion_px", metrics["maximum_fingertip_vertical_excursion_px"], "<=", quality["maximum_fingertip_vertical_excursion_px"], metrics["maximum_fingertip_vertical_excursion_px"] <= quality["maximum_fingertip_vertical_excursion_px"]),
        _gate("final_identical_frame_count", metrics["final_identical_frame_count"], "==", quality["required_final_identical_frame_count"], metrics["final_identical_frame_count"] == quality["required_final_identical_frame_count"]),
        _gate("opening_has_one_overshoot_and_settle", opening, "F072>F066 and F072>F082", True, opening["F072"] > opening["F066"] and opening["F072"] > opening["F082"]),
        _gate("compression_has_one_overshoot_and_settle", compression, "F115>F110 and F115>F126", True, compression["F115"] > compression["F110"] and compression["F115"] > compression["F126"]),
        _gate("moving_source_resample_count", prepared.contract["deformation"]["moving_source_resample_count"], "==", 1, prepared.contract["deformation"]["moving_source_resample_count"] == 1),
        _gate("encoding_process_count", 0, "==", quality["required_zero_encoder_processes"], quality["required_zero_encoder_processes"] == 0),
    ]


def _draw_label(image: Image.Image, text: str, xy: tuple[int, int]) -> None:
    draw = ImageDraw.Draw(image)
    x, y = xy
    box = draw.textbbox((x, y), text)
    draw.rectangle((box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 3), fill=(8, 10, 14))
    draw.text((x, y), text, fill=(245, 242, 231))


def _support_overlay(prepared: PreparedRig) -> Image.Image:
    base = prepared.plate.astype(np.float32) * 0.52
    colors = {
        "torso": np.asarray([41, 182, 246], dtype=np.float32),
        "viewer_left_arm": np.asarray([200, 120, 255], dtype=np.float32),
        "table_hand": np.asarray([255, 135, 75], dtype=np.float32),
    }
    for name, region in prepared.regions.items():
        left, top, right, bottom = region.bbox
        alpha = (region.alpha[:, :, None] * 0.55).astype(np.float32)
        target = base[top:bottom, left:right]
        target[:] = target * (1.0 - alpha) + colors[name] * alpha
    image = Image.fromarray(np.clip(np.rint(base), 0, 255).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(image)
    for name, region in prepared.regions.items():
        color = tuple(int(value) for value in colors[name])
        points = [tuple(map(int, point)) for point in prepared.contract["rig_regions"][name]["polygon_xy"]]
        draw.line(points + [points[0]], fill=color, width=3)
        for control_name, point in zip(region.names, region.points):
            x, y = map(float, point)
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color, outline=(255, 255, 255), width=1)
            draw.text((x + 7, y - 6), control_name, fill=(255, 255, 255))
    for name, values in prepared.contract["protected_source_regions"].items():
        left, top, right, bottom = values
        draw.rectangle((left, top, right - 1, bottom - 1), outline=(255, 70, 70), width=3)
        draw.text((left + 5, top + 5), f"PROTECTED {name}", fill=(255, 90, 90))
    _draw_label(image, "PHASE39 SOURCE-RIG SUPPORT / RED = BYTE-PROTECTED", (18, 18))
    return image


def _keyframe_sheet(retained: dict[int, RenderedFrame]) -> Image.Image:
    numbers = [1, 24, 50, 66, 72, 82, 98, 110, 115, 126, 148, 162]
    thumb_size = (552, 311)
    sheet = Image.new("RGB", (thumb_size[0] * 3, thumb_size[1] * 4), (10, 12, 16))
    for index, number in enumerate(numbers):
        image = Image.fromarray(retained[number].image, "RGB").resize(thumb_size, Image.Resampling.LANCZOS)
        row, column = divmod(index, 3)
        sheet.paste(image, (column * thumb_size[0], row * thumb_size[1]))
        state = retained[number].state
        _draw_label(
            sheet,
            f"F{number:03d} spread {state['finger_spread']:+.2f} compress {state['finger_compress']:+.2f}",
            (column * thumb_size[0] + 10, row * thumb_size[1] + 10),
        )
    return sheet


def _difference_sheet(prepared: PreparedRig, retained: dict[int, RenderedFrame]) -> Image.Image:
    numbers = [24, 66, 72, 110, 115, 148]
    crop = (0, 390, 1100, 941)
    cell = (660, 331)
    sheet = Image.new("RGB", (cell[0] * 3, cell[1] * 2), (8, 10, 14))
    base_crop = prepared.plate[crop[1] : crop[3], crop[0] : crop[2]]
    for index, number in enumerate(numbers):
        current = retained[number].image[crop[1] : crop[3], crop[0] : crop[2]]
        delta = np.abs(current.astype(np.int16) - base_crop.astype(np.int16)).astype(np.uint8)
        amplified = np.clip(delta.astype(np.int16) * 8, 0, 255).astype(np.uint8)
        blended = current.copy()
        changed = np.any(delta > 0, axis=2)
        blended[changed] = np.clip(
            blended[changed].astype(np.float32) * 0.6 + amplified[changed].astype(np.float32) * 0.4,
            0,
            255,
        ).astype(np.uint8)
        image = Image.fromarray(blended, "RGB").resize(cell, Image.Resampling.LANCZOS)
        row, column = divmod(index, 3)
        sheet.paste(image, (column * cell[0], row * cell[1]))
        _draw_label(sheet, f"F{number:03d} RGB + 8X DIFFERENCE", (column * cell[0] + 10, row * cell[1] + 10))
    return sheet


def _motion_arc_sheet(prepared: PreparedRig, metrics: dict[str, Any]) -> Image.Image:
    image = Image.fromarray((prepared.plate.astype(np.float32) * 0.62).astype(np.uint8), "RGB")
    draw = ImageDraw.Draw(image)
    colors = {
        "torso.sternum": (41, 182, 246),
        "viewer_left_arm.elbow": (200, 120, 255),
        "table_hand.palm": (255, 135, 75),
        "table_hand.index_tip": (255, 230, 75),
        "table_hand.pinky_tip": (120, 255, 165),
    }
    for name, track in metrics["landmark_tracks"].items():
        points = [tuple(map(float, point)) for point in track]
        draw.line(points, fill=colors[name], width=4)
        for frame in (1, 24, 50, 66, 72, 82, 98, 110, 115, 126, 148, 162):
            x, y = points[frame - 1]
            radius = 5 if frame in (72, 115) else 3
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=colors[name])
        x, y = points[71]
        draw.text((x + 8, y - 18), f"{name} F072", fill=colors[name])
        x, y = points[114]
        draw.text((x + 8, y + 6), f"{name} F115", fill=colors[name])
    _draw_label(image, "RENDERED LANDMARK ARCS / F072 OPEN OVERSHOOT / F115 COMPRESSION OVERSHOOT", (18, 18))
    return image


def _write_png(image: Image.Image, path: Path) -> dict[str, Any]:
    image.save(path, format="PNG", optimize=False, compress_level=6)
    image.close()
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}


def build_evidence(
    output: str | Path | None = None,
    contract_path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> dict[str, Any]:
    prepared = prepare_rig(contract_path)
    destination = (
        Path(output).resolve()
        if output is not None
        else _repo_path(prepared.contract["evidence"]["directory"])
    )
    if destination.exists():
        raise CloseBodyActingRigError(f"output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    metrics, retained = _measure(prepared)
    gates = _gates(prepared, metrics)
    failed = [row["id"] for row in gates if not row["passed"]]
    if failed:
        raise CloseBodyActingRigError(f"Phase39 machine gates failed: {failed}")
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    try:
        artifacts = []
        artifacts.append(_write_png(_support_overlay(prepared), stage / "phase39-rig-support-overlay-v1.png"))
        artifacts.append(_write_png(_keyframe_sheet(retained), stage / "phase39-silent-acting-keyframes-v1.png"))
        artifacts.append(_write_png(_difference_sheet(prepared, retained), stage / "phase39-silent-acting-difference-v1.png"))
        artifacts.append(_write_png(_motion_arc_sheet(prepared, metrics), stage / "phase39-motion-arcs-v1.png"))
        report = {
            "report_version": 1,
            "diagnostic_id": prepared.contract["contract_id"],
            "status": "MACHINE_PROTOTYPE_PASSED_HUMAN_ACTING_REVIEW_REQUIRED",
            "machine_passed": True,
            "human_acting_accepted": False,
            "picture_master_mutated": False,
            "picture_rebuild_authorized": False,
            "video_encode_authorized": False,
            "promotion_allowed": False,
            "cash_cost": 0,
            "paid_service_calls": 0,
            "network_calls": 0,
            "encoding_process_count": 0,
            "contract": {"path": str(CONTRACT_RELATIVE_PATH).replace("\\", "/"), "sha256": _sha256(prepared.contract_path)},
            "implementation": {"path": str(IMPLEMENTATION_RELATIVE_PATH).replace("\\", "/"), "sha256": _sha256(_repo_path(IMPLEMENTATION_RELATIVE_PATH))},
            "tests": {"path": str(TEST_RELATIVE_PATH).replace("\\", "/"), "sha256": _sha256(_repo_path(TEST_RELATIVE_PATH))},
            "source_plate": {"path": prepared.contract["locks"]["gs070_plate"]["path"], "sha256": prepared.contract["locks"]["gs070_plate"]["sha256"], "mutated": False},
            "method": prepared.contract["deformation"],
            "authored_beats": prepared.contract["authored_beats"],
            "measurements": metrics,
            "gates": gates,
            "gate_count": len(gates),
            "failed_gates": failed,
            "artifacts": artifacts,
            "recommendation": "HUMAN_REVIEW_THE_FOUR_BEATS_AT_NATIVE_SCALE_BEFORE_ANY_INTEGRATION",
        }
        report_path = stage / "phase39-close-body-acting-machine-report-v1.json"
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        actual_names = sorted(path.name for path in stage.iterdir())
        expected_names = sorted(prepared.contract["evidence"]["allowlist"])
        if actual_names != expected_names:
            raise CloseBodyActingRigError(f"output inventory mismatch: {actual_names} != {expected_names}")
        os.replace(stage, destination)
        return report
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", default=str(REPO_ROOT / CONTRACT_RELATIVE_PATH))
    parser.add_argument("--output")
    args = parser.parse_args()
    report = build_evidence(args.output, args.contract)
    print(
        json.dumps(
            {
                "status": report["status"],
                "gate_count": report["gate_count"],
                "failed_gates": report["failed_gates"],
                "recommendation": report["recommendation"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
