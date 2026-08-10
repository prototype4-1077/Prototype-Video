from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import shutil
import tempfile
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, __version__ as PILLOW_VERSION

import pipeline.cartoon_semantic_face as phase33


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase34_source_textured_visemes_v1.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_source_textured_face.py"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "894f453758ad3b685487140702d90846068b8907803d90fc7e96c5a11d850b1d"
ORAL_OUTER_RING_EXCLUSION_PX = 24.0
ORAL_OUTER_RING_SAFETY_GAP_PX = 4.0
ORAL_OUTER_RING_COLOR_RULE = "red_dominant_lip_material_within_outer_distance_v1"
ORAL_BLEND_GAMMA = 1.0
ORAL_ACTIVATION_METHOD = "semantic_non_neutral_weight_v1"
UPPER_DENTITION_CANONICAL_CELL = "E"
UPPER_DENTITION_TARGET_WIDTH_PX = 88.0
UPPER_DENTITION_TARGET_HEIGHT_PX = 16.0


class SourceTexturedFaceError(RuntimeError):
    pass


@dataclass(frozen=True)
class OralCell:
    rgba: np.ndarray
    excluded_outer_ring: np.ndarray
    upper_dentition_rgba: np.ndarray
    upper_dentition_forbidden_source_pixels: int


@dataclass
class PreparedSourceTexturedFace:
    contract: dict[str, Any]
    contract_path: Path
    phase33_base: phase33.PreparedSemanticFace
    source_points: np.ndarray
    triangles: np.ndarray
    feature_support: np.ndarray
    oral_cells: dict[str, OralCell]
    moustache_alpha: np.ndarray
    beard_alpha: np.ndarray
    preflight_measurements: dict[str, Any]
    preflight_native_frames: dict[int, np.ndarray]

    @property
    def plate(self) -> np.ndarray:
        return self.phase33_base.plate


@dataclass
class FrameEvidence:
    pose_weights: dict[str, float]
    oral_activation: float
    blink_closure: float
    iris_occlusion_ratios: list[float]
    lid_areas: list[int]
    cavity_area: int
    upper_teeth_area: int
    upper_dentition_centroid_y: float
    lower_teeth_area: int
    tongue_area: int
    warped_source_pixels: int
    source_texture_variance: float
    source_lip_ribbon_pixels: int
    moustache_front_overlap: int
    beard_front_overlap: int
    connected_source_seam_coverage_ratio: float
    oral_pixels_outside_cavity: int
    generated_atlas_outer_ring_pixels: int
    upper_dentition_forbidden_source_pixels: int
    changed_pixels: int
    changed_outside_support: int
    folded_triangles: int
    minimum_triangle_area_ratio: float
    maximum_triangle_area_ratio: float
    maximum_triangle_condition_number: float
    final_owner_counts: dict[str, int]
    depth_order_violation_pixels: int


OWNER_NAMES = {
    0: "authored_plate",
    1: "source_textured_face",
    2: "mouth_cavity",
    3: "gum_shadow",
    4: "tongue",
    5: "lower_dentition",
    6: "upper_dentition",
    7: "source_textured_lip_edge",
    8: "moustache",
    9: "beard",
    10: "upper_lids",
    11: "lower_lids",
    12: "lid_crease",
}

POSE_FIELDS = (
    "width", "opening", "round", "jaw_drop", "upper_roll", "lower_roll",
    "upper_teeth", "lower_teeth", "tongue", "corner_l", "corner_r",
    "cheek_l", "cheek_r", "beard_follow",
)

LAYER_BITS = {
    "source_warp": 1,
    "cavity": 2,
    "oral_interior": 4,
    "source_lip_edge": 8,
    "moustache": 16,
    "beard": 32,
    "eyelids": 64,
}
LOWER_FACE_LAYER_MASK = sum(value for name, value in LAYER_BITS.items() if name != "eyelids")


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _raw_frame_hash(frame: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()


def _write_lossless_frame_archive(frames: list[Image.Image], path: str | Path) -> dict[str, Any]:
    if not frames:
        raise SourceTexturedFaceError("lossless review archive requires at least one frame")
    first = np.asarray(frames[0].convert("RGB"), dtype=np.uint8)
    height, width = first.shape[:2]
    header = {
        "format": "phase34_rgb24_xor_previous_gzip_v1",
        "width": width,
        "height": height,
        "channels": 3,
        "frame_count": len(frames),
        "frame_bytes": int(first.size),
        "xor_seed": "all_zero_rgb24_frame",
    }
    previous = np.zeros_like(first)
    with Path(path).open("wb") as raw_handle:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw_handle, mtime=0) as archive:
            archive.write(
                json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            )
            for index, image in enumerate(frames, start=1):
                frame = np.asarray(image.convert("RGB"), dtype=np.uint8)
                if frame.shape != first.shape:
                    raise SourceTexturedFaceError(
                        f"lossless review frame {index} shape changed: {frame.shape} != {first.shape}"
                    )
                archive.write(np.bitwise_xor(frame, previous).tobytes(order="C"))
                previous = frame
    return header


def _read_lossless_frame_archive(path: str | Path) -> tuple[dict[str, Any], list[np.ndarray]]:
    with gzip.open(path, "rb") as archive:
        header = json.loads(archive.readline().decode("utf-8"))
        if header.get("format") != "phase34_rgb24_xor_previous_gzip_v1":
            raise SourceTexturedFaceError(f"unsupported lossless archive format: {header.get('format')}")
        shape = (int(header["height"]), int(header["width"]), int(header["channels"]))
        frame_bytes = int(np.prod(shape))
        if frame_bytes != int(header["frame_bytes"]):
            raise SourceTexturedFaceError("lossless archive frame byte count is inconsistent")
        previous = np.zeros(shape, dtype=np.uint8)
        frames: list[np.ndarray] = []
        for frame_number in range(1, int(header["frame_count"]) + 1):
            payload = archive.read(frame_bytes)
            if len(payload) != frame_bytes:
                raise SourceTexturedFaceError(f"lossless archive frame {frame_number} is truncated")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous)
            frames.append(frame.copy())
            previous = frame
        if archive.read(1):
            raise SourceTexturedFaceError("lossless archive has trailing payload")
    return header, frames


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_lf_normalized_text(path: str | Path) -> str:
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _locked_source_hash(reference: dict[str, Any]) -> str:
    path = _resolve_repo_path(reference["path"])
    domain = reference.get("hash_domain", "raw_bytes")
    if domain == "raw_bytes":
        return _sha256(path)
    if domain == "lf_normalized_text":
        return _sha256_lf_normalized_text(path)
    raise SourceTexturedFaceError(f"unsupported locked-source hash domain: {domain}")


