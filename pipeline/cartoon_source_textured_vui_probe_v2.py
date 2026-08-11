"""Fail-closed Phase35 Candidate03 nine-frame H.264/MP4 VUI successor probe."""
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
import re
import shutil
import struct
import subprocess
import tempfile
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase35_candidate03_blink_vui_probe_v2.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_source_textured_vui_probe_v2.py"
# This hash deliberately excludes authorization.receipt. Binding a receipt later therefore
# cannot change the reviewed subject or require a post-authorization implementation edit.
EXPECTED_AUTHORIZATION_SUBJECT_SHA256 = "5fb952bf048b200b20e85c3287e8f600c2b6b4088b7a9f9e965974afdb9b93c3"


class VuiProbeError(RuntimeError):
    pass


class ClaimWriteError(VuiProbeError):
    """The process owns the exclusive claim, but its durable write failed."""

    def __init__(self, claim: Path, cause: BaseException) -> None:
        super().__init__(f"attempt claim was created but could not be durably written: {cause}")
        self.claim = claim


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
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise VuiProbeError(f"{label} contains duplicate key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise VuiProbeError(f"{label} contains non-finite JSON value: {value}")

    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicate,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VuiProbeError(f"{label} is not strict UTF-8 JSON") from exc


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise VuiProbeError(f"Phase35 blink VUI probe mismatch for {label}: {actual!r} != {expected!r}")


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise VuiProbeError(f"locked repository path escapes the repository: {relative}") from exc
    if not path.is_file():
        raise VuiProbeError(f"locked repository file is missing: {relative}")
    return path


def _outputs_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    outputs_root = (REPO_ROOT / "../../outputs").resolve()
    try:
        path.relative_to(outputs_root)
    except ValueError as exc:
        raise VuiProbeError(f"probe path escapes the pinned outputs tree: {relative}") from exc
    return path


def _resolved_tool(executable: str) -> Path:
    located = shutil.which(executable)
    if located is None:
        candidate = Path(executable).resolve()
        if not candidate.is_file():
            raise VuiProbeError(f"required executable was not found: {executable}")
        located = str(candidate)
    return Path(located).resolve()


def _authorization_subject(contract: dict[str, Any]) -> dict[str, Any]:
    subject = copy.deepcopy(contract)
    subject["authorization"]["receipt"] = None
    return subject


def _lock_hash(reference: dict[str, Any]) -> str:
    path = _repo_path(str(reference["path"]))
    return _lf_hash(path) if reference.get("hash_domain") == "lf_normalized_text" else _sha256(path)


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned contract path")
    contract = _strict_json_loads(resolved.read_bytes(), "VUI probe contract")
    _require_equal(
        _canonical_hash(_authorization_subject(contract)),
        EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
        "authorization-subject canonical SHA-256",
    )
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(
        contract["contract_id"],
        "june_oxley_phase35_candidate03_blink_vui_probe_v2",
        "contract id",
    )
    _require_equal(contract["cash_cost"], 0, "cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "paid dependency policy")
    _require_equal(contract["network_runtime_required"], False, "network policy")
    _require_equal(
        contract["predecessor_branch_commit"],
        "7387c35c3275aa36d02b2587887f2ec25a29d88f",
        "predecessor branch commit",
    )
    _require_equal(contract["clock"], {
        "width": 1920,
        "height": 1080,
        "pixel_format": "rgb24",
        "fps": 30,
        "frame_count": 9,
        "duration_seconds": 0.3,
        "audio_streams": 0,
    }, "probe clock")
    selection = contract["selection"]
    _require_equal(selection["source_frame_numbers"], list(range(77, 86)), "selected frames")
    _require_equal(selection["contains_attempt01_worst_codec_delta_pair"], [80, 81], "worst pair")
    _require_equal(len(selection["frame_hashes"]), 9, "selected frame hash count")
    _require_equal(
        _canonical_hash(selection["frame_hashes"]),
        selection["frame_inventory_canonical_sha256"],
        "selected frame inventory hash",
    )
    encoding = contract["encoding"]
    _require_equal(encoding["video_codec"], "libx264", "video codec")
    _require_equal(encoding["pixel_format"], "yuv420p", "encoded pixel format")
    _require_equal(encoding["crf"], 0, "CRF")
    _require_equal(encoding["audio_allowed"], False, "audio policy")
    _require_equal(encoding["h264_metadata_patch_allowed"], False, "bitstream patch policy")
    _require_equal(encoding["setparams_filter_allowed"], True, "frame filter policy")
    _require_equal(
        encoding["filter_chain"],
        "setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709",
        "frame metadata filter",
    )
    _require_equal(encoding["setparams_is_only_v1_command_delta"], True, "V1 command-delta policy")
    authorization = contract["authorization"]
    _require_equal(
        authorization["required_verdict"],
        "PHASE35_C03_BLINK_VUI_PROBE_V2_ATTEMPT02_ALLOWED",
        "authorization verdict",
    )
    _require_equal(authorization["maximum_video_encoder_processes"], 1, "encoder allowance")
    _require_equal(authorization["automatic_retry_allowed"], False, "retry policy")
    failure = contract["failure_policy"]
    for field in (
        "fallback_allowed", "automatic_reencode_allowed", "renderer_invocation_allowed",
        "network_allowed", "full_phase35_encode_allowed", "phase36_encode_allowed",
        "candidate02_audio_mux_allowed", "promotion_allowed",
    ):
        _require_equal(failure[field], False, f"failure policy {field}")
    for name, reference in contract["locks"].items():
        _require_equal(_lock_hash(reference), reference["sha256"], f"locked {name} SHA-256")
    return contract


def _command_template(contract: dict[str, Any]) -> list[str]:
    encoding = contract["encoding"]
    return [
        "$FFMPEG", "-hide_banner", "-loglevel", "error", "-xerror",
        "-abort_on", "empty_output+empty_output_stream",
        "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "1920x1080",
        "-framerate", "30", "-i", "pipe:0",
        "-map", "0:v:0", "-map_metadata", "-1", "-map_chapters", "-1",
        "-sn", "-dn", "-an", "-frames:v", "9", "-vf", str(encoding["filter_chain"]),
        "-c:v", str(encoding["video_codec"]), "-preset", str(encoding["preset"]),
        "-tune", str(encoding["tune"]), "-crf", str(encoding["crf"]),
        "-pix_fmt", str(encoding["pixel_format"]), "-fps_mode", "cfr",
        "-color_range", str(encoding["color_range"]),
        "-colorspace", str(encoding["color_space"]),
        "-color_primaries", str(encoding["color_primaries"]),
        "-color_trc", str(encoding["color_transfer"]),
        "-x264-params", str(encoding["x264_params"]),
        "-tag:v", str(encoding["codec_tag"]),
        "-movflags", str(encoding["movflags"]),
        "-n", "$OUTPUT",
    ]


def _command_template_hash(contract: dict[str, Any]) -> str:
    return _canonical_hash(_command_template(contract))


def _authorization(contract: dict[str, Any]) -> dict[str, str] | None:
    gate = contract["authorization"]
    reference = gate.get("receipt")
    if reference is None:
        return None
    if not isinstance(reference, dict):
        raise VuiProbeError("authorization receipt must be null or a locked reference")
    path = _repo_path(str(reference["path"]))
    digest = _lf_hash(path) if reference.get("hash_domain") == "lf_normalized_text" else _sha256(path)
    _require_equal(digest, reference["sha256"], "authorization receipt SHA-256")
    text = path.read_text(encoding="utf-8")
    verdict = f'{gate["required_verdict_field"]} {gate["required_verdict"]}'
    verdict_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("## Verdict:")]
    _require_equal(verdict_lines, [verdict], "authorization verdict lines")
    required_tokens = [
        EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
        _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
        _command_template_hash(contract),
        contract["predecessor_branch_commit"],
        contract["source_evidence"]["archive_sha256"],
        contract["selection"]["frame_inventory_canonical_sha256"],
        contract["selection"]["combined_rgb24_payload_sha256"],
        contract["toolchain"]["ffmpeg_sha256"],
        contract["toolchain"]["ffprobe_sha256"],
    ]
    required_tokens.extend(
        reference["sha256"] for _, reference in sorted(contract["locks"].items())
    )
    for token in required_tokens:
        if token not in text:
            raise VuiProbeError(f"authorization receipt omits binding token: {token}")
    return {
        "path": str(reference["path"]),
        "hash_domain": str(reference.get("hash_domain", "raw_bytes")),
        "sha256": digest,
        "verdict": str(gate["required_verdict"]),
    }


def _source_paths(contract: dict[str, Any]) -> tuple[Path, Path]:
    source = contract["source_evidence"]
    directory = _outputs_path(str(source["external_directory"]))
    expected = (REPO_ROOT / "../../outputs/edit/phase35-source-textured-direct-address-preview-v2-candidate-03").resolve()
    _require_equal(directory, expected, "Candidate03 external evidence directory")
    manifest = directory / str(source["manifest_filename"])
    archive = directory / str(source["archive_filename"])
    if not manifest.is_file() or not archive.is_file():
        raise VuiProbeError("the exact local Candidate03 manifest/archive pair is missing")
    return manifest, archive


def _read_exact(handle: gzip.GzipFile, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = handle.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _reconstruct_selected_frames(
    archive_path: Path,
    contract: dict[str, Any],
    frame_hashes: list[dict[str, Any]],
) -> tuple[list[np.ndarray], dict[str, Any]]:
    expected_header = contract["source_evidence"]["archive_header"]
    selected_numbers = set(contract["selection"]["source_frame_numbers"])
    selected: list[np.ndarray] = []
    combined = hashlib.sha256()
    with gzip.open(archive_path, "rb") as archive:
        try:
            header = _strict_json_loads(archive.readline(), "Candidate03 archive header")
        except OSError as exc:
            raise VuiProbeError("Candidate03 archive header is unreadable") from exc
        _require_equal(header, expected_header, "Candidate03 archive header")
        shape = (int(header["height"]), int(header["width"]), int(header["channels"]))
        frame_bytes = int(header["frame_bytes"])
        _require_equal(frame_bytes, int(np.prod(shape)), "archive frame byte geometry")
        _require_equal(len(frame_hashes), int(header["frame_count"]), "archive inventory length")
        previous = np.zeros(shape, dtype=np.uint8)
        for frame_number, expected in enumerate(frame_hashes, start=1):
            payload = _read_exact(archive, frame_bytes)
            if len(payload) != frame_bytes:
                raise VuiProbeError(f"Candidate03 archive frame {frame_number} is truncated")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous)
            digest = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
            _require_equal(expected, {"frame": frame_number, "rgb_sha256": digest}, f"source frame {frame_number}")
            if frame_number in selected_numbers:
                frozen = np.ascontiguousarray(frame).copy()
                selected.append(frozen)
                combined.update(frozen.tobytes())
            previous = frame
        if archive.read(1):
            raise VuiProbeError("Candidate03 archive has trailing decompressed payload")
    selection = contract["selection"]
    _require_equal(len(selected), 9, "selected source frame count")
    _require_equal(sum(frame.nbytes for frame in selected), selection["combined_rgb24_payload_bytes"], "selected payload bytes")
    _require_equal(combined.hexdigest(), selection["combined_rgb24_payload_sha256"], "selected payload SHA-256")
    return selected, {
        "verified_archive_frames": len(frame_hashes),
        "selected_frames": selection["source_frame_numbers"],
        "selected_payload_bytes": sum(frame.nbytes for frame in selected),
        "selected_payload_sha256": combined.hexdigest(),
    }


def _validate_toolchain(ffmpeg: Path, ffprobe: Path, contract: dict[str, Any]) -> dict[str, Any]:
    tools = contract["toolchain"]
    _require_equal(_sha256(ffmpeg), tools["ffmpeg_sha256"], "FFmpeg executable SHA-256")
    _require_equal(_sha256(ffprobe), tools["ffprobe_sha256"], "FFprobe executable SHA-256")
    ffmpeg_version_command = [str(ffmpeg), "-version"]
    ffprobe_version_command = [str(ffprobe), "-version"]
    ffmpeg_version = subprocess.run(ffmpeg_version_command, check=True, capture_output=True, text=True).stdout.splitlines()[0]
    ffprobe_version = subprocess.run(ffprobe_version_command, check=True, capture_output=True, text=True).stdout.splitlines()[0]
    expected = str(tools["version"])
    if not ffmpeg_version.startswith(f"ffmpeg version {expected} "):
        raise VuiProbeError(f"unexpected FFmpeg version: {ffmpeg_version}")
    if not ffprobe_version.startswith(f"ffprobe version {expected} "):
        raise VuiProbeError(f"unexpected FFprobe version: {ffprobe_version}")
    help_specs = [
        ("encoder", str(tools["required_video_encoder"]), "Encoder libx264"),
        ("decoder", str(tools["required_video_decoder"]), "Decoder h264"),
        ("demuxer", str(tools["required_input_demuxer"]), "Demuxer rawvideo"),
        ("muxer", str(tools["required_output_muxer"]), "Muxer mp4"),
        ("bsf", str(tools["required_bitstream_filter"]), "trace_headers"),
        ("filter", str(tools["required_frame_filter"]), "setparams AVOptions"),
    ]
    help_commands: list[list[str]] = []
    help_text: dict[str, str] = {}
    for kind, name, marker in help_specs:
        command = [str(ffmpeg), "-hide_banner", "-h", f"{kind}={name}"]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        text = result.stdout + result.stderr
        if marker not in text or "Unknown" in text:
            raise VuiProbeError(f"required FFmpeg {kind} is unavailable: {name}")
        help_commands.append(command)
        help_text[f"{kind}:{name}"] = text
    if str(tools["required_muxer_flag"]) not in help_text["muxer:mp4"]:
        raise VuiProbeError("required MP4 write_colr muxer flag is unavailable")
    if "x264-params" not in help_text["encoder:libx264"]:
        raise VuiProbeError("required libx264 x264-params passthrough is unavailable")
    return {
        "ffmpeg": {"path": str(ffmpeg), "sha256": _sha256(ffmpeg), "version": ffmpeg_version},
        "ffprobe": {"path": str(ffprobe), "sha256": _sha256(ffprobe), "version": ffprobe_version},
        "ffmpeg_version_command": ffmpeg_version_command,
        "ffprobe_version_command": ffprobe_version_command,
        "help_commands": help_commands,
    }


def _validate_attempt01_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    report_path = _repo_path(str(contract["locks"]["attempt01_report"]["path"]))
    failure_path = _repo_path(str(contract["locks"]["attempt01_failure"]["path"]))
    report = _strict_json_loads(report_path.read_bytes(), "Attempt01 report")
    failure = _strict_json_loads(failure_path.read_bytes(), "Attempt01 failure receipt")
    _require_equal(failure.get("encoder_process_started"), True, "Attempt01 encoder started")
    _require_equal(failure.get("attempt", {}).get("encoding_process_count"), 1, "Attempt01 encoder count")
    _require_equal(failure.get("attempt", {}).get("encoder_return_code"), 0, "Attempt01 encoder return code")
    error = str(failure.get("error", ""))
    for gate_name in ("video_color_transfer", "video_color_primaries"):
        if gate_name not in error:
            raise VuiProbeError(f"Attempt01 failure does not bind expected metadata defect: {gate_name}")
    _require_equal(report.get("machine_passed"), False, "Attempt01 machine result")
    return {
        "report_sha256": _sha256(report_path),
        "failure_sha256": _sha256(failure_path),
        "failed_metadata_gates": ["video_color_transfer", "video_color_primaries"],
    }


def _validate_raw_rgb_calibration(
    contract: dict[str, Any], ffmpeg: Path | None = None,
) -> dict[str, Any]:
    locks = contract["locks"]
    report_path = _repo_path(str(locks["raw_rgb_metadata_calibration_report"]["path"]))
    package_path = _repo_path(str(locks["raw_rgb_metadata_calibration_package"]["path"]))
    _require_equal(report_path.parent, package_path.parent, "raw-RGB calibration evidence directory")
    root = report_path.parent
    report = _strict_json_loads(report_path.read_bytes(), "raw-RGB metadata calibration report")
    package = _strict_json_loads(package_path.read_bytes(), "raw-RGB metadata calibration package")

    _require_equal(report["report_version"], 1, "raw-RGB calibration report version")
    _require_equal(report["report_id"], "phase35_vui_metadata_rgb_calibration_v2", "raw-RGB calibration id")
    _require_equal(report["candidate_media_used"], False, "raw-RGB calibration candidate policy")
    _require_equal(report["candidate_authorization_consumed"], False, "raw-RGB calibration authorization policy")
    _require_equal(report["cash_cost"], 0, "raw-RGB calibration cash cost")
    _require_equal(report["machine_passed"], True, "raw-RGB calibration machine result")
    _require_equal(report["toolchain"], {
        "ffmpeg_sha256": contract["toolchain"]["ffmpeg_sha256"],
        "ffprobe_sha256": contract["toolchain"]["ffprobe_sha256"],
        "version": contract["toolchain"]["version"],
    }, "raw-RGB calibration toolchain")

    source_payload = bytearray()
    for y in range(64):
        for x in range(64):
            source_payload.extend(((4 * x + 2 * y) % 256, (4 * y + x) % 256, 4 * (x ^ y) % 256))
    source = report["source"]
    _require_equal(source["pixel_format"], "rgb24", "raw-RGB calibration pixel format")
    _require_equal((source["width"], source["height"], source["frame_count"]), (64, 64, 1), "raw-RGB calibration geometry")
    _require_equal(source["payload_bytes"], len(source_payload), "raw-RGB calibration source bytes")
    _require_equal(source["payload_sha256"], hashlib.sha256(source_payload).hexdigest(), "raw-RGB calibration source hash")
    expected_input = [
        "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "64x64",
        "-framerate", "30", "-i", "pipe:0",
    ]
    _require_equal(source["input_boundary"], expected_input, "raw-RGB calibration input boundary")
    filter_argv = ["-vf", contract["encoding"]["filter_chain"]]
    _require_equal(report["controlled_variable"], {
        "control_filter_argv": [],
        "treatment_filter_argv": filter_argv,
        "remaining_encoder_argv_byte_identical": True,
    }, "raw-RGB calibration controlled variable")
    expected_prefix = [
        "$FFMPEG", "-hide_banner", "-loglevel", "error", "-xerror", "-abort_on",
        "empty_output+empty_output_stream", *expected_input, "-map", "0:v:0",
        "-map_metadata", "-1", "-map_chapters", "-1", "-sn", "-dn", "-an",
        "-frames:v", "1",
    ]
    encoding = contract["encoding"]
    expected_suffix = [
        "-c:v", encoding["video_codec"], "-preset", encoding["preset"], "-tune",
        encoding["tune"], "-crf", str(encoding["crf"]), "-pix_fmt",
        encoding["pixel_format"], "-fps_mode", "cfr", "-color_range",
        encoding["color_range"], "-colorspace", encoding["color_space"],
        "-color_primaries", encoding["color_primaries"], "-color_trc",
        encoding["color_transfer"], "-x264-params", encoding["x264_params"],
        "-tag:v", encoding["codec_tag"], "-movflags", encoding["movflags"],
        "-n", "$OUTPUT",
    ]
    _require_equal(report["common_encoder_prefix"], expected_prefix, "raw-RGB calibration encoder prefix")
    _require_equal(report["common_encoder_suffix"], expected_suffix, "raw-RGB calibration encoder suffix")
    expected_diagnostics = {
        "stream_probe": ["$FFPROBE", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", "$OUTPUT"],
        "frame_probe": ["$FFPROBE", "-v", "error", "-show_frames", "-of", "json", "$OUTPUT"],
        "sps_trace": ["$FFMPEG", "-hide_banner", "-loglevel", "info", "-i", "$OUTPUT", "-map", "0:v:0", "-c", "copy", "-bsf:v", "trace_headers", "-f", "null", "-"],
        "decode_rgb24": ["$FFMPEG", "-hide_banner", "-loglevel", "error", "-xerror", "-i", "$OUTPUT", "-map", "0:v:0", "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
        "decode_yuv420p": ["$FFMPEG", "-hide_banner", "-loglevel", "error", "-xerror", "-i", "$OUTPUT", "-map", "0:v:0", "-an", "-f", "rawvideo", "-pix_fmt", "yuv420p", "pipe:1"],
    }
    _require_equal(report["diagnostic_commands"], expected_diagnostics, "raw-RGB calibration diagnostic commands")

    expected_artifact_names = {
        "calibration-report-v1.json", "control-decode-stderr.txt", "control-encoder-stderr.txt",
        "control-ffprobe-frames.json", "control-ffprobe-frames-stderr.txt",
        "control-ffprobe-stream.json", "control-ffprobe-stream-stderr.txt", "control-sps-trace.txt",
        "h264-rgb-control.mp4", "h264-rgb-setparams.mp4", "setparams-decode-stderr.txt",
        "setparams-encoder-stderr.txt", "setparams-ffprobe-frames.json",
        "setparams-ffprobe-frames-stderr.txt", "setparams-ffprobe-stream.json",
        "setparams-ffprobe-stream-stderr.txt", "setparams-sps-trace.txt",
    }
    _require_equal(package["package_version"], 1, "raw-RGB calibration package version")
    _require_equal(package["package_id"], report["report_id"], "raw-RGB calibration package id")
    _require_equal(package["candidate_media_used"], False, "raw-RGB package candidate policy")
    _require_equal(package["candidate_authorization_consumed"], False, "raw-RGB package authorization policy")
    _require_equal(package["source_rgb24"], {
        "bytes": len(source_payload), "sha256": hashlib.sha256(source_payload).hexdigest(),
    }, "raw-RGB package source binding")
    _require_equal(package["machine_passed"], True, "raw-RGB package machine result")
    _require_equal(package["package_excludes_itself"], True, "raw-RGB package self-exclusion")
    artifacts = package["artifacts"]
    _require_equal({item["file"] for item in artifacts}, expected_artifact_names, "raw-RGB package artifact names")
    _require_equal({path.name for path in root.iterdir() if path.is_file()}, expected_artifact_names | {package_path.name}, "raw-RGB evidence directory inventory")
    for artifact in artifacts:
        path = root / artifact["file"]
        _require_equal(path.stat().st_size, artifact["bytes"], f"raw-RGB package bytes {path.name}")
        _require_equal(_sha256(path), artifact["sha256"], f"raw-RGB package hash {path.name}")

    sps_mapping = {
        "video_signal_type_present": "video_signal_type_present_flag",
        "full_range": "video_full_range_flag",
        "color_description_present": "colour_description_present_flag",
        "primaries": "colour_primaries",
        "transfer": "transfer_characteristics",
        "matrix": "matrix_coefficients",
    }
    decoded_audits: dict[str, dict[str, Any]] = {}
    for label, stem in (("control", "control"), ("treatment", "setparams")):
        evidence = report[label]
        media = root / evidence["media"]["file"]
        _require_equal(media.stat().st_size, evidence["media"]["bytes"], f"raw-RGB {label} media bytes")
        _require_equal(_sha256(media), evidence["media"]["sha256"], f"raw-RGB {label} media hash")
        stream_path = root / evidence["stream_probe"]["file"]
        frame_path = root / evidence["frame_probe"]["file"]
        trace_path = root / evidence["sps_trace"]["file"]
        _require_equal(_sha256(stream_path), evidence["stream_probe"]["sha256"], f"raw-RGB {label} stream hash")
        _require_equal(_sha256(frame_path), evidence["frame_probe"]["sha256"], f"raw-RGB {label} frame hash")
        _require_equal(_sha256(trace_path), evidence["sps_trace"]["sha256"], f"raw-RGB {label} SPS hash")
        stream_probe = _strict_json_loads(stream_path.read_bytes(), f"raw-RGB {label} stream probe")
        frame_probe = _strict_json_loads(frame_path.read_bytes(), f"raw-RGB {label} frame probe")
        _require_equal(len(stream_probe.get("streams", [])), 1, f"raw-RGB {label} stream count")
        _require_equal(len(frame_probe.get("frames", [])), 1, f"raw-RGB {label} frame count")
        stream = stream_probe["streams"][0]
        frame = frame_probe["frames"][0]
        _require_equal(evidence["stream_color"], {
            "range": stream.get("color_range"), "space": stream.get("color_space"),
            "transfer": stream.get("color_transfer"), "primaries": stream.get("color_primaries"),
        }, f"raw-RGB {label} stream color")
        _require_equal(evidence["frame_color"], {
            "range": frame.get("color_range"), "space": frame.get("color_space"),
            "transfer": frame.get("color_transfer"), "primaries": frame.get("color_primaries"),
        }, f"raw-RGB {label} frame color")
        parsed_sps = _parse_sps_trace(trace_path.read_text(encoding="utf-8"))
        for report_name, parsed_name in sps_mapping.items():
            values = parsed_sps[parsed_name]
            _require_equal(bool(values), True, f"raw-RGB {label} SPS {report_name} presence")
            _require_equal(set(values), {evidence["sps_vui"][report_name]}, f"raw-RGB {label} SPS {report_name}")
        _require_equal(_parse_mp4_colr(media), [evidence["container_nclx"]], f"raw-RGB {label} MP4 nclx")
        if ffmpeg is not None:
            for pixel_format, field_prefix in (("yuv420p", "decoded_yuv420p"), ("rgb24", "decoded_rgb24")):
                command = [
                    str(ffmpeg) if item == "$FFMPEG" else str(media) if item == "$OUTPUT" else item
                    for item in expected_diagnostics[f"decode_{pixel_format}"]
                ]
                result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                _require_equal(result.returncode, 0, f"raw-RGB {label} {pixel_format} decode return code")
                _require_equal(len(result.stdout), evidence[f"{field_prefix}_bytes"], f"raw-RGB {label} {pixel_format} decode bytes")
                _require_equal(hashlib.sha256(result.stdout).hexdigest(), evidence[f"{field_prefix}_sha256"], f"raw-RGB {label} {pixel_format} decode hash")
                _require_equal(result.stderr, b"", f"raw-RGB {label} {pixel_format} decode stderr")
        decoded_audits[label] = {
            "media_sha256": evidence["media"]["sha256"],
            "decoded_yuv420p_sha256": evidence["decoded_yuv420p_sha256"],
            "decoded_rgb24_sha256": evidence["decoded_rgb24_sha256"],
        }

    _require_equal(decoded_audits["control"]["decoded_yuv420p_sha256"], decoded_audits["treatment"]["decoded_yuv420p_sha256"], "raw-RGB control/treatment decoded YUV identity")
    _require_equal(decoded_audits["control"]["decoded_rgb24_sha256"], decoded_audits["treatment"]["decoded_rgb24_sha256"], "raw-RGB control/treatment decoded RGB identity")
    _require_equal(report["control"]["stream_color"], {"range": "tv", "space": "bt709", "transfer": None, "primaries": None}, "raw-RGB control stream defect")
    _require_equal(report["treatment"]["stream_color"], {"range": "tv", "space": "bt709", "transfer": "bt709", "primaries": "bt709"}, "raw-RGB treatment stream correction")
    _require_equal((report["control"]["container_nclx"]["primaries"], report["control"]["container_nclx"]["transfer"], report["control"]["container_nclx"]["matrix"]), (2, 2, 1), "raw-RGB control nclx defect")
    _require_equal((report["treatment"]["container_nclx"]["primaries"], report["treatment"]["container_nclx"]["transfer"], report["treatment"]["container_nclx"]["matrix"]), (1, 1, 1), "raw-RGB treatment nclx correction")
    _require_equal(all(report["gates"].values()), True, "raw-RGB calibration gates")
    return {
        "report_sha256": _sha256(report_path),
        "package_sha256": _sha256(package_path),
        "source_rgb24_sha256": source["payload_sha256"],
        "control": decoded_audits["control"],
        "treatment": decoded_audits["treatment"],
        "decoded_native_and_rgb_byte_identical": True,
        "stream_and_nclx_defect_cleared": True,
    }


def _validate_v1_probe_evidence(
    contract: dict[str, Any], ffmpeg: Path | None = None,
) -> dict[str, Any]:
    locks = contract["locks"]
    report_path = _repo_path(str(locks["vui_probe_v1_report"]["path"]))
    failure_path = _repo_path(str(locks["vui_probe_v1_failure"]["path"]))
    package_path = _repo_path(str(locks["vui_probe_v1_package"]["path"]))
    video_path = _repo_path(str(locks["vui_probe_v1_video"]["path"]))
    calibration_path = _repo_path(str(locks["synthetic_metadata_calibration"]["path"]))
    report = _strict_json_loads(report_path.read_bytes(), "V1 probe report")
    failure = _strict_json_loads(failure_path.read_bytes(), "V1 probe failure")
    package = _strict_json_loads(package_path.read_bytes(), "V1 probe package")
    calibration = _strict_json_loads(calibration_path.read_bytes(), "synthetic metadata calibration")
    _require_equal(report["status"], "METADATA_PROBE_REJECTED_NO_RETRY", "V1 probe report status")
    _require_equal(report["machine_passed"], False, "V1 probe machine result")
    _require_equal(report["failed_gates"], ["stream_color_metadata", "mp4_colr_nclx"], "V1 failed gates")
    _require_equal(report["encoder"]["process_count"], 1, "V1 encoder count")
    _require_equal(report["encoder"]["return_code"], 0, "V1 encoder return code")
    _require_equal(report["video"]["sha256"], _sha256(video_path), "V1 video report binding")
    _require_equal(report["decoded"]["minimum_full_frame_psnr_db"] >= 39.0, True, "V1 decoded PSNR gate")
    _require_equal(
        report["decoded"]["decoded_rgb24_sha256"],
        contract["acceptance"]["required_v1_identical_decoded_rgb24_sha256"],
        "V1 decoded RGB24 aggregate",
    )
    _require_equal(
        [item["decoded_rgb_sha256"] for item in report["decoded"]["frames"]],
        contract["acceptance"]["required_v1_identical_per_frame_rgb24_sha256"],
        "V1 decoded per-frame hashes",
    )
    _require_equal(failure["disposition"]["further_probe_attempt_allowed"], False, "V1 retry disposition")
    _require_equal(package["machine_passed"], False, "V1 package result")
    v2_command = _command_template(contract)
    filter_index = v2_command.index("-vf")
    _require_equal(
        v2_command[:filter_index] + v2_command[filter_index + 2:],
        report["encoder"]["command_template"],
        "V2 command with sole setparams pair removed equals V1 command",
    )
    _require_equal(calibration["candidate_media_used"], False, "synthetic calibration source policy")
    _require_equal(calibration["h264_mp4"]["baseline"]["container_colr"]["primaries"], 2, "synthetic control primaries")
    _require_equal(calibration["h264_mp4"]["baseline"]["container_colr"]["transfer"], 2, "synthetic control transfer")
    _require_equal(calibration["h264_mp4"]["setparams"]["container_colr"]["primaries"], 1, "synthetic treatment primaries")
    _require_equal(calibration["h264_mp4"]["setparams"]["container_colr"]["transfer"], 1, "synthetic treatment transfer")
    raw_rgb_calibration = _validate_raw_rgb_calibration(contract, ffmpeg)
    return {
        "report_sha256": _sha256(report_path), "failure_sha256": _sha256(failure_path),
        "package_sha256": _sha256(package_path), "video_sha256": _sha256(video_path),
        "synthetic_calibration_sha256": _sha256(calibration_path),
        "failed_gates": report["failed_gates"],
        "decoded_rgb24_sha256": report["decoded"]["decoded_rgb24_sha256"],
        "successor_delta": contract["encoding"]["filter_chain"],
        "raw_rgb_calibration": raw_rgb_calibration,
    }


def _capture_state(
    contract: dict[str, Any], ffmpeg: Path, ffprobe: Path, authorization: dict[str, str] | None,
) -> dict[str, Any]:
    local_manifest, archive = _source_paths(contract)
    return {
        "contract_raw_sha256": _sha256(REPO_ROOT / CONTRACT_RELATIVE_PATH),
        "authorization_subject_sha256": _canonical_hash(_authorization_subject(contract)),
        "implementation_sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
        "locks": {name: _lock_hash(reference) for name, reference in sorted(contract["locks"].items())},
        "local_source_manifest_sha256": _sha256(local_manifest),
        "source_archive_sha256": _sha256(archive),
        "ffmpeg_sha256": _sha256(ffmpeg),
        "ffprobe_sha256": _sha256(ffprobe),
        "command_template_sha256": _command_template_hash(contract),
        "authorization": authorization,
    }


def _assert_state(state: dict[str, Any], contract: dict[str, Any]) -> None:
    _require_equal(state["authorization_subject_sha256"], EXPECTED_AUTHORIZATION_SUBJECT_SHA256, "state subject hash")
    _require_equal(state["locks"], {name: reference["sha256"] for name, reference in sorted(contract["locks"].items())}, "state locks")
    _require_equal(state["local_source_manifest_sha256"], contract["locks"]["source_manifest"]["sha256"], "local manifest hash")
    _require_equal(state["source_archive_sha256"], contract["source_evidence"]["archive_sha256"], "archive hash")
    _require_equal(state["ffmpeg_sha256"], contract["toolchain"]["ffmpeg_sha256"], "FFmpeg state hash")
    _require_equal(state["ffprobe_sha256"], contract["toolchain"]["ffprobe_sha256"], "FFprobe state hash")
    _require_equal(state["command_template_sha256"], _command_template_hash(contract), "command template state hash")


def _prepare(contract: dict[str, Any], ffmpeg: Path, ffprobe: Path) -> dict[str, Any]:
    local_manifest, archive = _source_paths(contract)
    repository_manifest = _repo_path(str(contract["locks"]["source_manifest"]["path"]))
    local_payload = local_manifest.read_bytes()
    repository_payload = repository_manifest.read_bytes()
    _require_equal(local_payload, repository_payload, "local/repository manifest bytes")
    manifest = _strict_json_loads(repository_payload, "Candidate03 source manifest")
    _require_equal(manifest.get("manifest_version"), 2, "source manifest version")
    _require_equal(manifest.get("development_label"), "candidate-03", "source candidate")
    _require_equal(manifest.get("machine_passed"), True, "source machine result")
    _require_equal(manifest.get("encode_authorized"), False, "source encode state")
    frame_hashes = manifest.get("frame_hashes", [])
    _require_equal([item.get("frame") for item in frame_hashes], list(range(1, 229)), "ordered source inventory")
    selection = contract["selection"]
    selected_inventory = [frame_hashes[number - 1] for number in selection["source_frame_numbers"]]
    _require_equal(selected_inventory, selection["frame_hashes"], "selected source inventory")
    _require_equal(_canonical_hash(selected_inventory), selection["frame_inventory_canonical_sha256"], "selected inventory hash")
    source = contract["source_evidence"]
    _require_equal(archive.stat().st_size, source["archive_bytes"], "source archive byte count")
    _require_equal(_sha256(archive), source["archive_sha256"], "source archive SHA-256")
    _require_equal(manifest.get("lossless_archive_header"), source["archive_header"], "source archive header binding")
    frames, source_audit = _reconstruct_selected_frames(archive, contract, frame_hashes)
    return {
        "manifest": manifest,
        "repository_manifest": repository_manifest,
        "archive": archive,
        "frames": frames,
        "source_audit": source_audit,
        "attempt01": _validate_attempt01_evidence(contract),
        "predecessor_v1_probe": _validate_v1_probe_evidence(contract, ffmpeg),
        "toolchain": _validate_toolchain(ffmpeg, ffprobe, contract),
    }


def preflight(
    *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    contract = load_contract()
    ffmpeg_path = _resolved_tool(ffmpeg)
    ffprobe_path = _resolved_tool(ffprobe)
    before = _capture_state(contract, ffmpeg_path, ffprobe_path, _authorization(contract))
    _assert_state(before, contract)
    prepared = _prepare(contract, ffmpeg_path, ffprobe_path)
    after = _capture_state(contract, ffmpeg_path, ffprobe_path, _authorization(contract))
    _assert_state(after, contract)
    _require_equal(after, before, "nonpublishing preflight fixed state")
    return {
        "status": "SCAFFOLDED_UNAUTHORIZED" if before["authorization"] is None else "AUTHORIZED_PREFLIGHT_PASS",
        "build_authorized": before["authorization"] is not None,
        "encode_started": False,
        "encoding_process_count": 0,
        "output_resolved": False,
        "authorization_subject_sha256": EXPECTED_AUTHORIZATION_SUBJECT_SHA256,
        "implementation_sha256": before["implementation_sha256"],
        "command_template": _command_template(contract),
        "command_template_sha256": before["command_template_sha256"],
        "source_audit": prepared["source_audit"],
        "attempt01": prepared["attempt01"],
        "predecessor_v1_probe": prepared["predecessor_v1_probe"],
        "toolchain": prepared["toolchain"],
    }


def _output_path(contract: dict[str, Any]) -> Path:
    output = _outputs_path(str(contract["output"]["directory"]))
    expected = (REPO_ROOT / "../../outputs/edit/phase35-c03-blink-vui-probe-v2-attempt02").resolve()
    _require_equal(output, expected, "pinned probe output directory")
    return output


def _encoder_command(contract: dict[str, Any], ffmpeg: Path, output: Path) -> list[str]:
    return [str(ffmpeg) if value == "$FFMPEG" else str(output) if value == "$OUTPUT" else value for value in _command_template(contract)]


def _claim_attempt(output: Path, state: dict[str, Any], command: list[str]) -> Path:
    claim = output.parent / f".{output.name}.claim.json"
    payload = {
        "claim_version": 1,
        "attempt_id": "phase35_c03_blink_vui_probe_v2_attempt02",
        "state": "CLAIMED_BEFORE_ENCODER_LAUNCH",
        "authorization_consumed": True,
        "maximum_video_encoder_processes": 1,
        "automatic_retry_allowed": False,
        "captured_inputs": state,
        "encoder_command": command,
    }
    encoded = (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode("utf-8")
    try:
        descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise VuiProbeError(f"the single VUI probe attempt was already claimed: {claim}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException as exc:
        # Once O_EXCL succeeds this process owns the transaction. Even an incomplete
        # durable write consumes authorization and the claim must never be removed.
        raise ClaimWriteError(claim, exc) from exc
    return claim


def _run_json_command(
    command: list[str], destination: Path, stderr_destination: Path,
) -> dict[str, Any]:
    result = subprocess.run(command, capture_output=True, text=True)
    destination.write_text(result.stdout, encoding="utf-8")
    stderr_destination.write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise VuiProbeError(
            f"diagnostic command failed with exit {result.returncode}: {stderr_destination.name}"
        )
    return _strict_json_loads(result.stdout.encode("utf-8"), destination.name)


def _probe_stream(
    video: Path, ffprobe: Path, destination: Path, stderr_destination: Path,
) -> tuple[dict[str, Any], list[str]]:
    command = [
        str(ffprobe), "-v", "error", "-count_frames", "-show_entries",
        "stream=index,codec_type,codec_name,codec_tag_string,profile,pix_fmt,color_range,color_space,"
        "color_transfer,color_primaries,width,height,r_frame_rate,avg_frame_rate,nb_frames,"
        "nb_read_frames,start_time,duration,duration_ts,time_base:format=start_time,duration",
        "-of", "json", str(video),
    ]
    return _run_json_command(command, destination, stderr_destination), command


def _probe_frames(
    video: Path, ffprobe: Path, destination: Path, stderr_destination: Path,
) -> tuple[dict[str, Any], list[str]]:
    command = [
        str(ffprobe), "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=media_type,stream_index,width,height,pix_fmt,best_effort_timestamp,"
        "best_effort_timestamp_time,pkt_duration,pkt_duration_time,color_range,color_space,"
        "color_transfer,color_primaries", "-of", "json", str(video),
    ]
    return _run_json_command(command, destination, stderr_destination), command


SPS_FIELDS = (
    "video_signal_type_present_flag",
    "video_full_range_flag",
    "colour_description_present_flag",
    "colour_primaries",
    "transfer_characteristics",
    "matrix_coefficients",
)


def _parse_sps_trace(text: str) -> dict[str, list[int]]:
    observed: dict[str, list[int]] = {field: [] for field in SPS_FIELDS}
    for line in text.splitlines():
        for field in SPS_FIELDS:
            match = re.search(rf"\b{re.escape(field)}\b.*=\s*(\d+)\s*$", line)
            if match:
                observed[field].append(int(match.group(1)))
    return observed


def _trace_sps(video: Path, ffmpeg: Path, destination: Path) -> tuple[dict[str, list[int]], list[str]]:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "info", "-i", str(video),
        "-map", "0:v:0", "-c", "copy", "-bsf:v", "trace_headers", "-f", "null", "-",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    text = result.stdout + result.stderr
    destination.write_text(text, encoding="utf-8")
    if result.returncode != 0:
        raise VuiProbeError(f"H.264 SPS trace failed with exit {result.returncode}")
    return _parse_sps_trace(text), command


def _parse_mp4_colr(path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    containers = {b"moov", b"trak", b"mdia", b"minf", b"stbl"}
    records: list[dict[str, Any]] = []

    def boxes(start: int, end: int, parents: tuple[str, ...]) -> None:
        position = start
        while position + 8 <= end:
            size = struct.unpack_from(">I", data, position)[0]
            kind = data[position + 4:position + 8]
            header = 8
            if size == 1:
                if position + 16 > end:
                    raise VuiProbeError("truncated extended MP4 box")
                size = struct.unpack_from(">Q", data, position + 8)[0]
                header = 16
            elif size == 0:
                size = end - position
            if size < header or position + size > end:
                raise VuiProbeError("invalid MP4 box bounds")
            payload = position + header
            box_end = position + size
            name = kind.decode("latin-1")
            path_parts = parents + (name,)
            if kind == b"colr":
                if payload + 4 > box_end:
                    raise VuiProbeError("truncated MP4 colr box")
                colour_type = data[payload:payload + 4].decode("latin-1")
                payload_bytes = box_end - payload
                if colour_type != "nclx":
                    records.append({
                        "path": "/".join(path_parts),
                        "type": colour_type,
                        "payload_bytes": payload_bytes,
                    })
                else:
                    record: dict[str, Any] = {
                        "path": "/".join(path_parts),
                        "type": colour_type,
                        "payload_bytes": payload_bytes,
                    }
                    if payload_bytes >= 11:
                        primaries, transfer, matrix = struct.unpack_from(">HHH", data, payload + 4)
                        record.update({
                            "primaries": primaries,
                            "transfer": transfer,
                            "matrix": matrix,
                            "full_range_flag": (data[payload + 10] >> 7) & 1,
                            "reserved_bits": data[payload + 10] & 0x7f,
                        })
                    records.append(record)
            elif kind in containers:
                boxes(payload, box_end, path_parts)
            elif kind == b"stsd":
                if payload + 8 > box_end:
                    raise VuiProbeError("truncated MP4 stsd box")
                entry_count = struct.unpack_from(">I", data, payload + 4)[0]
                entry_position = payload + 8
                for _ in range(entry_count):
                    if entry_position + 8 > box_end:
                        raise VuiProbeError("truncated MP4 sample entry")
                    entry_size = struct.unpack_from(">I", data, entry_position)[0]
                    entry_kind = data[entry_position + 4:entry_position + 8]
                    entry_end = entry_position + entry_size
                    if entry_size < 86 or entry_end > box_end:
                        raise VuiProbeError("invalid MP4 visual sample entry")
                    if entry_kind in {b"avc1", b"avc3", b"hvc1", b"hev1"}:
                        boxes(entry_position + 86, entry_end, path_parts + (entry_kind.decode("latin-1"),))
                    entry_position = entry_end
                _require_equal(entry_position, box_end, "MP4 stsd sample-entry boundary")
            position = box_end
        if position != end:
            raise VuiProbeError("MP4 container has trailing partial box bytes")

    boxes(0, len(data), ())
    return records


def _decode_video(
    video: Path, source_frames: list[np.ndarray], ffmpeg: Path, stderr_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(video),
        "-map", "0:v:0", "-an", "-sn", "-dn", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True)
    stderr_path.write_bytes(result.stderr)
    if result.returncode != 0:
        raise VuiProbeError(f"probe decode failed with exit {result.returncode}")
    frame_bytes = 1920 * 1080 * 3
    _require_equal(len(result.stdout), frame_bytes * 9, "decoded RGB24 byte count")
    decoded = np.frombuffer(result.stdout, dtype=np.uint8).reshape(9, 1080, 1920, 3)
    per_frame: list[dict[str, Any]] = []
    nearest_order: list[int] = []
    for index, frame in enumerate(decoded):
        source = source_frames[index]
        difference = frame.astype(np.float64) - source.astype(np.float64)
        mse = float(np.mean(difference * difference))
        psnr = 999.0 if mse == 0.0 else 10.0 * math.log10((255.0 * 255.0) / mse)
        candidate_mse = [
            float(np.mean((frame.astype(np.float64) - candidate.astype(np.float64)) ** 2))
            for candidate in source_frames
        ]
        nearest_index = int(np.argmin(candidate_mse))
        nearest_number = 77 + nearest_index
        nearest_order.append(nearest_number)
        per_frame.append({
            "probe_frame": index + 1,
            "source_frame": 77 + index,
            "decoded_rgb_sha256": hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest(),
            "full_frame_psnr_db": psnr,
            "nearest_source_frame": nearest_number,
            "nearest_source_mse": candidate_mse[nearest_index],
        })
    return {
        "decoder_process_count": 1,
        "decoded_frame_count": 9,
        "decoded_rgb24_bytes": len(result.stdout),
        "decoded_rgb24_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "minimum_full_frame_psnr_db": min(item["full_frame_psnr_db"] for item in per_frame),
        "nearest_source_frame_order": nearest_order,
        "frames": per_frame,
    }, command


def _gate(name: str, actual: Any, expected: Any, passed: bool) -> dict[str, Any]:
    return {"name": name, "actual": actual, "expected": expected, "passed": bool(passed)}


def _audit_gates(
    contract: dict[str, Any], stream_probe: dict[str, Any], frame_probe: dict[str, Any],
    sps: dict[str, list[int]], colr: list[dict[str, Any]], decoded: dict[str, Any],
) -> list[dict[str, Any]]:
    acceptance = contract["acceptance"]
    streams = stream_probe.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    other_streams = [stream for stream in streams if stream.get("codec_type") not in {"video", "audio"}]
    video = video_streams[0] if len(video_streams) == 1 else {}
    frames = frame_probe.get("frames", [])
    expected_color = {
        "color_range": acceptance["required_color_range"],
        "color_space": acceptance["required_color_space"],
        "color_transfer": acceptance["required_color_transfer"],
        "color_primaries": acceptance["required_color_primaries"],
    }
    frame_colors = [
        {name: frame.get(name) for name in expected_color}
        for frame in frames
    ]
    timestamps = [float(frame.get("best_effort_timestamp_time", "nan")) for frame in frames]
    clock_ok = len(timestamps) == 9 and all(
        math.isfinite(value) and abs(value - index / 30.0) <= 0.00000051
        for index, value in enumerate(timestamps)
    )
    required_sps = {
        "video_signal_type_present_flag": acceptance["required_sps_video_signal_type_present_flag"],
        "video_full_range_flag": acceptance["required_sps_video_full_range_flag"],
        "colour_description_present_flag": acceptance["required_sps_colour_description_present_flag"],
        "colour_primaries": acceptance["required_sps_colour_primaries"],
        "transfer_characteristics": acceptance["required_sps_transfer_characteristics"],
        "matrix_coefficients": acceptance["required_sps_matrix_coefficients"],
    }
    expected_colr = {
        "path": acceptance["required_mp4_colr_path"],
        "type": acceptance["required_mp4_colr_type"],
        "payload_bytes": acceptance["required_mp4_colr_payload_bytes"],
        "primaries": acceptance["required_mp4_colr_primaries"],
        "transfer": acceptance["required_mp4_colr_transfer"],
        "matrix": acceptance["required_mp4_colr_matrix"],
        "full_range_flag": acceptance["required_mp4_colr_full_range_flag"],
        "reserved_bits": acceptance["required_mp4_colr_reserved_bits"],
    }
    gates = [
        _gate("stream_count", len(streams), acceptance["required_stream_count"], len(streams) == acceptance["required_stream_count"]),
        _gate("video_stream_count", len(video_streams), 1, len(video_streams) == 1),
        _gate("audio_stream_count", len(audio_streams), 0, len(audio_streams) == 0),
        _gate("other_stream_count", len(other_streams), 0, len(other_streams) == 0),
        _gate("video_codec", video.get("codec_name"), acceptance["required_codec_name"], video.get("codec_name") == acceptance["required_codec_name"]),
        _gate("video_codec_tag", video.get("codec_tag_string"), acceptance["required_codec_tag_string"], video.get("codec_tag_string") == acceptance["required_codec_tag_string"]),
        _gate("video_pixel_format", video.get("pix_fmt"), acceptance["required_pixel_format"], video.get("pix_fmt") == acceptance["required_pixel_format"]),
        _gate("video_geometry", [video.get("width"), video.get("height")], [1920, 1080], [video.get("width"), video.get("height")] == [1920, 1080]),
        _gate("reported_frames", int(video.get("nb_frames", 0)), 9, int(video.get("nb_frames", 0)) == 9),
        _gate("read_frames", int(video.get("nb_read_frames", 0)), 9, int(video.get("nb_read_frames", 0)) == 9),
        _gate("r_frame_rate", video.get("r_frame_rate"), "30/1", Fraction(video.get("r_frame_rate", "0/1")) == Fraction(30, 1)),
        _gate("avg_frame_rate", video.get("avg_frame_rate"), "30/1", Fraction(video.get("avg_frame_rate", "0/1")) == Fraction(30, 1)),
        _gate("video_start", video.get("start_time"), "0.000000", abs(float(video.get("start_time", "nan"))) <= 1e-9),
        _gate("video_duration", video.get("duration"), "0.300000", abs(float(video.get("duration", "nan")) - 0.3) <= 1e-9),
        _gate("container_start", stream_probe.get("format", {}).get("start_time"), "0.000000", abs(float(stream_probe.get("format", {}).get("start_time", "nan"))) <= 1e-9),
        _gate("container_duration", stream_probe.get("format", {}).get("duration"), "0.300000", abs(float(stream_probe.get("format", {}).get("duration", "nan")) - 0.3) <= 1e-9),
        _gate("stream_color_metadata", {name: video.get(name) for name in expected_color}, expected_color, all(video.get(name) == value for name, value in expected_color.items())),
        _gate("frame_probe_count", len(frames), 9, len(frames) == 9),
        _gate("frame_color_metadata", frame_colors, [expected_color] * 9, len(frames) == 9 and all(item == expected_color for item in frame_colors)),
        _gate("frame_clock", timestamps, [index / 30.0 for index in range(9)], clock_ok),
        _gate("decoded_frame_count", decoded["decoded_frame_count"], 9, decoded["decoded_frame_count"] == 9),
        _gate("decoded_frame_order", decoded["nearest_source_frame_order"], acceptance["required_nearest_source_frame_order"], decoded["nearest_source_frame_order"] == acceptance["required_nearest_source_frame_order"]),
        _gate("decoded_full_frame_psnr", decoded["minimum_full_frame_psnr_db"], acceptance["minimum_full_frame_psnr_db_all_frames"], decoded["minimum_full_frame_psnr_db"] >= acceptance["minimum_full_frame_psnr_db_all_frames"]),
        _gate(
            "decoded_rgb24_identical_to_v1",
            decoded["decoded_rgb24_sha256"],
            acceptance["required_v1_identical_decoded_rgb24_sha256"],
            decoded["decoded_rgb24_sha256"] == acceptance["required_v1_identical_decoded_rgb24_sha256"],
        ),
        _gate(
            "decoded_per_frame_identical_to_v1",
            [item["decoded_rgb_sha256"] for item in decoded["frames"]],
            acceptance["required_v1_identical_per_frame_rgb24_sha256"],
            [item["decoded_rgb_sha256"] for item in decoded["frames"]]
            == acceptance["required_v1_identical_per_frame_rgb24_sha256"],
        ),
        _gate("mp4_colr_count", len(colr), 1, len(colr) == 1),
        _gate("mp4_colr_nclx", {key: colr[0].get(key) for key in expected_colr} if len(colr) == 1 else colr, expected_colr, len(colr) == 1 and all(colr[0].get(key) == value for key, value in expected_colr.items())),
    ]
    for field, expected in required_sps.items():
        observed = sps.get(field, [])
        gates.append(_gate(f"sps_{field}", observed, [expected], bool(observed) and set(observed) == {expected}))
    return gates


def _artifact_inventory(directory: Path, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude or set()
    entries: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name in excluded:
            continue
        if not path.is_file():
            raise VuiProbeError(f"probe stage contains non-file entry: {path.name}")
        entries.append({"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return entries


def _preserve_rejected(
    stage: Path, rejected: Path, claim: Path, exc: BaseException,
    encoder_started: bool, attempt: dict[str, Any], contract: dict[str, Any],
) -> None:
    if rejected.exists():
        raise VuiProbeError(f"immutable rejected probe already exists: {rejected}") from exc
    if claim.is_file() and not (stage / "attempt-claim-v1.json").exists():
        shutil.copy2(claim, stage / "attempt-claim-v1.json")
    failure_path = stage / "failure-v1.json"
    package_path = stage / str(contract["output"]["package_filename"])
    failure = {
        "status": "PHASE35_C03_BLINK_VUI_PROBE_V2_ATTEMPT02_REJECTED_NO_RETRY",
        "authorization_consumed": True,
        "encoder_process_started": encoder_started,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "attempt": attempt,
        "available_artifacts": _artifact_inventory(stage, {failure_path.name, package_path.name}),
        "disposition": {
            "further_probe_attempt_allowed": False,
            "full_phase35_encode_authorized": False,
            "phase36_encode_authorized": False,
            "promotion_allowed": False,
        },
    }
    failure_path.write_text(json.dumps(failure, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    package = {
        "package_version": 1,
        "attempt_id": "phase35_c03_blink_vui_probe_v2_attempt02",
        "machine_passed": False,
        "authorization_consumed": True,
        "artifacts": _artifact_inventory(stage, {package_path.name}),
        "disposition": failure["disposition"],
    }
    package_path.write_text(json.dumps(package, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for artifact in package["artifacts"]:
        path = stage / artifact["file"]
        _require_equal(path.stat().st_size, artifact["bytes"], f"rejection package bytes {path.name}")
        _require_equal(_sha256(path), artifact["sha256"], f"rejection package SHA-256 {path.name}")
    stage.rename(rejected)


def run_authorized_probe(
    *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    contract = load_contract()
    authorization = _authorization(contract)
    if authorization is None:
        raise VuiProbeError("probe is scaffolded but not authorized; refusing before output resolution")
    ffmpeg_path = _resolved_tool(ffmpeg)
    ffprobe_path = _resolved_tool(ffprobe)
    output = _output_path(contract)
    rejected = output.with_name(output.name + "-rejected")
    claim_path = output.parent / f".{output.name}.claim.json"
    for immutable in (output, rejected, claim_path):
        if immutable.exists():
            raise VuiProbeError(f"immutable VUI probe state already exists: {immutable}")
    output.parent.mkdir(parents=True, exist_ok=True)
    prior_partial = next(iter(output.parent.glob(f".{output.name}.partial-*")), None)
    if prior_partial is not None:
        raise VuiProbeError(f"an earlier VUI probe partial state exists: {prior_partial}")
    initial_state = _capture_state(contract, ffmpeg_path, ffprobe_path, authorization)
    _assert_state(initial_state, contract)
    prepared = _prepare(contract, ffmpeg_path, ffprobe_path)
    _require_equal(_capture_state(contract, ffmpeg_path, ffprobe_path, _authorization(contract)), initial_state, "preclaim fixed state")
    free_bytes = shutil.disk_usage(output.parent).free
    minimum_free = int(contract["toolchain"]["minimum_free_output_bytes"])
    if free_bytes < minimum_free:
        raise VuiProbeError(f"insufficient free space before single probe: {free_bytes} < {minimum_free}")

    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    claim: Path | None = None
    process: subprocess.Popen[bytes] | None = None
    encoder_started = False
    claim_created = False
    encode_count = 0
    encoder_return_code: int | None = None
    partial_video = stage / (Path(str(contract["output"]["video_filename"])).stem + ".partial.mp4")
    command = _encoder_command(contract, ffmpeg_path, partial_video)
    attempt: dict[str, Any] = {
        "captured_state": initial_state,
        "encoder_command": command,
        "encoding_process_count": encode_count,
        "encoder_return_code": encoder_return_code,
        "source_frames_written": 0,
        "source_bytes_written": 0,
    }
    try:
        try:
            claim = _claim_attempt(output, initial_state, command)
            claim_created = True
        except ClaimWriteError as exc:
            claim = exc.claim
            claim_created = True
            raise
        shutil.copy2(claim, stage / "attempt-claim-v1.json")
        _require_equal(_capture_state(contract, ffmpeg_path, ffprobe_path, _authorization(contract)), initial_state, "postclaim fixed state")
        stderr_path = stage / str(contract["output"]["stderr_filename"])
        frames_written = 0
        bytes_written = 0
        with stderr_path.open("wb") as stderr_handle:
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr_handle,
            )
            encoder_started = True
            encode_count = 1
            attempt["encoding_process_count"] = encode_count
            if process.stdin is None:
                raise VuiProbeError("ffmpeg raw-video pipe was not created")
            for frame in prepared["frames"]:
                payload = np.ascontiguousarray(frame).tobytes()
                _require_equal(len(payload), 6220800, f"encoder frame {frames_written + 1} byte count")
                written = process.stdin.write(payload)
                _require_equal(written, len(payload), f"encoder frame {frames_written + 1} pipe write")
                frames_written += 1
                bytes_written += len(payload)
                attempt["source_frames_written"] = frames_written
                attempt["source_bytes_written"] = bytes_written
            process.stdin.close()
            encoder_return_code = process.wait()
            attempt["encoder_return_code"] = encoder_return_code
        _require_equal(frames_written, 9, "encoder source frame count")
        _require_equal(bytes_written, 55987200, "encoder source byte count")
        if encoder_return_code != 0:
            raise VuiProbeError(f"single FFmpeg probe encode failed with exit {encoder_return_code}")
        if not partial_video.is_file() or partial_video.stat().st_size == 0:
            raise VuiProbeError("single FFmpeg probe encode produced no video")
        video = stage / str(contract["output"]["video_filename"])
        os.replace(partial_video, video)
        _require_equal(_capture_state(contract, ffmpeg_path, ffprobe_path, _authorization(contract)), initial_state, "postencode fixed state")

        stream_path = stage / str(contract["output"]["stream_probe_filename"])
        stream_stderr_path = stage / str(contract["output"]["stream_probe_stderr_filename"])
        frame_path = stage / str(contract["output"]["frame_probe_filename"])
        frame_stderr_path = stage / str(contract["output"]["frame_probe_stderr_filename"])
        trace_path = stage / str(contract["output"]["sps_trace_filename"])
        decode_stderr = stage / "decode-stderr-v1.txt"
        stream_probe, stream_command = _probe_stream(
            video, ffprobe_path, stream_path, stream_stderr_path,
        )
        frame_probe, frame_command = _probe_frames(
            video, ffprobe_path, frame_path, frame_stderr_path,
        )
        sps, trace_command = _trace_sps(video, ffmpeg_path, trace_path)
        colr = _parse_mp4_colr(video)
        decoded, decode_command = _decode_video(video, prepared["frames"], ffmpeg_path, decode_stderr)
        gates = _audit_gates(contract, stream_probe, frame_probe, sps, colr, decoded)
        machine_passed = all(gate["passed"] for gate in gates)
        report = {
            "report_version": 1,
            "attempt_id": "phase35_c03_blink_vui_probe_v2_attempt02",
            "status": "METADATA_PROBE_PASSED_NO_DELIVERY_AUTHORITY" if machine_passed else "METADATA_PROBE_REJECTED_NO_RETRY",
            "machine_passed": machine_passed,
            "authorization_consumed": True,
            "scope": "one exact nine-frame Candidate03 blink H.264/MP4 V2 setparams metadata diagnostic",
            "authorization": authorization,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": initial_state["contract_raw_sha256"],
                "authorization_subject_sha256": initial_state["authorization_subject_sha256"],
            },
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": initial_state["implementation_sha256"]},
            "attempt_claim": {"file": "attempt-claim-v1.json", "sha256": _sha256(stage / "attempt-claim-v1.json")},
            "captured_state": initial_state,
            "source": prepared["source_audit"],
            "attempt01_defect": prepared["attempt01"],
            "predecessor_v1_probe": prepared["predecessor_v1_probe"],
            "toolchain": prepared["toolchain"],
            "encoder": {
                "command": command,
                "command_template": _command_template(contract),
                "command_template_sha256": _command_template_hash(contract),
                "process_count": encode_count,
                "return_code": encoder_return_code,
                "source_frames_written": frames_written,
                "source_bytes_written": bytes_written,
                "stderr": {"file": stderr_path.name, "sha256": _sha256(stderr_path)},
            },
            "video": {"file": video.name, "bytes": video.stat().st_size, "sha256": _sha256(video)},
            "diagnostic_commands": {
                "stream_probe": stream_command,
                "frame_probe": frame_command,
                "sps_trace": trace_command,
                "decode": decode_command,
            },
            "stream_probe": stream_probe,
            "frame_probe": frame_probe,
            "sps_vui": sps,
            "mp4_colr": colr,
            "decoded": decoded,
            "gates": gates,
            "gate_count": len(gates),
            "gates_passed": sum(1 for gate in gates if gate["passed"]),
            "gates_failed": sum(1 for gate in gates if not gate["passed"]),
            "failed_gates": [gate["name"] for gate in gates if not gate["passed"]],
            "disposition": {
                "metadata_defects_cleared": machine_passed,
                "attempt01_chroma_failures_cleared": False,
                "full_phase35_encode_authorized": False,
                "phase36_encode_authorized": False,
                "candidate02_audio_mux_authorized": False,
                "promotion_allowed": False,
                "retry_allowed": False,
            },
        }
        report_path = stage / str(contract["output"]["report_filename"])
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if not machine_passed:
            raise VuiProbeError(f"VUI metadata probe gates failed: {report['failed_gates']}")
        package_path = stage / str(contract["output"]["package_filename"])
        package = {
            "package_version": 1,
            "attempt_id": report["attempt_id"],
            "machine_passed": True,
            "authorization_consumed": True,
            "artifacts": _artifact_inventory(stage, {package_path.name}),
            "disposition": report["disposition"],
        }
        package_path.write_text(json.dumps(package, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        expected_names = {
            "attempt-claim-v1.json", str(contract["output"]["video_filename"]),
            str(contract["output"]["stderr_filename"]), str(contract["output"]["stream_probe_filename"]),
            str(contract["output"]["stream_probe_stderr_filename"]),
            str(contract["output"]["frame_probe_filename"]),
            str(contract["output"]["frame_probe_stderr_filename"]),
            str(contract["output"]["sps_trace_filename"]),
            "decode-stderr-v1.txt", str(contract["output"]["report_filename"]),
            str(contract["output"]["package_filename"]),
        }
        _require_equal({path.name for path in stage.iterdir()}, expected_names, "success artifact inventory")
        for artifact in package["artifacts"]:
            path = stage / artifact["file"]
            _require_equal(path.stat().st_size, artifact["bytes"], f"package bytes {path.name}")
            _require_equal(_sha256(path), artifact["sha256"], f"package SHA-256 {path.name}")
        _require_equal(_capture_state(contract, ffmpeg_path, ffprobe_path, _authorization(contract)), initial_state, "prepublication fixed state")
        if output.exists():
            raise VuiProbeError(f"immutable output appeared before publication: {output}")
        stage.rename(output)
        return {
            "output_directory": str(output),
            "video": str(output / video.name),
            "video_sha256": report["video"]["sha256"],
            "report": str(output / report_path.name),
            "package": str(output / package_path.name),
            "machine_passed": True,
            "encoding_process_count": encode_count,
            "retry_allowed": False,
            "phase36_encode_authorized": False,
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
        if process is not None:
            attempt["encoder_return_code"] = process.poll()
        if claim_created and claim is not None:
            _preserve_rejected(stage, rejected, claim, exc, encoder_started, attempt, contract)
        elif stage.exists():
            shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run-authorized-probe"):
        command = subparsers.add_parser(name)
        command.add_argument("--ffmpeg", default="ffmpeg")
        command.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "preflight":
        result = preflight(ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    else:
        result = run_authorized_probe(ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
