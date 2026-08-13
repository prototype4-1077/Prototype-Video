"""Phase40: integrate Phase39 body acting with the accepted direct-address stack.

This is an unencoded A/B proof.  It reuses the accepted Phase35 facial,
secondary-motion, and camera clock, replaces only the rectangular shoulder
warp while Phase39 has nonzero additive state, and returns exactly to the
baseline compositor once that additive state reaches zero.
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

from pipeline import cartoon_close_body_acting_rig as phase39
from pipeline import cartoon_source_textured_direct_address as phase35
from pipeline.cartoon_hero_scene import _camera_frame, _lantern_glow, _secondary_overlay, _warp_region


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = Path(
    "concept/characters/june_oxley_phase40_synchronized_acting_integration_v1.json"
)
IMPLEMENTATION_RELATIVE_PATH = Path("pipeline/cartoon_synchronized_acting_integration.py")
TEST_RELATIVE_PATH = Path("pipeline/tests/test_cartoon_synchronized_acting_integration.py")


class SynchronizedActingIntegrationError(RuntimeError):
    """Raised when Phase40 cannot satisfy the exact A/B contract."""


@dataclass
class PreparedIntegration:
    contract: dict[str, Any]
    contract_path: Path
    direct: phase35.PreparedDirectAddress
    body: phase39.PreparedRig


@dataclass
class IntegratedFrame:
    frame_number: int
    baseline: np.ndarray
    candidate: np.ndarray
    native_baseline: np.ndarray
    native_candidate: np.ndarray
    native_body_support: np.ndarray
    transformed_body_support: np.ndarray
    transformed_head_support: np.ndarray
    transformed_face_support: np.ndarray
    transformed_mug_support: np.ndarray
    delivery_landmarks: dict[str, tuple[float, float]]
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
    path = (REPO_ROOT / Path(relative)).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SynchronizedActingIntegrationError(f"path escapes repository: {relative}") from exc
    return path


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = _repo_path(reference.get("path", ""))
    if not path.is_file():
        raise SynchronizedActingIntegrationError(f"{label} missing: {path}")
    actual = _sha256(path)
    expected = str(reference.get("sha256", ""))
    if actual != expected:
        raise SynchronizedActingIntegrationError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def _require(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SynchronizedActingIntegrationError(f"{label}: {actual!r} != {expected!r}")


def load_contract(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> tuple[dict[str, Any], Path]:
    source = Path(path).resolve()
    contract = json.loads(source.read_text(encoding="utf-8"))
    _require(contract.get("contract_version"), 1, "contract version")
    _require(contract.get("contract_id"), "june_oxley_phase40_synchronized_acting_integration_v1", "contract id")
    _require(contract.get("cash_cost"), 0, "cash cost")
    _require(contract.get("paid_service_calls_allowed"), 0, "paid services")
    _require(contract.get("network_calls_allowed"), 0, "network calls")
    _require(contract.get("video_encode_allowed"), False, "encode policy")
    _require(contract.get("picture_master_mutation_allowed"), False, "master mutation")
    _require(contract.get("promotion_allowed"), False, "promotion policy")
    _require(contract["clock"]["frame_count"], 228, "frame count")
    _require(contract["clock"]["unchanged_tail_frames_inclusive"], [148, 228], "unchanged tail")
    _require(contract["integration"]["phase39_replaces_existing_rectangular_shoulders_warp"], True, "shoulder replacement")
    _require(contract["integration"]["baseline_is_returned_exactly_when_phase39_additive_state_is_zero"], True, "zero-state baseline policy")
    for label, reference in contract["locks"].items():
        _locked_path(reference, label)
    report = json.loads(_locked_path(contract["locks"]["phase39_report"], "Phase39 report").read_text(encoding="utf-8"))
    _require(report.get("status"), "MACHINE_PROTOTYPE_PASSED_HUMAN_ACTING_REVIEW_REQUIRED", "Phase39 status")
    _require(report.get("machine_passed"), True, "Phase39 machine pass")
    _require(report.get("picture_rebuild_authorized"), False, "Phase39 rebuild authority")
    return contract, source


def prepare_integration(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> PreparedIntegration:
    contract, contract_path = load_contract(path)
    direct = phase35.prepare_direct_address(_locked_path(contract["locks"]["phase35_contract"], "Phase35 contract"))
    body = phase39.prepare_rig(_locked_path(contract["locks"]["phase39_contract"], "Phase39 contract"))
    _require(len(direct.visemes), contract["quality_gates"]["required_existing_viseme_clock_frames"], "viseme clock")
    _require(len(direct.expressions), contract["quality_gates"]["required_existing_expression_clock_frames"], "expression clock")
    _require(len(direct.motion), contract["quality_gates"]["required_existing_motion_clock_frames"], "motion clock")
    _require(body.plate.shape, direct.face.plate.shape, "Phase39/Phase35 plate shape")
    if not np.array_equal(body.plate, direct.face.plate):
        raise SynchronizedActingIntegrationError("Phase39 and Phase35 plate pixels differ")
    return PreparedIntegration(contract, contract_path, direct, body)


def _state_nonzero(state: dict[str, float]) -> bool:
    return any(abs(float(value)) > 1e-12 for value in state.values())


def _body_state(prepared: PreparedIntegration, frame_number: int) -> dict[str, float]:
    if 1 <= int(frame_number) <= len(prepared.body.states):
        return prepared.body.states[int(frame_number) - 1]
    return {channel: 0.0 for channel in prepared.body.contract["motion_channels"]}


def _body_field(
    prepared: PreparedIntegration,
    frame_number: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, tuple[float, float]]]:
    state = _body_state(prepared, frame_number)
    offsets = phase39._region_offsets(prepared.body, state)
    landmarks = phase39._landmarks(prepared.body, offsets)
    if not _state_nonzero(state):
        empty = np.zeros(prepared.body.plate.shape[:2], dtype=bool)
        return np.zeros((*empty.shape, 2), dtype=np.float32), empty, landmarks
    displacement = phase39._compose_displacement(prepared.body, offsets)
    support = np.linalg.norm(displacement, axis=2) > 1e-5
    guard = int(prepared.body.contract["deformation"]["prospective_kernel_guard_px"])
    if guard > 0 and np.any(support):
        kernel = np.ones((2 * guard + 1, 2 * guard + 1), dtype=np.uint8)
        support = cv2.dilate(support.astype(np.uint8), kernel, iterations=1) > 0
    return displacement, support, landmarks


def _compose_no_shoulders_native(
    prepared: PreparedIntegration,
    frame_number: int,
) -> Image.Image:
    direct = prepared.direct
    index = int(frame_number) - 1
    closure = phase35.production_blink_closure(direct.contract, frame_number)
    facial_native, _ = phase35.controlled_native_frame(direct, direct.visemes[index], closure)
    face = direct.face
    frame = Image.fromarray(face.plate, "RGB")
    feature_mask = Image.fromarray(face.feature_support.astype(np.uint8) * 255, "L")
    frame.paste(Image.fromarray(facial_native, "RGB"), (0, 0), feature_mask)
    motion = direct.motion[index]
    regions = direct.scene_contract["rig_regions"]
    secondary = direct.motion_metadata["secondary_motion"]
    chime = secondary.get("wind_chime") or {}
    period = max(0.5, float(chime.get("period_seconds", 3.1)))
    chime_dx = float(chime.get("amplitude_px", 0.0)) * math.sin(
        frame_number / 30 / period * math.tau + float(chime.get("phase", 0.0))
    )
    _warp_region(frame, regions["wind_chime"], dx=chime_dx, rotation_deg=chime_dx * 0.10)
    _warp_region(
        frame,
        regions["head"],
        dx=float(motion["head_x_px"]),
        dy=float(motion["head_y_px"]),
        rotation_deg=float(motion["head_tilt_deg"]),
    )
    lantern = secondary.get("lantern") or {}
    lantern_period = max(0.2, float(lantern.get("period_seconds", 0.71)))
    glow = float(lantern.get("flicker_strength", 0.0)) * (
        0.55
        + 0.45
        * math.sin(frame_number / 30 / lantern_period * math.tau + float(lantern.get("phase", 0.0)))
    )
    _lantern_glow(frame, regions["lantern"], max(0.0, glow))
    _secondary_overlay(frame, frame_number, 30, regions, secondary)
    return frame


def _native_body_face_preview(
    prepared: PreparedIntegration,
    frame_number: int,
) -> np.ndarray:
    direct = prepared.direct
    state = _body_state(prepared, frame_number)
    if _state_nonzero(state):
        body = phase39.render_frame(prepared.body, frame_number).image
    else:
        body = prepared.body.plate.copy()
    closure = phase35.production_blink_closure(direct.contract, frame_number)
    facial, _ = phase35.controlled_native_frame(
        direct,
        direct.visemes[frame_number - 1],
        closure,
    )
    result = body.copy()
    result[direct.face.feature_support] = facial[direct.face.feature_support]
    return result


def _source_rect_mask(shape: tuple[int, int], box: list[int]) -> np.ndarray:
    left, top, right, bottom = (int(value) for value in box)
    result = np.zeros(shape, dtype=bool)
    result[top:bottom, left:right] = True
    return result


def _camera_geometry(prepared: PreparedIntegration, frame_number: int) -> tuple[float, int, int]:
    scene = prepared.direct.scene_contract
    output = scene["output"]
    source_height, source_width = prepared.body.plate.shape[:2]
    push = float(prepared.direct.motion[frame_number - 1]["camera_push"])
    scale = max(int(output["width"]) / source_width, int(output["height"]) / source_height) * (1.0 + push)
    resized_width = round(source_width * scale)
    resized_height = round(source_height * scale)
    extra_x = resized_width - int(output["width"])
    extra_y = resized_height - int(output["height"])
    anchor_x, anchor_y = (float(value) for value in scene["rig_regions"]["camera_anchor"])
    left = round(max(0.0, min(float(extra_x), extra_x * anchor_x)))
    top = round(max(0.0, min(float(extra_y), extra_y * anchor_y)))
    return scale, left, top


def _fused_body_camera_sample(
    prepared: PreparedIntegration,
    frame_number: int,
    no_shoulders_native: Image.Image,
    displacement: np.ndarray,
) -> np.ndarray:
    output = prepared.direct.scene_contract["output"]
    output_width, output_height = int(output["width"]), int(output["height"])
    scale, left, top = _camera_geometry(prepared, frame_number)
    yy, xx = np.mgrid[0:output_height, 0:output_width].astype(np.float32)
    source_x = (xx + float(left)) / float(scale)
    source_y = (yy + float(top)) / float(scale)
    dx = cv2.remap(displacement[:, :, 0], source_x, source_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    dy = cv2.remap(displacement[:, :, 1], source_x, source_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    map_x = source_x - dx
    map_y = source_y - dy
    return cv2.remap(
        np.asarray(no_shoulders_native, dtype=np.uint8),
        map_x,
        map_y,
        cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def _fused_body_delta(
    prepared: PreparedIntegration,
    frame_number: int,
    source_plate: Image.Image,
    displacement: np.ndarray,
) -> np.ndarray:
    plate_delivery = np.asarray(
        _camera_frame(
            source_plate,
            float(prepared.direct.motion[frame_number - 1]["camera_push"]),
            prepared.direct.scene_contract,
        ),
        dtype=np.uint8,
    )
    fused = _fused_body_camera_sample(prepared, frame_number, source_plate, displacement)
    return fused.astype(np.int16) - plate_delivery.astype(np.int16)


def _transform_mask(
    mask: np.ndarray,
    prepared: PreparedIntegration,
    frame_number: int,
    *,
    follow_head: bool = False,
) -> np.ndarray:
    image = Image.fromarray(np.repeat(mask.astype(np.uint8)[:, :, None] * 255, 3, axis=2), "RGB")
    motion = prepared.direct.motion[frame_number - 1]
    if follow_head:
        _warp_region(
            image,
            prepared.direct.scene_contract["rig_regions"]["head"],
            dx=float(motion["head_x_px"]),
            dy=float(motion["head_y_px"]),
            rotation_deg=float(motion["head_tilt_deg"]),
        )
    transformed = _camera_frame(image, float(motion["camera_push"]), prepared.direct.scene_contract)
    return np.any(np.asarray(transformed, dtype=np.uint8) > 0, axis=2)


def _transform_landmarks(
    prepared: PreparedIntegration,
    frame_number: int,
    landmarks: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    scale, left, top = _camera_geometry(prepared, frame_number)
    return {
        name: (float(point[0]) * scale - left, float(point[1]) * scale - top)
        for name, point in landmarks.items()
    }


def compose_integrated_frame(prepared: PreparedIntegration, frame_number: int) -> IntegratedFrame:
    if not 1 <= int(frame_number) <= int(prepared.contract["clock"]["frame_count"]):
        raise SynchronizedActingIntegrationError(f"frame outside F001-F228: {frame_number}")
    baseline_image, baseline_native, _ = phase35.compose_direct_address_frame(prepared.direct, frame_number)
    baseline = np.asarray(baseline_image, dtype=np.uint8)
    state = _body_state(prepared, frame_number)
    if not _state_nonzero(state):
        candidate = baseline.copy()
        native_candidate = baseline_native.copy()
        empty = np.zeros(baseline.shape[:2], dtype=bool)
        native_empty = np.zeros(prepared.body.plate.shape[:2], dtype=bool)
        offsets = phase39._region_offsets(prepared.body, state)
        delivery_landmarks = _transform_landmarks(prepared, frame_number, phase39._landmarks(prepared.body, offsets))
        return IntegratedFrame(
            frame_number,
            baseline,
            candidate,
            baseline_native,
            native_candidate,
            native_empty,
            empty,
            empty,
            empty,
            empty,
            delivery_landmarks,
            {
                "baseline_rgb_sha256": _rgb_hash(baseline),
                "candidate_rgb_sha256": _rgb_hash(candidate),
                "changed_pixel_count": 0,
                "changed_pixels_outside_transformed_phase39_support": 0,
                "changed_pixels_in_transformed_head_support": 0,
                "changed_pixels_in_transformed_face_feature_support": 0,
                "changed_pixels_in_transformed_mug_support": 0,
                "mean_rgb_delta": 0.0,
                "state_nonzero": False,
            },
        )
    displacement, native_support, landmarks = _body_field(prepared, frame_number)
    no_shoulders_native = _compose_no_shoulders_native(prepared, frame_number)
    no_shoulders_delivery = np.asarray(
        _camera_frame(
            no_shoulders_native,
            float(prepared.direct.motion[frame_number - 1]["camera_push"]),
            prepared.direct.scene_contract,
        ),
        dtype=np.uint8,
    )
    transformed_body_support = _transform_mask(native_support, prepared, frame_number)
    guard = int(prepared.body.contract["deformation"]["prospective_kernel_guard_px"])
    if guard > 0 and np.any(transformed_body_support):
        kernel = np.ones((2 * guard + 1, 2 * guard + 1), dtype=np.uint8)
        transformed_body_support = cv2.dilate(transformed_body_support.astype(np.uint8), kernel, iterations=1) > 0
    old_shoulders_native = _source_rect_mask(
        prepared.body.plate.shape[:2],
        prepared.direct.scene_contract["rig_regions"]["shoulders"],
    )
    old_shoulders_support = _transform_mask(old_shoulders_native, prepared, frame_number)
    transformed_support = transformed_body_support | old_shoulders_support
    transformed_head = _transform_mask(prepared.body.protected["face_head"], prepared, frame_number, follow_head=True)
    transformed_face = _transform_mask(prepared.direct.face.feature_support, prepared, frame_number, follow_head=True)
    transformed_mug = _transform_mask(prepared.body.protected["mug"], prepared, frame_number)
    allowed_replacement = transformed_support & ~transformed_head & ~transformed_mug
    allowed_body = transformed_body_support & ~transformed_head & ~transformed_mug
    delta = _fused_body_delta(
        prepared,
        frame_number,
        Image.fromarray(prepared.body.plate, "RGB"),
        displacement,
    )
    candidate = baseline.copy()
    candidate[allowed_replacement] = no_shoulders_delivery[allowed_replacement]
    working = candidate.astype(np.int16)
    working[allowed_body] += delta[allowed_body]
    candidate = np.clip(working, 0, 255).astype(np.uint8)
    changed = np.any(candidate != baseline, axis=2)
    metrics = {
        "baseline_rgb_sha256": _rgb_hash(baseline),
        "candidate_rgb_sha256": _rgb_hash(candidate),
        "changed_pixel_count": int(np.count_nonzero(changed)),
        "changed_pixels_outside_transformed_phase39_support": int(np.count_nonzero(changed & ~transformed_support)),
        "changed_pixels_in_transformed_head_support": int(np.count_nonzero(changed & transformed_head)),
        "changed_pixels_in_transformed_face_feature_support": int(np.count_nonzero(changed & transformed_face)),
        "changed_pixels_in_transformed_mug_support": int(np.count_nonzero(changed & transformed_mug)),
        "mean_rgb_delta": float(np.mean(np.abs(candidate.astype(np.int16) - baseline.astype(np.int16)))),
        "state_nonzero": True,
    }
    return IntegratedFrame(
        frame_number,
        baseline,
        candidate,
        baseline_native,
        _native_body_face_preview(prepared, frame_number),
        native_support,
        transformed_support,
        transformed_head,
        transformed_face,
        transformed_mug,
        _transform_landmarks(prepared, frame_number, landmarks),
        metrics,
    )


def _gate(identifier: str, actual: Any, comparator: str, expected: Any, passed: bool) -> dict[str, Any]:
    return {"id": identifier, "actual": actual, "comparator": comparator, "expected": expected, "passed": bool(passed)}


def _measure(prepared: PreparedIntegration) -> tuple[dict[str, Any], dict[int, IntegratedFrame]]:
    retain = set(int(value) for value in prepared.contract["review_frames"])
    retain.update({23, 25, 49, 51, 65, 67, 71, 73, 81, 83, 97, 99, 109, 111, 114, 116, 125, 127, 147})
    retained: dict[int, IntegratedFrame] = {}
    candidate_hashes: list[str] = []
    baseline_hashes: list[str] = []
    changed_frames: list[int] = []
    maximum_outside = 0
    maximum_head = 0
    maximum_face = 0
    maximum_mug = 0
    mean_deltas: list[float] = []
    landmark_tracks: dict[str, list[list[float]]] = {}
    maximum_step = 0.0
    maximum_step_name = ""
    maximum_step_frame = 0
    previous_landmarks: dict[str, tuple[float, float]] | None = None
    for frame_number in range(1, int(prepared.contract["clock"]["frame_count"]) + 1):
        frame = compose_integrated_frame(prepared, frame_number)
        baseline_hashes.append(frame.metrics["baseline_rgb_sha256"])
        candidate_hashes.append(frame.metrics["candidate_rgb_sha256"])
        mean_deltas.append(float(frame.metrics["mean_rgb_delta"]))
        if frame.metrics["changed_pixel_count"] > 0:
            changed_frames.append(frame_number)
        maximum_outside = max(maximum_outside, int(frame.metrics["changed_pixels_outside_transformed_phase39_support"]))
        maximum_head = max(maximum_head, int(frame.metrics["changed_pixels_in_transformed_head_support"]))
        maximum_face = max(maximum_face, int(frame.metrics["changed_pixels_in_transformed_face_feature_support"]))
        maximum_mug = max(maximum_mug, int(frame.metrics["changed_pixels_in_transformed_mug_support"]))
        for name in (
            "torso.sternum",
            "viewer_left_arm.elbow",
            "table_hand.palm",
            "table_hand.index_tip",
            "table_hand.pinky_tip",
        ):
            landmark_tracks.setdefault(name, []).append(list(map(float, frame.delivery_landmarks[name])))
        if previous_landmarks is not None:
            for name, point in frame.delivery_landmarks.items():
                step = float(np.linalg.norm(np.asarray(point) - np.asarray(previous_landmarks[name])))
                if step > maximum_step:
                    maximum_step = step
                    maximum_step_name = name
                    maximum_step_frame = frame_number
        previous_landmarks = frame.delivery_landmarks
        if frame_number in retain:
            retained[frame_number] = frame
    tail_start, tail_end = prepared.contract["clock"]["unchanged_tail_frames_inclusive"]
    tail_identical = sum(
        baseline_hashes[index - 1] == candidate_hashes[index - 1]
        for index in range(int(tail_start), int(tail_end) + 1)
    )
    return {
        "frame_count": len(candidate_hashes),
        "baseline_combined_rgb_sha256": hashlib.sha256("".join(baseline_hashes).encode("ascii")).hexdigest(),
        "candidate_combined_rgb_sha256": hashlib.sha256("".join(candidate_hashes).encode("ascii")).hexdigest(),
        "changed_frame_count": len(changed_frames),
        "changed_frames": changed_frames,
        "maximum_changed_pixels_outside_transformed_phase39_support": maximum_outside,
        "maximum_changed_pixels_in_transformed_head_support": maximum_head,
        "maximum_changed_pixels_in_transformed_face_feature_support": maximum_face,
        "maximum_changed_pixels_in_transformed_mug_support": maximum_mug,
        "maximum_adjacent_delivery_landmark_step_px": maximum_step,
        "maximum_adjacent_delivery_landmark_step_landmark": maximum_step_name,
        "maximum_adjacent_delivery_landmark_step_frame": maximum_step_frame,
        "maximum_mean_rgb_delta": max(mean_deltas),
        "maximum_mean_rgb_delta_frame": int(np.argmax(mean_deltas)) + 1,
        "handoff_frame_148_mean_rgb_delta": mean_deltas[147],
        "tail_identical_frame_count": tail_identical,
        "landmark_tracks": landmark_tracks,
        "baseline_frame_hashes": baseline_hashes,
        "candidate_frame_hashes": candidate_hashes,
    }, retained


def _gates(prepared: PreparedIntegration, metrics: dict[str, Any]) -> list[dict[str, Any]]:
    quality = prepared.contract["quality_gates"]
    return [
        _gate("frame_count", metrics["frame_count"], "==", quality["required_frame_count"], metrics["frame_count"] == quality["required_frame_count"]),
        _gate("changed_pixels_outside_transformed_phase39_support", metrics["maximum_changed_pixels_outside_transformed_phase39_support"], "==", quality["maximum_changed_pixels_outside_transformed_phase39_support"], metrics["maximum_changed_pixels_outside_transformed_phase39_support"] == quality["maximum_changed_pixels_outside_transformed_phase39_support"]),
        _gate("transformed_head_support_preserved", metrics["maximum_changed_pixels_in_transformed_head_support"], "==", quality["maximum_changed_pixels_in_transformed_head_support"], metrics["maximum_changed_pixels_in_transformed_head_support"] == quality["maximum_changed_pixels_in_transformed_head_support"]),
        _gate("transformed_face_feature_support_preserved", metrics["maximum_changed_pixels_in_transformed_face_feature_support"], "==", quality["maximum_changed_pixels_in_transformed_face_feature_support"], metrics["maximum_changed_pixels_in_transformed_face_feature_support"] == quality["maximum_changed_pixels_in_transformed_face_feature_support"]),
        _gate("transformed_mug_support_preserved", metrics["maximum_changed_pixels_in_transformed_mug_support"], "==", quality["maximum_changed_pixels_in_transformed_mug_support"], metrics["maximum_changed_pixels_in_transformed_mug_support"] == quality["maximum_changed_pixels_in_transformed_mug_support"]),
        _gate("tail_identical_frame_count", metrics["tail_identical_frame_count"], "==", quality["required_tail_identical_frame_count"], metrics["tail_identical_frame_count"] == quality["required_tail_identical_frame_count"]),
        _gate("changed_frame_count_minimum", metrics["changed_frame_count"], ">=", quality["required_changed_frame_count_minimum"], metrics["changed_frame_count"] >= quality["required_changed_frame_count_minimum"]),
        _gate("changed_frame_count_maximum", metrics["changed_frame_count"], "<=", quality["required_changed_frame_count_maximum"], metrics["changed_frame_count"] <= quality["required_changed_frame_count_maximum"]),
        _gate("maximum_adjacent_delivery_landmark_step_px", metrics["maximum_adjacent_delivery_landmark_step_px"], "<=", quality["maximum_adjacent_delivery_landmark_step_px"], metrics["maximum_adjacent_delivery_landmark_step_px"] <= quality["maximum_adjacent_delivery_landmark_step_px"]),
        _gate("handoff_frame_148_rgb_delta", metrics["handoff_frame_148_mean_rgb_delta"], "==", quality["required_handoff_frame_148_rgb_delta"], math.isclose(metrics["handoff_frame_148_mean_rgb_delta"], quality["required_handoff_frame_148_rgb_delta"], abs_tol=1e-12)),
        _gate("viseme_clock_frames", len(prepared.direct.visemes), "==", quality["required_existing_viseme_clock_frames"], len(prepared.direct.visemes) == quality["required_existing_viseme_clock_frames"]),
        _gate("expression_clock_frames", len(prepared.direct.expressions), "==", quality["required_existing_expression_clock_frames"], len(prepared.direct.expressions) == quality["required_existing_expression_clock_frames"]),
        _gate("body_motion_clock_frames", len(prepared.direct.motion), "==", quality["required_existing_motion_clock_frames"], len(prepared.direct.motion) == quality["required_existing_motion_clock_frames"]),
        _gate("phase39_body_source_resample_count", prepared.body.contract["deformation"]["moving_source_resample_count"], "==", 1, prepared.body.contract["deformation"]["moving_source_resample_count"] == 1),
        _gate("encoding_process_count", 0, "==", quality["required_zero_encoder_processes"], quality["required_zero_encoder_processes"] == 0),
    ]


def _draw_label(image: Image.Image, text: str, xy: tuple[int, int]) -> None:
    draw = ImageDraw.Draw(image)
    x, y = xy
    box = draw.textbbox((x, y), text)
    draw.rectangle((box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 3), fill=(8, 10, 14))
    draw.text((x, y), text, fill=(245, 242, 231))


def _keyframe_sheet(retained: dict[int, IntegratedFrame]) -> Image.Image:
    numbers = [1, 24, 50, 66, 72, 82, 98, 110, 115, 126, 148, 162]
    cell = (640, 360)
    sheet = Image.new("RGB", (cell[0] * 3, cell[1] * 4), (8, 10, 14))
    for index, number in enumerate(numbers):
        frame = retained[number]
        image = Image.fromarray(frame.candidate, "RGB").resize(cell, Image.Resampling.LANCZOS)
        row, column = divmod(index, 3)
        sheet.paste(image, (column * cell[0], row * cell[1]))
        _draw_label(sheet, f"F{number:03d} SYNCHRONIZED CANDIDATE / DELTA {frame.metrics['mean_rgb_delta']:.3f}", (column * cell[0] + 10, row * cell[1] + 10))
    return sheet


def _hand_native_sheet(retained: dict[int, IntegratedFrame]) -> Image.Image:
    numbers = [1, 66, 72, 82, 110, 115, 126, 148]
    crop = (620, 700, 1010, 941)
    cell = ((crop[2] - crop[0]) * 2, (crop[3] - crop[1]) * 2)
    sheet = Image.new("RGB", (cell[0] * 4, cell[1] * 2), (8, 10, 14))
    for index, number in enumerate(numbers):
        current = retained[number].native_candidate[crop[1] : crop[3], crop[0] : crop[2]]
        image = Image.fromarray(current, "RGB").resize(cell, Image.Resampling.NEAREST)
        row, column = divmod(index, 4)
        sheet.paste(image, (column * cell[0], row * cell[1]))
        _draw_label(sheet, f"F{number:03d} NATIVE BODY + FACE STAGE 2X", (column * cell[0] + 10, row * cell[1] + 10))
    return sheet


def _support_sheet(retained: dict[int, IntegratedFrame]) -> Image.Image:
    numbers = [24, 72, 115, 148]
    cell = (960, 540)
    sheet = Image.new("RGB", (cell[0] * 2, cell[1] * 2), (8, 10, 14))
    for index, number in enumerate(numbers):
        frame = retained[number]
        image = frame.candidate.astype(np.float32) * 0.58
        colors = [
            (frame.transformed_body_support, np.asarray([35, 188, 255], dtype=np.float32), 0.45),
            (frame.transformed_head_support, np.asarray([255, 70, 110], dtype=np.float32), 0.32),
            (frame.transformed_face_support, np.asarray([255, 70, 110], dtype=np.float32), 0.55),
            (frame.transformed_mug_support, np.asarray([255, 210, 65], dtype=np.float32), 0.5),
        ]
        for mask, color, alpha in colors:
            image[mask] = image[mask] * (1.0 - alpha) + color * alpha
        resized = Image.fromarray(np.clip(np.rint(image), 0, 255).astype(np.uint8), "RGB").resize(cell, Image.Resampling.LANCZOS)
        row, column = divmod(index, 2)
        sheet.paste(resized, (column * cell[0], row * cell[1]))
        _draw_label(sheet, f"F{number:03d} BLUE BODY / RED FACE / YELLOW MUG", (column * cell[0] + 10, row * cell[1] + 10))
    return sheet


def _neighbor_sheet(retained: dict[int, IntegratedFrame]) -> Image.Image:
    groups = [(23, 24, 25), (71, 72, 73), (114, 115, 116), (147, 148, 149)]
    crop = (0, 455, 1250, 1080)
    cell = (500, 250)
    sheet = Image.new("RGB", (cell[0] * 3, cell[1] * 4), (8, 10, 14))
    for row, group in enumerate(groups):
        for column, number in enumerate(group):
            frame = retained[number]
            image = Image.fromarray(frame.candidate[crop[1] : crop[3], crop[0] : crop[2]], "RGB").resize(cell, Image.Resampling.LANCZOS)
            sheet.paste(image, (column * cell[0], row * cell[1]))
            _draw_label(sheet, f"F{number:03d} DELTA {frame.metrics['mean_rgb_delta']:.3f}", (column * cell[0] + 10, row * cell[1] + 10))
    return sheet


def _timeline_sheet(metrics: dict[str, Any]) -> Image.Image:
    width, height = 1800, 760
    image = Image.new("RGB", (width, height), (10, 12, 16))
    draw = ImageDraw.Draw(image)
    tracks = metrics["landmark_tracks"]
    colors = {
        "torso.sternum": (35, 188, 255),
        "viewer_left_arm.elbow": (200, 120, 255),
        "table_hand.palm": (255, 135, 75),
        "table_hand.index_tip": (255, 225, 65),
        "table_hand.pinky_tip": (110, 255, 165),
    }
    margin = 80
    for row, (name, points) in enumerate(tracks.items()):
        baseline = margin + row * 125
        values = np.asarray(points, dtype=np.float64)
        delta = values - values[0]
        scale = 28.0
        polyline = [
            (
                margin + index * (width - 2 * margin) / (len(points) - 1),
                baseline - float(delta[index, 0]) * scale,
            )
            for index in range(len(points))
        ]
        draw.line(polyline, fill=colors[name], width=4)
        draw.text((15, baseline - 8), name, fill=colors[name])
        for frame in (24, 50, 72, 98, 115, 148, 162, 228):
            x, y = polyline[frame - 1]
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=colors[name])
            if row == 0:
                draw.text((x - 12, 25), f"F{frame:03d}", fill=(220, 220, 220))
    _draw_label(image, "DELIVERY-SPACE LANDMARK X DELTA / BODY + FACE + CAMERA CLOCK", (15, height - 42))
    return image


def _write_png(image: Image.Image, path: Path) -> dict[str, Any]:
    image.save(path, format="PNG", optimize=False, compress_level=6)
    image.close()
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}


def build_evidence(
    output: str | Path | None = None,
    contract_path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> dict[str, Any]:
    prepared = prepare_integration(contract_path)
    destination = Path(output).resolve() if output is not None else _repo_path(prepared.contract["evidence"]["directory"])
    if destination.exists():
        raise SynchronizedActingIntegrationError(f"output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    metrics, retained = _measure(prepared)
    gates = _gates(prepared, metrics)
    failed = [row["id"] for row in gates if not row["passed"]]
    if failed:
        raise SynchronizedActingIntegrationError(f"Phase40 gates failed: {failed}")
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    try:
        artifacts = [
            _write_png(_keyframe_sheet(retained), stage / "phase40-synchronized-keyframes-v1.png"),
            _write_png(_hand_native_sheet(retained), stage / "phase40-synchronized-hand-native-v1.png"),
            _write_png(_support_sheet(retained), stage / "phase40-transformed-support-v1.png"),
            _write_png(_neighbor_sheet(retained), stage / "phase40-temporal-neighbors-v1.png"),
            _write_png(_timeline_sheet(metrics), stage / "phase40-motion-timeline-v1.png"),
        ]
        report = {
            "report_version": 1,
            "diagnostic_id": prepared.contract["contract_id"],
            "status": "MACHINE_SYNCHRONIZED_A_B_PASSED_HUMAN_ACTING_REVIEW_REQUIRED",
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
            "stage_order": prepared.contract["integration"]["stage_order"],
            "measurements": metrics,
            "gates": gates,
            "gate_count": len(gates),
            "failed_gates": failed,
            "artifacts": artifacts,
            "recommendation": "HUMAN_REVIEW_SYNCHRONIZED_BODY_FACE_TIMING_BEFORE_ANY_REBUILD_CONTRACT",
        }
        report_path = stage / "phase40-synchronized-acting-machine-report-v1.json"
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        actual = sorted(path.name for path in stage.iterdir())
        expected = sorted(prepared.contract["evidence"]["allowlist"])
        if actual != expected:
            raise SynchronizedActingIntegrationError(f"output inventory mismatch: {actual} != {expected}")
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
    print(json.dumps({"status": report["status"], "gate_count": report["gate_count"], "failed_gates": report["failed_gates"], "recommendation": report["recommendation"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
