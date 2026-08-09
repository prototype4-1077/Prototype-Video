"""Phase 33 close-view facial acting prototype for June Oxley.

This is deliberately a CLOSE_HERO_FRONT view adapter.  It reuses the GS070
production plate and its registered feature atlases, but it may never be
presented as reconstruction of the Phase 32 WIDE_BODY_3Q face.  Phase 32 stays
an immutable control until its pending human review is recorded.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
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

from pipeline.cartoon_expression_atlas import expression_performance_plan
from pipeline.cartoon_hero_scene import _blend, load_body_motion_contract
from pipeline.cartoon_reconstruction_locked_textured_mechanics import (
    _masked_psnr,
    _masked_ssim,
)
from pipeline.cartoon_resolution_scene import (
    compose_resolution_frame,
    prepare_resolution_sources,
)
from pipeline.cartoon_viseme_atlas import performance_viseme_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = Path(
    "concept/characters/june_oxley_phase33_close_facial_acting_v1.json"
)
IMPLEMENTATION_RELATIVE_PATH = Path("pipeline/cartoon_close_facial_acting.py")
_PINNED_CONTRACT_CANONICAL_SHA256 = "19c44426ec0caebe6d24fdafcd4f3092820391b469e95a49363e84c1443435ad"
OUTPUT_SIZE = (1920, 1080)
REVIEW_FRAMES = (1, 12, 24, 25, 46, 79, 82, 111, 132, 162, 168, 180, 192, 201, 202, 228)


class CloseFacialActingError(ValueError):
    """Raised when the Phase 33 prototype cannot prove a required invariant."""


@dataclass
class PreparedActingShot:
    contract: dict[str, Any]
    sources: dict[str, Any]
    visemes: list[dict[str, Any]]
    expressions: list[dict[str, Any]]
    motion: list[dict[str, float]]
    viseme_metadata: dict[str, Any]
    expression_metadata: dict[str, Any]
    motion_metadata: dict[str, Any]
    audio_path: Path
    dialogue_path: Path
    preflight_measurements: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _source_commit() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and len(value) == 40 else None


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise CloseFacialActingError(f"{label} mismatch: {actual!r} != {expected!r}")


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(reference.get("path", ""))).resolve()
    if not path.is_file():
        raise CloseFacialActingError(f"{label} is missing: {path}")
    actual = _sha256(path)
    expected = str(reference.get("sha256", ""))
    if not expected or actual != expected:
        raise CloseFacialActingError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def _wave_probe(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if not executable:
        raise CloseFacialActingError("ffprobe is required to validate locked PCM audio")
    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bits_per_raw_sample,duration_ts,time_base:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise CloseFacialActingError(f"invalid locked WAV: {path}")
    try:
        payload = json.loads(completed.stdout)
        streams = payload.get("streams") or []
        if len(streams) != 1:
            raise ValueError("stream inventory")
        stream = streams[0]
        sample_rate = int(stream["sample_rate"])
        sample_count = int(stream["duration_ts"])
        bits = int(stream.get("bits_per_raw_sample", 0) or 0)
        return {
            "channels": int(stream["channels"]),
            "sample_width_bytes": bits // 8,
            "sample_rate": sample_rate,
            "sample_count": sample_count,
            "duration_seconds": sample_count / sample_rate,
            "compression": "NONE" if stream.get("codec_name") == "pcm_s24le" else stream.get("codec_name"),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise CloseFacialActingError(f"invalid locked WAV metadata: {path}") from error


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_equal(
        _canonical_hash(contract),
        _PINNED_CONTRACT_CANONICAL_SHA256,
        "complete Phase33 contract",
    )
    _require_equal(contract.get("contract_version"), 1, "contract version")
    _require_equal(
        contract.get("contract_id"),
        "june_oxley_phase33_close_facial_acting_v1",
        "contract id",
    )
    _require_equal(contract.get("phase"), "phase33_close_facial_acting_prototype", "phase")
    _require_equal(contract.get("cash_cost"), 0, "cash cost")
    _require_equal(contract.get("paid_runtime_dependency"), False, "paid dependency")
    _require_equal(contract.get("network_runtime_required"), False, "network dependency")

    promotion = contract["promotion_policy"]
    _require_equal(promotion["phase32_current_human_review_completed"], False, "Phase32 human review")
    _require_equal(
        promotion["phase32_current_facial_performance_promotion_allowed"],
        False,
        "Phase32 facial promotion",
    )
    _require_equal(promotion["prototype_render_allowed"], True, "prototype render policy")
    _require_equal(
        promotion["accepted_delivery_publication_allowed"],
        False,
        "accepted delivery policy",
    )
    _require_equal(
        promotion["audience_status"],
        "prototype_candidate_human_review_required",
        "audience status",
    )
    representation = contract["representation_policy"]
    _require_equal(representation["close_view_adapter_is_phase32_face_reconstruction"], False, "view claim")
    _require_equal(representation["cross_view_face_paste_allowed"], False, "cross-view paste policy")
    _require_equal(
        representation["straight_on_atlas_pixels_allowed_in_phase32_head"],
        False,
        "Phase32 atlas policy",
    )

    clock = contract["clock"]
    _require_equal(
        (
            clock["width"],
            clock["height"],
            clock["fps"],
            clock["frame_count"],
            clock["duration_seconds"],
        ),
        (1920, 1080, 30, 228, 7.6),
        "picture clock",
    )
    _require_equal(
        (
            clock["audio_sample_rate"],
            clock["audio_samples_per_frame"],
            clock["audio_sample_count"],
        ),
        (48000, 1600, 364800),
        "audio clock",
    )
    _require_equal(clock["audio_sample_count"], clock["frame_count"] * clock["audio_samples_per_frame"], "sample/frame clock")

    performance = contract["performance"]
    _require_equal(performance["plate_visible_start_frame"], 1, "plate start")
    _require_equal(performance["attention_and_thought_frames"], [1, 24], "thought beat")
    _require_equal(performance["dialogue_frames"], [25, 162], "dialogue window")
    _require_equal(performance["mouth_returns_to_authored_plate_frame"], 168, "mouth return")
    _require_equal(performance["reaction_nod_frames"], [168, 201], "reaction window")
    _require_equal(performance["final_hold_frames"], [202, 228], "final hold")
    _require_equal(performance["review_frames"], list(REVIEW_FRAMES), "review inventory")

    delivery = contract["delivery"]
    _require_equal(delivery["attempt_version"], 1, "attempt version")
    _require_equal(delivery["one_video_encode_without_retry"], True, "single encode")
    _require_equal(delivery["staged_atomic_directory_publication"], True, "atomic publication")
    _require_equal(
        delivery["output_directory"],
        "../../outputs/edit/phase33-close-facial-acting-prototype-v1",
        "versioned output",
    )
    failure = contract["failure_policy"]
    _require_equal(failure["mode"], "fail_closed", "failure mode")
    _require_equal(failure["partial_success_allowed"], False, "partial success")
    _require_equal(failure["fallback_allowed"], False, "fallback")
    _require_equal(failure["automatic_reencode_allowed"], False, "automatic reencode")

    locked = {
        name: _locked_path(reference, name)
        for name, reference in contract["locks"].items()
    }
    receipt = json.loads(locked["phase32_control_receipt"].read_text(encoding="utf-8"))
    _require_equal(receipt.get("status"), promotion["phase32_current_status"], "Phase32 receipt status")
    _require_equal(receipt["review"]["human_full_size_review_completed"], False, "Phase32 receipt human review")
    _require_equal(receipt["review"]["facial_performance_promotion_allowed"], False, "Phase32 receipt promotion")

    dialogue_probe = _wave_probe(locked["dialogue_audio"])
    mix_probe = _wave_probe(locked["delivery_mix"])
    for label, probe, channels in (
        ("dialogue", dialogue_probe, clock["dialogue_audio_channels"]),
        ("delivery mix", mix_probe, clock["delivery_audio_channels"]),
    ):
        _require_equal(probe["compression"], "NONE", f"{label} PCM")
        _require_equal(probe["sample_width_bytes"], 3, f"{label} PCM width")
        _require_equal(probe["sample_rate"], clock["audio_sample_rate"], f"{label} sample rate")
        _require_equal(probe["sample_count"], clock["audio_sample_count"], f"{label} sample count")
        _require_equal(probe["channels"], channels, f"{label} channels")


def load_close_facial_acting_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path).resolve()
    if not contract_path.is_file():
        raise CloseFacialActingError(f"Phase33 contract is missing: {contract_path}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    _validate_contract(contract)
    return contract


def _strict_viseme_plan(
    cue_path: Path,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(cue_path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata") or {}
    clock = contract["clock"]
    _require_equal(float(metadata.get("duration", -1.0)), clock["duration_seconds"], "cue duration")
    _require_equal(metadata.get("sourceAudioSha256"), contract["locks"]["dialogue_audio"]["sha256"], "cue/audio binding")
    _require_equal(metadata.get("deliveryMixSha256"), contract["locks"]["delivery_mix"]["sha256"], "cue/mix binding")
    _require_equal(metadata.get("sourceAudioSampleRate"), clock["audio_sample_rate"], "cue sample rate")
    _require_equal(metadata.get("sourceAudioSampleCount"), clock["audio_sample_count"], "cue sample count")
    cues = payload.get("mouthCues") or []
    if not cues:
        raise CloseFacialActingError("Phase33 mouth cues cannot be empty")
    duration = float(clock["duration_seconds"])
    cursor = 0.0
    for index, cue in enumerate(cues):
        start = float(cue.get("start", -1.0))
        end = float(cue.get("end", -1.0))
        if start < cursor - 1e-9 or end <= start or end > duration + 1e-9:
            raise CloseFacialActingError(f"mouth cue {index} leaves the locked audio clock")
        cursor = end
    if abs(cursor - duration) > 1e-9:
        raise CloseFacialActingError("mouth cues must end on the locked audio sample clock")
    result = performance_viseme_plan(
        cue_path,
        fps=int(clock["fps"]),
        transition_frames=int(contract["performance"]["transition_frames"]),
    )
    metadata_result, plan = result
    _require_equal(metadata_result["frame_count"], clock["frame_count"], "viseme frame count")
    _require_equal(metadata_result["shapes"], contract["performance"]["required_viseme_shapes_in_cues"], "viseme cue shapes")
    return metadata_result, plan


def _feature_scope_metrics(
    sources: dict[str, Any],
    visemes: list[dict[str, Any]],
    expressions: list[dict[str, Any]],
) -> dict[str, Any]:
    plate = np.asarray(sources["plate"], dtype=np.uint8)
    height, width = plate.shape[:2]
    mouth_box = tuple(int(value) for value in sources["plate_mouth_box"])
    expression_box = tuple(int(value) for value in sources["plate_expression_box"])
    mouth_mask_local = np.asarray(sources["viseme_mask"], dtype=np.uint8) > 0
    expression_mask_local = np.asarray(sources["expression_mask"], dtype=np.uint8) > 0
    mouth_support = np.zeros((height, width), dtype=bool)
    expression_support = np.zeros((height, width), dtype=bool)
    mouth_support[mouth_box[1] : mouth_box[3], mouth_box[0] : mouth_box[2]] = mouth_mask_local
    expression_support[
        expression_box[1] : expression_box[3], expression_box[0] : expression_box[2]
    ] = expression_mask_local
    feature_support = mouth_support | expression_support
    head_box = (330, 20, 875, 610)
    stable = np.zeros((height, width), dtype=bool)
    stable[head_box[1] : head_box[3], head_box[0] : head_box[2]] = True
    stable &= ~feature_support
    if not np.any(stable) or not np.any(mouth_support) or not np.any(expression_support):
        raise CloseFacialActingError("Phase33 feature evidence masks must be nonempty")

    maximum_outside = 0
    for patches, mask, box in (
        (sources["viseme_patches"], sources["viseme_mask"], mouth_box),
        (sources["expression_patches"], sources["expression_mask"], expression_box),
    ):
        support = np.zeros((height, width), dtype=bool)
        local = np.asarray(mask, dtype=np.uint8) > 0
        support[box[1] : box[3], box[0] : box[2]] = local
        for patch in patches.values():
            composite = sources["plate"].copy()
            composite.paste(patch, box[:2], mask)
            changed = np.any(np.asarray(composite, dtype=np.uint8) != plate, axis=2)
            maximum_outside = max(maximum_outside, int(np.count_nonzero(changed & ~support)))

    blink = np.asarray(sources["expression_patches"]["blink"], dtype=np.float32)
    neutral = np.asarray(sources["expression_patches"]["neutral"], dtype=np.float32)
    blink_delta = np.mean(np.abs(blink - neutral), axis=2)
    local_eye_mask = expression_mask_local
    midpoint = blink_delta.shape[1] // 2
    left = local_eye_mask.copy()
    left[:, midpoint:] = False
    right = local_eye_mask.copy()
    right[:, :midpoint] = False
    bilateral = [float(np.mean(blink_delta[mask])) for mask in (left, right)]

    mouth_arrays = {
        name: np.asarray(patch, dtype=np.float32)
        for name, patch in sources["viseme_patches"].items()
    }
    expression_arrays = {
        name: np.asarray(patch, dtype=np.float32)
        for name, patch in sources["expression_patches"].items()
    }
    mouth_step = 0.0
    expression_step = 0.0
    previous_mouth: np.ndarray | None = None
    previous_expression: np.ndarray | None = None
    settled_x_frames = 0
    non_x_observed_frames = 0
    for viseme, expression in zip(visemes, expressions):
        mouth = (
            mouth_arrays[viseme["from_shape"]] * (1.0 - float(viseme["blend"]))
            + mouth_arrays[viseme["to_shape"]] * float(viseme["blend"])
        )
        eyes = (
            expression_arrays[expression["from_state"]] * (1.0 - float(expression["blend"]))
            + expression_arrays[expression["to_state"]] * float(expression["blend"])
        )
        if previous_mouth is not None:
            mouth_step = max(
                mouth_step,
                float(np.mean(np.abs(mouth - previous_mouth)[mouth_mask_local])),
            )
            expression_step = max(
                expression_step,
                float(np.mean(np.abs(eyes - previous_expression)[expression_mask_local])),
            )
        if viseme["to_shape"] == "X" and float(viseme["blend"]) >= 1.0:
            settled_x_frames += 1
        if viseme["to_shape"] != "X":
            delta = float(np.mean(np.abs(mouth - mouth_arrays["X"])[mouth_mask_local]))
            if delta > 0.5:
                non_x_observed_frames += 1
        previous_mouth = mouth
        previous_expression = eyes

    distinct_visemes = {
        name
        for name, value in mouth_arrays.items()
        if name == "X" or float(np.mean(np.abs(value - mouth_arrays["X"])[mouth_mask_local])) > 0.5
    }
    return {
        "stable_identity_pixel_count": int(np.count_nonzero(stable)),
        "mouth_feature_mask_pixel_count": int(np.count_nonzero(mouth_support)),
        "expression_feature_mask_pixel_count": int(np.count_nonzero(expression_support)),
        "maximum_changed_pixels_outside_declared_feature_support": maximum_outside,
        "bilateral_blink_mean_absolute_delta": min(bilateral),
        "left_blink_mean_absolute_delta": bilateral[0],
        "right_blink_mean_absolute_delta": bilateral[1],
        "maximum_adjacent_mouth_patch_mean_absolute_delta": mouth_step,
        "maximum_adjacent_expression_patch_mean_absolute_delta": expression_step,
        "maximum_adjacent_feature_patch_mean_absolute_delta": max(mouth_step, expression_step),
        "settled_x_frame_count": settled_x_frames,
        "non_x_observed_frame_count": non_x_observed_frames,
        "distinct_registered_viseme_count": len(distinct_visemes),
        "distinct_registered_visemes": sorted(distinct_visemes),
    }


def _gate(id_: str, measured: Any, operator: str, threshold: Any) -> dict[str, Any]:
    if operator == "==":
        passed = measured == threshold
    elif operator == ">=":
        passed = measured is not None and math.isfinite(float(measured)) and float(measured) >= float(threshold)
    elif operator == "<=":
        passed = measured is not None and math.isfinite(float(measured)) and float(measured) <= float(threshold)
    else:
        raise CloseFacialActingError(f"unsupported gate operator: {operator}")
    return {"id": id_, "measured": measured, "operator": operator, "threshold": threshold, "passed": bool(passed)}


def _preflight_gates(contract: dict[str, Any], measurements: dict[str, Any]) -> list[dict[str, Any]]:
    scope = contract["feature_scope"]
    performance = contract["performance"]
    return [
        _gate("promotion.prototype_only", measurements["audience_status"], "==", "prototype_candidate_human_review_required"),
        _gate("promotion.accepted_delivery_forbidden", measurements["accepted_delivery_publication_allowed"], "==", False),
        _gate("representation.cross_view_paste_forbidden", measurements["cross_view_face_paste_allowed"], "==", False),
        _gate("clock.frame_count", measurements["frame_count"], "==", 228),
        _gate("clock.audio_sample_count", measurements["audio_sample_count"], "==", 364800),
        _gate("clock.samples_per_frame", measurements["audio_samples_per_frame"], "==", 1600),
        _gate("lipsync.cue_audio_hash_bound", measurements["cue_audio_hash_bound"], "==", True),
        _gate("lipsync.cue_mix_hash_bound", measurements["cue_mix_hash_bound"], "==", True),
        _gate("lipsync.required_shapes", measurements["cue_shapes"], "==", performance["required_viseme_shapes_in_cues"]),
        _gate("lipsync.observed_non_x_frames", measurements["non_x_observed_frame_count"], ">=", 40),
        _gate("lipsync.closed_x_frames", measurements["settled_x_frame_count"], ">=", 60),
        _gate("expression.required_states", measurements["expression_states"], "==", performance["required_expression_states"]),
        _gate("expression.blink_cues", measurements["blink_cue_count"], ">=", performance["minimum_blink_cue_count"]),
        _gate("expression.bilateral_blink_delta", measurements["bilateral_blink_mean_absolute_delta"], ">=", scope["minimum_bilateral_blink_mean_absolute_delta"]),
        _gate("identity.stable_pixel_evidence", measurements["stable_identity_pixel_count"], ">=", scope["minimum_stable_identity_pixels"]),
        _gate("identity.zero_out_of_scope_changes", measurements["maximum_changed_pixels_outside_declared_feature_support"], "<=", scope["maximum_changed_pixels_outside_declared_feature_support"]),
        _gate("identity.mouth_mask_nonvacuous", measurements["mouth_feature_mask_pixel_count"], ">=", scope["minimum_feature_mask_pixels"]),
        _gate("identity.eye_mask_nonvacuous", measurements["expression_feature_mask_pixel_count"], ">=", scope["minimum_feature_mask_pixels"]),
        _gate("temporal.feature_patch_step", measurements["maximum_adjacent_feature_patch_mean_absolute_delta"], "<=", scope["maximum_adjacent_feature_patch_mean_absolute_delta"]),
        _gate("performance.final_hold_controls_zero", measurements["final_hold_controls_zero"], "==", True),
        _gate("performance.final_mouth_authored", measurements["final_mouth_authored"], "==", True),
    ]


def prepare_close_facial_acting(contract_path: str | Path) -> PreparedActingShot:
    contract = load_close_facial_acting_contract(contract_path)
    locks = contract["locks"]
    sources = prepare_resolution_sources(
        _locked_path(locks["gs070_close_view"], "GS070 close view"),
        _locked_path(locks["viseme_atlas"], "viseme atlas"),
        _locked_path(locks["expression_atlas"], "expression atlas"),
    )
    sources = deepcopy(sources)
    sequence = sources["contract"]["sequence"]
    sequence["offer_insert_end_frame"] = 0
    sequence["direct_address_start_frame"] = 1
    sequence["dialogue_end_frame"] = int(contract["performance"]["dialogue_frames"][1])
    sequence["nod_start_frame"] = int(contract["performance"]["reaction_nod_frames"][0])
    sequence["nod_end_frame"] = int(contract["performance"]["reaction_nod_frames"][1])
    sequence["final_hold_start_frame"] = int(contract["performance"]["final_hold_frames"][0])
    sequence["final_hold_frames"] = int(contract["performance"]["final_hold_frame_count"])
    sequence["mouth_returns_to_authored_plate_frame"] = int(
        contract["performance"]["mouth_returns_to_authored_plate_frame"]
    )

    cue_path = _locked_path(locks["viseme_cues"], "viseme cues")
    expression_path = _locked_path(locks["expression_cues"], "expression cues")
    motion_path = _locked_path(locks["body_motion"], "body motion")
    viseme_metadata, visemes = _strict_viseme_plan(cue_path, contract)
    expression_metadata, expressions = expression_performance_plan(
        expression_path,
        expected_atlas_id=sources["expression_contract"]["atlas_id"],
    )
    motion_metadata, motion = load_body_motion_contract(
        motion_path,
        hero_contract=sources["contract"],
    )
    if {len(visemes), len(expressions), len(motion)} != {228}:
        raise CloseFacialActingError("all Phase33 performance plans must share 228 frames")
    if expression_metadata["states"] != contract["performance"]["required_expression_states"]:
        raise CloseFacialActingError("Phase33 expression state inventory changed")

    feature = _feature_scope_metrics(sources, visemes, expressions)
    final_controls = ("head_x_px", "head_y_px", "head_tilt_deg", "shoulder_x_px", "breath_y_px")
    final_hold = motion[201:]
    final_hold_controls_zero = all(
        all(abs(float(entry[channel])) <= 1e-9 for channel in final_controls)
        for entry in final_hold
    )
    raw_cues = json.loads(cue_path.read_text(encoding="utf-8"))
    expression_payload = json.loads(expression_path.read_text(encoding="utf-8"))
    dialogue_probe = _wave_probe(_locked_path(locks["dialogue_audio"], "dialogue audio"))
    metadata = raw_cues["metadata"]
    measurements = {
        "audience_status": contract["promotion_policy"]["audience_status"],
        "accepted_delivery_publication_allowed": contract["promotion_policy"]["accepted_delivery_publication_allowed"],
        "cross_view_face_paste_allowed": contract["representation_policy"]["cross_view_face_paste_allowed"],
        "frame_count": len(visemes),
        "audio_sample_count": dialogue_probe["sample_count"],
        "audio_samples_per_frame": dialogue_probe["sample_count"] // len(visemes),
        "cue_audio_hash_bound": metadata["sourceAudioSha256"] == locks["dialogue_audio"]["sha256"],
        "cue_mix_hash_bound": metadata["deliveryMixSha256"] == locks["delivery_mix"]["sha256"],
        "cue_shapes": viseme_metadata["shapes"],
        "expression_states": expression_metadata["states"],
        "blink_cue_count": sum(1 for cue in expression_payload["cues"] if cue["state"] == "blink"),
        "final_hold_controls_zero": final_hold_controls_zero,
        "final_mouth_authored": all(index + 1 >= 168 and visemes[index]["to_shape"] == "X" for index in range(167, 228)),
        **feature,
    }
    gates = _preflight_gates(contract, measurements)
    if not all(row["passed"] for row in gates):
        failed = [row["id"] for row in gates if not row["passed"]]
        raise CloseFacialActingError(f"Phase33 preflight gates failed: {failed}")
    measurements["gates"] = gates
    return PreparedActingShot(
        contract=contract,
        sources=sources,
        visemes=visemes,
        expressions=expressions,
        motion=motion,
        viseme_metadata=viseme_metadata,
        expression_metadata=expression_metadata,
        motion_metadata=motion_metadata,
        audio_path=_locked_path(locks["delivery_mix"], "delivery mix"),
        dialogue_path=_locked_path(locks["dialogue_audio"], "dialogue audio"),
        preflight_measurements=measurements,
    )


def compose_close_facial_acting_frame(prepared: PreparedActingShot, frame_index: int) -> Image.Image:
    if not 1 <= int(frame_index) <= 228:
        raise CloseFacialActingError("Phase33 frame index must be between 1 and 228")
    index = int(frame_index) - 1
    return compose_resolution_frame(
        prepared.sources,
        prepared.visemes[index],
        prepared.expressions[index],
        prepared.motion[index],
        frame_index=int(frame_index),
        fps=30,
        secondary=prepared.motion_metadata["secondary_motion"],
    )


def _format_srt_time(frame_boundary: int, fps: int) -> str:
    milliseconds = round(frame_boundary * 1000 / fps)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _write_captions(contract: dict[str, Any], path: Path) -> None:
    blocks = []
    fps = int(contract["clock"]["fps"])
    for index, cue in enumerate(contract["captions"], start=1):
        blocks.append(
            "\n".join(
                (
                    str(index),
                    f"{_format_srt_time(int(cue['start_frame']) - 1, fps)} --> {_format_srt_time(int(cue['end_frame']), fps)}",
                    str(cue["text"]),
                )
            )
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _executable(value: str | Path) -> str:
    candidate = Path(value)
    result = str(candidate.resolve()) if candidate.is_file() else shutil.which(str(value))
    if not result:
        raise CloseFacialActingError(f"required executable not found: {value}")
    return result


def _encode_once(
    prepared: PreparedActingShot,
    stage: Path,
    *,
    ffmpeg: str,
) -> tuple[Path, dict[int, np.ndarray]]:
    contract = prepared.contract
    delivery = contract["delivery"]
    video = stage / delivery["video_filename"]
    partial = stage / (video.stem + ".partial.mp4")
    encoding = delivery["encoding"]
    command = [
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        "1920x1080",
        "-r",
        "30",
        "-i",
        "pipe:0",
        "-i",
        str(prepared.audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        str(encoding["implementation"]),
        "-preset",
        str(encoding["preset"]),
        "-tune",
        str(encoding["tune"]),
        "-crf",
        str(encoding["crf"]),
        "-pix_fmt",
        str(encoding["pixel_format"]),
        "-frames:v",
        "228",
        "-c:a",
        str(encoding["audio_codec"]),
        "-b:a",
        str(encoding["audio_bitrate"]),
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(partial),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise CloseFacialActingError("unable to open Phase33 FFmpeg pipe")
    expected: dict[int, np.ndarray] = {}
    try:
        for frame_index in range(1, 229):
            frame = compose_close_facial_acting_frame(prepared, frame_index)
            array = np.asarray(frame, dtype=np.uint8)
            process.stdin.write(array.tobytes())
            if frame_index in REVIEW_FRAMES:
                expected[frame_index] = array.copy()
        process.stdin.close()
        error_output = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    if return_code != 0:
        raise CloseFacialActingError(f"Phase33 FFmpeg encode failed: {error_output[-2000:]}")
    if not partial.is_file() or partial.stat().st_size <= 0:
        raise CloseFacialActingError("Phase33 FFmpeg did not create a usable candidate")
    partial.replace(video)
    return video, expected


def _ffprobe(video: Path, executable: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,pix_fmt,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,sample_rate,channels,duration,duration_ts,time_base",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _roi_mask(shape: tuple[int, int, int], box: list[int]) -> np.ndarray:
    mask = np.zeros(shape[:2], dtype=bool)
    x0, y0, x1, y1 = (int(value) for value in box)
    mask[y0:y1, x0:x1] = True
    return mask


def _decode_and_audit(
    video: Path,
    expected: dict[int, np.ndarray],
    contract: dict[str, Any],
    *,
    ffmpeg: str,
    ffprobe: str,
) -> tuple[dict[str, Any], dict[int, np.ndarray]]:
    process = subprocess.Popen(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None and process.stderr is not None
    frame_bytes = 1920 * 1080 * 3
    decoded_review: dict[int, np.ndarray] = {}
    decoded_count = 0
    full_psnr: list[float] = []
    face_psnr: list[float] = []
    face_ssim: list[float] = []
    eye_psnr: list[float] = []
    mouth_psnr: list[float] = []
    sharpness: list[float] = []
    quality = contract["decoded_quality_gate"]
    while True:
        payload = process.stdout.read(frame_bytes)
        if not payload:
            break
        if len(payload) != frame_bytes:
            raise CloseFacialActingError("Phase33 decoder returned a partial frame")
        decoded_count += 1
        frame = np.frombuffer(payload, dtype=np.uint8).reshape(1080, 1920, 3).copy()
        if decoded_count in expected:
            reference = expected[decoded_count]
            full = np.ones((1080, 1920), dtype=bool)
            face = _roi_mask(frame.shape, quality["face_roi_xyxy"])
            eyes = _roi_mask(frame.shape, quality["eye_roi_xyxy"])
            mouth = _roi_mask(frame.shape, quality["mouth_roi_xyxy"])
            full_psnr.append(_masked_psnr(reference, frame, full))
            face_psnr.append(_masked_psnr(reference, frame, face))
            face_ssim.append(_masked_ssim(reference, frame, face))
            eye_psnr.append(_masked_psnr(reference, frame, eyes))
            mouth_psnr.append(_masked_psnr(reference, frame, mouth))
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            decoded_review[decoded_count] = frame
    error_output = process.stderr.read().decode("utf-8", errors="replace")
    return_code = process.wait()
    if return_code != 0:
        raise CloseFacialActingError(f"Phase33 full decode failed: {error_output[-2000:]}")
    probe = _ffprobe(video, ffprobe)
    streams = probe.get("streams") or []
    video_streams = [row for row in streams if row.get("codec_type") == "video"]
    audio_streams = [row for row in streams if row.get("codec_type") == "audio"]
    video_stream = video_streams[0] if len(video_streams) == 1 else {}
    audio_stream = audio_streams[0] if len(audio_streams) == 1 else {}
    rate = Fraction(str(video_stream.get("r_frame_rate", "0/1")))
    return {
        "full_decode": decoded_count == 228,
        "decoded_frame_count": decoded_count,
        "review_frame_count": len(decoded_review),
        "minimum_full_frame_psnr_db": min(full_psnr, default=0.0),
        "minimum_face_psnr_db": min(face_psnr, default=0.0),
        "minimum_face_ssim": min(face_ssim, default=0.0),
        "minimum_eye_psnr_db": min(eye_psnr, default=0.0),
        "minimum_mouth_psnr_db": min(mouth_psnr, default=0.0),
        "minimum_encoded_laplacian_variance": min(sharpness, default=0.0),
        "width": int(video_stream.get("width", 0) or 0),
        "height": int(video_stream.get("height", 0) or 0),
        "fps": float(rate),
        "video_codec": video_stream.get("codec_name"),
        "pixel_format": video_stream.get("pix_fmt"),
        "video_stream_count": len(video_streams),
        "audio_stream_count": len(audio_streams),
        "audio_codec": audio_stream.get("codec_name"),
        "audio_sample_rate": int(audio_stream.get("sample_rate", 0) or 0),
        "audio_channels": int(audio_stream.get("channels", 0) or 0),
        "duration_seconds": float(probe.get("format", {}).get("duration", 0.0) or 0.0),
    }, decoded_review


def _delivery_gates(contract: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    quality = contract["decoded_quality_gate"]
    return [
        _gate("decoded.full_decode", metrics["full_decode"], "==", True),
        _gate("decoded.frame_count", metrics["decoded_frame_count"], "==", 228),
        _gate("decoded.review_inventory", metrics["review_frame_count"], "==", len(REVIEW_FRAMES)),
        _gate("decoded.full_frame_psnr", metrics["minimum_full_frame_psnr_db"], ">=", quality["minimum_full_frame_psnr_db"]),
        _gate("decoded.face_psnr", metrics["minimum_face_psnr_db"], ">=", quality["minimum_face_psnr_db"]),
        _gate("decoded.face_ssim", metrics["minimum_face_ssim"], ">=", quality["minimum_face_ssim"]),
        _gate("decoded.eye_psnr", metrics["minimum_eye_psnr_db"], ">=", quality["minimum_eye_psnr_db"]),
        _gate("decoded.mouth_psnr", metrics["minimum_mouth_psnr_db"], ">=", quality["minimum_mouth_psnr_db"]),
        _gate("decoded.sharpness", metrics["minimum_encoded_laplacian_variance"], ">=", quality["minimum_encoded_laplacian_variance"]),
        _gate("stream.width", metrics["width"], "==", 1920),
        _gate("stream.height", metrics["height"], "==", 1080),
        _gate("stream.fps", metrics["fps"], "==", 30.0),
        _gate("stream.video_codec", metrics["video_codec"], "==", "h264"),
        _gate("stream.pixel_format", metrics["pixel_format"], "==", "yuv420p"),
        _gate("stream.video_count", metrics["video_stream_count"], "==", 1),
        _gate("stream.audio_count", metrics["audio_stream_count"], "==", 1),
        _gate("stream.audio_codec", metrics["audio_codec"], "==", "aac"),
        _gate("stream.audio_sample_rate", metrics["audio_sample_rate"], "==", 48000),
        _gate("stream.audio_channels", metrics["audio_channels"], "==", 2),
        _gate("stream.duration", metrics["duration_seconds"], "==", 7.6),
    ]


def _crop_tile(frame: np.ndarray, box: list[int], size: tuple[int, int]) -> np.ndarray:
    x0, y0, x1, y1 = (int(value) for value in box)
    crop = frame[y0:y1, x0:x1]
    return cv2.resize(crop, size, interpolation=cv2.INTER_AREA)


def _write_review_artifacts(
    stage: Path,
    decoded: dict[int, np.ndarray],
    contract: dict[str, Any],
) -> dict[str, Any]:
    if set(decoded) != set(REVIEW_FRAMES):
        raise CloseFacialActingError("decoded Phase33 review frame inventory is incomplete")
    contact = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for index, frame_number in enumerate(REVIEW_FRAMES):
        row, column = divmod(index, 4)
        contact[row * 270 : (row + 1) * 270, column * 480 : (column + 1) * 480] = cv2.resize(
            decoded[frame_number], (480, 270), interpolation=cv2.INTER_AREA
        )
    contact_path = stage / "june-phase33-decoded-contact-sheet-v1.png"
    Image.fromarray(contact, "RGB").save(contact_path)

    eye_frames = (78, 79, 80, 81, 82, 83, 169, 170, 171, 172, 173, 174)
    prepared_eye_frames = {frame: decoded.get(frame) for frame in eye_frames}
    missing = [frame for frame, value in prepared_eye_frames.items() if value is None]
    if missing:
        # Decode review frames nearest the authored blink when the compact review
        # inventory does not retain the complete strip.
        capture = cv2.VideoCapture(str(stage / contract["delivery"]["video_filename"]))
        for frame_number in eye_frames:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
            ok, bgr = capture.read()
            if not ok:
                capture.release()
                raise CloseFacialActingError("unable to decode Phase33 blink strip")
            prepared_eye_frames[frame_number] = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        capture.release()
    eye_sheet = np.zeros((540, 1920, 3), dtype=np.uint8)
    eye_box = contract["decoded_quality_gate"]["eye_roi_xyxy"]
    for index, frame_number in enumerate(eye_frames):
        row, column = divmod(index, 6)
        eye_sheet[row * 270 : (row + 1) * 270, column * 320 : (column + 1) * 320] = _crop_tile(
            prepared_eye_frames[frame_number], eye_box, (320, 270)
        )
    eye_path = stage / "june-phase33-decoded-blink-strip-v1.png"
    Image.fromarray(eye_sheet, "RGB").save(eye_path)

    mouth_frames = (1, 24, 25, 46, 82, 111, 132, 162, 168, 180, 202, 228)
    mouth_sheet = np.zeros((540, 1920, 3), dtype=np.uint8)
    mouth_box = contract["decoded_quality_gate"]["mouth_roi_xyxy"]
    for index, frame_number in enumerate(mouth_frames):
        row, column = divmod(index, 6)
        mouth_sheet[row * 270 : (row + 1) * 270, column * 320 : (column + 1) * 320] = _crop_tile(
            decoded[frame_number], mouth_box, (320, 270)
        )
    mouth_path = stage / "june-phase33-decoded-mouth-strip-v1.png"
    Image.fromarray(mouth_sheet, "RGB").save(mouth_path)
    return {
        "contact_sheet": {"file": contact_path.name, "sha256": _sha256(contact_path), "source": "decoded_mp4"},
        "blink_strip": {"file": eye_path.name, "sha256": _sha256(eye_path), "source": "decoded_mp4"},
        "mouth_strip": {"file": mouth_path.name, "sha256": _sha256(mouth_path), "source": "decoded_mp4"},
    }


def _write_ab_sheet(
    stage: Path,
    candidate: dict[int, np.ndarray],
    baseline_path: Path,
) -> dict[str, Any] | None:
    if not baseline_path.is_file():
        return None
    expected_hash = "9b1a05e0affce70ee52cbc3ca5068a5d7499ded19304a6dae976f2f7fda698e5"
    if _sha256(baseline_path) != expected_hash:
        raise CloseFacialActingError("Phase27 A/B baseline hash changed")
    pairs = ((1, 46), (46, 90), (82, 143), (162, 168), (202, 202), (228, 228))
    capture = cv2.VideoCapture(str(baseline_path))
    sheet = np.zeros((720, 1920, 3), dtype=np.uint8)
    for column, (candidate_frame, baseline_frame) in enumerate(pairs):
        capture.set(cv2.CAP_PROP_POS_FRAMES, baseline_frame - 1)
        ok, bgr = capture.read()
        if not ok:
            capture.release()
            raise CloseFacialActingError("unable to decode Phase27 A/B baseline")
        baseline = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        sheet[0:360, column * 320 : (column + 1) * 320] = cv2.resize(
            candidate[candidate_frame], (320, 360), interpolation=cv2.INTER_AREA
        )
        sheet[360:720, column * 320 : (column + 1) * 320] = cv2.resize(
            baseline, (320, 360), interpolation=cv2.INTER_AREA
        )
    capture.release()
    path = stage / "june-phase33-blinded-ab-vs-phase27-v1.png"
    Image.fromarray(sheet, "RGB").save(path)
    return {
        "file": path.name,
        "sha256": _sha256(path),
        "baseline_sha256": expected_hash,
        "row_identity_hidden": True,
        "human_preference_required": True,
    }


def render_close_facial_acting(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
    baseline_video: str | Path | None = None,
) -> dict[str, Any]:
    prepared = prepare_close_facial_acting(contract_path)
    contract = prepared.contract
    output = Path(output_dir).resolve()
    if output.exists():
        raise CloseFacialActingError(f"immutable Phase33 output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = _executable(ffmpeg)
    ffprobe_bin = _executable(ffprobe)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    encode_process_count = 0
    try:
        captions = stage / contract["delivery"]["caption_filename"]
        _write_captions(contract, captions)
        encode_process_count += 1
        video, expected = _encode_once(prepared, stage, ffmpeg=ffmpeg_bin)
        decoded_metrics, decoded = _decode_and_audit(
            video,
            expected,
            contract,
            ffmpeg=ffmpeg_bin,
            ffprobe=ffprobe_bin,
        )
        delivery_gates = _delivery_gates(contract, decoded_metrics)
        if not all(row["passed"] for row in delivery_gates):
            failed = [row["id"] for row in delivery_gates if not row["passed"]]
            raise CloseFacialActingError(f"Phase33 decoded delivery gates failed: {failed}")
        review = _write_review_artifacts(stage, decoded, contract)
        ab = _write_ab_sheet(stage, decoded, Path(baseline_video).resolve()) if baseline_video else None
        preflight_gates = prepared.preflight_measurements["gates"]
        all_gates = preflight_gates + delivery_gates
        report = {
            "contract_version": 1,
            "gate": "phase33_reconstruction_audited_close_facial_acting_prototype",
            "classification": contract["classification"],
            "audience_status": contract["promotion_policy"]["audience_status"],
            "accepted_production_delivery": False,
            "human_review_required": True,
            "contract": {
                "path": str(CONTRACT_RELATIVE_PATH).replace("\\", "/"),
                "raw_sha256": _sha256((REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve()),
                "canonical_sha256": _canonical_hash(contract),
            },
            "implementation": {
                "path": str(IMPLEMENTATION_RELATIVE_PATH).replace("\\", "/"),
                "sha256": _sha256((REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH).resolve()),
            },
            "source_commit": _source_commit(),
            "view_policy": contract["representation_policy"],
            "phase32_control": {
                "receipt_sha256": contract["locks"]["phase32_control_receipt"]["sha256"],
                "status": contract["promotion_policy"]["phase32_current_status"],
                "human_approved": False,
            },
            "audio": {
                "dialogue_file": prepared.dialogue_path.name,
                "dialogue_sha256": _sha256(prepared.dialogue_path),
                "delivery_mix_file": prepared.audio_path.name,
                "delivery_mix_sha256": _sha256(prepared.audio_path),
                "sample_rate": 48000,
                "sample_count": 364800,
                "samples_per_frame": 1600,
                "cue_sha256": prepared.viseme_metadata["sha256"],
                "cash_cost": 0,
                "human_casting_approval_required": True,
            },
            "performance": {
                "frame_count": 228,
                "duration_seconds": 7.6,
                "setup_frames": [1, 24],
                "dialogue_frames": [25, 162],
                "reaction_frames": [168, 201],
                "final_hold_frames": [202, 228],
                "viseme_shapes": prepared.viseme_metadata["shapes"],
                "expression_states": prepared.expression_metadata["states"],
            },
            "preflight_measurements": {
                key: value
                for key, value in prepared.preflight_measurements.items()
                if key != "gates"
            },
            "decoded_quality": decoded_metrics,
            "review_artifacts": review,
            "blinded_ab": ab,
            "gate_count": len(all_gates),
            "passed_gate_count": sum(row["passed"] for row in all_gates),
            "failed_gate_count": sum(not row["passed"] for row in all_gates),
            "gates": all_gates,
            "delivery": {
                "video": video.name,
                "video_sha256": _sha256(video),
                "video_bytes": video.stat().st_size,
                "caption_file": captions.name,
                "caption_sha256": _sha256(captions),
                "encoding_process_count": encode_process_count,
                "staged_atomic_publication": True,
            },
            "known_limitations": contract["known_limitations"],
            "paid_runtime_dependency": False,
            "machine_passed": True,
        }
        report_path = stage / contract["delivery"]["report_filename"]
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        os.replace(stage, output)
        return report
    except BaseException:
        # Preserve a failed encoded candidate for audit, but never publish it at
        # the requested delivery path and never retry the video encoder.
        if encode_process_count and stage.exists():
            rejected = output.parent / f"{output.name}-rejected"
            if not rejected.exists():
                os.replace(stage, rejected)
        elif stage.exists():
            shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's Phase33 close facial acting prototype")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--baseline-video")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.preflight_only:
        prepared = prepare_close_facial_acting(args.contract)
        payload = {
            "preflight_passed": True,
            "measurements": prepared.preflight_measurements,
        }
    else:
        payload = render_close_facial_acting(
            args.contract,
            args.output_dir,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
            baseline_video=args.baseline_video,
        )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
