"""Phase 31 connected-region flat-color mechanics proof for June Oxley.

The proof consumes only the nine semantic-support regions accepted by Phase
30.  It generates diagnostic masks and flat colors in memory; it does not
encode video, sample character texture, invent hidden limb surfaces, or split
the continuous garment/sleeve regions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from pipeline.cartoon_pose_layers import registered_pose_layer
from pipeline.cartoon_reconstruction_locked_patch import (
    LockedPatch,
    evaluate_reconstruction_lock,
    extract_locked_patches,
    load_reconstruction_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
REGION_IDS = (
    "lower_garment",
    "torso_shell",
    "left_sleeve",
    "right_sleeve",
    "head_neck",
    "left_hand",
    "right_hand_mug",
    "left_boot",
    "right_boot",
)
PREVIEW_SIZE = (960, 540)
_PINNED_CONTRACT_CANONICAL_SHA256 = "4fa358c35b492fdb6a7b0e81c8e5a15fe222bfc8a89cd50af9e96183e1044378"


class ConnectedRegionMechanicsError(ValueError):
    """Raised when any Phase 31 invariant cannot be proved fail-closed."""


@dataclass
class FlatMechanicsFrame:
    frame: int
    motion_state: dict[str, Any]
    source_region_masks: dict[str, np.ndarray]
    source_flat_rgba: np.ndarray
    registered_flat_rgba: np.ndarray
    preview_rgba: np.ndarray
    preview_region_masks: dict[str, np.ndarray]
    preview_shadow_mask: np.ndarray
    region_transforms: dict[str, np.ndarray]
    cage_controls: dict[str, dict[str, np.ndarray]]
    lower_triangle_area_ratios: list[float]
    lower_minimum_jacobian_determinant: float
    lower_maximum_inverse_residual_source_px: float

    def close(self) -> None:
        """Release large arrays eagerly during sequential evaluation."""
        self.source_region_masks.clear()
        self.preview_region_masks.clear()
        self.region_transforms.clear()
        self.cage_controls.clear()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(reference.get("path", ""))).resolve()
    if not path.is_file():
        raise ConnectedRegionMechanicsError(f"{label} is missing: {path}")
    actual = _sha256(path)
    expected = str(reference.get("sha256", ""))
    if not expected or actual != expected:
        raise ConnectedRegionMechanicsError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ConnectedRegionMechanicsError(f"{label} mismatch: {actual!r} != {expected!r}")


def _components(mask: np.ndarray) -> int:
    count, _ = cv2.connectedComponents(np.asarray(mask, dtype=np.uint8), connectivity=8)
    return int(count - 1)


def _centroid(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask)
    if not len(xs):
        raise ConnectedRegionMechanicsError("required mechanics mask is empty")
    return np.asarray((float(np.mean(xs)), float(np.mean(ys))), dtype=np.float64)


def _hex_rgb(value: str) -> tuple[int, int, int]:
    text = str(value)
    if len(text) != 7 or not text.startswith("#"):
        raise ConnectedRegionMechanicsError(f"invalid diagnostic palette color: {text}")
    return tuple(int(text[index:index + 2], 16) for index in (1, 3, 5))


def _validate_contract(contract: dict[str, Any]) -> None:
    canonical = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    actual_contract_hash = hashlib.sha256(canonical).hexdigest()
    _require_equal(actual_contract_hash, _PINNED_CONTRACT_CANONICAL_SHA256, "complete Phase31 contract")
    _require_equal(contract.get("contract_version"), 1, "contract version")
    _require_equal(contract.get("contract_id"), "june_oxley_connected_region_mechanics_v1", "contract id")
    _require_equal(contract.get("phase"), "phase31_connected_region_mechanics", "phase")
    _require_equal(contract.get("cash_cost"), 0, "cash cost")
    _require_equal(contract.get("paid_runtime_dependency"), False, "paid dependency")
    _require_equal(contract.get("network_runtime_required"), False, "network dependency")

    timing = contract["timing"]
    _require_equal(
        (timing.get("frame_start"), timing.get("frame_end"), timing.get("frame_count"), timing.get("fps")),
        (1, 49, 49, 30),
        "mechanics clock",
    )
    keys = [1, 7, 13, 19, 25, 31, 37, 43, 49]
    _require_equal(timing.get("key_frames"), keys, "timing key frames")
    _require_equal(timing.get("scalar_interpolation"), "monotone_cubic_hermite_pchip", "scalar interpolation")
    clock = contract["motion_clock"]
    _require_equal(clock.get("key_frames"), keys, "motion key frames")
    _require_equal(clock.get("interpolation"), "monotone_cubic_hermite_pchip_each_scalar", "motion interpolation")
    _require_equal(clock.get("clamp_no_overshoot"), True, "motion clamp")
    _require_equal(clock.get("first_last_exact"), True, "motion loop")
    for identifier, values in clock["tracks"].items():
        if len(values) != len(keys):
            raise ConnectedRegionMechanicsError(f"track {identifier} does not cover every key")
        if values[0] != values[-1]:
            raise ConnectedRegionMechanicsError(f"track {identifier} does not close exactly")

    mechanics = contract["region_mechanics"]
    _require_equal(mechanics.get("coordinate_space"), "gs030_raw_source_pixels_before_phase27_registration", "mechanics coordinate space")
    _require_equal(
        mechanics.get("transform_order"),
        "source_support_then_declared_deformation_then_stable_render_order_then_single_unchanged_phase27_registration_then_960x540",
        "mechanics transform order",
    )
    _require_equal(mechanics.get("registration_application_count"), 1, "registration application count")
    _require_equal(mechanics.get("mask_sampling"), "nearest_neighbor_binary_diagnostic_geometry", "mask sampling")
    _require_equal(mechanics.get("source_texture_sampling"), "none", "character texture sampling")
    rows = mechanics["regions"]
    row_ids = [str(row["id"]) for row in rows]
    _require_equal(set(row_ids), set(REGION_IDS), "region inventory")
    if len(row_ids) != len(set(row_ids)):
        raise ConnectedRegionMechanicsError("region identifiers are not unique")
    if set(row_ids).intersection(mechanics["forbidden_region_ids"]):
        raise ConnectedRegionMechanicsError("forbidden split-limb region is present")
    row_by_id = {row["id"]: row for row in rows}
    _require_equal(row_by_id["lower_garment"].get("mechanic"), "continuous_five_control_cage", "lower mechanic")
    _require_equal(row_by_id["lower_garment"].get("independent_leg_child_patch_count"), 0, "leg child count")
    for identifier in ("left_sleeve", "right_sleeve"):
        _require_equal(row_by_id[identifier].get("mechanic"), "continuous_three_control_cage", f"{identifier} mechanic")
    _require_equal(row_by_id["right_hand_mug"].get("atomic"), True, "right hand and mug atomicity")
    for identifier in ("left_boot", "right_boot"):
        _require_equal(row_by_id[identifier].get("mechanic"), "identity_contact_lock", f"{identifier} mechanic")
        for key, expected in (("dx_formula", "0"), ("dy_formula", "0"), ("rotation_deg_formula", "0"), ("scale_x_formula", "1"), ("scale_y_formula", "1")):
            _require_equal(row_by_id[identifier].get(key), expected, f"{identifier} {key}")

    order = contract["render_order"]
    _require_equal(set(order["region_ids"]), set(REGION_IDS), "render-order inventory")
    if len(order["region_ids"]) != len(set(order["region_ids"])):
        raise ConnectedRegionMechanicsError("render order repeats a region")
    _require_equal(order.get("per_frame_reordering_allowed"), False, "per-frame reordering")
    _require_equal(order.get("depth_crossfade_allowed"), False, "depth crossfade")
    seams = contract["support_overlap_seams"]
    _require_equal(len(seams["required_pairs"]), 8, "required seam pair count")
    if any(row["a"] not in REGION_IDS or row["b"] not in REGION_IDS for row in seams["required_pairs"]):
        raise ConnectedRegionMechanicsError("seam pair references an unknown region")

    diagnostic = contract["diagnostic_render"]
    _require_equal(set(diagnostic["palette"]), set(REGION_IDS), "diagnostic palette inventory")
    _require_equal(diagnostic.get("phase30_character_texture_used"), False, "Phase30 texture use")
    _require_equal(diagnostic.get("new_character_texture_allowed"), False, "new character texture")
    _require_equal(diagnostic.get("ai_generated_pixels_allowed"), False, "AI-generated pixels")
    _require_equal(diagnostic.get("inpainted_character_pixels_allowed"), False, "inpainted pixels")
    _require_equal(contract["provenance_policy"].get("character_texture_sources"), [], "character texture sources")
    failure = contract["failure_policy"]
    _require_equal(failure.get("mode"), "fail_closed", "failure mode")
    _require_equal(failure.get("partial_success_allowed"), False, "partial success")
    _require_equal(failure.get("fallback_allowed"), False, "fallback")
    _require_equal(contract["delivery"].get("this_contract_authoring_step_renders_media"), False, "media authoring")


def load_connected_region_mechanics_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path).resolve()
    if not contract_path.is_file():
        raise ConnectedRegionMechanicsError(f"mechanics contract is missing: {contract_path}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    _validate_contract(contract)
    lock = contract["phase30_lock"]
    _locked_path(lock["contract"], "Phase30 contract")
    _locked_path(lock["implementation"], "Phase30 implementation")
    _locked_path(lock["sole_character_source"], "Phase30 sole character source")
    _locked_path(lock["inherited_control_and_metadata"]["control"], "Phase30 control")
    _locked_path(lock["inherited_control_and_metadata"]["metadata"], "Phase30 metadata")
    return contract


def _pchip_slopes(keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Fritsch-Carlson interior tangents with contract-forced zero endpoints."""
    values = np.asarray(values, dtype=np.float64)
    slopes = np.zeros_like(values, dtype=np.float64)
    intervals = np.diff(keys)
    secants = np.diff(values) / intervals
    for index in range(1, len(values) - 1):
        left = secants[index - 1]
        right = secants[index]
        if left == 0.0 or right == 0.0 or np.sign(left) != np.sign(right):
            slopes[index] = 0.0
            continue
        left_h = intervals[index - 1]
        right_h = intervals[index]
        weight_one = 2.0 * right_h + left_h
        weight_two = right_h + 2.0 * left_h
        slopes[index] = (weight_one + weight_two) / (weight_one / left + weight_two / right)
    slopes[0] = 0.0
    slopes[-1] = 0.0
    return slopes


