"""Unencoded Phase35 dialogue/body/camera integration with Candidate09 blink timing."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, replace
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import tempfile
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps, __version__ as PILLOW_VERSION

from pipeline import cartoon_source_textured_face as phase34
from pipeline import cartoon_source_textured_face_v2 as phase34_candidate09
from pipeline.cartoon_expression_atlas import expression_performance_plan
from pipeline.cartoon_hero_scene import (
    _camera_frame,
    _lantern_glow,
    _secondary_overlay,
    _warp_region,
    load_body_motion_contract,
)
from pipeline.cartoon_viseme_atlas import performance_viseme_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase35_source_textured_direct_address_v2.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_source_textured_direct_address.py"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "5069774dfb92511a5adc291f7d09c755f0b51c1ea2ed1bae5356bcaab597d25f"
VISEME_NAMES = tuple("ABCDEFGHX")
CANDIDATE09_BLINK_CURVE = (0.0, 0.25, 0.5, 0.75, 1.0, 0.75, 0.5, 0.25, 0.0)


class SourceTexturedDirectAddressError(RuntimeError):
    pass


@dataclass
class PreparedDirectAddress:
    contract: dict[str, Any]
    contract_path: Path
    face: phase34_candidate09.PreparedSourceTexturedFace
    candidate08_face: phase34.PreparedSourceTexturedFace
    candidate01_contract: dict[str, Any]
    scene_contract: dict[str, Any]
    visemes: list[dict[str, Any]]
    expressions: list[dict[str, Any]]
    motion: list[dict[str, float]]
    viseme_metadata: dict[str, Any]
    expression_metadata: dict[str, Any]
    motion_metadata: dict[str, Any]
    dialogue_path: Path
    mix_path: Path
    adapter_cache: dict[tuple[Any, ...], tuple[phase34_candidate09.PreparedSourceTexturedFace, int]]
    native_cache: dict[tuple[Any, ...], tuple[np.ndarray, phase34_candidate09.FrameEvidence]]
    candidate08_adapter_cache: dict[tuple[Any, ...], tuple[phase34.PreparedSourceTexturedFace, int]]
    candidate08_native_cache: dict[tuple[Any, ...], tuple[np.ndarray, phase34.FrameEvidence]]


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lf_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise SourceTexturedDirectAddressError(f"locked path escapes repository: {relative}") from exc
    if not path.is_file():
        raise SourceTexturedDirectAddressError(f"locked file is missing: {relative}")
    return path


def _locked_hash(reference: dict[str, Any]) -> str:
    path = _repo_path(str(reference["path"]))
    if reference.get("hash_domain") == "lf_normalized_text":
        return _lf_hash(path)
    return _sha256(path)


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SourceTexturedDirectAddressError(
            f"Phase35 contract mismatch for {label}: {actual!r} != {expected!r}"
        )


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_equal(contract["contract_version"], 2, "contract version")
    _require_equal(
        contract["contract_id"],
        "june_oxley_phase35_source_textured_direct_address_v2",
        "contract id",
    )
    _require_equal(contract["cash_cost"], 0, "cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "paid dependency")
    _require_equal(contract["network_runtime_required"], False, "network runtime")
    clock = contract["clock"]
    expected_clock = {
        "source_width": 1672,
        "source_height": 941,
        "output_width": 1920,
        "output_height": 1080,
        "fps": 30,
        "frame_count": 228,
        "duration_seconds": 7.6,
        "audio_sample_rate": 48000,
        "audio_sample_count": 364800,
        "audio_samples_per_frame": 1600,
    }
    _require_equal(clock, expected_clock, "production clock")
    representation = contract["representation"]
    _require_equal(representation["full_face_or_mouth_atlas_crossfade_allowed"], False, "atlas crossfade")
    _require_equal(representation["rejected_phase33_bitmap_expression_atlas_allowed"], False, "rejected expression atlas")
    _require_equal(representation["audio_or_video_encode_allowed"], False, "encode policy")
    _require_equal(representation["runtime_ai_generation_allowed"], False, "runtime generation")
    _require_equal(representation["reinforcement_learning_allowed"], False, "RL policy")
    _require_equal(contract["failure_policy"]["encode_on_preview_pass_allowed"], False, "preview encode policy")
    _require_equal(contract["promotion_policy"]["accepted_full_cartoon_production_delivery"], False, "promotion scope")
    required = list(contract["performance"]["required_review_frames"])
    if required != sorted(set(required)) or required[0] != 1 or required[-1] != 228:
        raise SourceTexturedDirectAddressError("review frames must be unique, sorted, and cover endpoints")
    expected_curve = list(CANDIDATE09_BLINK_CURVE)
    occupied: set[int] = set()
    curves = contract["performance"]["blink_curves"]
    _require_equal(len(curves), 2, "semantic blink curve count")
    for curve in curves:
        frames = [int(value) for value in curve["frames"]]
        closures = [float(value) for value in curve["closures"]]
        _require_equal(closures, expected_curve, f"{curve['id']} Candidate09-approved linear closure curve")
        if len(frames) != len(closures) or frames != list(range(frames[0], frames[-1] + 1)):
            raise SourceTexturedDirectAddressError(f"{curve['id']} frames must be one contiguous curve")
        if occupied.intersection(frames):
            raise SourceTexturedDirectAddressError("semantic blink curves overlap")
        occupied.update(frames)


def load_contract(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> tuple[dict[str, Any], Path]:
    source = Path(path).resolve()
    contract = json.loads(source.read_text(encoding="utf-8"))
    _validate_contract(contract)
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "canonical contract SHA-256")
    for name, reference in contract["locks"].items():
        _require_equal(_locked_hash(reference), reference["sha256"], f"locked {name} SHA-256")
    blink_policy = json.loads(
        _repo_path(contract["locks"]["phase34_default_blink_policy"]["path"]).read_text(encoding="utf-8")
    )
    _require_equal(
        blink_policy["status"],
        "approved_default_for_future_source_textured_facial_subsystem_reuse",
        "Candidate09 blink policy status",
    )
    _require_equal(
        blink_policy["closure_table"], list(CANDIDATE09_BLINK_CURVE),
        "Candidate09 blink policy closure table",
    )
    policy_review = blink_policy["review_receipt"]
    _require_equal(
        _lf_hash(_repo_path(policy_review["path"])),
        policy_review["lf_normalized_sha256"],
        "Candidate09 policy Claude review LF SHA-256",
    )
    policy_addendum = blink_policy["review_addendum"]
    _require_equal(
        _sha256(_repo_path(policy_addendum["path"])),
        policy_addendum["sha256"],
        "Candidate09 policy review addendum SHA-256",
    )
    return contract, source


def _capture_execution_state(
    contract: dict[str, Any], contract_path: Path,
) -> dict[str, Any]:
    on_disk = json.loads(contract_path.read_text(encoding="utf-8"))
    state = {
        "contract_raw_sha256": _sha256(contract_path),
        "contract_canonical_sha256": _canonical_hash(on_disk),
        "implementation_sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
        "lock_sha256": {
            name: _locked_hash(reference)
            for name, reference in contract["locks"].items()
        },
    }
    _require_equal(
        state["contract_canonical_sha256"], EXPECTED_CONTRACT_CANONICAL_SHA256,
        "captured canonical contract SHA-256",
    )
    for name, reference in contract["locks"].items():
        _require_equal(
            state["lock_sha256"][name], reference["sha256"],
            f"captured locked {name} SHA-256",
        )
    return state


def _execution_state_mismatches(
    captured: dict[str, Any], contract: dict[str, Any], contract_path: Path,
) -> list[str]:
    try:
        current = _capture_execution_state(contract, contract_path)
    except BaseException as exc:
        return [f"execution_state_unreadable:{type(exc).__name__}"]
    mismatches: list[str] = []
    for name in ("contract_raw_sha256", "contract_canonical_sha256", "implementation_sha256"):
        if current[name] != captured[name]:
            mismatches.append(name)
    for name, expected in captured["lock_sha256"].items():
        if current["lock_sha256"].get(name) != expected:
            mismatches.append(f"lock:{name}")
    return mismatches


def _wave_probe(path: Path) -> dict[str, int]:
    """Read the locked PCM WAV clock without an optional audio dependency.

    Python 3.11's :mod:`wave` rejects WAVE_FORMAT_EXTENSIBLE even when its
    subtype is ordinary PCM.  The Phase35 sources use that standards-compliant
    wrapper for 24-bit PCM, so validate the small RIFF/fmt/data surface needed
    by the render contract directly.
    """

    def fail(detail: str) -> None:
        raise SourceTexturedDirectAddressError(f"invalid PCM WAV {path.name}: {detail}")

    file_size = path.stat().st_size
    with path.open("rb") as audio:
        header = audio.read(12)
        if len(header) != 12:
            fail("truncated RIFF header")
        riff_id, riff_size, wave_id = struct.unpack("<4sI4s", header)
        if riff_id != b"RIFF" or wave_id != b"WAVE":
            fail("missing RIFF/WAVE signature")
        riff_end = riff_size + 8
        if riff_end != file_size:
            fail("declared RIFF size does not match file length")

        fmt_payload: bytes | None = None
        data_size: int | None = None
        while audio.tell() < riff_end:
            if riff_end - audio.tell() < 8:
                fail("truncated chunk header")
            chunk_header = audio.read(8)
            if len(chunk_header) != 8:
                fail("truncated chunk header")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            chunk_end = audio.tell() + chunk_size
            padded_chunk_end = chunk_end + (chunk_size % 2)
            if padded_chunk_end > riff_end:
                fail(f"{chunk_id!r} chunk exceeds the RIFF container")
            if chunk_id == b"fmt ":
                if fmt_payload is not None:
                    fail("duplicate fmt chunk")
                fmt_payload = audio.read(chunk_size)
            else:
                if chunk_id == b"data":
                    if data_size is not None:
                        fail("duplicate data chunk")
                    data_size = chunk_size
                audio.seek(chunk_size, os.SEEK_CUR)
            if chunk_size % 2:
                if audio.read(1) == b"":
                    fail(f"{chunk_id!r} chunk is missing its pad byte")

    if fmt_payload is None or len(fmt_payload) < 16:
        fail("missing or truncated fmt chunk")
    if data_size is None:
        fail("missing data chunk")

    format_tag, channels, sample_rate, byte_rate, block_align, bits_per_sample = (
        struct.unpack("<HHIIHH", fmt_payload[:16])
    )
    if format_tag == 0xFFFE:
        if len(fmt_payload) < 40:
            fail("truncated WAVE_FORMAT_EXTENSIBLE fmt chunk")
        extension_size = struct.unpack_from("<H", fmt_payload, 16)[0]
        valid_bits = struct.unpack_from("<H", fmt_payload, 18)[0]
        pcm_subformat = bytes.fromhex("0100000000001000800000aa00389b71")
        if extension_size < 22 or 18 + extension_size > len(fmt_payload):
            fail("truncated WAVE_FORMAT_EXTENSIBLE extension")
        if fmt_payload[24:40] != pcm_subformat:
            fail("WAVE_FORMAT_EXTENSIBLE subtype is not PCM")
        if valid_bits != bits_per_sample:
            fail("valid bits do not match the PCM container width")
    elif format_tag != 1:
        fail(f"unsupported compression format {format_tag}")

    if channels <= 0 or sample_rate <= 0 or bits_per_sample <= 0 or bits_per_sample % 8:
        fail("invalid PCM channel, sample-rate, or sample-width field")
    sample_width = bits_per_sample // 8
    if block_align <= 0 or block_align != channels * sample_width:
        fail("block alignment does not match PCM geometry")
    if byte_rate != sample_rate * block_align:
        fail("byte rate does not match PCM geometry")
    if data_size % block_align:
        fail("data chunk is not aligned to a complete sample frame")

    return {
        "sample_rate": int(sample_rate),
        "channels": int(channels),
        "sample_width": int(sample_width),
        "sample_count": int(data_size // block_align),
    }


def _ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def _fraction_for_eased_value(value: float, *, maximum_denominator: int = 12) -> tuple[int, int]:
    for denominator in range(1, maximum_denominator + 1):
        for numerator in range(1, denominator + 1):
            if math.isclose(_ease(numerator / denominator), value, abs_tol=1e-9):
                return numerator, denominator
    raise SourceTexturedDirectAddressError(
        f"timing blend {value!r} is not representable by the locked Phase34 cubic control"
    )


def production_blink_closure(contract: dict[str, Any], frame_number: int) -> float:
    for curve in contract["performance"]["blink_curves"]:
        frames = curve["frames"]
        if int(frames[0]) <= frame_number <= int(frames[-1]):
            return float(curve["closures"][frame_number - int(frames[0])])
    return 0.0


def _synthetic_blink_schedule(closure: float) -> tuple[int, dict[str, float]]:
    if not 0.0 <= closure <= 1.0:
        raise SourceTexturedDirectAddressError(f"blink closure is outside [0, 1]: {closure}")
    render_frame = 2
    return render_frame, {str(render_frame): float(closure)}


def _synthetic_viseme_schedule(
    viseme: dict[str, Any], render_frame: int,
) -> list[dict[str, Any]]:
    left = str(viseme["from_shape"])
    right = str(viseme["to_shape"])
    if left not in VISEME_NAMES or right not in VISEME_NAMES:
        raise SourceTexturedDirectAddressError("dialogue requested an unsupported viseme")
    blend = float(viseme["blend"])
    if left == right or math.isclose(blend, 1.0, abs_tol=1e-9):
        return [{"frame": 1, "pose": right}, {"frame": 96, "pose": right}]
    numerator, denominator = _fraction_for_eased_value(blend)
    left_frame = render_frame - numerator
    right_frame = left_frame + denominator
    if left_frame < 1 or right_frame > 96:
        shift = max(0, 1 - left_frame)
        left_frame += shift
        right_frame += shift
        render_frame += shift
    if not left_frame <= render_frame <= right_frame <= 96:
        raise SourceTexturedDirectAddressError("synthetic viseme schedule left Phase34's clock")
    return [{"frame": left_frame, "pose": left}, {"frame": right_frame, "pose": right}]


def _adapter_key(viseme: dict[str, Any], closure: float) -> tuple[Any, ...]:
    return (
        viseme["from_shape"], viseme["to_shape"], round(float(viseme["blend"]), 12),
        round(float(closure), 12),
    )


def controlled_native_frame(
    prepared: PreparedDirectAddress,
    viseme: dict[str, Any],
    closure: float,
) -> tuple[np.ndarray, phase34_candidate09.FrameEvidence]:
    key = _adapter_key(viseme, closure)
    rendered = prepared.native_cache.get(key)
    if rendered is not None:
        return rendered
    cached = prepared.adapter_cache.get(key)
    if cached is None:
        render_frame, blink_table = _synthetic_blink_schedule(closure)
        contract = deepcopy(prepared.face.contract)
        contract["performance"]["viseme_keyframes"] = _synthetic_viseme_schedule(
            viseme, render_frame,
        )
        contract["performance"]["blink_closure_by_frame"] = blink_table
        adapted = replace(prepared.face, contract=contract)
        cached = (adapted, render_frame)
        prepared.adapter_cache[key] = cached
    native, evidence = phase34_candidate09._native_frame(cached[0], cached[1])
    if not math.isclose(evidence.blink_closure, closure, abs_tol=1e-9):
        raise SourceTexturedDirectAddressError(
            f"semantic blink adapter mismatch: {evidence.blink_closure} != {closure}"
        )
    if len(prepared.native_cache) >= 12:
        prepared.native_cache.pop(next(iter(prepared.native_cache)))
    prepared.native_cache[key] = (native, evidence)
    return native, evidence


def _candidate08_synthetic_blink_schedule(
    closure: float,
) -> tuple[int, list[int], list[int]]:
    if math.isclose(closure, 0.0, abs_tol=1e-9):
        return 2, [10, 11], [10, 10]
    if math.isclose(closure, 1.0, abs_tol=1e-9):
        return 2, [1, 3], [2, 2]
    numerator, denominator = _fraction_for_eased_value(closure)
    return numerator + 1, [1, denominator + 1], [denominator + 1, denominator + 1]


def controlled_candidate08_native_frame(
    prepared: PreparedDirectAddress,
    viseme: dict[str, Any],
    closure: float,
) -> tuple[np.ndarray, phase34.FrameEvidence]:
    """Reconstruct Candidate01 exactly for the eight blink-only differential frames."""
    key = _adapter_key(viseme, closure)
    rendered = prepared.candidate08_native_cache.get(key)
    if rendered is not None:
        return rendered
    cached = prepared.candidate08_adapter_cache.get(key)
    if cached is None:
        render_frame, blink_frames, blink_max_frames = _candidate08_synthetic_blink_schedule(closure)
        contract = deepcopy(prepared.candidate08_face.contract)
        contract["performance"]["viseme_keyframes"] = _synthetic_viseme_schedule(
            viseme, render_frame,
        )
        contract["performance"]["blink_frames"] = blink_frames
        contract["performance"]["blink_max_frames"] = blink_max_frames
        adapted = replace(prepared.candidate08_face, contract=contract)
        cached = (adapted, render_frame)
        prepared.candidate08_adapter_cache[key] = cached
    native, evidence = phase34._native_frame(cached[0], cached[1])
    if not math.isclose(evidence.blink_closure, closure, abs_tol=1e-9):
        raise SourceTexturedDirectAddressError(
            f"Candidate01 blink adapter mismatch: {evidence.blink_closure} != {closure}"
        )
    if len(prepared.candidate08_native_cache) >= 12:
        prepared.candidate08_native_cache.pop(next(iter(prepared.candidate08_native_cache)))
    prepared.candidate08_native_cache[key] = (native, evidence)
    return native, evidence


def _load_scene_contract(contract: dict[str, Any]) -> dict[str, Any]:
    path = _repo_path(contract["locks"]["gs070_scene_contract"]["path"])
    scene = json.loads(path.read_text(encoding="utf-8"))
    _require_equal(scene["plate_id"], "june_golden_scene_gs070_resolution_plate", "scene plate id")
    _require_equal(scene["image"]["sha256"], contract["locks"]["gs070_plate"]["sha256"], "scene plate hash")
    _require_equal(scene["output"]["width"], 1920, "scene width")
    _require_equal(scene["output"]["height"], 1080, "scene height")
    _require_equal(scene["output"]["fps"], 30, "scene fps")
    _require_equal(scene["output"]["frame_count"], 228, "scene frame count")
    return scene


def _prepare_phase34_face(contract_path: Path, renderer: Any, provenance: str) -> Any:
    """Load one hash-locked Phase34 face implementation without rerunning its audition."""
    contract = renderer.load_contract(contract_path)
    phase33_contract = renderer._resolve_repo_path(contract["locks"]["phase33_v3_contract"]["path"])
    base = renderer.phase33.prepare_semantic_face(phase33_contract)
    clock = contract["clock"]
    if base.plate.shape != (clock["source_height"], clock["source_width"], 3):
        raise SourceTexturedDirectAddressError(f"Phase34 plate dimensions changed: {base.plate.shape}")
    source_points, triangles = renderer._cage(contract)
    support = np.zeros(base.plate.shape[:2], dtype=np.uint8)
    x1, y1, x2, y2 = contract["semantic_geometry_native_xy"]["feature_support_box"]
    support[y1:y2, x1:x2] = 255
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = contract["semantic_geometry_native_xy"][eye_name]
        support = cv2.bitwise_or(
            support,
            renderer.phase33._ellipse_mask(
                base.plate.shape[:2],
                tuple(eye["center"]),
                (eye["radius"][0] + 7, eye["radius"][1] + 7),
            ),
        )
    oral_cells = renderer._load_oral_cells(
        renderer._resolve_repo_path(contract["locks"]["oral_interior_atlas"]["path"])
    )
    moustache_alpha = cv2.GaussianBlur(base.moustache_mask, (0, 0), sigmaX=0.75, sigmaY=0.75)
    beard_alpha = cv2.GaussianBlur(base.beard_mask, (0, 0), sigmaX=0.75, sigmaY=0.75)
    return renderer.PreparedSourceTexturedFace(
        contract,
        contract_path,
        base,
        source_points,
        triangles,
        support > 0,
        oral_cells,
        moustache_alpha,
        beard_alpha,
        {provenance: True},
        {},
    )


def prepare_direct_address(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
) -> PreparedDirectAddress:
    contract, contract_path = load_contract(path)
    scene = _load_scene_contract(contract)
    face = _prepare_phase34_face(
        _repo_path(contract["locks"]["phase34_contract"]["path"]),
        phase34_candidate09,
        "inherited_from_locked_candidate08_acceptance_and_candidate09_blink_review",
    )
    candidate08_face = _prepare_phase34_face(
        _repo_path(contract["locks"]["phase34_candidate08_contract"]["path"]),
        phase34,
        "inherited_from_locked_candidate08_acceptance",
    )
    if phase34._raw_frame_hash(face.plate) != phase34._raw_frame_hash(
        np.asarray(Image.open(_repo_path(contract["locks"]["gs070_plate"]["path"])).convert("RGB"))
    ):
        raise SourceTexturedDirectAddressError("Phase34 and Phase35 GS070 plate pixels differ")

    cue_path = _repo_path(contract["locks"]["viseme_cues"]["path"])
    expression_path = _repo_path(contract["locks"]["expression_cues"]["path"])
    motion_path = _repo_path(contract["locks"]["body_motion"]["path"])
    viseme_metadata, visemes = performance_viseme_plan(
        cue_path,
        fps=int(contract["clock"]["fps"]),
        transition_frames=int(contract["performance"]["viseme_transition_frames"]),
    )
    expression_metadata, expressions = expression_performance_plan(
        expression_path,
        expected_atlas_id="june_oxley_canonical_expressions",
    )
    motion_metadata, motion = load_body_motion_contract(motion_path, hero_contract=scene)
    frame_count = int(contract["clock"]["frame_count"])
    _require_equal({len(visemes), len(expressions), len(motion)}, {frame_count}, "shared frame clock")
    _require_equal(viseme_metadata["shapes"], contract["performance"]["required_cue_visemes"], "cue visemes")
    _require_equal(float(viseme_metadata["duration_seconds"]), 7.6, "viseme duration")
    _require_equal(float(expression_metadata["duration_seconds"]), 7.6, "expression duration")
    _require_equal(float(motion_metadata["duration_seconds"]), 7.6, "motion duration")

    dialogue = _repo_path(contract["locks"]["dialogue_audio"]["path"])
    mix = _repo_path(contract["locks"]["delivery_mix"]["path"])
    dialogue_probe = _wave_probe(dialogue)
    mix_probe = _wave_probe(mix)
    clock = contract["clock"]
    _require_equal(dialogue_probe["sample_rate"], clock["audio_sample_rate"], "dialogue sample rate")
    _require_equal(dialogue_probe["sample_count"], clock["audio_sample_count"], "dialogue sample count")
    _require_equal(dialogue_probe["channels"], 1, "dialogue channels")
    _require_equal(dialogue_probe["sample_width"], 3, "dialogue sample width")
    _require_equal(mix_probe["sample_rate"], clock["audio_sample_rate"], "mix sample rate")
    _require_equal(mix_probe["sample_count"], clock["audio_sample_count"], "mix sample count")
    _require_equal(mix_probe["channels"], 2, "mix channels")
    _require_equal(mix_probe["sample_width"], 3, "mix sample width")
    cue_payload = json.loads(cue_path.read_text(encoding="utf-8"))
    metadata = cue_payload["metadata"]
    _require_equal(metadata["sourceAudioSha256"], contract["locks"]["dialogue_audio"]["sha256"], "cue dialogue hash")
    _require_equal(metadata["deliveryMixSha256"], contract["locks"]["delivery_mix"]["sha256"], "cue mix hash")
    return PreparedDirectAddress(
        contract=contract,
        contract_path=contract_path,
        face=face,
        candidate08_face=candidate08_face,
        candidate01_contract=json.loads(
            _repo_path(contract["locks"]["phase35_candidate01_contract"]["path"]).read_text(encoding="utf-8")
        ),
        scene_contract=scene,
        visemes=visemes,
        expressions=expressions,
        motion=motion,
        viseme_metadata=viseme_metadata,
        expression_metadata=expression_metadata,
        motion_metadata=motion_metadata,
        dialogue_path=dialogue,
        mix_path=mix,
        adapter_cache={},
        native_cache={},
        candidate08_adapter_cache={},
        candidate08_native_cache={},
    )


def compose_direct_address_frame(
    prepared: PreparedDirectAddress,
    frame_number: int,
    *,
    candidate01: bool = False,
) -> tuple[Image.Image, np.ndarray, Any]:
    frame_count = int(prepared.contract["clock"]["frame_count"])
    if not 1 <= frame_number <= frame_count:
        raise SourceTexturedDirectAddressError(f"frame number out of range: {frame_number}")
    index = frame_number - 1
    if candidate01:
        closure = production_blink_closure(prepared.candidate01_contract, frame_number)
        native, evidence = controlled_candidate08_native_frame(
            prepared, prepared.visemes[index], closure,
        )
        face = prepared.candidate08_face
    else:
        closure = production_blink_closure(prepared.contract, frame_number)
        native, evidence = controlled_native_frame(prepared, prepared.visemes[index], closure)
        face = prepared.face
    face_frame = Image.fromarray(native, "RGB")
    frame = Image.fromarray(face.plate, "RGB")
    motion = prepared.motion[index]
    regions = prepared.scene_contract["rig_regions"]
    _warp_region(
        frame,
        regions["shoulders"],
        dx=float(motion["shoulder_x_px"]),
        dy=float(motion["breath_y_px"]),
        scale_y=1.0 + float(motion["breath_y_px"]) / 900.0,
    )
    feature_mask = Image.fromarray(
        face.feature_support.astype(np.uint8) * 255,
        "L",
    )
    frame.paste(face_frame, (0, 0), feature_mask)
    secondary = prepared.motion_metadata["secondary_motion"]
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
    composed = _camera_frame(frame, float(motion["camera_push"]), prepared.scene_contract)
    return composed.convert("RGB"), native, evidence


def _native_eye_support_mask(prepared: PreparedDirectAddress) -> np.ndarray:
    shape = prepared.face.plate.shape[:2]
    support = np.zeros(shape, dtype=np.uint8)
    geometry = prepared.face.contract["semantic_geometry_native_xy"]
    for eye_name in ("viewer_left_eye", "viewer_right_eye"):
        eye = geometry[eye_name]
        support = cv2.bitwise_or(
            support,
            phase34_candidate09.phase33._ellipse_mask(
                shape,
                tuple(eye["center"]),
                (eye["radius"][0] + 7, eye["radius"][1] + 7),
            ),
        )
    return support > 0


def _final_eye_support_mask(
    prepared: PreparedDirectAddress,
    frame_number: int,
) -> np.ndarray:
    """Transform Candidate09's complete eye support through the same head and camera path."""
    support = _native_eye_support_mask(prepared).astype(np.uint8) * 255
    mask = Image.fromarray(np.repeat(support[:, :, None], 3, axis=2), "RGB")
    motion = prepared.motion[frame_number - 1]
    _warp_region(
        mask,
        prepared.scene_contract["rig_regions"]["head"],
        dx=float(motion["head_x_px"]),
        dy=float(motion["head_y_px"]),
        rotation_deg=float(motion["head_tilt_deg"]),
    )
    transformed = _camera_frame(
        mask, float(motion["camera_push"]), prepared.scene_contract,
    ).convert("RGB")
    allowed = np.any(np.asarray(transformed, dtype=np.uint8) > 0, axis=2).astype(np.uint8)
    dilation = int(prepared.contract["representation"]["transformed_eye_support_dilation_px"])
    if dilation > 0:
        kernel = np.ones((2 * dilation + 1, 2 * dilation + 1), dtype=np.uint8)
        allowed = cv2.dilate(allowed, kernel, iterations=1)
    return allowed > 0