def _resolve_repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SourceTexturedFaceError(f"locked path escapes repository: {relative}") from exc
    return path


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SourceTexturedFaceError(f"complete Phase34 v1 contract required: {label}: {actual!r} != {expected!r}")


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_equal(
        _canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256,
        "complete canonical contract SHA-256",
    )
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase34_source_textured_visemes_v1", "contract id")
    _require_equal(contract["view_id"], "CLOSE_HERO_FRONT_GS070", "view")
    representation = contract["representation"]
    _require_equal(representation["method"], "source_textured_piecewise_affine_semantic_face_v1", "method")
    for name in (
        "source_plate_is_only_identity_texture", "piecewise_affine_texture_deformation",
        "single_final_output_resample", "neutral_bypass_is_exact_source_plate",
        "registered_authored_oral_interior_atlas_allowed",
    ):
        _require_equal(representation[name], True, name)
    for name in (
        "complete_eye_mouth_or_face_photo_crossfades_allowed", "foreign_atlas_identity_pixels_allowed",
        "procedural_lip_color_slabs_allowed", "head_motion_allowed", "camera_motion_allowed",
        "body_motion_allowed", "atmosphere_motion_allowed", "audio_allowed",
        "generated_lip_pixels_allowed_in_final_composite", "runtime_ai_generation_allowed",
    ):
        _require_equal(representation[name], False, name)
    _require_equal(representation["paired_canonical_lid_pixels_allowed"], True, "paired lids")
    _require_equal(representation["procedural_recessed_oral_anatomy_allowed"], True, "oral anatomy")
    _require_equal(
        representation["oral_interior_atlas_outer_ring_exclusion_px"],
        ORAL_OUTER_RING_EXCLUSION_PX, "atlas outer-ring exclusion",
    )
    _require_equal(
        representation["oral_interior_atlas_outer_ring_safety_gap_px"],
        ORAL_OUTER_RING_SAFETY_GAP_PX, "atlas outer-ring safety gap",
    )
    _require_equal(
        representation["oral_interior_atlas_outer_ring_color_rule"],
        ORAL_OUTER_RING_COLOR_RULE, "atlas outer-ring color rule",
    )
    _require_equal(
        representation["oral_interior_interpolation"],
        "registered_pose_blend_linear_semantic_layers_v1", "oral interpolation",
    )
    _require_equal(representation["oral_interior_blend_gamma"], ORAL_BLEND_GAMMA, "oral blend gamma")
    _require_equal(
        representation["oral_activation_method"],
        ORAL_ACTIVATION_METHOD, "oral activation method",
    )
    _require_equal(
        representation["upper_dentition_transform"],
        "independent_skull_anchored_affine_v1", "upper dentition transform",
    )
    _require_equal(
        representation["upper_dentition_canonical_cell"],
        UPPER_DENTITION_CANONICAL_CELL, "upper dentition canonical cell",
    )
    _require_equal(
        representation["upper_dentition_target_width_px"],
        UPPER_DENTITION_TARGET_WIDTH_PX, "upper dentition target width",
    )
    _require_equal(
        representation["upper_dentition_target_height_px"],
        UPPER_DENTITION_TARGET_HEIGHT_PX, "upper dentition target height",
    )
    _require_equal(contract["clock"], {
        "source_width": 1672, "source_height": 941, "output_width": 1920, "output_height": 1080,
        "fps": 24, "frame_count": 96, "duration_seconds": 4.0,
    }, "clock")
    _require_equal(contract["performance"]["required_pose_order"], list("XABCDEFGHX"), "pose order")
    _require_equal(sorted(contract["pose_geometry_native_px"]), list("ABCDEFGHX"), "pose inventory")
    for pose in contract["pose_geometry_native_px"].values():
        _require_equal(sorted(pose), sorted(POSE_FIELDS), "pose fields")
    failure = contract["failure_policy"]
    _require_equal(failure["mode"], "fail_closed", "failure mode")
    _require_equal(failure["automatic_reencode_allowed"], False, "automatic reencode")
    _require_equal(failure["caller_selected_output_directory_allowed"], False, "caller output")
    _require_equal(contract["delivery"]["one_video_encode_without_retry"], True, "one encode")
    _require_equal(contract["promotion_policy"]["reinforcement_learning_allowed"], False, "RL")
    for name, reference in contract["locks"].items():
        path = _resolve_repo_path(reference["path"])
        if not path.is_file():
            raise SourceTexturedFaceError(f"missing locked source {name}: {path}")
        actual = _locked_source_hash(reference)
        if actual != reference["sha256"]:
            raise SourceTexturedFaceError(f"{name} SHA-256 mismatch: {actual} != {reference['sha256']}")


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    expected = (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve()
    if resolved != expected:
        raise SourceTexturedFaceError(f"Phase34 contract path is pinned: {resolved} != {expected}")
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    _validate_contract(payload)
    return payload


def _center_rgba_on_alpha_centroid(rgba: np.ndarray) -> np.ndarray:
    alpha = rgba[:, :, 3].astype(np.float64)
    total = float(alpha.sum())
    if total <= 0.0:
        return np.zeros((1, 1, 4), dtype=np.uint8)
    yy, xx = np.indices(alpha.shape, dtype=np.float64)
    centroid_x = float((xx * alpha).sum() / total)
    centroid_y = float((yy * alpha).sum() / total)
    half_width = int(math.ceil(max(centroid_x, rgba.shape[1] - 1 - centroid_x))) + 2
    half_height = int(math.ceil(max(centroid_y, rgba.shape[0] - 1 - centroid_y))) + 2
    centered = np.zeros((2 * half_height + 1, 2 * half_width + 1, 4), dtype=np.uint8)
    offset_x = int(round(half_width - centroid_x))
    offset_y = int(round(half_height - centroid_y))
    centered[offset_y:offset_y + rgba.shape[0], offset_x:offset_x + rgba.shape[1]] = rgba
    return centered


def _load_oral_cells(path: str | Path) -> dict[str, OralCell]:
    atlas = np.asarray(Image.open(path).convert("RGBA"), dtype=np.uint8)
    if atlas.shape != (1254, 1254, 4):
        raise SourceTexturedFaceError(f"oral atlas dimensions changed: {atlas.shape}")
    cell_size = 418
    cells: dict[str, OralCell] = {}
    for index, name in enumerate("XABCDEFGH"):
        row, column = divmod(index, 3)
        cell = atlas[row * cell_size:(row + 1) * cell_size, column * cell_size:(column + 1) * cell_size].copy()
        visible = cell[:, :, 3] > 8
        yy, xx = np.where(visible)
        if not yy.size:
            raise SourceTexturedFaceError(f"oral atlas cell {name} is empty")
        pad = 4
        if int(yy.min()) < pad or int(xx.min()) < pad or int(yy.max()) >= cell_size - pad or int(xx.max()) >= cell_size - pad:
            raise SourceTexturedFaceError(f"oral atlas cell {name} lacks {pad}px transparent registration padding")
        hard = cell[:, :, 3] >= 128
        if hard[0].any() or hard[-1].any() or hard[:, 0].any() or hard[:, -1].any():
            raise SourceTexturedFaceError(f"oral atlas cell {name} touches its registration boundary")
        y1, y2 = max(0, int(yy.min()) - pad), min(cell_size, int(yy.max()) + pad + 1)
        x1, x2 = max(0, int(xx.min()) - pad), min(cell_size, int(xx.max()) + pad + 1)
        crop = cell[y1:y2, x1:x2].copy()
        original_alpha = crop[:, :, 3].copy()
        opaque = (crop[:, :, 3] > 8).astype(np.uint8)
        distance = cv2.distanceTransform(opaque, cv2.DIST_L2, 5)
        red = crop[:, :, 0].astype(np.float32)
        green = crop[:, :, 1].astype(np.float32)
        blue = crop[:, :, 2].astype(np.float32)
        dental_material = (
            (red > 145.0)
            & (green > 105.0)
            & (blue > 70.0)
            & (red < green * 1.55)
        )
        lip_material = (
            (red >= 85.0)
            & (red > green * 1.28)
            & (red > blue * 1.08)
            & ~dental_material
        )
        excluded_bool = (opaque > 0) & (distance <= ORAL_OUTER_RING_EXCLUSION_PX) & lip_material
        excluded = excluded_bool.astype(np.uint8) * 255
        gap_radius = int(round(ORAL_OUTER_RING_SAFETY_GAP_PX))
        gap_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gap_radius + 1, 2 * gap_radius + 1))
        excluded_with_gap = cv2.dilate(excluded, gap_kernel) > 0
        upper_half = np.indices(opaque.shape)[0] < opaque.shape[0] * 0.55
        upper_dentition_core = (opaque > 0) & dental_material & upper_half
        upper_dentition_mask = cv2.dilate(
            upper_dentition_core.astype(np.uint8) * 255,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        upper_dentition_mask = cv2.GaussianBlur(upper_dentition_mask, (0, 0), 0.55)
        upper_dentition_mask[excluded_with_gap] = 0
        upper_dentition = crop.copy()
        upper_dentition[:, :, 3] = np.clip(
            original_alpha.astype(np.float32) * (upper_dentition_mask.astype(np.float32) / 255.0),
            0, 255,
        ).astype(np.uint8)
        upper_forbidden = int(((upper_dentition[:, :, 3] > 8) & excluded_bool).sum())
        if upper_forbidden:
            raise SourceTexturedFaceError(
                f"oral atlas cell {name} upper dentition retains {upper_forbidden} forbidden outer-ring pixels"
            )
        upper_visible = upper_dentition[:, :, 3] > 8
        upper_yy, upper_xx = np.where(upper_visible)
        if upper_yy.size:
            uy1, uy2 = max(0, int(upper_yy.min()) - 2), min(crop.shape[0], int(upper_yy.max()) + 3)
            ux1, ux2 = max(0, int(upper_xx.min()) - 2), min(crop.shape[1], int(upper_xx.max()) + 3)
            upper_dentition = upper_dentition[uy1:uy2, ux1:ux2].copy()
            upper_dentition = _center_rgba_on_alpha_centroid(upper_dentition)
        else:
            upper_dentition = np.zeros((1, 1, 4), dtype=np.uint8)
        retained = ((opaque > 0) & (~excluded_with_gap | dental_material)).astype(np.uint8)
        retained_distance = cv2.distanceTransform(retained, cv2.DIST_L2, 5)
        inner = np.clip(retained_distance / 5.0, 0.0, 1.0)
        remove_upper_dentition = 1.0 - upper_dentition_mask.astype(np.float32) / 255.0
        crop[:, :, 3] = np.clip(
            original_alpha.astype(np.float32) * inner * remove_upper_dentition,
            0, 255,
        ).astype(np.uint8)
        if name == "X":
            crop[:, :, 3] = 0
            upper_dentition[:, :, 3] = 0
        cells[name] = OralCell(
            rgba=crop,
            excluded_outer_ring=excluded,
            upper_dentition_rgba=upper_dentition,
            upper_dentition_forbidden_source_pixels=upper_forbidden,
        )
    return cells


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _oral_activation(pose: dict[str, float], pose_weights: dict[str, float]) -> float:
    del pose
    return float(np.clip(1.0 - float(pose_weights.get("X", 0.0)), 0.0, 1.0))


def blink_closure(contract: dict[str, Any], frame_number: int) -> float:
    start, end = [int(value) for value in contract["performance"]["blink_frames"]]
    peak_start, peak_end = [int(value) for value in contract["performance"]["blink_max_frames"]]
    if frame_number < start or frame_number > end:
        return 0.0
    if frame_number <= peak_start:
        return _ease((frame_number - start) / max(peak_start - start, 1))
    if frame_number <= peak_end:
        return 1.0
    return _ease((end - frame_number) / max(end - peak_end, 1))


def _pose_vector(contract: dict[str, Any], pose: str) -> np.ndarray:
    values = contract["pose_geometry_native_px"][pose]
    return np.asarray([values[name] for name in POSE_FIELDS], dtype=np.float32)


def mouth_controls(contract: dict[str, Any], frame_number: int) -> tuple[dict[str, float], dict[str, float]]:
    keys = [(int(item["frame"]), str(item["pose"])) for item in contract["performance"]["viseme_keyframes"]]
    if frame_number <= keys[0][0]:
        pose = keys[0][1]
        return dict(zip(POSE_FIELDS, _pose_vector(contract, pose))), {name: float(name == pose) for name in "ABCDEFGHX"}
    for (left_frame, left_pose), (right_frame, right_pose) in zip(keys, keys[1:]):
        if left_frame <= frame_number <= right_frame:
            if left_pose == right_pose:
                return dict(zip(POSE_FIELDS, _pose_vector(contract, left_pose))), {
                    name: float(name == left_pose) for name in "ABCDEFGHX"
                }
            amount = _ease((frame_number - left_frame) / float(right_frame - left_frame))
            values = (1.0 - amount) * _pose_vector(contract, left_pose) + amount * _pose_vector(contract, right_pose)
            weights = {name: 0.0 for name in "ABCDEFGHX"}
            weights[left_pose] = 1.0 - amount
            weights[right_pose] = amount
            return dict(zip(POSE_FIELDS, values)), weights
    return dict(zip(POSE_FIELDS, _pose_vector(contract, "X"))), {name: float(name == "X") for name in "ABCDEFGHX"}


def _cage(contract: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    geometry = contract["semantic_geometry_native_xy"]
    xs = geometry["cage_x"]
    ys = geometry["cage_y"]
    points = np.asarray([(x, y) for y in ys for x in xs], dtype=np.float32)
    columns = len(xs)
    rows = len(ys)
    triangles: list[tuple[int, int, int]] = []
    for row in range(rows - 1):
        for column in range(columns - 1):
            tl = row * columns + column
            tr = tl + 1
            bl = (row + 1) * columns + column
            br = bl + 1
            if (row + column) % 2 == 0:
                triangles.extend(((tl, tr, br), (tl, br, bl)))
            else:
                triangles.extend(((tl, tr, bl), (tr, br, bl)))
    return points, np.asarray(triangles, dtype=np.int32)


def _destination_points(
    contract: dict[str, Any], source: np.ndarray, pose: dict[str, float],
) -> np.ndarray:
    if pose["opening"] <= 1e-6 and pose["width"] <= 1e-6:
        return source.copy()
    geometry = contract["semantic_geometry_native_xy"]
    cx, cy = [float(value) for value in geometry["mouth_center"]]
    neutral_half_width = float(geometry["neutral_mouth_half_width"])
    x_min, y_min, x_max, y_max = geometry["deformation_roi"]
    destination = source.copy()
    target_lip_half_width = 0.5 * float(pose["width"]) + 10.0 + 5.0 * float(pose["round"])
    lip_scale = target_lip_half_width / neutral_half_width
    opening = float(pose["opening"])
    jaw_drop = float(pose["jaw_drop"])
    for index, (x, y) in enumerate(source):
        if x in (x_min, x_max) or y in (y_min, y_max):
            continue
        dx = float(x - cx)
        dy = float(y - cy)
        horizontal_field = math.exp(-((dy / 58.0) ** 2)) * math.exp(-((abs(dx) / 125.0) ** 4))
        center_field = math.exp(-((dx / 115.0) ** 4))
        mouth_field = math.exp(-((dy / 72.0) ** 2)) * center_field
        lower_field = max(0.0, min(1.0, (y - 374.0) / 92.0)) * center_field
        side = "l" if dx < 0.0 else "r"
        cheek = float(pose[f"cheek_{side}"])
        corner = float(pose[f"corner_{side}"])
        side_field = math.exp(-(((abs(dx) - 74.0) / 42.0) ** 2 + ((dy + 10.0) / 56.0) ** 2))
        destination[index, 0] = cx + dx * (1.0 + (lip_scale - 1.0) * horizontal_field * 0.55)
        vertical_open = max(0.0, opening - 3.0)
        separation_factor = math.tanh(dy / 20.0)
        separation_scale = 0.22 if separation_factor < 0.0 else 0.25
        separation = separation_scale * vertical_open * separation_factor * mouth_field
        if y > cy:
            separation += 0.45 * jaw_drop * lower_field
        separation += -4.2 * cheek * side_field + 4.5 * corner * side_field
        separation += float(pose["beard_follow"]) * jaw_drop * 0.28 * lower_field
        destination[index, 1] = y + separation
    return destination


def _signed_area(triangle: np.ndarray) -> float:
    a, b, c = triangle
    first = b - a
    second = c - a
    return 0.5 * float(first[0] * second[1] - first[1] * second[0])


def _triangle_metrics(source: np.ndarray, destination: np.ndarray, triangles: np.ndarray) -> dict[str, float | int]:
    ratios: list[float] = []
    conditions: list[float] = []
    folded = 0
    for indices in triangles:
        src = source[indices]
        dst = destination[indices]
        source_area = _signed_area(src)
        destination_area = _signed_area(dst)
        if source_area * destination_area <= 0.0:
            folded += 1
        ratios.append(abs(destination_area) / max(abs(source_area), 1e-9))
        source_basis = np.stack((src[1] - src[0], src[2] - src[0]), axis=1)
        destination_basis = np.stack((dst[1] - dst[0], dst[2] - dst[0]), axis=1)
        affine = destination_basis @ np.linalg.inv(source_basis)
        singular = np.linalg.svd(affine, compute_uv=False)
        conditions.append(float(singular.max() / max(singular.min(), 1e-9)))
    return {
        "folded_triangles": folded,
        "minimum_triangle_area_ratio": min(ratios),
        "maximum_triangle_area_ratio": max(ratios),
        "maximum_triangle_condition_number": max(conditions),
    }


def _dense_inverse_maps(
    shape: tuple[int, int], source: np.ndarray, destination: np.ndarray, triangles: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    height, width = shape
    x0 = max(0, int(math.floor(float(destination[:, 0].min()))) - 2)
    y0 = max(0, int(math.floor(float(destination[:, 1].min()))) - 2)
    x1 = min(width, int(math.ceil(float(destination[:, 0].max()))) + 3)
    y1 = min(height, int(math.ceil(float(destination[:, 1].max()))) + 3)
    local_y, local_x = np.indices((y1 - y0, x1 - x0), dtype=np.float32)
    map_x = local_x + x0
    map_y = local_y + y0
    support = np.zeros((y1 - y0, x1 - x0), dtype=np.uint8)
    for indices in triangles:
        src = source[indices].astype(np.float32)
        dst = destination[indices].astype(np.float32)
        x, y, w, h = cv2.boundingRect(dst)
        tx0, ty0 = max(x0, x), max(y0, y)
        tx1, ty1 = min(x1, x + w), min(y1, y + h)
        if tx1 <= tx0 or ty1 <= ty0:
            continue
        local = np.zeros((ty1 - ty0, tx1 - tx0), dtype=np.uint8)
        polygon = np.round(dst - np.asarray([tx0, ty0], dtype=np.float32)).astype(np.int32)
        cv2.fillConvexPoly(local, polygon, 255, lineType=cv2.LINE_8)
        matrix = cv2.getAffineTransform(dst, src)
        triangle_y, triangle_x = np.indices(local.shape, dtype=np.float32)
        global_x = triangle_x + tx0
        global_y = triangle_y + ty0
        source_x = matrix[0, 0] * global_x + matrix[0, 1] * global_y + matrix[0, 2]
        source_y = matrix[1, 0] * global_x + matrix[1, 1] * global_y + matrix[1, 2]
        inside = local > 0
        rx0, ry0 = tx0 - x0, ty0 - y0
        rx1, ry1 = tx1 - x0, ty1 - y0
        map_x[ry0:ry1, rx0:rx1][inside] = source_x[inside]
        map_y[ry0:ry1, rx0:rx1][inside] = source_y[inside]
        support[ry0:ry1, rx0:rx1][inside] = 255
    return map_x, map_y, support, (x0, y0, x1, y1)


def _blend(canvas: np.ndarray, color: np.ndarray, alpha: np.ndarray) -> None:
    amount = alpha.astype(np.float32)[:, :, None] / 255.0
    canvas[:] = np.clip(canvas.astype(np.float32) * (1.0 - amount) + color.astype(np.float32) * amount, 0, 255).astype(np.uint8)


def _soft(mask: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma, sigmaY=sigma)


def _mouth_mask(
    shape: tuple[int, int], center: tuple[float, float], pose: dict[str, float], angle_degrees: float,
) -> tuple[np.ndarray, np.ndarray]:
    mask = np.zeros(shape, dtype=np.uint8)
    contour: list[tuple[int, int]] = []
    cx, cy = center
    radius_x = max(1.0, 0.5 * float(pose["width"]))
    radius_y = max(1.0, 0.5 * float(pose["opening"]))
    roundness = float(pose["round"])
    exponent = 1.0 + 0.8 * (1.0 - roundness)
    angle = math.radians(angle_degrees)
    for index in range(96):
        theta = math.tau * index / 96.0
        horizontal = math.cos(theta)
        vertical = math.sin(theta)
        x = radius_x * math.copysign(abs(horizontal) ** exponent, horizontal)
        y = radius_y * math.copysign(abs(vertical) ** (0.82 + 0.35 * roundness), vertical)
        corner = float(pose["corner_l"] if x < 0.0 else pose["corner_r"])
        y += 3.6 * corner * (abs(horizontal) ** 6)
        rotated_x = cx + math.cos(angle) * x - math.sin(angle) * y
        rotated_y = cy + math.sin(angle) * x + math.cos(angle) * y
        contour.append((int(round(rotated_x)), int(round(rotated_y))))
    polygon = np.asarray(contour, dtype=np.int32)
    cv2.fillPoly(mask, [polygon], 255, lineType=cv2.LINE_AA)
    return mask, polygon


def _oriented_coordinates(
    shape: tuple[int, int], center: tuple[float, float], angle_degrees: float,
) -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.indices(shape, dtype=np.float32)
    dx = xx - center[0]
    dy = yy - center[1]
    angle = math.radians(angle_degrees)
    return math.cos(angle) * dx + math.sin(angle) * dy, -math.sin(angle) * dx + math.cos(angle) * dy


def _legacy_procedural_oral_anatomy_for_rejected_01(
    canvas: np.ndarray,
    warped_source: np.ndarray,
    warped_moustache: np.ndarray,
    warped_beard: np.ndarray,
    owner: np.ndarray,
    center: tuple[float, float],
    pose: dict[str, float],
    angle_degrees: float,
) -> dict[str, int | float]:
    cavity, contour = _mouth_mask(canvas.shape[:2], center, pose, angle_degrees)
    cavity_hard = cavity > 128
    mouth_u, mouth_v = _oriented_coordinates(canvas.shape[:2], center, angle_degrees)
    width = float(pose["width"])
    opening = float(pose["opening"])

    yy, _ = np.indices(canvas.shape[:2], dtype=np.float32)
    vertical = np.clip((yy - (center[1] - opening * 0.55)) / max(opening * 1.25, 1.0), 0.0, 1.0)
    cavity_color = np.zeros_like(canvas)
    top = np.asarray([70, 24, 22], dtype=np.float32)
    bottom = np.asarray([24, 7, 12], dtype=np.float32)
    cavity_color[:] = np.clip(top[None, None, :] * (1.0 - vertical[:, :, None]) + bottom[None, None, :] * vertical[:, :, None], 0, 255)
    radial = np.clip(1.0 - np.sqrt((mouth_u / max(width * 0.5, 1.0)) ** 2 + (mouth_v / max(opening * 0.55, 1.0)) ** 2), 0.0, 1.0)
    cavity_color = np.clip(cavity_color.astype(np.float32) + radial[:, :, None] * np.asarray([7.0, 2.0, 1.0]), 0, 255).astype(np.uint8)
    _blend(canvas, cavity_color, _soft(cavity, 0.65))
    owner[cavity_hard] = 2

    gum_shadow = (
        cavity_hard
        & (mouth_v >= -opening * 0.50)
        & (mouth_v <= -opening * 0.31)
        & (np.abs(mouth_u) <= width * 0.38)
    )
    gum_color = np.zeros_like(canvas)
    gum_color[:] = np.asarray([121, 49, 45], dtype=np.uint8)
    _blend(canvas, gum_color, _soft(gum_shadow.astype(np.uint8) * 255, 0.55))
    owner[gum_shadow] = 3

    tongue = np.zeros(canvas.shape[:2], dtype=np.uint8)
    if float(pose["tongue"]) > 0.03:
        tongue_center = (int(round(center[0])), int(round(center[1] + opening * 0.29)))
        tongue_axes = (
            max(2, int(round(width * (0.22 + 0.06 * float(pose["tongue"]))))),
            max(2, int(round(opening * (0.12 + 0.11 * float(pose["tongue"]))))),
        )
        cv2.ellipse(
            tongue, tongue_center, tongue_axes,
            angle_degrees, 0, 360, 255, -1, lineType=cv2.LINE_AA,
        )
        tongue = cv2.bitwise_and(tongue, cavity)
        tongue_color = np.zeros_like(canvas)
        tongue_color[:] = np.asarray([148, 64, 65], dtype=np.uint8)
        highlight = np.clip(1.0 - np.abs(mouth_u) / max(width * 0.25, 1.0), 0.0, 1.0)
        tongue_color = np.clip(tongue_color.astype(np.float32) + highlight[:, :, None] * np.asarray([16.0, 6.0, 5.0]), 0, 255).astype(np.uint8)
        _blend(canvas, tongue_color, _soft(tongue, 0.55))
        owner[tongue > 128] = 4

    lower_teeth = np.zeros(canvas.shape[:2], dtype=np.uint8)
    if float(pose["lower_teeth"]) > 0.03:
        lower_height = max(1.0, 7.5 * float(pose["lower_teeth"]))
        lower_teeth = (
            cavity_hard
            & (mouth_v >= opening * 0.24 - lower_height)
            & (mouth_v <= opening * 0.24 + 1.0)
            & (np.abs(mouth_u) <= width * 0.34)
        ).astype(np.uint8) * 255
        lower_color = np.zeros_like(canvas)
        lower_color[:] = np.asarray([207, 187, 151], dtype=np.uint8)
        _blend(canvas, lower_color, _soft(lower_teeth, 0.4))
        owner[lower_teeth > 128] = 5

    upper_teeth = np.zeros(canvas.shape[:2], dtype=np.uint8)
    if float(pose["upper_teeth"]) > 0.03:
        exposure = max(2.0, 12.0 * float(pose["upper_teeth"]))
        arch = 2.5 * (1.0 - np.clip((mouth_u / max(width * 0.42, 1.0)) ** 2, 0.0, 1.0))
        top_edge = -opening * 0.49 + 2.0
        upper_teeth_bool = (
            cavity_hard
            & (mouth_v >= top_edge)
            & (mouth_v <= top_edge + exposure + arch)
            & (np.abs(mouth_u) <= width * 0.39)
        )
        upper_teeth = upper_teeth_bool.astype(np.uint8) * 255
        base_luma = 223.0 + 10.0 * np.clip(1.0 - np.abs(mouth_u) / max(width * 0.4, 1.0), 0.0, 1.0)
        tooth_color = np.stack((base_luma, base_luma * 0.91, base_luma * 0.75), axis=2)
        tooth_color = np.clip(tooth_color, 0, 255).astype(np.uint8)
        _blend(canvas, tooth_color, _soft(upper_teeth, 0.38))
        owner[upper_teeth_bool] = 6
        tooth_pitch = max(8.0, width / 9.0)
        separators = (
            upper_teeth_bool
            & (np.mod(mouth_u + width * 0.5, tooth_pitch) < 0.62)
        ).astype(np.uint8) * 76
        separator_color = np.zeros_like(canvas)
        separator_color[:] = np.asarray([113, 82, 62], dtype=np.uint8)
        _blend(canvas, separator_color, separators)

    lip_edge = np.zeros(canvas.shape[:2], dtype=np.uint8)
    cv2.polylines(lip_edge, [contour], True, 150, 1, lineType=cv2.LINE_AA)
    edge_color = cv2.GaussianBlur(warped_source, (0, 0), 1.2).astype(np.float32) * np.asarray([0.72, 0.60, 0.58])
    _blend(canvas, np.clip(edge_color, 0, 255).astype(np.uint8), lip_edge)
    owner[lip_edge > 96] = 7

    perimeter = cv2.subtract(cv2.dilate(cavity, np.ones((13, 13), np.uint8)), cv2.erode(cavity, np.ones((5, 5), np.uint8)))
    top_half = mouth_v <= 3.0
    bottom_half = mouth_v >= -1.0
    moustache_front = (warped_moustache > 96) & (perimeter > 0) & top_half
    beard_front = (warped_beard > 96) & (perimeter > 0) & bottom_half
    moustache_alpha = _soft(moustache_front.astype(np.uint8) * 255, 0.45)
    beard_alpha = _soft(beard_front.astype(np.uint8) * 255, 0.45)
    _blend(canvas, warped_source, moustache_alpha)
    owner[moustache_front] = 8
    _blend(canvas, warped_source, beard_alpha)
    owner[beard_front] = 9

    oral_union = (tongue > 128) | (lower_teeth > 128) | (upper_teeth > 128) | gum_shadow
    texture_ring = cv2.subtract(cv2.dilate(cavity, np.ones((13, 13), np.uint8)), cavity) > 0
    texture_values = cv2.cvtColor(warped_source, cv2.COLOR_RGB2GRAY)[texture_ring]
    return {
        "cavity": int(cavity_hard.sum()),
        "upper_teeth": int((upper_teeth > 128).sum()),
        "lower_teeth": int((lower_teeth > 128).sum()),
        "tongue": int((tongue > 128).sum()),
        "moustache_overlap": int(moustache_front.sum()),
        "beard_overlap": int(beard_front.sum()),
        "oral_outside": int((oral_union & ~cavity_hard).sum()),
        "source_texture_variance": float(texture_values.var()) if texture_values.size else 0.0,
    }


def _oral_affine_matrix(
    source_shape: tuple[int, int],
    center: tuple[float, float],
    target_width: float,
    target_height: float,
    angle_degrees: float,
) -> np.ndarray:
    source_height, source_width = source_shape
    source_center_x = (source_width - 1) * 0.5
    source_center_y = (source_height - 1) * 0.5
    scale_x = max(2.0, target_width) / max(source_width, 1)
    scale_y = max(2.0, target_height) / max(source_height, 1)
    angle = math.radians(angle_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    return np.asarray([
        [cosine * scale_x, -sine * scale_y,
         center[0] - cosine * scale_x * source_center_x + sine * scale_y * source_center_y],
        [sine * scale_x, cosine * scale_y,
         center[1] - sine * scale_x * source_center_x - cosine * scale_y * source_center_y],
    ], dtype=np.float32)


def _warp_oral_cell(
    cell: OralCell,
    shape: tuple[int, int],
    center: tuple[float, float],
    target_width: float,
    target_height: float,
    angle_degrees: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    height, width = shape
    matrix = _oral_affine_matrix(
        cell.rgba.shape[:2], center, target_width, target_height, angle_degrees,
    )
    alpha = cell.rgba[:, :, 3].astype(np.float32) / 255.0
    premultiplied = cell.rgba[:, :, :3].astype(np.float32) * alpha[:, :, None]
    warped_alpha = cv2.warpAffine(
        alpha, matrix, (width, height), flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )
    warped_premultiplied = cv2.warpAffine(
        premultiplied, matrix, (width, height), flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )
    warped_excluded = cv2.warpAffine(
        cell.excluded_outer_ring.astype(np.float32) / 255.0,
        matrix, (width, height), flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )
    warped_alpha = np.clip(warped_alpha, 0.0, 1.0)
    warped_premultiplied = np.clip(warped_premultiplied, 0.0, 255.0)
    warped_premultiplied = np.minimum(warped_premultiplied, warped_alpha[:, :, None] * 255.0)
    warped_premultiplied[warped_alpha <= 1e-6] = 0.0
    return warped_premultiplied, warped_alpha, np.clip(warped_excluded, 0.0, 1.0)


def _record_layer(coverage: np.ndarray, mask: np.ndarray, layer_name: str) -> None:
    coverage[np.asarray(mask) > 8] |= np.uint16(LAYER_BITS[layer_name])


def _depth_order_violation_pixels(owner: np.ndarray, coverage: np.ndarray) -> int:
    violation = np.zeros(coverage.shape, dtype=bool)
    eyelids = (coverage & LAYER_BITS["eyelids"]) != 0
    lower_face = (coverage & LOWER_FACE_LAYER_MASK) != 0
    cavity = (coverage & LAYER_BITS["cavity"]) != 0
    oral = (coverage & LAYER_BITS["oral_interior"]) != 0
    lip = (coverage & LAYER_BITS["source_lip_edge"]) != 0
    moustache = (coverage & LAYER_BITS["moustache"]) != 0
    beard = (coverage & LAYER_BITS["beard"]) != 0
    warp = (coverage & LAYER_BITS["source_warp"]) != 0

    violation |= eyelids & lower_face
    violation |= oral & ~cavity
    violation |= eyelids & ~np.isin(owner, (10, 11, 12))
    violation |= beard & ~eyelids & (owner != 9)
    violation |= moustache & ~beard & ~eyelids & (owner != 8)
    violation |= lip & ~moustache & ~beard & ~eyelids & (owner != 7)
    violation |= oral & ~lip & ~moustache & ~beard & ~eyelids & ~np.isin(owner, (3, 4, 5, 6))
    violation |= cavity & ~oral & ~lip & ~moustache & ~beard & ~eyelids & (owner != 2)
    violation |= warp & ~cavity & ~oral & ~lip & ~moustache & ~beard & ~eyelids & (owner != 1)
    return int(violation.sum())


def _compose_authored_oral_anatomy(
    canvas: np.ndarray,
    warped_source: np.ndarray,
    warped_moustache: np.ndarray,
    warped_beard: np.ndarray,
    owner: np.ndarray,
    coverage: np.ndarray,
    oral_cells: dict[str, OralCell],
    center: tuple[float, float],
    upper_dentition_anchor: tuple[float, float],
    pose: dict[str, float],
    pose_weights: dict[str, float],
    oral_activation: float,
    angle_degrees: float,
) -> dict[str, int | float]:
    cavity, _ = _mouth_mask(canvas.shape[:2], center, pose, angle_degrees)
    cavity_hard = cavity > 128
    mouth_u, mouth_v = _oriented_coordinates(canvas.shape[:2], center, angle_degrees)
    width = float(pose["width"])
    opening = float(pose["opening"])

    shadow = np.zeros_like(canvas)
    radial = np.clip(1.0 - np.sqrt(
        (mouth_u / max(width * 0.5, 1.0)) ** 2
        + (mouth_v / max(opening * 0.55, 1.0)) ** 2
    ), 0.0, 1.0)
    shadow[:, :, 0] = np.clip(72.0 - 48.0 * radial, 0, 255).astype(np.uint8)
    shadow[:, :, 1] = np.clip(28.0 - 21.0 * radial, 0, 255).astype(np.uint8)
    shadow[:, :, 2] = np.clip(30.0 - 20.0 * radial, 0, 255).astype(np.uint8)
    cavity_alpha = np.clip(_soft(cavity, 0.8).astype(np.float32) * oral_activation, 0, 255).astype(np.uint8)
    _blend(canvas, shadow, cavity_alpha)
    active_cavity = cavity_hard & (oral_activation > 0.02)
    _record_layer(coverage, active_cavity.astype(np.uint8) * 255, "cavity")
    owner[active_cavity] = 2

    accumulated_premultiplied = np.zeros_like(canvas, dtype=np.float32)
    accumulated_alpha = np.zeros(canvas.shape[:2], dtype=np.float32)
    accumulated_excluded = np.zeros(canvas.shape[:2], dtype=np.float32)
    sharpened = {name: float(weight) ** ORAL_BLEND_GAMMA for name, weight in pose_weights.items()}
    normalizer = max(sum(sharpened.values()), 1e-9)
    sharpened = {name: weight / normalizer for name, weight in sharpened.items()}
    for name, weight in sharpened.items():
        if name == "X" or weight <= 1e-4:
            continue
        premultiplied, alpha, excluded = _warp_oral_cell(
            oral_cells[name], canvas.shape[:2], center,
            width * 0.98, opening * 0.96, angle_degrees,
        )
        accumulated_premultiplied += premultiplied * weight
        accumulated_alpha += alpha * weight
        accumulated_excluded += excluded * weight
    accumulated_alpha = np.clip(accumulated_alpha, 0.0, 1.0)
    exclusion_guard = cv2.dilate(
        (accumulated_excluded > 0.02).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ) > 0
    accumulated_alpha[exclusion_guard] = 0.0
    accumulated_premultiplied[exclusion_guard] = 0.0
    unmasked_alpha = accumulated_alpha.copy()
    inner_cavity = cv2.erode(cavity, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    clip_alpha = _soft(inner_cavity, 0.45).astype(np.float32) / 255.0
    accumulated_alpha *= clip_alpha * oral_activation
    oral_rgb = np.zeros_like(canvas)
    valid = unmasked_alpha > 1e-5
    oral_rgb[valid] = np.clip(
        accumulated_premultiplied[valid] / unmasked_alpha[valid][:, None], 0, 255,
    ).astype(np.uint8)
    oral_alpha_u8 = np.clip(accumulated_alpha * 255.0, 0, 255).astype(np.uint8)
    _blend(canvas, oral_rgb, oral_alpha_u8)
    generated_outer_ring = (
        (accumulated_excluded > 0.20)
        & (accumulated_alpha > 0.02)
        & (clip_alpha > 0.02)
    )

    canonical_dentition = oral_cells[UPPER_DENTITION_CANONICAL_CELL]
    upper_cell = OralCell(
        rgba=canonical_dentition.upper_dentition_rgba,
        excluded_outer_ring=np.zeros(canonical_dentition.upper_dentition_rgba.shape[:2], dtype=np.uint8),
        upper_dentition_rgba=np.zeros((1, 1, 4), dtype=np.uint8),
        upper_dentition_forbidden_source_pixels=canonical_dentition.upper_dentition_forbidden_source_pixels,
    )
    accumulated_upper_premultiplied, unmasked_upper_alpha, _ = _warp_oral_cell(
        upper_cell, canvas.shape[:2], upper_dentition_anchor,
        UPPER_DENTITION_TARGET_WIDTH_PX, UPPER_DENTITION_TARGET_HEIGHT_PX, angle_degrees,
    )
    dental_visibility = oral_activation * (0.45 + 0.55 * float(pose["upper_teeth"]))
    accumulated_upper_alpha = np.clip(unmasked_upper_alpha, 0.0, 1.0) * clip_alpha * dental_visibility
    upper_rgb = np.zeros_like(canvas)
    upper_valid = accumulated_upper_alpha > 1e-5
    upper_rgb[upper_valid] = np.clip(
        accumulated_upper_premultiplied[upper_valid]
        / np.maximum(unmasked_upper_alpha[upper_valid][:, None], 1e-5),
        0, 255,
    ).astype(np.uint8)
    upper_alpha_u8 = np.clip(accumulated_upper_alpha * 255.0, 0, 255).astype(np.uint8)
    _blend(canvas, upper_rgb, upper_alpha_u8)

    red = oral_rgb[:, :, 0].astype(np.float32)
    green = oral_rgb[:, :, 1].astype(np.float32)
    blue = oral_rgb[:, :, 2].astype(np.float32)
    visible = accumulated_alpha > 0.30
    teeth = visible & (red > 145.0) & (green > 105.0) & (blue > 70.0) & (red < green * 1.55)
    tongue = visible & (red > 105.0) & (green > 34.0) & (blue > 35.0) & (red > green * 1.50) & (mouth_v > -opening * 0.05)
    lower_teeth = teeth & (mouth_v >= 0.0)
    upper_teeth = accumulated_upper_alpha > 0.30
    oral_visible = visible | upper_teeth
    _record_layer(coverage, oral_visible.astype(np.uint8) * 255, "oral_interior")
    upper_y, _ = np.where(upper_teeth)
    upper_centroid_y = float(upper_y.mean()) if upper_y.size else 0.0
    owner[visible] = 3
    owner[tongue] = 4
    owner[lower_teeth] = 5
    owner[upper_teeth] = 6

    inner_edge = cv2.subtract(
        cavity,
        cv2.erode(cavity, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))),
    )
    source_feather_alpha = np.clip(
        _soft(inner_edge, 0.75).astype(np.float32) * (0.58 * oral_activation),
        0, 255,
    ).astype(np.uint8)
    graded_source_edge = np.clip(
        warped_source.astype(np.float32) * np.asarray([0.56, 0.43, 0.42], dtype=np.float32),
        0, 255,
    ).astype(np.uint8)
    _blend(canvas, graded_source_edge, source_feather_alpha)
    source_feather_front = source_feather_alpha > 24
    _record_layer(coverage, source_feather_front.astype(np.uint8) * 255, "source_lip_edge")
    owner[source_feather_front] = 7

    upper_size = max(3, 3 + 2 * int(round(3.0 * float(pose["upper_roll"]))))
    lower_size = max(3, 3 + 2 * int(round(3.0 * float(pose["lower_roll"]))))
    upper_outer = cv2.dilate(cavity, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (upper_size, upper_size)))
    lower_outer = cv2.dilate(cavity, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (lower_size, lower_size)))
    inner = cv2.erode(cavity, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    upper_ribbon = (cv2.subtract(upper_outer, inner) > 0) & (mouth_v <= 1.0)
    lower_ribbon = (cv2.subtract(lower_outer, inner) > 0) & (mouth_v >= -1.0)
    upper_alpha = _soft(upper_ribbon.astype(np.uint8) * 255, 0.55)
    lower_alpha = _soft(lower_ribbon.astype(np.uint8) * 255, 0.55)
    _blend(canvas, warped_source, upper_alpha)
    _record_layer(coverage, upper_ribbon.astype(np.uint8) * 255, "source_lip_edge")
    owner[upper_ribbon] = 7
    _blend(canvas, warped_source, lower_alpha)
    _record_layer(coverage, lower_ribbon.astype(np.uint8) * 255, "source_lip_edge")
    owner[lower_ribbon] = 7

    perimeter = cv2.subtract(
        cv2.dilate(cavity, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19))),
        cv2.erode(cavity, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))),
    )
    top_half = mouth_v <= 4.0
    bottom_half = mouth_v >= -2.0
    moustache_alpha = (warped_moustache.astype(np.float32) / 255.0) * (perimeter.astype(np.float32) / 255.0) * top_half
    beard_alpha = (warped_beard.astype(np.float32) / 255.0) * (perimeter.astype(np.float32) / 255.0) * bottom_half
    moustache_alpha_u8 = np.clip(moustache_alpha * 255.0, 0, 255).astype(np.uint8)
    beard_alpha_u8 = np.clip(beard_alpha * 255.0, 0, 255).astype(np.uint8)
    moustache_soft = _soft(moustache_alpha_u8, 0.45)
    _blend(canvas, warped_source, moustache_soft)
    moustache_front = moustache_alpha > 0.20
    _record_layer(coverage, moustache_front.astype(np.uint8) * 255, "moustache")
    owner[moustache_front] = 8
    beard_soft = _soft(beard_alpha_u8, 0.45)
    _blend(canvas, warped_source, beard_soft)
    beard_front = beard_alpha > 0.20
    _record_layer(coverage, beard_front.astype(np.uint8) * 255, "beard")
    owner[beard_front] = 9

    seam_boundary = cv2.morphologyEx(
        cavity, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ) > 0
    seam_sources = (
        source_feather_front | upper_ribbon | lower_ribbon | moustache_front | beard_front
    ).astype(np.uint8)
    seam_sources = cv2.morphologyEx(
        seam_sources, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
    )
    labels_count, seam_labels = cv2.connectedComponents(seam_sources)
    largest_boundary_coverage = 0
    boundary_total = int(seam_boundary.sum())
    for label in range(1, labels_count):
        component = (seam_labels == label).astype(np.uint8)
        expanded = cv2.dilate(component, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
        largest_boundary_coverage = max(
            largest_boundary_coverage, int((expanded & seam_boundary).sum()),
        )
    seam_coverage_ratio = (
        float(largest_boundary_coverage / boundary_total) if boundary_total else 1.0
    )

    oral_union = visible | upper_teeth | lower_teeth | tongue
    texture_ring = cv2.subtract(
        cv2.dilate(cavity, np.ones((13, 13), np.uint8)), cavity,
    ) > 0
    texture_values = cv2.cvtColor(warped_source, cv2.COLOR_RGB2GRAY)[texture_ring]
    return {
        "cavity": int(cavity_hard.sum()),
        "upper_teeth": int(upper_teeth.sum()),
        "upper_dentition_centroid_y": upper_centroid_y,
        "lower_teeth": int(lower_teeth.sum()),
        "tongue": int(tongue.sum()),
        "lip_ribbon": int((source_feather_front | upper_ribbon | lower_ribbon).sum()),
        "moustache_overlap": int(moustache_front.sum()),
        "beard_overlap": int(beard_front.sum()),
        "connected_source_seam_coverage_ratio": seam_coverage_ratio,
        "oral_outside": int((oral_union & ~cavity_hard).sum()),
        "generated_atlas_outer_ring": int(generated_outer_ring.sum()),
        "upper_dentition_forbidden_source_pixels": int(
            canonical_dentition.upper_dentition_forbidden_source_pixels
        ),
        "source_texture_variance": float(texture_values.var()) if texture_values.size else 0.0,
    }


def _native_frame(
    prepared: PreparedSourceTexturedFace, frame_number: int,
) -> tuple[np.ndarray, FrameEvidence]:
    if not 1 <= frame_number <= prepared.contract["clock"]["frame_count"]:
        raise SourceTexturedFaceError(f"frame number out of range: {frame_number}")
    plate = prepared.plate
    canvas = plate.copy()
    owner = np.zeros(plate.shape[:2], dtype=np.uint8)
    coverage = np.zeros(plate.shape[:2], dtype=np.uint16)
    pose, weights = mouth_controls(prepared.contract, frame_number)
    oral_activation = _oral_activation(pose, weights)
    geometry = prepared.contract["semantic_geometry_native_xy"]
    destination = _destination_points(prepared.contract, prepared.source_points, pose)
    triangle_metrics = _triangle_metrics(prepared.source_points, destination, prepared.triangles)
    warped_source = plate
    warped_moustache = prepared.moustache_alpha
    warped_beard = prepared.beard_alpha
    warp_support = np.zeros(plate.shape[:2], dtype=np.uint8)
    warped_source_pixels = 0
    oral = {
        "cavity": 0, "upper_teeth": 0, "lower_teeth": 0, "tongue": 0,
        "upper_dentition_centroid_y": 0.0,
        "lip_ribbon": 0, "moustache_overlap": 0, "beard_overlap": 0, "oral_outside": 0,
        "connected_source_seam_coverage_ratio": 1.0,
        "generated_atlas_outer_ring": 0,
        "upper_dentition_forbidden_source_pixels": 0,
        "source_texture_variance": 0.0,
    }
    if pose["opening"] > 0.01 and pose["width"] > 0.01:
        map_x, map_y, support_crop, bounds = _dense_inverse_maps(
            plate.shape[:2], prepared.source_points, destination, prepared.triangles,
        )
        x1, y1, x2, y2 = bounds
        warped_source = plate.copy()
        warped_source[y1:y2, x1:x2] = cv2.remap(
            plate, map_x, map_y, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101,
        )
        warped_moustache = prepared.moustache_alpha.copy()
        warped_moustache[y1:y2, x1:x2] = cv2.remap(
            prepared.moustache_alpha, map_x, map_y, cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
        warped_beard = prepared.beard_alpha.copy()
        warped_beard[y1:y2, x1:x2] = cv2.remap(
            prepared.beard_alpha, map_x, map_y, cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
        warp_support[y1:y2, x1:x2] = support_crop
        changed_by_warp = (warp_support > 0) & np.any(warped_source != plate, axis=2)
        warped_source_pixels = int(changed_by_warp.sum())
        canvas[warp_support > 0] = warped_source[warp_support > 0]
        owner[changed_by_warp] = 1
        _record_layer(coverage, changed_by_warp.astype(np.uint8) * 255, "source_warp")
        center = (
            float(geometry["mouth_center"][0]),
            float(geometry["mouth_center"][1]) + float(pose["jaw_drop"]) * 0.16,
        )
        oral = _compose_authored_oral_anatomy(
            canvas, warped_source, warped_moustache, warped_beard, owner, coverage,
            prepared.oral_cells, center,
            tuple(float(value) for value in geometry["upper_dentition_anchor_native_xy"]),
            pose, weights, oral_activation, float(geometry["mouth_angle_degrees"]),
        )

    closure = blink_closure(prepared.contract, frame_number)
    iris_ratios: list[float] = []
    lid_areas: list[int] = []
    lid_owner = np.zeros_like(owner)
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        ratio, area = phase33._compose_eye_lids(
            canvas, plate, prepared.phase33_base.lid_texture, lid_owner,
            tuple(eye["center"]), tuple(eye["radius"]), closure,
        )
        iris_ratios.append(ratio)
        lid_areas.append(area)
    owner[lid_owner == 7] = 10
    owner[lid_owner == 8] = 11
    owner[lid_owner == 9] = 12
    _record_layer(coverage, (lid_owner > 0).astype(np.uint8) * 255, "eyelids")

    changed = np.any(canvas != plate, axis=2)
    outside = changed & ~prepared.feature_support
    counts = {
        OWNER_NAMES[index]: int((owner == index).sum())
        for index in OWNER_NAMES if int((owner == index).sum()) > 0
    }
    evidence = FrameEvidence(
        pose_weights={name: float(value) for name, value in weights.items()},
        oral_activation=oral_activation,
        blink_closure=closure,
        iris_occlusion_ratios=iris_ratios,
        lid_areas=lid_areas,
        cavity_area=int(oral["cavity"]),
        upper_teeth_area=int(oral["upper_teeth"]),
        upper_dentition_centroid_y=float(oral["upper_dentition_centroid_y"]),
        lower_teeth_area=int(oral["lower_teeth"]),
        tongue_area=int(oral["tongue"]),
        warped_source_pixels=warped_source_pixels,
        source_texture_variance=float(oral["source_texture_variance"]),
        source_lip_ribbon_pixels=int(oral["lip_ribbon"]),
        moustache_front_overlap=int(oral["moustache_overlap"]),
        beard_front_overlap=int(oral["beard_overlap"]),
        connected_source_seam_coverage_ratio=float(oral["connected_source_seam_coverage_ratio"]),
        oral_pixels_outside_cavity=int(oral["oral_outside"]),
        generated_atlas_outer_ring_pixels=int(oral["generated_atlas_outer_ring"]),
        upper_dentition_forbidden_source_pixels=int(oral["upper_dentition_forbidden_source_pixels"]),
        changed_pixels=int(changed.sum()),
        changed_outside_support=int(outside.sum()),
        folded_triangles=int(triangle_metrics["folded_triangles"]),
        minimum_triangle_area_ratio=float(triangle_metrics["minimum_triangle_area_ratio"]),
        maximum_triangle_area_ratio=float(triangle_metrics["maximum_triangle_area_ratio"]),
        maximum_triangle_condition_number=float(triangle_metrics["maximum_triangle_condition_number"]),
        final_owner_counts=counts,
        depth_order_violation_pixels=_depth_order_violation_pixels(owner, coverage),
    )
    return canvas, evidence


def compose_frame(prepared: PreparedSourceTexturedFace, frame_number: int) -> Image.Image:
    native, _ = _native_frame(prepared, frame_number)
    clock = prepared.contract["clock"]
    return Image.fromarray(native, "RGB").resize(
        (clock["output_width"], clock["output_height"]), Image.Resampling.LANCZOS,
    )


def _max_8x8_delta(first: np.ndarray, second: np.ndarray, mask: np.ndarray) -> float:
    delta = np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(axis=2)
    local = cv2.boxFilter(delta, -1, (8, 8), normalize=True)
    values = local[mask]
    return float(values.max()) if values.size else 0.0


def _preflight(prepared: PreparedSourceTexturedFace) -> dict[str, Any]:
    frame_count = prepared.contract["clock"]["frame_count"]
    frames: dict[int, tuple[np.ndarray, FrameEvidence]] = {}
    maximum_delta = 0.0
    maximum_delta_pair = [1, 1]
    maximum_outside = 0
    previous: np.ndarray | None = None
    for frame_number in range(1, frame_count + 1):
        frame, evidence = _native_frame(prepared, frame_number)
        frames[frame_number] = (frame, evidence)
        maximum_outside = max(maximum_outside, evidence.changed_outside_support)
        if previous is not None:
            adjacent = _max_8x8_delta(previous, frame, prepared.feature_support)
            if adjacent > maximum_delta:
                maximum_delta = adjacent
                maximum_delta_pair = [frame_number - 1, frame_number]
        previous = frame
    prepared.preflight_native_frames = {
        frame_number: frame for frame_number, (frame, _) in frames.items()
    }
    plate = prepared.plate
    endpoints = max(
        int(np.any(frames[1][0] != plate, axis=2).sum()),
        int(np.any(frames[frame_count][0] != plate, axis=2).sum()),
    )
    key_frames = prepared.contract["performance"]["key_pose_frames"]
    non_neutral = {name: frames[int(frame)][1] for name, frame in key_frames.items() if name != "X"}
    pose_hashes = {_raw_frame_hash(frames[int(frame)][0]) for name, frame in key_frames.items() if name != "X"}
    alar_base_y = int(prepared.contract["semantic_geometry_native_xy"]["protected_alar_base_y"])
    viseme_changed_above_alar = max(
        int(np.any(frames[int(frame)][0][:alar_base_y] != plate[:alar_base_y], axis=2).sum())
        for name, frame in key_frames.items() if name != "X"
    )
    guard = int(prepared.contract["semantic_geometry_native_xy"]["final_resample_guard_native_px"])
    clock = prepared.contract["clock"]
    protected_output_y = int(math.floor((alar_base_y - guard) * clock["output_height"] / clock["source_height"]))
    output_size = (int(clock["output_width"]), int(clock["output_height"]))
    plate_output = np.asarray(Image.fromarray(plate, "RGB").resize(output_size, Image.Resampling.LANCZOS), dtype=np.uint8)
    output_viseme_changed_above_margin = 0
    for name, frame in key_frames.items():
        if name == "X":
            continue
        output_frame = np.asarray(
            Image.fromarray(frames[int(frame)][0], "RGB").resize(output_size, Image.Resampling.LANCZOS),
            dtype=np.uint8,
        )
        output_viseme_changed_above_margin = max(
            output_viseme_changed_above_margin,
            int(np.any(output_frame[:protected_output_y] != plate_output[:protected_output_y], axis=2).sum()),
        )
    protected_displacements = []
    for name, pose in prepared.contract["pose_geometry_native_px"].items():
        if name == "X":
            continue
        destination = _destination_points(prepared.contract, prepared.source_points, pose)
        protected = prepared.source_points[:, 1] <= alar_base_y
        protected_displacements.extend(
            np.linalg.norm(destination[protected] - prepared.source_points[protected], axis=1).tolist()
        )
    x1, y1, x2, y2 = prepared.contract["semantic_geometry_native_xy"]["deformation_roi"]
    confusable_pair_deltas = {}
    for first, second in (("A", "F"), ("C", "E"), ("B", "D"), ("G", "H")):
        first_frame = frames[int(key_frames[first])][0][y1:y2, x1:x2].astype(np.float32)
        second_frame = frames[int(key_frames[second])][0][y1:y2, x1:x2].astype(np.float32)
        confusable_pair_deltas[f"{first}/{second}"] = float(np.abs(first_frame - second_frame).mean())
    blink_peak = int(prepared.contract["performance"]["blink_max_frames"][-1])
    blink = frames[blink_peak][1]
    return {
        "exact_endpoint_changed_pixels": endpoints,
        "maximum_changed_pixels_outside_feature_support": maximum_outside,
        "minimum_full_blink_iris_occlusion_ratio": min(blink.iris_occlusion_ratios),
        "minimum_full_blink_lid_area_per_eye": min(blink.lid_areas),
        "distinct_non_neutral_pose_hashes": len(pose_hashes),
        "minimum_open_pose_cavity_area": min(item.cavity_area for item in non_neutral.values()),
        "B_cavity_area": non_neutral["B"].cavity_area,
        "E_upper_teeth_area": non_neutral["E"].upper_teeth_area,
        "upper_dentition_anchor_y_range_px": (
            max(item.upper_dentition_centroid_y for item in non_neutral.values())
            - min(item.upper_dentition_centroid_y for item in non_neutral.values())
        ),
        "H_tongue_area": non_neutral["H"].tongue_area,
        "minimum_warped_source_pixels_per_non_neutral_pose": min(item.warped_source_pixels for item in non_neutral.values()),
        "maximum_warped_source_pixels_per_non_neutral_pose": max(item.warped_source_pixels for item in non_neutral.values()),
        "minimum_source_texture_variance": min(item.source_texture_variance for item in non_neutral.values()),
        "maximum_triangle_condition_number": max(item.maximum_triangle_condition_number for item in non_neutral.values()),
        "minimum_triangle_area_ratio": min(item.minimum_triangle_area_ratio for item in non_neutral.values()),
        "maximum_triangle_area_ratio": max(item.maximum_triangle_area_ratio for item in non_neutral.values()),
        "maximum_folded_triangles": max(item.folded_triangles for item in non_neutral.values()),
        "maximum_oral_pixels_outside_cavity": max(item.oral_pixels_outside_cavity for item in non_neutral.values()),
        "maximum_generated_atlas_outer_ring_pixels": max(
            item.generated_atlas_outer_ring_pixels for item in non_neutral.values()
        ),
        "maximum_upper_dentition_forbidden_source_pixels": max(
            item.upper_dentition_forbidden_source_pixels for item in non_neutral.values()
        ),
        "minimum_moustache_front_overlap_pixels": min(item.moustache_front_overlap for item in non_neutral.values()),
        "minimum_beard_front_overlap_pixels": min(item.beard_front_overlap for item in non_neutral.values()),
        "minimum_connected_source_seam_coverage_ratio": min(
            item.connected_source_seam_coverage_ratio for item in non_neutral.values()
        ),
        "minimum_source_lip_or_hair_seam_pixels_per_pose": min(
            item.source_lip_ribbon_pixels + item.moustache_front_overlap + item.beard_front_overlap
            for item in non_neutral.values()
        ),
        "maximum_viseme_changed_pixels_above_alar_base": viseme_changed_above_alar,
        "maximum_output_viseme_changed_pixels_above_protected_margin": output_viseme_changed_above_margin,
        "protected_output_margin_y": protected_output_y,
        "maximum_protected_landmark_displacement_px": max(protected_displacements, default=0.0),
        "confusable_pair_mouth_mean_absolute_deltas": confusable_pair_deltas,
        "minimum_confusable_pair_mouth_mean_absolute_delta": min(confusable_pair_deltas.values()),
        "maximum_depth_order_violation_pixels": max(
            evidence.depth_order_violation_pixels for _, evidence in frames.values()
        ),
        "maximum_adjacent_feature_8x8_mean_delta": maximum_delta,
        "maximum_adjacent_feature_8x8_mean_delta_frame_pair": maximum_delta_pair,
        "maximum_adjacent_oral_activation_delta": max(
            abs(frames[index + 1][1].oral_activation - frames[index][1].oral_activation)
            for index in range(1, frame_count)
        ),
        "frame_82_oral_activation": frames[82][1].oral_activation,
        "frames_evaluated": frame_count,
        "source_identity_texture_only": True,
        "complete_feature_photo_crossfades_used": False,
        "generated_atlas_outer_ring_used": any(
            item.generated_atlas_outer_ring_pixels > 0 for item in non_neutral.values()
        ),
        "audio_used": False,
        "reinforcement_learning_used": False,
    }


def _preflight_gates(contract: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    thresholds = contract["preencode_gates"]
    checks = [
        ("exact_endpoint_changed_pixels", metrics["exact_endpoint_changed_pixels"], "==", thresholds["required_exact_endpoint_changed_pixels"]),
        ("changed_pixels_outside_feature_support", metrics["maximum_changed_pixels_outside_feature_support"], "==", thresholds["required_changes_outside_feature_support"]),
        ("full_blink_iris_occlusion", metrics["minimum_full_blink_iris_occlusion_ratio"], ">=", thresholds["minimum_full_blink_iris_occlusion_ratio"]),
        ("full_blink_lid_area", metrics["minimum_full_blink_lid_area_per_eye"], ">=", thresholds["minimum_full_blink_lid_area_per_eye"]),
        ("distinct_non_neutral_pose_hashes", metrics["distinct_non_neutral_pose_hashes"], "==", thresholds["required_distinct_non_neutral_pose_hashes"]),
        ("open_pose_cavity_area", metrics["minimum_open_pose_cavity_area"], ">=", thresholds["minimum_open_pose_cavity_area"]),
        ("B_cavity_area", metrics["B_cavity_area"], ">=", thresholds["minimum_B_cavity_area"]),
        ("E_upper_teeth_area", metrics["E_upper_teeth_area"], ">=", thresholds["minimum_E_upper_teeth_area"]),
        ("upper_dentition_anchor_y_range", metrics["upper_dentition_anchor_y_range_px"], "<=", thresholds["maximum_upper_dentition_anchor_y_range_px"]),
        ("H_tongue_area", metrics["H_tongue_area"], ">=", thresholds["minimum_H_tongue_area"]),
        ("warped_source_pixels", metrics["minimum_warped_source_pixels_per_non_neutral_pose"], ">=", thresholds["minimum_warped_source_pixels_per_non_neutral_pose"]),
        ("maximum_warped_source_pixels", metrics["maximum_warped_source_pixels_per_non_neutral_pose"], "<=", thresholds["maximum_warped_source_pixels_per_non_neutral_pose"]),
        ("source_texture_variance", metrics["minimum_source_texture_variance"], ">=", thresholds["minimum_source_texture_variance"]),
        ("triangle_condition_number", metrics["maximum_triangle_condition_number"], "<=", thresholds["maximum_triangle_condition_number"]),
        ("minimum_triangle_area_ratio", metrics["minimum_triangle_area_ratio"], ">=", thresholds["minimum_triangle_area_ratio"]),
        ("maximum_triangle_area_ratio", metrics["maximum_triangle_area_ratio"], "<=", thresholds["maximum_triangle_area_ratio"]),
        ("folded_triangles", metrics["maximum_folded_triangles"], "==", thresholds["required_folded_triangles"]),
        ("oral_pixels_outside_cavity", metrics["maximum_oral_pixels_outside_cavity"], "==", thresholds["required_oral_pixels_outside_cavity"]),
        ("generated_atlas_outer_ring_pixels", metrics["maximum_generated_atlas_outer_ring_pixels"], "==", thresholds["required_generated_atlas_outer_ring_pixels"]),
        ("upper_dentition_forbidden_source_pixels", metrics["maximum_upper_dentition_forbidden_source_pixels"], "==", thresholds["required_upper_dentition_forbidden_source_pixels"]),
        ("moustache_front_overlap", metrics["minimum_moustache_front_overlap_pixels"], ">=", thresholds["minimum_moustache_front_overlap_pixels"]),
        ("beard_front_overlap", metrics["minimum_beard_front_overlap_pixels"], ">=", thresholds["minimum_beard_front_overlap_pixels"]),
        ("connected_source_seam_coverage", metrics["minimum_connected_source_seam_coverage_ratio"], ">=", thresholds["minimum_connected_source_seam_coverage_ratio"]),
        ("source_lip_or_hair_seam", metrics["minimum_source_lip_or_hair_seam_pixels_per_pose"], ">=", thresholds["minimum_source_lip_or_hair_seam_pixels_per_pose"]),
        ("viseme_changes_above_alar_base", metrics["maximum_viseme_changed_pixels_above_alar_base"], "==", thresholds["required_viseme_changed_pixels_above_alar_base"]),
        ("output_viseme_changes_above_protected_margin", metrics["maximum_output_viseme_changed_pixels_above_protected_margin"], "==", thresholds["required_output_viseme_changed_pixels_above_protected_margin"]),
        ("protected_landmark_displacement", metrics["maximum_protected_landmark_displacement_px"], "<=", thresholds["maximum_protected_landmark_displacement_px"]),
        ("confusable_pose_separation", metrics["minimum_confusable_pair_mouth_mean_absolute_delta"], ">=", thresholds["minimum_confusable_pair_mouth_mean_absolute_delta"]),
        ("depth_order_violation_pixels", metrics["maximum_depth_order_violation_pixels"], "==", thresholds["maximum_depth_order_violation_pixels"]),
        ("adjacent_feature_8x8_mean_delta", metrics["maximum_adjacent_feature_8x8_mean_delta"], "<=", thresholds["maximum_adjacent_feature_8x8_mean_delta"]),
        ("adjacent_oral_activation_delta", metrics["maximum_adjacent_oral_activation_delta"], "<=", thresholds["maximum_adjacent_oral_activation_delta"]),
        ("frame_82_oral_activation", metrics["frame_82_oral_activation"], "<=", thresholds["maximum_frame_82_oral_activation"]),
    ]
    results = []
    for name, actual, operator, threshold in checks:
        if operator == "==":
            passed = actual == threshold
        elif operator == ">=":
            passed = actual >= threshold
        else:
            passed = actual <= threshold
        results.append({"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(passed)})
    return results


def prepare_source_textured_face(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> PreparedSourceTexturedFace:
    contract_path = Path(path).resolve()
    contract = load_contract(contract_path)
    phase33_contract = _resolve_repo_path(contract["locks"]["phase33_v3_contract"]["path"])
    base = phase33.prepare_semantic_face(phase33_contract)
    clock = contract["clock"]
    if base.plate.shape != (clock["source_height"], clock["source_width"], 3):
        raise SourceTexturedFaceError(f"plate dimensions changed: {base.plate.shape}")
    source_points, triangles = _cage(contract)
    support = np.zeros(base.plate.shape[:2], dtype=np.uint8)
    x1, y1, x2, y2 = contract["semantic_geometry_native_xy"]["feature_support_box"]
    support[y1:y2, x1:x2] = 255
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = contract["semantic_geometry_native_xy"][eye_name]
        support = cv2.bitwise_or(
            support,
            phase33._ellipse_mask(base.plate.shape[:2], tuple(eye["center"]), (eye["radius"][0] + 7, eye["radius"][1] + 7)),
        )
    oral_cells = _load_oral_cells(_resolve_repo_path(contract["locks"]["oral_interior_atlas"]["path"]))
    moustache_alpha = cv2.GaussianBlur(base.moustache_mask, (0, 0), sigmaX=0.75, sigmaY=0.75)
    beard_alpha = cv2.GaussianBlur(base.beard_mask, (0, 0), sigmaX=0.75, sigmaY=0.75)
    prepared = PreparedSourceTexturedFace(
        contract, contract_path, base, source_points, triangles, support > 0,
        oral_cells, moustache_alpha, beard_alpha, {}, {},
    )
    prepared.preflight_measurements = _preflight(prepared)
    failures = [gate for gate in _preflight_gates(contract, prepared.preflight_measurements) if not gate["passed"]]
    if failures:
        raise SourceTexturedFaceError("source-textured preflight failed: " + json.dumps(failures, sort_keys=True))
    return prepared


def _contact_sheet(frames: list[Image.Image], columns: int, tile: tuple[int, int], labels: list[str]) -> Image.Image:
    rows = int(math.ceil(len(frames) / columns))
    sheet = Image.new("RGB", (columns * tile[0], rows * tile[1]), (15, 12, 10))
    draw = ImageDraw.Draw(sheet)
    for index, (frame, label) in enumerate(zip(frames, labels)):
        thumb = frame.copy()
        thumb.thumbnail(tile, Image.Resampling.LANCZOS)
        x = (index % columns) * tile[0] + (tile[0] - thumb.width) // 2
        y = (index // columns) * tile[1] + (tile[1] - thumb.height) // 2
        sheet.paste(thumb, (x, y))
        draw.rectangle((x + 3, y + 3, x + 64, y + 20), fill=(15, 12, 10))
        draw.text((x + 7, y + 5), label, fill=(246, 227, 186))
    return sheet


def _scaled_native_box(contract: dict[str, Any], box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    clock = contract["clock"]
    scale_x = clock["output_width"] / clock["source_width"]
    scale_y = clock["output_height"] / clock["source_height"]
    return tuple(
        int(round(value * (scale_x if index % 2 == 0 else scale_y)))
        for index, value in enumerate(box)
    )


def _write_review_sheets(
    frames: list[Image.Image], stage: Path, contract: dict[str, Any],
) -> dict[str, dict[str, str]]:
    preview = contract["preview"]
    key_frames = contract["performance"]["key_pose_frames"]
    mouth_box = _scaled_native_box(contract, (540, 330, 735, 465))

    pose_names = list("XABCDEFGH")
    pose_numbers = [int(key_frames[name]) for name in pose_names]
    mouth_crops = [frames[number - 1].crop(mouth_box) for number in pose_numbers]
    mouth_sheet = _contact_sheet(mouth_crops, 3, (360, 250), pose_names)
    mouth_path = stage / preview["mouth_pose_sheet_filename"]
    mouth_sheet.save(mouth_path, format="PNG", optimize=True)

    transition_numbers: list[int] = []
    transition_labels: list[str] = []
    keys = [(int(item["frame"]), str(item["pose"])) for item in contract["performance"]["viseme_keyframes"]]
    for (left_frame, left_pose), (right_frame, right_pose) in zip(keys, keys[1:]):
        if left_pose == right_pose:
            continue
        for number in (left_frame, left_frame + 1, right_frame - 1, right_frame):
            transition_numbers.append(number)
            transition_labels.append(f"{left_pose}>{right_pose} F{number:03d}")
    transition_crops = [frames[number - 1].crop(mouth_box) for number in transition_numbers]
    transition_sheet = _contact_sheet(transition_crops, 4, (300, 190), transition_labels)
    transition_path = stage / preview["transition_sheet_filename"]
    transition_sheet.save(transition_path, format="PNG", optimize=True)

    neutral = np.asarray(frames[int(key_frames["X"]) - 1], dtype=np.uint8)
    alar_y = int(contract["semantic_geometry_native_xy"]["protected_alar_base_y"])
    guard = int(contract["semantic_geometry_native_xy"]["final_resample_guard_native_px"])
    upper_box_native = (500, 185, 755, alar_y - guard)
    upper_box = _scaled_native_box(contract, upper_box_native)
    difference_images: list[Image.Image] = []
    difference_labels: list[str] = []
    for name in "ABCDEFGH":
        current = np.asarray(frames[int(key_frames[name]) - 1], dtype=np.uint8)
        difference = np.abs(current.astype(np.int16) - neutral.astype(np.int16)).astype(np.uint8)
        changed = int(np.any(difference[upper_box[1]:upper_box[3], upper_box[0]:upper_box[2]] > 0, axis=2).sum())
        amplified = np.clip(difference.astype(np.uint16) * 4, 0, 255).astype(np.uint8)
        difference_images.append(Image.fromarray(amplified, "RGB").crop(upper_box))
        difference_labels.append(f"{name} changed={changed}")
    difference_sheet = _contact_sheet(difference_images, 4, (360, 210), difference_labels)
    difference_path = stage / preview["upper_face_difference_sheet_filename"]
    difference_sheet.save(difference_path, format="PNG", optimize=True)

    delivery_pairs: list[Image.Image] = []
    for name in "ABCDEFGH":
        frame = frames[int(key_frames[name]) - 1]
        pair = Image.new("RGB", (640, 240), (15, 12, 10))
        full = frame.copy()
        full.thumbnail((320, 180), Image.Resampling.LANCZOS)
        mouth = frame.crop(mouth_box)
        mouth.thumbnail((320, 220), Image.Resampling.LANCZOS)
        pair.paste(full, (0, 30))
        pair.paste(mouth, (320 + (320 - mouth.width) // 2, (240 - mouth.height) // 2))
        delivery_pairs.append(pair)
    delivery_sheet = _contact_sheet(delivery_pairs, 2, (640, 240), list("ABCDEFGH"))
    delivery_path = stage / preview["delivery_scale_sheet_filename"]
    delivery_sheet.save(delivery_path, format="PNG", optimize=True)

    special_groups = (
        ("F-contact", [58, 59, 62, 64]),
        ("H-tongue", [74, 75, 78, 80]),
        ("H>X", [80, 81, 82, 83]),
    )
    special_numbers = [number for _, numbers in special_groups for number in numbers]
    special_labels = [f"{label} F{number:03d}" for label, numbers in special_groups for number in numbers]
    special_crops = [frames[number - 1].crop(mouth_box) for number in special_numbers]
    special_sheet = _contact_sheet(special_crops, 4, (320, 210), special_labels)
    special_path = stage / preview["articulation_specials_sheet_filename"]
    special_sheet.save(special_path, format="PNG", optimize=True)

    return {
        "mouth_pose_sheet": {"file": mouth_path.name, "sha256": _sha256(mouth_path)},
        "transition_sheet": {"file": transition_path.name, "sha256": _sha256(transition_path)},
        "upper_face_difference_sheet": {"file": difference_path.name, "sha256": _sha256(difference_path)},
        "delivery_scale_sheet": {"file": delivery_path.name, "sha256": _sha256(delivery_path)},
        "articulation_specials_sheet": {"file": special_path.name, "sha256": _sha256(special_path)},
    }


def _preview_output_path(contract: dict[str, Any], development_label: str | None) -> Path:
    output = (REPO_ROOT / contract["preview"]["directory"]).resolve()
    if development_label is None:
        return output
    if not development_label or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in development_label):
        raise SourceTexturedFaceError("development label must contain only lowercase letters, digits, and hyphens")
    return output.with_name(f"{output.name}-{development_label}")


def write_unencoded_preview(
    contract_path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
    *,
    development_label: str | None = None,
) -> dict[str, Any]:
    prepared = prepare_source_textured_face(contract_path)
    output = _preview_output_path(prepared.contract, development_label)
    if output.exists():
        raise SourceTexturedFaceError(f"immutable preview already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    try:
        frame_count = prepared.contract["clock"]["frame_count"]
        frames: list[Image.Image] = []
        frame_hashes = []
        for frame_number in range(1, frame_count + 1):
            native = prepared.preflight_native_frames.pop(frame_number)
            clock = prepared.contract["clock"]
            frame = Image.fromarray(native, "RGB").resize(
                (clock["output_width"], clock["output_height"]), Image.Resampling.LANCZOS,
            )
            frames.append(frame)
            frame_hashes.append({"frame": frame_number, "rgb_sha256": _raw_frame_hash(np.asarray(frame, dtype=np.uint8))})
        archive_path = stage / prepared.contract["preview"]["lossless_frame_archive_filename"]
        archive_metadata = _write_lossless_frame_archive(frames, archive_path)
        labels = []
        for frame_number in range(1, frame_count + 1):
            _, weights = mouth_controls(prepared.contract, frame_number)
            pose = max(weights, key=weights.get)
            labels.append(f"F{frame_number:03d} {pose}")
        contact = _contact_sheet(frames, 12, (160, 90), labels)
        contact_path = stage / prepared.contract["preview"]["contact_sheet_filename"]
        contact.save(contact_path, format="PNG", optimize=True)
        key_frames = prepared.contract["performance"]["key_pose_frames"]
        key_numbers = [
            1,
            int(prepared.contract["performance"]["blink_max_frames"][-1]),
            int(key_frames["X"]),
            *[int(key_frames[name]) for name in "ABCDEFGH"],
            frame_count,
        ]
        key_labels = ["neutral", "blink", "X", "A", "B", "C", "D", "E", "F", "G", "H", "X-return"]
        clock = prepared.contract["clock"]
        sx = clock["output_width"] / clock["source_width"]
        sy = clock["output_height"] / clock["source_height"]
        crop_native = (485, 180, 790, 535)
        crop = tuple(int(round(value * (sx if index % 2 == 0 else sy))) for index, value in enumerate(crop_native))
        crops = [frames[number - 1].crop(crop) for number in key_numbers]
        key_sheet = _contact_sheet(crops, 6, (360, 390), key_labels)
        key_path = stage / prepared.contract["preview"]["key_sheet_filename"]
        key_sheet.save(key_path, format="PNG", optimize=True)
        review_sheets = _write_review_sheets(frames, stage, prepared.contract)
        manifest = {
            "manifest_version": 1,
            "development_label": development_label,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": _sha256(prepared.contract_path),
                "canonical_sha256": _canonical_hash(prepared.contract),
            },
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH)},
            "toolchain": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "numpy": np.__version__,
                "pillow": PILLOW_VERSION,
                "opencv": cv2.__version__,
            },
            "clock": prepared.contract["clock"],
            "frame_hash_domain": "raw_rgb24_1920x1080_row_major",
            "frames": frame_hashes,
            "lossless_review_frame_archive": {
                "file": archive_path.name,
                "sha256": _sha256(archive_path),
                **archive_metadata,
            },
            "all_96_contact_sheet": {"file": contact_path.name, "sha256": _sha256(contact_path)},
            "key_pose_sheet": {"file": key_path.name, "sha256": _sha256(key_path)},
            "review_sheets": review_sheets,
            "preflight_measurements": prepared.preflight_measurements,
            "preflight_gates": _preflight_gates(prepared.contract, prepared.preflight_measurements),
            "complete_beat_review_required": True,
            "all_96_raw_frame_hashes_present": len(frame_hashes) == 96,
            "lossless_review_frame_archive_present": archive_path.is_file(),
            "final_encode_allowed_without_bound_review_receipt": False,
        }
        manifest_path = stage / prepared.contract["preview"]["manifest_filename"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(stage, output)
        return {
            "preview_directory": str(output),
            "manifest": str(output / manifest_path.name),
            "manifest_sha256": _sha256(output / manifest_path.name),
            "contact_sheet": str(output / contact_path.name),
            "key_sheet": str(output / key_path.name),
            "preflight_measurements": prepared.preflight_measurements,
        }
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the Phase34 source-textured nine-viseme preview")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--development-label")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.preview:
        raise SourceTexturedFaceError("Phase34 v1 is preview-only until a bound visual review authorizes one encode")
    print(json.dumps(write_unencoded_preview(development_label=args.development_label), indent=2))


if __name__ == "__main__":
    main()