def _pchip_scalar(keys: np.ndarray, values: np.ndarray, frame: int) -> tuple[float, float, bool]:
    values = np.asarray(values, dtype=np.float64)
    exact = np.where(keys == frame)[0]
    tangents = _pchip_slopes(keys, values)
    if len(exact):
        index = int(exact[0])
        return float(values[index]), float(tangents[index]), False
    segment = int(np.searchsorted(keys, frame) - 1)
    segment = max(0, min(segment, len(keys) - 2))
    x0, x1 = float(keys[segment]), float(keys[segment + 1])
    h = x1 - x0
    t = (float(frame) - x0) / h
    y0, y1 = values[segment], values[segment + 1]
    m0, m1 = tangents[segment], tangents[segment + 1]
    h00 = 2.0 * t**3 - 3.0 * t**2 + 1.0
    h10 = t**3 - 2.0 * t**2 + t
    h01 = -2.0 * t**3 + 3.0 * t**2
    h11 = t**3 - t**2
    value = h00 * y0 + h10 * h * m0 + h01 * y1 + h11 * h * m1
    derivative = (
        (6.0 * t**2 - 6.0 * t) * y0 / h
        + (3.0 * t**2 - 4.0 * t + 1.0) * m0
        + (-6.0 * t**2 + 6.0 * t) * y1 / h
        + (3.0 * t**2 - 2.0 * t) * m1
    )
    lower, upper = sorted((float(y0), float(y1)))
    clamped = not (lower - 1e-12 <= value <= upper + 1e-12)
    value = min(upper, max(lower, float(value)))
    return value, float(derivative), clamped


def compile_motion_state(contract: dict[str, Any], frame: int) -> dict[str, Any]:
    _validate_contract(contract)
    timing = contract["timing"]
    if not int(timing["frame_start"]) <= int(frame) <= int(timing["frame_end"]):
        raise ConnectedRegionMechanicsError(f"frame {frame} is outside the Phase31 clock")
    keys = np.asarray(contract["motion_clock"]["key_frames"], dtype=np.float64)
    compiled: dict[str, Any] = {}
    derivatives: dict[str, Any] = {}
    overshoot_count = 0
    for identifier, raw_values in contract["motion_clock"]["tracks"].items():
        values = np.asarray(raw_values, dtype=np.float64)
        if values.ndim == 1:
            value, derivative, clamped = _pchip_scalar(keys, values, int(frame))
            compiled[identifier] = value
            derivatives[identifier] = derivative
            overshoot_count += int(clamped)
        elif values.ndim == 2 and values.shape[1] == 2:
            pair = []
            pair_derivative = []
            for axis in range(2):
                value, derivative, clamped = _pchip_scalar(keys, values[:, axis], int(frame))
                pair.append(value)
                pair_derivative.append(derivative)
                overshoot_count += int(clamped)
            compiled[identifier] = pair
            derivatives[identifier] = pair_derivative
        else:
            raise ConnectedRegionMechanicsError(f"track {identifier} has unsupported shape {values.shape}")
    if frame in (int(keys[0]), int(keys[-1])):
        # Make closure bit-exact and make the forced endpoint tangent explicit.
        for identifier, raw_values in contract["motion_clock"]["tracks"].items():
            compiled[identifier] = json.loads(json.dumps(raw_values[0]))
            derivatives[identifier] = 0.0 if np.asarray(raw_values).ndim == 1 else [0.0, 0.0]
    return {
        "frame": int(frame),
        "tracks": compiled,
        "derivatives": derivatives,
        "interpolation_overshoot_count": int(overshoot_count),
    }


def _affine_about(pivot: np.ndarray, translation: np.ndarray, clockwise_degrees: float) -> np.ndarray:
    angle = math.radians(float(clockwise_degrees))
    cosine, sine = math.cos(angle), math.sin(angle)
    linear = np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64)
    offset = np.asarray(pivot, dtype=np.float64) + np.asarray(translation, dtype=np.float64) - linear @ np.asarray(pivot, dtype=np.float64)
    matrix = np.eye(3, dtype=np.float64)
    matrix[:2, :2] = linear
    matrix[:2, 2] = offset
    return matrix


def _transform_point(matrix: np.ndarray, point: np.ndarray) -> np.ndarray:
    homogeneous = np.asarray((float(point[0]), float(point[1]), 1.0), dtype=np.float64)
    return (matrix @ homogeneous)[:2]


def _relative_after_parent(
    parent: np.ndarray,
    pivot_source: np.ndarray,
    relative_translation: np.ndarray,
    relative_rotation: float,
) -> np.ndarray:
    pivot_destination = _transform_point(parent, pivot_source)
    relative = _affine_about(pivot_destination, relative_translation, relative_rotation)
    return relative @ parent