def _max_8x8_delta(
    first: np.ndarray,
    second: np.ndarray,
    roi_xyxy: tuple[int, int, int, int],
) -> float:
    x1, y1, x2, y2 = roi_xyxy
    first = first[y1:y2, x1:x2]
    second = second[y1:y2, x1:x2]
    delta = np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(axis=2)
    local = cv2.boxFilter(delta, -1, (8, 8), normalize=True)
    return float(local.max()) if local.size else 0.0


def _gate(name: str, actual: Any, operator: str, threshold: Any) -> dict[str, Any]:
    if operator == "==":
        passed = actual == threshold
    elif operator == ">=":
        passed = math.isfinite(float(actual)) and float(actual) >= float(threshold)
    elif operator == "<=":
        passed = math.isfinite(float(actual)) and float(actual) <= float(threshold)
    else:
        raise SourceTexturedDirectAddressError(f"unsupported gate operator: {operator}")
    return {
        "name": name,
        "actual": actual,
        "operator": operator,
        "threshold": threshold,
        "passed": bool(passed),
    }


def _output_path(contract: dict[str, Any], development_label: str | None) -> Path:
    base = (REPO_ROOT / contract["preview"]["directory"]).resolve()
    if development_label is None:
        return base
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", development_label):
        raise SourceTexturedDirectAddressError("development label must be lowercase kebab-case")
    return base.with_name(f"{base.name}-{development_label}")


