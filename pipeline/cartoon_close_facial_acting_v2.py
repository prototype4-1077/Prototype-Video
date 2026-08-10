"""Phase 33 v2: plate-neutral corrective-delta facial acting.

The v1 machine candidate proved the clock and delivery path but failed visual
review because neutral atlas crops replaced the authored face.  V2 keeps the
GS070 plate exact at neutral/X and applies attenuated state deltas once, with
mouth ownership removing the expression/mouth overlap ambiguity.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
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

import pipeline.cartoon_close_facial_acting as v1
from pipeline.cartoon_hero_scene import (
    _camera_frame,
    _lantern_glow,
    _secondary_overlay,
    _warp_region,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = Path(
    "concept/characters/june_oxley_phase33_close_facial_acting_v2.json"
)
IMPLEMENTATION_RELATIVE_PATH = Path("pipeline/cartoon_close_facial_acting_v2.py")
_PINNED_CONTRACT_CANONICAL_SHA256 = "00d127a19db8f7ee9fadb4559ab4d4401e8f324e138dfd40049a28c61de03c59"
REVIEW_FRAMES = v1.REVIEW_FRAMES


class CorrectiveFacialActingError(ValueError):
    """Raised when the Phase 33 v2 corrective proof fails closed."""


@dataclass
class PreparedCorrectiveShot:
    contract: dict[str, Any]
    effective_contract: dict[str, Any]
    base: v1.PreparedActingShot
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


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = (REPO_ROOT / str(reference.get("path", ""))).resolve()
    if not path.is_file():
        raise CorrectiveFacialActingError(f"{label} is missing: {path}")
    actual = _sha256(path)
    expected = str(reference.get("sha256", ""))
    if actual != expected:
        raise CorrectiveFacialActingError(f"{label} SHA-256 mismatch: {actual} != {expected}")
    return path


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise CorrectiveFacialActingError(f"{label} mismatch: {actual!r} != {expected!r}")


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_equal(_canonical_hash(contract), _PINNED_CONTRACT_CANONICAL_SHA256, "complete Phase33 v2 contract")
    _require_equal(contract.get("contract_version"), 1, "contract version")
    _require_equal(contract.get("contract_id"), "june_oxley_phase33_close_facial_acting_v2", "contract id")
    _require_equal(contract.get("delivery_attempt_version"), 2, "delivery attempt")
    _require_equal(contract.get("cash_cost"), 0, "cash cost")
    _require_equal(contract.get("paid_runtime_dependency"), False, "paid dependency")
    _require_equal(contract.get("network_runtime_required"), False, "network dependency")
    _require_equal(contract["promotion_policy"]["accepted_delivery_publication_allowed"], False, "promotion policy")
    corrective = contract["corrective_compositing"]
    _require_equal(corrective["base"], "authored_gs070_plate", "corrective base")
    _require_equal(corrective["neutral_and_x_change_source_pixels"], False, "neutral policy")
    _require_equal(corrective["mouth_owns_expression_overlap"], True, "overlap owner")
    _require_equal(corrective["rgb_crop_painter_order_allowed"], False, "painter order")
    _require_equal(corrective["resample_count_after_feature_composite"], 1, "resample count")
    _require_equal(set(corrective["mouth_state_weights"]), set("ABCDEFGHX"), "mouth weights")
    _require_equal(corrective["mouth_state_weights"]["X"], 0.0, "X weight")
    _require_equal(
        set(corrective["expression_state_weights"]),
        {"neutral", "blink", "squint", "brow_raise", "brow_knit", "concern", "warm_eyes", "gaze_down", "compassion"},
        "expression weights",
    )
    _require_equal(corrective["expression_state_weights"]["neutral"], 0.0, "neutral weight")
    _require_equal(
        tuple(contract["inherited_clock"].values()),
        (1920, 1080, 30, 228, 7.6, 48000, 364800, 1600),
        "inherited clock",
    )
    _require_equal(contract["performance"]["review_frames"], list(REVIEW_FRAMES), "review frames")
    _require_equal(contract["delivery"]["one_video_encode_without_retry"], True, "single encode")
    _require_equal(contract["delivery"]["staged_atomic_directory_publication"], True, "atomic publication")
    _require_equal(contract["failure_policy"]["preview_required_before_encode"], True, "preview policy")
    _require_equal(contract["failure_policy"]["automatic_reencode_allowed"], False, "retry policy")
    paths = {name: _locked_path(reference, name) for name, reference in contract["locks"].items()}
    rejected = json.loads(paths["rejected_delivery_v1"].read_text(encoding="utf-8"))
    _require_equal(rejected.get("status"), "machine_passed_ai_visual_review_rejected", "v1 rejection")
    _require_equal(rejected.get("promotion_allowed"), False, "v1 promotion")


def load_corrective_contract(path: str | Path) -> dict[str, Any]:
    source = Path(path).resolve()
    contract = json.loads(source.read_text(encoding="utf-8"))
    _validate_contract(contract)
    return contract


def _effective_contract(contract: dict[str, Any], base_contract: dict[str, Any]) -> dict[str, Any]:
    effective = deepcopy(base_contract)
    effective["contract_id"] = contract["contract_id"]
    effective["classification"] = contract["classification"]
    effective["delivery"] = deepcopy(contract["delivery"])
    effective["decoded_quality_gate"] = deepcopy(contract["decoded_quality_gate"])
    effective["known_limitations"] = deepcopy(contract["known_limitations"])
    return effective


def _state_delta(
    patches: dict[str, Image.Image],
    base_patch: np.ndarray,
    entry: dict[str, Any],
    weights: dict[str, float],
    *,
    from_key: str,
    to_key: str,
) -> np.ndarray:
    from_state = str(entry[from_key])
    to_state = str(entry[to_key])
    amount = float(entry["blend"])
    from_delta = (
        np.asarray(patches[from_state], dtype=np.float32) - base_patch
    ) * float(weights[from_state])
    to_delta = (
        np.asarray(patches[to_state], dtype=np.float32) - base_patch
    ) * float(weights[to_state])
    return from_delta * (1.0 - amount) + to_delta * amount


def _feature_composite(
    prepared: PreparedCorrectiveShot,
    frame_index: int,
) -> tuple[Image.Image, dict[str, Any]]:
    base = prepared.base
    index = frame_index - 1
    policy = prepared.contract["corrective_compositing"]
    plate = np.asarray(base.sources["plate"], dtype=np.float32)
    result = plate.copy()
    mouth_box = tuple(int(value) for value in base.sources["plate_mouth_box"])
    eye_box = tuple(int(value) for value in base.sources["plate_expression_box"])
    mouth_alpha_local = np.asarray(base.sources["viseme_mask"], dtype=np.float32) / 255.0
    eye_alpha_local = np.asarray(base.sources["expression_mask"], dtype=np.float32) / 255.0
    mouth_support = mouth_alpha_local > 0.0
    eye_support = eye_alpha_local > 0.0
    mouth_alpha = np.zeros(plate.shape[:2], dtype=np.float32)
    eye_alpha = np.zeros(plate.shape[:2], dtype=np.float32)
    mouth_alpha[mouth_box[1] : mouth_box[3], mouth_box[0] : mouth_box[2]] = mouth_alpha_local
    eye_alpha[eye_box[1] : eye_box[3], eye_box[0] : eye_box[2]] = eye_alpha_local
    raw_overlap = (mouth_alpha > 0.0) & (eye_alpha > 0.0)
    owned_eye_alpha = np.where(mouth_alpha > 0.0, 0.0, eye_alpha)

    mouth_delta = _state_delta(
        base.sources["viseme_patches"],
        plate[mouth_box[1] : mouth_box[3], mouth_box[0] : mouth_box[2]],
        base.visemes[index],
        policy["mouth_state_weights"],
        from_key="from_shape",
        to_key="to_shape",
    )
    eye_delta = _state_delta(
        base.sources["expression_patches"],
        plate[eye_box[1] : eye_box[3], eye_box[0] : eye_box[2]],
        base.expressions[index],
        policy["expression_state_weights"],
        from_key="from_state",
        to_key="to_state",
    )
    eye_target = result[eye_box[1] : eye_box[3], eye_box[0] : eye_box[2]]
    eye_owned_local = owned_eye_alpha[eye_box[1] : eye_box[3], eye_box[0] : eye_box[2]]
    eye_target += eye_delta * eye_owned_local[:, :, None]
    mouth_target = result[mouth_box[1] : mouth_box[3], mouth_box[0] : mouth_box[2]]
    mouth_target += mouth_delta * mouth_alpha_local[:, :, None]
    result = np.clip(np.rint(result), 0, 255).astype(np.uint8)
    changed = np.any(result != plate.astype(np.uint8), axis=2)
    owned_support = (mouth_alpha > 0.0) | (owned_eye_alpha > 0.0)
    metrics = {
        "raw_feature_overlap_pixel_count": int(np.count_nonzero(raw_overlap)),
        "multiply_owned_overlap_pixel_count": int(np.count_nonzero((mouth_alpha > 0.0) & (owned_eye_alpha > 0.0))),
        "changed_pixels_outside_owned_feature_support": int(np.count_nonzero(changed & ~owned_support)),
        "changed_pixel_count": int(np.count_nonzero(changed)),
        "mouth_delta": mouth_delta,
        "expression_delta": eye_delta,
        "mouth_support_local": mouth_support,
        "expression_support_local": eye_support,
    }
    return Image.fromarray(result, "RGB"), metrics


def compose_corrective_frame(prepared: PreparedCorrectiveShot, frame_index: int) -> Image.Image:
    if not 1 <= int(frame_index) <= 228:
        raise CorrectiveFacialActingError("Phase33 v2 frame index must be between 1 and 228")
    base = prepared.base
    index = int(frame_index) - 1
    contract = base.sources["contract"]
    motion = base.motion[index]
    frame, _ = _feature_composite(prepared, int(frame_index))
    regions = contract["rig_regions"]
    _warp_region(
        frame,
        regions["shoulders"],
        dx=float(motion["shoulder_x_px"]),
        dy=float(motion["breath_y_px"]),
        scale_y=1.0 + float(motion["breath_y_px"]) / 900.0,
    )
    secondary = base.motion_metadata["secondary_motion"]
    chime = secondary.get("wind_chime") or {}
    period = max(0.5, float(chime.get("period_seconds", 3.1)))
    chime_dx = float(chime.get("amplitude_px", 0.0)) * math.sin(
        frame_index / 30 / period * math.tau + float(chime.get("phase", 0.0))
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
        * math.sin(frame_index / 30 / lantern_period * math.tau + float(lantern.get("phase", 0.0)))
    )
    _lantern_glow(frame, regions["lantern"], max(0.0, glow))
    _secondary_overlay(frame, frame_index, 30, regions, secondary)
    return _camera_frame(frame, float(motion["camera_push"]), contract)


def _corrective_measurements(prepared: PreparedCorrectiveShot) -> dict[str, Any]:
    frames = []
    previous_mouth: np.ndarray | None = None
    previous_expression: np.ndarray | None = None
    mouth_step = 0.0
    expression_step = 0.0
    changed_outside = 0
    non_x_observed = 0
    overlap = 0
    multiply_owned = 0
    for frame_index in range(1, 229):
        _, metrics = _feature_composite(prepared, frame_index)
        frames.append(metrics)
        mouth = metrics["mouth_delta"]
        expression = metrics["expression_delta"]
        if previous_mouth is not None:
            mouth_step = max(
                mouth_step,
                float(np.mean(np.abs(mouth - previous_mouth)[metrics["mouth_support_local"]])),
            )
            expression_step = max(
                expression_step,
                float(np.mean(np.abs(expression - previous_expression)[metrics["expression_support_local"]])),
            )
        if prepared.base.visemes[frame_index - 1]["to_shape"] != "X" and float(
            np.mean(np.abs(mouth)[metrics["mouth_support_local"]])
        ) > 0.5:
            non_x_observed += 1
        previous_mouth = mouth
        previous_expression = expression
        changed_outside = max(changed_outside, metrics["changed_pixels_outside_owned_feature_support"])
        overlap = max(overlap, metrics["raw_feature_overlap_pixel_count"])
        multiply_owned = max(multiply_owned, metrics["multiply_owned_overlap_pixel_count"])

    blink_index = next(
        index
        for index, entry in enumerate(prepared.base.expressions)
        if entry["to_state"] == "blink" and float(entry["blend"]) >= 1.0
    )
    blink_delta = frames[blink_index]["expression_delta"]
    support = frames[blink_index]["expression_support_local"]
    middle = blink_delta.shape[1] // 2
    left = support.copy()
    left[:, middle:] = False
    right = support.copy()
    right[:, :middle] = False
    blink_gray = np.mean(np.abs(blink_delta), axis=2)
    bilateral = min(float(np.mean(blink_gray[left])), float(np.mean(blink_gray[right])))

    head_box = (330, 20, 875, 610)
    plate_shape = np.asarray(prepared.base.sources["plate"]).shape
    stable = np.zeros(plate_shape[:2], dtype=bool)
    stable[head_box[1] : head_box[3], head_box[0] : head_box[2]] = True
    mouth_box = prepared.base.sources["plate_mouth_box"]
    eye_box = prepared.base.sources["plate_expression_box"]
    mouth_mask = np.asarray(prepared.base.sources["viseme_mask"], dtype=np.uint8) > 0
    eye_mask = np.asarray(prepared.base.sources["expression_mask"], dtype=np.uint8) > 0
    stable[mouth_box[1] : mouth_box[3], mouth_box[0] : mouth_box[2]] &= ~mouth_mask
    stable[eye_box[1] : eye_box[3], eye_box[0] : eye_box[2]] &= ~eye_mask
    return {
        "neutral_source_changed_pixels": frames[0]["changed_pixel_count"],
        "x_source_changed_pixels": int(
            np.count_nonzero(np.any(np.abs(frames[-1]["mouth_delta"]) > 0.5, axis=2))
        ),
        "feature_overlap_pixel_count": overlap,
        "multiply_owned_overlap_pixels": multiply_owned,
        "stable_identity_pixels": int(np.count_nonzero(stable)),
        "maximum_changed_pixels_outside_owned_feature_support": changed_outside,
        "bilateral_blink_mean_absolute_delta": bilateral,
        "non_x_observed_frame_count": non_x_observed,
        "maximum_adjacent_mouth_corrective_mean_absolute_delta": mouth_step,
        "maximum_adjacent_expression_corrective_mean_absolute_delta": expression_step,
    }


def _corrective_gates(contract: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    gates = contract["corrective_quality_gates"]
    return [
        v1._gate("corrective.neutral_exact", metrics["neutral_source_changed_pixels"], "==", gates["required_neutral_source_changed_pixels"]),
        v1._gate("corrective.x_exact", metrics["x_source_changed_pixels"], "==", gates["required_x_source_changed_pixels"]),
        v1._gate("corrective.overlap_evaluated", metrics["feature_overlap_pixel_count"], ">=", gates["required_feature_overlap_pixels"]),
        v1._gate("corrective.single_overlap_owner", metrics["multiply_owned_overlap_pixels"], "==", gates["required_multiply_owned_overlap_pixels"]),
        v1._gate("corrective.stable_identity_nonvacuous", metrics["stable_identity_pixels"], ">=", gates["minimum_stable_identity_pixels"]),
        v1._gate("corrective.no_out_of_scope_change", metrics["maximum_changed_pixels_outside_owned_feature_support"], "<=", gates["maximum_changed_pixels_outside_owned_feature_support"]),
        v1._gate("corrective.bilateral_blink", metrics["bilateral_blink_mean_absolute_delta"], ">=", gates["minimum_bilateral_blink_mean_absolute_delta"]),
        v1._gate("corrective.observed_mouth_motion", metrics["non_x_observed_frame_count"], ">=", gates["minimum_non_x_observed_frame_count"]),
        v1._gate("corrective.mouth_step", metrics["maximum_adjacent_mouth_corrective_mean_absolute_delta"], "<=", gates["maximum_adjacent_mouth_corrective_mean_absolute_delta"]),
        v1._gate("corrective.expression_step", metrics["maximum_adjacent_expression_corrective_mean_absolute_delta"], "<=", gates["maximum_adjacent_expression_corrective_mean_absolute_delta"]),
    ]


def prepare_corrective_shot(contract_path: str | Path) -> PreparedCorrectiveShot:
    contract = load_corrective_contract(contract_path)
    base_path = _locked_path(contract["locks"]["base_contract_v1"], "base contract v1")
    base = v1.prepare_close_facial_acting(base_path)
    prepared = PreparedCorrectiveShot(
        contract=contract,
        effective_contract=_effective_contract(contract, base.contract),
        base=base,
        preflight_measurements={},
    )
    metrics = _corrective_measurements(prepared)
    gates = _corrective_gates(contract, metrics)
    if not all(row["passed"] for row in gates):
        failed = [row["id"] for row in gates if not row["passed"]]
        raise CorrectiveFacialActingError(f"Phase33 v2 corrective gates failed: {failed}")
    prepared.preflight_measurements = {**metrics, "gates": gates}
    return prepared


def write_unencoded_preview(prepared: PreparedCorrectiveShot, path: str | Path) -> Path:
    destination = Path(path).resolve()
    if destination.exists():
        raise CorrectiveFacialActingError(f"immutable preview already exists: {destination}")
    sheet = Image.new("RGB", (1920, 1080), (12, 12, 12))
    for index, frame_number in enumerate(REVIEW_FRAMES):
        frame = compose_corrective_frame(prepared, frame_number).resize((480, 270), Image.Resampling.LANCZOS)
        row, column = divmod(index, 4)
        sheet.paste(frame, (column * 480, row * 270))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, 785, 28), fill=(12, 12, 12))
    draw.text((8, 7), "UNENCODED PHASE 33 V2 CORRECTIVE PREVIEW | f1 12 24 25 46 79 82 111 132 162 168 180 192 201 202 228", fill=(245, 245, 245))
    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination)
    return destination


def _encode_once(
    prepared: PreparedCorrectiveShot,
    stage: Path,
    *,
    ffmpeg: str,
) -> tuple[Path, dict[int, np.ndarray]]:
    delivery = prepared.contract["delivery"]
    encoding = delivery["encoding"]
    video = stage / delivery["video_filename"]
    partial = stage / (video.stem + ".partial.mp4")
    command = [
        ffmpeg, "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", "1920x1080", "-r", "30", "-i", "pipe:0",
        "-i", str(prepared.base.audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", str(encoding["implementation"]), "-preset", str(encoding["preset"]), "-tune", str(encoding["tune"]),
        "-crf", str(encoding["crf"]), "-pix_fmt", str(encoding["pixel_format"]), "-frames:v", "228",
        "-c:a", str(encoding["audio_codec"]), "-b:a", str(encoding["audio_bitrate"]), "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(partial),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise CorrectiveFacialActingError("unable to open Phase33 v2 FFmpeg pipe")
    expected: dict[int, np.ndarray] = {}
    try:
        for frame_index in range(1, 229):
            array = np.asarray(compose_corrective_frame(prepared, frame_index), dtype=np.uint8)
            process.stdin.write(array.tobytes())
            if frame_index in REVIEW_FRAMES:
                expected[frame_index] = array.copy()
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    if return_code != 0:
        raise CorrectiveFacialActingError(f"Phase33 v2 encode failed: {error[-2000:]}")
    if not partial.is_file() or partial.stat().st_size <= 0:
        raise CorrectiveFacialActingError("Phase33 v2 encoder produced no candidate")
    partial.replace(video)
    return video, expected


def _rename_review_artifacts(stage: Path, review: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "contact_sheet": contract["delivery"]["contact_sheet_filename"],
        "blink_strip": contract["delivery"]["blink_strip_filename"],
        "mouth_strip": contract["delivery"]["mouth_strip_filename"],
    }
    for key, filename in mapping.items():
        source = stage / review[key]["file"]
        destination = stage / filename
        source.replace(destination)
        review[key]["file"] = destination.name
        review[key]["sha256"] = _sha256(destination)
    return review


def _write_ab_vs_v1(
    stage: Path,
    decoded: dict[int, np.ndarray],
    baseline: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    expected = "a4dba16a07568ea01adad00134f020f9a9b75764621a26ee3763812ae37d2ca7"
    if _sha256(baseline) != expected:
        raise CorrectiveFacialActingError("Phase33 v1 A/B baseline hash changed")
    pairs = (1, 25, 46, 82, 111, 132, 162, 180, 202, 228)
    sheet = np.zeros((720, 1920, 3), dtype=np.uint8)
    capture = cv2.VideoCapture(str(baseline))
    for index, frame_number in enumerate(pairs):
        column = index % 5
        pair_row = index // 5
        y = pair_row * 360
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number - 1)
        ok, bgr = capture.read()
        if not ok:
            capture.release()
            raise CorrectiveFacialActingError("unable to decode Phase33 v1 baseline")
        old = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        left = cv2.resize(decoded[frame_number], (192, 180), interpolation=cv2.INTER_AREA)
        right = cv2.resize(old, (192, 180), interpolation=cv2.INTER_AREA)
        sheet[y : y + 180, column * 384 : column * 384 + 192] = left
        sheet[y : y + 180, column * 384 + 192 : (column + 1) * 384] = right
    capture.release()
    path = stage / contract["delivery"]["ab_sheet_filename"]
    Image.fromarray(sheet, "RGB").save(path)
    return {
        "file": path.name,
        "sha256": _sha256(path),
        "baseline_sha256": expected,
        "left_right_identity_hidden": True,
        "human_preference_required": True,
    }


def render_corrective_shot(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    preview_path: str | Path,
    baseline_v1: str | Path,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
) -> dict[str, Any]:
    prepared = prepare_corrective_shot(contract_path)
    preview = Path(preview_path).resolve()
    if not preview.is_file():
        raise CorrectiveFacialActingError("the locked unencoded v2 preview must exist before encode")
    output = Path(output_dir).resolve()
    if output.exists():
        raise CorrectiveFacialActingError(f"immutable Phase33 v2 output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = v1._executable(ffmpeg)
    ffprobe_bin = v1._executable(ffprobe)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    encode_process_count = 0
    try:
        captions = stage / prepared.contract["delivery"]["caption_filename"]
        v1._write_captions(prepared.effective_contract, captions)
        encode_process_count += 1
        video, expected = _encode_once(prepared, stage, ffmpeg=ffmpeg_bin)
        decoded_metrics, decoded = v1._decode_and_audit(
            video,
            expected,
            prepared.effective_contract,
            ffmpeg=ffmpeg_bin,
            ffprobe=ffprobe_bin,
        )
        delivery_gates = v1._delivery_gates(prepared.effective_contract, decoded_metrics)
        if not all(row["passed"] for row in delivery_gates):
            failed = [row["id"] for row in delivery_gates if not row["passed"]]
            raise CorrectiveFacialActingError(f"Phase33 v2 decoded gates failed: {failed}")
        review = _rename_review_artifacts(
            stage,
            v1._write_review_artifacts(stage, decoded, prepared.effective_contract),
            prepared.contract,
        )
        ab = _write_ab_vs_v1(stage, decoded, Path(baseline_v1).resolve(), prepared.contract)
        gates = prepared.preflight_measurements["gates"] + delivery_gates
        report = {
            "contract_version": 1,
            "gate": "phase33_plate_neutral_corrective_facial_acting_prototype",
            "classification": prepared.contract["classification"],
            "audience_status": prepared.contract["promotion_policy"]["audience_status"],
            "accepted_production_delivery": False,
            "human_review_required": True,
            "contract": {
                "path": str(CONTRACT_RELATIVE_PATH).replace("\\", "/"),
                "raw_sha256": _sha256((REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve()),
                "canonical_sha256": _canonical_hash(prepared.contract),
            },
            "implementation": {
                "path": str(IMPLEMENTATION_RELATIVE_PATH).replace("\\", "/"),
                "sha256": _sha256((REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH).resolve()),
            },
            "corrective_policy": prepared.contract["corrective_compositing"],
            "preflight_measurements": {
                key: value for key, value in prepared.preflight_measurements.items() if key != "gates"
            },
            "decoded_quality": decoded_metrics,
            "review_artifacts": review,
            "blinded_ab_vs_v1": ab,
            "preview": {"file": preview.name, "sha256": _sha256(preview), "source": "unencoded_frames"},
            "gate_count": len(gates),
            "passed_gate_count": sum(row["passed"] for row in gates),
            "failed_gate_count": sum(not row["passed"] for row in gates),
            "gates": gates,
            "delivery": {
                "video": video.name,
                "video_sha256": _sha256(video),
                "video_bytes": video.stat().st_size,
                "caption_file": captions.name,
                "caption_sha256": _sha256(captions),
                "encoding_process_count": encode_process_count,
                "staged_atomic_publication": True,
            },
            "v1_disposition": {
                "status": "machine_passed_ai_visual_review_rejected",
                "receipt_sha256": prepared.contract["locks"]["rejected_delivery_v1"]["sha256"],
                "video_sha256": "a4dba16a07568ea01adad00134f020f9a9b75764621a26ee3763812ae37d2ca7",
            },
            "known_limitations": prepared.contract["known_limitations"],
            "paid_runtime_dependency": False,
            "machine_passed": True,
        }
        report_path = stage / prepared.contract["delivery"]["report_filename"]
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        os.replace(stage, output)
        return report
    except BaseException:
        if encode_process_count and stage.exists():
            rejected = output.parent / f"{output.name}-rejected"
            if not rejected.exists():
                os.replace(stage, rejected)
        elif stage.exists():
            shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's Phase33 v2 corrective acting prototype")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--baseline-v1", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--write-preview", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    prepared = prepare_corrective_shot(args.contract)
    if args.write_preview:
        path = write_unencoded_preview(prepared, args.preview)
        payload: dict[str, Any] = {
            "preflight_passed": True,
            "preview": str(path),
            "preview_sha256": _sha256(path),
            "measurements": prepared.preflight_measurements,
        }
    elif args.preflight_only:
        payload = {"preflight_passed": True, "measurements": prepared.preflight_measurements}
    else:
        payload = render_corrective_shot(
            args.contract,
            args.output_dir,
            preview_path=args.preview,
            baseline_v1=args.baseline_v1,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
        )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