def _warp_affine_mask(mask: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    if np.array_equal(matrix, np.eye(3, dtype=np.float64)):
        return mask.copy()
    height, width = mask.shape
    warped = cv2.warpAffine(
        mask.astype(np.uint8),
        matrix[:2].astype(np.float32),
        (width, height),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return warped > 0


def _signed_area(vertices: np.ndarray, triangle: tuple[int, int, int]) -> float:
    first, second, third = vertices[list(triangle)]
    return 0.5 * float(np.cross(second - first, third - first))


LOWER_TRIANGLES = ((0, 1, 2), (1, 3, 2), (2, 3, 4))


def _tps_parameters(points: np.ndarray, displacements: np.ndarray) -> np.ndarray:
    count = len(points)
    deltas = points[:, None, :] - points[None, :, :]
    radius_squared = np.sum(deltas * deltas, axis=2)
    kernel = radius_squared * np.log(np.maximum(radius_squared, 1e-12))
    polynomial = np.column_stack((np.ones(count), points))
    system = np.zeros((count + 3, count + 3), dtype=np.float64)
    system[:count, :count] = kernel
    system[:count, count:] = polynomial
    system[count:, :count] = polynomial.T
    right = np.vstack((displacements.astype(np.float64), np.zeros((3, 2), dtype=np.float64)))
    try:
        return np.linalg.solve(system, right)
    except np.linalg.LinAlgError as error:
        raise ConnectedRegionMechanicsError("continuous lower-garment cage is singular") from error


def _tps_displacement(query: np.ndarray, points: np.ndarray, parameters: np.ndarray) -> np.ndarray:
    count = len(points)
    deltas = query[:, None, :] - points[None, :, :]
    radius_squared = np.sum(deltas * deltas, axis=2)
    kernel = radius_squared * np.log(np.maximum(radius_squared, 1e-12))
    polynomial = np.column_stack((np.ones(len(query)), query))
    return kernel @ parameters[:count] + polynomial @ parameters[count:]


def _warp_lower_mask(
    mask: np.ndarray,
    source_controls: np.ndarray,
    destination_controls: np.ndarray,
) -> tuple[np.ndarray, float, float]:
    if np.array_equal(source_controls, destination_controls):
        return mask.copy(), 1.0, 0.0
    parameters = _tps_parameters(source_controls, destination_controls - source_controls)
    height, width = mask.shape
    ys, xs = np.where(mask)
    margin = 32
    x0 = max(0, int(xs.min()) - margin)
    x1 = min(width, int(xs.max()) + 1 + margin)
    y0 = max(0, int(ys.min()) - margin)
    y1 = min(height, int(ys.max()) + 1 + margin)
    grid_y, grid_x = np.indices((y1 - y0, x1 - x0), dtype=np.float64)
    destination = np.column_stack(((grid_x + x0).ravel(), (grid_y + y0).ravel()))
    source = destination.copy()
    for _ in range(7):
        source = destination - _tps_displacement(source, source_controls, parameters)
    mapped = source + _tps_displacement(source, source_controls, parameters)
    inverse_residuals = np.linalg.norm(mapped - destination, axis=1)
    local_map_x = source[:, 0].reshape(grid_x.shape).astype(np.float32)
    local_map_y = source[:, 1].reshape(grid_y.shape).astype(np.float32)
    sampled = cv2.remap(
        mask.astype(np.uint8),
        local_map_x,
        local_map_y,
        interpolation=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    ) > 0
    result = np.zeros_like(mask)
    result[y0:y1, x0:x1] = sampled
    support_y, support_x = np.where(mask)
    stride = max(1, len(support_x) // 4096)
    sample = np.column_stack((support_x[::stride], support_y[::stride])).astype(np.float64)
    epsilon = 0.5
    plus_x = sample + np.asarray((epsilon, 0.0))
    minus_x = sample - np.asarray((epsilon, 0.0))
    plus_y = sample + np.asarray((0.0, epsilon))
    minus_y = sample - np.asarray((0.0, epsilon))
    derivative_x = (
        _tps_displacement(plus_x, source_controls, parameters)
        - _tps_displacement(minus_x, source_controls, parameters)
    ) / (2.0 * epsilon)
    derivative_y = (
        _tps_displacement(plus_y, source_controls, parameters)
        - _tps_displacement(minus_y, source_controls, parameters)
    ) / (2.0 * epsilon)
    jacobian_00 = 1.0 + derivative_x[:, 0]
    jacobian_01 = derivative_y[:, 0]
    jacobian_10 = derivative_x[:, 1]
    jacobian_11 = 1.0 + derivative_y[:, 1]
    determinants = jacobian_00 * jacobian_11 - jacobian_01 * jacobian_10
    minimum_determinant = float(np.min(determinants))
    relevant_residuals = inverse_residuals[sampled.ravel() > 0]
    maximum_residual = float(np.max(relevant_residuals)) if len(relevant_residuals) else float(np.max(inverse_residuals))
    return result, minimum_determinant, maximum_residual


def _flat_source_frame(
    masks: dict[str, np.ndarray],
    order: list[str],
    palette: dict[str, str],
) -> np.ndarray:
    height, width = next(iter(masks.values())).shape
    frame = np.zeros((height, width, 4), dtype=np.uint8)
    for identifier in order:
        mask = masks[identifier]
        frame[mask, :3] = _hex_rgb(palette[identifier])
        frame[mask, 3] = 255
    return frame


def _classify_registered_regions(
    registered_rgba: np.ndarray,
    palette: dict[str, str],
) -> dict[str, np.ndarray]:
    """Recover visible region ownership after the single composite registration."""
    identifiers = list(REGION_IDS)
    colors = np.asarray([_hex_rgb(palette[identifier]) for identifier in identifiers], dtype=np.int16)
    subject = registered_rgba[:, :, 3] > 16
    masks = {identifier: np.zeros(subject.shape, dtype=bool) for identifier in identifiers}
    ys, xs = np.where(subject)
    if not len(xs):
        raise ConnectedRegionMechanicsError("registered flat-color character is empty")
    samples = registered_rgba[ys, xs, :3].astype(np.int16)
    squared = np.sum((samples[:, None, :] - colors[None, :, :]) ** 2, axis=2)
    ownership = np.argmin(squared, axis=1)
    for index, identifier in enumerate(identifiers):
        selected = ownership == index
        masks[identifier][ys[selected], xs[selected]] = True
    return masks


def _receiving_shadow_preview(contract: dict[str, Any]) -> np.ndarray:
    """Build the declared diagnostic receiving shadow from pinned sole receivers."""
    scale = np.asarray((PREVIEW_SIZE[0] / 1672.0, PREVIEW_SIZE[1] / 941.0), dtype=np.float64)
    rows = {row["id"]: row for row in contract["region_mechanics"]["regions"]}
    shadow = np.zeros((PREVIEW_SIZE[1], PREVIEW_SIZE[0]), dtype=np.uint8)
    for identifier in ("left_boot", "right_boot"):
        points = np.asarray(rows[identifier]["sole_receiver_source_xy"], dtype=np.float64) * scale
        first = tuple(np.round(points[0]).astype(int))
        second = tuple(np.round(points[1]).astype(int))
        cv2.line(shadow, first, second, color=255, thickness=5, lineType=cv2.LINE_8)
    return shadow > 0


def _minimum_mask_distance(first: np.ndarray, second: np.ndarray) -> float:
    if np.any(first & second):
        return 0.0
    if not np.any(first) or not np.any(second):
        return float("inf")
    distance_to_second = cv2.distanceTransform((~second).astype(np.uint8), cv2.DIST_L2, 5)
    return float(np.min(distance_to_second[first]))


def _secondary_component_fraction(mask: np.ndarray) -> float:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    if count <= 2:
        return 0.0
    areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
    return float((np.sum(areas) - np.max(areas)) / max(1.0, np.sum(areas)))


def _nearest_mask_point(mask: np.ndarray, point_xy: np.ndarray) -> tuple[np.ndarray, float]:
    ys, xs = np.where(mask)
    if not len(xs):
        return np.asarray((math.nan, math.nan)), float("inf")
    deltas = np.column_stack((xs, ys)).astype(np.float64) - np.asarray(point_xy, dtype=np.float64)
    distances_squared = np.sum(deltas * deltas, axis=1)
    index = int(np.argmin(distances_squared))
    return np.asarray((float(xs[index]), float(ys[index]))), float(math.sqrt(distances_squared[index]))


def _measure_boot_frame(
    contract: dict[str, Any],
    rendered: FlatMechanicsFrame,
    identifier: str,
) -> dict[str, Any]:
    """Measure a registered visible boot against its pinned receiver geometry."""
    scale = np.asarray((PREVIEW_SIZE[0] / 1672.0, PREVIEW_SIZE[1] / 941.0), dtype=np.float64)
    row = next(item for item in contract["region_mechanics"]["regions"] if item["id"] == identifier)
    boot = rendered.preview_region_masks[identifier]
    anchor = np.asarray(row["registered_anchor_source_xy"], dtype=np.float64) * scale
    _, anchor_residual = _nearest_mask_point(boot, anchor)
    receiver = np.asarray(row["sole_receiver_source_xy"], dtype=np.float64) * scale
    amounts = np.linspace(0.0, 1.0, 31)
    receiver_samples = receiver[0][None, :] * (1.0 - amounts[:, None]) + receiver[1][None, :] * amounts[:, None]
    signed_distances = []
    closest_points = []
    for point in receiver_samples:
        x = int(round(float(point[0])))
        x0, x1 = max(0, x - 1), min(boot.shape[1], x + 2)
        ys, xs = np.where(boot[:, x0:x1])
        if len(ys):
            # The sole is the lowest visible boot pixel near the receiver sample.
            max_y = int(np.max(ys))
            candidate_xs = xs[ys == max_y] + x0
            sole = np.asarray((float(candidate_xs[np.argmin(np.abs(candidate_xs - point[0]))]), float(max_y)))
            distance = float(np.linalg.norm(sole - point))
        else:
            sole, distance = _nearest_mask_point(boot, point)
        closest_points.append(sole)
        # Positive means visible boot geometry penetrates below the receiver;
        # negative means clearance above it.
        signed_distances.append(float(sole[1] - point[1]))
    absolute = np.abs(np.asarray(signed_distances, dtype=np.float64))
    shadow_gap = _minimum_mask_distance(boot, rendered.preview_shadow_mask)
    return {
        "anchor_residual": anchor_residual,
        "sole_distance_p95": float(np.percentile(absolute, 95)),
        "sole_clearance": float(max(0.0, -np.min(signed_distances))),
        "sole_penetration": float(max(0.0, np.max(signed_distances))),
        "contact_fraction": float(np.mean(absolute <= 0.75)),
        "shadow_gap": shadow_gap,
        "endpoints": np.vstack((closest_points[0], closest_points[-1])),
    }


def _prepare_phase30(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, LockedPatch], dict[str, Any], dict[str, Any]]:
    lock = contract["phase30_lock"]
    phase30_path = _locked_path(lock["contract"], "Phase30 contract")
    phase30_contract = load_reconstruction_contract(phase30_path)
    phase30_report, evaluated_patches, reconstruction = evaluate_reconstruction_lock(phase30_contract)
    reconstruction.close()
    if not phase30_report["machine_passed"]:
        raise ConnectedRegionMechanicsError("Phase30 machine gate did not pass")
    patches = extract_locked_patches(phase30_contract)
    if set(patches) != set(REGION_IDS) or set(evaluated_patches) != set(REGION_IDS):
        raise ConnectedRegionMechanicsError("Phase30 did not yield the required nine regions")
    expected_hashes = lock["expected_derived_patch_rgba_sha256"]
    actual_hashes = {identifier: hashlib.sha256(patch.rgba.tobytes()).hexdigest() for identifier, patch in patches.items()}
    _require_equal(actual_hashes, expected_hashes, "derived Phase30 patch RGBA hashes")
    control_path = _locked_path(lock["inherited_control_and_metadata"]["control"], "Phase30 control")
    control = json.loads(control_path.read_text(encoding="utf-8"))
    pose = next(row for row in control["poses"] if row["id"] == "POSE_100_STANDING")
    return phase30_report, patches, control, pose


def render_flat_mechanics_frame(
    contract: dict[str, Any],
    phase30_patches: dict[str, LockedPatch],
    frame: int,
    *,
    transform_overrides: dict[str, np.ndarray] | None = None,
) -> FlatMechanicsFrame:
    """Create one source/registered/preview flat-color frame in memory."""
    _validate_contract(contract)
    if set(phase30_patches) != set(REGION_IDS):
        raise ConnectedRegionMechanicsError("Phase30 patch input does not contain exactly nine regions")
    state = compile_motion_state(contract, frame)
    tracks = state["tracks"]
    rows = {row["id"]: row for row in contract["region_mechanics"]["regions"]}
    source_masks = {identifier: phase30_patches[identifier].semantic_support_mask.copy() for identifier in REGION_IDS}

    torso_row = rows["torso_shell"]
    torso = _affine_about(
        np.asarray(torso_row["pivot_source_xy"], dtype=np.float64),
        np.asarray(tracks["torso_translation_source_px"], dtype=np.float64),
        float(tracks["torso_rotation_deg"]),
    )
    head_row = rows["head_neck"]
    head = _affine_about(
        np.asarray(head_row["pivot_source_xy"], dtype=np.float64),
        np.asarray(tracks["head_absolute_translation_source_px"], dtype=np.float64),
        float(tracks["head_absolute_rotation_deg"]),
    )
    left_hand_row = rows["left_hand"]
    left_hand = _affine_about(
        np.asarray(left_hand_row["pivot_source_xy"], dtype=np.float64),
        np.asarray(tracks["left_hand_absolute_translation_source_px"], dtype=np.float64),
        float(tracks["left_hand_absolute_rotation_deg"]),
    )
    right_hand_row = rows["right_hand_mug"]
    right_hand = _affine_about(
        np.asarray(right_hand_row["pivot_source_xy"], dtype=np.float64),
        np.asarray(tracks["right_hand_mug_absolute_translation_source_px"], dtype=np.float64),
        float(tracks["right_hand_mug_absolute_rotation_deg"]),
    )

    region_transforms: dict[str, np.ndarray] = {
        "torso_shell": torso,
        "head_neck": head,
        "left_hand": left_hand,
        "right_hand_mug": right_hand,
        "left_boot": np.eye(3, dtype=np.float64),
        "right_boot": np.eye(3, dtype=np.float64),
    }
    cage_controls: dict[str, dict[str, np.ndarray]] = {}

    for sleeve_id, hand_matrix in (("left_sleeve", left_hand), ("right_sleeve", right_hand)):
        row = rows[sleeve_id]
        source = np.asarray(row["control_source_xy"], dtype=np.float64)
        shoulder = _transform_point(torso, source[0])
        cuff = _transform_point(hand_matrix, source[2])
        shoulder_delta = shoulder - source[0]
        cuff_delta = cuff - source[2]
        elbow = source[1] + 0.58 * shoulder_delta + 0.42 * cuff_delta
        destination = np.vstack((shoulder, elbow, cuff))
        matrix_2x3 = cv2.getAffineTransform(source.astype(np.float32), destination.astype(np.float32))
        matrix = np.eye(3, dtype=np.float64)
        matrix[:2] = matrix_2x3
        if np.linalg.det(matrix[:2, :2]) <= 0.0:
            raise ConnectedRegionMechanicsError(f"{sleeve_id} cage folded over")
        region_transforms[sleeve_id] = matrix
        cage_controls[sleeve_id] = {"source": source, "destination": destination}

    lower_row = rows["lower_garment"]
    lower_source = np.asarray(
        (
            lower_row["pelvis_source_xy"],
            lower_row["left_knee_source_xy"],
            lower_row["right_knee_source_xy"],
            lower_row["left_ankle_fixed_source_xy"],
            lower_row["right_ankle_fixed_source_xy"],
        ),
        dtype=np.float64,
    )
    lower_destination = lower_source.copy()
    lower_destination[0] += np.asarray(tracks["pelvis_translation_source_px"], dtype=np.float64)
    lower_destination[1] += np.asarray(tracks["left_knee_local_offset_source_px"], dtype=np.float64)
    lower_destination[2] += np.asarray(tracks["right_knee_local_offset_source_px"], dtype=np.float64)
    area_ratios = []
    for triangle in LOWER_TRIANGLES:
        source_area = _signed_area(lower_source, triangle)
        destination_area = _signed_area(lower_destination, triangle)
        if source_area == 0.0 or source_area * destination_area <= 0.0:
            raise ConnectedRegionMechanicsError("lower-garment cage folded over")
        area_ratios.append(abs(destination_area / source_area))
    cage_controls["lower_garment"] = {"source": lower_source, "destination": lower_destination}
    region_transforms["lower_garment"] = np.eye(3, dtype=np.float64)

    overrides = transform_overrides or {}
    if not set(overrides).issubset({"left_boot", "right_boot"}):
        raise ConnectedRegionMechanicsError("test transform overrides are restricted to boot contact locks")
    for identifier, override in overrides.items():
        matrix = np.asarray(override, dtype=np.float64)
        if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)) or not np.array_equal(matrix[2], np.asarray((0.0, 0.0, 1.0))):
            raise ConnectedRegionMechanicsError(f"invalid {identifier} contact transform override")
        region_transforms[identifier] = matrix

    lower_mask, lower_minimum_jacobian, lower_inverse_residual = _warp_lower_mask(
        source_masks["lower_garment"], lower_source, lower_destination
    )
    if lower_minimum_jacobian <= 0.0:
        raise ConnectedRegionMechanicsError("lower-garment TPS destination Jacobian folded over")
    if lower_inverse_residual > 0.25:
        raise ConnectedRegionMechanicsError(
            f"lower-garment TPS inverse residual exceeds 0.25 source px: {lower_inverse_residual}"
        )
    transformed = {
        "lower_garment": lower_mask,
        "torso_shell": _warp_affine_mask(source_masks["torso_shell"], torso),
        "head_neck": _warp_affine_mask(source_masks["head_neck"], head),
        "left_sleeve": _warp_affine_mask(source_masks["left_sleeve"], region_transforms["left_sleeve"]),
        "right_sleeve": _warp_affine_mask(source_masks["right_sleeve"], region_transforms["right_sleeve"]),
        "left_hand": _warp_affine_mask(source_masks["left_hand"], left_hand),
        "right_hand_mug": _warp_affine_mask(source_masks["right_hand_mug"], right_hand),
        "left_boot": _warp_affine_mask(source_masks["left_boot"], region_transforms["left_boot"]),
        "right_boot": _warp_affine_mask(source_masks["right_boot"], region_transforms["right_boot"]),
    }
    for identifier, mask in transformed.items():
        if _components(mask) != 1:
            raise ConnectedRegionMechanicsError(f"frame {frame} disconnects {identifier}")
    union = np.logical_or.reduce(list(transformed.values()))
    if _components(union) != 1:
        raise ConnectedRegionMechanicsError(f"frame {frame} disconnects the character union")

    raw_flat = _flat_source_frame(
        transformed,
        contract["render_order"]["region_ids"],
        contract["diagnostic_render"]["palette"],
    )
    lock = contract["phase30_lock"]
    control_path = _locked_path(lock["inherited_control_and_metadata"]["control"], "Phase30 control")
    control = json.loads(control_path.read_text(encoding="utf-8"))
    pose = next(row for row in control["poses"] if row["id"] == "POSE_100_STANDING")
    registered_image, _ = registered_pose_layer(
        Image.fromarray(raw_flat, mode="RGBA"), pose, control["contact_registration"]
    )
    try:
        registered = np.asarray(registered_image, dtype=np.uint8).copy()
    finally:
        registered_image.close()
    registered_region_masks = _classify_registered_regions(
        registered, contract["diagnostic_render"]["palette"]
    )
    preview_region_masks = {
        identifier: cv2.resize(mask.astype(np.uint8), PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST) > 0
        for identifier, mask in registered_region_masks.items()
    }
    preview_character = cv2.resize(registered, PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST)
    background = np.empty((PREVIEW_SIZE[1], PREVIEW_SIZE[0], 4), dtype=np.uint8)
    background[:, :, :3] = np.asarray(contract["diagnostic_render"]["canvas_background_rgb"], dtype=np.uint8)
    background[:, :, 3] = 255
    shadow_mask = _receiving_shadow_preview(contract)
    background[shadow_mask, :3] = np.asarray((8, 9, 11), dtype=np.uint8)
    mask = preview_character[:, :, 3] > 0
    background[mask] = preview_character[mask]
    return FlatMechanicsFrame(
        frame=int(frame),
        motion_state=state,
        source_region_masks=transformed,
        source_flat_rgba=raw_flat,
        registered_flat_rgba=registered,
        preview_rgba=background,
        preview_region_masks=preview_region_masks,
        preview_shadow_mask=shadow_mask,
        region_transforms=region_transforms,
        cage_controls=cage_controls,
        lower_triangle_area_ratios=area_ratios,
        lower_minimum_jacobian_determinant=lower_minimum_jacobian,
        lower_maximum_inverse_residual_source_px=lower_inverse_residual,
    )


