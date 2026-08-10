"""Build June's fail-closed, unencoded Phase 36 Ledger Pour production slice."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import sys
import tarfile
import tempfile
from typing import Any, Iterator
import wave

import numpy as np
import PIL
from PIL import Image, ImageDraw

from pipeline import cartoon_golden_sound as golden_sound
from pipeline import cartoon_pour_layers as pour
from pipeline import cartoon_shot_sequence as shot_sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase36_ledger_pour_v1.json"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "6d164ee60686ae3722607806e3dcd5d8c54b29ce684503ac7f569a4068fc0962"
ARCHIVE_FORMAT = "phase36_rgb24_xor_previous_gzip_v1"
PHASE35_ARCHIVE_FORMAT = "phase35_rgb24_xor_previous_gzip_v1"
FACE_ROI = (500, 185, 870, 620)
EYE_ROI = (625, 235, 850, 360)


class LedgerPourError(RuntimeError):
    """Raised when a Phase 36 invariant is violated."""


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_frame_hash(frame: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(frame, dtype=np.uint8).tobytes()).hexdigest()


def _repo_path(relative: str) -> Path:
    path = Path(relative)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _outputs_path(relative: str) -> Path:
    path = Path(relative)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise LedgerPourError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _lock_hash(reference: dict[str, Any]) -> str:
    path = _repo_path(str(reference["path"]))
    if reference.get("hash_domain") == "lf_normalized_text":
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return _sha256(path)


def _validate_shots(contract: dict[str, Any]) -> None:
    frame_count = int(contract["clock"]["frame_count"])
    previous_output = 0
    mapped = 0
    source_keys: set[tuple[str, int]] = set()
    for shot in contract["shots"]:
        output_start, output_end = (int(value) for value in shot["output_frames"])
        source_start, source_end = (int(value) for value in shot["source_frames"])
        if output_start != previous_output + 1 or output_end < output_start:
            raise LedgerPourError("Phase36 shot output spans must be ordered and contiguous")
        if output_end - output_start != source_end - source_start:
            raise LedgerPourError(f"Phase36 shot {shot['id']} implicitly retimes its source")
        for source_frame in range(source_start, source_end + 1):
            key = (str(shot["source"]), source_frame)
            if key in source_keys:
                raise LedgerPourError(f"Phase36 source frame is duplicated: {key}")
            source_keys.add(key)
        mapped += output_end - output_start + 1
        previous_output = output_end
    _require_equal(previous_output, frame_count, "Phase36 shot terminal frame")
    _require_equal(mapped, frame_count, "Phase36 source mapping count")
    _require_equal(
        [int(shot["output_frames"][0]) for shot in contract["shots"][1:]],
        [int(value) for value in contract["edit"]["hard_cut_output_frames"]],
        "Phase36 hard-cut frames",
    )


def _validate_review_lists(contract: dict[str, Any]) -> None:
    frame_count = int(contract["clock"]["frame_count"])
    for name in (
        "key_frames", "cut_review_frames", "liquid_review_frames",
        "compassion_review_frames", "full_resolution_review_frames",
    ):
        values = [int(value) for value in contract["review"][name]]
        if values != sorted(set(values)) or any(value < 1 or value > frame_count for value in values):
            raise LedgerPourError(f"Phase36 {name} must be unique, ordered, and in range")
    required_cut_neighbors = set(range(69, 83)) | set(range(232, 246))
    _require_equal(set(contract["review"]["cut_review_frames"]), required_cut_neighbors, "cut review coverage")
    _require_equal(
        set(contract["review"]["full_resolution_review_frames"]),
        {75, 76, 237, 238, 248},
        "full-resolution boundary and blink coverage",
    )


def _phase35_paths(contract: dict[str, Any]) -> tuple[Path, Path]:
    evidence = contract["source_evidence"]
    directory = _outputs_path(str(evidence["phase35_external_directory"]))
    expected = (REPO_ROOT / "../../outputs/edit/phase35-source-textured-direct-address-preview-v2-candidate-03").resolve()
    _require_equal(directory, expected, "Phase35 external evidence directory")
    return (
        directory / str(evidence["phase35_manifest_filename"]),
        directory / str(evidence["phase35_archive_filename"]),
    )


def load_contract(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
    *,
    require_external: bool = False,
) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned Phase36 contract path")
    contract = json.loads(resolved.read_text(encoding="utf-8"))
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "Phase36 canonical contract SHA-256")
    _require_equal(contract["contract_version"], 1, "Phase36 contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase36_ledger_pour_v1", "Phase36 contract id")
    _require_equal(contract["character_id"], "june_oxley", "Phase36 character")
    _require_equal(contract["cash_cost"], 0, "Phase36 cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "Phase36 paid dependency policy")
    _require_equal(contract["network_runtime_required"], False, "Phase36 network policy")
    _require_equal(contract["clock"], {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "frame_count": 303,
        "duration_seconds": 10.1,
        "audio_sample_rate": 48000,
        "audio_samples_per_frame": 1600,
        "audio_sample_count": 484800,
        "audio_channels": 2,
        "audio_sample_width": 3,
    }, "Phase36 exact clock")
    _require_equal(contract["failure_policy"]["encode_allowed"], False, "Phase36 encode policy")
    _require_equal(contract["promotion_policy"]["future_encode_requires_new_binding"], True, "future encode binding")
    _require_equal(contract["edit"]["cross_dissolve_allowed"], False, "cross-dissolve policy")
    _require_equal(contract["edit"]["optical_flow_allowed"], False, "optical-flow policy")
    _require_equal(contract["edit"]["implicit_retiming_allowed"], False, "retiming policy")
    for name, reference in contract["locks"].items():
        _require_equal(_lock_hash(reference), reference["sha256"], f"locked {name} SHA-256")
    _validate_shots(contract)
    _validate_review_lists(contract)
    phase25 = json.loads(
        _repo_path(str(contract["locks"]["phase25_master_contract"]["path"])).read_text(encoding="utf-8")
    )
    phase25_gs060 = next(shot for shot in phase25["shots"] if shot["id"] == "GS060")
    _require_equal(
        [phase25_gs060["start_frame"], phase25_gs060["end_frame"]],
        [679, 936],
        "Phase25 GS060 master span",
    )
    _require_equal(phase25["rendered_sources"]["GS060"]["frame_count"], 258, "Phase25 GS060 source length")
    if require_external:
        _require_equal(PIL.__version__, contract["shots"][2]["camera"]["pillow_version"], "Phase36 Pillow version")
        multishot = json.loads(
            _repo_path(str(contract["locks"]["phase21_multishot_contract"]["path"])).read_text(encoding="utf-8")
        )
        inherited_camera = next(
            shot["camera"] for shot in multishot["shots"]
            if shot["id"] == "GS050_IDENTITY_LOCKED_COMPASSION_CLOSEUP"
        )
        declared_camera = contract["shots"][2]["camera"]
        for key in ("start_zoom", "end_zoom", "focus_start", "focus_end", "easing"):
            _require_equal(declared_camera[key], inherited_camera[key], f"inherited Phase21 camera {key}")
        external_manifest, external_archive = _phase35_paths(contract)
        if not external_manifest.is_file() or not external_archive.is_file():
            raise LedgerPourError("exact local Phase35 manifest/archive pair is missing")
        repository_manifest = _repo_path(str(contract["locks"]["phase35_manifest"]["path"]))
        _require_equal(_sha256(external_manifest), _sha256(repository_manifest), "external Phase35 manifest SHA-256")
        _require_equal(_sha256(external_archive), contract["source_evidence"]["phase35_archive_sha256"], "external Phase35 archive SHA-256")
        _require_equal(external_archive.stat().st_size, contract["source_evidence"]["phase35_archive_bytes"], "external Phase35 archive bytes")
    return contract


def _phase35_manifest(contract: dict[str, Any]) -> dict[str, Any]:
    path = _repo_path(str(contract["locks"]["phase35_manifest"]["path"]))
    manifest = json.loads(path.read_text(encoding="utf-8"))
    _require_equal(manifest["machine_passed"], True, "Phase35 source machine status")
    _require_equal(manifest["measurements"]["frame_count"], 228, "Phase35 source frame count")
    _require_equal(len(manifest["frame_hashes"]), 228, "Phase35 frame hash inventory")
    evidence = contract["source_evidence"]
    _require_equal(
        manifest["contract"]["raw_sha256"],
        contract["locks"]["phase35_source_contract"]["sha256"],
        "Phase35 manifest-bound source contract raw SHA-256",
    )
    _require_equal(
        manifest["contract"]["canonical_sha256"],
        evidence["phase35_manifest_contract_canonical_sha256"],
        "Phase35 manifest-bound source contract canonical SHA-256",
    )
    _require_equal(
        manifest["implementation"],
        {
            "path": evidence["phase35_manifest_implementation_path"],
            "sha256": evidence["phase35_manifest_implementation_sha256"],
        },
        "Phase35 manifest-bound implementation",
    )
    _require_equal(
        manifest["artifacts"]["lossless_frame_archive"],
        {
            "file": evidence["phase35_archive_filename"],
            "sha256": evidence["phase35_archive_sha256"],
            "bytes": evidence["phase35_archive_bytes"],
        },
        "Phase35 manifest-bound lossless archive",
    )
    implementation_archive = _repo_path(str(contract["locks"]["phase35_implementation_archive"]["path"]))
    member_name = str(evidence["phase35_manifest_implementation_path"])
    with tarfile.open(implementation_archive, "r:") as archive:
        try:
            member = archive.getmember(member_name)
        except KeyError as exc:
            raise LedgerPourError(f"Phase35 implementation archive omits {member_name}") from exc
        source = archive.extractfile(member)
        if source is None:
            raise LedgerPourError(f"Phase35 implementation archive member is not a file: {member_name}")
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    _require_equal(
        digest.hexdigest(),
        evidence["phase35_manifest_implementation_sha256"],
        "Phase35 archived implementation member SHA-256",
    )
    review = _repo_path(str(contract["locks"]["phase35_visual_acceptance"]["path"])).read_text(encoding="utf-8")
    if "PHASE35_C03_VISUAL_ACCEPTED_ENCODE_AUTHORIZED" not in review:
        raise LedgerPourError("Phase35 source visual acceptance verdict is absent")
    return manifest


def _phase35_attempt_review(contract: dict[str, Any]) -> dict[str, str] | None:
    gate = contract["phase35_attempt_review_gate"]
    review_directory = _repo_path(str(gate["review_directory"]))
    _require_equal(review_directory, (REPO_ROOT / "collab").resolve(), "Phase35 attempt review directory")
    required_tokens = (
        str(gate["required_verdict"]),
        str(gate["required_video_sha256"]),
        str(gate["required_failure_receipt_sha256"]),
        str(gate["required_attempt_claim_sha256"]),
    )
    allowed_line = f"{gate['required_verdict_field']} {gate['required_verdict']}"
    blocked_line = f"{gate['required_verdict_field']} {gate['forbidden_verdict']}"
    matches: list[tuple[Path, str]] = []
    blocked_receipts: list[Path] = []
    for candidate in sorted(review_directory.glob(str(gate["review_filename_glob"]))):
        if not candidate.is_file():
            continue
        payload = candidate.read_bytes()
        text = payload.decode("utf-8")
        lines = [line.strip() for line in text.splitlines()]
        if blocked_line in lines:
            blocked_receipts.append(candidate.resolve())
        if lines.count(allowed_line) == 1 and all(token in text for token in required_tokens[1:]):
            matches.append((candidate.resolve(), hashlib.sha256(payload).hexdigest()))
    if blocked_receipts:
        return None
    if not matches:
        return None
    if len(matches) != 1:
        raise LedgerPourError("Phase35 post-attempt review receipt is ambiguous")
    path, digest = matches[0]
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": digest,
        "verdict": str(gate["required_verdict"]),
    }


def _phase23_runtime_asset_hashes(contract: dict[str, Any]) -> dict[str, str]:
    phase23_path = _repo_path(str(contract["locks"]["phase23_contract"]["path"]))
    _, background, poses = pour.load_pour_layer_contract(phase23_path)
    paths = {"background": background, **{f"pose_{name}": path for name, path in poses.items()}}
    return {name: _sha256(path) for name, path in paths.items()}


def _capture_execution_state(
    contract: dict[str, Any],
    contract_path: str | Path,
    attempt_review: dict[str, str],
) -> dict[str, Any]:
    current_attempt_review = _phase35_attempt_review(contract)
    if current_attempt_review is None:
        raise LedgerPourError("Phase35 post-attempt authorization disappeared or was blocked")
    _require_equal(
        current_attempt_review,
        attempt_review,
        "Phase35 post-attempt authorization receipt",
    )
    resolved_contract = Path(contract_path).resolve()
    parsed_contract = json.loads(resolved_contract.read_text(encoding="utf-8"))
    return {
        "self": {
            "contract_raw_sha256": _sha256(resolved_contract),
            "contract_canonical_sha256": _canonical_hash(parsed_contract),
            "implementation_sha256": _sha256(Path(__file__).resolve()),
        },
        "locked": {name: _lock_hash(reference) for name, reference in contract["locks"].items()},
        "external": {
            "phase35_manifest_sha256": _sha256(_phase35_paths(contract)[0]),
            "phase35_archive_sha256": _sha256(_phase35_paths(contract)[1]),
        },
        "phase23_runtime_assets": _phase23_runtime_asset_hashes(contract),
        "phase35_attempt_review": {
            "path": current_attempt_review["path"],
            "sha256": current_attempt_review["sha256"],
            "verdict": current_attempt_review["verdict"],
        },
    }


def _execution_state_mismatches(expected: Any, actual: Any, prefix: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        names: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            name = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected or key not in actual:
                names.append(name)
            else:
                names.extend(_execution_state_mismatches(expected[key], actual[key], name))
        return names
    return [] if expected == actual else [prefix]


def _assert_execution_state(initial: dict[str, Any], current: dict[str, Any], checkpoint: str) -> None:
    mismatches = _execution_state_mismatches(initial, current)
    if mismatches:
        raise LedgerPourError(
            f"Phase36 execution inputs changed at {checkpoint}: " + ", ".join(mismatches)
        )


def iter_phase35_frames(
    archive_path: str | Path,
    expected_hashes: list[dict[str, Any]],
    *,
    expected_header: dict[str, Any],
) -> Iterator[tuple[int, np.ndarray]]:
    with gzip.open(Path(archive_path), "rb") as archive:
        header = json.loads(archive.readline().decode("utf-8"))
        _require_equal(header, expected_header, "Phase35 archive header")
        _require_equal(header.get("format"), PHASE35_ARCHIVE_FORMAT, "Phase35 archive format")
        shape = (int(header["height"]), int(header["width"]), int(header["channels"]))
        _require_equal(shape, (1080, 1920, 3), "Phase35 archive shape")
        frame_bytes = int(np.prod(shape))
        _require_equal(int(header["frame_bytes"]), frame_bytes, "Phase35 archive frame bytes")
        _require_equal(int(header["frame_count"]), len(expected_hashes), "Phase35 archive frame count")
        previous = np.zeros(shape, dtype=np.uint8)
        for frame_number, expected in enumerate(expected_hashes, start=1):
            payload = archive.read(frame_bytes)
            if len(payload) != frame_bytes:
                raise LedgerPourError(f"Phase35 archive frame {frame_number} is truncated")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous)
            _require_equal(int(expected["frame"]), frame_number, f"Phase35 frame {frame_number} number")
            _require_equal(_raw_frame_hash(frame), expected["rgb_sha256"], f"Phase35 frame {frame_number} RGB SHA-256")
            yield frame_number, frame
            previous = frame
        if archive.read(1):
            raise LedgerPourError("Phase35 archive has trailing payload")


def compassion_camera(
    frame: np.ndarray,
    camera: dict[str, Any],
    source_frame: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    if frame.shape != (1080, 1920, 3) or frame.dtype != np.uint8:
        raise LedgerPourError("compassion camera requires one 1920x1080 RGB24 frame")
    motion_start, motion_end = (int(value) for value in camera["motion_source_frames"])
    lock_start, lock_end = (int(value) for value in camera["locked_source_frames"])
    if not motion_start <= source_frame <= lock_end or lock_start != motion_end + 1:
        raise LedgerPourError("compassion camera source frame is outside its clock")
    amount = min(1.0, max(0.0, (source_frame - motion_start) / max(1, motion_end - motion_start)))
    if amount < 0.5:
        eased = 4.0 * amount * amount * amount
    else:
        eased = 1.0 - ((-2.0 * amount + 2.0) ** 3) / 2.0
    zoom = float(camera["start_zoom"]) + (float(camera["end_zoom"]) - float(camera["start_zoom"])) * eased
    focus = tuple(
        float(camera["focus_start"][axis])
        + (float(camera["focus_end"][axis]) - float(camera["focus_start"][axis])) * eased
        for axis in range(2)
    )
    crop_xyxy = shot_sequence.camera_crop_box((1920, 1080), (1920, 1080), zoom, focus)
    x1, y1, x2, y2 = crop_xyxy
    image = Image.fromarray(frame, "RGB")
    output = np.asarray(image.crop(crop_xyxy).resize((1920, 1080), Image.Resampling.LANCZOS), dtype=np.uint8)
    scale_x, scale_y = 1920.0 / (x2 - x1), 1080.0 / (y2 - y1)
    def transform_roi(roi: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        rx1, ry1, rx2, ry2 = roi
        return (
            int(round((rx1 - x1) * scale_x)),
            int(round((ry1 - y1) * scale_y)),
            int(round((rx2 - x1) * scale_x)),
            int(round((ry2 - y1) * scale_y)),
        )
    face_roi = transform_roi(FACE_ROI)
    eye_roi = transform_roi(EYE_ROI)
    return output, {
        "crop_xyxy": list(crop_xyxy),
        "zoom": zoom,
        "focus": list(focus),
        "eased_amount": eased,
        "camera_locked": lock_start <= source_frame <= lock_end,
        "transformed_face_roi_xyxy": list(face_roi),
        "transformed_eye_roi_xyxy": list(eye_roi),
        "minimum_face_edge_margin_px": min(face_roi[0], face_roi[1], 1920 - face_roi[2], 1080 - face_roi[3]),
    }


def _max_8x8_delta(first: np.ndarray, second: np.ndarray, roi_xyxy: tuple[int, int, int, int]) -> float:
    x1, y1, x2, y2 = roi_xyxy
    delta = np.abs(first[y1:y2, x1:x2].astype(np.float32) - second[y1:y2, x1:x2].astype(np.float32)).mean(axis=2)
    if delta.shape[0] < 8 or delta.shape[1] < 8:
        return 0.0
    integral = np.pad(delta.astype(np.float64), ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)
    windows = integral[8:, 8:] - integral[:-8, 8:] - integral[8:, :-8] + integral[:-8, :-8]
    return float(windows.max() / 64.0)


def _mean_abs_delta(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.abs(first.astype(np.float32) - second.astype(np.float32)).mean())


class _Sheet:
    def __init__(self, frames: list[int], *, columns: int, tile_size: tuple[int, int], title: str) -> None:
        self.frames = frames
        self.positions = {frame: index for index, frame in enumerate(frames)}
        self.columns = columns
        self.tile_size = tile_size
        rows = math.ceil(len(frames) / columns)
        self.image = Image.new("RGB", (columns * tile_size[0], rows * tile_size[1]), (17, 19, 23))
        self.title = title

    def add(self, frame_number: int, frame: np.ndarray) -> None:
        if frame_number not in self.positions:
            return
        index = self.positions[frame_number]
        row, column = divmod(index, self.columns)
        tile = Image.fromarray(frame, "RGB").resize(self.tile_size, Image.Resampling.LANCZOS)
        x, y = column * self.tile_size[0], row * self.tile_size[1]
        self.image.paste(tile, (x, y))
        draw = ImageDraw.Draw(self.image)
        label = f"{self.title} F{frame_number:03d}"
        draw.rectangle((x + 4, y + 4, x + 8 + 6 * len(label), y + 20), fill=(10, 12, 16))
        draw.text((x + 7, y + 6), label, fill=(244, 238, 218))

    def save(self, path: Path) -> None:
        self.image.save(path, compress_level=2)
        self.image.close()


class _CropSheet:
    def __init__(self, frames: list[int], *, columns: int, tile_size: tuple[int, int], title: str) -> None:
        self.frames = frames
        self.positions = {frame: index for index, frame in enumerate(frames)}
        self.columns = columns
        self.tile_size = tile_size
        rows = math.ceil(len(frames) / columns)
        self.image = Image.new("RGB", (columns * tile_size[0], rows * tile_size[1]), (17, 19, 23))
        self.title = title

    def add(self, frame_number: int, frame: np.ndarray, crop_xyxy: tuple[int, int, int, int]) -> None:
        if frame_number not in self.positions:
            return
        index = self.positions[frame_number]
        row, column = divmod(index, self.columns)
        crop = Image.fromarray(frame, "RGB").crop(crop_xyxy)
        tile = crop.resize(self.tile_size, Image.Resampling.NEAREST)
        x, y = column * self.tile_size[0], row * self.tile_size[1]
        self.image.paste(tile, (x, y))
        draw = ImageDraw.Draw(self.image)
        label = f"{self.title} F{frame_number:03d} 2X NEAREST"
        draw.rectangle((x + 4, y + 4, x + 8 + 6 * len(label), y + 20), fill=(10, 12, 16))
        draw.text((x + 7, y + 6), label, fill=(244, 238, 218))

    def save(self, path: Path) -> None:
        self.image.save(path, compress_level=2)
        self.image.close()


def _read_pcm24_wave(path: Path) -> tuple[np.ndarray, dict[str, int]]:
    file_size = path.stat().st_size
    with path.open("rb") as source:
        header = source.read(12)
        if len(header) != 12:
            raise LedgerPourError(f"PCM source has a truncated RIFF header: {path.name}")
        riff, riff_size, wave_id = struct.unpack("<4sI4s", header)
        if riff != b"RIFF" or wave_id != b"WAVE" or riff_size + 8 != file_size:
            raise LedgerPourError(f"PCM source has invalid RIFF geometry: {path.name}")
        fmt: bytes | None = None
        data: bytes | None = None
        while source.tell() < file_size:
            chunk_header = source.read(8)
            if len(chunk_header) != 8:
                raise LedgerPourError(f"PCM source has a truncated chunk: {path.name}")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            payload = source.read(chunk_size)
            if len(payload) != chunk_size:
                raise LedgerPourError(f"PCM source chunk is truncated: {path.name}")
            if chunk_size % 2:
                if source.read(1) == b"":
                    raise LedgerPourError(f"PCM source chunk pad is missing: {path.name}")
            if chunk_id == b"fmt ":
                if fmt is not None:
                    raise LedgerPourError(f"PCM source has duplicate fmt chunks: {path.name}")
                fmt = payload
            elif chunk_id == b"data":
                if data is not None:
                    raise LedgerPourError(f"PCM source has duplicate data chunks: {path.name}")
                data = payload
    if fmt is None or data is None or len(fmt) < 16:
        raise LedgerPourError(f"PCM source omits fmt/data chunks: {path.name}")
    format_tag, channels, sample_rate, byte_rate, block_align, bits = struct.unpack("<HHIIHH", fmt[:16])
    if format_tag == 0xFFFE:
        if len(fmt) < 40 or struct.unpack("<H", fmt[16:18])[0] < 22:
            raise LedgerPourError(f"PCM extensible fmt is incomplete: {path.name}")
        valid_bits = struct.unpack("<H", fmt[18:20])[0]
        pcm_guid = bytes.fromhex("0100000000001000800000aa00389b71")
        if valid_bits != bits or fmt[24:40] != pcm_guid:
            raise LedgerPourError(f"PCM extensible subtype is not matching-width PCM: {path.name}")
    elif format_tag != 1:
        raise LedgerPourError(f"PCM source is compressed: {path.name}")
    if bits != 24 or block_align != channels * 3 or byte_rate != sample_rate * block_align:
        raise LedgerPourError(f"PCM24 source geometry is invalid: {path.name}")
    if len(data) % block_align:
        raise LedgerPourError(f"PCM24 source payload is not frame-aligned: {path.name}")
    packed = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
    values = (
        packed[:, 0].astype(np.int32)
        | (packed[:, 1].astype(np.int32) << 8)
        | (packed[:, 2].astype(np.int32) << 16)
    )
    values = np.where(values & 0x800000, values - 0x1000000, values).astype(np.int32)
    samples = values.reshape(-1, channels)
    return samples, {
        "sample_rate": sample_rate,
        "channels": channels,
        "bits_per_sample": bits,
        "sample_count": samples.shape[0],
        "data_bytes": len(data),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def _write_pcm24_wave(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    values = np.asarray(samples, dtype=np.int32)
    if values.ndim != 2 or values.shape[1] != 2:
        raise LedgerPourError("Phase36 output mix must be an N x 2 PCM24 array")
    unsigned = values.reshape(-1).astype(np.int64) & 0xFFFFFF
    packed = np.empty((unsigned.size, 3), dtype=np.uint8)
    packed[:, 0] = unsigned & 0xFF
    packed[:, 1] = (unsigned >> 8) & 0xFF
    packed[:, 2] = (unsigned >> 16) & 0xFF
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(2)
        destination.setsampwidth(3)
        destination.setframerate(sample_rate)
        destination.writeframes(packed.tobytes())


def _verify_pcm24_readback(
    decoded: np.ndarray,
    intended: np.ndarray,
    probe: dict[str, Any],
) -> int:
    _require_equal(
        {key: probe[key] for key in ("sample_rate", "channels", "bits_per_sample", "sample_count", "data_bytes")},
        {
            "sample_rate": 48000,
            "channels": 2,
            "bits_per_sample": 24,
            "sample_count": 484800,
            "data_bytes": 2908800,
        },
        "Phase36 PCM24 readback geometry",
    )
    _require_equal(decoded.shape, intended.shape, "Phase36 PCM24 readback sample shape")
    bit_exact_values = int(np.count_nonzero(decoded == intended))
    _require_equal(bit_exact_values, int(intended.size), "Phase36 PCM24 readback exact channel values")
    return bit_exact_values


def build_exact_audio(contract: dict[str, Any], path: Path) -> dict[str, Any]:
    audio = contract["audio"]
    phase26_path = _repo_path(str(contract["locks"]["phase26_sound_contract"]["path"]))
    phase26_contract, _ = golden_sound.load_sound_contract(phase26_path, require_dialogue_source=False)
    stems = golden_sound.render_procedural_stems(phase26_contract)
    start_frame, end_frame = (int(value) for value in audio["pour_segment"]["global_source_frames"])
    samples_per_frame = int(contract["clock"]["audio_samples_per_frame"])
    start_sample, end_sample = (start_frame - 1) * samples_per_frame, end_frame * samples_per_frame
    stem_slices = {
        name: np.ascontiguousarray(stems[name][start_sample:end_sample], dtype=np.float32)
        for name in ("AMB_PORCH_STEREO", "FOLEY_PROP_MONO", "FOLEY_BODY_STEREO")
    }
    expected_stem_hashes = audio["pour_segment"]["expected_float32_stem_slice_sha256"]
    actual_stem_hashes = {
        name: hashlib.sha256(values.tobytes()).hexdigest() for name, values in stem_slices.items()
    }
    stem_hash_mismatches = sum(
        actual_stem_hashes[name] != expected_stem_hashes[name] for name in expected_stem_hashes
    )
    prop = stem_slices["FOLEY_PROP_MONO"][:, 0].astype(np.float64)
    body = stem_slices["FOLEY_BODY_STEREO"].astype(np.float64)
    ambience = stem_slices["AMB_PORCH_STEREO"].astype(np.float64)
    pour_mix = np.column_stack([prop, prop]) * (10.0 ** (float(audio["pour_segment"]["prop_gain_db"]) / 20.0)) / math.sqrt(2.0)
    pour_mix += body * (10.0 ** (float(audio["pour_segment"]["body_gain_db"]) / 20.0))
    pour_mix += ambience * (10.0 ** (float(audio["pour_segment"]["ambience_gain_db"]) / 20.0))
    pour_limit = 10.0 ** (float(audio["pour_segment"]["peak_ceiling_dbfs"]) / 20.0)
    pour_peak = float(np.max(np.abs(pour_mix)))
    if pour_peak > pour_limit:
        pour_mix *= pour_limit / pour_peak
    pour_integer = np.round(np.clip(pour_mix, -1.0, 1.0) * 8388607.0).astype(np.int32)

    phase33_path = _repo_path(str(contract["locks"]["phase33_delivery_mix"]["path"]))
    phase33_integer, phase33_probe = _read_pcm24_wave(phase33_path)
    _require_equal(phase33_probe, {
        "sample_rate": 48000,
        "channels": 2,
        "bits_per_sample": 24,
        "sample_count": 364800,
        "data_bytes": 2188800,
        "data_sha256": audio["direct_address_segment"]["pcm_data_sha256"],
    }, "Phase33 direct-address mix geometry")
    output = np.concatenate([pour_integer, phase33_integer], axis=0)
    _require_equal(output.shape, (484800, 2), "Phase36 PCM sample shape")
    _write_pcm24_wave(path, output, 48000)
    decoded, probe = _read_pcm24_wave(path)
    phase36_bit_exact_values = _verify_pcm24_readback(decoded, output, probe)
    bit_exact_values = int(np.count_nonzero(decoded[120000:] == phase33_integer))
    clipped_samples = int(np.count_nonzero(np.abs(decoded.astype(np.int64)) > 8388607))
    peak = float(np.max(np.abs(decoded.astype(np.float64))) / 8388607.0)
    peak_dbfs = 20.0 * math.log10(max(peak, 1e-12))
    boundary_step = float(np.max(np.abs(
        decoded[120000].astype(np.float64) - decoded[119999].astype(np.float64)
    )) / 8388607.0)
    return {
        "file": path.name,
        "sha256": _sha256(path),
        "probe": probe,
        "pour_source_global_frames": [start_frame, end_frame],
        "pour_samples": int(pour_integer.shape[0]),
        "phase33_samples": int(phase33_integer.shape[0]),
        "phase36_bit_exact_scalar_samples": phase36_bit_exact_values,
        "phase33_bit_exact_scalar_samples": bit_exact_values,
        "phase26_float32_stem_slice_sha256": actual_stem_hashes,
        "phase26_stem_array_hash_mismatches": stem_hash_mismatches,
        "clipped_samples": clipped_samples,
        "peak_dbfs": peak_dbfs,
        "boundary_step": boundary_step,
        "dialogue_in_pour_segment": False,
        "lossy_audio_encode_used": False,
    }


def _prepare_pour(
    contract: dict[str, Any],
    expected_asset_hashes: dict[str, str] | None = None,
) -> tuple[dict[str, Any], Image.Image, dict[str, Image.Image], dict[int, Image.Image]]:
    phase23_path = _repo_path(str(contract["locks"]["phase23_contract"]["path"]))
    phase23, background_path, pose_paths = pour.load_pour_layer_contract(phase23_path)
    if expected_asset_hashes is not None:
        _require_equal(
            _phase23_runtime_asset_hashes(contract),
            expected_asset_hashes,
            "Phase23 runtime assets immediately before decode",
        )
    with Image.open(background_path) as source_background:
        background = source_background.convert("RGB")
    pose_by_id = {pose_spec["id"]: pose_spec for pose_spec in phase23["poses"]}
    registered: dict[str, Image.Image] = {}
    for pose_id, source_path in pose_paths.items():
        with Image.open(source_path) as source:
            layer, _ = pour.registered_pose_layer(source, pose_by_id[pose_id], phase23["contact_registration"])
        registered[pose_id] = layer
    smears: dict[int, Image.Image] = {}
    for entry in phase23["timeline"]:
        if entry["type"] == "smear":
            smears[int(entry["start_frame"])] = pour.directional_smear(registered[entry["to_pose_id"]], entry["travel"])
    if expected_asset_hashes is not None:
        _require_equal(
            _phase23_runtime_asset_hashes(contract),
            expected_asset_hashes,
            "Phase23 runtime assets immediately after decode",
        )
    return phase23, background, registered, smears


def _close_pour_assets(background: Image.Image, registered: dict[str, Image.Image], smears: dict[int, Image.Image]) -> None:
    background.close()
    for image in registered.values():
        image.close()
    for image in smears.values():
        image.close()


def _gate(name: str, actual: Any, operator: str, threshold: Any) -> dict[str, Any]:
    if operator == "==":
        passed = actual == threshold
    elif operator == ">=":
        passed = math.isfinite(float(actual)) and float(actual) >= float(threshold)
    elif operator == "<=":
        passed = math.isfinite(float(actual)) and float(actual) <= float(threshold)
    else:
        raise LedgerPourError(f"unsupported gate operator: {operator}")
    return {"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": passed}


def _verify_output_archive(
    path: Path,
    expected_hashes: list[dict[str, Any]],
    *,
    expected_shape: tuple[int, int, int] = (1080, 1920, 3),
    expected_contract_sha256: str,
    expected_hard_cuts: list[int],
) -> int:
    with gzip.open(path, "rb") as archive:
        header = json.loads(archive.readline().decode("utf-8"))
        height, width, channels = expected_shape
        expected_header = {
            "format": ARCHIVE_FORMAT,
            "width": width,
            "height": height,
            "channels": channels,
            "frame_count": len(expected_hashes),
            "frame_bytes": int(np.prod(expected_shape)),
            "xor_seed": "all_zero_rgb24_frame",
            "contract_canonical_sha256": expected_contract_sha256,
            "hard_cut_output_frames": expected_hard_cuts,
        }
        _require_equal(header, expected_header, "Phase36 output archive header")
        shape = expected_shape
        frame_bytes = int(np.prod(shape))
        previous = np.zeros(shape, dtype=np.uint8)
        for frame_number, expected in enumerate(expected_hashes, start=1):
            payload = archive.read(frame_bytes)
            if len(payload) != frame_bytes:
                raise LedgerPourError(f"Phase36 output archive frame {frame_number} is truncated")
            frame = np.bitwise_xor(np.frombuffer(payload, dtype=np.uint8).reshape(shape), previous)
            _require_equal(int(expected["frame"]), frame_number, f"Phase36 output frame {frame_number} number")
            _require_equal(_raw_frame_hash(frame), expected["rgb_sha256"], f"Phase36 output frame {frame_number} hash")
            previous = frame
        if archive.read(1):
            raise LedgerPourError("Phase36 output archive has trailing payload")
    return len(expected_hashes)


def _output_path(contract: dict[str, Any], development_label: str | None) -> Path:
    base = _outputs_path(str(contract["preview"]["directory"]))
    if development_label:
        if not development_label.replace("-", "").replace("_", "").isalnum():
            raise LedgerPourError("development label must contain only letters, digits, dashes, and underscores")
        return base.with_name(f"{base.name}-{development_label}")
    return base


def _required_stage_files(contract: dict[str, Any], *, include_manifest: bool) -> set[str]:
    review = contract["review"]
    names = {
        str(review["all_frames_sheet_filename"]),
        str(review["key_beats_sheet_filename"]),
        str(review["cut_sheet_filename"]),
        str(review["liquid_sheet_filename"]),
        str(review["compassion_sheet_filename"]),
        str(review["blink_eye_stress_sheet_filename"]),
        str(review["lossless_frame_archive_filename"]),
        str(review["pcm_mix_filename"]),
    }
    full_resolution_directory = str(review["full_resolution_directory"])
    names.update(
        f"{full_resolution_directory}/frame_{int(frame):04d}.png"
        for frame in review["full_resolution_review_frames"]
    )
    if include_manifest:
        names.add(str(review["manifest_filename"]))
    return names


def _assert_stage_allowlist(stage: Path, contract: dict[str, Any], *, include_manifest: bool) -> None:
    actual = {
        candidate.relative_to(stage).as_posix()
        for candidate in stage.rglob("*")
        if candidate.is_file()
    }
    _require_equal(actual, _required_stage_files(contract, include_manifest=include_manifest), "Phase36 stage file allowlist")


def write_unencoded_preview(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
    *,
    development_label: str | None = None,
) -> dict[str, Any]:
    contract = load_contract(path, require_external=True)
    attempt_review = _phase35_attempt_review(contract)
    if attempt_review is None:
        raise LedgerPourError(
            "Phase36 build is blocked pending Claude's exact post-attempt real-time A/V verdict"
        )
    output = _output_path(contract, development_label)
    stage = output.parent / f".{output.name}.stage"
    if output.exists() or stage.exists():
        raise LedgerPourError(f"immutable Phase36 output already exists: {output if output.exists() else stage}")
    initial_state = _capture_execution_state(contract, path, attempt_review)
    _require_equal(
        initial_state["self"]["contract_canonical_sha256"],
        EXPECTED_CONTRACT_CANONICAL_SHA256,
        "initial Phase36 canonical contract SHA-256",
    )
    initial_hashes = initial_state["locked"]
    initial_phase23_assets = initial_state["phase23_runtime_assets"]
    external_manifest_path, external_archive_path = _phase35_paths(contract)
    initial_external = initial_state["external"]
    phase35 = _phase35_manifest(contract)
    output.parent.mkdir(parents=True, exist_ok=True)
    review = contract["review"]
    all_sheet = _Sheet(list(range(1, 304)), columns=12, tile_size=(160, 90), title="ALL")
    key_sheet = _Sheet([int(value) for value in review["key_frames"]], columns=4, tile_size=(320, 180), title="KEY")
    cut_sheet = _Sheet([int(value) for value in review["cut_review_frames"]], columns=4, tile_size=(480, 270), title="CUT")
    liquid_sheet = _Sheet([int(value) for value in review["liquid_review_frames"]], columns=4, tile_size=(480, 270), title="POUR")
    compassion_sheet = _Sheet([int(value) for value in review["compassion_review_frames"]], columns=4, tile_size=(320, 180), title="CLOSE")
    sheets = (all_sheet, key_sheet, cut_sheet, liquid_sheet, compassion_sheet)
    blink_eye_sheet = _CropSheet(list(range(244, 253)), columns=3, tile_size=(720, 400), title="EYES")
    full_resolution_dir = stage / str(review["full_resolution_directory"])
    full_resolution_frames = set(int(value) for value in review["full_resolution_review_frames"])
    archive_path = stage / str(review["lossless_frame_archive_filename"])
    mix_path = stage / str(review["pcm_mix_filename"])
    frame_hashes: list[dict[str, Any]] = []
    source_map: list[dict[str, Any]] = []
    liquid_rows: list[dict[str, Any]] = []
    cut_deltas: list[dict[str, Any]] = []
    maximum_face_delta = {"LP020_DIRECT_ADDRESS": 0.0, "LP030_COMPASSION_PUNCH": 0.0}
    maximum_face_pair: dict[str, list[int] | None] = {"LP020_DIRECT_ADDRESS": None, "LP030_COMPASSION_PUNCH": None}
    phase35_exact_reused = 0
    phase35_transformed = 0
    phase35_source_hash_mismatches = 0
    close_crop_locked_frames = 0
    maximum_close_zoom = 0.0
    minimum_close_face_margin = 10_000
    previous = np.zeros((1080, 1920, 3), dtype=np.uint8)
    previous_output: np.ndarray | None = None
    output_frame = 0
    close_camera = contract["shots"][2]["camera"]
    archive_header = {
        "format": ARCHIVE_FORMAT,
        "width": 1920,
        "height": 1080,
        "channels": 3,
        "frame_count": 303,
        "frame_bytes": 1920 * 1080 * 3,
        "xor_seed": "all_zero_rgb24_frame",
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "hard_cut_output_frames": [76, 238],
    }

    def consume(
        frame: np.ndarray,
        mapping: dict[str, Any],
        *,
        face_roi: tuple[int, int, int, int] | None = None,
    ) -> None:
        nonlocal output_frame, previous, previous_output
        output_frame += 1
        _require_equal(frame.shape, (1080, 1920, 3), f"output frame {output_frame} shape")
        _require_equal(frame.dtype, np.dtype(np.uint8), f"output frame {output_frame} dtype")
        mapping = {"output_frame": output_frame, **mapping}
        archive.write(np.bitwise_xor(frame, previous).tobytes(order="C"))
        digest = _raw_frame_hash(frame)
        mapping["output_rgb_sha256"] = digest
        source_map.append(mapping)
        frame_hashes.append({"frame": output_frame, "rgb_sha256": digest})
        for sheet in sheets:
            sheet.add(output_frame, frame)
        if output_frame in full_resolution_frames:
            Image.fromarray(frame, "RGB").save(
                full_resolution_dir / f"frame_{output_frame:04d}.png",
                compress_level=2,
            )
        if output_frame in blink_eye_sheet.positions:
            if "transformed_eye_roi_xyxy" not in mapping:
                raise LedgerPourError(f"blink eye stress frame {output_frame} has no transformed eye ROI")
            blink_eye_sheet.add(
                output_frame,
                frame,
                tuple(int(value) for value in mapping["transformed_eye_roi_xyxy"]),
            )
        if previous_output is not None:
            if output_frame in contract["edit"]["hard_cut_output_frames"]:
                cut_deltas.append({
                    "frames": [output_frame - 1, output_frame],
                    "mean_abs_delta": _mean_abs_delta(previous_output, frame),
                })
            elif output_frame >= 77 and face_roi is not None:
                shot_id = str(mapping["shot_id"])
                value = _max_8x8_delta(previous_output, frame, face_roi)
                if value > maximum_face_delta[shot_id]:
                    maximum_face_delta[shot_id] = value
                    maximum_face_pair[shot_id] = [output_frame - 1, output_frame]
        previous = frame
        previous_output = frame

    phase23: dict[str, Any] | None = None
    background: Image.Image | None = None
    registered: dict[str, Image.Image] = {}
    smears: dict[int, Image.Image] = {}
    verified_execution_checkpoints = [
        "prestage",
        "after_prepare",
        "after_picture",
        "after_audio",
        "pre_manifest",
        "prepublication",
    ]

    def verify_execution_state(checkpoint: str) -> dict[str, Any]:
        current = _capture_execution_state(contract, path, attempt_review)
        _assert_execution_state(initial_state, current, checkpoint)
        return current

    try:
        verify_execution_state("prestage")
        stage.mkdir()
        full_resolution_dir.mkdir()
        with archive_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", compresslevel=4, fileobj=raw, mtime=0) as archive:
                archive.write(json.dumps(archive_header, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
                phase23, background, registered, smears = _prepare_pour(contract, initial_phase23_assets)
                verify_execution_state("after_prepare")
                for source_frame in range(112, 187):
                    entry = pour.timeline_entry_for_frame(phase23["timeline"], source_frame)
                    layer = registered[entry["pose_id"]] if entry["type"] == "pose" else smears[source_frame]
                    image, liquid = pour.compose_pour_frame(background, layer, phase23, source_frame)
                    frame = np.asarray(image, dtype=np.uint8)
                    consume(frame, {
                        "shot_id": "LP010_POUR",
                        "source": "phase23_gs060_deterministic_lossless_rerender",
                        "source_frame": source_frame,
                        "transform": "phase23_camera_exact",
                    })
                    liquid_rows.append({"output_frame": output_frame, "source_frame": source_frame, **liquid})
                    image.close()
                _close_pour_assets(background, registered, smears)
                background, registered, smears = None, {}, {}
                for source_frame, source in iter_phase35_frames(
                    external_archive_path,
                    phase35["frame_hashes"],
                    expected_header=phase35["lossless_archive_header"],
                ):
                    if _raw_frame_hash(source) != phase35["frame_hashes"][source_frame - 1]["rgb_sha256"]:
                        phase35_source_hash_mismatches += 1
                    if source_frame <= 162:
                        frame = source
                        transform = "identity"
                        shot_id = "LP020_DIRECT_ADDRESS"
                        phase35_exact_reused += 1
                        transform_evidence: dict[str, Any] = {}
                        face_roi = FACE_ROI
                    else:
                        frame, transform_evidence = compassion_camera(source, close_camera, source_frame)
                        transform = "phase21_endpoint_and_easing_adaptation_39f_then_lock_to_lossless_rgb"
                        shot_id = "LP030_COMPASSION_PUNCH"
                        phase35_transformed += 1
                        if transform_evidence["camera_locked"]:
                            close_crop_locked_frames += 1
                        maximum_close_zoom = max(maximum_close_zoom, float(transform_evidence["zoom"]))
                        minimum_close_face_margin = min(
                            minimum_close_face_margin,
                            int(transform_evidence["minimum_face_edge_margin_px"]),
                        )
                        face_roi = tuple(int(value) for value in transform_evidence["transformed_face_roi_xyxy"])
                    consume(frame, {
                        "shot_id": shot_id,
                        "source": "phase35_candidate03_exact_lossless_archive",
                        "source_frame": source_frame,
                        "source_rgb_sha256": phase35["frame_hashes"][source_frame - 1]["rgb_sha256"],
                        "transform": transform,
                        **transform_evidence,
                    }, face_roi=face_roi)
        _require_equal(output_frame, 303, "Phase36 rendered frame count")
        for sheet, filename in zip(sheets, (
            review["all_frames_sheet_filename"],
            review["key_beats_sheet_filename"],
            review["cut_sheet_filename"],
            review["liquid_sheet_filename"],
            review["compassion_sheet_filename"],
        )):
            sheet.save(stage / str(filename))
        blink_eye_sheet.save(stage / str(review["blink_eye_stress_sheet_filename"]))
        verify_execution_state("after_picture")
        audio_report = build_exact_audio(contract, mix_path)
        verify_execution_state("after_audio")
        verified_output_frames = _verify_output_archive(
            archive_path,
            frame_hashes,
            expected_contract_sha256=EXPECTED_CONTRACT_CANONICAL_SHA256,
            expected_hard_cuts=[int(value) for value in contract["edit"]["hard_cut_output_frames"]],
        )
        maximum_spill = max(int(row["rendered_spill_pixels_source"]) for row in liquid_rows)
        maximum_spout_error = max(float(row["spout_start_error_px_source"]) for row in liquid_rows)
        minimum_cut_delta = min(float(row["mean_abs_delta"]) for row in cut_deltas)
        final_state = verify_execution_state("pre_manifest")
        final_hashes = final_state["locked"]
        final_phase23_assets = final_state["phase23_runtime_assets"]
        final_external = final_state["external"]
        end_state_mismatches = _execution_state_mismatches(initial_state, final_state)
        _assert_stage_allowlist(stage, contract, include_manifest=False)
        encoded_media_files = 0
        thresholds = contract["preencode_gates"]
        measurements = {
            "input_hash_mismatches": 0,
            "frame_count": len(frame_hashes),
            "source_mapping_count": len(source_map),
            "hard_cut_count": len(cut_deltas),
            "phase35_exact_reused_frames": phase35_exact_reused,
            "phase35_transformed_frames": phase35_transformed,
            "phase23_rendered_frames": sum(row["shot_id"] == "LP010_POUR" for row in source_map),
            "phase35_source_hash_mismatches": phase35_source_hash_mismatches,
            "phase35_external_archive_verified_frames": 228,
            "lossless_output_archive_verified_frames": verified_output_frames,
            "complete_output_hash_inventory": len(frame_hashes) == 303,
            "maximum_liquid_spill_pixels": maximum_spill,
            "maximum_spout_start_error_px_source": maximum_spout_error,
            "minimum_visible_cut_mean_abs_delta": minimum_cut_delta,
            "maximum_direct_address_face_adjacent_8x8_mean_delta": maximum_face_delta["LP020_DIRECT_ADDRESS"],
            "maximum_direct_address_face_pair": maximum_face_pair["LP020_DIRECT_ADDRESS"],
            "maximum_compassion_face_adjacent_8x8_mean_delta": maximum_face_delta["LP030_COMPASSION_PUNCH"],
            "maximum_compassion_face_pair": maximum_face_pair["LP030_COMPASSION_PUNCH"],
            "audio_sample_count": audio_report["probe"]["sample_count"],
            "phase36_bit_exact_audio_samples": audio_report["phase36_bit_exact_scalar_samples"],
            "phase33_bit_exact_audio_samples": audio_report["phase33_bit_exact_scalar_samples"],
            "phase26_stem_array_hash_mismatches": audio_report["phase26_stem_array_hash_mismatches"],
            "audio_boundary_step": audio_report["boundary_step"],
            "close_crop_locked_frames": close_crop_locked_frames,
            "maximum_close_crop_zoom": maximum_close_zoom,
            "minimum_close_face_edge_margin_px": minimum_close_face_margin,
            "full_resolution_review_frames": len(list(full_resolution_dir.glob("frame_*.png"))),
            "blink_eye_stress_frames": len(blink_eye_sheet.positions),
            "pcm_clipped_samples": audio_report["clipped_samples"],
            "audio_peak_dbfs": audio_report["peak_dbfs"],
            "encoded_media_files": encoded_media_files,
            "end_state_hash_mismatch_names": end_state_mismatches,
        }
        gates = [
            _gate("input_hashes", measurements["input_hash_mismatches"], "==", thresholds["required_input_hash_mismatches"]),
            _gate("frame_count", measurements["frame_count"], "==", thresholds["required_frame_count"]),
            _gate("source_mapping", measurements["source_mapping_count"], "==", thresholds["required_source_mapping_count"]),
            _gate("hard_cut_count", measurements["hard_cut_count"], "==", thresholds["required_hard_cut_count"]),
            _gate("phase35_exact_reuse", measurements["phase35_exact_reused_frames"], "==", thresholds["required_phase35_exact_reused_frames"]),
            _gate("phase35_transformed", measurements["phase35_transformed_frames"], "==", thresholds["required_phase35_transformed_frames"]),
            _gate("phase23_rendered", measurements["phase23_rendered_frames"], "==", thresholds["required_phase23_rendered_frames"]),
            _gate("phase35_source_hashes", measurements["phase35_source_hash_mismatches"], "==", thresholds["required_phase35_source_hash_mismatches"]),
            _gate("phase35_archive", measurements["phase35_external_archive_verified_frames"], "==", thresholds["required_phase35_external_archive_verified_frames"]),
            _gate("output_archive", measurements["lossless_output_archive_verified_frames"], "==", thresholds["required_lossless_output_archive_verified_frames"]),
            _gate("output_hash_inventory", measurements["complete_output_hash_inventory"], "==", thresholds["required_complete_output_hash_inventory"]),
            _gate("liquid_spill", measurements["maximum_liquid_spill_pixels"], "==", thresholds["required_liquid_spill_pixels"]),
            _gate("spout_contact", measurements["maximum_spout_start_error_px_source"], "==", thresholds["required_spout_start_error_px_source"]),
            _gate("visible_cuts", measurements["minimum_visible_cut_mean_abs_delta"], ">=", thresholds["minimum_visible_cut_mean_abs_delta"]),
            _gate("direct_address_face_temporal", measurements["maximum_direct_address_face_adjacent_8x8_mean_delta"], "<=", thresholds["maximum_direct_address_face_adjacent_8x8_mean_delta"]),
            _gate("compassion_face_temporal", measurements["maximum_compassion_face_adjacent_8x8_mean_delta"], "<=", thresholds["maximum_compassion_face_adjacent_8x8_mean_delta"]),
            _gate("audio_clock", measurements["audio_sample_count"], "==", thresholds["required_audio_sample_count"]),
            _gate("phase36_audio_exact", measurements["phase36_bit_exact_audio_samples"], "==", thresholds["required_phase36_bit_exact_audio_channel_values"]),
            _gate("phase33_audio_exact", measurements["phase33_bit_exact_audio_samples"], "==", thresholds["required_phase33_bit_exact_audio_channel_values"]),
            _gate("phase26_audio_provenance", measurements["phase26_stem_array_hash_mismatches"], "==", thresholds["required_phase26_stem_array_hash_mismatches"]),
            _gate("audio_boundary_step", measurements["audio_boundary_step"], "<=", thresholds["maximum_audio_boundary_step"]),
            _gate("close_crop_hold", measurements["close_crop_locked_frames"], "==", thresholds["required_close_crop_locked_frames"]),
            _gate("close_crop_zoom", measurements["maximum_close_crop_zoom"], "<=", thresholds["maximum_close_crop_zoom"]),
            _gate("close_face_margin", measurements["minimum_close_face_edge_margin_px"], ">=", thresholds["minimum_close_face_edge_margin_px"]),
            _gate("full_resolution_evidence", measurements["full_resolution_review_frames"], "==", thresholds["required_full_resolution_review_frames"]),
            _gate("blink_eye_stress_evidence", measurements["blink_eye_stress_frames"], "==", thresholds["required_blink_eye_stress_frames"]),
            _gate("pcm_clipping", measurements["pcm_clipped_samples"], "==", thresholds["required_pcm_clipped_samples"]),
            _gate("audio_peak", measurements["audio_peak_dbfs"], "<=", thresholds["maximum_audio_peak_dbfs"]),
            _gate("unencoded_media", measurements["encoded_media_files"], "==", thresholds["required_encoded_media_files"]),
            _gate("end_state_hashes", len(end_state_mismatches), "==", thresholds["required_end_state_hash_mismatches"]),
        ]
        failures = [gate for gate in gates if not gate["passed"]]
        manifest = {
            "manifest_version": 1,
            "development_label": development_label,
            "status": "preencode_machine_passed_exact_frame_audio_review_required" if not failures else "preencode_machine_failed",
            "machine_passed": not failures,
            "accepted_full_cartoon_production_delivery": False,
            "encode_authorized": False,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": initial_state["self"]["contract_raw_sha256"],
                "canonical_sha256": initial_state["self"]["contract_canonical_sha256"],
            },
            "implementation": {
                "path": "pipeline/cartoon_ledger_pour.py",
                "sha256": initial_state["self"]["implementation_sha256"],
            },
            "toolchain": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "pillow": PIL.__version__,
                "gzip_mtime": 0,
                "gzip_compresslevel": 4,
            },
            "clock": contract["clock"],
            "shots": contract["shots"],
            "edit": {"hard_cuts": cut_deltas, "cross_dissolve_used": False, "optical_flow_used": False, "retiming_used": False},
            "source_evidence": {
                "phase23_contract_sha256": contract["locks"]["phase23_contract"]["sha256"],
                "phase23_renderer_sha256": contract["locks"]["phase23_renderer"]["sha256"],
                "phase35_manifest_sha256": contract["locks"]["phase35_manifest"]["sha256"],
                "phase35_archive_sha256": contract["source_evidence"]["phase35_archive_sha256"],
                "phase35_visual_acceptance_sha256": contract["locks"]["phase35_visual_acceptance"]["sha256"],
                "phase35_attempt_review": initial_state["phase35_attempt_review"],
            },
            "execution_state": {
                "initial": initial_state,
                "final": final_state,
                "verified_checkpoints": verified_execution_checkpoints,
                "initial_locked_hashes": initial_hashes,
                "final_locked_hashes": final_hashes,
                "initial_external_hashes": initial_external,
                "final_external_hashes": final_external,
                "initial_phase23_runtime_asset_hashes": initial_phase23_assets,
                "final_phase23_runtime_asset_hashes": final_phase23_assets,
                "mismatch_names": end_state_mismatches,
            },
            "audio": audio_report,
            "measurements": measurements,
            "gates": gates,
            "failed_gates": [gate["name"] for gate in failures],
            "frame_hashes": frame_hashes,
            "lossless_archive_header": archive_header,
            "source_map": source_map,
            "liquid_evidence": liquid_rows,
            "artifacts": {},
            "promotion": contract["promotion_policy"],
        }
        for name in (
            review["all_frames_sheet_filename"], review["key_beats_sheet_filename"],
            review["cut_sheet_filename"], review["liquid_sheet_filename"],
            review["compassion_sheet_filename"], review["lossless_frame_archive_filename"],
            review["blink_eye_stress_sheet_filename"], review["pcm_mix_filename"],
        ):
            artifact = stage / str(name)
            manifest["artifacts"][str(name)] = {
                "sha256": _sha256(artifact),
                "bytes": artifact.stat().st_size,
            }
        for artifact in sorted(full_resolution_dir.glob("frame_*.png")):
            manifest["artifacts"][f"{review['full_resolution_directory']}/{artifact.name}"] = {
                "sha256": _sha256(artifact),
                "bytes": artifact.stat().st_size,
            }
        manifest_path = stage / str(review["manifest_filename"])
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if failures:
            raise LedgerPourError("Phase36 machine gates failed: " + ", ".join(gate["name"] for gate in failures))
        _assert_stage_allowlist(stage, contract, include_manifest=True)
        verify_execution_state("prepublication")
        os.replace(stage, output)
    except BaseException:
        if background is not None:
            _close_pour_assets(background, registered, smears)
        for sheet in sheets:
            try:
                sheet.image.close()
            except Exception:
                pass
        try:
            blink_eye_sheet.image.close()
        except Exception:
            pass
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        "output_directory": str(output),
        "manifest": str(output / str(review["manifest_filename"])),
        "manifest_sha256": _sha256(output / str(review["manifest_filename"])),
        "lossless_archive": str(output / str(review["lossless_frame_archive_filename"])),
        "lossless_archive_sha256": _sha256(output / str(review["lossless_frame_archive_filename"])),
        "pcm_mix": str(output / str(review["pcm_mix_filename"])),
        "pcm_mix_sha256": _sha256(output / str(review["pcm_mix_filename"])),
        "frame_count": 303,
        "gate_count": 30,
        "machine_passed": True,
        "encode_authorized": False,
    }


def preflight(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    contract = load_contract(path, require_external=True)
    attempt_review = _phase35_attempt_review(contract)
    output = _output_path(contract, None)

    def output_state() -> list[tuple[str, int, int]] | None:
        if not output.exists():
            return None
        return sorted(
            (str(candidate.relative_to(output)), candidate.stat().st_size, candidate.stat().st_mtime_ns)
            for candidate in output.rglob("*") if candidate.is_file()
        )

    state_before = output_state()
    manifest = _phase35_manifest(contract)
    phase23_assets = _phase23_runtime_asset_hashes(contract)
    phase33_samples, phase33_probe = _read_pcm24_wave(
        _repo_path(str(contract["locks"]["phase33_delivery_mix"]["path"]))
    )
    _require_equal(phase33_samples.shape, (364800, 2), "preflight Phase33 audio sample shape")
    _require_equal(
        phase33_probe["data_sha256"],
        contract["audio"]["direct_address_segment"]["pcm_data_sha256"],
        "preflight Phase33 PCM data SHA-256",
    )
    external_manifest, external_archive = _phase35_paths(contract)
    decoded_phase35_frames = sum(
        1 for _ in iter_phase35_frames(
            external_archive,
            manifest["frame_hashes"],
            expected_header=manifest["lossless_archive_header"],
        )
    )
    phase23, background, registered, smears = _prepare_pour(contract, phase23_assets)
    try:
        _require_equal(phase23["output"]["frame_count"], 258, "preflight Phase23 frame count")
    finally:
        _close_pour_assets(background, registered, smears)
    with tempfile.TemporaryDirectory(prefix="phase36-preflight-") as temporary:
        audio_report = build_exact_audio(contract, Path(temporary) / "phase36-preflight.wav")
    state_after = output_state()
    _require_equal(state_after, state_before, "preflight output state")
    return {
        "contract_id": contract["contract_id"],
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "phase35_manifest_sha256": _sha256(external_manifest),
        "phase35_archive_sha256": _sha256(external_archive),
        "phase35_frame_hashes": len(manifest["frame_hashes"]),
        "phase35_decoded_frames": decoded_phase35_frames,
        "phase23_runtime_assets": len(phase23_assets),
        "phase33_audio_samples": phase33_probe["sample_count"],
        "phase36_audio_samples": audio_report["probe"]["sample_count"],
        "phase26_stem_hash_mismatches": audio_report["phase26_stem_array_hash_mismatches"],
        "phase35_attempt_review_authorized": attempt_review is not None,
        "phase35_attempt_review": attempt_review,
        "build_authorized": attempt_review is not None,
        "output_created": state_after != state_before,
        "encode_authorized": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="verify all bound inputs without creating output")
    build = subparsers.add_parser("build-unencoded", help="build only lossless RGB/PCM/review evidence")
    build.add_argument("--development-label")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = preflight() if args.command == "preflight" else write_unencoded_preview(
        development_label=args.development_label,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