def _paste_labelled(
    canvas: Image.Image,
    image: Image.Image,
    position: tuple[int, int],
    size: tuple[int, int],
    label: str,
    *,
    crop: tuple[int, int, int, int] | None = None,
) -> None:
    source = image.crop(crop) if crop else image
    tile = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS)
    canvas.paste(tile, position)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((position[0], position[1], position[0] + min(size[0], 112), position[1] + 18), fill=(10, 10, 10))
    draw.text((position[0] + 4, position[1] + 3), label, fill=(245, 245, 245))


def _write_sheet(
    frames: dict[int, Path],
    selected: list[int],
    path: Path,
    *,
    columns: int,
    tile_size: tuple[int, int],
    crop: tuple[int, int, int, int] | None = None,
) -> None:
    rows = math.ceil(len(selected) / columns)
    canvas = Image.new("RGB", (columns * tile_size[0], rows * tile_size[1]), (10, 10, 10))
    for index, frame_number in enumerate(selected):
        row, column = divmod(index, columns)
        with Image.open(frames[frame_number]) as source:
            _paste_labelled(
                canvas,
                source.convert("RGB"),
                (column * tile_size[0], row * tile_size[1]),
                tile_size,
                f"F{frame_number:03d}",
                crop=crop,
            )
    canvas.save(path, compress_level=2)


