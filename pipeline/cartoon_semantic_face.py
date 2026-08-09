from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline.cartoon_resolution_scene import prepare_resolution_sources


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase33_semantic_face_v3.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_semantic_face.py"


class SemanticFaceError(RuntimeError):
    pass


@dataclass
class PreparedSemanticFace:
    contract: dict[str, Any]
    contract_path: Path
    plate: np.ndarray
    lid_texture: np.ndarray
    moustache_mask: np.ndarray
    beard_mask: np.ndarray
    feature_support: np.ndarray
    preflight_measurements: dict[str, Any]


@dataclass
class FrameEvidence:
    blink_closure: float
    mouth_pose_weights: dict[str, float]
    iris_occlusion_ratios: list[float]
    lid_areas: list[int]
    cavity_area: int
    upper_teeth_area: int
    lower_teeth_area: int
    tongue_area: int
    moustache_front_overlap: int
    beard_front_overlap: int
    changed_pixels: int
    changed_outside_support: int
    final_owner_counts: dict[str, int]
    multiply_owned_final_pixels: int


OWNER_NAMES = {
    0: "authored_plate",
    1: "mouth_cavity",
    2: "tongue",
    3: "lower_teeth",
    4: "upper_teeth",
    5: "upper_lip",
    6: "lower_lip",
    7: "upper_lids",
    8: "lower_lids",
    9: "lid_crease",
    10: "moustache",
    11: "beard_clearance",
}


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _raw_frame_hash(frame: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SemanticFaceError(f"complete Phase33 v3 contract required: {label}: {actual!r} != {expected!r}")


def _resolve_repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SemanticFaceError(f"locked source escapes repository: {relative}") from exc
    return path


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase33_semantic_face_v3", "contract id")
    _require_equal(contract["view_id"], "CLOSE_HERO_FRONT_GS070", "view")
    representation = contract["representation"]
    _require_equal(representation["method"], "source_aligned_semantic_occlusion_2p5d_v1", "representation")
    _require_equal(representation["complete_eye_or_mouth_photo_crossfades_allowed"], False, "photo crossfade")
    _require_equal(representation["foreign_atlas_pixels_allowed"], False, "foreign atlas")
    _require_equal(representation["paired_canonical_atlas_semantic_lid_pixels_allowed"], True, "paired lid pixels")
    _require_equal(representation["head_motion_allowed"], False, "head motion")
    _require_equal(representation["camera_motion_allowed"], False, "camera motion")
    _require_equal(representation["audio_allowed"], False, "audio")
    _require_equal(representation["neutral_bypass_is_exact_source_plate"], True, "neutral bypass")
    _require_equal(representation["single_final_output_resample"], True, "resample")
    _require_equal(
        representation["depth_order_back_to_front"],
        [
            "authored_plate_open_eye_and_neutral_mouth",
            "mouth_cavity",
            "tongue",
            "lower_teeth_jaw_driven",
            "upper_teeth_skull_locked",
            "upper_lip",
            "lower_lip_jaw_driven",
            "upper_lids",
            "lower_lids",
            "lid_crease",
            "moustache_source_pixels",
            "beard_clearance_source_pixels",
        ],
        "depth order",
    )
    _require_equal(contract["clock"], {
        "source_width": 1672,
        "source_height": 941,
        "output_width": 1920,
        "output_height": 1080,
        "fps": 30,
        "frame_count": 60,
        "duration_seconds": 2.0,
    }, "clock")
    _require_equal(contract["performance"]["exact_neutral_frames"], [1, 8, 19, 22, 60], "neutral frames")
    _require_equal(contract["performance"]["required_pose_order"], ["neutral", "blink", "B", "A", "F", "neutral"], "pose order")
    failure = contract["failure_policy"]
    _require_equal(failure["mode"], "fail_closed", "failure mode")
    _require_equal(failure["automatic_reencode_allowed"], False, "automatic reencode")
    _require_equal(failure["caller_selected_output_directory_allowed"], False, "caller output")
    _require_equal(contract["delivery"]["one_video_encode_without_retry"], True, "one encode")
    _require_equal(contract["delivery"]["staged_atomic_directory_publication"], True, "atomic publication")
    _require_equal(contract["promotion_policy"]["reinforcement_learning_allowed"], False, "RL")
    for name, reference in contract["locks"].items():
        path = _resolve_repo_path(reference["path"])
        if not path.is_file():
            raise SemanticFaceError(f"missing locked source {name}: {path}")
        actual = _sha256(path)
        if actual != reference["sha256"]:
            raise SemanticFaceError(f"{name} SHA-256 mismatch: {actual} != {reference['sha256']}")


def load_semantic_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    _validate_contract(contract)
    return contract


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def blink_closure(frame_number: int) -> float:
    if 9 <= frame_number <= 13:
        return _ease((frame_number - 8) / 5.0)
    if frame_number == 14:
        return 1.0
    if 15 <= frame_number <= 18:
        return _ease((19 - frame_number) / 5.0)
    return 0.0


def _pose_vector(contract: dict[str, Any], name: str) -> np.ndarray:
    pose = contract["pose_geometry_native_px"][name]
    return np.asarray([
        pose["mouth_width"], pose["cavity_height"], pose["jaw_drop"],
        pose["upper_teeth"], pose["lower_teeth"], pose["tongue"],
    ], dtype=np.float32)


def mouth_controls(contract: dict[str, Any], frame_number: int) -> tuple[np.ndarray, dict[str, float]]:
    keyframes = [(22, "neutral"), (28, "B"), (38, "A"), (48, "F"), (52, "F"), (60, "neutral")]
    if frame_number <= keyframes[0][0]:
        return _pose_vector(contract, "neutral"), {"neutral": 1.0, "B": 0.0, "A": 0.0, "F": 0.0}
    for (left_frame, left_name), (right_frame, right_name) in zip(keyframes, keyframes[1:]):
        if left_frame <= frame_number <= right_frame:
            if left_name == right_name:
                return _pose_vector(contract, left_name), {
                    "neutral": float(left_name == "neutral"), "B": float(left_name == "B"),
                    "A": float(left_name == "A"), "F": float(left_name == "F"),
                }
            t = _ease((frame_number - left_frame) / float(right_frame - left_frame))
            values = (1.0 - t) * _pose_vector(contract, left_name) + t * _pose_vector(contract, right_name)
            weights = {"neutral": 0.0, "B": 0.0, "A": 0.0, "F": 0.0}
            weights[left_name] += 1.0 - t
            weights[right_name] += t
            return values, weights
    return _pose_vector(contract, "neutral"), {"neutral": 1.0, "B": 0.0, "A": 0.0, "F": 0.0}


def _polygon_mask(shape: tuple[int, int], points: list[tuple[int, int]]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.fillPoly(mask, [np.asarray(points, dtype=np.int32)], 255)
    return mask


def _hair_mask(plate: np.ndarray, roi: list[int], polygon: list[tuple[int, int]]) -> np.ndarray:
    height, width = plate.shape[:2]
    poly = _polygon_mask((height, width), polygon)
    hsv = cv2.cvtColor(plate, cv2.COLOR_RGB2HSV)
    rgb_range = plate.max(axis=2).astype(np.int16) - plate.min(axis=2).astype(np.int16)
    hair = (
        (poly > 0)
        & (hsv[:, :, 1] < 112)
        & (hsv[:, :, 2] > 78)
        & (rgb_range < 88)
    ).astype(np.uint8) * 255
    x1, y1, x2, y2 = roi
    bounds = np.zeros_like(hair)
    bounds[y1:y2, x1:x2] = 255
    hair = cv2.bitwise_and(hair, bounds)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    hair = cv2.morphologyEx(hair, cv2.MORPH_CLOSE, kernel, iterations=1)
    return hair


def _ellipse_mask(
    shape: tuple[int, int], center: tuple[float, float], radii: tuple[float, float], angle: float = 0.0,
) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.ellipse(
        mask,
        (int(round(center[0])), int(round(center[1]))),
        (max(1, int(round(radii[0]))), max(1, int(round(radii[1])))),
        angle, 0.0, 360.0, 255, -1, lineType=cv2.LINE_AA,
    )
    return mask


def _blend_color(canvas: np.ndarray, color: np.ndarray, alpha: np.ndarray) -> None:
    a = (alpha.astype(np.float32) / 255.0)[:, :, None]
    canvas[:] = np.clip(canvas.astype(np.float32) * (1.0 - a) + color.astype(np.float32) * a, 0, 255).astype(np.uint8)


def _blend_source(canvas: np.ndarray, source: np.ndarray, alpha: np.ndarray) -> None:
    _blend_color(canvas, source, alpha)


def _soft(mask: np.ndarray, sigma: float = 0.85) -> np.ndarray:
    return cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma, sigmaY=sigma)


def _color_field(shape: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> np.ndarray:
    height, width = shape
    t = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
    top_array = np.asarray(top, dtype=np.float32)[None, None, :]
    bottom_array = np.asarray(bottom, dtype=np.float32)[None, None, :]
    row = top_array * (1.0 - t) + bottom_array * t
    return np.repeat(row, width, axis=1).astype(np.uint8)


def _compose_eye_lids(
    canvas: np.ndarray,
    plate: np.ndarray,
    lid_texture: np.ndarray,
    owner: np.ndarray,
    center: tuple[int, int],
    radius: tuple[int, int],
    closure: float,
) -> tuple[float, int]:
    if closure <= 0.0:
        return 0.0, 0
    cx, cy = center
    rx, ry = radius
    x1, y1 = cx - rx - 5, cy - ry - 12
    x2, y2 = cx + rx + 6, cy + ry + 12
    plate_roi = plate[y1:y2, x1:x2]
    lid_texture_roi = lid_texture[y1:y2, x1:x2]
    canvas_roi = canvas[y1:y2, x1:x2]
    owner_roi = owner[y1:y2, x1:x2]
    roi_height, roi_width = plate_roi.shape[:2]
    yy, xx = np.indices((roi_height, roi_width), dtype=np.float32)
    local_cx, local_cy = cx - x1, cy - y1
    ellipse = (((xx - local_cx) / rx) ** 2 + ((yy - local_cy) / ry) ** 2) <= 1.0
    upper_edge = local_cy - ry + closure * (ry + 1.5)
    lower_edge = local_cy + ry - closure * (ry + 1.5)
    upper_hard = ellipse & (yy <= upper_edge)
    lower_hard = ellipse & (yy >= lower_edge)

    upper_alpha = _soft(upper_hard.astype(np.uint8) * 255, 0.7)
    lower_alpha = _soft(lower_hard.astype(np.uint8) * 255, 0.7)
    _blend_source(canvas_roi, lid_texture_roi, upper_alpha)
    owner_roi[upper_hard] = 7
    _blend_source(canvas_roi, lid_texture_roi, lower_alpha)
    owner_roi[lower_hard] = 8

    if closure > 0.72:
        crease = np.zeros((roi_height, roi_width), dtype=np.uint8)
        amplitude = 2.0 + 1.5 * closure
        points = []
        for x in range(local_cx - rx + 4, local_cx + rx - 3):
            normalized = (x - local_cx) / float(rx)
            y = int(round(local_cy + amplitude * (normalized * normalized - 0.45)))
            points.append((x, y))
        cv2.polylines(crease, [np.asarray(points, dtype=np.int32)], False, 190, 1, lineType=cv2.LINE_AA)
        crease_alpha = (crease.astype(np.float32) * min(1.0, (closure - 0.72) / 0.28)).astype(np.uint8)
        crease_color = np.zeros_like(canvas_roi)
        crease_color[:] = np.asarray([111, 67, 47], dtype=np.uint8)
        _blend_color(canvas_roi, crease_color, crease_alpha)
        owner_roi[crease_alpha > 96] = 9

    iris = (((xx - local_cx) / 11.5) ** 2 + ((yy - local_cy) / 14.0) ** 2) <= 1.0
    occluded = iris & (upper_hard | lower_hard)
    ratio = float(occluded.sum() / max(1, iris.sum()))
    return ratio, int((upper_hard | lower_hard).sum())


def _compose_mouth(
    canvas: np.ndarray,
    plate: np.ndarray,
    owner: np.ndarray,
    moustache_mask: np.ndarray,
    beard_mask: np.ndarray,
    center: tuple[int, int],
    controls: np.ndarray,
) -> dict[str, int]:
    width, cavity_height, jaw_drop, upper_teeth_amount, lower_teeth_amount, tongue_amount = [float(v) for v in controls]
    if width <= 0.01 or cavity_height <= 0.01:
        return {
            "cavity": 0, "upper_teeth": 0, "lower_teeth": 0, "tongue": 0,
            "moustache_overlap": 0, "beard_overlap": 0,
        }
    cx, cy = center
    cy = cy + int(round(jaw_drop * 0.22))
    x1, y1, x2, y2 = 500, 305, 755, 525
    plate_roi = plate[y1:y2, x1:x2]
    canvas_roi = canvas[y1:y2, x1:x2]
    owner_roi = owner[y1:y2, x1:x2]
    moustache_roi = moustache_mask[y1:y2, x1:x2]
    beard_roi = beard_mask[y1:y2, x1:x2]
    roi_height, roi_width = plate_roi.shape[:2]
    local_center = (cx - x1, cy - y1)
    mouth_angle = 5.0
    cavity = _ellipse_mask(
        (roi_height, roi_width), local_center, (width / 2.0, max(1.5, cavity_height / 2.0)), mouth_angle,
    )
    cavity_hard = cavity > 128
    cavity_color = _color_field((roi_height, roi_width), (61, 22, 19), (29, 8, 12))
    source_luma = cv2.GaussianBlur(cv2.cvtColor(plate_roi, cv2.COLOR_RGB2GRAY), (0, 0), 3.0).astype(np.float32)
    texture = np.clip((source_luma - float(source_luma.mean())) * 0.055, -4.0, 4.0)[:, :, None]
    cavity_color = np.clip(cavity_color.astype(np.float32) + texture, 0, 255).astype(np.uint8)
    _blend_color(canvas_roi, cavity_color, _soft(cavity, 0.85))
    owner_roi[cavity_hard] = 1

    yy, xx = np.indices((roi_height, roi_width), dtype=np.float32)
    local_cx, local_cy = local_center
    theta = math.radians(mouth_angle)
    dx = xx - local_cx
    dy = yy - local_cy
    mouth_u = math.cos(theta) * dx + math.sin(theta) * dy
    mouth_v = -math.sin(theta) * dx + math.cos(theta) * dy
    tongue = np.zeros_like(cavity)
    if tongue_amount > 0.01:
        tongue_center = (local_cx, local_cy + cavity_height * 0.28)
        tongue_shape = _ellipse_mask(
            (roi_height, roi_width), tongue_center,
            (width * (0.25 + 0.08 * tongue_amount), cavity_height * (0.13 + 0.10 * tongue_amount)),
            mouth_angle,
        )
        tongue = cv2.bitwise_and(tongue_shape, cavity)
        tongue_color = _color_field((roi_height, roi_width), (156, 69, 62), (105, 37, 43))
        _blend_color(canvas_roi, tongue_color, _soft(tongue, 0.65))
        owner_roi[tongue > 128] = 2

    lower_teeth = np.zeros_like(cavity)
    if lower_teeth_amount > 0.01:
        band_height = max(1, int(round(7.0 * lower_teeth_amount)))
        band = ((mouth_v >= cavity_height * 0.18) & (mouth_v <= cavity_height * 0.18 + band_height)).astype(np.uint8) * 255
        central = (np.abs(mouth_u) <= width * 0.36).astype(np.uint8) * 255
        lower_teeth = cv2.bitwise_and(cv2.bitwise_and(cavity, band), central)
        teeth_color = _color_field((roi_height, roi_width), (226, 209, 170), (174, 151, 119))
        _blend_color(canvas_roi, teeth_color, _soft(lower_teeth, 0.45))
        owner_roi[lower_teeth > 128] = 3

    upper_teeth = np.zeros_like(cavity)
    if upper_teeth_amount > 0.01:
        band_height = max(2, int(round(13.0 * upper_teeth_amount)))
        arch = 2.2 * (1.0 - np.clip((mouth_u / max(1.0, width / 2.0)) ** 2, 0.0, 1.0))
        top = -cavity_height / 2.0 + 3.0
        band = ((mouth_v >= top) & (mouth_v <= top + band_height + arch)).astype(np.uint8) * 255
        central = (np.abs(mouth_u) <= width * 0.36).astype(np.uint8) * 255
        upper_teeth = cv2.bitwise_and(cv2.bitwise_and(cavity, band), central)
        teeth_color = _color_field((roi_height, roi_width), (246, 230, 193), (189, 165, 126))
        _blend_color(canvas_roi, teeth_color, _soft(upper_teeth, 0.45))
        separators = ((np.mod(mouth_u + width / 2.0, 11.0) < 0.7) & (upper_teeth > 128)).astype(np.uint8) * 72
        separator_color = np.zeros_like(canvas_roi)
        separator_color[:] = np.asarray([119, 91, 68], dtype=np.uint8)
        _blend_color(canvas_roi, separator_color, separators)
        owner_roi[upper_teeth > 128] = 4

    outer = _ellipse_mask(
        (roi_height, roi_width), local_center,
        (width / 2.0 + 2.4, max(3.5, cavity_height / 2.0 + 2.3)), mouth_angle,
    )
    lip_ring = cv2.subtract(outer, cavity)
    upper_lip = lip_ring.copy()
    upper_lip[mouth_v > 0.5] = 0
    lower_lip = lip_ring.copy()
    lower_lip[mouth_v < -0.5] = 0
    upper_color = _color_field((roi_height, roi_width), (143, 73, 53), (111, 50, 42))
    lower_color = _color_field((roi_height, roi_width), (176, 97, 72), (126, 60, 52))
    _blend_color(canvas_roi, upper_color, _soft(upper_lip, 0.65))
    owner_roi[upper_lip > 128] = 5
    _blend_color(canvas_roi, lower_color, _soft(lower_lip, 0.65))
    owner_roi[lower_lip > 128] = 6

    moustache_overlap = int((cavity_hard & (moustache_roi > 0)).sum())
    beard_overlap = int((cavity_hard & (beard_roi > 0)).sum())
    moustache_alpha = _soft(moustache_roi, 0.55)
    beard_alpha = _soft(beard_roi, 0.55)
    _blend_source(canvas_roi, plate_roi, moustache_alpha)
    owner_roi[moustache_roi > 0] = 10
    _blend_source(canvas_roi, plate_roi, beard_alpha)
    owner_roi[beard_roi > 0] = 11
    return {
        "cavity": int(cavity_hard.sum()),
        "upper_teeth": int((upper_teeth > 128).sum()),
        "lower_teeth": int((lower_teeth > 128).sum()),
        "tongue": int((tongue > 128).sum()),
        "moustache_overlap": moustache_overlap,
        "beard_overlap": beard_overlap,
    }


def _native_frame(prepared: PreparedSemanticFace, frame_number: int) -> tuple[np.ndarray, FrameEvidence]:
    if not 1 <= frame_number <= prepared.contract["clock"]["frame_count"]:
        raise SemanticFaceError(f"frame number out of range: {frame_number}")
    plate = prepared.plate
    canvas = plate.copy()
    owner = np.zeros(plate.shape[:2], dtype=np.uint8)
    closure = blink_closure(frame_number)
    controls, weights = mouth_controls(prepared.contract, frame_number)

    geometry = prepared.contract["semantic_geometry_native_xy"]
    mouth = _compose_mouth(
        canvas, plate, owner, prepared.moustache_mask, prepared.beard_mask,
        tuple(geometry["mouth_center"]), controls,
    )
    iris_ratios: list[float] = []
    lid_areas: list[int] = []
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        ratio, area = _compose_eye_lids(
            canvas, plate, prepared.lid_texture, owner, tuple(eye["center"]), tuple(eye["radius"]), closure,
        )
        iris_ratios.append(ratio)
        lid_areas.append(area)

    changed = np.any(canvas != plate, axis=2)
    outside = changed & ~prepared.feature_support
    counts = {OWNER_NAMES[index]: int((owner == index).sum()) for index in OWNER_NAMES if int((owner == index).sum()) > 0}
    evidence = FrameEvidence(
        blink_closure=closure,
        mouth_pose_weights={name: float(value) for name, value in weights.items()},
        iris_occlusion_ratios=iris_ratios,
        lid_areas=lid_areas,
        cavity_area=mouth["cavity"],
        upper_teeth_area=mouth["upper_teeth"],
        lower_teeth_area=mouth["lower_teeth"],
        tongue_area=mouth["tongue"],
        moustache_front_overlap=mouth["moustache_overlap"],
        beard_front_overlap=mouth["beard_overlap"],
        changed_pixels=int(changed.sum()),
        changed_outside_support=int(outside.sum()),
        final_owner_counts=counts,
        multiply_owned_final_pixels=0,
    )
    return canvas, evidence


def compose_semantic_frame(prepared: PreparedSemanticFace, frame_number: int) -> Image.Image:
    native, _ = _native_frame(prepared, frame_number)
    clock = prepared.contract["clock"]
    image = Image.fromarray(native, "RGB")
    return image.resize((clock["output_width"], clock["output_height"]), Image.Resampling.LANCZOS)


def _max_8x8_delta(first: np.ndarray, second: np.ndarray, mask: np.ndarray | None = None) -> float:
    delta = np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(axis=2)
    local = cv2.boxFilter(delta, -1, (8, 8), normalize=True)
    if mask is not None:
        values = local[mask]
        return float(values.max()) if values.size else 0.0
    return float(local.max())


def _preflight(prepared: PreparedSemanticFace) -> dict[str, Any]:
    frames: dict[int, tuple[np.ndarray, FrameEvidence]] = {}
    maximum_outside = 0
    maximum_delta = 0.0
    maximum_delta_pair = [1, 1]
    previous: np.ndarray | None = None
    for frame_number in range(1, 61):
        frame, evidence = _native_frame(prepared, frame_number)
        frames[frame_number] = (frame, evidence)
        maximum_outside = max(maximum_outside, evidence.changed_outside_support)
        if previous is not None:
            adjacent_delta = _max_8x8_delta(previous, frame, prepared.feature_support)
            if adjacent_delta > maximum_delta:
                maximum_delta = adjacent_delta
                maximum_delta_pair = [frame_number - 1, frame_number]
        previous = frame
    plate = prepared.plate
    endpoint_changes = max(
        int(np.any(frames[1][0] != plate, axis=2).sum()),
        int(np.any(frames[60][0] != plate, axis=2).sum()),
    )
    blink = frames[14][1]
    b_pose = frames[28][1]
    a_pose = frames[38][1]
    f_pose = frames[48][1]
    return {
        "exact_endpoint_changed_pixels": endpoint_changes,
        "maximum_changed_pixels_outside_feature_support": maximum_outside,
        "minimum_full_blink_iris_occlusion_ratio": min(blink.iris_occlusion_ratios),
        "minimum_full_blink_lid_area_per_eye": min(blink.lid_areas),
        "B_cavity_area": b_pose.cavity_area,
        "A_cavity_area": a_pose.cavity_area,
        "F_upper_teeth_area": f_pose.upper_teeth_area,
        "A_moustache_front_overlap_pixels": a_pose.moustache_front_overlap,
        "A_beard_front_overlap_pixels": a_pose.beard_front_overlap,
        "maximum_multiply_owned_final_pixels": max(e.multiply_owned_final_pixels for _, e in frames.values()),
        "maximum_adjacent_feature_8x8_mean_delta": maximum_delta,
        "maximum_adjacent_feature_8x8_mean_delta_frame_pair": maximum_delta_pair,
        "frames_evaluated": 60,
        "single_final_output_resample": True,
        "foreign_atlas_pixels_used": False,
        "paired_canonical_semantic_lid_pixels_used": True,
        "head_motion_used": False,
        "camera_motion_used": False,
        "audio_used": False,
    }


def _preflight_gates(contract: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    gates = contract["preencode_gates"]
    checks = [
        ("exact_endpoint_changed_pixels", metrics["exact_endpoint_changed_pixels"], "==", gates["required_exact_endpoint_changed_pixels"]),
        ("changed_pixels_outside_feature_support", metrics["maximum_changed_pixels_outside_feature_support"], "==", gates["required_changes_outside_feature_support"]),
        ("full_blink_iris_occlusion", metrics["minimum_full_blink_iris_occlusion_ratio"], ">=", gates["minimum_full_blink_iris_occlusion_ratio"]),
        ("full_blink_lid_area", metrics["minimum_full_blink_lid_area_per_eye"], ">=", gates["minimum_full_blink_lid_area_per_eye"]),
        ("A_cavity_area", metrics["A_cavity_area"], ">=", gates["minimum_A_cavity_area"]),
        ("B_cavity_area", metrics["B_cavity_area"], "<=", gates["maximum_B_cavity_area"]),
        ("F_upper_teeth_area", metrics["F_upper_teeth_area"], ">=", gates["minimum_F_upper_teeth_area"]),
        ("moustache_front_overlap", metrics["A_moustache_front_overlap_pixels"], ">=", gates["minimum_moustache_front_overlap_pixels"]),
        ("beard_front_overlap", metrics["A_beard_front_overlap_pixels"], ">=", gates["minimum_beard_front_overlap_pixels"]),
        ("multiply_owned_final_pixels", metrics["maximum_multiply_owned_final_pixels"], "==", gates["maximum_multiply_owned_final_pixels"]),
        ("adjacent_feature_8x8_mean_delta", metrics["maximum_adjacent_feature_8x8_mean_delta"], "<=", gates["maximum_adjacent_feature_8x8_mean_delta"]),
    ]
    results = []
    for name, actual, operator, threshold in checks:
        passed = actual == threshold if operator == "==" else actual >= threshold if operator == ">=" else actual <= threshold
        results.append({"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(passed)})
    return results


def prepare_semantic_face(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> PreparedSemanticFace:
    contract_path = Path(path).resolve()
    contract = load_semantic_contract(contract_path)
    plate_path = _resolve_repo_path(contract["locks"]["gs070_plate"]["path"])
    plate = np.asarray(Image.open(plate_path).convert("RGB"), dtype=np.uint8)
    clock = contract["clock"]
    if plate.shape != (clock["source_height"], clock["source_width"], 3):
        raise SemanticFaceError(f"plate dimensions changed: {plate.shape}")
    geometry = contract["semantic_geometry_native_xy"]
    moustache = _hair_mask(
        plate, geometry["moustache_roi"],
        [(525, 357), (558, 330), (600, 326), (635, 342), (673, 328), (716, 347), (725, 381), (680, 386), (636, 381), (592, 390), (540, 382)],
    )
    beard = _hair_mask(
        plate, geometry["beard_clearance_roi"],
        [(526, 389), (575, 380), (635, 391), (699, 378), (738, 395), (744, 449), (704, 503), (575, 509), (518, 447)],
    )
    registered = prepare_resolution_sources(
        _resolve_repo_path(contract["locks"]["gs070_contract"]["path"]),
        _resolve_repo_path(contract["locks"]["paired_viseme_contract"]["path"]),
        _resolve_repo_path(contract["locks"]["paired_expression_contract"]["path"]),
    )
    blink_patch = np.asarray(registered["expression_patches"]["blink"].convert("RGB"), dtype=np.uint8)
    lid_texture = plate.copy()
    source_boxes = {
        "viewer_left_eye": (73, 76, 139, 135),
        "viewer_right_eye": (198, 88, 265, 149),
    }
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        cx, cy = eye["center"]
        rx, ry = eye["radius"]
        sx1, sy1, sx2, sy2 = source_boxes[eye_name]
        source = blink_patch[sy1:sy2, sx1:sx2]
        resized = cv2.resize(source, (rx * 2 + 1, ry * 2 + 1), interpolation=cv2.INTER_CUBIC)
        tx1, ty1 = cx - rx, cy - ry
        tx2, ty2 = cx + rx + 1, cy + ry + 1
        target = cv2.inpaint(
            plate,
            _ellipse_mask(plate.shape[:2], tuple(eye["center"]), tuple(eye["radius"])),
            5.0,
            cv2.INPAINT_TELEA,
        )[ty1:ty2, tx1:tx2]
        source_pixels = resized.reshape(-1, 3).astype(np.float32)
        target_pixels = target.reshape(-1, 3).astype(np.float32)
        source_mean = source_pixels.mean(axis=0)
        source_std = np.maximum(source_pixels.std(axis=0), 1.0)
        target_mean = target_pixels.mean(axis=0)
        target_std = np.maximum(target_pixels.std(axis=0), 1.0)
        matched = (resized.astype(np.float32) - source_mean) * (target_std / source_std) * 0.82 + target_mean
        lid_texture[ty1:ty2, tx1:tx2] = np.clip(matched, 0, 255).astype(np.uint8)
    support = np.zeros(plate.shape[:2], dtype=np.uint8)
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        expanded = _ellipse_mask(plate.shape[:2], tuple(eye["center"]), (eye["radius"][0] + 7, eye["radius"][1] + 7))
        support = cv2.bitwise_or(support, expanded)
    x1, y1, x2, y2 = geometry["mouth_allowed_box"]
    support[y1:y2, x1:x2] = 255
    prepared = PreparedSemanticFace(contract, contract_path, plate, lid_texture, moustache, beard, support > 0, {})
    prepared.preflight_measurements = _preflight(prepared)
    failures = [gate for gate in _preflight_gates(contract, prepared.preflight_measurements) if not gate["passed"]]
    if failures:
        raise SemanticFaceError("semantic preflight failed: " + json.dumps(failures, sort_keys=True))
    return prepared


def _contact_sheet(frames: list[Image.Image], columns: int, tile: tuple[int, int], labels: list[str]) -> Image.Image:
    rows = int(math.ceil(len(frames) / columns))
    sheet = Image.new("RGB", (columns * tile[0], rows * tile[1]), (16, 13, 10))
    draw = ImageDraw.Draw(sheet)
    for index, (frame, label) in enumerate(zip(frames, labels)):
        thumb = frame.copy()
        thumb.thumbnail((tile[0], tile[1]), Image.Resampling.LANCZOS)
        x = (index % columns) * tile[0] + (tile[0] - thumb.width) // 2
        y = (index // columns) * tile[1] + (tile[1] - thumb.height) // 2
        sheet.paste(thumb, (x, y))
        draw.rectangle((x + 3, y + 3, x + 48, y + 18), fill=(15, 12, 10))
        draw.text((x + 7, y + 5), label, fill=(246, 227, 186))
    return sheet


def _preview_output_path(contract: dict[str, Any]) -> Path:
    return (REPO_ROOT / contract["preview"]["directory"]).resolve()


def _delivery_output_path(contract: dict[str, Any]) -> Path:
    return (REPO_ROOT / contract["delivery"]["output_directory"]).resolve()


def write_unencoded_preview(
    contract_path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> dict[str, Any]:
    prepared = prepare_semantic_face(contract_path)
    output = _preview_output_path(prepared.contract)
    if output.exists():
        raise SemanticFaceError(f"immutable preview already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    try:
        frames: list[Image.Image] = []
        hashes = []
        for frame_number in range(1, 61):
            frame = compose_semantic_frame(prepared, frame_number)
            rgb = np.asarray(frame, dtype=np.uint8)
            frames.append(frame)
            hashes.append({"frame": frame_number, "rgb_sha256": _raw_frame_hash(rgb)})
        all_sheet = _contact_sheet(frames, 12, (160, 90), [f"F{index:02d}" for index in range(1, 61)])
        all_path = stage / prepared.contract["preview"]["contact_sheet_filename"]
        all_sheet.save(all_path, format="PNG", optimize=True)
        key_numbers = [1, 8, 13, 14, 19, 22, 28, 33, 38, 43, 48, 52, 56, 60]
        clock = prepared.contract["clock"]
        sx = clock["output_width"] / clock["source_width"]
        sy = clock["output_height"] / clock["source_height"]
        crop_native = (485, 175, 800, 535)
        crop = tuple(int(round(value * (sx if index % 2 == 0 else sy))) for index, value in enumerate(crop_native))
        key_frames = [frames[number - 1].crop(crop) for number in key_numbers]
        key_sheet = _contact_sheet(key_frames, 7, (315, 360), [f"F{number:02d}" for number in key_numbers])
        key_path = stage / prepared.contract["preview"]["key_sheet_filename"]
        key_sheet.save(key_path, format="PNG", optimize=True)
        manifest = {
            "manifest_version": 1,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": _sha256(prepared.contract_path),
                "canonical_sha256": _canonical_hash(prepared.contract),
            },
            "implementation": {
                "path": IMPLEMENTATION_RELATIVE_PATH,
                "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
            },
            "clock": prepared.contract["clock"],
            "source_plate_sha256": prepared.contract["locks"]["gs070_plate"]["sha256"],
            "frame_hash_domain": "raw_rgb24_1920x1080_row_major",
            "frames": hashes,
            "all_60_contact_sheet": {"file": all_path.name, "sha256": _sha256(all_path)},
            "key_pose_sheet": {"file": key_path.name, "sha256": _sha256(key_path)},
            "preflight_measurements": prepared.preflight_measurements,
            "preflight_gates": _preflight_gates(prepared.contract, prepared.preflight_measurements),
            "complete_beat_review_required": True,
            "final_encode_allowed_without_bound_review_receipt": False,
        }
        manifest_path = stage / prepared.contract["preview"]["manifest_filename"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(stage, output)
        return {
            "preview_directory": str(output),
            "manifest": str(output / manifest_path.name),
            "manifest_sha256": _sha256(output / manifest_path.name),
            "contact_sheet": str(output / all_path.name),
            "key_sheet": str(output / key_path.name),
        }
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def _verify_preview_review(prepared: PreparedSemanticFace) -> tuple[dict[str, Any], dict[str, Any], Path]:
    preview_dir = _preview_output_path(prepared.contract)
    manifest_path = preview_dir / prepared.contract["preview"]["manifest_filename"]
    if not manifest_path.is_file():
        raise SemanticFaceError("bound all-frame preview manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["contract"]["raw_sha256"] != _sha256(prepared.contract_path):
        raise SemanticFaceError("preview contract hash changed")
    if manifest["implementation"]["sha256"] != _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH):
        raise SemanticFaceError("implementation changed after preview")
    if len(manifest["frames"]) != 60:
        raise SemanticFaceError("preview does not bind all 60 frames")
    for key in ("all_60_contact_sheet", "key_pose_sheet"):
        artifact = preview_dir / manifest[key]["file"]
        if not artifact.is_file() or _sha256(artifact) != manifest[key]["sha256"]:
            raise SemanticFaceError(f"preview artifact changed: {key}")
    review_path = _resolve_repo_path(prepared.contract["preview"]["review_receipt"])
    if not review_path.is_file():
        raise SemanticFaceError("explicit preview review receipt is missing")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("status") != "all_60_unencoded_frames_reviewed_encode_once_allowed":
        raise SemanticFaceError("preview review did not authorize one encode")
    if review.get("manifest_sha256") != _sha256(manifest_path):
        raise SemanticFaceError("preview review is not bound to current manifest")
    if review.get("contract_raw_sha256") != _sha256(prepared.contract_path):
        raise SemanticFaceError("preview review contract hash changed")
    if review.get("implementation_sha256") != _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH):
        raise SemanticFaceError("preview review implementation hash changed")
    return manifest, review, manifest_path


def _psnr(first: np.ndarray, second: np.ndarray) -> float:
    mse = float(np.mean((first.astype(np.float32) - second.astype(np.float32)) ** 2))
    if mse <= 1e-12:
        return 99.0
    return float(10.0 * math.log10((255.0 * 255.0) / mse))


def _ssim(first: np.ndarray, second: np.ndarray) -> float:
    first_f = first.astype(np.float32)
    second_f = second.astype(np.float32)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    scores = []
    for channel in range(3):
        a = first_f[:, :, channel]
        b = second_f[:, :, channel]
        mu_a = cv2.GaussianBlur(a, (11, 11), 1.5)
        mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)
        sigma_a = cv2.GaussianBlur(a * a, (11, 11), 1.5) - mu_a * mu_a
        sigma_b = cv2.GaussianBlur(b * b, (11, 11), 1.5) - mu_b * mu_b
        sigma_ab = cv2.GaussianBlur(a * b, (11, 11), 1.5) - mu_a * mu_b
        numerator = (2.0 * mu_a * mu_b + c1) * (2.0 * sigma_ab + c2)
        denominator = (mu_a * mu_a + mu_b * mu_b + c1) * (sigma_a + sigma_b + c2)
        scores.append(float(np.mean(numerator / np.maximum(denominator, 1e-12))))
    return float(np.mean(scores))


def _probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    command = [
        ffprobe, "-v", "error", "-show_entries",
        "stream=index,codec_type,codec_name,pix_fmt,width,height,r_frame_rate,nb_frames:format=duration",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _decode_and_measure(
    prepared: PreparedSemanticFace,
    video: Path,
    stage: Path,
) -> tuple[dict[str, Any], list[np.ndarray]]:
    capture = cv2.VideoCapture(str(video))
    decoded: list[np.ndarray] = []
    while True:
        ok, bgr = capture.read()
        if not ok:
            break
        decoded.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    capture.release()
    if len(decoded) != 60:
        raise SemanticFaceError(f"full decode required 60 frames, got {len(decoded)}")
    gates = prepared.contract["decoded_gates"]
    face = gates["face_roi_xyxy"]
    eyes = gates["eye_roi_xyxy"]
    mouth = gates["mouth_roi_xyxy"]
    full_psnr: list[float] = []
    face_psnr: list[float] = []
    face_ssim: list[float] = []
    eye_psnr: list[float] = []
    mouth_psnr: list[float] = []
    sharpness: list[float] = []
    temporal: list[float] = []
    previous_face: np.ndarray | None = None
    for frame_number, encoded in enumerate(decoded, start=1):
        expected = np.asarray(compose_semantic_frame(prepared, frame_number), dtype=np.uint8)
        full_psnr.append(_psnr(expected, encoded))
        expected_face = expected[face[1]:face[3], face[0]:face[2]]
        encoded_face = encoded[face[1]:face[3], face[0]:face[2]]
        face_psnr.append(_psnr(expected_face, encoded_face))
        face_ssim.append(_ssim(expected_face, encoded_face))
        eye_psnr.append(_psnr(expected[eyes[1]:eyes[3], eyes[0]:eyes[2]], encoded[eyes[1]:eyes[3], eyes[0]:eyes[2]]))
        mouth_psnr.append(_psnr(expected[mouth[1]:mouth[3], mouth[0]:mouth[2]], encoded[mouth[1]:mouth[3], mouth[0]:mouth[2]]))
        sharpness.append(float(cv2.Laplacian(cv2.cvtColor(encoded, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()))
        if previous_face is not None:
            temporal.append(_max_8x8_delta(previous_face, encoded_face))
        previous_face = encoded_face
    sheet_frames = [Image.fromarray(frame, "RGB") for frame in decoded]
    sheet = _contact_sheet(sheet_frames, 12, (160, 90), [f"F{index:02d}" for index in range(1, 61)])
    sheet_path = stage / prepared.contract["delivery"]["decoded_contact_sheet_filename"]
    sheet.save(sheet_path, format="PNG", optimize=True)
    return {
        "decoded_frame_count": len(decoded),
        "worst_full_frame_psnr_db": min(full_psnr),
        "worst_face_psnr_db": min(face_psnr),
        "worst_face_ssim": min(face_ssim),
        "worst_eye_psnr_db": min(eye_psnr),
        "worst_mouth_psnr_db": min(mouth_psnr),
        "minimum_encoded_laplacian_variance": min(sharpness),
        "maximum_decoded_adjacent_face_8x8_mean_delta": max(temporal),
        "first_last_decoded_psnr_db": _psnr(decoded[0], decoded[-1]),
        "all_frames_evaluated": True,
        "decoded_contact_sheet": {"file": sheet_path.name, "sha256": _sha256(sheet_path)},
    }, decoded


def _decoded_gates(contract: dict[str, Any], metrics: dict[str, Any], probe: dict[str, Any]) -> list[dict[str, Any]]:
    gates = contract["decoded_gates"]
    video_streams = [stream for stream in probe["streams"] if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in probe["streams"] if stream.get("codec_type") == "audio"]
    stream = video_streams[0] if len(video_streams) == 1 else {}
    checks = [
        ("one_video_stream", len(video_streams), "==", 1),
        ("no_audio_stream", len(audio_streams), "==", 0),
        ("codec_h264", stream.get("codec_name"), "==", "h264"),
        ("pixel_format_yuv420p", stream.get("pix_fmt"), "==", "yuv420p"),
        ("width", stream.get("width"), "==", 1920),
        ("height", stream.get("height"), "==", 1080),
        ("frame_count", int(stream.get("nb_frames", 0)), "==", 60),
        ("full_decode", metrics["decoded_frame_count"], "==", 60),
        ("all_frame_full_psnr", metrics["worst_full_frame_psnr_db"], ">=", gates["minimum_full_frame_psnr_db_all_frames"]),
        ("all_frame_face_psnr", metrics["worst_face_psnr_db"], ">=", gates["minimum_face_psnr_db_all_frames"]),
        ("all_frame_face_ssim", metrics["worst_face_ssim"], ">=", gates["minimum_face_ssim_all_frames"]),
        ("all_frame_eye_psnr", metrics["worst_eye_psnr_db"], ">=", gates["minimum_eye_psnr_db_all_frames"]),
        ("all_frame_mouth_psnr", metrics["worst_mouth_psnr_db"], ">=", gates["minimum_mouth_psnr_db_all_frames"]),
        ("all_frame_sharpness", metrics["minimum_encoded_laplacian_variance"], ">=", gates["minimum_encoded_laplacian_variance_all_frames"]),
        ("decoded_local_temporal_pop", metrics["maximum_decoded_adjacent_face_8x8_mean_delta"], "<=", gates["maximum_decoded_adjacent_face_8x8_mean_delta"]),
    ]
    results = []
    for name, actual, operator, threshold in checks:
        passed = actual == threshold if operator == "==" else actual >= threshold if operator == ">=" else actual <= threshold
        results.append({"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(passed)})
    return results


def render_semantic_proof(
    contract_path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
    *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    prepared = prepare_semantic_face(contract_path)
    output = _delivery_output_path(prepared.contract)
    rejected = output.with_name(output.name + "-rejected-attempt-v3")
    if output.exists() or rejected.exists():
        raise SemanticFaceError(f"immutable v3 attempt path already exists: {output if output.exists() else rejected}")
    manifest, review, manifest_path = _verify_preview_review(prepared)
    expected_hashes = [entry["rgb_sha256"] for entry in manifest["frames"]]
    for frame_number, expected_hash in enumerate(expected_hashes, start=1):
        actual = _raw_frame_hash(np.asarray(compose_semantic_frame(prepared, frame_number), dtype=np.uint8))
        if actual != expected_hash:
            raise SemanticFaceError(f"frame {frame_number} changed after preview review")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    encode_count = 0
    try:
        delivery = prepared.contract["delivery"]
        video = stage / delivery["video_filename"]
        partial = stage / (video.stem + ".partial.mp4")
        encoding = delivery["encoding"]
        command = [
            ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s:v", "1920x1080", "-r", "30", "-i", "-", "-an",
            "-c:v", encoding["implementation"], "-preset", encoding["preset"],
            "-crf", str(encoding["crf"]), "-pix_fmt", encoding["pixel_format"],
            "-frames:v", "60", "-movflags", "+faststart", str(partial),
        ]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        encode_count += 1
        assert process.stdin is not None
        try:
            for frame_number in range(1, 61):
                frame = np.asarray(compose_semantic_frame(prepared, frame_number), dtype=np.uint8)
                process.stdin.write(np.ascontiguousarray(frame).tobytes())
            process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr is not None else ""
            return_code = process.wait()
        except Exception:
            process.kill()
            process.wait()
            raise
        if return_code != 0:
            raise SemanticFaceError(f"single ffmpeg encode failed: {stderr.strip()}")
        os.replace(partial, video)
        probe = _probe_video(video, ffprobe)
        decoded_metrics, _ = _decode_and_measure(prepared, video, stage)
        preflight_gates = _preflight_gates(prepared.contract, prepared.preflight_measurements)
        decoded_gates = _decoded_gates(prepared.contract, decoded_metrics, probe)
        all_gates = preflight_gates + decoded_gates
        machine_passed = all(gate["passed"] for gate in all_gates)
        report = {
            "report_version": 1,
            "status": "machine_semantic_and_delivery_gates_passed_human_visual_review_required" if machine_passed else "machine_gates_failed",
            "machine_passed": machine_passed,
            "accepted_production_delivery": False,
            "human_full_size_review_required": True,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": _sha256(prepared.contract_path),
                "canonical_sha256": _canonical_hash(prepared.contract),
            },
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH)},
            "preview_manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
            "preview_review": {"path": prepared.contract["preview"]["review_receipt"], "sha256": _sha256(_resolve_repo_path(prepared.contract["preview"]["review_receipt"]))},
            "video": {"file": video.name, "sha256": _sha256(video), "bytes": video.stat().st_size, "encoding_process_count": encode_count},
            "probe": probe,
            "preflight_measurements": prepared.preflight_measurements,
            "decoded_measurements": decoded_metrics,
            "gates": all_gates,
            "gate_count": len(all_gates),
            "gates_passed": sum(1 for gate in all_gates if gate["passed"]),
            "gates_failed": sum(1 for gate in all_gates if not gate["passed"]),
            "cash_cost": 0,
            "paid_runtime_dependency": False,
            "reinforcement_learning_used": False,
            "voiced_reencode_allowed": False,
        }
        report_path = stage / delivery["report_filename"]
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not machine_passed:
            os.replace(stage, rejected)
            raise SemanticFaceError(f"encoded v3 attempt failed gates and was preserved at {rejected}")
        os.replace(stage, output)
        return {
            "output_directory": str(output),
            "video": str(output / video.name),
            "video_sha256": _sha256(output / video.name),
            "report": str(output / report_path.name),
            "report_sha256": _sha256(output / report_path.name),
            "machine_passed": True,
            "human_review_required": True,
        }
    except Exception:
        if stage.exists():
            if encode_count:
                os.replace(stage, rejected)
            else:
                shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build June's Phase33 v3 semantic facial proof")
    parser.add_argument("--contract", default=str(REPO_ROOT / CONTRACT_RELATIVE_PATH))
    parser.add_argument("--write-preview", action="store_true")
    parser.add_argument("--encode", action="store_true")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.write_preview == args.encode:
        raise SystemExit("choose exactly one of --write-preview or --encode")
    if args.write_preview:
        result = write_unencoded_preview(args.contract)
    else:
        result = render_semantic_proof(args.contract, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
