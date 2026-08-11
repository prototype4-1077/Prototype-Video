"""Read-only human-review evidence harness for a future reauthorized Phase36 MOV.

This module never renders or creates a compressed media stream. FFmpeg is used only
to decode the complete video to raw RGB on stdout and the complete audio to raw
PCM24 on stdout. The source MOV is hash/stat checked before and after inspection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any, BinaryIO, Iterator

import numpy as np
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_ROOT = (REPO_ROOT / "../../outputs").resolve()
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase36_master_review_harness_v1.json"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "7619ae2abef87ed95f278f9e430485acb56bc7df9b40763089ea996bcf2e858e"


class ReviewHarnessError(RuntimeError):
    pass


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ReviewHarnessError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _strict_json_loads(payload: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ReviewHarnessError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise ReviewHarnessError(f"{label} contains non-finite value {value}")

    value = json.loads(payload, object_pairs_hook=pairs, parse_constant=reject)
    if not isinstance(value, dict):
        raise ReviewHarnessError(f"{label} must be a JSON object")
    return value


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _outputs_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(OUTPUTS_ROOT)
    except ValueError as exc:
        raise ReviewHarnessError(f"path escapes the outputs root: {path}") from exc
    return path


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned harness contract path")
    contract = _strict_json_loads(resolved.read_bytes(), "review harness contract")
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "harness contract canonical SHA-256")
    _require_equal(contract["contract_version"], 1, "harness contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase36_master_review_harness_v1", "harness contract id")
    for key, expected in {
        "cash_cost": 0,
        "paid_runtime_dependency": False,
        "network_runtime_required": False,
        "source_mutation_allowed": False,
        "video_encoder_allowed": False,
    }.items():
        _require_equal(contract[key], expected, f"harness policy {key}")
    binding = contract["binding_policy"]
    _require_equal(binding["binding_version"], 1, "binding version")
    _require_equal(binding["required_binding_status"], "FUTURE_REAUTHORIZED_MASTER_COMPLETED", "binding status")
    _require_equal(binding["candidate02_or_f91_lineage_allowed"], False, "revoked lineage policy")
    _require_equal(binding["required_supersedes_revoked_candidate02_master"], True, "revocation supersession policy")
    clock = contract["clock"]
    _require_equal(
        {key: clock[key] for key in ("width", "height", "fps", "frame_count", "audio_sample_rate", "audio_channels", "audio_bits_per_sample", "audio_sample_count")},
        {"width": 1920, "height": 1080, "fps": 30, "frame_count": 303, "audio_sample_rate": 48000, "audio_channels": 2, "audio_bits_per_sample": 24, "audio_sample_count": 484800},
        "review clock",
    )
    review = contract["review_frames"]
    _require_equal([item["frame"] for item in review["cuts"]], [75, 76, 237, 238], "cut review frames")
    _require_equal([item["frame"] for item in review["f240_f256"]], list(range(240, 257)), "F240-F256 review span")
    _require_equal([item["frame"] for item in review["blink"]], list(range(244, 253)), "blink review frames")
    _require_equal([item["viseme"] for item in review["viseme"]], list("GBCHA EFX".replace(" ", "")), "viseme labels")
    _require_equal([item["frame"] for item in review["viseme"]], [101, 112, 126, 136, 142, 150, 173, 201], "viseme review frames")
    segment = contract["audio_segment"]
    _require_equal(segment["start_sample"], round(segment["start_seconds"] * clock["audio_sample_rate"]), "segment start sample")
    _require_equal(segment["end_sample"], round(segment["end_seconds"] * clock["audio_sample_rate"]), "segment end sample")
    _require_equal(segment["sample_frames"], segment["end_sample"] - segment["start_sample"], "segment sample frames")
    _require_equal(segment["pcm_bytes"], segment["sample_frames"] * clock["audio_channels"] * 3, "segment PCM bytes")
    return contract


def _load_binding(path: str | Path, expected_sha256: str, contract: dict[str, Any]) -> dict[str, Any]:
    if not _is_sha256(expected_sha256):
        raise ReviewHarnessError("binding SHA-256 must be an exact lowercase hexadecimal digest")
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ReviewHarnessError(f"future master binding is absent: {resolved}")
    _require_equal(_sha256(resolved), expected_sha256, "future master binding SHA-256")
    binding = _strict_json_loads(resolved.read_bytes(), "future master binding")
    policy = contract["binding_policy"]
    _require_equal(binding["binding_version"], policy["binding_version"], "future binding version")
    _require_equal(binding["status"], policy["required_binding_status"], "future binding status")
    _require_equal(binding["supersedes_revoked_candidate02_master"], True, "future binding revocation supersession")
    _require_equal(binding["revoked_candidate02_or_f91_artifact_used"], False, "future binding revoked artifact policy")
    if not isinstance(binding.get("attempt_id"), str) or not binding["attempt_id"]:
        raise ReviewHarnessError("future binding has no attempt id")
    if not isinstance(binding.get("claim_filename"), str) or Path(binding["claim_filename"]).name != binding["claim_filename"]:
        raise ReviewHarnessError("future binding claim filename must be one basename")
    if not isinstance(binding.get("master_directory"), str):
        raise ReviewHarnessError("future binding has no master directory")
    _outputs_path(binding["master_directory"])
    for field in policy["required_hash_fields"]:
        if not _is_sha256(binding.get(field)):
            raise ReviewHarnessError(f"future binding field {field!r} is not an exact SHA-256")
    revoked = contract["revoked_inputs"]
    if binding["audio_wav_sha256"] == revoked["candidate02_audio_wav_sha256"]:
        raise ReviewHarnessError("future binding still uses the revoked Candidate02 audio WAV")
    if binding["audio_pcm_sha256"] == revoked["candidate02_audio_pcm_sha256"]:
        raise ReviewHarnessError("future binding still uses the revoked Candidate02 PCM payload")
    return binding


def _input_paths(binding: dict[str, Any], contract: dict[str, Any]) -> dict[str, Path]:
    root = _outputs_path(binding["master_directory"])
    required = contract["master_requirements"]
    return {
        "root": root,
        "report": root / required["report_filename"],
        "package": root / required["package_filename"],
        "media": root / required["media_filename"],
        "claim": root / binding["claim_filename"],
    }


def _verify_master_evidence(binding: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    paths = _input_paths(binding, contract)
    for name, path in paths.items():
        if name != "root" and not path.is_file():
            raise ReviewHarnessError(f"verified master {name} is absent: {path}")
    root = paths["root"]
    report = _strict_json_loads(paths["report"].read_bytes(), "future master report")
    package = _strict_json_loads(paths["package"].read_bytes(), "future master package")
    for name in ("report", "package", "media", "claim"):
        _require_equal(_sha256(paths[name]), binding[f"{name}_sha256"], f"future master {name} SHA-256")

    required = contract["master_requirements"]
    _require_equal(report["attempt_id"], binding["attempt_id"], "future master attempt id")
    _require_equal(report["status"], required["required_status"], "future master report status")
    _require_equal(report["machine_passed"], True, "future master machine result")
    _require_equal(report["authorization_consumed"], True, "future master authorization consumption")
    _require_equal(report["encoder"]["process_count"], required["required_encoder_processes"], "future master encoder count")
    _require_equal(report["encoder"]["return_code"], 0, "future master encoder return code")
    _require_equal(report["encoder"]["command_template_sha256"], binding["command_template_sha256"], "future master report command hash")
    _require_equal(report["media"]["file"], required["media_filename"], "future master media filename")
    _require_equal(report["media"]["sha256"], binding["media_sha256"], "future master report media hash")
    _require_equal(report["media"]["bytes"], paths["media"].stat().st_size, "future master report media bytes")
    _require_equal(report["gates_failed"], 0, "future master failed gate count")
    _require_equal(report["failed_gates"], [], "future master failed gates")
    _require_equal(all(item["passed"] for item in report["gates"]), True, "future master individual gates")
    disposition = report["disposition"]
    _require_equal(disposition["human_native_size_review_required"], True, "future master human review requirement")
    for field in ("promotion_allowed", "distribution_encode_allowed", "retry_allowed"):
        _require_equal(disposition[field], False, f"future master disposition {field}")

    captured = report["captured_state"]
    for field in ("authorization_subject_sha256", "implementation_sha256", "command_template_sha256", "picture_archive_sha256", "ffmpeg_sha256", "ffprobe_sha256"):
        _require_equal(captured[field], binding[field], f"future master captured {field}")
    _require_equal(captured["authorization"]["sha256"], binding["authorization_receipt_sha256"], "future master authorization receipt")
    _require_equal(captured["vui_result"]["sha256"], binding["vui_report_sha256"], "future master VUI result")
    _require_equal(binding["audio_wav_sha256"] in captured["locks"].values(), True, "future master captured audio WAV")
    _require_equal(report["sources"]["audio"]["data_sha256"], binding["audio_pcm_sha256"], "future master source PCM hash")

    _require_equal(package["package_version"], 1, "future master package version")
    _require_equal(package["attempt_id"], binding["attempt_id"], "future master package attempt id")
    _require_equal(package["machine_passed"], True, "future master package result")
    _require_equal(package["disposition"], disposition, "future master package disposition")
    artifacts = package["artifacts"]
    names = [item["file"] for item in artifacts]
    _require_equal(names, sorted(names), "future master package artifact order")
    _require_equal(len(names), len(set(names)), "future master package unique artifacts")
    for required_name in (paths["report"].name, paths["media"].name, paths["claim"].name):
        if required_name not in names:
            raise ReviewHarnessError(f"future master package omits {required_name}")
    _require_equal({path.name for path in root.iterdir() if path.is_file()}, set(names) | {paths["package"].name}, "future master directory inventory")
    for artifact in artifacts:
        artifact_path = root / artifact["file"]
        if artifact_path.parent != root or not artifact_path.is_file():
            raise ReviewHarnessError(f"future master package has unsafe artifact path {artifact['file']!r}")
        _require_equal(artifact_path.stat().st_size, artifact["bytes"], f"future master artifact bytes {artifact_path.name}")
        _require_equal(_sha256(artifact_path), artifact["sha256"], f"future master artifact hash {artifact_path.name}")
    return {"paths": paths, "report": report, "package": package}


def _resolved_tool(executable: str) -> Path:
    located = shutil.which(executable)
    if located is None:
        candidate = Path(executable).resolve()
        if not candidate.is_file():
            raise ReviewHarnessError(f"required executable is absent: {executable}")
        located = str(candidate)
    return Path(located).resolve()


def _validate_tools(ffmpeg: Path, ffprobe: Path, binding: dict[str, Any]) -> None:
    _require_equal(_sha256(ffmpeg), binding["ffmpeg_sha256"], "inspection FFmpeg SHA-256")
    _require_equal(_sha256(ffprobe), binding["ffprobe_sha256"], "inspection FFprobe SHA-256")


def _ffprobe_command(ffprobe: Path, media: Path) -> list[str]:
    return [str(ffprobe), "-v", "error", "-show_streams", "-show_format", "-show_frames", "-of", "json", str(media)]


def _video_decode_command(ffmpeg: Path, media: Path) -> list[str]:
    return [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(media), "-map", "0:v:0", "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]


def _audio_decode_command(ffmpeg: Path, media: Path) -> list[str]:
    return [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(media), "-map", "0:a:0", "-vn", "-f", "s24le", "-acodec", "pcm_s24le", "-ar", "48000", "-ac", "2", "pipe:1"]


def _run_ffprobe(ffprobe: Path, media: Path, stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    command = _ffprobe_command(ffprobe, media)
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        result = subprocess.run(command, stdout=stdout, stderr=stderr, check=False)
    if result.returncode != 0:
        raise ReviewHarnessError(f"ffprobe failed with exit {result.returncode}")
    return _strict_json_loads(stdout_path.read_bytes(), "full ffprobe audit")


def _frame_duration(frame: dict[str, Any]) -> int:
    value = frame.get("duration", frame.get("pkt_duration"))
    if value is None:
        raise ReviewHarnessError("decoded frame has no duration")
    return int(value)


def _audit_pts(probe: dict[str, Any], contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    clock = contract["clock"]
    requirements = contract["master_requirements"]
    streams = probe.get("streams", [])
    video_streams = [item for item in streams if item.get("codec_type") == "video"]
    audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
    _require_equal((len(video_streams), len(audio_streams), len(streams)), (1, 1, 2), "master stream inventory")
    video, audio = video_streams[0], audio_streams[0]
    _require_equal(video.get("codec_name"), requirements["required_video_codec"], "master video codec")
    _require_equal(video.get("codec_tag_string"), requirements["required_video_tag"], "master video tag")
    _require_equal(video.get("pix_fmt"), requirements["required_decoded_pixel_format"], "master decoded pixel format")
    _require_equal((int(video.get("width", 0)), int(video.get("height", 0))), (clock["width"], clock["height"]), "master video geometry")
    _require_equal(video.get("time_base"), clock["video_time_base"], "master video time base")
    _require_equal(Fraction(video.get("avg_frame_rate", "0/1")), Fraction(clock["fps"], 1), "master average frame rate")
    _require_equal(audio.get("codec_name"), requirements["required_audio_codec"], "master audio codec")
    _require_equal(audio.get("time_base"), clock["audio_time_base"], "master audio time base")
    _require_equal((int(audio.get("sample_rate", 0)), int(audio.get("channels", 0))), (clock["audio_sample_rate"], clock["audio_channels"]), "master audio geometry")

    frames = probe.get("frames", [])
    video_frames = [item for item in frames if item.get("media_type") == "video"]
    audio_frames = [item for item in frames if item.get("media_type") == "audio"]
    _require_equal(len(video_frames), clock["frame_count"], "full video PTS frame count")
    expected_video_pts = [index * clock["video_pts_step"] for index in range(clock["frame_count"])]
    _require_equal([int(item["pts"]) for item in video_frames], expected_video_pts, "full video PTS sequence")
    _require_equal([_frame_duration(item) for item in video_frames], [clock["video_pts_step"]] * clock["frame_count"], "full video duration sequence")

    cursor = 0
    audio_rows: list[dict[str, int]] = []
    for index, frame in enumerate(audio_frames):
        pts = int(frame["pts"])
        samples = int(frame["nb_samples"])
        _require_equal(pts, cursor, f"audio frame {index} PTS continuity")
        if samples <= 0:
            raise ReviewHarnessError(f"audio frame {index} has no samples")
        audio_rows.append({"pts": pts, "samples": samples})
        cursor += samples
    _require_equal(cursor, clock["audio_sample_count"], "full audio PTS sample count")
    video_end = Fraction(expected_video_pts[-1] + clock["video_pts_step"], 15360)
    audio_end = Fraction(cursor, clock["audio_sample_rate"])
    _require_equal(video_end, Fraction(101, 10), "video end time")
    _require_equal(audio_end, Fraction(101, 10), "audio end time")
    pts_audit = {
        "video_frame_count": len(video_frames),
        "video_first_pts": expected_video_pts[0],
        "video_last_pts": expected_video_pts[-1],
        "video_pts_step": clock["video_pts_step"],
        "video_end_seconds": float(video_end),
        "audio_frame_count": len(audio_frames),
        "audio_sample_count": cursor,
        "audio_end_seconds": float(audio_end),
        "end_sync_offset_seconds": float(video_end - audio_end),
        "video_pts_sha256": _canonical_hash(expected_video_pts),
        "audio_pts_samples_sha256": _canonical_hash(audio_rows),
        "continuous": True,
    }
    color = contract["required_color"]
    observed_color = {
        "range": video.get("color_range"), "space": video.get("color_space"),
        "transfer": video.get("color_transfer"), "primaries": video.get("color_primaries"),
    }
    _require_equal(observed_color, {key: color[key] for key in ("range", "space", "transfer", "primaries")}, "stream color metadata")
    return pts_audit, {"stream": observed_color, "video": video, "audio": audio}


def _walk_mov_atoms(handle: BinaryIO, start: int, end: int, path: tuple[str, ...]) -> Iterator[dict[str, Any]]:
    cursor = start
    containers = {"moov", "trak", "mdia", "minf", "stbl"}
    while cursor + 8 <= end:
        handle.seek(cursor)
        header_bytes = handle.read(8)
        if len(header_bytes) != 8:
            raise ReviewHarnessError("MOV atom header is truncated")
        size32, raw_type = struct.unpack(">I4s", header_bytes)
        atom_type = raw_type.decode("latin1")
        header = 8
        if size32 == 1:
            extended = handle.read(8)
            if len(extended) != 8:
                raise ReviewHarnessError("MOV extended atom size is truncated")
            size = struct.unpack(">Q", extended)[0]
            header = 16
        elif size32 == 0:
            size = end - cursor
        else:
            size = size32
        if size < header or cursor + size > end:
            raise ReviewHarnessError(f"MOV atom {atom_type!r} has invalid geometry")
        atom_path = path + (atom_type,)
        atom = {"type": atom_type, "path": "/".join(atom_path), "start": cursor, "size": size, "header": header}
        yield atom
        child_start = cursor + header
        if atom_type in containers:
            yield from _walk_mov_atoms(handle, child_start, cursor + size, atom_path)
        elif atom_type == "stsd":
            yield from _walk_mov_atoms(handle, child_start + 8, cursor + size, atom_path)
        elif atom_type in {"ap4h", "ap4x", "apcn", "apch", "apcs", "apco"}:
            yield from _walk_mov_atoms(handle, child_start + 78, cursor + size, atom_path)
        cursor += size


def _parse_mov_colr(media: Path) -> dict[str, Any]:
    size = media.stat().st_size
    with media.open("rb") as handle:
        atoms = list(_walk_mov_atoms(handle, 0, size, ()))
        colr = [item for item in atoms if item["type"] == "colr"]
        _require_equal(len(colr), 1, "MOV colr atom count")
        atom = colr[0]
        handle.seek(atom["start"] + atom["header"])
        payload = handle.read(atom["size"] - atom["header"])
    _require_equal(len(payload), 10, "MOV colr payload bytes")
    color_type = payload[:4].decode("ascii", errors="strict")
    primaries, transfer, matrix = struct.unpack(">HHH", payload[4:])
    top = {item["type"]: item["start"] for item in atoms if item["path"] in {"moov", "mdat"}}
    return {
        "type": color_type, "path": atom["path"], "payload_bytes": len(payload),
        "primaries": primaries, "transfer": transfer, "matrix": matrix,
        "moov_before_mdat": "moov" in top and "mdat" in top and top["moov"] < top["mdat"],
    }


def _audit_colr(colr: dict[str, Any], contract: dict[str, Any]) -> None:
    required = contract["required_color"]
    _require_equal(colr["type"], required["mov_colr_type"], "MOV colr type")
    for field in ("primaries", "transfer", "matrix"):
        _require_equal(colr[field], required[f"mov_colr_{field}"], f"MOV colr {field}")
    _require_equal(colr["moov_before_mdat"], required["moov_before_mdat"], "MOV faststart")


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


def _selected_frame_numbers(contract: dict[str, Any]) -> list[int]:
    return sorted({item["frame"] for group in contract["review_frames"].values() for item in group})


def _decode_selected_frames(ffmpeg: Path, media: Path, stderr_path: Path, contract: dict[str, Any]) -> tuple[dict[int, np.ndarray], dict[str, Any]]:
    clock = contract["clock"]
    selected = set(_selected_frame_numbers(contract))
    frame_bytes = clock["width"] * clock["height"] * 3
    command = _video_decode_command(ffmpeg, media)
    retained: dict[int, np.ndarray] = {}
    combined = hashlib.sha256()
    with stderr_path.open("wb") as stderr:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stderr)
        if process.stdout is None:
            raise ReviewHarnessError("raw RGB decoder stdout pipe was not created")
        for frame_number in range(1, clock["frame_count"] + 1):
            payload = _read_exact(process.stdout, frame_bytes)
            if len(payload) != frame_bytes:
                process.kill()
                process.wait()
                raise ReviewHarnessError(f"raw RGB decode truncated at frame {frame_number}")
            combined.update(payload)
            if frame_number in selected:
                retained[frame_number] = np.frombuffer(payload, dtype=np.uint8).reshape(clock["height"], clock["width"], 3).copy()
        trailing = process.stdout.read(1)
        return_code = process.wait()
    _require_equal(return_code, 0, "raw RGB decoder return code")
    _require_equal(trailing, b"", "raw RGB decoder trailing payload")
    _require_equal(sorted(retained), sorted(selected), "retained review frames")
    return retained, {"command": command, "decoded_frames": clock["frame_count"], "decoded_rgb24_sha256": combined.hexdigest()}


def _decode_audio_pcm(ffmpeg: Path, media: Path, stderr_path: Path, contract: dict[str, Any]) -> tuple[bytes, list[str]]:
    command = _audio_decode_command(ffmpeg, media)
    with stderr_path.open("wb") as stderr:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=stderr, check=False)
    _require_equal(result.returncode, 0, "PCM24 decoder return code")
    expected = contract["clock"]["audio_sample_count"] * contract["clock"]["audio_channels"] * 3
    _require_equal(len(result.stdout), expected, "decoded PCM24 bytes")
    return result.stdout, command


def _pcm24_array(payload: bytes, channels: int) -> np.ndarray:
    if len(payload) % (channels * 3):
        raise ReviewHarnessError("PCM24 payload is not sample aligned")
    raw = np.frombuffer(payload, dtype=np.uint8).reshape(-1, channels, 3).astype(np.int32)
    values = raw[:, :, 0] | (raw[:, :, 1] << 8) | (raw[:, :, 2] << 16)
    return np.where(values & 0x800000, values - 0x1000000, values)


def _write_audio_segment(pcm: bytes, output: Path, contract: dict[str, Any]) -> dict[str, Any]:
    clock, segment = contract["clock"], contract["audio_segment"]
    stride = clock["audio_channels"] * 3
    payload = pcm[segment["start_sample"] * stride:segment["end_sample"] * stride]
    _require_equal(len(payload), segment["pcm_bytes"], "review audio segment bytes")
    samples = _pcm24_array(payload, clock["audio_channels"])
    with wave.open(str(output), "wb") as handle:
        handle.setnchannels(clock["audio_channels"])
        handle.setsampwidth(3)
        handle.setframerate(clock["audio_sample_rate"])
        handle.writeframes(payload)
    per_channel = []
    for index in range(clock["audio_channels"]):
        channel = samples[:, index].astype(np.float64)
        per_channel.append({
            "channel": index,
            "minimum": int(samples[:, index].min()),
            "maximum": int(samples[:, index].max()),
            "peak_absolute": int(np.abs(channel).max()),
            "rms": math.sqrt(float(np.mean(channel * channel, dtype=np.float64))),
            "dc_mean": float(channel.mean()),
        })
    return {
        "start_seconds": segment["start_seconds"], "end_seconds": segment["end_seconds"],
        "start_sample": segment["start_sample"], "end_sample": segment["end_sample"],
        "sample_frames": samples.shape[0], "pcm_bytes": len(payload),
        "pcm_sha256": hashlib.sha256(payload).hexdigest(),
        "wav_file": output.name, "wav_sha256": _sha256(output),
        "clipped_samples": int(np.count_nonzero(np.abs(samples.astype(np.int64)) >= 8388607)),
        "channels": per_channel,
    }


def _contact_entries(contract: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    review = contract["review_frames"]
    return [("CUT", item) for item in review["cuts"]] + [("F240-256", item) for item in review["f240_f256"]] + [("BLINK", item) for item in review["blink"]] + [("VISEME", item) for item in review["viseme"]]


def _render_contact_sheet(frames: dict[int, np.ndarray], destination: Path, color: dict[str, Any], media_sha256: str, contract: dict[str, Any]) -> None:
    entries = _contact_entries(contract)
    columns, cell_width, cell_height, header_height = 5, 384, 260, 150
    rows = math.ceil(len(entries) / columns)
    sheet = Image.new("RGB", (columns * cell_width, header_height + rows * cell_height), (18, 20, 24))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    stream, colr = color["stream"], color["mov_colr"]
    lines = [
        "PHASE36 FUTURE REAUTHORIZED MASTER - READ-ONLY REVIEW",
        f"MOV SHA-256 {media_sha256}",
        f"Stream: {stream['range']} / {stream['space']} / {stream['transfer']} / {stream['primaries']} | MOV {colr['type']} {colr['primaries']}/{colr['transfer']}/{colr['matrix']} | moov-before-mdat={colr['moov_before_mdat']}",
        "F248 remains blocking until a human explicitly passes the repaired future master.",
    ]
    for index, line in enumerate(lines):
        draw.text((20, 15 + index * 28), line, fill=(238, 242, 248), font=font)
    colors = {"CUT": (220, 160, 70), "F240-256": (190, 80, 80), "BLINK": (80, 170, 220), "VISEME": (110, 205, 130)}
    for index, (group, item) in enumerate(entries):
        row, column = divmod(index, columns)
        x, y = column * cell_width, header_height + row * cell_height
        image = Image.fromarray(frames[item["frame"]], "RGB")
        image.thumbnail((cell_width, 216), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (cell_width, 216), (0, 0, 0))
        canvas.paste(image, ((cell_width - image.width) // 2, (216 - image.height) // 2))
        sheet.paste(canvas, (x, y))
        label = f"{group}  F{item['frame']:03d}"
        if "viseme" in item:
            label += f"  viseme {item['viseme']}"
        elif "closure" in item:
            label += f"  closure {item['closure']:.2f}"
        elif "label" in item:
            label += f"  {item['label']}"
        draw.rectangle((x, y + 216, x + cell_width - 1, y + cell_height - 1), fill=(28, 31, 38), outline=colors[group])
        draw.text((x + 8, y + 229), label, fill=colors[group], font=font)
    sheet.save(destination, format="PNG", compress_level=6)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def _write_checklist(path: Path, contract: dict[str, Any], binding: dict[str, Any], evidence: dict[str, Any]) -> None:
    lines = [
        "# Phase36 Future Master Human Review Checklist", "",
        f"Binding SHA-256: `{evidence['binding_sha256']}`", f"MOV SHA-256: `{binding['media_sha256']}`", "",
        "This package is inspection evidence only. It does not authorize promotion, distribution, or another encode.", "",
    ]
    lines.extend(f"- [ ] {item}" for item in contract["human_checklist"])
    lines.extend(["", "## Decision", "", "- [ ] PASS — every item above is explicitly satisfied.", "- [ ] FAIL — record exact frame/time and defect.", ""])
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _inventory(directory: Path, exclude: set[str]) -> list[dict[str, Any]]:
    result = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name in exclude:
            continue
        if not path.is_file():
            raise ReviewHarnessError(f"review stage has non-file entry {path.name}")
        result.append({"file": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    return result


def _output_directory(binding: dict[str, Any], contract: dict[str, Any]) -> Path:
    prefix = contract["output"]["directory_prefix"]
    return (OUTPUTS_ROOT / "review" / f"{prefix}{binding['media_sha256'][:12]}").resolve()


def _file_state(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": _sha256(path)}


def plan() -> dict[str, Any]:
    contract = load_contract()
    return {
        "status": "WAITING_FOR_FUTURE_REAUTHORIZED_MASTER_BINDING",
        "current_candidate02_or_f91_master_allowed": False,
        "binding_required": True,
        "binding_hash_required": True,
        "binding_template": contract["binding_policy"]["template_path"],
        "video_encoder_allowed": False,
        "source_mutation_allowed": False,
        "review_frames": {name: [item["frame"] for item in values] for name, values in contract["review_frames"].items()},
        "unique_decoded_review_frames": _selected_frame_numbers(contract),
        "audio_segment": contract["audio_segment"],
        "artifacts": [
            *[value for key, value in contract["output"].items() if key.endswith("_filename")],
            contract["audio_segment"]["filename"],
        ],
    }


def inspect_master(
    *, binding_path: str | Path, binding_sha256: str, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    contract = load_contract()
    binding = _load_binding(binding_path, binding_sha256, contract)
    evidence = _verify_master_evidence(binding, contract)
    media = evidence["paths"]["media"]
    before = {
        name: _file_state(evidence["paths"][name])
        for name in ("report", "package", "media", "claim")
    }
    ffmpeg_path, ffprobe_path = _resolved_tool(ffmpeg), _resolved_tool(ffprobe)
    _validate_tools(ffmpeg_path, ffprobe_path, binding)

    output = _output_directory(binding, contract)
    if output.exists():
        raise ReviewHarnessError(f"immutable review harness output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    names = contract["output"]
    try:
        probe_path = stage / names["ffprobe_filename"]
        probe = _run_ffprobe(ffprobe_path, media, probe_path, stage / names["ffprobe_stderr_filename"])
        pts_audit, color_audit = _audit_pts(probe, contract)
        mov_colr = _parse_mov_colr(media)
        _audit_colr(mov_colr, contract)
        color_audit["mov_colr"] = mov_colr
        frames, video_decode = _decode_selected_frames(ffmpeg_path, media, stage / names["video_decode_stderr_filename"], contract)
        pcm, audio_command = _decode_audio_pcm(ffmpeg_path, media, stage / names["audio_decode_stderr_filename"], contract)
        audio_audit = _write_audio_segment(pcm, stage / contract["audio_segment"]["filename"], contract)
        _render_contact_sheet(frames, stage / names["contact_sheet_filename"], color_audit, binding["media_sha256"], contract)
        _write_json(stage / names["pts_audit_filename"], pts_audit)
        _write_json(stage / names["color_audit_filename"], color_audit)
        _write_json(stage / names["audio_audit_filename"], audio_audit)
        binding_observed_sha = _sha256(binding_path)
        _require_equal(binding_observed_sha, binding_sha256, "future master binding fixed state")
        report = {
            "report_version": 1,
            "status": "INSPECTION_EVIDENCE_READY_HUMAN_DECISION_REQUIRED",
            "binding_sha256": binding_observed_sha,
            "future_master": {
                "attempt_id": binding["attempt_id"], "media_sha256": binding["media_sha256"],
                "report_sha256": binding["report_sha256"], "package_sha256": binding["package_sha256"],
                "supersedes_revoked_candidate02_master": True,
            },
            "source_mov_immutable": True,
            "video_encoder_processes_started": 0,
            "decode_commands": {"video_raw_rgb": video_decode["command"], "audio_pcm24": audio_command, "ffprobe": _ffprobe_command(ffprobe_path, media)},
            "picture": {**video_decode, "selected_frames": _selected_frame_numbers(contract), "contact_sheet": names["contact_sheet_filename"]},
            "audio_segment": audio_audit,
            "pts_audit": pts_audit,
            "color_audit": color_audit,
            "human_decision_required": True,
            "promotion_allowed": False,
            "distribution_encode_allowed": False,
        }
        _write_json(stage / names["report_filename"], report)
        _write_checklist(stage / names["checklist_filename"], contract, binding, {"binding_sha256": binding_observed_sha})
        package_path = stage / names["package_filename"]
        package = {
            "package_version": 1,
            "status": report["status"],
            "future_master_media_sha256": binding["media_sha256"],
            "source_mov_immutable": True,
            "video_encoder_processes_started": 0,
            "artifacts": _inventory(stage, {package_path.name}),
            "human_decision_required": True,
            "promotion_allowed": False,
            "distribution_encode_allowed": False,
        }
        _write_json(package_path, package)
        after = {
            name: _file_state(evidence["paths"][name])
            for name in ("report", "package", "media", "claim")
        }
        _require_equal(after, before, "future master immutable evidence state")
        stage.rename(output)
        return {
            "status": report["status"], "output_directory": str(output),
            "contact_sheet": str(output / names["contact_sheet_filename"]),
            "audio_segment": str(output / contract["audio_segment"]["filename"]),
            "checklist": str(output / names["checklist_filename"]),
            "report": str(output / names["report_filename"]),
            "package": str(output / names["package_filename"]),
            "source_mov_immutable": True, "video_encoder_processes_started": 0,
            "human_decision_required": True, "promotion_allowed": False,
        }
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("plan")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--binding", required=True)
    inspect_parser.add_argument("--binding-sha256", required=True)
    inspect_parser.add_argument("--ffmpeg", default="ffmpeg")
    inspect_parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = plan() if args.command == "plan" else inspect_master(
        binding_path=args.binding, binding_sha256=args.binding_sha256,
        ffmpeg=args.ffmpeg, ffprobe=args.ffprobe,
    )
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