def _blink_intervals(contract: dict[str, Any]) -> list[list[int]]:
    return [
        [int(frame) for frame, closure in zip(curve["frames"], curve["closures"]) if float(closure) > 0.0]
        for curve in contract["performance"]["blink_curves"]
    ]


def _blink_pairs(contract: dict[str, Any]) -> set[tuple[int, int]]:
    """Return every adjacent pair in each full nine-frame blink table, endpoints included."""
    return {
        (int(first), int(second))
        for curve in contract["performance"]["blink_curves"]
        for first, second in zip(curve["frames"], curve["frames"][1:])
    }


def _blink_review_frames(contract: dict[str, Any]) -> list[int]:
    return [
        int(frame)
        for curve in contract["performance"]["blink_curves"]
        for frame in curve["frames"]
    ]


def _stream_archive_header(contract: dict[str, Any]) -> dict[str, Any]:
    clock = contract["clock"]
    return {
        "format": "phase35_rgb24_xor_previous_gzip_v1",
        "width": int(clock["output_width"]),
        "height": int(clock["output_height"]),
        "channels": 3,
        "frame_count": int(clock["frame_count"]),
        "frame_bytes": int(clock["output_width"] * clock["output_height"] * 3),
        "xor_seed": "all_zero_rgb24_frame",
    }


