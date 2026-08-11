"""Fail-closed Phase36 ProRes 4444 + PCM24 review-master transaction."""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from typing import Any, BinaryIO, Iterator

import numpy as np
from PIL import Image, __version__ as PILLOW_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase36_prores4444_review_master_v1.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_ledger_pour_prores_master.py"
# Only authorization.receipt is normalized away. The VUI result remains part of the
# reviewed subject, so it must be bound before master authorization is requested.
EXPECTED_AUTHORIZATION_SUBJECT_SHA256 = "6362252d62d02a950461f200468665472d0da71bb70f7d81651eed4630afdba7"


class ProResMasterError(RuntimeError):
    """Raised when any immutable review-master invariant is violated."""


class ClaimWriteError(ProResMasterError):
    """A final-path claim exists, but its durable write did not complete."""

    def __init__(self, claim: Path, cause: BaseException) -> None:
        super().__init__(f"attempt claim was created but could not be durably written: {cause}")
        self.claim = claim


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ProResMasterError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _lf_hash(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strict_json_loads(payload: bytes, label: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProResMasterError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ProResMasterError(f"{label} contains non-finite value {value}")

    try:
        return json.loads(
            payload.decode("utf-8"), object_pairs_hook=object_pairs, parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProResMasterError(f"{label} is not strict UTF-8 JSON") from exc


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ProResMasterError(f"repository path escapes the repository: {relative}") from exc
    if not path.is_file():
        raise ProResMasterError(f"required repository file is missing: {relative}")
    return path


def _outputs_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    root = (REPO_ROOT / "../../outputs").resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ProResMasterError(f"path escapes the pinned outputs tree: {relative}") from exc
    return path


def _lock_hash(reference: dict[str, Any]) -> str:
    path = _repo_path(str(reference["path"]))
    if reference.get("hash_domain", "raw_bytes") == "lf_normalized_text":
        return _lf_hash(path)
    return _sha256(path)


def _authorization_subject(contract: dict[str, Any]) -> dict[str, Any]:
    subject = copy.deepcopy(contract)
    subject["authorization"]["receipt"] = None
    return subject


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned contract path")
    contract = _strict_json_loads(resolved.read_bytes(), "ProRes master contract")
    _require_equal(
        _canonical_hash(_authorization_subject(contract)),
        EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
        "authorization-subject canonical SHA-256",
    )
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase36_prores4444_review_master_v1", "contract id")
    _require_equal(contract["cash_cost"], 0, "cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "paid dependency policy")
    _require_equal(contract["network_runtime_required"], False, "network policy")
    _require_equal(contract["clock"], {
        "width": 1920, "height": 1080, "source_pixel_format": "rgb24", "fps": 30,
        "frame_count": 303, "duration_seconds": 10.1, "video_track_timescale": 15360,
        "sample_aspect_ratio": "1:1",
    }, "master clock")
    encoding = contract["encoding"]
    for key, expected in {
        "video_codec": "prores_ks", "profile": 4, "encoder_input_pixel_format": "yuv444p10le",
        "decoded_pixel_format": "yuv444p12le", "decoded_bits_per_raw_sample": 12, "alpha_bits": 0,
        "codec_tag": "ap4h", "color_range": "tv", "color_space": "bt709",
        "color_transfer": "bt709", "color_primaries": "bt709",
        "audio_codec": "pcm_s24le", "audio_sample_rate": 48000, "audio_channels": 2,
    }.items():
        _require_equal(encoding[key], expected, f"encoding {key}")
    failure = contract["failure_policy"]
    for key in (
        "fallback_allowed", "automatic_reencode_allowed", "renderer_invocation_allowed",
        "picture_mutation_allowed", "audio_mutation_allowed", "network_allowed",
        "distribution_encode_allowed", "promotion_allowed",
    ):
        _require_equal(failure[key], False, f"failure policy {key}")
    for name, reference in contract["locks"].items():
        _require_equal(_lock_hash(reference), reference["sha256"], f"locked {name} SHA-256")
    return contract


def _command_template(contract: dict[str, Any]) -> list[str]:
    encoding = contract["encoding"]
    clock = contract["clock"]
    scale = (
        "scale=in_range=full:out_range=limited:out_color_matrix=bt709:"
        f"flags={encoding['scale_flags']},format={encoding['encoder_input_pixel_format']},"
        f"setsar=1,{encoding['frame_metadata_filter']}"
    )
    return [
        "$FFMPEG", "-hide_banner", "-loglevel", "error", "-xerror",
        "-abort_on", "empty_output+empty_output_stream",
        "-f", "rawvideo", "-pixel_format", str(clock["source_pixel_format"]),
        "-video_size", f"{clock['width']}x{clock['height']}",
        "-framerate", str(clock["fps"]), "-i", "pipe:0",
        "-i", "$AUDIO", "-map", "0:v:0", "-map", "1:a:0",
        "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn",
        "-frames:v", str(clock["frame_count"]), "-vf", scale,
        "-c:v", str(encoding["video_codec"]), "-profile:v", str(encoding["profile"]),
        "-pix_fmt", str(encoding["encoder_input_pixel_format"]),
        "-alpha_bits", str(encoding["alpha_bits"]), "-tag:v", str(encoding["codec_tag"]),
        "-color_range", str(encoding["color_range"]), "-colorspace", str(encoding["color_space"]),
        "-color_primaries", str(encoding["color_primaries"]),
        "-color_trc", str(encoding["color_transfer"]),
        "-c:a", str(encoding["audio_codec"]), "-ar", str(encoding["audio_sample_rate"]),
        "-ac", str(encoding["audio_channels"]),
        "-af", f"atrim=end_sample={contract['audio']['sample_count']},asetpts=PTS-STARTPTS",
        "-video_track_timescale", str(clock["video_track_timescale"]),
        "-fps_mode", str(encoding["fps_mode"]),
        "-movflags", str(encoding["movflags"]), "-n", "$OUTPUT",
    ]


def _command_template_hash(contract: dict[str, Any]) -> str:
    return _canonical_hash(_command_template(contract))


def _vui_result(contract: dict[str, Any]) -> dict[str, Any] | None:
    gate = contract["vui_prerequisite"]
    reference = gate.get("probe_result_receipt")
    if reference is None:
        return None
    if not isinstance(reference, dict):
        raise ProResMasterError("VUI result receipt must be null or an exact path/hash lock")
    _require_equal(reference, contract["locks"]["vui_probe_v2_report"], "VUI report lock identity")
    path = _repo_path(str(reference["path"]))
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    _require_equal(digest, reference["sha256"], "VUI result receipt SHA-256")
    result = _strict_json_loads(payload, "VUI result receipt")
    evidence_root = path.parent
    package_path = _repo_path(str(contract["locks"]["vui_probe_v2_package"]["path"]))
    video_path = _repo_path(str(contract["locks"]["vui_probe_v2_video"]["path"]))
    claim_path = _repo_path(str(contract["locks"]["vui_probe_v2_claim"]["path"]))
    _require_equal(package_path.parent, evidence_root, "VUI package evidence directory")
    _require_equal(video_path.parent, evidence_root, "VUI video evidence directory")
    _require_equal(claim_path.parent, evidence_root, "VUI claim evidence directory")
    package = _strict_json_loads(package_path.read_bytes(), "VUI result package")
    expected_artifacts = {
        "attempt-claim-v1.json", "decode-stderr-v1.txt", "ffmpeg-stderr-v1.txt",
        "ffprobe-frames-stderr-v1.txt", "ffprobe-frames-v1.json",
        "ffprobe-stream-stderr-v1.txt", "ffprobe-stream-v1.json",
        "h264-sps-trace-v1.txt", "june-phase35-c03-blink-vui-probe-v2.mp4",
        "probe-report-v1.json",
    }
    _require_equal(package["package_version"], 1, "VUI package version")
    _require_equal(package["attempt_id"], "phase35_c03_blink_vui_probe_v2_attempt02", "VUI package attempt id")
    _require_equal(package["machine_passed"], True, "VUI package machine result")
    _require_equal(package["authorization_consumed"], True, "VUI package authorization consumption")
    artifacts = package["artifacts"]
    _require_equal([item["file"] for item in artifacts], sorted(expected_artifacts), "VUI package artifact order")
    _require_equal(
        {item.name for item in evidence_root.iterdir() if item.is_file()},
        expected_artifacts | {package_path.name},
        "VUI evidence directory inventory",
    )
    for artifact in artifacts:
        artifact_path = evidence_root / artifact["file"]
        _require_equal(artifact_path.stat().st_size, artifact["bytes"], f"VUI artifact bytes {artifact_path.name}")
        _require_equal(_sha256(artifact_path), artifact["sha256"], f"VUI artifact hash {artifact_path.name}")
    _require_equal(result["machine_passed"], gate["required_machine_passed"], "VUI machine result")
    _require_equal(result["status"], gate["required_status"], "VUI report status")
    _require_equal(
        result["encoder"]["process_count"], gate["required_encoding_process_count"], "VUI encoder count",
    )
    _require_equal(result["disposition"]["retry_allowed"], gate["required_retry_allowed"], "VUI retry disposition")
    _require_equal(result["gate_count"], gate["required_gate_count"], "VUI gate count")
    _require_equal(result["gates_passed"], gate["required_gate_count"], "VUI gates passed")
    _require_equal(result["gates_failed"], gate["required_gates_failed"], "VUI gates failed")
    _require_equal(result["failed_gates"], [], "VUI failed gate names")
    _require_equal(all(item["passed"] for item in result["gates"]), True, "VUI individual gates")
    _require_equal(result["decoded"]["decoded_frame_count"], gate["required_decoded_frame_count"], "VUI decoded frame count")
    _require_equal(result["decoded"]["decoded_rgb24_sha256"], gate["required_decoded_rgb24_sha256"], "VUI decoded RGB24 hash")
    _require_equal(result["video"]["sha256"], gate["required_video_sha256"], "VUI report video hash")
    _require_equal(result["video"]["sha256"], _sha256(video_path), "VUI video bytes")
    _require_equal(result["attempt_claim"]["sha256"], _sha256(claim_path), "VUI claim bytes")
    stream = result["stream_probe"]["streams"][0]
    _require_equal(isinstance(stream, dict), True, "VUI stream JSON object")
    _require_equal(
        {field: stream.get(field) for field in gate["required_stream_color"]},
        gate["required_stream_color"],
        "VUI stream color metadata",
    )
    for index, frame in enumerate(result["frame_probe"]["frames"], start=1):
        _require_equal(
            {field: frame.get(field) for field in gate["required_stream_color"]},
            gate["required_stream_color"],
            f"VUI frame {index} color metadata",
        )
    _require_equal(result["mp4_colr"], [gate["required_mp4_colr"]], "VUI MP4 colr")
    _require_equal(package["disposition"], result["disposition"], "VUI package disposition")
    captured = result["captured_state"]
    _require_equal(captured["contract_raw_sha256"], contract["locks"]["vui_probe_v2_contract"]["sha256"], "VUI captured contract hash")
    for field, expected in {
        "authorization_subject_sha256": gate["probe_authorization_subject_sha256"],
        "implementation_sha256": gate["probe_implementation_sha256"],
        "command_template_sha256": gate["probe_command_template_sha256"],
    }.items():
        _require_equal(captured[field], expected, f"VUI captured {field}")
    probe_contract_path = _repo_path(str(contract["locks"]["vui_probe_v2_contract"]["path"]))
    probe_contract = _strict_json_loads(probe_contract_path.read_bytes(), "VUI probe contract")
    _require_equal(
        captured["locks"],
        {name: item["sha256"] for name, item in sorted(probe_contract["locks"].items())},
        "VUI captured repository locks",
    )
    _require_equal(
        captured["authorization"]["sha256"],
        contract["locks"]["vui_probe_v2_authorization_receipt"]["sha256"],
        "VUI captured authorization receipt",
    )
    return {
        "path": str(reference["path"]), "sha256": digest, "report": result,
        "package_sha256": _sha256(package_path), "video_sha256": _sha256(video_path),
        "claim_sha256": _sha256(claim_path),
    }


def _authorization(contract: dict[str, Any], vui: dict[str, Any] | None) -> dict[str, str] | None:
    gate = contract["authorization"]
    reference = gate.get("receipt")
    if reference is None:
        return None
    if vui is None:
        raise ProResMasterError("master authorization cannot be consumed before a passing VUI result is bound")
    if not isinstance(reference, dict):
        raise ProResMasterError("master authorization receipt must be null or an exact path/hash lock")
    path = _repo_path(str(reference["path"]))
    domain = reference.get("hash_domain", "raw_bytes")
    digest = _lf_hash(path) if domain == "lf_normalized_text" else _sha256(path)
    _require_equal(digest, reference["sha256"], "master authorization receipt SHA-256")
    text = path.read_text(encoding="utf-8")
    verdict = f'{gate["required_verdict_field"]} {gate["required_verdict"]}'
    prefix = str(gate["required_verdict_field"])
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith(prefix)]
    _require_equal(lines, [verdict], "master authorization verdict lines")
    tokens = [
        EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
        _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
        _command_template_hash(contract),
        contract["vui_prerequisite"]["source_commit"],
        vui["sha256"],
        vui["package_sha256"],
        vui["video_sha256"],
        vui["claim_sha256"],
        contract["picture"]["archive_sha256"],
        contract["picture"]["frame_inventory_canonical_sha256"],
        contract["audio"]["wav_sha256"],
        contract["audio"]["pcm_data_sha256"],
        contract["toolchain"]["ffmpeg_sha256"],
        contract["toolchain"]["ffprobe_sha256"],
    ]
    tokens.extend(reference["sha256"] for _, reference in sorted(contract["locks"].items()))
    for token in tokens:
        if token not in text:
            raise ProResMasterError(f"master authorization receipt omits binding token: {token}")
    return {"path": str(reference["path"]), "hash_domain": str(domain), "sha256": digest, "verdict": gate["required_verdict"]}


def _read_exact(handle: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = handle.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _picture_inputs(contract: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    manifest_path = _repo_path(str(contract["locks"]["picture_manifest"]["path"]))
    manifest = _strict_json_loads(manifest_path.read_bytes(), "picture manifest")
    picture = contract["picture"]
    _require_equal(manifest["machine_passed"], True, "accepted picture machine result")
    _require_equal(manifest["measurements"]["frame_count"], 303, "picture manifest frame count")
    _require_equal(len(manifest["frame_hashes"]), 303, "picture frame inventory length")
    _require_equal(
        _canonical_hash(manifest["frame_hashes"]),
        picture["frame_inventory_canonical_sha256"],
        "picture frame inventory canonical SHA-256",
    )
    archive = _outputs_path(str(picture["external_archive_path"]))
    if not archive.is_file():
        raise ProResMasterError(f"accepted picture archive is missing: {archive}")
    _require_equal(archive.stat().st_size, picture["archive_bytes"], "picture archive bytes")
    _require_equal(_sha256(archive), picture["archive_sha256"], "picture archive SHA-256")
    return archive, manifest


def _iter_picture_frames(
    archive: Path, manifest: dict[str, Any], contract: dict[str, Any],
) -> Iterator[np.ndarray]:
    expected_header = contract["picture"]["archive_header"]
    inventory = manifest["frame_hashes"]
    with gzip.open(archive, "rb") as handle:
        header = _strict_json_loads(handle.readline(), "picture archive header")
        _require_equal(header, expected_header, "picture archive header")
        shape = (header["height"], header["width"], header["channels"])
        previous = np.zeros(shape, dtype=np.uint8)
        for frame_number, expected in enumerate(inventory, start=1):
            payload = _read_exact(handle, header["frame_bytes"])
            if len(payload) != header["frame_bytes"]:
                raise ProResMasterError(f"picture archive frame {frame_number} is truncated")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous)
            digest = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
            _require_equal(expected, {"frame": frame_number, "rgb_sha256": digest}, f"picture frame {frame_number}")
            yield frame
            previous = frame
        if handle.read(1):
            raise ProResMasterError("picture archive has trailing decompressed payload")


def _read_pcm24_data(path: Path, contract: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ProResMasterError("audio master is not a RIFF/WAVE file")
    _require_equal(struct.unpack("<I", raw[4:8])[0] + 8, len(raw), "audio RIFF geometry")
    cursor = 12
    fmt: bytes | None = None
    pcm: bytes | None = None
    while cursor < len(raw):
        if cursor + 8 > len(raw):
            raise ProResMasterError("audio master has a truncated chunk header")
        chunk_id = raw[cursor:cursor + 4]
        size = struct.unpack("<I", raw[cursor + 4:cursor + 8])[0]
        start = cursor + 8
        end = start + size
        if end > len(raw):
            raise ProResMasterError("audio master has a truncated chunk")
        if chunk_id == b"fmt ":
            if fmt is not None:
                raise ProResMasterError("audio master has duplicate fmt chunks")
            fmt = raw[start:end]
        elif chunk_id == b"data":
            if pcm is not None:
                raise ProResMasterError("audio master has duplicate data chunks")
            pcm = raw[start:end]
        cursor = end + (size & 1)
    if fmt is None or pcm is None or len(fmt) < 16:
        raise ProResMasterError("audio master omits fmt/data chunks")
    tag, channels, rate, byte_rate, align, bits = struct.unpack("<HHIIHH", fmt[:16])
    if tag not in (1, 0xFFFE):
        raise ProResMasterError("audio master is compressed")
    audio = contract["audio"]
    _require_equal((channels, rate, bits, align, byte_rate), (2, 48000, 24, 6, 288000), "audio PCM geometry")
    _require_equal(len(pcm) // align, audio["sample_count"], "audio PCM sample count")
    _require_equal(hashlib.sha256(pcm).hexdigest(), audio["pcm_data_sha256"], "audio PCM data SHA-256")
    return pcm, {"sample_rate": rate, "channels": channels, "bits_per_sample": bits, "sample_count": len(pcm) // align, "data_sha256": hashlib.sha256(pcm).hexdigest()}


def _resolved_tool(executable: str) -> Path:
    located = shutil.which(executable)
    if located is None:
        candidate = Path(executable).resolve()
        if not candidate.is_file():
            raise ProResMasterError(f"required executable was not found: {executable}")
        located = str(candidate)
    return Path(located).resolve()


def _validate_toolchain(ffmpeg: Path, ffprobe: Path, contract: dict[str, Any]) -> dict[str, Any]:
    tools = contract["toolchain"]
    _require_equal(PILLOW_VERSION, tools["pillow_version"], "Pillow version")
    _require_equal(_sha256(ffmpeg), tools["ffmpeg_sha256"], "FFmpeg executable SHA-256")
    _require_equal(_sha256(ffprobe), tools["ffprobe_sha256"], "FFprobe executable SHA-256")
    versions: dict[str, str] = {}
    for name, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)):
        result = subprocess.run([str(path), "-version"], check=True, capture_output=True, text=True)
        first = result.stdout.splitlines()[0]
        if not first.startswith(f"{name} version {tools['version']} "):
            raise ProResMasterError(f"unexpected {name} version: {first}")
        versions[name] = first
    checks = [
        ("encoder", tools["required_video_encoder"], "Encoder prores_ks"),
        ("decoder", tools["required_video_decoder"], "Decoder prores"),
        ("encoder", tools["required_audio_encoder"], "Encoder pcm_s24le"),
        ("demuxer", tools["required_input_demuxer"], "Demuxer rawvideo"),
        ("muxer", tools["required_output_muxer"], "Muxer mov"),
    ]
    help_text: dict[str, str] = {}
    commands: list[list[str]] = []
    for kind, name, marker in checks:
        command = [str(ffmpeg), "-hide_banner", "-h", f"{kind}={name}"]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        output = result.stdout + result.stderr
        if marker not in output or "Unknown" in output:
            raise ProResMasterError(f"required FFmpeg {kind} is unavailable: {name}")
        commands.append(command)
        help_text[f"{kind}:{name}"] = output
    video_help = help_text["encoder:prores_ks"]
    for marker in ("4444", "yuv444p10le"):
        if marker not in video_help:
            raise ProResMasterError(f"prores_ks help omits required capability: {marker}")
    muxer_help = help_text["muxer:mov"]
    for marker in tools["required_muxer_flags"]:
        if marker not in muxer_help:
            raise ProResMasterError(f"MOV muxer help omits required flag: {marker}")
    filters = subprocess.run([str(ffmpeg), "-hide_banner", "-filters"], check=True, capture_output=True, text=True)
    filter_text = filters.stdout + filters.stderr
    for name in tools["required_filters"]:
        if name not in filter_text:
            raise ProResMasterError(f"FFmpeg filter list omits required filter: {name}")
    return {
        "ffmpeg": {"path": str(ffmpeg), "sha256": _sha256(ffmpeg), "version": versions["ffmpeg"]},
        "ffprobe": {"path": str(ffprobe), "sha256": _sha256(ffprobe), "version": versions["ffprobe"]},
        "pillow_version": PILLOW_VERSION,
        "help_commands": commands,
    }


def _prepare(contract: dict[str, Any], ffmpeg: Path, ffprobe: Path) -> dict[str, Any]:
    archive, manifest = _picture_inputs(contract)
    verified = 0
    combined = hashlib.sha256()
    for frame in _iter_picture_frames(archive, manifest, contract):
        verified += 1
        combined.update(np.ascontiguousarray(frame).tobytes())
    _require_equal(verified, 303, "verified picture frames")
    audio_path = _repo_path(str(contract["locks"]["audio_wav"]["path"]))
    _require_equal(_sha256(audio_path), contract["audio"]["wav_sha256"], "audio WAV SHA-256")
    _, audio_probe = _read_pcm24_data(audio_path, contract)
    toolchain = _validate_toolchain(ffmpeg, ffprobe, contract)
    return {
        "archive": archive, "manifest": manifest, "audio_path": audio_path,
        "picture_audit": {"verified_frames": verified, "combined_rgb24_sha256": combined.hexdigest()},
        "audio_audit": audio_probe, "toolchain": toolchain,
    }


def preflight(*, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    contract = load_contract()
    ffmpeg_path = _resolved_tool(ffmpeg)
    ffprobe_path = _resolved_tool(ffprobe)
    prepared = _prepare(contract, ffmpeg_path, ffprobe_path)
    vui = _vui_result(contract)
    authorization = _authorization(contract, vui)
    return {
        "status": "READY_FOR_AUTHORIZED_ATTEMPT" if authorization else "BLOCKED_NO_MEDIA_PROCESS_STARTED",
        "cash_cost": 0,
        "picture": prepared["picture_audit"],
        "audio": prepared["audio_audit"],
        "toolchain": prepared["toolchain"],
        "vui_prerequisite_bound": vui is not None,
        "master_authorization_bound": authorization is not None,
        "authorization_subject_sha256": EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
        "implementation_sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
        "command_template": _command_template(contract),
        "command_template_sha256": _command_template_hash(contract),
        "encoder_processes_started": 0,
        "output_resolved": False,
        "next_action": (
            "bind passing VUI probe result before requesting master authorization"
            if vui is None else "bind exact master authorization receipt"
            if authorization is None else "run the one authorized ProRes master attempt"
        ),
    }


def _encoder_command(contract: dict[str, Any], ffmpeg: Path, audio: Path, output: Path) -> list[str]:
    replacements = {"$FFMPEG": str(ffmpeg), "$AUDIO": str(audio), "$OUTPUT": str(output)}
    return [replacements.get(token, token) for token in _command_template(contract)]


def _capture_state(
    contract: dict[str, Any], ffmpeg: Path, ffprobe: Path,
    vui: dict[str, Any], authorization: dict[str, str],
) -> dict[str, Any]:
    archive = _outputs_path(str(contract["picture"]["external_archive_path"]))
    return {
        "contract_raw_sha256": _sha256(REPO_ROOT / CONTRACT_RELATIVE_PATH),
        "authorization_subject_sha256": _canonical_hash(_authorization_subject(contract)),
        "implementation_sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
        "command_template_sha256": _command_template_hash(contract),
        "locks": {name: _lock_hash(reference) for name, reference in sorted(contract["locks"].items())},
        "picture_archive_sha256": _sha256(archive),
        "ffmpeg_sha256": _sha256(ffmpeg),
        "ffprobe_sha256": _sha256(ffprobe),
        "vui_result": {"path": vui["path"], "sha256": vui["sha256"]},
        "authorization": authorization,
    }


def _assert_state(state: dict[str, Any], contract: dict[str, Any]) -> None:
    _require_equal(state["authorization_subject_sha256"], EXPECTED_AUTHORIZATION_SUBJECT_SHA256, "state authorization subject")
    _require_equal(state["command_template_sha256"], _command_template_hash(contract), "state command template")
    _require_equal(
        state["locks"],
        {name: reference["sha256"] for name, reference in sorted(contract["locks"].items())},
        "state repository locks",
    )
    _require_equal(state["picture_archive_sha256"], contract["picture"]["archive_sha256"], "state picture archive")
    _require_equal(state["ffmpeg_sha256"], contract["toolchain"]["ffmpeg_sha256"], "state FFmpeg")
    _require_equal(state["ffprobe_sha256"], contract["toolchain"]["ffprobe_sha256"], "state FFprobe")


def _claim_attempt(output: Path, state: dict[str, Any], command: list[str]) -> Path:
    claim = output.parent / f".{output.name}.attempt01-claim.json"
    payload = {
        "claim_version": 1,
        "attempt_id": "phase36_prores4444_review_master_v1_attempt01",
        "authorization_consumed_on_postclaim_failure": True,
        "captured_state": state,
        "encoder_command": command,
        "maximum_encoder_processes": 1,
        "automatic_retry_allowed": False,
    }
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    try:
        descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ProResMasterError(f"the single master attempt is already claimed: {claim}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException as exc:
        # A successfully-created claim is never removed: even an incomplete durable
        # write consumes the transaction and is handled as postclaim failure.
        raise ClaimWriteError(claim, exc) from exc
    return claim


def _run_json(command: list[str], stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        result = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
    if result.returncode != 0:
        raise ProResMasterError(f"diagnostic command failed with exit {result.returncode}: {command}")
    return _strict_json_loads(stdout_path.read_bytes(), stdout_path.name)


def _probe_media(media: Path, ffprobe: Path, stage: Path, contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    stream_path = stage / str(contract["output"]["stream_probe_filename"])
    stream_stderr = stage / "ffprobe-stream-stderr-v1.txt"
    stream_command = [
        str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(media),
    ]
    stream = _run_json(stream_command, stream_path, stream_stderr)
    frame_path = stage / str(contract["output"]["frame_probe_filename"])
    frame_stderr = stage / "ffprobe-frames-stderr-v1.txt"
    frame_command = [
        str(ffprobe), "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries",
        "frame=media_type,stream_index,best_effort_timestamp,best_effort_timestamp_time,pkt_duration,pkt_duration_time,color_range,color_space,color_transfer,color_primaries,pix_fmt,width,height",
        "-of", "json", str(media),
    ]
    frames = _run_json(frame_command, frame_path, frame_stderr)
    return stream, frames, {"stream_probe": stream_command, "frame_probe": frame_command}


def _walk_mov_atoms(data: bytes, start: int, end: int, path: tuple[str, ...]) -> Iterator[dict[str, Any]]:
    cursor = start
    containers = {"moov", "trak", "mdia", "minf", "stbl"}
    while cursor + 8 <= end:
        size32, raw_type = struct.unpack(">I4s", data[cursor:cursor + 8])
        atom_type = raw_type.decode("latin1")
        header = 8
        if size32 == 1:
            if cursor + 16 > end:
                raise ProResMasterError("MOV atom has a truncated extended size")
            size = struct.unpack(">Q", data[cursor + 8:cursor + 16])[0]
            header = 16
        elif size32 == 0:
            size = end - cursor
        else:
            size = size32
        if size < header or cursor + size > end:
            raise ProResMasterError(f"MOV atom {atom_type!r} has invalid geometry")
        atom_path = path + (atom_type,)
        yield {"type": atom_type, "path": "/".join(atom_path), "start": cursor, "size": size, "header": header}
        child_start = cursor + header
        if atom_type in containers:
            yield from _walk_mov_atoms(data, child_start, cursor + size, atom_path)
        elif atom_type == "stsd":
            child_start += 8  # full-box flags/version and entry count
            yield from _walk_mov_atoms(data, child_start, cursor + size, atom_path)
        elif atom_type in {"ap4h", "ap4x", "apcn", "apch", "apcs", "apco"}:
            child_start = cursor + header + 78  # VisualSampleEntry fields after atom header
            yield from _walk_mov_atoms(data, child_start, cursor + size, atom_path)
        cursor += size
    if cursor != end and any(data[cursor:end]):
        raise ProResMasterError(f"MOV atom path {'/'.join(path) or '<root>'} has trailing bytes")


def _parse_mov_colr(media: Path) -> dict[str, Any]:
    data = media.read_bytes()
    atoms = list(_walk_mov_atoms(data, 0, len(data), ()))
    colr = [atom for atom in atoms if atom["type"] == "colr"]
    _require_equal(len(colr), 1, "MOV colr atom count")
    atom = colr[0]
    payload_start = atom["start"] + atom["header"]
    payload = data[payload_start:atom["start"] + atom["size"]]
    if len(payload) != 10:
        raise ProResMasterError(f"MOV colr payload has {len(payload)} bytes instead of 10")
    color_type = payload[:4].decode("ascii", errors="strict")
    primaries, transfer, matrix = struct.unpack(">HHH", payload[4:10])
    top = {atom["type"]: atom["start"] for atom in atoms if atom["path"] in {"moov", "mdat"}}
    return {
        "type": color_type, "path": atom["path"], "payload_bytes": len(payload),
        "primaries": primaries, "transfer": transfer, "matrix": matrix,
        "moov_before_mdat": "moov" in top and "mdat" in top and top["moov"] < top["mdat"],
    }


def _psnr(reference: np.ndarray, decoded: np.ndarray) -> float:
    error = reference.astype(np.float32) - decoded.astype(np.float32)
    mse = float(np.mean(error * error, dtype=np.float64))
    return 999.0 if mse == 0.0 else 10.0 * math.log10((255.0 * 255.0) / mse)


def _windowed_ssim(reference: np.ndarray, decoded: np.ndarray, window: int = 8) -> float:
    """Mean RGB SSIM over explicit non-overlapping windows.

    This is intentionally named and reported as an 8x8-window metric, rather than
    being presented as the Gaussian-window SSIM implementation from another library.
    """
    height = min(reference.shape[0], decoded.shape[0]) // window * window
    width = min(reference.shape[1], decoded.shape[1]) // window * window
    if height == 0 or width == 0:
        raise ProResMasterError("SSIM ROI is smaller than one complete window")
    x = reference[:height, :width].astype(np.float64)
    y = decoded[:height, :width].astype(np.float64)
    x = x.reshape(height // window, window, width // window, window, 3).transpose(0, 2, 1, 3, 4)
    y = y.reshape(height // window, window, width // window, window, 3).transpose(0, 2, 1, 3, 4)
    axes = (2, 3)
    ux, uy = x.mean(axis=axes), y.mean(axis=axes)
    vx, vy = x.var(axis=axes), y.var(axis=axes)
    covariance = ((x - ux[:, :, None, None, :]) * (y - uy[:, :, None, None, :])).mean(axis=axes)
    c1, c2 = (0.01 * 255.0) ** 2, (0.03 * 255.0) ** 2
    numerator = (2 * ux * uy + c1) * (2 * covariance + c2)
    denominator = (ux * ux + uy * uy + c1) * (vx + vy + c2)
    values = np.where(denominator == 0.0, 1.0, numerator / denominator)
    return float(values.mean())


def _sharpness(frame: np.ndarray) -> float:
    gray = frame.astype(np.float32).mean(axis=2)
    laplace = -4.0 * gray[1:-1, 1:-1]
    laplace += gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
    return float(laplace.var(dtype=np.float64))


def _clamped_roi(values: list[int] | tuple[int, ...], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = (int(value) for value in values)
    x1, x2 = max(0, min(width - 1, x1)), max(1, min(width, x2))
    y1, y2 = max(0, min(height - 1, y1)), max(1, min(height, y2))
    if x2 <= x1 or y2 <= y1:
        raise ProResMasterError(f"invalid decoded-audit ROI: {(x1, y1, x2, y2)}")
    return x1, y1, x2, y2


def _frame_rois(frame_number: int, manifest: dict[str, Any], contract: dict[str, Any]) -> dict[str, tuple[int, int, int, int]] | None:
    acceptance = contract["acceptance"]
    first, last = acceptance["roi_frame_span"]
    if frame_number < first or frame_number > last:
        return None
    entry = manifest["source_map"][frame_number - 1]
    face = entry.get("transformed_face_roi_xyxy", acceptance["base_face_roi_xyxy"])
    eye = entry.get("transformed_eye_roi_xyxy", acceptance["base_eye_roi_xyxy"])
    mouth = acceptance["base_mouth_roi_xyxy"]
    if "crop_xyxy" in entry:
        crop_x1, crop_y1, crop_x2, crop_y2 = (float(value) for value in entry["crop_xyxy"])
        sx = contract["clock"]["width"] / (crop_x2 - crop_x1)
        sy = contract["clock"]["height"] / (crop_y2 - crop_y1)
        mx1, my1, mx2, my2 = mouth
        mouth = [
            round((mx1 - crop_x1) * sx), round((my1 - crop_y1) * sy),
            round((mx2 - crop_x1) * sx), round((my2 - crop_y1) * sy),
        ]
    width, height = contract["clock"]["width"], contract["clock"]["height"]
    return {
        "face": _clamped_roi(face, width, height),
        "eye": _clamped_roi(eye, width, height),
        "mouth": _clamped_roi(mouth, width, height),
    }


def _decode_picture(
    media: Path, ffmpeg: Path, prepared: dict[str, Any], stage: Path, contract: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(media),
        "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]
    stderr_path = stage / "decode-picture-stderr-v1.txt"
    frame_bytes = contract["picture"]["archive_header"]["frame_bytes"]
    records: list[dict[str, Any]] = []
    minima = {
        "full_psnr_db": math.inf, "face_psnr_db": math.inf, "eye_psnr_db": math.inf,
        "mouth_psnr_db": math.inf, "face_8x8_window_ssim": math.inf, "sharpness_ratio": math.inf,
    }
    minimum_frames: dict[str, int] = {}
    minimum_images: dict[str, np.ndarray] = {}
    fixed_review_numbers = set(int(value) for value in contract["output"]["review_frame_numbers"])
    fixed_review_images: dict[int, np.ndarray] = {}
    maximum_pairwise = 0.0
    maximum_pairwise_frame = 0
    maximum_pairwise_image: np.ndarray | None = None
    prior_source: np.ndarray | None = None
    prior_decoded: np.ndarray | None = None
    process: subprocess.Popen[bytes] | None = None
    return_code: int | None = None
    with stderr_path.open("wb") as stderr:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr)
            if process.stdout is None:
                raise ProResMasterError("decoded-picture pipe was not created")
            for frame_number, source in enumerate(
                _iter_picture_frames(prepared["archive"], prepared["manifest"], contract), start=1,
            ):
                payload = _read_exact(process.stdout, frame_bytes)
                if len(payload) != frame_bytes:
                    raise ProResMasterError(f"decoded picture ended during frame {frame_number}")
                decoded = np.frombuffer(payload, dtype=np.uint8).reshape(source.shape).copy()
                if frame_number in fixed_review_numbers:
                    fixed_review_images[frame_number] = decoded.copy()
                record: dict[str, Any] = {
                    "frame": frame_number,
                    "decoded_rgb_sha256": hashlib.sha256(payload).hexdigest(),
                    "full_psnr_db": _psnr(source, decoded),
                }
                if record["full_psnr_db"] < minima["full_psnr_db"]:
                    minima["full_psnr_db"] = record["full_psnr_db"]
                    minimum_frames["full_psnr_db"] = frame_number
                    minimum_images["full_psnr_db"] = decoded.copy()
                rois = _frame_rois(frame_number, prepared["manifest"], contract)
                if rois is not None:
                    for name, roi in rois.items():
                        x1, y1, x2, y2 = roi
                        metric = f"{name}_psnr_db"
                        value = _psnr(source[y1:y2, x1:x2], decoded[y1:y2, x1:x2])
                        record[metric] = value
                        if value < minima[metric]:
                            minima[metric] = value
                            minimum_frames[metric] = frame_number
                            minimum_images[metric] = decoded.copy()
                    x1, y1, x2, y2 = rois["face"]
                    face_ssim = _windowed_ssim(source[y1:y2, x1:x2], decoded[y1:y2, x1:x2])
                    record["face_8x8_window_ssim"] = face_ssim
                    if face_ssim < minima["face_8x8_window_ssim"]:
                        minima["face_8x8_window_ssim"] = face_ssim
                        minimum_frames["face_8x8_window_ssim"] = frame_number
                        minimum_images["face_8x8_window_ssim"] = decoded.copy()
                source_sharpness = _sharpness(source)
                sharpness_ratio = _sharpness(decoded) / source_sharpness if source_sharpness > 0 else 1.0
                record["sharpness_ratio"] = sharpness_ratio
                if sharpness_ratio < minima["sharpness_ratio"]:
                    minima["sharpness_ratio"] = sharpness_ratio
                    minimum_frames["sharpness_ratio"] = frame_number
                    minimum_images["sharpness_ratio"] = decoded.copy()
                if prior_source is not None and prior_decoded is not None:
                    source_motion = source.astype(np.int16) - prior_source.astype(np.int16)
                    decoded_motion = decoded.astype(np.int16) - prior_decoded.astype(np.int16)
                    pairwise = float(np.mean(np.abs(source_motion - decoded_motion), dtype=np.float64))
                    record["pairwise_motion_delta"] = pairwise
                    if pairwise > maximum_pairwise:
                        maximum_pairwise = pairwise
                        maximum_pairwise_frame = frame_number
                        maximum_pairwise_image = decoded.copy()
                records.append(record)
                prior_source, prior_decoded = source.copy(), decoded
            if process.stdout.read(1):
                raise ProResMasterError("decoded picture has trailing frames or bytes")
            return_code = process.wait()
        finally:
            if process is not None:
                if process.stdout is not None and not process.stdout.closed:
                    process.stdout.close()
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
    _require_equal(return_code, 0, "decoded-picture process exit")
    _require_equal(set(fixed_review_images), fixed_review_numbers, "decoded fixed review-frame inventory")
    review_artifacts: list[dict[str, Any]] = []
    prefix = str(contract["output"]["review_frame_prefix"])
    for frame_number, frame in sorted(fixed_review_images.items()):
        path = stage / f"{prefix}-{frame_number:04d}.png"
        Image.fromarray(frame, mode="RGB").save(path, format="PNG", compress_level=6)
        review_artifacts.append({"purpose": "fixed_review_frame", "frame": frame_number, "file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    worst_images = dict(minimum_images)
    if maximum_pairwise_image is not None:
        worst_images["maximum_pairwise_motion_delta"] = maximum_pairwise_image
        minimum_frames["maximum_pairwise_motion_delta"] = maximum_pairwise_frame
    for metric, frame in sorted(worst_images.items()):
        frame_number = minimum_frames[metric]
        safe_metric = metric.replace("_", "-")
        path = stage / f"{prefix}-worst-{safe_metric}-{frame_number:04d}.png"
        Image.fromarray(frame, mode="RGB").save(path, format="PNG", compress_level=6)
        review_artifacts.append({"purpose": "worst_metric_frame", "metric": metric, "frame": frame_number, "file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    metrics = {
        "frame_count": len(records), "minimums": minima, "minimum_frames": minimum_frames,
        "maximum_pairwise_motion_delta": maximum_pairwise,
        "maximum_pairwise_motion_delta_frame": maximum_pairwise_frame,
        "review_artifacts": review_artifacts, "frames": records,
    }
    path = stage / str(contract["output"]["decode_metrics_filename"])
    path.write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return metrics, command


def _decode_audio(media: Path, ffmpeg: Path, stage: Path, contract: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(media),
        "-map", "0:a:0", "-f", "s24le", "-acodec", "pcm_s24le", "-ar", "48000", "-ac", "2", "pipe:1",
    ]
    result = subprocess.run(command, check=False, capture_output=True)
    stderr_path = stage / "decode-audio-stderr-v1.txt"
    stderr_path.write_bytes(result.stderr)
    _require_equal(result.returncode, 0, "decoded-audio process exit")
    decoded = result.stdout
    audit = {
        "sample_count": len(decoded) // 6,
        "data_bytes": len(decoded),
        "data_sha256": hashlib.sha256(decoded).hexdigest(),
        "exact_source_pcm": hashlib.sha256(decoded).hexdigest() == contract["audio"]["pcm_data_sha256"],
    }
    path = stage / str(contract["output"]["audio_audit_filename"])
    path.write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return audit, command


def _as_fraction(value: Any, label: str) -> Fraction:
    try:
        return Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise ProResMasterError(f"{label} is not a rational value: {value!r}") from exc


def _gate(name: str, actual: Any, expected: Any, mode: str = "equal") -> dict[str, Any]:
    if mode == "minimum":
        passed = actual >= expected
    elif mode == "maximum":
        passed = actual <= expected
    else:
        passed = actual == expected
    return {"name": name, "actual": actual, "expected": expected, "mode": mode, "passed": bool(passed)}


def _audit_gates(
    contract: dict[str, Any], streams_payload: dict[str, Any], frames_payload: dict[str, Any],
    colr: dict[str, Any], picture: dict[str, Any], audio: dict[str, Any],
) -> list[dict[str, Any]]:
    acceptance = contract["acceptance"]
    streams = streams_payload.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    other_streams = [stream for stream in streams if stream.get("codec_type") not in {"video", "audio"}]
    if len(video_streams) != 1 or len(audio_streams) != 1:
        raise ProResMasterError("stream probe does not contain exactly one video and one audio stream")
    video, audio_stream = video_streams[0], audio_streams[0]
    clock = contract["clock"]
    frame_rows = [row for row in frames_payload.get("frames", []) if row.get("media_type") == "video"]
    ticks_per_frame = clock["video_track_timescale"] // clock["fps"]
    timestamps = [int(row["best_effort_timestamp"]) for row in frame_rows]
    expected_timestamps = [index * ticks_per_frame for index in range(clock["frame_count"])]
    exact_timestamps = timestamps == expected_timestamps
    expected_frame_metadata = {
        "width": clock["width"], "height": clock["height"],
        "pix_fmt": acceptance["required_video_pixel_format"],
        "color_range": acceptance["required_color_range"],
        "color_space": acceptance["required_color_space"],
        "color_transfer": acceptance["required_color_transfer"],
        "color_primaries": acceptance["required_color_primaries"],
    }
    frame_metadata = [
        {
            "width": int(row.get("width", 0)), "height": int(row.get("height", 0)),
            "pix_fmt": row.get("pix_fmt"), "color_range": row.get("color_range"),
            "color_space": row.get("color_space"), "color_transfer": row.get("color_transfer"),
            "color_primaries": row.get("color_primaries"),
        }
        for row in frame_rows
    ]
    duration = Fraction(clock["frame_count"], clock["fps"])
    gates = [
        _gate("stream_count", len(streams), acceptance["required_stream_count"]),
        _gate("video_stream_count", len(video_streams), acceptance["required_video_streams"]),
        _gate("audio_stream_count", len(audio_streams), acceptance["required_audio_streams"]),
        _gate("other_stream_count", len(other_streams), acceptance["required_other_streams"]),
        _gate("video_codec_name", video.get("codec_name"), acceptance["required_video_codec_name"]),
        _gate("video_profile", video.get("profile"), acceptance["required_video_profile"]),
        _gate("video_codec_tag", video.get("codec_tag_string"), acceptance["required_video_codec_tag_string"]),
        _gate("video_vendor_id", video.get("tags", {}).get("vendor_id"), acceptance["required_video_vendor_id"]),
        _gate("video_pixel_format", video.get("pix_fmt"), acceptance["required_video_pixel_format"]),
        _gate("video_bits_per_raw_sample", int(video.get("bits_per_raw_sample", 0)), acceptance["required_video_bits_per_raw_sample"]),
        _gate("video_width", int(video.get("width", 0)), clock["width"]),
        _gate("video_height", int(video.get("height", 0)), clock["height"]),
        _gate("video_frame_rate", _as_fraction(video.get("avg_frame_rate", "0/1"), "video frame rate") == Fraction(30, 1), True),
        _gate("video_frame_count", int(video.get("nb_frames", 0)), clock["frame_count"]),
        _gate("video_time_base", video.get("time_base"), f"1/{clock['video_track_timescale']}"),
        _gate("video_duration_ticks", int(video.get("duration_ts", -1)), clock["frame_count"] * ticks_per_frame),
        _gate("video_start_time", _as_fraction(video.get("start_time", "-1"), "video start time") == 0, True),
        _gate("video_duration", _as_fraction(video.get("duration", "-1"), "video duration") == duration, True),
        _gate("sample_aspect_ratio", video.get("sample_aspect_ratio"), clock["sample_aspect_ratio"]),
        _gate("color_range", video.get("color_range"), acceptance["required_color_range"]),
        _gate("color_space", video.get("color_space"), acceptance["required_color_space"]),
        _gate("color_transfer", video.get("color_transfer"), acceptance["required_color_transfer"]),
        _gate("color_primaries", video.get("color_primaries"), acceptance["required_color_primaries"]),
        _gate("audio_codec_name", audio_stream.get("codec_name"), acceptance["required_audio_codec_name"]),
        _gate("audio_sample_format", audio_stream.get("sample_fmt"), acceptance["required_audio_sample_format"]),
        _gate("audio_sample_rate", int(audio_stream.get("sample_rate", 0)), contract["audio"]["sample_rate"]),
        _gate("audio_channels", int(audio_stream.get("channels", 0)), contract["audio"]["channels"]),
        _gate("audio_start_time", _as_fraction(audio_stream.get("start_time", "-1"), "audio start time") == 0, True),
        _gate("audio_duration", _as_fraction(audio_stream.get("duration", "-1"), "audio duration") == duration, True),
        _gate("video_frame_integer_timestamps", exact_timestamps, True),
        _gate("video_frame_metadata_count", len(frame_metadata), clock["frame_count"]),
        _gate("video_frame_metadata_all_frames", all(row == expected_frame_metadata for row in frame_metadata), True),
        _gate("mov_colr_type", colr["type"], acceptance["required_mov_colr_type"]),
        _gate("mov_colr_path", colr["path"], acceptance["required_mov_colr_path"]),
        _gate("mov_colr_payload_bytes", colr["payload_bytes"], acceptance["required_mov_colr_payload_bytes"]),
        _gate("mov_colr_primaries", colr["primaries"], acceptance["required_mov_colr_primaries"]),
        _gate("mov_colr_transfer", colr["transfer"], acceptance["required_mov_colr_transfer"]),
        _gate("mov_colr_matrix", colr["matrix"], acceptance["required_mov_colr_matrix"]),
        _gate("mov_faststart", colr["moov_before_mdat"], True),
        _gate("decoded_picture_frame_count", picture["frame_count"], clock["frame_count"]),
        _gate("minimum_full_frame_psnr_db", picture["minimums"]["full_psnr_db"], acceptance["minimum_full_frame_psnr_db"], "minimum"),
        _gate("minimum_face_roi_psnr_db", picture["minimums"]["face_psnr_db"], acceptance["minimum_face_roi_psnr_db"], "minimum"),
        _gate("minimum_eye_roi_psnr_db", picture["minimums"]["eye_psnr_db"], acceptance["minimum_eye_roi_psnr_db"], "minimum"),
        _gate("minimum_mouth_roi_psnr_db", picture["minimums"]["mouth_psnr_db"], acceptance["minimum_mouth_roi_psnr_db"], "minimum"),
        _gate(
            "minimum_face_roi_8x8_window_ssim",
            picture["minimums"]["face_8x8_window_ssim"],
            acceptance["minimum_face_roi_8x8_window_ssim"], "minimum",
        ),
        _gate("minimum_sharpness_ratio", picture["minimums"]["sharpness_ratio"], acceptance["minimum_sharpness_ratio"], "minimum"),
        _gate("maximum_pairwise_motion_delta", picture["maximum_pairwise_motion_delta"], acceptance["maximum_pairwise_motion_delta"], "maximum"),
        _gate("decoded_audio_sample_count", audio["sample_count"], contract["audio"]["sample_count"]),
        _gate("decoded_audio_data_sha256", audio["data_sha256"], acceptance["required_decoded_pcm_data_sha256"]),
    ]
    return gates


def _attempt_gates(attempt: dict[str, Any], contract: dict[str, Any]) -> list[dict[str, Any]]:
    clock = contract["clock"]
    expected_bytes = clock["frame_count"] * clock["width"] * clock["height"] * 3
    return [
        _gate("encoder_process_count", attempt["encoding_process_count"], 1),
        _gate("encoder_return_code", attempt["encoder_return_code"], 0),
        _gate("encoder_source_frames", attempt["source_frames_written"], clock["frame_count"]),
        _gate("encoder_source_bytes", attempt["source_bytes_written"], expected_bytes),
    ]


def _write_human_review_instructions(
    stage: Path, media: Path, report: Path, picture: dict[str, Any], contract: dict[str, Any],
) -> Path:
    receipt = contract["human_review_receipt"]
    lines = [
        "# Phase36 ProRes 4444 review-master human gate",
        "",
        "Machine PASS is not promotion. Review the exact files and publish a separate signed PASS or REJECT receipt.",
        "",
        f"- MOV SHA-256: `{_sha256(media)}`",
        f"- machine report SHA-256: `{_sha256(report)}`",
        f"- required PASS verdict: `{receipt['required_pass_verdict']}`",
        "- the receipt must also bind the final attempt-package SHA-256",
        "",
        "## Required review",
        "",
    ]
    lines.extend(f"- {item}" for item in receipt["required_review_scope"])
    lines.extend(["", "## Extracted evidence", ""])
    for item in picture["review_artifacts"]:
        label = item["purpose"].replace("_", " ")
        metric = f" ({item['metric']})" if "metric" in item else ""
        lines.append(f"- {label}{metric}, F{item['frame']:03d}: `{item['file']}` SHA-256 `{item['sha256']}`")
    lines.extend([
        "", "A PASS receipt must explicitly address every required-review bullet. Any omission is non-promotion.", "",
    ])
    path = stage / str(contract["output"]["human_review_instructions_filename"])
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return path


def _expected_success_artifacts(
    contract: dict[str, Any], claim_name: str, picture: dict[str, Any], *, include_package: bool,
) -> set[str]:
    output = contract["output"]
    names = {
        claim_name, str(output["video_filename"]), str(output["stderr_filename"]),
        str(output["stream_probe_filename"]), "ffprobe-stream-stderr-v1.txt",
        str(output["frame_probe_filename"]), "ffprobe-frames-stderr-v1.txt",
        "decode-picture-stderr-v1.txt", "decode-audio-stderr-v1.txt",
        str(output["decode_metrics_filename"]), str(output["audio_audit_filename"]),
        str(output["report_filename"]), str(output["human_review_instructions_filename"]),
    }
    names.update(str(item["file"]) for item in picture["review_artifacts"])
    if include_package:
        names.add(str(output["package_filename"]))
    return names


def _artifact_inventory(directory: Path, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude or set()
    artifacts: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name in excluded:
            continue
        if not path.is_file():
            raise ProResMasterError(f"attempt package contains a non-file entry: {path.name}")
        artifacts.append({"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return artifacts


def _write_failure(
    stage: Path, rejected: Path, claim: Path, error: BaseException,
    attempt: dict[str, Any], contract: dict[str, Any],
) -> None:
    if rejected.exists():
        raise ProResMasterError(f"immutable rejected attempt already exists: {rejected}") from error
    if claim.is_file() and not (stage / claim.name).exists():
        shutil.copy2(claim, stage / claim.name)
    receipt = {
        "receipt_version": 1,
        "attempt_id": "phase36_prores4444_review_master_v1_attempt01",
        "status": "REJECTED_NO_RETRY",
        "error_type": type(error).__name__,
        "error": str(error),
        "attempt": attempt,
        "disposition": {
            "authorization_consumed": True,
            "retry_allowed": False,
            "promotion_allowed": False,
            "distribution_encode_allowed": False,
            "source_picture_immutable": True,
            "source_audio_immutable": True,
        },
    }
    path = stage / "failure-v1.json"
    path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    package_path = stage / str(contract["output"]["package_filename"])
    package = {
        "package_version": 1, "attempt_id": receipt["attempt_id"], "machine_passed": False,
        "artifacts": _artifact_inventory(stage, {package_path.name}), "disposition": receipt["disposition"],
    }
    package_path.write_text(json.dumps(package, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    stage.rename(rejected)


def run_authorized_master(*, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    # These two gates intentionally precede tool discovery, output resolution, directory
    # creation, archive loading, and every subprocess. An unbound scaffold is inert.
    contract = load_contract()
    vui = _vui_result(contract)
    if vui is None:
        raise ProResMasterError("passing VUI probe result is not bound; no tool or output was resolved")
    authorization = _authorization(contract, vui)
    if authorization is None:
        raise ProResMasterError("master authorization receipt is not bound; no tool or output was resolved")

    ffmpeg_path = _resolved_tool(ffmpeg)
    ffprobe_path = _resolved_tool(ffprobe)
    output = _outputs_path(str(contract["output"]["directory"]))
    rejected = output.with_name(output.name + "-rejected")
    claim_path = output.parent / f".{output.name}.attempt01-claim.json"
    if output.exists() or rejected.exists() or claim_path.exists():
        raise ProResMasterError(f"immutable master attempt state already exists: {output}, {rejected}, or {claim_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if next(output.parent.glob(f".{output.name}.partial-*"), None) is not None:
        raise ProResMasterError("an earlier partial master attempt exists")
    prepared = _prepare(contract, ffmpeg_path, ffprobe_path)
    free_bytes = shutil.disk_usage(output.parent).free
    if free_bytes < contract["toolchain"]["minimum_free_output_bytes"]:
        raise ProResMasterError("insufficient free space for the single ProRes master attempt")
    state = _capture_state(contract, ffmpeg_path, ffprobe_path, vui, authorization)
    _assert_state(state, contract)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    media_partial = stage / (Path(str(contract["output"]["video_filename"])).stem + ".partial.mov")
    command = _encoder_command(contract, ffmpeg_path, prepared["audio_path"], media_partial)
    claim: Path | None = None
    claim_created = False
    process: subprocess.Popen[bytes] | None = None
    attempt = {
        "captured_state": state, "encoder_command": command, "encoding_process_count": 0,
        "encoder_return_code": None, "source_frames_written": 0, "source_bytes_written": 0,
    }
    try:
        try:
            claim = _claim_attempt(output, state, command)
            claim_created = True
        except ClaimWriteError as exc:
            claim = exc.claim
            claim_created = True
            raise
        shutil.copy2(claim, stage / claim.name)
        current = _capture_state(contract, ffmpeg_path, ffprobe_path, _vui_result(contract), _authorization(contract, _vui_result(contract)))
        _require_equal(current, state, "postclaim fixed state")
        stderr_path = stage / str(contract["output"]["stderr_filename"])
        with stderr_path.open("wb") as stderr:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr)
            attempt["encoding_process_count"] = 1
            if process.stdin is None:
                raise ProResMasterError("FFmpeg raw-video pipe was not created")
            for frame in _iter_picture_frames(prepared["archive"], prepared["manifest"], contract):
                payload = np.ascontiguousarray(frame).tobytes()
                written = process.stdin.write(payload)
                _require_equal(written, len(payload), f"source frame {attempt['source_frames_written'] + 1} pipe write")
                attempt["source_frames_written"] += 1
                attempt["source_bytes_written"] += len(payload)
            process.stdin.close()
            attempt["encoder_return_code"] = process.wait()
        _require_equal(attempt["source_frames_written"], 303, "encoded source frame count")
        _require_equal(attempt["source_bytes_written"], 303 * 6220800, "encoded source byte count")
        _require_equal(attempt["encoder_return_code"], 0, "encoder return code")
        if not media_partial.is_file() or media_partial.stat().st_size == 0:
            raise ProResMasterError("single encoder process produced no media")
        media = stage / str(contract["output"]["video_filename"])
        os.replace(media_partial, media)
        current = _capture_state(contract, ffmpeg_path, ffprobe_path, _vui_result(contract), _authorization(contract, _vui_result(contract)))
        _require_equal(current, state, "postencode fixed state")

        streams, frames, probe_commands = _probe_media(media, ffprobe_path, stage, contract)
        colr = _parse_mov_colr(media)
        picture_metrics, picture_command = _decode_picture(media, ffmpeg_path, prepared, stage, contract)
        audio_audit, audio_command = _decode_audio(media, ffmpeg_path, stage, contract)
        gates = _attempt_gates(attempt, contract) + _audit_gates(
            contract, streams, frames, colr, picture_metrics, audio_audit,
        )
        passed = all(gate["passed"] for gate in gates)
        report = {
            "report_version": 1,
            "attempt_id": "phase36_prores4444_review_master_v1_attempt01",
            "status": "MACHINE_PASSED_HUMAN_REVIEW_REQUIRED" if passed else "REJECTED_NO_RETRY",
            "machine_passed": passed,
            "authorization_consumed": True,
            "scope": "one ProRes 4444 plus exact PCM24 professional review master; no render or distribution derivative",
            "captured_state": state,
            "sources": {"picture": prepared["picture_audit"], "audio": prepared["audio_audit"]},
            "toolchain": prepared["toolchain"],
            "encoder": {
                "command": command, "command_template": _command_template(contract),
                "command_template_sha256": _command_template_hash(contract),
                "process_count": attempt["encoding_process_count"], "return_code": attempt["encoder_return_code"],
                "source_frames_written": attempt["source_frames_written"], "source_bytes_written": attempt["source_bytes_written"],
            },
            "media": {"file": media.name, "bytes": media.stat().st_size, "sha256": _sha256(media)},
            "diagnostic_commands": {**probe_commands, "decode_picture": picture_command, "decode_audio": audio_command},
            "stream_probe": streams, "frame_probe": frames, "mov_colr": colr,
            "picture_metrics": picture_metrics, "audio_audit": audio_audit,
            "gates": gates, "gate_count": len(gates),
            "gates_passed": sum(1 for gate in gates if gate["passed"]),
            "gates_failed": sum(1 for gate in gates if not gate["passed"]),
            "failed_gates": [gate["name"] for gate in gates if not gate["passed"]],
            "disposition": {
                "human_native_size_review_required": passed,
                "promotion_allowed": False,
                "distribution_encode_allowed": False,
                "retry_allowed": False,
                "source_picture_immutable": True,
                "source_audio_immutable": True,
            },
        }
        report_path = stage / str(contract["output"]["report_filename"])
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if not passed:
            raise ProResMasterError(f"ProRes review-master gates failed: {report['failed_gates']}")
        instructions = _write_human_review_instructions(stage, media, report_path, picture_metrics, contract)
        expected_without_package = _expected_success_artifacts(
            contract, claim.name, picture_metrics, include_package=False,
        )
        _require_equal({path.name for path in stage.iterdir()}, expected_without_package, "prepackage success artifact allowlist")
        package_path = stage / str(contract["output"]["package_filename"])
        package = {
            "package_version": 1, "attempt_id": report["attempt_id"], "machine_passed": True,
            "artifacts": _artifact_inventory(stage, {package_path.name}), "disposition": report["disposition"],
        }
        package_path.write_text(json.dumps(package, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        _require_equal(
            {path.name for path in stage.iterdir()},
            _expected_success_artifacts(contract, claim.name, picture_metrics, include_package=True),
            "published success artifact allowlist",
        )
        current = _capture_state(contract, ffmpeg_path, ffprobe_path, _vui_result(contract), _authorization(contract, _vui_result(contract)))
        _require_equal(current, state, "prepublication fixed state")
        if output.exists():
            raise ProResMasterError(f"immutable output appeared before publication: {output}")
        stage.rename(output)
        return {
            "output_directory": str(output), "media": str(output / media.name),
            "media_sha256": report["media"]["sha256"], "report": str(output / report_path.name),
            "package": str(output / package_path.name), "machine_passed": True,
            "human_review_instructions": str(output / instructions.name),
            "human_review_required": True, "distribution_encode_authorized": False, "retry_allowed": False,
        }
    except BaseException as exc:
        if process is not None and process.poll() is None:
            try:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
            except BaseException:
                pass
            try:
                process.kill()
                process.wait(timeout=10)
            except BaseException:
                pass
        attempt["encoder_return_code"] = process.poll() if process is not None else None
        if claim_created and claim is not None and stage.exists():
            _write_failure(stage, rejected, claim, exc, attempt, contract)
        elif stage.exists():
            shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run-authorized-master"):
        command = subparsers.add_parser(name)
        command.add_argument("--ffmpeg", default="ffmpeg")
        command.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "preflight":
        result = preflight(ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    else:
        result = run_authorized_master(ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
