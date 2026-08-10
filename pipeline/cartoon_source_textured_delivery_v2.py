"""One-shot A/V delivery and successor audit for Phase35 Candidate 03."""
from __future__ import annotations

import argparse
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
import tarfile
import tempfile
from typing import Any, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase35_candidate03_delivery_v1.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_source_textured_delivery_v2.py"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "24b323458358341c547ba41fc61edb9b521814fd2c5b685e369b9be93bb1e578"


class SourceTexturedDeliveryV2Error(RuntimeError):
    pass


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
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_frame_hash(frame: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SourceTexturedDeliveryV2Error(
            f"Phase35 Candidate03 delivery mismatch for {label}: {actual!r} != {expected!r}"
        )


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise SourceTexturedDeliveryV2Error(f"locked repository path escapes the repository: {relative}") from exc
    if not path.is_file():
        raise SourceTexturedDeliveryV2Error(f"locked repository file is missing: {relative}")
    return path


def _outputs_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    outputs_root = (REPO_ROOT / "../../outputs").resolve()
    try:
        path.relative_to(outputs_root)
    except ValueError as exc:
        raise SourceTexturedDeliveryV2Error(f"delivery path escapes the pinned outputs tree: {relative}") from exc
    return path


def _resolved_tool(executable: str) -> Path:
    located = shutil.which(executable)
    if located is None:
        candidate = Path(executable).resolve()
        if not candidate.is_file():
            raise SourceTexturedDeliveryV2Error(f"required executable was not found: {executable}")
        located = str(candidate)
    return Path(located).resolve()


def _validate_toolchain(ffmpeg: Path, ffprobe: Path, contract: dict[str, Any]) -> dict[str, Any]:
    requirements = contract["preclaim_requirements"]
    encoders_command = [str(ffmpeg), "-hide_banner", "-encoders"]
    encoders = subprocess.run(encoders_command, check=True, capture_output=True, text=True)
    for encoder in (
        requirements["required_video_encoder"], requirements["required_audio_encoder"],
    ):
        if re.search(rf"(?m)^\s*[A-Z.]+\s+{re.escape(str(encoder))}\s", encoders.stdout) is None:
            raise SourceTexturedDeliveryV2Error(f"required FFmpeg encoder is unavailable: {encoder}")
        help_command = [str(ffmpeg), "-hide_banner", "-h", f"encoder={encoder}"]
        help_result = subprocess.run(help_command, check=True, capture_output=True, text=True)
        if f"Encoder {encoder}" not in help_result.stdout:
            raise SourceTexturedDeliveryV2Error(f"FFmpeg could not describe required encoder: {encoder}")
    component_checks = [
        ("decoder", str(decoder)) for decoder in requirements["required_video_decoders"]
    ]
    component_checks.extend(
        ("decoder", str(decoder)) for decoder in requirements["required_audio_decoders"]
    )
    component_checks.extend(
        ("demuxer", str(name)) for name in requirements["required_input_demuxers"]
    )
    component_checks.extend(
        ("muxer", str(name)) for name in requirements["required_output_muxers"]
    )
    component_checks.append(("filter", str(requirements["required_audio_filter"])))
    component_commands: list[list[str]] = []
    for kind, name in component_checks:
        command = [str(ffmpeg), "-hide_banner", "-h", f"{kind}={name}"]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        if not result.stdout.strip() or "Unknown" in result.stdout:
            raise SourceTexturedDeliveryV2Error(f"required FFmpeg {kind} is unavailable: {name}")
        component_commands.append(command)
    ffmpeg_version_command = [str(ffmpeg), "-version"]
    ffprobe_version_command = [str(ffprobe), "-version"]
    ffmpeg_version_text = subprocess.run(
        ffmpeg_version_command, check=True, capture_output=True, text=True,
    ).stdout
    ffprobe_version_text = subprocess.run(
        ffprobe_version_command, check=True, capture_output=True, text=True,
    ).stdout
    ffmpeg_version = ffmpeg_version_text.splitlines()
    ffprobe_version = ffprobe_version_text.splitlines()
    if (
        not ffmpeg_version or not ffmpeg_version[0].startswith("ffmpeg version ")
        or not ffprobe_version or not ffprobe_version[0].startswith("ffprobe version ")
    ):
        raise SourceTexturedDeliveryV2Error("FFmpeg/FFprobe version output is unavailable")
    def build_identity(lines: list[str]) -> dict[str, Any]:
        first = lines[0].split()
        configuration = next((line.strip() for line in lines if line.startswith("configuration:")), "")
        libraries = sorted(
            re.sub(r"\s+", " ", line.strip())
            for line in lines
            if re.match(r"^lib(?:av|sw|postproc)", line.strip())
        )
        return {
            "version": first[2] if len(first) >= 3 else "",
            "configuration": configuration,
            "libraries": libraries,
        }
    ffmpeg_identity = build_identity(ffmpeg_version)
    ffprobe_identity = build_identity(ffprobe_version)
    if requirements["required_tool_version_family_match"] is True:
        _require_equal(ffprobe_identity, ffmpeg_identity, "FFmpeg/FFprobe build identity")

    available_backends = set(cv2.videoio_registry.getBackends())
    if cv2.CAP_FFMPEG not in available_backends:
        raise SourceTexturedDeliveryV2Error("OpenCV FFmpeg video-I/O backend is unavailable")
    h264_probe_path = _repo_path(str(contract["locks"]["opencv_h264_probe_video"]["path"]))
    h264_probe = _probe(h264_probe_path, ffprobe)
    h264_streams = [stream for stream in h264_probe.get("streams", []) if stream.get("codec_type") == "video"]
    _require_equal(len(h264_streams), 1, "H.264 probe video stream count")
    h264_stream = h264_streams[0]
    _require_equal(h264_stream.get("codec_name"), "h264", "H.264 probe codec")
    _require_equal(
        int(h264_stream.get("nb_read_frames", 0)),
        requirements["opencv_h264_probe_frame_count"],
        "FFprobe H.264 decoded frame count",
    )
    capture = cv2.VideoCapture(str(h264_probe_path), cv2.CAP_FFMPEG)
    if not capture.isOpened():
        raise SourceTexturedDeliveryV2Error("OpenCV FFmpeg backend could not open the locked H.264 probe")
    opencv_frames = 0
    backend_name = ""
    try:
        backend_name = capture.getBackendName()
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            _require_equal(
                frame.shape,
                (
                    requirements["opencv_h264_probe_height"],
                    requirements["opencv_h264_probe_width"],
                    3,
                ),
                f"OpenCV H.264 probe frame {opencv_frames + 1} shape",
            )
            opencv_frames += 1
    finally:
        capture.release()
    _require_equal(backend_name, "FFMPEG", "OpenCV video backend")
    _require_equal(
        opencv_frames,
        requirements["opencv_h264_probe_frame_count"],
        "OpenCV H.264 decoded frame count",
    )
    return {
        "encoders_command": encoders_command,
        "ffmpeg_version_command": ffmpeg_version_command,
        "ffprobe_version_command": ffprobe_version_command,
        "required_encoders": [
            requirements["required_video_encoder"], requirements["required_audio_encoder"],
        ],
        "required_components": [f"{kind}:{name}" for kind, name in component_checks],
        "component_commands": component_commands,
        "ffmpeg_version": ffmpeg_version[0],
        "ffprobe_version": ffprobe_version[0],
        "shared_build_identity": ffmpeg_identity,
        "h264_probe": {
            "path": str(h264_probe_path),
            "sha256": _sha256(h264_probe_path),
            "ffprobe_decoded_frames": int(h264_stream["nb_read_frames"]),
            "opencv_backend": backend_name,
            "opencv_decoded_frames": opencv_frames,
        },
    }


def _lock_hash(reference: dict[str, Any]) -> str:
    path = _repo_path(str(reference["path"]))
    if reference.get("hash_domain") == "lf_normalized_text":
        return _lf_hash(path)
    return _sha256(path)


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned contract path")
    contract = json.loads(resolved.read_text(encoding="utf-8"))
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "contract canonical SHA-256")
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase35_candidate03_delivery_v1", "contract id")
    _require_equal(contract["cash_cost"], 0, "cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "paid dependency policy")
    _require_equal(contract["network_runtime_required"], False, "network policy")
    _require_equal(contract["clock"], {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "frame_count": 228,
        "duration_seconds": 7.6,
        "audio_sample_rate": 48000,
        "audio_sample_count": 364800,
        "audio_channels": 2,
        "audio_sample_width": 3,
    }, "delivery clock")
    authorization = contract["authorization"]
    _require_equal(authorization["required_verdict"], "PHASE35_C03_VISUAL_ACCEPTED_ENCODE_AUTHORIZED", "review verdict")
    _require_equal(authorization["maximum_video_encoder_processes"], 1, "encoder allowance")
    _require_equal(authorization["automatic_retry_allowed"], False, "automatic retry policy")
    _require_equal(authorization["source_must_be_exact_archived_rgb_frames"], True, "archived source policy")
    _require_equal(authorization["audio_must_be_exact_locked_delivery_mix"], True, "audio source policy")
    _require_equal(authorization["renderer_invocation_allowed"], False, "renderer invocation policy")
    _require_equal(authorization["one_versioned_encode_only"], True, "one encode policy")
    _require_equal(contract["preclaim_requirements"], {
        "required_video_encoder": "libx264",
        "required_audio_encoder": "aac",
        "required_video_decoders": ["h264"],
        "required_audio_decoders": ["aac", "pcm_s24le"],
        "required_input_demuxers": ["rawvideo", "wav", "mov"],
        "required_output_muxers": ["mp4", "s24le"],
        "required_audio_filter": "atrim",
        "required_probe_tool": "ffprobe",
        "required_tool_version_family_match": True,
        "opencv_h264_probe_width": 1920,
        "opencv_h264_probe_height": 1080,
        "opencv_h264_probe_frame_count": 96,
        "minimum_free_output_bytes": 2147483648,
    }, "preclaim requirements")
    _require_equal(contract["delivery"]["one_video_encode_without_retry"], True, "delivery retry policy")
    _require_equal(contract["failure_policy"]["failed_encode_attempt_is_preserved"], True, "failed attempt preservation")
    _require_equal(contract["promotion_policy"]["accepted_full_cartoon_production_delivery"], False, "production acceptance")
    for name, reference in contract["locks"].items():
        _require_equal(_lock_hash(reference), reference["sha256"], f"locked {name} SHA-256")
    return contract


def _source_paths(contract: dict[str, Any]) -> tuple[Path, Path, Path]:
    source = contract["source_evidence"]
    directory = _outputs_path(str(source["external_directory"]))
    expected = (REPO_ROOT / "../../outputs/edit/phase35-source-textured-direct-address-preview-v2-candidate-03").resolve()
    _require_equal(directory, expected, "Candidate03 external evidence directory")
    manifest = directory / str(source["manifest_filename"])
    archive = directory / str(source["archive_filename"])
    if not manifest.is_file() or not archive.is_file():
        raise SourceTexturedDeliveryV2Error("the exact local Candidate03 manifest/archive pair is missing")
    return directory, manifest, archive


def _validate_review_artifacts(manifest: dict[str, Any], repository_manifest: Path) -> dict[str, str]:
    evidence = repository_manifest.parent
    validated: dict[str, str] = {}
    for name, reference in manifest["artifacts"].items():
        if name == "lossless_frame_archive":
            continue
        path = evidence / str(reference["file"])
        if not path.is_file():
            raise SourceTexturedDeliveryV2Error(f"reviewed Candidate03 artifact is missing: {path.name}")
        digest = _sha256(path)
        _require_equal(digest, reference["sha256"], f"review artifact {path.name} SHA-256")
        _require_equal(path.stat().st_size, reference["bytes"], f"review artifact {path.name} byte count")
        validated[path.name] = digest
    _require_equal(len(validated), 5, "review artifact count")
    return validated


def _validate_source_implementation_archive(contract: dict[str, Any]) -> None:
    reference = contract["locks"]["source_implementation_archive"]
    path = _repo_path(str(reference["path"]))
    with tarfile.open(path, "r") as archive:
        member = archive.extractfile(str(reference["renderer_member"]))
        if member is None:
            raise SourceTexturedDeliveryV2Error("Candidate03 source archive omits the executed renderer")
        _require_equal(
            hashlib.sha256(member.read()).hexdigest(),
            reference["renderer_sha256"],
            "archived executed renderer SHA-256",
        )


def _validate_review(contract: dict[str, Any]) -> None:
    path = _repo_path(str(contract["locks"]["visual_review"]["path"]))
    text = path.read_text(encoding="utf-8")
    required = (
        "Verdict: PHASE35_C03_VISUAL_ACCEPTED_ENCODE_AUTHORIZED",
        "authorizes exactly one versioned 7.6s A/V proof encode of Candidate 03",
        contract["locks"]["source_manifest"]["sha256"],
        "same-domain successor-audit method (8x8 face-ROI, codec delta <= 2.0",
    )
    for phrase in required:
        if phrase not in text:
            raise SourceTexturedDeliveryV2Error(f"visual authorization omits required text: {phrase}")


def _probe(path: Path, ffprobe: Path) -> dict[str, Any]:
    command = [
        str(ffprobe), "-v", "error", "-count_frames", "-show_entries",
        "stream=index,codec_type,codec_name,profile,pix_fmt,color_range,color_space,color_transfer,color_primaries,"
        "width,height,r_frame_rate,avg_frame_rate,"
        "nb_frames,nb_read_frames,start_time,duration,duration_ts,time_base,sample_rate,channels,channel_layout:"
        "format=start_time,duration",
        "-of", "json", str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _probe_pcm_wave(path: Path) -> dict[str, int]:
    file_size = path.stat().st_size
    with path.open("rb") as audio:
        header = audio.read(12)
        if len(header) != 12:
            raise SourceTexturedDeliveryV2Error("source mix has a truncated RIFF header")
        riff_id, riff_size, wave_id = struct.unpack("<4sI4s", header)
        if riff_id != b"RIFF" or wave_id != b"WAVE" or riff_size + 8 != file_size:
            raise SourceTexturedDeliveryV2Error("source mix RIFF/WAVE signature or declared size is invalid")
        riff_end = riff_size + 8
        fmt_payload: bytes | None = None
        data_size: int | None = None
        while audio.tell() < riff_end:
            if riff_end - audio.tell() < 8:
                raise SourceTexturedDeliveryV2Error("source mix has a truncated chunk header")
            chunk_id, chunk_size = struct.unpack("<4sI", audio.read(8))
            padded_end = audio.tell() + chunk_size + (chunk_size % 2)
            if padded_end > riff_end:
                raise SourceTexturedDeliveryV2Error("source mix chunk exceeds the RIFF container")
            if chunk_id == b"fmt ":
                if fmt_payload is not None:
                    raise SourceTexturedDeliveryV2Error("source mix has duplicate fmt chunks")
                fmt_payload = audio.read(chunk_size)
            else:
                if chunk_id == b"data":
                    if data_size is not None:
                        raise SourceTexturedDeliveryV2Error("source mix has duplicate data chunks")
                    data_size = chunk_size
                audio.seek(chunk_size, os.SEEK_CUR)
            if chunk_size % 2 and audio.read(1) == b"":
                raise SourceTexturedDeliveryV2Error("source mix chunk is missing its pad byte")
    if fmt_payload is None or len(fmt_payload) < 16 or data_size is None:
        raise SourceTexturedDeliveryV2Error("source mix omits a complete fmt/data chunk pair")
    format_tag, channels, sample_rate, byte_rate, block_align, bits = struct.unpack(
        "<HHIIHH", fmt_payload[:16],
    )
    if format_tag == 0xFFFE:
        if len(fmt_payload) < 40:
            raise SourceTexturedDeliveryV2Error("source mix has a truncated extensible fmt chunk")
        extension_size = struct.unpack_from("<H", fmt_payload, 16)[0]
        valid_bits = struct.unpack_from("<H", fmt_payload, 18)[0]
        pcm_guid = bytes.fromhex("0100000000001000800000aa00389b71")
        if extension_size < 22 or 18 + extension_size > len(fmt_payload):
            raise SourceTexturedDeliveryV2Error("source mix extensible fmt payload is truncated")
        if fmt_payload[24:40] != pcm_guid or valid_bits != bits:
            raise SourceTexturedDeliveryV2Error("source mix extensible subtype is not matching-width PCM")
    elif format_tag != 1:
        raise SourceTexturedDeliveryV2Error("source mix is compressed rather than PCM")
    if channels <= 0 or sample_rate <= 0 or bits <= 0 or bits % 8:
        raise SourceTexturedDeliveryV2Error("source mix PCM geometry is invalid")
    sample_width = bits // 8
    if block_align != channels * sample_width or byte_rate != sample_rate * block_align:
        raise SourceTexturedDeliveryV2Error("source mix PCM alignment/rate is invalid")
    if data_size % block_align:
        raise SourceTexturedDeliveryV2Error("source mix data is not sample-frame aligned")
    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "sample_width": sample_width,
        "block_align": block_align,
        "byte_rate": byte_rate,
        "data_bytes": data_size,
        "sample_count": data_size // block_align,
    }


def _validate_source_audio_probe(probe: dict[str, Any], contract: dict[str, Any]) -> None:
    streams = probe.get("streams", [])
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    _require_equal(len(audio), 1, "source mix audio stream count")
    stream = audio[0]
    clock = contract["clock"]
    _require_equal(stream.get("codec_name"), "pcm_s24le", "source mix codec")
    _require_equal(int(stream.get("sample_rate", 0)), clock["audio_sample_rate"], "source mix sample rate")
    _require_equal(int(stream.get("channels", 0)), clock["audio_channels"], "source mix channels")
    _require_equal(int(stream.get("duration_ts", 0)), clock["audio_sample_count"], "source mix sample clock")
    _require_equal(Fraction(stream.get("time_base", "0/1")), Fraction(1, 48000), "source mix time base")


def _read_exact(handle: gzip.GzipFile, size: int) -> bytes:
    blocks: list[bytes] = []
    remaining = size
    while remaining:
        block = handle.read(remaining)
        if not block:
            break
        blocks.append(block)
        remaining -= len(block)
    return b"".join(blocks)


def iter_source_frames(
    archive_path: Path,
    contract: dict[str, Any],
    frame_hashes: list[dict[str, Any]],
) -> Iterator[np.ndarray]:
    expected_header = contract["source_evidence"]["archive_header"]
    with gzip.open(archive_path, "rb") as archive:
        try:
            header = json.loads(archive.readline().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceTexturedDeliveryV2Error("Candidate03 archive header is unreadable") from exc
        _require_equal(header, expected_header, "Candidate03 archive header")
        shape = (int(header["height"]), int(header["width"]), int(header["channels"]))
        frame_bytes = int(header["frame_bytes"])
        _require_equal(frame_bytes, int(np.prod(shape)), "archive frame byte geometry")
        _require_equal(len(frame_hashes), int(header["frame_count"]), "archive frame inventory length")
        previous = np.zeros(shape, dtype=np.uint8)
        for frame_number, expected in enumerate(frame_hashes, start=1):
            payload = _read_exact(archive, frame_bytes)
            if len(payload) != frame_bytes:
                raise SourceTexturedDeliveryV2Error(f"Candidate03 archive frame {frame_number} is truncated")
            delta = np.frombuffer(payload, dtype=np.uint8).reshape(shape)
            frame = np.bitwise_xor(delta, previous)
            _require_equal(expected.get("frame"), frame_number, f"source frame {frame_number} number")
            _require_equal(_raw_frame_hash(frame), expected.get("rgb_sha256"), f"source frame {frame_number} RGB SHA-256")
            yield frame
            previous = frame
        if archive.read(1):
            raise SourceTexturedDeliveryV2Error("Candidate03 archive has trailing decompressed payload")


def preflight(contract: dict[str, Any], ffprobe: Path) -> dict[str, Any]:
    directory, local_manifest_path, archive_path = _source_paths(contract)
    repository_manifest_path = _repo_path(str(contract["locks"]["source_manifest"]["path"]))
    _require_equal(local_manifest_path.read_bytes(), repository_manifest_path.read_bytes(), "local/repository manifest bytes")
    manifest = json.loads(repository_manifest_path.read_text(encoding="utf-8"))
    _require_equal(manifest.get("manifest_version"), 2, "source manifest version")
    _require_equal(manifest.get("development_label"), "candidate-03", "source manifest candidate")
    _require_equal(manifest.get("machine_passed"), True, "source machine result")
    _require_equal(manifest.get("encode_authorized"), False, "pre-receipt manifest encode state")
    _require_equal(manifest.get("gate_count"), 27, "source gate count")
    _require_equal(manifest.get("gates_passed"), 27, "source gates passed")
    _require_equal(manifest.get("gates_failed"), 0, "source gates failed")
    gates = manifest.get("gates", [])
    _require_equal(len(gates), 27, "source gate inventory")
    if not all(gate.get("passed") is True for gate in gates):
        raise SourceTexturedDeliveryV2Error("Candidate03 source manifest contains a failed gate")
    _require_equal(manifest.get("contract", {}).get("raw_sha256"), contract["locks"]["source_contract"]["sha256"], "manifest source contract")
    _require_equal(manifest.get("implementation", {}).get("sha256"), contract["locks"]["source_implementation_archive"]["renderer_sha256"], "manifest executed renderer")
    _require_equal(manifest.get("clock"), {
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
    }, "source manifest clock")
    frame_hashes = manifest.get("frame_hashes", [])
    _require_equal([item.get("frame") for item in frame_hashes], list(range(1, 229)), "ordered source frame inventory")
    source = contract["source_evidence"]
    _require_equal(archive_path.stat().st_size, source["archive_bytes"], "source archive byte count")
    _require_equal(_sha256(archive_path), source["archive_sha256"], "source archive SHA-256")
    _require_equal(manifest["artifacts"]["lossless_frame_archive"]["sha256"], source["archive_sha256"], "manifest archive SHA-256")
    _require_equal(manifest["lossless_archive_header"], source["archive_header"], "manifest archive header")
    review_artifacts = _validate_review_artifacts(manifest, repository_manifest_path)
    _validate_source_implementation_archive(contract)
    _validate_review(contract)
    mix_path = _repo_path(str(contract["locks"]["delivery_mix"]["path"]))
    source_wave_probe = _probe_pcm_wave(mix_path)
    _require_equal(source_wave_probe, {
        "sample_rate": 48000,
        "channels": 2,
        "sample_width": 3,
        "block_align": 6,
        "byte_rate": 288000,
        "data_bytes": 2188800,
        "sample_count": 364800,
    }, "source mix PCM24 geometry")
    source_audio_probe = _probe(mix_path, ffprobe)
    _validate_source_audio_probe(source_audio_probe, contract)
    verified_frames = sum(1 for _ in iter_source_frames(archive_path, contract, frame_hashes))
    _require_equal(verified_frames, 228, "preflight archive frame count")
    return {
        "source_directory": directory,
        "local_manifest_path": local_manifest_path,
        "repository_manifest_path": repository_manifest_path,
        "archive_path": archive_path,
        "mix_path": mix_path,
        "manifest": manifest,
        "frame_hashes": frame_hashes,
        "review_artifacts": review_artifacts,
        "source_wave_probe": source_wave_probe,
        "source_audio_probe": source_audio_probe,
        "verified_frames": verified_frames,
    }


def _capture_declared_state(
    contract: dict[str, Any],
    ffmpeg: Path,
    ffprobe: Path,
) -> dict[str, Any]:
    _, local_manifest, source_archive = _source_paths(contract)
    return {
        "delivery_contract_raw_sha256": _sha256(REPO_ROOT / CONTRACT_RELATIVE_PATH),
        "delivery_contract_canonical_sha256": _canonical_hash(contract),
        "delivery_implementation_sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
        "source_contract_sha256": _sha256(_repo_path(str(contract["locks"]["source_contract"]["path"]))),
        "source_manifest_sha256": _sha256(_repo_path(str(contract["locks"]["source_manifest"]["path"]))),
        "local_source_manifest_sha256": _sha256(local_manifest),
        "source_archive_sha256": _sha256(source_archive),
        "source_implementation_archive_sha256": _sha256(_repo_path(str(contract["locks"]["source_implementation_archive"]["path"]))),
        "visual_review_lf_sha256": _lf_hash(_repo_path(str(contract["locks"]["visual_review"]["path"]))),
        "delivery_mix_sha256": _sha256(_repo_path(str(contract["locks"]["delivery_mix"]["path"]))),
        "opencv_h264_probe_video_sha256": _sha256(_repo_path(str(contract["locks"]["opencv_h264_probe_video"]["path"]))),
        "ffmpeg_sha256": _sha256(ffmpeg),
        "ffprobe_sha256": _sha256(ffprobe),
    }


def _assert_declared_state(state: dict[str, Any], contract: dict[str, Any]) -> None:
    expected = {
        "delivery_contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "source_contract_sha256": contract["locks"]["source_contract"]["sha256"],
        "source_manifest_sha256": contract["locks"]["source_manifest"]["sha256"],
        "local_source_manifest_sha256": contract["locks"]["source_manifest"]["sha256"],
        "source_archive_sha256": contract["source_evidence"]["archive_sha256"],
        "source_implementation_archive_sha256": contract["locks"]["source_implementation_archive"]["sha256"],
        "visual_review_lf_sha256": contract["locks"]["visual_review"]["sha256"],
        "delivery_mix_sha256": contract["locks"]["delivery_mix"]["sha256"],
        "opencv_h264_probe_video_sha256": contract["locks"]["opencv_h264_probe_video"]["sha256"],
    }
    for name, value in expected.items():
        _require_equal(state.get(name), value, f"declared state {name}")


def _capture_state(
    contract: dict[str, Any],
    prepared: dict[str, Any],
    ffmpeg: Path,
    ffprobe: Path,
) -> dict[str, Any]:
    state = _capture_declared_state(contract, ffmpeg, ffprobe)
    state.update({
        "review_artifacts": {
            name: _sha256(prepared["repository_manifest_path"].parent / name)
            for name in sorted(prepared["review_artifacts"])
        },
    })
    _assert_declared_state(state, contract)
    _require_equal(state["review_artifacts"], prepared["review_artifacts"], "captured review artifact hashes")
    return state


def _output_path(contract: dict[str, Any]) -> Path:
    output = _outputs_path(str(contract["delivery"]["output_directory"]))
    expected = (REPO_ROOT / "../../outputs/edit/phase35-candidate03-av-proof-v1").resolve()
    _require_equal(output, expected, "pinned output directory")
    return output


def _claim_attempt(output: Path, state: dict[str, Any]) -> Path:
    claim = output.parent / f".{output.name}.attempt-v1.claim.json"
    payload = {
        "claim_version": 1,
        "attempt_version": 1,
        "state": "claimed_before_encoder_launch",
        "maximum_video_encoder_processes": 1,
        "automatic_retry_allowed": False,
        "captured_inputs": state,
    }
    encoded = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise SourceTexturedDeliveryV2Error(f"the single Candidate03 encode attempt was already claimed: {claim}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def _psnr(first: np.ndarray, second: np.ndarray) -> float:
    mse = float(np.mean((first.astype(np.float32) - second.astype(np.float32)) ** 2))
    if mse <= 1e-12:
        return 99.0
    return float(10.0 * math.log10((255.0 * 255.0) / mse))


def _ssim(first: np.ndarray, second: np.ndarray) -> float:
    a = first.astype(np.float32)
    b = second.astype(np.float32)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    scores: list[float] = []
    for channel in range(3):
        x = a[:, :, channel]
        y = b[:, :, channel]
        mean_x = cv2.GaussianBlur(x, (11, 11), 1.5)
        mean_y = cv2.GaussianBlur(y, (11, 11), 1.5)
        variance_x = cv2.GaussianBlur(x * x, (11, 11), 1.5) - mean_x * mean_x
        variance_y = cv2.GaussianBlur(y * y, (11, 11), 1.5) - mean_y * mean_y
        covariance = cv2.GaussianBlur(x * y, (11, 11), 1.5) - mean_x * mean_y
        numerator = (2.0 * mean_x * mean_y + c1) * (2.0 * covariance + c2)
        denominator = (mean_x * mean_x + mean_y * mean_y + c1) * (variance_x + variance_y + c2)
        scores.append(float(np.mean(numerator / np.maximum(denominator, 1e-12))))
    return float(np.mean(scores))


def _max_8x8_delta(first: np.ndarray, second: np.ndarray) -> float:
    delta = np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(axis=2)
    return float(cv2.boxFilter(delta, -1, (8, 8), normalize=True).max())


def _write_contact_sheet(
    thumbnails: list[Image.Image],
    review_faces: dict[int, Image.Image],
    destination: Path,
) -> None:
    columns = 12
    tile = (160, 90)
    rows = math.ceil(len(thumbnails) / columns)
    review_columns = 8
    review_cell = (220, 250)
    review_rows = math.ceil(len(review_faces) / review_columns)
    width = columns * tile[0]
    review_origin = 34 + rows * tile[1] + 34
    height = review_origin + review_rows * review_cell[1]
    sheet = Image.new("RGB", (width, height), (16, 13, 10))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), "PHASE35 CANDIDATE03 - ALL 228 DECODED A/V PROOF FRAMES", fill=(246, 227, 186))
    for index, thumbnail in enumerate(thumbnails):
        x = (index % columns) * tile[0]
        y = 34 + (index // columns) * tile[1]
        sheet.paste(thumbnail, (x, y))
        draw.rectangle((x + 3, y + 3, x + 52, y + 19), fill=(15, 12, 10))
        draw.text((x + 6, y + 5), f"F{index + 1:03d}", fill=(246, 227, 186))
    draw.rectangle((0, review_origin - 34, width, review_origin), fill=(34, 27, 20))
    draw.text((12, review_origin - 24), "REVIEWED FACE TIMELINE + COMPLETE BLINK TABLES", fill=(246, 227, 186))
    x_origin = (width - review_columns * review_cell[0]) // 2
    for index, (frame_number, face) in enumerate(sorted(review_faces.items())):
        face.thumbnail((review_cell[0] - 12, review_cell[1] - 30), Image.Resampling.LANCZOS)
        x = x_origin + (index % review_columns) * review_cell[0] + 6
        y = review_origin + (index // review_columns) * review_cell[1] + 24
        sheet.paste(face, (x, y))
        draw.text((x, y - 18), f"F{frame_number:03d}", fill=(226, 204, 165))
    sheet.save(destination, format="PNG", optimize=True)


def _decode_video(
    video: Path,
    prepared: dict[str, Any],
    contract: dict[str, Any],
    contact_sheet: Path,
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SourceTexturedDeliveryV2Error("OpenCV could not open the encoded Candidate03 proof")
    face_roi = contract["decoded_gates"]["face_roi_xyxy"]
    x1, y1, x2, y2 = [int(value) for value in face_roi]
    eye_x1, eye_y1, eye_x2, eye_y2 = [int(value) for value in contract["decoded_gates"]["eye_roi_xyxy"]]
    mouth_x1, mouth_y1, mouth_x2, mouth_y2 = [int(value) for value in contract["decoded_gates"]["mouth_roi_xyxy"]]
    frame_count = int(contract["clock"]["frame_count"])
    source_frames = iter_source_frames(prepared["archive_path"], contract, prepared["frame_hashes"])
    full_psnr: list[float] = []
    face_psnr: list[float] = []
    face_ssim: list[float] = []
    eye_psnr: list[float] = []
    mouth_psnr: list[float] = []
    sharpness: list[float] = []
    pairwise: list[dict[str, Any]] = []
    decoded_hashes: list[dict[str, Any]] = []
    thumbnails: list[Image.Image] = []
    review_faces: dict[int, Image.Image] = {}
    review_frame_numbers = set(int(value) for value in contract["review_frames"])
    previous_source_face: np.ndarray | None = None
    previous_decoded_face: np.ndarray | None = None
    decoded_count = 0
    try:
        for frame_number in range(1, frame_count + 1):
            source = next(source_frames)
            ok, bgr = capture.read()
            if not ok:
                raise SourceTexturedDeliveryV2Error(f"encoded proof ended before frame {frame_number}")
            _require_equal(bgr.shape, (1080, 1920, 3), f"decoded frame {frame_number} shape")
            decoded = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            decoded_count += 1
            decoded_hashes.append({"frame": frame_number, "rgb_sha256": _raw_frame_hash(decoded)})
            full_psnr.append(_psnr(source, decoded))
            source_face = source[y1:y2, x1:x2]
            decoded_face = decoded[y1:y2, x1:x2]
            face_psnr.append(_psnr(source_face, decoded_face))
            face_ssim.append(_ssim(source_face, decoded_face))
            eye_psnr.append(_psnr(
                source[eye_y1:eye_y2, eye_x1:eye_x2],
                decoded[eye_y1:eye_y2, eye_x1:eye_x2],
            ))
            mouth_psnr.append(_psnr(
                source[mouth_y1:mouth_y2, mouth_x1:mouth_x2],
                decoded[mouth_y1:mouth_y2, mouth_x1:mouth_x2],
            ))
            gray = cv2.cvtColor(decoded, cv2.COLOR_RGB2GRAY)
            sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            if previous_source_face is not None and previous_decoded_face is not None:
                source_pop = _max_8x8_delta(previous_source_face, source_face)
                decoded_pop = _max_8x8_delta(previous_decoded_face, decoded_face)
                pairwise.append({
                    "frames": [frame_number - 1, frame_number],
                    "source_pop": source_pop,
                    "decoded_pop": decoded_pop,
                    "decoded_minus_source": decoded_pop - source_pop,
                    "absolute_codec_delta": abs(decoded_pop - source_pop),
                })
            previous_source_face = source_face.copy()
            previous_decoded_face = decoded_face.copy()
            image = Image.fromarray(decoded, mode="RGB")
            thumbnail = image.copy()
            thumbnail.thumbnail((160, 90), Image.Resampling.LANCZOS)
            thumbnails.append(thumbnail)
            if frame_number in review_frame_numbers:
                review_faces[frame_number] = image.crop((x1, y1, x2, y2))
        if capture.read()[0]:
            raise SourceTexturedDeliveryV2Error("encoded proof contains more than 228 decoded frames")
        try:
            next(source_frames)
        except StopIteration:
            pass
        else:
            raise SourceTexturedDeliveryV2Error("source archive contains an unexpected extra frame")
    finally:
        capture.release()
    _require_equal(decoded_count, frame_count, "decoded video frame count")
    _require_equal(len(pairwise), frame_count - 1, "decoded temporal pair count")
    _write_contact_sheet(thumbnails, review_faces, contact_sheet)
    maximum_codec = max(item["absolute_codec_delta"] for item in pairwise)
    maximum_item = next(item for item in pairwise if item["absolute_codec_delta"] == maximum_codec)
    return {
        "decoded_frame_count": decoded_count,
        "decoded_rgb24_hashes": decoded_hashes,
        "worst_full_frame_psnr_db": min(full_psnr),
        "worst_full_frame_psnr_frame": full_psnr.index(min(full_psnr)) + 1,
        "worst_face_psnr_db": min(face_psnr),
        "worst_face_psnr_frame": face_psnr.index(min(face_psnr)) + 1,
        "worst_face_ssim": min(face_ssim),
        "worst_face_ssim_frame": face_ssim.index(min(face_ssim)) + 1,
        "worst_eye_psnr_db": min(eye_psnr),
        "worst_eye_psnr_frame": eye_psnr.index(min(eye_psnr)) + 1,
        "worst_mouth_psnr_db": min(mouth_psnr),
        "worst_mouth_psnr_frame": mouth_psnr.index(min(mouth_psnr)) + 1,
        "minimum_decoded_laplacian_variance": min(sharpness),
        "minimum_decoded_laplacian_variance_frame": sharpness.index(min(sharpness)) + 1,
        "pair_count": len(pairwise),
        "maximum_decoded_adjacent_face_8x8_mean_delta": max(item["decoded_pop"] for item in pairwise),
        "maximum_decoded_adjacent_face_8x8_mean_delta_frame_pair": next(
            item["frames"] for item in pairwise
            if item["decoded_pop"] == max(row["decoded_pop"] for row in pairwise)
        ),
        "maximum_absolute_pairwise_codec_delta": maximum_codec,
        "maximum_absolute_pairwise_codec_delta_frame_pair": maximum_item["frames"],
        "pairwise_codec_measurements": pairwise,
        "metric_domain": "maximum 8x8 box-filtered mean absolute RGB delta in [500,185,870,620], decoded pair minus exact source pair",
        "decoded_contact_sheet": {
            "file": contact_sheet.name,
            "sha256": _sha256(contact_sheet),
            "bytes": contact_sheet.stat().st_size,
        },
    }


def _decode_audio_s24(
    path: Path,
    ffmpeg: Path,
    *,
    trim_samples: int | None = None,
) -> tuple[np.ndarray, bytes, list[str]]:
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(path),
        "-map", "0:a:0", "-vn", "-sn", "-dn",
    ]
    if trim_samples is not None:
        command.extend(["-af", f"atrim=start_sample=0:end_sample={trim_samples}"])
    command.extend([
        "-f", "s24le", "-acodec", "pcm_s24le", "-ar", "48000", "-ac", "2", "pipe:1",
    ])
    result = subprocess.run(command, check=True, capture_output=True)
    payload = result.stdout
    if len(payload) % 6:
        raise SourceTexturedDeliveryV2Error(f"decoded audio byte count is not stereo PCM24 aligned: {path.name}")
    octets = np.frombuffer(payload, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
    values = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
    values = np.where(values & 0x800000, values - 0x1000000, values)
    audio = values.astype(np.float64).reshape(-1, 2) / float(1 << 23)
    return audio, payload, command


def _audio_correlation(first: np.ndarray, second: np.ndarray) -> float:
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator <= 0.0:
        raise SourceTexturedDeliveryV2Error("audio correlation metric is degenerate")
    return float(np.vdot(first, second) / denominator)


def _audio_snr(reference: np.ndarray, decoded: np.ndarray) -> float:
    signal = float(np.sum(reference * reference))
    error = float(np.sum((reference - decoded) ** 2))
    if signal <= 0.0 or error <= 0.0:
        raise SourceTexturedDeliveryV2Error("audio signal-to-error metric is degenerate")
    return float(10.0 * math.log10(signal / error))


def _audit_audio(
    video: Path,
    mix: Path,
    ffmpeg: Path,
    probe: dict[str, Any],
    contract: dict[str, Any],
) -> dict[str, Any]:
    expected = int(contract["decoded_gates"]["required_audited_playback_samples_per_channel"])
    source, source_payload, source_command = _decode_audio_s24(mix, ffmpeg)
    decoded, decoded_payload, decoded_command = _decode_audio_s24(
        video, ffmpeg, trim_samples=expected,
    )
    _require_equal(source.shape, (expected, 2), "decoded source mix shape")
    _require_equal(decoded.shape, (expected, 2), "trimmed decoded AAC shape")
    _require_equal(len(source_payload), expected * 6, "decoded source PCM24 bytes")
    _require_equal(len(decoded_payload), expected * 6, "trimmed decoded AAC PCM24 bytes")
    audio_streams = [stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"]
    if len(audio_streams) != 1:
        raise SourceTexturedDeliveryV2Error("AAC packet accounting requires exactly one audio stream")
    audio_stream = audio_streams[0]
    try:
        packet_frames = int(audio_stream.get("nb_read_frames", 0))
        duration_samples = int(audio_stream.get("duration_ts", 0))
    except (TypeError, ValueError) as exc:
        raise SourceTexturedDeliveryV2Error("AAC packet counters are missing or invalid") from exc
    if packet_frames <= 0 or duration_samples <= 0:
        raise SourceTexturedDeliveryV2Error("AAC packet counters must be positive")
    padding = packet_frames * 1024 - duration_samples
    channel_correlation = [
        _audio_correlation(source[:, channel], decoded[:, channel]) for channel in range(2)
    ]
    channel_snr = [
        _audio_snr(source[:, channel], decoded[:, channel]) for channel in range(2)
    ]
    source_mid = (source[:, 0] + source[:, 1]) * 0.5
    decoded_mid = (decoded[:, 0] + decoded[:, 1]) * 0.5
    source_side = (source[:, 0] - source[:, 1]) * 0.5
    decoded_side = (decoded[:, 0] - decoded[:, 1]) * 0.5
    lag_scores: dict[int, float] = {}
    for lag in range(-64, 65):
        if lag < 0:
            reference = source[-lag:]
            candidate = decoded[:lag]
        elif lag > 0:
            reference = source[:-lag]
            candidate = decoded[lag:]
        else:
            reference = source
            candidate = decoded
        lag_scores[lag] = _audio_correlation(reference, candidate)
    best_lag = max(lag_scores, key=lag_scores.get)
    return {
        "source_decoder_command": source_command,
        "encoded_decoder_command": decoded_command,
        "decoder_process_count": 2,
        "source_samples_per_channel": int(source.shape[0]),
        "audited_playback_samples_per_channel": expected,
        "aac_packet_frames": packet_frames,
        "aac_decoder_padding_samples_per_channel": padding,
        "trimmed_decoded_pcm24_bytes": len(decoded_payload),
        "trimmed_decoded_pcm24_sha256": hashlib.sha256(decoded_payload).hexdigest(),
        "channel_zero_lag_correlation": channel_correlation,
        "channel_signal_to_error_db": channel_snr,
        "mid_zero_lag_correlation": _audio_correlation(source_mid, decoded_mid),
        "mid_signal_to_error_db": _audio_snr(source_mid, decoded_mid),
        "side_zero_lag_correlation": _audio_correlation(source_side, decoded_side),
        "side_signal_to_error_db": _audio_snr(source_side, decoded_side),
        "best_correlation_lag_samples": best_lag,
        "best_correlation_lag_score": lag_scores[best_lag],
        "zero_lag_combined_correlation": lag_scores[0],
        "maximum_absolute_sample_error": float(np.max(np.abs(source - decoded))),
    }


def _fraction_equal(value: Any, expected: Fraction) -> bool:
    try:
        return Fraction(str(value)) == expected
    except (ValueError, ZeroDivisionError):
        return False


def _gate(name: str, actual: Any, operator: str, threshold: Any, passed: bool) -> dict[str, Any]:
    return {"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(passed)}


def decoded_gates(
    contract: dict[str, Any],
    probe: dict[str, Any],
    video_metrics: dict[str, Any],
    audio_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    clock = contract["clock"]
    thresholds = contract["decoded_gates"]
    streams = probe.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    others = [stream for stream in streams if stream.get("codec_type") not in {"video", "audio"}]
    video = videos[0] if len(videos) == 1 else {}
    audio = audios[0] if len(audios) == 1 else {}
    try:
        video_frames = int(video.get("nb_frames", 0))
        video_read_frames = int(video.get("nb_read_frames", 0))
        audio_duration_ts = int(audio.get("duration_ts", 0))
        video_duration = float(video.get("duration", "nan"))
        audio_duration = float(audio.get("duration", "nan"))
        format_duration = float(probe.get("format", {}).get("duration", "nan"))
        video_start = float(video.get("start_time", "nan"))
        audio_start = float(audio.get("start_time", "nan"))
        format_start = float(probe.get("format", {}).get("start_time", "nan"))
    except (TypeError, ValueError):
        video_frames = video_read_frames = audio_duration_ts = 0
        video_duration = audio_duration = format_duration = math.nan
        video_start = audio_start = format_start = math.nan
    checks = [
        _gate("one_video_stream", len(videos), "==", 1, len(videos) == 1),
        _gate("one_audio_stream", len(audios), "==", 1, len(audios) == 1),
        _gate("no_other_streams", len(others), "==", 0, len(others) == 0),
        _gate("video_codec_h264", video.get("codec_name"), "==", "h264", video.get("codec_name") == "h264"),
        _gate("video_pixel_format", video.get("pix_fmt"), "==", "yuv420p", video.get("pix_fmt") == "yuv420p"),
        _gate("video_color_range", video.get("color_range"), "==", "tv", video.get("color_range") == "tv"),
        _gate("video_color_space", video.get("color_space"), "==", "bt709", video.get("color_space") == "bt709"),
        _gate("video_color_transfer", video.get("color_transfer"), "==", "bt709", video.get("color_transfer") == "bt709"),
        _gate("video_color_primaries", video.get("color_primaries"), "==", "bt709", video.get("color_primaries") == "bt709"),
        _gate("video_width", video.get("width"), "==", clock["width"], video.get("width") == clock["width"]),
        _gate("video_height", video.get("height"), "==", clock["height"], video.get("height") == clock["height"]),
        _gate("video_reported_frames", video_frames, "==", clock["frame_count"], video_frames == clock["frame_count"]),
        _gate("video_ffprobe_read_frames", video_read_frames, "==", clock["frame_count"], video_read_frames == clock["frame_count"]),
        _gate("video_opencv_decoded_frames", video_metrics["decoded_frame_count"], "==", clock["frame_count"], video_metrics["decoded_frame_count"] == clock["frame_count"]),
        _gate("video_r_frame_rate", video.get("r_frame_rate"), "==", "30/1", _fraction_equal(video.get("r_frame_rate"), Fraction(30, 1))),
        _gate("video_avg_frame_rate", video.get("avg_frame_rate"), "==", "30/1", _fraction_equal(video.get("avg_frame_rate"), Fraction(30, 1))),
        _gate("video_start_time", video_start, "==", 0.0, math.isfinite(video_start) and abs(video_start) <= 1e-6),
        _gate("video_duration", video_duration, "==", 7.6, math.isfinite(video_duration) and abs(video_duration - 7.6) <= 1e-6),
        _gate("audio_codec_aac", audio.get("codec_name"), "==", "aac", audio.get("codec_name") == "aac"),
        _gate("audio_profile_lc", audio.get("profile"), "==", "LC", audio.get("profile") == "LC"),
        _gate("audio_sample_rate", int(audio.get("sample_rate", 0) or 0), "==", 48000, int(audio.get("sample_rate", 0) or 0) == 48000),
        _gate("audio_channels", audio.get("channels"), "==", 2, audio.get("channels") == 2),
        _gate("audio_time_base", audio.get("time_base"), "==", "1/48000", _fraction_equal(audio.get("time_base"), Fraction(1, 48000))),
        _gate("audio_start_time", audio_start, "==", 0.0, math.isfinite(audio_start) and abs(audio_start) <= 1e-6),
        _gate("audio_container_duration_samples", audio_duration_ts, "==", thresholds["required_container_audio_duration_samples"], audio_duration_ts == thresholds["required_container_audio_duration_samples"]),
        _gate("audio_duration", audio_duration, "==", 7.6, math.isfinite(audio_duration) and abs(audio_duration - 7.6) <= 1e-6),
        _gate("container_start_time", format_start, "==", 0.0, math.isfinite(format_start) and abs(format_start) <= 1e-6),
        _gate("container_duration", format_duration, "==", 7.6, math.isfinite(format_duration) and abs(format_duration - 7.6) <= 1e-6),
        _gate("full_frame_psnr", video_metrics["worst_full_frame_psnr_db"], ">=", thresholds["minimum_full_frame_psnr_db_all_frames"], video_metrics["worst_full_frame_psnr_db"] >= thresholds["minimum_full_frame_psnr_db_all_frames"]),
        _gate("face_psnr", video_metrics["worst_face_psnr_db"], ">=", thresholds["minimum_face_psnr_db_all_frames"], video_metrics["worst_face_psnr_db"] >= thresholds["minimum_face_psnr_db_all_frames"]),
        _gate("face_ssim", video_metrics["worst_face_ssim"], ">=", thresholds["minimum_face_ssim_all_frames"], video_metrics["worst_face_ssim"] >= thresholds["minimum_face_ssim_all_frames"]),
        _gate("eye_psnr", video_metrics["worst_eye_psnr_db"], ">=", thresholds["minimum_eye_psnr_db_all_frames"], video_metrics["worst_eye_psnr_db"] >= thresholds["minimum_eye_psnr_db_all_frames"]),
        _gate("mouth_psnr", video_metrics["worst_mouth_psnr_db"], ">=", thresholds["minimum_mouth_psnr_db_all_frames"], video_metrics["worst_mouth_psnr_db"] >= thresholds["minimum_mouth_psnr_db_all_frames"]),
        _gate("decoded_sharpness", video_metrics["minimum_decoded_laplacian_variance"], ">=", thresholds["minimum_decoded_laplacian_variance_all_frames"], video_metrics["minimum_decoded_laplacian_variance"] >= thresholds["minimum_decoded_laplacian_variance_all_frames"]),
        _gate("decoded_adjacent_face_delta", video_metrics["maximum_decoded_adjacent_face_8x8_mean_delta"], "<=", thresholds["maximum_decoded_adjacent_face_8x8_mean_delta"], video_metrics["maximum_decoded_adjacent_face_8x8_mean_delta"] <= thresholds["maximum_decoded_adjacent_face_8x8_mean_delta"]),
        _gate("same_domain_pairwise_codec_delta", video_metrics["maximum_absolute_pairwise_codec_delta"], "<=", thresholds["maximum_absolute_pairwise_codec_delta"], video_metrics["maximum_absolute_pairwise_codec_delta"] <= thresholds["maximum_absolute_pairwise_codec_delta"]),
        _gate("all_temporal_pairs_evaluated", video_metrics["pair_count"], "==", 227, video_metrics["pair_count"] == 227),
        _gate("audio_playback_sample_clock", audio_metrics["audited_playback_samples_per_channel"], "==", thresholds["required_audited_playback_samples_per_channel"], audio_metrics["audited_playback_samples_per_channel"] == thresholds["required_audited_playback_samples_per_channel"]),
        _gate("aac_packet_frames_present", audio_metrics["aac_packet_frames"], ">", 0, audio_metrics["aac_packet_frames"] > 0),
        _gate("aac_decoder_padding", audio_metrics["aac_decoder_padding_samples_per_channel"], "<=", thresholds["maximum_aac_decoder_padding_samples_per_channel"], 0 <= audio_metrics["aac_decoder_padding_samples_per_channel"] <= thresholds["maximum_aac_decoder_padding_samples_per_channel"]),
        _gate("audio_channel_correlation", min(audio_metrics["channel_zero_lag_correlation"]), ">=", thresholds["minimum_audio_channel_zero_lag_correlation"], min(audio_metrics["channel_zero_lag_correlation"]) >= thresholds["minimum_audio_channel_zero_lag_correlation"]),
        _gate("audio_channel_signal_to_error", min(audio_metrics["channel_signal_to_error_db"]), ">=", thresholds["minimum_audio_channel_signal_to_error_db"], min(audio_metrics["channel_signal_to_error_db"]) >= thresholds["minimum_audio_channel_signal_to_error_db"]),
        _gate("audio_mid_correlation", audio_metrics["mid_zero_lag_correlation"], ">=", thresholds["minimum_audio_mid_zero_lag_correlation"], audio_metrics["mid_zero_lag_correlation"] >= thresholds["minimum_audio_mid_zero_lag_correlation"]),
        _gate("audio_side_correlation", audio_metrics["side_zero_lag_correlation"], ">=", thresholds["minimum_audio_side_zero_lag_correlation"], audio_metrics["side_zero_lag_correlation"] >= thresholds["minimum_audio_side_zero_lag_correlation"]),
        _gate("audio_side_signal_to_error", audio_metrics["side_signal_to_error_db"], ">=", thresholds["minimum_audio_side_signal_to_error_db"], audio_metrics["side_signal_to_error_db"] >= thresholds["minimum_audio_side_signal_to_error_db"]),
        _gate("audio_best_correlation_lag", audio_metrics["best_correlation_lag_samples"], "==", thresholds["required_audio_best_correlation_lag_samples"], audio_metrics["best_correlation_lag_samples"] == thresholds["required_audio_best_correlation_lag_samples"]),
    ]
    return checks


def _preserve_rejected(
    stage: Path,
    rejected: Path,
    error: BaseException,
    encoder_started: bool,
    attempt_context: dict[str, Any],
) -> None:
    if not stage.exists():
        return
    failure = {
        "status": "single_candidate03_encode_rejected_no_retry_allowed",
        "encoder_process_started": encoder_started,
        "error_type": type(error).__name__,
        "error": str(error),
        "attempt": attempt_context,
        "available_artifacts": [
            {"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in sorted(stage.iterdir()) if path.is_file()
        ],
    }
    (stage / "failure-v1.json").write_text(json.dumps(failure, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if rejected.exists():
        raise SourceTexturedDeliveryV2Error(f"cannot preserve rejected attempt because immutable path exists: {rejected}") from error
    stage.rename(rejected)


def _validate_report(report_path: Path, stage: Path, claim: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("machine_passed") is not True or report.get("accepted_full_cartoon_production_delivery") is not False:
        raise SourceTexturedDeliveryV2Error("Candidate03 delivery report acceptance state is invalid")
    if report.get("video", {}).get("encoding_process_count") != 1:
        raise SourceTexturedDeliveryV2Error("Candidate03 report does not prove exactly one encoder process")
    if report.get("gates_failed") != 0 or report.get("gates_passed") != report.get("gate_count"):
        raise SourceTexturedDeliveryV2Error("Candidate03 delivery report contains failed gates")
    preencode_gates = report.get("source", {}).get("preencode_gates", [])
    decoded_gate_inventory = report.get("decoded_gates", [])
    all_gates = preencode_gates + decoded_gate_inventory
    if len(preencode_gates) != 27 or len(all_gates) != report.get("gate_count"):
        raise SourceTexturedDeliveryV2Error("Candidate03 delivery report gate inventory is incomplete")
    gate_names = [gate.get("name") for gate in all_gates]
    if len(set(gate_names)) != len(gate_names) or not all(gate.get("passed") is True for gate in all_gates):
        raise SourceTexturedDeliveryV2Error("Candidate03 delivery report gates are duplicated or failed")
    if report.get("probe_canonical_sha256") != _canonical_hash(report.get("probe", {})):
        raise SourceTexturedDeliveryV2Error("Candidate03 delivery probe hash is invalid")
    if report.get("source", {}).get("manifest_sha256") != "250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe":
        raise SourceTexturedDeliveryV2Error("Candidate03 delivery report source manifest binding is invalid")
    if report.get("source", {}).get("archive_sha256") != "b5908bfce4ac10ad7e3ad74e58a8cf9f8e352033b14c1828315e96cd615f6e0f":
        raise SourceTexturedDeliveryV2Error("Candidate03 delivery report source archive binding is invalid")
    source_hashes = report.get("source", {}).get("frame_hashes", [])
    decoded_hashes = report.get("decoded_video", {}).get("decoded_rgb24_hashes", [])
    if [item.get("frame") for item in source_hashes] != list(range(1, 229)):
        raise SourceTexturedDeliveryV2Error("Candidate03 report source frame inventory is incomplete")
    if [item.get("frame") for item in decoded_hashes] != list(range(1, 229)):
        raise SourceTexturedDeliveryV2Error("Candidate03 report decoded frame inventory is incomplete")
    references = [report["video"], report["decoded_video"]["decoded_contact_sheet"]]
    for reference in references:
        artifact = stage / str(reference["file"])
        if not artifact.is_file() or _sha256(artifact) != reference["sha256"]:
            raise SourceTexturedDeliveryV2Error(f"Candidate03 delivery artifact integrity failed: {artifact.name}")
    stderr = report["encoder_stderr"]
    stderr_path = stage / str(stderr["file"])
    if not stderr_path.is_file() or _sha256(stderr_path) != stderr["sha256"]:
        raise SourceTexturedDeliveryV2Error("Candidate03 encoder stderr integrity failed")
    if not claim.is_file() or _sha256(claim) != report.get("attempt_claim", {}).get("sha256"):
        raise SourceTexturedDeliveryV2Error("Candidate03 attempt claim integrity failed")


def render_authorized_proof(*, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    contract = load_contract()
    ffmpeg_path = _resolved_tool(ffmpeg)
    ffprobe_path = _resolved_tool(ffprobe)
    output = _output_path(contract)
    rejected = output.with_name(output.name + "-rejected-attempt-v1")
    claim_path = output.parent / f".{output.name}.attempt-v1.claim.json"
    for immutable in (output, rejected, claim_path):
        if immutable.exists():
            raise SourceTexturedDeliveryV2Error(f"immutable Candidate03 delivery state already exists: {immutable}")
    output.parent.mkdir(parents=True, exist_ok=True)
    old_partial = next(iter(output.parent.glob(f".{output.name}.partial-*")), None)
    if old_partial is not None:
        raise SourceTexturedDeliveryV2Error(f"an earlier Candidate03 partial state exists: {old_partial}")

    initial_declared_state = _capture_declared_state(contract, ffmpeg_path, ffprobe_path)
    _assert_declared_state(initial_declared_state, contract)
    toolchain_validation = _validate_toolchain(ffmpeg_path, ffprobe_path, contract)
    post_toolchain_declared_state = _capture_declared_state(contract, ffmpeg_path, ffprobe_path)
    _assert_declared_state(post_toolchain_declared_state, contract)
    _require_equal(post_toolchain_declared_state, initial_declared_state, "toolchain validation fixed input state")
    free_bytes = shutil.disk_usage(output.parent).free
    minimum_free = int(contract["preclaim_requirements"]["minimum_free_output_bytes"])
    if free_bytes < minimum_free:
        raise SourceTexturedDeliveryV2Error(
            f"insufficient free space before single encode: {free_bytes} < {minimum_free}"
        )
    prepared = preflight(contract, ffprobe_path)
    post_preflight_declared_state = _capture_declared_state(contract, ffmpeg_path, ffprobe_path)
    _assert_declared_state(post_preflight_declared_state, contract)
    _require_equal(post_preflight_declared_state, initial_declared_state, "preflight fixed input state")
    captured_state = _capture_state(contract, prepared, ffmpeg_path, ffprobe_path)
    _require_equal(
        {name: captured_state[name] for name in initial_declared_state},
        initial_declared_state,
        "captured declared input state",
    )
    _require_equal(_capture_state(contract, prepared, ffmpeg_path, ffprobe_path), captured_state, "pre-claim fixed input state")
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    process: subprocess.Popen[bytes] | None = None
    encoder_started = False
    claim_created = False
    encode_count = 0
    command: list[str] = []
    attempt_context: dict[str, Any] = {
        "captured_state": captured_state,
        "encoder_command": command,
        "encoding_process_count": encode_count,
        "encoder_return_code": None,
    }
    try:
        claim = _claim_attempt(output, captured_state)
        claim_created = True
        _require_equal(_capture_state(contract, prepared, ffmpeg_path, ffprobe_path), captured_state, "post-claim fixed input state")
        delivery = contract["delivery"]
        encoding = delivery["encoding"]
        video = stage / str(delivery["video_filename"])
        partial_video = stage / f"{video.stem}.partial.mp4"
        command = [
            str(ffmpeg_path), "-hide_banner", "-loglevel", "error", "-xerror",
            "-abort_on", "empty_output+empty_output_stream",
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "1920x1080",
            "-framerate", "30", "-i", "pipe:0", "-i", str(prepared["mix_path"]),
            "-map", "0:v:0", "-map", "1:a:0", "-map_metadata", "-1", "-map_chapters", "-1",
            "-sn", "-dn", "-frames:v", "228",
            "-c:v", str(encoding["video_codec"]), "-preset", str(encoding["preset"]),
            "-tune", str(encoding["tune"]), "-crf", str(encoding["crf"]),
            "-pix_fmt", str(encoding["pixel_format"]), "-fps_mode", "cfr",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-color_range", "tv",
            "-c:a", str(encoding["audio_codec"]), "-b:a", str(encoding["audio_bitrate"]),
            "-profile:a", "aac_low", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
            "-n", str(partial_video),
        ]
        attempt_context["encoder_command"] = command
        stderr_path = stage / "ffmpeg-stderr-v1.txt"
        frames_written = 0
        bytes_written = 0
        with stderr_path.open("wb") as stderr_handle:
            process = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr_handle,
            )
            encoder_started = True
            encode_count = 1
            attempt_context["encoding_process_count"] = encode_count
            if process.stdin is None:
                raise SourceTexturedDeliveryV2Error("ffmpeg raw-video pipe was not created")
            for frame in iter_source_frames(prepared["archive_path"], contract, prepared["frame_hashes"]):
                payload = np.ascontiguousarray(frame).tobytes()
                _require_equal(len(payload), 6220800, f"encoder frame {frames_written + 1} byte count")
                written = process.stdin.write(payload)
                _require_equal(written, len(payload), f"encoder frame {frames_written + 1} pipe write")
                frames_written += 1
                bytes_written += len(payload)
            process.stdin.close()
            return_code = process.wait()
            attempt_context["encoder_return_code"] = return_code
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        _require_equal(frames_written, 228, "encoder source frame count")
        _require_equal(bytes_written, 228 * 6220800, "encoder source byte count")
        if return_code != 0:
            raise SourceTexturedDeliveryV2Error(f"single ffmpeg encode failed with exit {return_code}: {stderr_text.strip()}")
        if not partial_video.is_file() or partial_video.stat().st_size == 0:
            raise SourceTexturedDeliveryV2Error("single ffmpeg encode produced no video")
        os.replace(partial_video, video)

        _require_equal(_capture_state(contract, prepared, ffmpeg_path, ffprobe_path), captured_state, "post-encode fixed input state")
        probe = _probe(video, ffprobe_path)
        contact_sheet = stage / str(delivery["decoded_contact_sheet_filename"])
        video_metrics = _decode_video(video, prepared, contract, contact_sheet)
        audio_metrics = _audit_audio(video, prepared["mix_path"], ffmpeg_path, probe, contract)
        gates = decoded_gates(contract, probe, video_metrics, audio_metrics)
        preencode_gates = prepared["manifest"]["gates"]
        all_gates = preencode_gates + gates
        machine_passed = all(gate["passed"] is True for gate in all_gates)
        report = {
            "report_version": 1,
            "status": "machine_av_successor_audit_passed_real_time_review_required" if machine_passed else "machine_av_successor_audit_failed_no_retry_allowed",
            "machine_passed": machine_passed,
            "accepted_full_cartoon_production_delivery": False,
            "real_time_human_motion_and_audio_review_required": True,
            "scope": "one exact Phase35 Candidate03 7.6-second A/V proof encode",
            "authorization_consumed": True,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": captured_state["delivery_contract_raw_sha256"],
                "canonical_sha256": captured_state["delivery_contract_canonical_sha256"],
            },
            "delivery_implementation": {
                "path": IMPLEMENTATION_RELATIVE_PATH,
                "sha256": captured_state["delivery_implementation_sha256"],
            },
            "source": {
                "manifest": str(contract["locks"]["source_manifest"]["path"]),
                "manifest_sha256": captured_state["source_manifest_sha256"],
                "archive": str(prepared["archive_path"]),
                "archive_sha256": captured_state["source_archive_sha256"],
                "executed_renderer_sha256": contract["locks"]["source_implementation_archive"]["renderer_sha256"],
                "frame_hashes": prepared["frame_hashes"],
                "preencode_gates": preencode_gates,
            },
            "visual_review": {
                "path": contract["locks"]["visual_review"]["path"],
                "lf_normalized_sha256": captured_state["visual_review_lf_sha256"],
                "verdict": contract["authorization"]["required_verdict"],
            },
            "audio_source": {
                "path": contract["locks"]["delivery_mix"]["path"],
                "sha256": captured_state["delivery_mix_sha256"],
                "wave_probe": prepared["source_wave_probe"],
                "probe": prepared["source_audio_probe"],
            },
            "attempt_claim": {"file": claim.name, "sha256": _sha256(claim)},
            "toolchain": {
                "ffmpeg": {"path": str(ffmpeg_path), "sha256": captured_state["ffmpeg_sha256"]},
                "ffprobe": {"path": str(ffprobe_path), "sha256": captured_state["ffprobe_sha256"]},
                "preclaim_validation": toolchain_validation,
                "free_output_bytes_before_claim": free_bytes,
                "opencv": cv2.__version__,
                "numpy": np.__version__,
            },
            "encoder_command": command,
            "encoder_stderr": {"file": stderr_path.name, "sha256": _sha256(stderr_path), "text": stderr_text},
            "video": {
                "file": video.name,
                "sha256": _sha256(video),
                "bytes": video.stat().st_size,
                "encoding_process_count": encode_count,
                "source_frames_written": frames_written,
                "source_bytes_written": bytes_written,
            },
            "probe": probe,
            "probe_canonical_sha256": _canonical_hash(probe),
            "decoded_video": video_metrics,
            "decoded_audio": audio_metrics,
            "decoded_gates": gates,
            "gate_count": len(all_gates),
            "gates_passed": sum(1 for gate in all_gates if gate["passed"]),
            "gates_failed": sum(1 for gate in all_gates if not gate["passed"]),
            "constraints": {
                "renderer_invoked": False,
                "source_was_exact_reviewed_archive": True,
                "audio_was_exact_locked_mix": True,
                "automatic_retry_used": False,
                "video_encoder_processes": encode_count,
                "audio_decoder_processes": audio_metrics["decoder_process_count"],
                "network_used": False,
                "paid_service_or_api_used": False,
                "production_promotion_granted": False,
            },
        }
        report_path = stage / str(delivery["report_filename"])
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if not machine_passed:
            failed = [gate["name"] for gate in gates if not gate["passed"]]
            raise SourceTexturedDeliveryV2Error(f"decoded Candidate03 A/V gates failed: {failed}")
        _validate_report(report_path, stage, claim)
        _require_equal(_capture_state(contract, prepared, ffmpeg_path, ffprobe_path), captured_state, "pre-publication fixed input state")
        if output.exists():
            raise SourceTexturedDeliveryV2Error(f"immutable output appeared before publication: {output}")
        stage.rename(output)
        return {
            "output_directory": str(output),
            "video": str(output / video.name),
            "video_sha256": report["video"]["sha256"],
            "report": str(output / report_path.name),
            "decoded_contact_sheet": str(output / contact_sheet.name),
            "machine_passed": True,
            "real_time_human_review_required": True,
            "encoding_process_count": encode_count,
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
            except BaseException:
                pass
            try:
                process.wait(timeout=10)
            except BaseException:
                pass
        if process is not None:
            attempt_context["encoder_return_code"] = process.poll()
        if claim_created:
            _preserve_rejected(stage, rejected, exc, encoder_started, attempt_context)
        elif stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Encode and audit the one authorized Phase35 Candidate03 A/V proof.")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    print(json.dumps(render_authorized_proof(ffmpeg=args.ffmpeg, ffprobe=args.ffprobe), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