def verify_lossless_archive(
    path: str | Path,
    expected_hashes: list[dict[str, Any]],
) -> int:
    with gzip.open(path, "rb") as archive:
        header = json.loads(archive.readline().decode("utf-8"))
        if header.get("format") != "phase35_rgb24_xor_previous_gzip_v1":
            raise SourceTexturedDirectAddressError("unsupported Phase35 lossless archive format")
        shape = (int(header["height"]), int(header["width"]), int(header["channels"]))
        frame_bytes = int(np.prod(shape))
        _require_equal(frame_bytes, int(header["frame_bytes"]), "archive frame bytes")
        _require_equal(len(expected_hashes), int(header["frame_count"]), "archive expected frame count")
        previous = np.zeros(shape, dtype=np.uint8)
        for index, expected in enumerate(expected_hashes, start=1):
            payload = archive.read(frame_bytes)
            if len(payload) != frame_bytes:
                raise SourceTexturedDirectAddressError(f"lossless archive frame {index} is truncated")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous)
            _require_equal(expected["frame"], index, f"archive frame {index} number")
            _require_equal(
                phase34._raw_frame_hash(frame),
                expected["rgb_sha256"],
                f"archive frame {index} RGB SHA-256",
            )
            previous = frame
        if archive.read(1):
            raise SourceTexturedDirectAddressError("lossless archive has trailing payload")
    return len(expected_hashes)


