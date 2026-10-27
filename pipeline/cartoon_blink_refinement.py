"""Small blink-timing/shape audition from James's near-pass feedback.

The eye-only study uses a locked head/camera pose and the 7.6-second scene
clock, not a half-second endlessly repeating blink. It never renders the full
scene. The near-pass closed-eye artwork and prior evidence remain unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_continuous_blink as continuous
from pipeline import cartoon_repaired_acting as integration


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-blink-refinement-v3"
BASE_MASKS = continuous.lid_alpha_masks
FRAME_COUNT = 228
FOCUS_FRAME = 173
CURVE_START = 167


def _ease(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def candidate_closure(frame: int) -> float:
    index = frame - CURVE_START
    if not 0 <= index <= 12:
        return 0.0
    if index <= 5:
        return _ease(index / 5.0)
    if index == 6:
        return 1.0
    return _ease((12 - index) / 6.0)


def curved_masks(shape: tuple[int, int], center: tuple[int, int], radius: tuple[int, int], closure: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    upper, lower, crease = BASE_MASKS(shape, center, radius, closure)
    if closure == 0.0 or closure == 1.0:
        return upper, lower, crease
    full_upper, full_lower, _ = BASE_MASKS(shape, center, radius, 1.0)
    socket = np.maximum(full_upper, full_lower)
    cx, cy = center
    rx, ry = radius
    x1, y1, x2, y2 = cx - rx - 5, cy - ry - 12, cx + rx + 6, cy + ry + 12
    local_socket = socket[y1:y2, x1:x2].astype(np.float64)
    yy, xx = np.indices(local_socket.shape, dtype=np.float64)
    normalized_x = np.clip((xx - (cx - x1)) / rx, -1.0, 1.0)
    # At most one source pixel at the center/corners: a subtle arch, not a
    # replacement eye design. Fade it out at both exact endpoints.
    arc = 2.0 * math.sin(math.pi * closure) * (normalized_x**2 - 0.5)
    local_cy = cy - y1
    meeting_y = local_cy + 0.30 * ry
    upper_start, lower_start = local_cy - ry - 9.0, local_cy + ry + 9.0
    upper_edge = upper_start + closure * (meeting_y + 3.0 - upper_start) + arc
    lower_edge = lower_start - closure * (lower_start - (meeting_y - 3.0)) - arc
    # Curve the analytic moving margins, not the already quantized masks.
    # Remapping quantized coverage caused tiny backwards opacity steps in the
    # first experiment; this formulation keeps coverage monotone and the
    # original socket feather completely fixed.
    coverages = (
        np.clip(upper_edge - yy + 0.5, 0, 1),
        np.clip(yy - lower_edge + 0.5, 0, 1),
    )
    for output, coverage in zip((upper, lower), coverages):
        softened = cv2.GaussianBlur(coverage, (0, 0), sigmaX=0.7, sigmaY=0.7)
        output[y1:y2, x1:x2] = np.rint(softened * local_socket).astype(np.uint8)
    return upper, lower, crease


@contextmanager
def shape_override(enabled: bool) -> Iterator[None]:
    previous = continuous.lid_alpha_masks
    if enabled:
        continuous.lid_alpha_masks = curved_masks
    try:
        yield
    finally:
        continuous.lid_alpha_masks = previous


def _render_crops(prepared: integration.PreparedRepairedActing, closures: list[float], curved: bool) -> tuple[dict[float, Image.Image], dict[str, Any]]:
    direct = prepared.integration.direct
    original_contract = direct.contract
    original_cache = direct.native_cache.copy()
    direct.contract = deepcopy(original_contract)
    direct.contract["performance"]["blink_curves"] = [{"id": "fixed_pose_shape_audition", "frames": [FOCUS_FRAME], "closures": [0.0]}]
    images = {}
    hashes = {}
    try:
        with integration.registered_lids(prepared), shape_override(curved):
            for closure in sorted(set(closures)):
                direct.native_cache.clear()
                direct.contract["performance"]["blink_curves"][0]["closures"][0] = closure
                source, _, evidence = integration.acting.phase35.compose_direct_address_frame(direct, FOCUS_FRAME)
                delivered, transform = integration.eyes.v4.v3.phase36.compassion_camera(np.asarray(source, dtype=np.uint8), prepared.camera, FOCUS_FRAME)
                eye = transform["transformed_eye_roi_xyxy"]
                box = (eye[0] - 16, eye[1] - 16, eye[2] + 16, eye[3] + 16)
                images[closure] = Image.fromarray(delivered).crop(box)
                hashes[str(closure)] = {"full_frame_rgb_sha256": integration.acting._rgb_hash(delivered), "native_outside_feature_support": evidence.changed_outside_support, "depth_order_violations": evidence.depth_order_violation_pixels}
    finally:
        direct.contract = original_contract
        direct.native_cache.clear()
        direct.native_cache.update(original_cache)
    return images, hashes


def _rle_timeline(frames: list[Image.Image]) -> tuple[list[Image.Image], list[int]]:
    boundaries = [round(index * 1000 / 30) for index in range(len(frames) + 1)]
    result, durations = [], []
    prior = None
    for index, frame in enumerate(frames):
        key = hashlib.sha256(frame.tobytes()).digest()
        duration = boundaries[index + 1] - boundaries[index]
        if key == prior:
            durations[-1] += duration
        else:
            result.append(frame)
            durations.append(duration)
            prior = key
    return result, durations


def build(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite blink audition: {output}")
    prepared = integration.prepare_repaired_acting()
    original_schedule = [integration.acting.phase35.production_blink_closure(prepared.integration.direct.contract, frame) for frame in range(1, FRAME_COUNT + 1)]
    schedule = [candidate_closure(frame) for frame in range(1, FRAME_COUNT + 1)]
    original, original_hashes = _render_crops(prepared, original_schedule, False)
    candidate, candidate_hashes = _render_crops(prepared, schedule, True)
    if original_hashes["1.0"]["full_frame_rgb_sha256"] != candidate_hashes["1.0"]["full_frame_rgb_sha256"]:
        raise ValueError("near-pass full-close artwork changed")
    if original[0.0].tobytes() != candidate[0.0].tobytes():
        raise ValueError("open eyes changed")
    if any(row["native_outside_feature_support"] or row["depth_order_violations"] for row in candidate_hashes.values()):
        raise ValueError("refined eye masks escaped support or depth order")
    font = integration.eyes._font(16)
    width, height = candidate[0.0].size
    pair_frames, single_frames = [], []
    for old_value, new_value in zip(original_schedule, schedule):
        pair = Image.new("RGB", (width * 2, height + 28), (14, 11, 9))
        pair.paste(original[old_value], (0, 28))
        pair.paste(candidate[new_value], (width, 28))
        draw = ImageDraw.Draw(pair)
        draw.text((8, 5), "Previous: 2 blinks / scene clock", font=font, fill=(245, 227, 197))
        draw.text((width + 8, 5), "Refined: slower / 1 blink / mild curve", font=font, fill=(245, 227, 197))
        pair_frames.append(pair)
        single_frames.append(candidate[new_value])
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase42-blink-v3-", dir=output.parent) as temporary:
        stage = Path(temporary)
        for name, timeline in (("comparison", pair_frames), ("refined", single_frames)):
            frames, durations = _rle_timeline(timeline)
            frames[0].save(stage / f"phase42-blink-{name}-real-cadence-v3.webp", save_all=True, append_images=frames[1:], duration=durations, loop=0, lossless=True, method=3)
        sheet = Image.new("RGB", (width * 4, height * 4 + 28), (14, 11, 9))
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 5), "Refined blink: closed art unchanged; intermediate margin gently curved", font=font, fill=(245, 227, 197))
        for index, frame in enumerate(range(CURVE_START, CURVE_START + 13)):
            crop = candidate[candidate_closure(frame)]
            sheet.paste(crop, ((index % 4) * width, (index // 4) * height + 28))
        sheet.save(stage / "phase42-blink-refined-neighbors-v3.png")
        report = {
            "report_version": 3, "classification": "LOCKED_HEAD_EYE_ONLY_TIMING_SHAPE_AUDITION",
            "cash_cost": 0, "network_calls": 0, "video_encoder_processes": 0, "full_scene_rendered": False,
            "locked_head_source_frame": FOCUS_FRAME, "timeline_frames": FRAME_COUNT, "timeline_duration_ms": 7600,
            "reference_blink_count": 2, "candidate_blink_count": 1,
            "candidate_curve_source_frames": list(range(CURVE_START, CURVE_START + 13)),
            "candidate_closures": [candidate_closure(frame) for frame in range(CURVE_START, CURVE_START + 13)],
            "candidate_control_span_ms": 400, "reference_control_span_ms": 267,
            "candidate_native_full_close_hold_frames": 2, "maximum_shape_offset_native_px": 1.0,
            "original_render_hashes": original_hashes, "candidate_render_hashes": candidate_hashes,
            "implementation_sha256": integration._sha256(Path(__file__)),
            "artifacts": {path.name: {"sha256": integration._sha256(path), "bytes": path.stat().st_size} for path in sorted(stage.iterdir())},
            "human_accepted": False, "promotion_allowed": False,
            "note": "Real scene-duration cadence on a fixed head/camera pose; not a full scene or proof of sustained acting. Full-close source artwork is unchanged.",
        }
        (stage / "phase42-blink-refinement-report-v3.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        shutil.move(str(stage), str(output))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    report = build(parser.parse_args().output)
    print(json.dumps({"artifacts": report["artifacts"], "duration_ms": 7600, "human_accepted": False}, indent=2))


if __name__ == "__main__":
    main()
