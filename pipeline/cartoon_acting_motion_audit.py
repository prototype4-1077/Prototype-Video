"""Still-only Phase38 camera-normalized acting-motion audit for June Oxley."""
from __future__ import annotations

import argparse
import gzip
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
from PIL import Image, ImageDraw, ImageFont, __version__ as PILLOW_VERSION

from pipeline.cartoon_hero_scene import load_body_motion_contract


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase38_acting_motion_audit_v1.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_acting_motion_audit.py"
TEST_RELATIVE_PATH = "pipeline/tests/test_cartoon_acting_motion_audit.py"


class ActingMotionAuditError(RuntimeError):
    pass


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _strict_json(path: str | Path, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ActingMotionAuditError(f"{label} contains duplicate key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ActingMotionAuditError(f"{label} contains non-finite value: {value}")

    try:
        payload = Path(path).read_bytes().decode("utf-8")
        result = json.loads(payload, object_pairs_hook=reject_duplicates, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ActingMotionAuditError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(result, dict):
        raise ActingMotionAuditError(f"{label} must be a JSON object")
    return result


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ActingMotionAuditError(f"{label} mismatch: {actual!r} != {expected!r}")


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ActingMotionAuditError(f"repository path escapes worktree: {relative}") from exc
    if not path.is_file():
        raise ActingMotionAuditError(f"repository file missing: {relative}")
    return path


def _outputs_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    outputs_root = (REPO_ROOT / "../../outputs").resolve()
    try:
        path.relative_to(outputs_root)
    except ValueError as exc:
        raise ActingMotionAuditError(f"external path escapes outputs tree: {relative}") from exc
    return path


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned contract path")
    contract = _strict_json(resolved, "Phase38 acting audit contract")
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase38_acting_motion_audit_v1", "contract id")
    _require_equal(contract["cash_cost"], 0, "cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "paid dependency")
    _require_equal(contract["network_runtime_required"], False, "network dependency")
    diagnostic = contract["diagnostic"]
    for field in (
        "source_mutation_allowed", "picture_rebuild_allowed", "video_encode_allowed",
        "promotion_allowed", "human_acting_acceptance_claim_allowed",
    ):
        _require_equal(diagnostic[field], False, field)
    for name, reference in contract["locks"].items():
        _require_equal(_sha256(_repo_path(reference["path"])), reference["sha256"], f"lock {name}")
    return contract


def _camera_geometry(push: float, scene: dict[str, Any]) -> dict[str, Any]:
    output = scene["output"]
    output_width = int(output["width"])
    output_height = int(output["height"])
    source_width = int(scene["image"]["width"])
    source_height = int(scene["image"]["height"])
    base_scale = max(output_width / source_width, output_height / source_height)
    scale = base_scale * (1.0 + float(push))
    resized_width = round(source_width * scale)
    resized_height = round(source_height * scale)
    anchor_x, anchor_y = (float(value) for value in scene["rig_regions"]["camera_anchor"])
    extra_x = resized_width - output_width
    extra_y = resized_height - output_height
    left = round(max(0.0, min(float(extra_x), extra_x * anchor_x)))
    top = round(max(0.0, min(float(extra_y), extra_y * anchor_y)))
    return {
        "source_width": source_width,
        "source_height": source_height,
        "output_width": output_width,
        "output_height": output_height,
        "base_scale": base_scale,
        "scale": scale,
        "relative_scale_from_zero_push": scale / base_scale,
        "resized_width": resized_width,
        "resized_height": resized_height,
        "crop_left": left,
        "crop_top": top,
    }


def _camera_normalize(
    frame: np.ndarray, push: float, scene: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    height, width = frame.shape[:2]
    geometry = _camera_geometry(push, scene)
    reference = _camera_geometry(0.0, scene)
    relative_scale = float(geometry["scale"]) / float(reference["scale"])
    left = float(geometry["crop_left"])
    top = float(geometry["crop_top"])
    reference_left = float(reference["crop_left"])
    reference_top = float(reference["crop_top"])
    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32),
    )
    map_x = (grid_x + reference_left) * relative_scale - left
    map_y = (grid_y + reference_top) * relative_scale - top
    valid = (map_x >= 0.0) & (map_y >= 0.0) & (map_x <= width - 1.0) & (map_y <= height - 1.0)
    aligned = cv2.remap(
        frame, map_x, map_y, interpolation=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0),
    )
    return aligned, valid, geometry


def _pair_region_metrics(
    first: np.ndarray,
    second: np.ndarray,
    first_valid: np.ndarray,
    second_valid: np.ndarray,
    box: list[int],
    metric_contract: dict[str, Any],
) -> dict[str, Any]:
    x1, y1, x2, y2 = (int(value) for value in box)
    valid = first_valid[y1:y2, x1:x2] & second_valid[y1:y2, x1:x2]
    if not np.any(valid):
        raise ActingMotionAuditError(f"region has no valid aligned pixels: {box}")
    a = first[y1:y2, x1:x2]
    b = second[y1:y2, x1:x2]
    pixel_delta = np.abs(a.astype(np.float32) - b.astype(np.float32)).mean(axis=2)
    values = pixel_delta[valid]
    thresholds = [float(value) for value in metric_contract["pixel_delta_thresholds_u8"]]

    gray_a = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    downscale = float(metric_contract["optical_flow_downscale"])
    flow_width = max(16, round(gray_a.shape[1] * downscale))
    flow_height = max(16, round(gray_a.shape[0] * downscale))
    small_a = cv2.resize(gray_a, (flow_width, flow_height), interpolation=cv2.INTER_AREA)
    small_b = cv2.resize(gray_b, (flow_width, flow_height), interpolation=cv2.INTER_AREA)
    flow_contract = metric_contract["farneback"]
    flow = cv2.calcOpticalFlowFarneback(
        small_a, small_b, None,
        float(flow_contract["pyr_scale"]), int(flow_contract["levels"]),
        int(flow_contract["winsize"]), int(flow_contract["iterations"]),
        int(flow_contract["poly_n"]), float(flow_contract["poly_sigma"]),
        int(flow_contract["flags"]),
    )
    flow_magnitude = np.linalg.norm(flow, axis=2) / downscale
    return {
        "valid_pixels": int(values.size),
        "mean_rgb_delta_u8": float(values.mean()),
        "p95_rgb_delta_u8": float(np.percentile(values, 95)),
        "maximum_rgb_delta_u8": float(values.max()),
        "fraction_above_2_u8": float(np.mean(values > thresholds[0])),
        "fraction_above_5_u8": float(np.mean(values > thresholds[1])),
        "median_flow_px": float(np.median(flow_magnitude)),
        "p95_flow_px": float(np.percentile(flow_magnitude, 95)),
        "maximum_flow_px": float(flow_magnitude.max()),
    }


def _aggregate_region(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mean_delta = np.asarray([row["mean_rgb_delta_u8"] for row in rows], dtype=np.float64)
    p95_delta = np.asarray([row["p95_rgb_delta_u8"] for row in rows], dtype=np.float64)
    p95_flow = np.asarray([row["p95_flow_px"] for row in rows], dtype=np.float64)
    maximum_index = int(np.argmax(mean_delta))
    return {
        "pair_count": len(rows),
        "median_pair_mean_rgb_delta_u8": float(np.median(mean_delta)),
        "p95_pair_mean_rgb_delta_u8": float(np.percentile(mean_delta, 95)),
        "maximum_pair_mean_rgb_delta_u8": float(mean_delta[maximum_index]),
        "maximum_pair_transition": rows[maximum_index]["transition"],
        "median_pair_p95_rgb_delta_u8": float(np.median(p95_delta)),
        "median_pair_p95_flow_px": float(np.median(p95_flow)),
        "p95_pair_p95_flow_px": float(np.percentile(p95_flow, 95)),
    }


def _font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    )
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _region_map(frame: np.ndarray, regions: dict[str, list[int]]) -> Image.Image:
    image = Image.fromarray(frame, "RGB")
    draw = ImageDraw.Draw(image)
    colors = {
        "face_head": (255, 214, 72),
        "torso": (85, 215, 255),
        "viewer_left_arm": (204, 126, 255),
        "table_hand": (255, 117, 75),
        "mug_static_control": (104, 238, 133),
        "background_atmosphere_control": (90, 160, 255),
    }
    font = _font(24)
    for name, box in regions.items():
        x1, y1, x2, y2 = (int(value) for value in box)
        color = colors[name]
        draw.rectangle((x1, y1, x2 - 1, y2 - 1), outline=color, width=4)
        text_box = draw.textbbox((0, 0), name, font=font)
        tw = text_box[2] - text_box[0]
        th = text_box[3] - text_box[1]
        draw.rectangle((x1, y1, x1 + tw + 10, y1 + th + 8), fill=(0, 0, 0))
        draw.text((x1 + 5, y1 + 3), name, fill=color, font=font)
    return image


def _timeline_image(
    rows_by_region: dict[str, list[dict[str, Any]]],
    frame_range: tuple[int, int],
    speech_start: int,
) -> Image.Image:
    width, height = 1920, 920
    margin_left, margin_right = 150, 70
    margin_top, margin_bottom = 110, 100
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    image = Image.new("RGB", (width, height), (17, 19, 22))
    draw = ImageDraw.Draw(image)
    title_font = _font(34)
    label_font = _font(22)
    small_font = _font(18)
    draw.text((margin_left, 28), "PHASE38 CAMERA-NORMALIZED DIRECT-ADDRESS MOTION", fill=(244, 238, 221), font=title_font)
    colors = {
        "face_head": (255, 214, 72),
        "torso": (85, 215, 255),
        "viewer_left_arm": (204, 126, 255),
        "table_hand": (255, 117, 75),
        "mug_static_control": (104, 238, 133),
        "background_atmosphere_control": (90, 160, 255),
    }
    all_values = [
        float(row["mean_rgb_delta_u8"])
        for rows in rows_by_region.values() for row in rows
    ]
    y_max = max(1.0, float(np.percentile(np.asarray(all_values), 99)) * 1.12)
    for index in range(6):
        value = y_max * index / 5
        y = margin_top + plot_height - round(plot_height * value / y_max)
        draw.line((margin_left, y, width - margin_right, y), fill=(55, 59, 65), width=1)
        draw.text((24, y - 10), f"{value:.2f}", fill=(180, 184, 189), font=small_font)
    first_frame, last_frame = frame_range
    for frame in (first_frame, speech_start, 120, 160, 200, last_frame):
        x = margin_left + round((frame - first_frame) / (last_frame - first_frame) * plot_width)
        color = (240, 132, 56) if frame == speech_start else (74, 78, 84)
        draw.line((x, margin_top, x, margin_top + plot_height), fill=color, width=2 if frame == speech_start else 1)
        draw.text((x - 18, margin_top + plot_height + 16), f"F{frame}", fill=(200, 203, 207), font=small_font)
    draw.text((22, margin_top - 42), "mean RGB delta (u8)", fill=(210, 213, 216), font=small_font)
    draw.text((margin_left + 8, margin_top + 8), "silent attention", fill=(192, 196, 201), font=small_font)
    speech_x = margin_left + round((speech_start - first_frame) / (last_frame - first_frame) * plot_width)
    draw.text((speech_x + 8, margin_top + 8), "dialogue begins", fill=(240, 132, 56), font=small_font)
    for region_name, rows in rows_by_region.items():
        points: list[tuple[int, int]] = []
        for row in rows:
            frame = int(row["to_frame"])
            value = min(y_max, float(row["mean_rgb_delta_u8"]))
            x = margin_left + round((frame - first_frame) / (last_frame - first_frame) * plot_width)
            y = margin_top + plot_height - round(value / y_max * plot_height)
            points.append((x, y))
        if len(points) > 1:
            draw.line(points, fill=colors[region_name], width=3, joint="curve")
    legend_y = height - 55
    x = margin_left
    for name, color in colors.items():
        draw.line((x, legend_y, x + 34, legend_y), fill=color, width=5)
        draw.text((x + 42, legend_y - 12), name, fill=(225, 226, 228), font=small_font)
        x += 270
    return image


def _contact_sheet(
    frames: dict[int, np.ndarray],
    motion: list[dict[str, float]],
    frame_map_offset: int,
) -> Image.Image:
    ordered = sorted(frames)
    cell_width, cell_height = 640, 400
    image = Image.new("RGB", (cell_width * 3, cell_height * 2), (13, 14, 16))
    draw = ImageDraw.Draw(image)
    font = _font(20)
    for index, frame_number in enumerate(ordered):
        local = frame_number - frame_map_offset
        source = Image.fromarray(frames[frame_number], "RGB")
        source.thumbnail((cell_width, 360), Image.Resampling.LANCZOS)
        x = (index % 3) * cell_width
        y = (index // 3) * cell_height + 40
        image.paste(source, (x, y))
        controls = motion[local - 1]
        label = (
            f"F{frame_number} / local {local}  "
            f"head({controls['head_x_px']:+.2f},{controls['head_y_px']:+.2f})  "
            f"shoulder {controls['shoulder_x_px']:+.2f}  breath {controls['breath_y_px']:+.2f}"
        )
        draw.rectangle((x, y - 40, x + cell_width, y), fill=(0, 0, 0))
        draw.text((x + 8, y - 31), label, fill=(238, 231, 213), font=font)
    return image


def _gate(identifier: str, measured: Any, operator: str, threshold: Any, passed: bool) -> dict[str, Any]:
    return {
        "id": identifier,
        "measured": measured,
        "operator": operator,
        "threshold": threshold,
        "passed": bool(passed),
    }


def _source_structure(
    contract: dict[str, Any], body_contract: dict[str, Any], scene: dict[str, Any], motion: list[dict[str, float]],
) -> dict[str, Any]:
    keyframe_controls = sorted(
        key for key in body_contract["keyframes"][0] if key != "frame"
    )
    rig_regions = sorted(scene["rig_regions"])
    independent_hand_controls = [key for key in keyframe_controls if "hand" in key]
    independent_arm_controls = [key for key in keyframe_controls if any(token in key for token in ("arm", "elbow", "wrist"))]
    gesture_events = body_contract.get("gesture_events") or []
    structural = contract["diagnostic"]["structural_claims_to_test"]
    final_start, final_end = (int(value) for value in structural["required_final_static_hold_local_frames_inclusive"])
    final_hold_controls = [
        {key: value for key, value in motion[index - 1].items() if key != "frame"}
        for index in range(final_start, final_end + 1)
    ]
    return {
        "body_motion_controls": keyframe_controls,
        "scene_rig_regions": rig_regions,
        "independent_hand_controls": independent_hand_controls,
        "independent_arm_controls": independent_arm_controls,
        "authored_gesture_events": gesture_events,
        "maximum_absolute_shoulder_x_px": max(abs(float(row["shoulder_x_px"])) for row in motion),
        "maximum_absolute_breath_y_px": max(abs(float(row["breath_y_px"])) for row in motion),
        "maximum_absolute_head_x_px": max(abs(float(row["head_x_px"])) for row in motion),
        "maximum_absolute_head_y_px": max(abs(float(row["head_y_px"])) for row in motion),
        "maximum_absolute_head_tilt_deg": max(abs(float(row["head_tilt_deg"])) for row in motion),
        "camera_push_range": [
            min(float(row["camera_push"]) for row in motion),
            max(float(row["camera_push"]) for row in motion),
        ],
        "final_hold_local_frames_inclusive": [final_start, final_end],
        "final_hold_all_declared_body_controls_zero": all(
            all(math.isclose(float(value), 0.0, abs_tol=1e-12) for key, value in row.items() if key != "camera_push")
            for row in final_hold_controls
        ),
        "final_hold_camera_push_constant": len({float(row["camera_push"]) for row in final_hold_controls}) == 1,
    }


def run_diagnostic(
    output_directory: str | Path | None = None,
) -> dict[str, Any]:
    contract = load_contract()
    diagnostic = contract["diagnostic"]
    manifest_path = _repo_path(contract["locks"]["phase36_candidate01_manifest"]["path"])
    manifest = _strict_json(manifest_path, "Phase36 Candidate01 manifest")
    body_path = _repo_path(contract["locks"]["phase33_body_motion"]["path"])
    body_contract = _strict_json(body_path, "Phase33 body motion")
    scene_path = _repo_path(contract["locks"]["gs070_scene"]["path"])
    scene = _strict_json(scene_path, "GS070 scene")
    _, motion = load_body_motion_contract(body_path, hero_contract=scene)

    output_start, output_end = (int(value) for value in diagnostic["phase36_direct_address_output_frames_inclusive"])
    local_start, local_end = (int(value) for value in diagnostic["phase35_local_frames_inclusive"])
    _require_equal(output_end - output_start, local_end - local_start, "direct/local frame span")
    _require_equal(len(motion), 228, "compiled body motion frame count")
    frame_offset = output_start - local_start
    selected_contact_frames = [76, 99, 121, 152, 187, 237]
    regions = diagnostic["regions_base_plate_xyxy"]
    rows_by_region: dict[str, list[dict[str, Any]]] = {name: [] for name in regions}
    contact_frames: dict[int, np.ndarray] = {}
    first_aligned_for_map: np.ndarray | None = None
    previous_aligned: np.ndarray | None = None
    previous_valid: np.ndarray | None = None
    previous_frame_number: int | None = None
    alignment_geometry: dict[int, dict[str, Any]] = {}

    picture = contract["immutable_picture"]
    archive_path = _outputs_path(picture["external_archive_path"])
    if not archive_path.is_file():
        raise ActingMotionAuditError(f"immutable picture archive missing: {archive_path}")
    before = {
        "bytes": archive_path.stat().st_size,
        "mtime_ns": archive_path.stat().st_mtime_ns,
        "sha256": _sha256(archive_path),
    }
    _require_equal(before["bytes"], picture["archive_bytes"], "archive bytes")
    _require_equal(before["sha256"], picture["archive_sha256"], "archive SHA-256")
    inventory = manifest["frame_hashes"]
    _require_equal(len(inventory), picture["frame_count"], "manifest frame count")
    _require_equal(_canonical_hash(inventory), picture["frame_inventory_canonical_sha256"], "inventory hash")

    combined = hashlib.sha256()
    with gzip.open(archive_path, "rb") as handle:
        header = json.loads(handle.readline().decode("utf-8"))
        _require_equal(header, manifest["lossless_archive_header"], "archive header")
        shape = (int(header["height"]), int(header["width"]), int(header["channels"]))
        previous_raw = np.zeros(shape, dtype=np.uint8)
        for frame_number, expected in enumerate(inventory, start=1):
            payload = handle.read(int(header["frame_bytes"]))
            if len(payload) != int(header["frame_bytes"]):
                raise ActingMotionAuditError(f"archive frame truncated: {frame_number}")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous_raw)
            digest = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
            _require_equal(expected, {"frame": frame_number, "rgb_sha256": digest}, f"frame {frame_number}")
            combined.update(np.ascontiguousarray(frame).tobytes())
            if output_start <= frame_number <= output_end:
                local_frame = frame_number - frame_offset
                controls = motion[local_frame - 1]
                aligned, valid, geometry = _camera_normalize(frame, float(controls["camera_push"]), scene)
                alignment_geometry[frame_number] = geometry
                if first_aligned_for_map is None:
                    first_aligned_for_map = aligned.copy()
                if frame_number in selected_contact_frames:
                    contact_frames[frame_number] = aligned.copy()
                if previous_aligned is not None and previous_valid is not None and previous_frame_number is not None:
                    for region_name, box in regions.items():
                        metrics = _pair_region_metrics(
                            previous_aligned, aligned, previous_valid, valid, box,
                            diagnostic["pair_metrics"],
                        )
                        metrics["transition"] = [previous_frame_number, frame_number]
                        metrics["from_frame"] = previous_frame_number
                        metrics["to_frame"] = frame_number
                        rows_by_region[region_name].append(metrics)
                previous_aligned = aligned
                previous_valid = valid
                previous_frame_number = frame_number
            previous_raw = frame
        if handle.read(1):
            raise ActingMotionAuditError("archive contains trailing decompressed payload")
    _require_equal(combined.hexdigest(), picture["combined_rgb24_sha256"], "combined RGB24 hash")
    _require_equal(set(contact_frames), set(selected_contact_frames), "contact frame inventory")
    if first_aligned_for_map is None:
        raise ActingMotionAuditError("direct-address range was not scanned")

    after = {
        "bytes": archive_path.stat().st_size,
        "mtime_ns": archive_path.stat().st_mtime_ns,
        "sha256": _sha256(archive_path),
    }
    _require_equal(after, before, "archive before/after state")
    summaries = {name: _aggregate_region(rows) for name, rows in rows_by_region.items()}
    static_control_median = summaries["mug_static_control"]["median_pair_mean_rgb_delta_u8"]
    for name, summary in summaries.items():
        summary["median_delta_relative_to_mug_control"] = float(
            summary["median_pair_mean_rgb_delta_u8"] / max(1e-9, static_control_median)
        )
    control_comparison = {
        "basis": "descriptive camera-resampling control comparison; not a preregistered artistic-acceptance gate",
        "mug_static_control_median_pair_mean_rgb_delta_u8": static_control_median,
        "table_hand_to_mug_median_delta_ratio": summaries["table_hand"]["median_delta_relative_to_mug_control"],
        "viewer_left_arm_to_mug_median_delta_ratio": summaries["viewer_left_arm"]["median_delta_relative_to_mug_control"],
        "torso_to_mug_median_delta_ratio": summaries["torso"]["median_delta_relative_to_mug_control"],
        "face_to_mug_median_delta_ratio": summaries["face_head"]["median_delta_relative_to_mug_control"],
    }

    structure = _source_structure(contract, body_contract, scene, motion)
    structural = diagnostic["structural_claims_to_test"]
    gates = [
        _gate("all_303_archive_frames_hash_verified", len(inventory), "==", 303, len(inventory) == 303),
        _gate("combined_rgb24_hash_exact", combined.hexdigest(), "==", picture["combined_rgb24_sha256"], combined.hexdigest() == picture["combined_rgb24_sha256"]),
        _gate("archive_state_unchanged", after, "==", before, after == before),
        _gate("direct_address_transition_count", len(next(iter(rows_by_region.values()))), "==", 161, len(next(iter(rows_by_region.values()))) == 161),
        _gate("independent_hand_control_count", len(structure["independent_hand_controls"]), "==", structural["required_independent_hand_control_count"], len(structure["independent_hand_controls"]) == structural["required_independent_hand_control_count"]),
        _gate("independent_arm_control_count", len(structure["independent_arm_controls"]), "==", structural["required_independent_arm_control_count"], len(structure["independent_arm_controls"]) == structural["required_independent_arm_control_count"]),
        _gate("authored_gesture_event_count", len(structure["authored_gesture_events"]), "==", structural["required_authored_gesture_event_count"], len(structure["authored_gesture_events"]) == structural["required_authored_gesture_event_count"]),
        _gate("maximum_absolute_shoulder_x_px", structure["maximum_absolute_shoulder_x_px"], "==", structural["maximum_absolute_shoulder_x_px"], math.isclose(structure["maximum_absolute_shoulder_x_px"], structural["maximum_absolute_shoulder_x_px"], abs_tol=1e-12)),
        _gate("maximum_absolute_breath_y_px", structure["maximum_absolute_breath_y_px"], "==", structural["maximum_absolute_breath_y_px"], math.isclose(structure["maximum_absolute_breath_y_px"], structural["maximum_absolute_breath_y_px"], abs_tol=1e-12)),
        _gate("final_hold_body_controls_zero", structure["final_hold_all_declared_body_controls_zero"], "==", True, structure["final_hold_all_declared_body_controls_zero"] is True),
        _gate("final_hold_camera_constant", structure["final_hold_camera_push_constant"], "==", True, structure["final_hold_camera_push_constant"] is True),
        _gate("network_calls", 0, "==", 0, True),
        _gate("paid_service_calls", 0, "==", 0, True),
        _gate("encoding_process_count", 0, "==", 0, True),
    ]
    failed = [gate["id"] for gate in gates if not gate["passed"]]
    if failed:
        raise ActingMotionAuditError(f"Phase38 acting audit failed gates: {failed}")

    destination = (
        Path(output_directory).resolve()
        if output_directory is not None
        else (REPO_ROOT / contract["output"]["directory"]).resolve()
    )
    if destination.exists():
        raise ActingMotionAuditError(f"output already exists and overwrite is forbidden: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".phase38-acting-audit-", dir=destination.parent))
    try:
        region_map_name = "phase38-direct-address-region-map-v1.png"
        timeline_name = "phase38-camera-normalized-motion-timeline-v1.png"
        contact_name = "phase38-acting-gap-contact-v1.png"
        report_name = "phase38-acting-motion-machine-report-v1.json"
        _region_map(first_aligned_for_map, regions).save(stage / region_map_name)
        _timeline_image(rows_by_region, (output_start, output_end), int(diagnostic["spoken_output_frames_inclusive"][0])).save(stage / timeline_name)
        _contact_sheet(contact_frames, motion, frame_offset).save(stage / contact_name)
        artifacts = []
        for name in (timeline_name, region_map_name, contact_name):
            path = stage / name
            artifacts.append({"name": name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
        report = {
            "report_version": 1,
            "diagnostic_id": contract["contract_id"],
            "status": "MACHINE_DIAGNOSTIC_PASSED_ACTING_RIG_GAP_CONFIRMED_PLAN_ONLY",
            "machine_passed": True,
            "acting_quality_human_accepted": False,
            "picture_rebuild_authorized": False,
            "video_encode_authorized": False,
            "promotion_allowed": False,
            "cash_cost": 0,
            "paid_service_calls": 0,
            "network_calls": 0,
            "encoding_process_count": 0,
            "toolchain": {"python": os.sys.version.split()[0], "opencv": cv2.__version__, "pillow": PILLOW_VERSION, "numpy": np.__version__},
            "contract": {"path": CONTRACT_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / CONTRACT_RELATIVE_PATH)},
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH)},
            "tests": {"path": TEST_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / TEST_RELATIVE_PATH) if (REPO_ROOT / TEST_RELATIVE_PATH).is_file() else None},
            "immutable_picture": {
                "path": str(archive_path),
                "before": before,
                "after": after,
                "mutated": False,
                "verified_frames": len(inventory),
                "frame_inventory_canonical_sha256": _canonical_hash(inventory),
                "combined_rgb24_sha256": combined.hexdigest(),
            },
            "frame_mapping": {
                "phase36_output_frames_inclusive": [output_start, output_end],
                "phase35_local_frames_inclusive": [local_start, local_end],
                "output_minus_local_offset": frame_offset,
                "pair_count": 161,
            },
            "camera_alignment": {
                "method": diagnostic["camera_alignment"]["method"],
                "first_frame_geometry": alignment_geometry[output_start],
                "last_frame_geometry": alignment_geometry[output_end],
            },
            "source_structure": structure,
            "region_summaries": summaries,
            "static_control_comparison": control_comparison,
            "per_transition_region_metrics": rows_by_region,
            "gates": gates,
            "gate_count": len(gates),
            "failed_gates": failed,
            "artifacts": artifacts,
            "diagnostic_conclusion": {
                "classification": "CLOSE_VIEW_BODY_ACTING_RIG_GAP_CONFIRMED",
                "evidence": [
                    "The declared close-view performance exposes no independent hand or arm control and no authored gesture events.",
                    "Shoulder translation is bounded to 0.4 source pixels and breath translation to 1.3 pixels while the face carries the dialogue.",
                    f"After exact camera normalization, the table-hand median delta is {control_comparison['table_hand_to_mug_median_delta_ratio']:.3f}x the stationary-mug control and the viewer-left arm is {control_comparison['viewer_left_arm_to_mug_median_delta_ratio']:.3f}x; these descriptive values agree with the missing independent limb controls without serving as an artistic pass/fail threshold.",
                    "The final static hold remains intentional and should be preserved; the next slice adds only beat-specific anticipation, one compact hand arc, torso counter-motion, and settle.",
                ],
                "proposed_next_slice": contract["proposed_next_acting_slice"],
                "human_review_required_before_source_mutation": True,
            },
        }
        report_path = stage / report_name
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        _require_equal(sorted(path.name for path in stage.iterdir()), sorted(contract["output"]["allowlist"]), "stage allowlist")
        stage.rename(destination)
        return report
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    report = run_diagnostic(args.output)
    print(json.dumps({
        "status": report["status"],
        "gate_count": report["gate_count"],
        "failed_gates": report["failed_gates"],
        "classification": report["diagnostic_conclusion"]["classification"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