def write_unencoded_preview(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
    *,
    development_label: str | None = None,
) -> dict[str, Any]:
    startup_contract, startup_contract_path = load_contract(path)
    execution_state = _capture_execution_state(startup_contract, startup_contract_path)
    prepared = prepare_direct_address(startup_contract_path)
    contract = prepared.contract
    preparation_mismatches = _execution_state_mismatches(
        execution_state, startup_contract, startup_contract_path,
    )
    if preparation_mismatches:
        raise SourceTexturedDirectAddressError(
            "Phase35 execution state changed during preparation: "
            + json.dumps(preparation_mismatches)
        )
    candidate01_manifest = json.loads(
        _repo_path(contract["locks"]["phase35_candidate01_manifest"]["path"]).read_text(encoding="utf-8")
    )
    candidate01_hashes = candidate01_manifest.get("frame_hashes", [])
    _require_equal(
        [entry.get("frame") for entry in candidate01_hashes],
        list(range(1, int(contract["clock"]["frame_count"]) + 1)),
        "Candidate01 ordered frame-hash inventory",
    )
    _require_equal(
        _canonical_hash(prepared.candidate01_contract),
        candidate01_manifest["contract"]["canonical_sha256"],
        "Candidate01 canonical contract SHA-256",
    )
    output = _output_path(contract, development_label)
    if output.exists():
        raise SourceTexturedDirectAddressError(f"immutable preview already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage: Path | None = None
    try:
        stage = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
        preview = contract["preview"]
        archive_path = stage / preview["lossless_frame_archive_filename"]
        header = _stream_archive_header(contract)
        frame_count = int(contract["clock"]["frame_count"])
        all_sheet = Image.new("RGB", (1920, 1710), (10, 10, 10))
        required_review = list(contract["performance"]["required_review_frames"])
        face_timeline = sorted(set([1, 12, 24, 25, 30, 40, 50, 60, 70, 79, 82, 90, 100, 111, 120, 132, 145, 162, 168, 180, 192, 202, 215, 228]))
        blink_frames = _blink_review_frames(contract)
        blink_pairs = _blink_pairs(contract)
        retained_numbers = set(required_review) | set(face_timeline) | set(blink_frames)
        selected_dir = stage / ".selected_frames"
        selected_dir.mkdir()
        retained: dict[int, Path] = {}
        frame_hashes: list[dict[str, Any]] = []
        native_previous: np.ndarray | None = None
        final_previous: np.ndarray | None = None
        maximum_native_delta = 0.0
        maximum_native_pair = [1, 2]
        maximum_native_blink_delta = 0.0
        maximum_native_blink_pair = [77, 78]
        maximum_final_delta = 0.0
        maximum_final_pair = [1, 2]
        maximum_changed_outside = 0
        maximum_depth_violation = 0
        maximum_folded = 0
        minimum_full_blink_occlusion = 1.0
        full_blink_frames = 0
        maximum_activation_delta = 0.0
        previous_activation: float | None = None
        non_x_frames = 0
        final_exact_x_frames = 0
        face_roi = (500, 185, 870, 620)
        previous_archive = np.zeros((1080, 1920, 3), dtype=np.uint8)
        expected_changed_frames = set(contract["preencode_gates"]["required_candidate01_changed_frames"])
        candidate01_baseline_hash_mismatches = 0
        maximum_candidate01_native_outside_eye = 0
        maximum_candidate01_final_outside_eye = 0
        candidate01_delta_frames_evaluated = 0
        native_eye_support = _native_eye_support_mask(prepared)
    except BaseException:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        raise
    try:
        with archive_path.open("wb") as raw_handle:
            with gzip.GzipFile(filename="", mode="wb", compresslevel=6, fileobj=raw_handle, mtime=0) as archive:
                archive.write(json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
                for frame_number in range(1, frame_count + 1):
                    image, native, evidence = compose_direct_address_frame(prepared, frame_number)
                    final = np.asarray(image, dtype=np.uint8)
                    native_output = np.asarray(
                        Image.fromarray(native, "RGB").resize((1920, 1080), Image.Resampling.LANCZOS),
                        dtype=np.uint8,
                    )
                    archive.write(np.bitwise_xor(final, previous_archive).tobytes(order="C"))
                    previous_archive = final
                    digest = phase34._raw_frame_hash(final)
                    frame_hashes.append({"frame": frame_number, "rgb_sha256": digest})
                    if frame_number in expected_changed_frames:
                        baseline_image, baseline_native, _ = compose_direct_address_frame(
                            prepared, frame_number, candidate01=True,
                        )
                        baseline_final = np.asarray(baseline_image, dtype=np.uint8)
                        if phase34._raw_frame_hash(baseline_final) != candidate01_hashes[frame_number - 1]["rgb_sha256"]:
                            candidate01_baseline_hash_mismatches += 1
                        native_changed = np.any(native != baseline_native, axis=2)
                        maximum_candidate01_native_outside_eye = max(
                            maximum_candidate01_native_outside_eye,
                            int((native_changed & ~native_eye_support).sum()),
                        )
                        final_changed = np.any(final != baseline_final, axis=2)
                        final_eye_support = _final_eye_support_mask(prepared, frame_number)
                        maximum_candidate01_final_outside_eye = max(
                            maximum_candidate01_final_outside_eye,
                            int((final_changed & ~final_eye_support).sum()),
                        )
                        candidate01_delta_frames_evaluated += 1
                    row, column = divmod(frame_number - 1, 12)
                    _paste_labelled(all_sheet, image, (column * 160, row * 90), (160, 90), f"F{frame_number:03d}")
                    if frame_number in retained_numbers:
                        selected_path = selected_dir / f"frame_{frame_number:04d}.png"
                        image.save(selected_path, compress_level=2)
                        retained[frame_number] = selected_path
                    maximum_changed_outside = max(maximum_changed_outside, evidence.changed_outside_support)
                    maximum_depth_violation = max(maximum_depth_violation, evidence.depth_order_violation_pixels)
                    maximum_folded = max(maximum_folded, evidence.folded_triangles)
                    if evidence.oral_activation > 0.01:
                        non_x_frames += 1
                    if frame_number >= int(contract["performance"]["final_settle_start_frame"]) and evidence.changed_pixels == 0:
                        final_exact_x_frames += 1
                    if math.isclose(evidence.blink_closure, 1.0, abs_tol=1e-9):
                        full_blink_frames += 1
                        minimum_full_blink_occlusion = min(
                            minimum_full_blink_occlusion, min(evidence.iris_occlusion_ratios),
                        )
                    if previous_activation is not None:
                        maximum_activation_delta = max(
                            maximum_activation_delta,
                            abs(evidence.oral_activation - previous_activation),
                        )
                    if native_previous is not None:
                        value = _max_8x8_delta(native_previous, native_output, face_roi)
                        if value > maximum_native_delta:
                            maximum_native_delta = value
                            maximum_native_pair = [frame_number - 1, frame_number]
                        if (frame_number - 1, frame_number) in blink_pairs and value > maximum_native_blink_delta:
                            maximum_native_blink_delta = value
                            maximum_native_blink_pair = [frame_number - 1, frame_number]
                    if final_previous is not None:
                        value = _max_8x8_delta(final_previous, final, face_roi)
                        if value > maximum_final_delta:
                            maximum_final_delta = value
                            maximum_final_pair = [frame_number - 1, frame_number]
                    native_previous = native_output
                    final_previous = final
                    previous_activation = evidence.oral_activation

        verified_archive_frames = verify_lossless_archive(archive_path, frame_hashes)
        candidate01_preserved = sum(
            current["rgb_sha256"] == previous["rgb_sha256"]
            for current, previous in zip(frame_hashes, candidate01_hashes)
        )
        candidate01_changed_frames = [
            current["frame"]
            for current, previous in zip(frame_hashes, candidate01_hashes)
            if current["rgb_sha256"] != previous["rgb_sha256"]
        ]
        all_path = stage / preview["contact_sheet_filename"]
        all_sheet.save(all_path, compress_level=2)
        key_path = stage / preview["key_sheet_filename"]
        _write_sheet(retained, required_review, key_path, columns=4, tile_size=(480, 270))
        face_path = stage / preview["face_timeline_filename"]
        _write_sheet(retained, face_timeline, face_path, columns=8, tile_size=(240, 270), crop=face_roi)
        blink_path = stage / preview["blink_sheet_filename"]
        _write_sheet(retained, blink_frames, blink_path, columns=8, tile_size=(240, 270), crop=face_roi)
        motion_path = stage / preview["motion_sheet_filename"]
        _write_sheet(retained, required_review, motion_path, columns=4, tile_size=(480, 270))
        shutil.rmtree(selected_dir)

        final_controls = ("head_x_px", "head_y_px", "head_tilt_deg", "shoulder_x_px", "breath_y_px")
        settle_index = int(contract["performance"]["final_settle_start_frame"]) - 1
        final_hold_zero = all(
            all(abs(float(entry[name])) <= 1e-9 for name in final_controls)
            for entry in prepared.motion[settle_index:]
        )
        end_state_mismatches = _execution_state_mismatches(
            execution_state, contract, prepared.contract_path,
        )
        thresholds = contract["preencode_gates"]
        measurements = {
            "measurement_domains": {
                "native_face_temporal": "phase34_lanczos_resampled_1920x1080_rgb_before_body_head_camera_or_atmosphere_using_locked_attempt01_face_roi_and_8x8_metric",
                "final_face_temporal": "final_composed_1920x1080_rgb_before_encode",
                "audio_clock": "locked_pcm24_source_files",
            },
            "input_hash_mismatches": len(end_state_mismatches),
            "end_state_hash_mismatch_names": end_state_mismatches,
            "frame_count": len(frame_hashes),
            "audio_sample_count": _wave_probe(prepared.dialogue_path)["sample_count"],
            "audio_samples_per_frame": _wave_probe(prepared.dialogue_path)["sample_count"] // frame_count,
            "maximum_changed_pixels_outside_phase34_feature_support": maximum_changed_outside,
            "maximum_depth_order_violation_pixels": maximum_depth_violation,
            "maximum_folded_triangles": maximum_folded,
            "minimum_full_blink_iris_occlusion_ratio": minimum_full_blink_occlusion,
            "semantic_blink_count": len(_blink_intervals(contract)),
            "full_blink_frame_count": full_blink_frames,
            "non_x_frame_count": non_x_frames,
            "final_exact_x_frame_count": final_exact_x_frames,
            "maximum_native_face_adjacent_8x8_mean_delta": maximum_native_delta,
            "maximum_native_face_adjacent_8x8_mean_delta_frame_pair": maximum_native_pair,
            "maximum_native_blink_adjacent_8x8_mean_delta": maximum_native_blink_delta,
            "maximum_native_blink_adjacent_8x8_mean_delta_frame_pair": maximum_native_blink_pair,
            "accepted_candidate08_same_domain_maximum_source_pop": thresholds["accepted_candidate08_same_domain_maximum_source_pop"],
            "native_face_temporal_excess_over_accepted_candidate08": maximum_native_delta - float(thresholds["accepted_candidate08_same_domain_maximum_source_pop"]),
            "maximum_final_composed_face_adjacent_8x8_mean_delta": maximum_final_delta,
            "maximum_final_composed_face_adjacent_8x8_mean_delta_frame_pair": maximum_final_pair,
            "maximum_adjacent_oral_activation_delta": maximum_activation_delta,
            "final_hold_body_controls_zero": final_hold_zero,
            "complete_rgb_hash_inventory": len(frame_hashes) == frame_count,
            "lossless_rgb_archive_verified_frames": verified_archive_frames,
            "candidate01_preserved_frame_hashes": candidate01_preserved,
            "candidate01_changed_frames": candidate01_changed_frames,
            "candidate01_baseline_rerender_hash_mismatches": candidate01_baseline_hash_mismatches,
            "maximum_candidate01_native_changed_pixels_outside_eye_support": maximum_candidate01_native_outside_eye,
            "maximum_candidate01_final_changed_pixels_outside_transformed_eye_support": maximum_candidate01_final_outside_eye,
            "candidate01_delta_frames_evaluated": candidate01_delta_frames_evaluated,
        }
        gates = [
            _gate("input_hashes", measurements["input_hash_mismatches"], "==", thresholds["required_input_hash_mismatches"]),
            _gate("frame_count", measurements["frame_count"], "==", thresholds["required_frame_count"]),
            _gate("audio_sample_count", measurements["audio_sample_count"], "==", thresholds["required_audio_sample_count"]),
            _gate("audio_samples_per_frame", measurements["audio_samples_per_frame"], "==", thresholds["required_audio_samples_per_frame"]),
            _gate("face_support", measurements["maximum_changed_pixels_outside_phase34_feature_support"], "==", thresholds["required_changed_pixels_outside_phase34_feature_support"]),
            _gate("depth_order", measurements["maximum_depth_order_violation_pixels"], "==", thresholds["required_depth_order_violation_pixels"]),
            _gate("triangle_topology", measurements["maximum_folded_triangles"], "==", thresholds["required_folded_triangles"]),
            _gate("full_blink", measurements["minimum_full_blink_iris_occlusion_ratio"], ">=", thresholds["minimum_full_blink_iris_occlusion_ratio"]),
            _gate("blink_count", measurements["semantic_blink_count"], ">=", thresholds["minimum_semantic_blink_count"]),
            _gate("full_blink_frames", measurements["full_blink_frame_count"], ">=", thresholds["minimum_full_blink_frame_count"]),
            _gate("speaking_frames", measurements["non_x_frame_count"], ">=", thresholds["minimum_non_x_frame_count"]),
            _gate("final_exact_face_settle", measurements["final_exact_x_frame_count"], ">=", thresholds["minimum_final_exact_x_frame_count"]),
            _gate("native_face_temporal_noninferiority", measurements["native_face_temporal_excess_over_accepted_candidate08"], "<=", thresholds["maximum_native_face_temporal_excess_over_accepted_candidate08"]),
            _gate("candidate09_native_face_temporal", measurements["maximum_native_face_adjacent_8x8_mean_delta"], "<=", thresholds["maximum_native_face_adjacent_8x8_mean_delta"]),
            _gate("candidate09_native_blink_temporal", measurements["maximum_native_blink_adjacent_8x8_mean_delta"], "<=", thresholds["maximum_native_blink_adjacent_8x8_mean_delta"]),
            _gate("final_face_temporal", measurements["maximum_final_composed_face_adjacent_8x8_mean_delta"], "<=", thresholds["maximum_final_composed_face_adjacent_8x8_mean_delta"]),
            _gate("oral_activation", measurements["maximum_adjacent_oral_activation_delta"], "<=", thresholds["maximum_adjacent_oral_activation_delta"]),
            _gate("final_hold_body", measurements["final_hold_body_controls_zero"], "==", thresholds["required_final_hold_body_controls_zero"]),
            _gate("frame_hash_inventory", measurements["complete_rgb_hash_inventory"], "==", thresholds["required_complete_rgb_hash_inventory"]),
            _gate("lossless_archive", measurements["lossless_rgb_archive_verified_frames"], "==", thresholds["required_lossless_rgb_archive_verified_frames"]),
            _gate("candidate01_preserved_hashes", measurements["candidate01_preserved_frame_hashes"], "==", thresholds["required_candidate01_preserved_frame_hashes"]),
            _gate("candidate01_changed_frames", measurements["candidate01_changed_frames"], "==", thresholds["required_candidate01_changed_frames"]),
            _gate("candidate01_baseline_rerender", measurements["candidate01_baseline_rerender_hash_mismatches"], "==", thresholds["required_candidate01_baseline_rerender_hash_mismatches"]),
            _gate("candidate01_native_eye_only", measurements["maximum_candidate01_native_changed_pixels_outside_eye_support"], "==", thresholds["required_candidate01_native_changed_pixels_outside_eye_support"]),
            _gate("candidate01_final_eye_only", measurements["maximum_candidate01_final_changed_pixels_outside_transformed_eye_support"], "==", thresholds["required_candidate01_final_changed_pixels_outside_transformed_eye_support"]),
            _gate("candidate01_delta_frame_count", measurements["candidate01_delta_frames_evaluated"], "==", thresholds["required_candidate01_delta_frames_evaluated"]),
            _gate("end_state_hashes", len(measurements["end_state_hash_mismatch_names"]), "==", thresholds["required_end_state_hash_mismatches"]),
        ]
        failed = [gate["name"] for gate in gates if not gate["passed"]]
        if failed:
            raise SourceTexturedDirectAddressError(
                "Phase35 preencode gates failed without publishing partial output: "
                + json.dumps(failed)
            )
        artifacts = {}
        for name, artifact_path in {
            "lossless_frame_archive": archive_path,
            "contact_sheet": all_path,
            "key_sheet": key_path,
            "face_timeline": face_path,
            "blink_sheet": blink_path,
            "motion_sheet": motion_path,
        }.items():
            artifacts[name] = {
                "file": artifact_path.name,
                "sha256": _sha256(artifact_path),
                "bytes": artifact_path.stat().st_size,
            }
        manifest = {
            "manifest_version": 2,
            "development_label": development_label,
            "status": "preencode_machine_passed_exact_frame_review_required" if not failed else "preencode_machine_rejected",
            "machine_passed": not failed,
            "accepted_full_cartoon_production_delivery": False,
            "encode_authorized": False,
            "contract": {
                "path": str(prepared.contract_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "raw_sha256": execution_state["contract_raw_sha256"],
                "canonical_sha256": execution_state["contract_canonical_sha256"],
            },
            "implementation": {
                "path": IMPLEMENTATION_RELATIVE_PATH,
                "sha256": execution_state["implementation_sha256"],
            },
            "candidate08_reuse": {
                "successor_audit_sha256": contract["locks"]["phase34_successor_audit"]["sha256"],
                "candidate08_renderer_unchanged_sha256": contract["locks"]["phase34_candidate08_renderer"]["sha256"],
                "candidate09_used": True,
                "candidate09_renderer_sha256": contract["locks"]["phase34_renderer"]["sha256"],
                "candidate09_manifest_sha256": contract["locks"]["phase34_candidate09_manifest"]["sha256"],
                "candidate09_archive_sha256": contract["locks"]["phase34_candidate09_archive"]["sha256"],
                "candidate09_blink_review_sha256": contract["locks"]["phase34_candidate09_blink_review"]["sha256"],
                "default_blink_policy_sha256": contract["locks"]["phase34_default_blink_policy"]["sha256"],
            },
            "candidate01_supersession": {
                "manifest_sha256": contract["locks"]["phase35_candidate01_manifest"]["sha256"],
                "implementation_archive_sha256": contract["locks"]["phase35_candidate01_implementation_archive"]["sha256"],
                "reason": "Candidate09 approved linear blink replaces Candidate08 smoothstep timing",
                "expected_changed_frames": contract["preencode_gates"]["required_candidate01_changed_frames"],
            },
            "clock": contract["clock"],
            "timing": {
                "viseme_cues_sha256": execution_state["lock_sha256"]["viseme_cues"],
                "expression_cues_sha256": execution_state["lock_sha256"]["expression_cues"],
                "body_motion_sha256": execution_state["lock_sha256"]["body_motion"],
                "dialogue_audio_sha256": execution_state["lock_sha256"]["dialogue_audio"],
                "delivery_mix_sha256": execution_state["lock_sha256"]["delivery_mix"],
            },
            "measurements": measurements,
            "gates": gates,
            "gate_count": len(gates),
            "gates_passed": len(gates) - len(failed),
            "gates_failed": len(failed),
            "failed_gate_names": failed,
            "frame_hashes": frame_hashes,
            "lossless_archive_header": header,
            "artifacts": artifacts,
            "toolchain": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "opencv": cv2.__version__,
                "pillow": PILLOW_VERSION,
            },
            "policies": {
                "no_render_service": True,
                "no_network": True,
                "no_audio_or_video_encode": True,
                "no_paid_service_or_api": True,
                "no_reinforcement_learning": True,
                "human_exact_frame_review_required": True,
            },
        }
        manifest_path = stage / preview["manifest_filename"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        post_manifest_mismatches = _execution_state_mismatches(
            execution_state, contract, prepared.contract_path,
        )
        if post_manifest_mismatches:
            raise SourceTexturedDirectAddressError(
                "Phase35 execution state changed before promotion: "
                + json.dumps(post_manifest_mismatches)
            )
        stage.replace(output)
    except BaseException:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        "preview_directory": str(output),
        "manifest": str(output / preview["manifest_filename"]),
        "manifest_sha256": _sha256(output / preview["manifest_filename"]),
        "machine_passed": not failed,
        "gates_passed": len(gates) - len(failed),
        "gate_count": len(gates),
        "failed_gate_names": failed,
        "measurements": measurements,
        "encode_authorized": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the unencoded Phase35 source-textured direct-address preview"
    )
    parser.add_argument("--contract", default=str(REPO_ROOT / CONTRACT_RELATIVE_PATH))
    parser.add_argument("--development-label")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(json.dumps(write_unencoded_preview(args.contract, development_label=args.development_label), indent=2))


if __name__ == "__main__":
    main()