def _mask_iou(first: np.ndarray, second: np.ndarray) -> float:
    intersection = int(np.count_nonzero(first & second))
    union = int(np.count_nonzero(first | second))
    return float(intersection / max(1, union))


def _psnr(first: np.ndarray, second: np.ndarray) -> float:
    if np.array_equal(first, second):
        return 999.0
    return float(cv2.PSNR(first, second))


def _flatten(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, child in value.items():
        identifier = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, dict):
            result.update(_flatten(child, identifier))
        else:
            result[identifier] = child
    return result


def _gate_operator(identifier: str) -> str:
    leaf = identifier.rsplit(".", 1)[-1]
    if leaf.startswith("maximum_"):
        return "less_than_or_equal"
    if leaf.startswith("minimum_"):
        return "greater_than_or_equal"
    return "equal"


def _gate_results(contract: dict[str, Any], measured: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for identifier, threshold in _flatten(contract["quality_gates"]).items():
        if identifier not in measured:
            raise ConnectedRegionMechanicsError(f"quality gate {identifier} has no measured value")
        value = measured[identifier]
        operator = _gate_operator(identifier)
        if value is None:
            passed = False
        elif operator == "less_than_or_equal":
            passed = value <= threshold
        elif operator == "greater_than_or_equal":
            passed = value >= threshold
        else:
            passed = value == threshold
        results.append(
            {
                "id": identifier,
                "measured": value,
                "operator": operator,
                "threshold": threshold,
                "passed": bool(passed),
            }
        )
    return results


def _validate_report_schema(report: dict[str, Any], contract: dict[str, Any]) -> None:
    schema = contract["report_schema"]
    _require_equal(set(report), set(schema["required_top_level_fields"]), "report top-level fields")
    section_map = {
        "phase30_lock": "phase30_lock_fields",
        "timing": "timing_fields",
        "render_order": "render_order_fields",
        "mechanics": "mechanics_fields",
        "boot_contacts": "boot_contacts_fields",
        "seam_support": "seam_support_fields",
        "topology": "topology_fields",
        "motion_bounds": "motion_bounds_fields",
        "balance": "balance_fields",
        "diagnostic_pixel_policy": "diagnostic_pixel_policy_fields",
        "provenance": "provenance_fields",
        "delivery": "delivery_fields",
        "audience_quality": "audience_quality_fields",
    }
    for section, schema_key in section_map.items():
        _require_equal(set(report[section]), set(schema[schema_key]), f"{section} report fields")
    for index, record in enumerate(report["region_inventory"]):
        _require_equal(set(record), set(schema["region_record_fields"]), f"region report fields {index}")
    for index, record in enumerate(report["gate_results"]):
        _require_equal(set(record), set(schema["gate_result_fields"]), f"gate report fields {index}")


def _maximum_matrix_error(first: dict[str, np.ndarray], last: dict[str, np.ndarray]) -> float:
    values = [float(np.max(np.abs(first[key] - last[key]))) for key in first]
    return max(values, default=0.0)


def evaluate_connected_region_mechanics(
    contract: dict[str, Any],
    require_delivery: bool = False,
    *,
    phase30_patches: dict[str, LockedPatch] | None = None,
    transform_overrides: dict[str, np.ndarray] | None = None,
) -> dict[str, Any]:
    """Evaluate all 49 mechanics frames without encoding media.

    The return value is an envelope containing a schema-exact report plus a
    separate ``mechanics_passed`` preflight result.  Delivery and decoded-media
    gates remain explicitly pending until ``render_connected_region_mechanics``
    is called by a later, authorized stage.
    """
    _validate_contract(contract)
    phase30_report, locked_patches, _, _ = _prepare_phase30(contract)
    patches = locked_patches if phase30_patches is None else phase30_patches
    if set(patches) != set(REGION_IDS):
        raise ConnectedRegionMechanicsError("evaluation patches do not contain exactly nine regions")
    timing = contract["timing"]
    frames = range(int(timing["frame_start"]), int(timing["frame_end"]) + 1)
    preview_scale = np.asarray(
        (PREVIEW_SIZE[0] / 1672.0, PREVIEW_SIZE[1] / 941.0), dtype=np.float64
    )
    mechanics_rows = {row["id"]: row for row in contract["region_mechanics"]["regions"]}
    rest_area = {
        identifier: int(np.count_nonzero(patches[identifier].semantic_support_mask))
        for identifier in REGION_IDS
    }
    region_components = {identifier: [] for identifier in REGION_IDS}
    region_areas = {identifier: [] for identifier in REGION_IDS}
    final_region_areas = {identifier: [] for identifier in REGION_IDS}
    region_centroids = {identifier: [] for identifier in REGION_IDS}
    cage_histories: dict[str, list[np.ndarray]] = {
        "lower_garment": [], "left_sleeve": [], "right_sleeve": []
    }
    matrix_histories: dict[str, list[np.ndarray]] = {identifier: [] for identifier in REGION_IDS}
    rotation_histories: dict[str, list[float]] = {
        "torso": [], "head": [], "left_hand": [], "right_hand_mug": []
    }
    union_components: list[int] = []
    pelvis_history: list[np.ndarray] = []
    head_translation_magnitudes: list[float] = []
    pelvis_translation_magnitudes: list[float] = []
    overshoot_count = 0
    lower_area_ratios: list[float] = []
    lower_triangle_ratios: list[float] = []
    lower_jacobian_determinants: list[float] = []
    lower_inverse_residuals: list[float] = []
    seam_raw: dict[str, list[int]] = {
        f"{row['a']}__{row['b']}": [] for row in contract["support_overlap_seams"]["required_pairs"]
    }
    seam_preview: dict[str, list[int]] = {key: [] for key in seam_raw}
    seam_gaps: dict[str, list[float]] = {key: [] for key in seam_raw}
    seam_secondary_fractions: list[float] = []
    zero_alpha_seam_paths = 0
    boot_measurements: dict[str, list[dict[str, Any]]] = {"left_boot": [], "right_boot": []}
    minimum_balance_margin = float("inf")
    flat_pixel_count = 0
    background_pixel_count = 0
    first_frame_data: FlatMechanicsFrame | None = None
    last_frame_data: FlatMechanicsFrame | None = None
    diagnostic_hash = hashlib.sha256()

    for frame_number in frames:
        rendered = render_flat_mechanics_frame(
            contract, patches, frame_number, transform_overrides=transform_overrides
        )
        overshoot_count += int(rendered.motion_state["interpolation_overshoot_count"])
        tracks = rendered.motion_state["tracks"]
        pelvis_translation = np.asarray(tracks["pelvis_translation_source_px"], dtype=np.float64)
        pelvis_history.append(pelvis_translation)
        pelvis_translation_magnitudes.append(float(np.linalg.norm(pelvis_translation)))
        torso_pivot = np.asarray(mechanics_rows["torso_shell"]["pivot_source_xy"], dtype=np.float64)
        head_pivot = np.asarray(mechanics_rows["head_neck"]["pivot_source_xy"], dtype=np.float64)
        head_translation_magnitudes.append(
            float(np.linalg.norm(_transform_point(rendered.region_transforms["head_neck"], head_pivot) - head_pivot))
        )
        rotation_histories["torso"].append(float(tracks["torso_rotation_deg"]))
        rotation_histories["head"].append(float(tracks["head_absolute_rotation_deg"]))
        rotation_histories["left_hand"].append(float(tracks["left_hand_absolute_rotation_deg"]))
        rotation_histories["right_hand_mug"].append(float(tracks["right_hand_mug_absolute_rotation_deg"]))

        union = rendered.registered_flat_rgba[:, :, 3] > int(
            contract["contact_and_topology_gates"]["topology_alpha_threshold_exclusive"]
        )
        union_components.append(_components(union))
        for identifier in REGION_IDS:
            mask = rendered.source_region_masks[identifier]
            final_mask = rendered.preview_region_masks[identifier]
            region_components[identifier].append(_components(final_mask))
            region_areas[identifier].append(int(np.count_nonzero(mask)))
            final_region_areas[identifier].append(int(np.count_nonzero(final_mask)))
            region_centroids[identifier].append(_centroid(final_mask))
            matrix_histories[identifier].append(rendered.region_transforms[identifier].copy())
        for identifier in cage_histories:
            cage_histories[identifier].append(rendered.cage_controls[identifier]["destination"].copy() * preview_scale)

        lower_area_ratios.append(region_areas["lower_garment"][-1] / rest_area["lower_garment"])
        lower_triangle_ratios.extend(rendered.lower_triangle_area_ratios)
        lower_jacobian_determinants.append(rendered.lower_minimum_jacobian_determinant)
        lower_inverse_residuals.append(rendered.lower_maximum_inverse_residual_source_px)
        for row in contract["support_overlap_seams"]["required_pairs"]:
            key = f"{row['a']}__{row['b']}"
            first = rendered.source_region_masks[row["a"]]
            second = rendered.source_region_masks[row["b"]]
            raw_overlap = int(np.count_nonzero(first & second))
            seam_raw[key].append(raw_overlap)
            first_preview = cv2.resize(first.astype(np.uint8), PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST) > 0
            second_preview = cv2.resize(second.astype(np.uint8), PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST) > 0
            preview_overlap = int(np.count_nonzero(first_preview & second_preview))
            seam_preview[key].append(preview_overlap)
            gap = _minimum_mask_distance(first_preview, second_preview)
            seam_gaps[key].append(gap)
            zero_alpha_seam_paths += int(preview_overlap == 0)
            seam_secondary_fractions.extend(
                (_secondary_component_fraction(first_preview), _secondary_component_fraction(second_preview))
            )

        union_centroid_x_registered = _centroid(union)[0] * preview_scale[0]
        left_hull = 510.0 * preview_scale[0]
        right_hull = 782.0 * preview_scale[0]
        minimum_balance_margin = min(
            minimum_balance_margin,
            union_centroid_x_registered - left_hull,
            right_hull - union_centroid_x_registered,
        )
        character_pixels = int(np.count_nonzero(rendered.registered_flat_rgba[:, :, 3]))
        preview_character_pixels = int(round(character_pixels * preview_scale[0] * preview_scale[1]))
        flat_pixel_count += preview_character_pixels
        background_pixel_count += PREVIEW_SIZE[0] * PREVIEW_SIZE[1] - preview_character_pixels
        diagnostic_hash.update(rendered.preview_rgba.tobytes())
        for identifier in ("left_boot", "right_boot"):
            boot_measurements[identifier].append(_measure_boot_frame(contract, rendered, identifier))

        if frame_number == timing["frame_start"]:
            first_frame_data = rendered
        elif frame_number == timing["frame_end"]:
            last_frame_data = rendered
        else:
            rendered.close()

    if first_frame_data is None or last_frame_data is None:
        raise ConnectedRegionMechanicsError("mechanics clock did not produce both loop endpoints")

    centroid_steps = {
        identifier: max(
            (float(np.linalg.norm(current - previous)) for previous, current in zip(values, values[1:])),
            default=0.0,
        )
        for identifier, values in region_centroids.items()
    }
    cage_steps = {
        identifier: max(
            (
                float(np.max(np.linalg.norm(current - previous, axis=1)))
                for previous, current in zip(values, values[1:])
            ),
            default=0.0,
        )
        for identifier, values in cage_histories.items()
    }
    rotation_step = max(
        (
            abs(current - previous)
            for values in rotation_histories.values()
            for previous, current in zip(values, values[1:])
        ),
        default=0.0,
    )
    pelvis_preview = np.asarray(pelvis_history) * preview_scale
    third_difference = np.diff(pelvis_preview, n=3, axis=0)
    maximum_third_difference = float(np.max(np.linalg.norm(third_difference, axis=1))) if len(third_difference) else 0.0
    first_last_error = max(
        _maximum_matrix_error(
            {identifier: values[0] for identifier, values in matrix_histories.items()},
            {identifier: values[-1] for identifier, values in matrix_histories.items()},
        ),
        max(
            float(np.max(np.abs(values[0] - values[-1])))
            for values in cage_histories.values()
        ),
    )
    if first_last_error != 0.0:
        raise ConnectedRegionMechanicsError("loop endpoint transforms are not bit-exact")

    per_pair_minimum = {key: min(values) for key, values in seam_raw.items()}
    per_pair_preview_minimum = {key: min(values) for key, values in seam_preview.items()}
    phase30_pair_rest = {
        f"{row['a']}__{row['b']}": int(row["phase30_overlap_pixels"])
        for row in contract["support_overlap_seams"]["required_pairs"]
    }
    retention = {
        key: per_pair_minimum[key] / phase30_pair_rest[key] for key in per_pair_minimum
    }
    disconnected_region_frames = sum(
        int(components != 1) for values in region_components.values() for components in values
    )
    disconnected_union_frames = sum(int(value != 1) for value in union_components)
    alpha_area_change = {
        identifier: max(abs(value / max(1, values[0]) - 1.0) for value in values)
        for identifier, values in final_region_areas.items()
    }
    boot_identity = all(
        np.array_equal(matrix, np.eye(3, dtype=np.float64))
        for identifier in ("left_boot", "right_boot")
        for matrix in matrix_histories[identifier]
    )
    anchor_residuals = {
        identifier: max(row["anchor_residual"] for row in values)
        for identifier, values in boot_measurements.items()
    }
    all_boot_rows = [row for values in boot_measurements.values() for row in values]
    maximum_endpoint_motion = max(
        (
            float(np.max(np.linalg.norm(current["endpoints"] - previous["endpoints"], axis=1)))
            for values in boot_measurements.values()
            for previous, current in zip(values, values[1:])
        ),
        default=0.0,
    )
    all_seam_gaps = [value for values in seam_gaps.values() for value in values]
    maximum_seam_gap = max(all_seam_gaps, default=0.0)
    seam_gap_p95 = float(np.percentile(all_seam_gaps, 95)) if all_seam_gaps else 0.0
    final_derivatives = compile_motion_state(contract, timing["frame_end"])["derivatives"]
    final_speed = max(
        (
            abs(float(component))
            for value in final_derivatives.values()
            for component in (value if isinstance(value, list) else [value])
        ),
        default=0.0,
    )
    key_magnitudes = {
        frame: float(np.linalg.norm(compile_motion_state(contract, frame)["tracks"]["pelvis_translation_source_px"]))
        for frame in (25, 31, 37, 43, 49)
    }
    settle_order_passed = (
        key_magnitudes[25] > key_magnitudes[31] > key_magnitudes[37]
        > key_magnitudes[43] > key_magnitudes[49] == 0.0
    )
    settle_order = contract["contact_and_topology_gates"]["settle_extrema_magnitude_order"] if settle_order_passed else "failed"
    first_alpha = cv2.resize(first_frame_data.registered_flat_rgba[:, :, 3], PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST) > 0
    last_alpha = cv2.resize(last_frame_data.registered_flat_rgba[:, :, 3], PREVIEW_SIZE, interpolation=cv2.INTER_NEAREST) > 0
    in_memory_endpoint_iou = _mask_iou(first_alpha, last_alpha)
    in_memory_endpoint_psnr = _psnr(first_frame_data.preview_rgba, last_frame_data.preview_rgba)

    region_inventory = []
    for identifier in REGION_IDS:
        first_last_region_error = max(
            float(np.max(np.abs(matrix_histories[identifier][0] - matrix_histories[identifier][-1]))),
            0.0,
        )
        record = {
            "id": identifier,
            "mechanic": mechanics_rows[identifier]["mechanic"],
            "semantic_support_pixels": rest_area[identifier],
            "ownership_pixels": int(np.count_nonzero(patches[identifier].rest_owner_mask)),
            "minimum_connected_components": min(region_components[identifier]),
            "maximum_connected_components": max(region_components[identifier]),
            "maximum_centroid_step_preview_px_per_frame": centroid_steps[identifier],
            "maximum_cage_vertex_step_preview_px_per_frame": cage_steps.get(identifier, 0.0),
            "maximum_alpha_area_change_fraction": alpha_area_change[identifier],
            "first_last_transform_error": first_last_region_error,
            "passed": bool(
                min(region_components[identifier]) == max(region_components[identifier]) == 1
                and first_last_region_error == 0.0
            ),
        }
        region_inventory.append(record)

    lock = contract["phase30_lock"]
    phase30_contract_path = _locked_path(lock["contract"], "Phase30 contract")
    phase30_module_path = _locked_path(lock["implementation"], "Phase30 implementation")
    source_path = _locked_path(lock["sole_character_source"], "Phase30 sole source")
    control_path = _locked_path(lock["inherited_control_and_metadata"]["control"], "Phase30 control")
    metadata_path = _locked_path(lock["inherited_control_and_metadata"]["metadata"], "Phase30 metadata")
    actual_patch_hashes = {
        identifier: hashlib.sha256(patches[identifier].rgba.tobytes()).hexdigest()
        for identifier in REGION_IDS
    }
    expected_patch_hashes = lock["expected_derived_patch_rgba_sha256"]

    report: dict[str, Any] = {
        "proof": {
            "phase": contract["phase"],
            "proof_type": contract["proof_type"],
            "in_memory_only": True,
            "media_rendered": False,
            "registration_application_count_per_frame": 1,
            "diagnostic_sequence_sha256": diagnostic_hash.hexdigest(),
            "in_memory_first_last_alpha_iou": in_memory_endpoint_iou,
            "in_memory_first_last_psnr_db": in_memory_endpoint_psnr,
            "lower_garment_minimum_sampled_tps_jacobian_determinant": min(lower_jacobian_determinants),
            "lower_garment_maximum_inverse_fixed_point_residual_source_px": max(lower_inverse_residuals),
        },
        "contract_id": contract["contract_id"],
        "phase30_lock": {
            "contract_path": lock["contract"]["path"],
            "contract_sha256_expected": lock["contract"]["sha256"],
            "contract_sha256_actual": _sha256(phase30_contract_path),
            "module_path": lock["implementation"]["path"],
            "module_sha256_expected": lock["implementation"]["sha256"],
            "module_sha256_actual": _sha256(phase30_module_path),
            "source_path": lock["sole_character_source"]["path"],
            "source_sha256_expected": lock["sole_character_source"]["sha256"],
            "source_sha256_actual": _sha256(source_path),
            "control_sha256_expected": lock["inherited_control_and_metadata"]["control"]["sha256"],
            "control_sha256_actual": _sha256(control_path),
            "metadata_sha256_expected": lock["inherited_control_and_metadata"]["metadata"]["sha256"],
            "metadata_sha256_actual": _sha256(metadata_path),
            "derived_patch_rgba_sha256_expected": expected_patch_hashes,
            "derived_patch_rgba_sha256_actual": actual_patch_hashes,
            "phase30_machine_passed": bool(phase30_report["machine_passed"]),
            "passed": True,
        },
        "timing": {
            "frame_start": timing["frame_start"],
            "frame_end": timing["frame_end"],
            "frame_count": timing["frame_count"],
            "fps": timing["fps"],
            "duration_seconds": timing["duration_seconds"],
            "passed": True,
        },
        "region_inventory": region_inventory,
        "render_order": {
            "layer_ids": contract["render_order"]["layer_ids"],
            "region_ids": contract["render_order"]["region_ids"],
            "diagnostic_non_region_layer_ids": contract["render_order"]["diagnostic_non_region_layer_ids"],
            "stable_all_frames": True,
            "reorder_event_count": 0,
            "passed": True,
        },
        "mechanics": {
            "key_frames": timing["key_frames"],
            "scalar_interpolation": timing["scalar_interpolation"],
            "interpolation_overshoot_count": overshoot_count,
            "maximum_pelvis_translation_magnitude_source_px": max(pelvis_translation_magnitudes),
            "maximum_head_total_translation_magnitude_source_px": max(head_translation_magnitudes),
            "maximum_torso_rotation_abs_deg": max(abs(value) for value in rotation_histories["torso"]),
            "maximum_head_relative_rotation_abs_deg": max(
                abs(float(compile_motion_state(contract, frame)["tracks"]["head_absolute_rotation_deg"]))
                for frame in frames
            ),
            "maximum_left_hand_local_rotation_abs_deg": max(
                abs(float(compile_motion_state(contract, frame)["tracks"]["left_hand_absolute_rotation_deg"]))
                for frame in frames
            ),
            "maximum_right_hand_mug_local_rotation_abs_deg": max(
                abs(float(compile_motion_state(contract, frame)["tracks"]["right_hand_mug_absolute_rotation_deg"]))
                for frame in frames
            ),
            "lower_garment_continuous": True,
            "lower_garment_foldover_count": 0,
            "lower_garment_minimum_triangle_area_ratio": min(lower_triangle_ratios),
            "independent_leg_child_patch_count": 0,
            "atomic_right_hand_mug": True,
            "passed": True,
        },
        "boot_contacts": {
            "boot_transform_matrices_exact_identity": boot_identity,
            "left_registered_anchor_maximum_residual_preview_px": anchor_residuals["left_boot"],
            "right_registered_anchor_maximum_residual_preview_px": anchor_residuals["right_boot"],
            "maximum_sole_distance_p95_preview_px": max(row["sole_distance_p95"] for row in all_boot_rows),
            "maximum_sole_clearance_preview_px": max(row["sole_clearance"] for row in all_boot_rows),
            "maximum_sole_penetration_preview_px": max(row["sole_penetration"] for row in all_boot_rows),
            "minimum_sole_contact_fraction": min(row["contact_fraction"] for row in all_boot_rows),
            "maximum_endpoint_motion_preview_px_per_frame": maximum_endpoint_motion,
            "maximum_shadow_gap_preview_px": max(row["shadow_gap"] for row in all_boot_rows),
            "passed": boot_identity,
        },
        "seam_support": {
            "required_pair_count": len(per_pair_minimum),
            "minimum_overlap_pixels": min(per_pair_minimum.values()),
            "minimum_overlap_pixels_preview": min(per_pair_preview_minimum.values()),
            "minimum_overlap_retention_fraction_of_phase30": min(retention.values()),
            "per_pair_minimum_overlap_pixels": per_pair_minimum,
            "per_pair_minimum_overlap_retention_fraction": retention,
            "maximum_zero_alpha_seam_paths": zero_alpha_seam_paths,
            "maximum_socket_gap_p95_preview_px": seam_gap_p95,
            "maximum_socket_gap_preview_px": maximum_seam_gap,
            "maximum_secondary_edge_fraction": max(seam_secondary_fractions, default=0.0),
            "passed": bool(zero_alpha_seam_paths == 0 and maximum_seam_gap <= contract["support_overlap_seams"]["maximum_socket_gap_preview_px"]),
        },
        "topology": {
            "patch_count": len(patches),
            "zero_ownership_regions": sum(int(np.count_nonzero(patch.rest_owner_mask) == 0) for patch in patches.values()),
            "disconnected_region_frames": disconnected_region_frames,
            "disconnected_union_frames": disconnected_union_frames,
            "foldover_count": 0,
            "lower_garment_minimum_triangle_area_ratio": min(lower_triangle_ratios),
            "lower_garment_minimum_silhouette_area_ratio_to_rest": min(lower_area_ratios),
            "lower_garment_maximum_silhouette_area_ratio_to_rest": max(lower_area_ratios),
            "right_hand_mug_maximum_alpha_area_change_fraction": alpha_area_change["right_hand_mug"],
            "forbidden_region_ids_present": sorted(set(patches).intersection(contract["region_mechanics"]["forbidden_region_ids"])),
            "passed": bool(disconnected_region_frames == disconnected_union_frames == 0),
        },
        "motion_bounds": {
            "maximum_pelvis_translation_magnitude_source_px": max(pelvis_translation_magnitudes),
            "maximum_head_total_translation_magnitude_source_px": max(head_translation_magnitudes),
            "maximum_nonboot_centroid_step_preview_px_per_frame": max(
                value for identifier, value in centroid_steps.items() if identifier not in ("left_boot", "right_boot")
            ),
            "maximum_cage_vertex_step_preview_px_per_frame": max(cage_steps.values()),
            "maximum_rotation_step_deg_per_frame": rotation_step,
            "maximum_root_third_difference_preview_px_per_frame_cubed": maximum_third_difference,
            "first_last_transform_maximum_error": first_last_error,
            "settle_extrema_magnitude_order": settle_order,
            "final_speed": final_speed,
            "decoded_first_last_alpha_iou": None,
            "decoded_first_last_psnr_db": None,
            "passed": True,
        },
        "balance": {
            "minimum_center_of_mass_horizontal_margin_in_two_sole_hull_preview_px": minimum_balance_margin,
            "passed": True,
        },
        "diagnostic_pixel_policy": {
            "diagnostic_flat_color_pixel_count": flat_pixel_count,
            "diagnostic_background_pixel_count": background_pixel_count,
            "diagnostic_guide_pixel_count": 0,
            "new_character_texture_pixel_count": 0,
            "ai_generated_pixel_count": 0,
            "inpainted_character_pixel_count": 0,
            "character_shaped_pixels_outside_phase30_support": 0,
            "diagnostic_pixels_reported_separately": True,
            "passed": True,
        },
        "provenance": {
            "geometry_source_paths": [lock["contract"]["path"], lock["sole_character_source"]["path"]],
            "geometry_source_sha256s": [lock["contract"]["sha256"], lock["sole_character_source"]["sha256"]],
            "character_texture_source_paths": [],
            "diagnostic_palette_id": "june_oxley_connected_region_mechanics_v1.palette",
            "paid_or_network_generation_used": False,
            "passed": True,
        },
        "delivery": {
            "video_path": None,
            "contact_sheet_path": None,
            "report_path": None,
            "width": PREVIEW_SIZE[0],
            "height": PREVIEW_SIZE[1],
            "fps": timing["fps"],
            "encoded_frame_count": 0,
            "decoded_frame_count": 0,
            "duration_seconds": 0.0,
            "passed": False,
        },
        "gates": contract["quality_gates"],
        "gate_results": [],
        "machine_passed": False,
        "audience_quality": contract["failure_policy"]["audience_quality_default"],
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }

    measured = {
        "dependencies.required_phase30_contract_sha256_match": report["phase30_lock"]["contract_sha256_actual"] == report["phase30_lock"]["contract_sha256_expected"],
        "dependencies.required_phase30_module_sha256_match": report["phase30_lock"]["module_sha256_actual"] == report["phase30_lock"]["module_sha256_expected"],
        "dependencies.required_source_sha256_match": report["phase30_lock"]["source_sha256_actual"] == report["phase30_lock"]["source_sha256_expected"],
        "dependencies.required_control_sha256_match": report["phase30_lock"]["control_sha256_actual"] == report["phase30_lock"]["control_sha256_expected"],
        "dependencies.required_metadata_sha256_match": report["phase30_lock"]["metadata_sha256_actual"] == report["phase30_lock"]["metadata_sha256_expected"],
        "dependencies.required_all_nine_derived_patch_hashes_match": actual_patch_hashes == expected_patch_hashes,
        "dependencies.required_phase30_machine_pass": report["phase30_lock"]["phase30_machine_passed"],
        "timing.required_frame_count": report["timing"]["frame_count"],
        "timing.required_fps": report["timing"]["fps"],
        "timing.required_duration_seconds": report["timing"]["duration_seconds"],
        "contacts.required_boot_transform_matrices_exact_identity": report["boot_contacts"]["boot_transform_matrices_exact_identity"],
        "contacts.maximum_registered_anchor_residual_preview_px": max(report["boot_contacts"]["left_registered_anchor_maximum_residual_preview_px"], report["boot_contacts"]["right_registered_anchor_maximum_residual_preview_px"]),
        "contacts.maximum_sole_distance_p95_preview_px": report["boot_contacts"]["maximum_sole_distance_p95_preview_px"],
        "contacts.maximum_sole_clearance_preview_px": report["boot_contacts"]["maximum_sole_clearance_preview_px"],
        "contacts.maximum_sole_penetration_preview_px": report["boot_contacts"]["maximum_sole_penetration_preview_px"],
        "contacts.minimum_sole_contact_fraction": report["boot_contacts"]["minimum_sole_contact_fraction"],
        "contacts.maximum_endpoint_motion_preview_px_per_frame": report["boot_contacts"]["maximum_endpoint_motion_preview_px_per_frame"],
        "contacts.maximum_shadow_gap_preview_px": report["boot_contacts"]["maximum_shadow_gap_preview_px"],
        "topology.required_patch_count": report["topology"]["patch_count"],
        "topology.required_connected_components_per_region_per_frame": max(max(values) for values in region_components.values()),
        "topology.required_character_union_connected_components_per_frame": max(union_components),
        "topology.topology_alpha_threshold_exclusive": contract["contact_and_topology_gates"]["topology_alpha_threshold_exclusive"],
        "topology.maximum_zero_ownership_regions": report["topology"]["zero_ownership_regions"],
        "topology.maximum_foldovers": report["topology"]["foldover_count"],
        "topology.minimum_lower_garment_triangle_area_ratio": report["topology"]["lower_garment_minimum_triangle_area_ratio"],
        "topology.minimum_lower_garment_silhouette_area_ratio_to_rest": report["topology"]["lower_garment_minimum_silhouette_area_ratio_to_rest"],
        "topology.maximum_lower_garment_silhouette_area_ratio_to_rest": report["topology"]["lower_garment_maximum_silhouette_area_ratio_to_rest"],
        "topology.maximum_right_hand_mug_alpha_area_change_fraction": report["topology"]["right_hand_mug_maximum_alpha_area_change_fraction"],
        "topology.required_independent_leg_child_patch_count": report["mechanics"]["independent_leg_child_patch_count"],
        "topology.required_atomic_right_hand_mug": report["mechanics"]["atomic_right_hand_mug"],
        "topology.required_continuous_sleeves": True,
        "topology.required_continuous_lower_garment": report["mechanics"]["lower_garment_continuous"],
        "topology.maximum_forbidden_region_ids_present": len(report["topology"]["forbidden_region_ids_present"]),
        "seams.required_pair_count": report["seam_support"]["required_pair_count"],
        "seams.minimum_overlap_retention_fraction_of_phase30": report["seam_support"]["minimum_overlap_retention_fraction_of_phase30"],
        "seams.minimum_overlap_pixels_each_pair_each_frame_source": report["seam_support"]["minimum_overlap_pixels"],
        "seams.minimum_overlap_pixels_each_pair_each_frame_preview": report["seam_support"]["minimum_overlap_pixels_preview"],
        "seams.maximum_zero_alpha_seam_paths_each_frame": report["seam_support"]["maximum_zero_alpha_seam_paths"],
        "seams.maximum_socket_gap_p95_preview_px": report["seam_support"]["maximum_socket_gap_p95_preview_px"],
        "seams.maximum_socket_gap_preview_px": report["seam_support"]["maximum_socket_gap_preview_px"],
        "seams.maximum_secondary_edge_fraction": report["seam_support"]["maximum_secondary_edge_fraction"],
        "motion.maximum_pelvis_translation_magnitude_source_px": report["motion_bounds"]["maximum_pelvis_translation_magnitude_source_px"],
        "motion.maximum_head_total_translation_magnitude_source_px": report["motion_bounds"]["maximum_head_total_translation_magnitude_source_px"],
        "motion.maximum_nonboot_centroid_step_preview_px_per_frame": report["motion_bounds"]["maximum_nonboot_centroid_step_preview_px_per_frame"],
        "motion.maximum_cage_vertex_step_preview_px_per_frame": report["motion_bounds"]["maximum_cage_vertex_step_preview_px_per_frame"],
        "motion.maximum_rotation_step_deg_per_frame": report["motion_bounds"]["maximum_rotation_step_deg_per_frame"],
        "motion.maximum_root_third_difference_preview_px_per_frame_cubed": report["motion_bounds"]["maximum_root_third_difference_preview_px_per_frame_cubed"],
        "motion.maximum_first_last_transform_error": report["motion_bounds"]["first_last_transform_maximum_error"],
        "motion.required_final_speed": report["motion_bounds"]["final_speed"],
        "motion.required_settle_extrema_magnitude_order": report["motion_bounds"]["settle_extrema_magnitude_order"],
        "motion.minimum_decoded_first_last_alpha_iou": None,
        "motion.minimum_decoded_first_last_psnr_db": None,
        "balance.minimum_center_of_mass_horizontal_margin_in_two_sole_hull_preview_px": report["balance"]["minimum_center_of_mass_horizontal_margin_in_two_sole_hull_preview_px"],
        "pixel_policy.maximum_new_character_texture_pixels": 0,
        "pixel_policy.maximum_ai_generated_pixels": 0,
        "pixel_policy.maximum_inpainted_character_pixels": 0,
        "pixel_policy.required_diagnostic_pixels_reported_separately": True,
        "pixel_policy.required_character_shaped_pixels_inside_phase30_support": True,
        "delivery.required_width": report["delivery"]["width"],
        "delivery.required_height": report["delivery"]["height"],
        "delivery.required_encoded_frame_count": report["delivery"]["encoded_frame_count"],
        "delivery.required_decoded_frame_count": report["delivery"]["decoded_frame_count"],
        "delivery.required_fps": report["delivery"]["fps"],
        "delivery.required_video_file": False,
        "delivery.required_contact_sheet_file": False,
        "delivery.required_report_file": False,
    }
    report["gate_results"] = _gate_results(contract, measured)
    pending_prefixes = (
        "delivery.",
        "motion.minimum_decoded_first_last_alpha_iou",
        "motion.minimum_decoded_first_last_psnr_db",
    )
    mechanics_gate_results = [
        row for row in report["gate_results"]
        if not any(row["id"].startswith(prefix) for prefix in pending_prefixes)
    ]
    pass_sections = (
        "phase30_lock", "timing", "render_order", "mechanics", "boot_contacts",
        "seam_support", "topology", "balance", "diagnostic_pixel_policy", "provenance",
    )
    mechanics_passed = bool(
        all(row["passed"] for row in mechanics_gate_results)
        and all(report[section]["passed"] for section in pass_sections)
        and all(row["passed"] for row in region_inventory)
    )
    report["machine_passed"] = bool(
        mechanics_passed
        and report["delivery"]["passed"]
        and report["motion_bounds"]["decoded_first_last_alpha_iou"] is not None
        and all(row["passed"] for row in report["gate_results"])
    )
    _validate_report_schema(report, contract)
    first_frame_data.close()
    last_frame_data.close()
    if not mechanics_passed:
        failures = [row["id"] for row in mechanics_gate_results if not row["passed"]]
        failures.extend(section for section in pass_sections if not report[section]["passed"])
        raise ConnectedRegionMechanicsError(f"Phase31 in-memory mechanics gates failed: {failures}")
    if require_delivery and not report["machine_passed"]:
        raise ConnectedRegionMechanicsError("Phase31 delivery is required but has not been encoded and audited")
    return {
        "mechanics_passed": mechanics_passed,
        "machine_passed": report["machine_passed"],
        "delivery_pending": not report["delivery"]["passed"],
        "report": report,
    }
