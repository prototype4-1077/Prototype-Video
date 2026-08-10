"""Verify and, when separately authorized, build Phase 36 Candidate 02 audio only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import tempfile
from typing import Any
import wave

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase36_candidate02_audio_repair_v1.json"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "aa18088d8e942fa6b5aadbe9f7b1d31df2c310788a4a85766f76a1299be7853e"
PCM24_MAX = 8388607


class AudioRepairError(RuntimeError):
    """Raised when a Candidate 02 audio-only invariant is violated."""


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AudioRepairError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _strict_json_loads(payload: bytes, label: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AudioRepairError(f"{label} is not UTF-8") from exc

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AudioRepairError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise AudioRepairError(f"{label} contains non-finite number {value}")

    try:
        return json.loads(text, object_pairs_hook=object_pairs, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise AudioRepairError(f"{label} is not valid JSON") from exc


def _repo_path(relative: str) -> Path:
    path = Path(relative)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = _repo_path(str(reference["path"]))
    if not path.is_file():
        raise AudioRepairError(f"{label} is missing: {path}")
    _require_equal(_sha256(path), reference["sha256"], f"{label} SHA-256")
    return path


def _locked_payload(reference: dict[str, Any], label: str) -> tuple[Path, bytes]:
    path = _repo_path(str(reference["path"]))
    if not path.is_file():
        raise AudioRepairError(f"{label} is missing: {path}")
    payload = path.read_bytes()
    _require_equal(hashlib.sha256(payload).hexdigest(), reference["sha256"], f"{label} SHA-256")
    return path, payload


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned Candidate02 contract path")
    contract = _strict_json_loads(resolved.read_bytes(), "Candidate02 contract")
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "Candidate02 canonical contract SHA-256")
    _require_equal(contract["contract_version"], 1, "Candidate02 contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase36_candidate02_audio_repair_v1", "Candidate02 contract id")
    _require_equal(contract["character_id"], "june_oxley", "Candidate02 character")
    _require_equal(contract["cash_cost"], 0, "Candidate02 cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "Candidate02 paid dependency policy")
    _require_equal(contract["network_runtime_required"], False, "Candidate02 network policy")
    _require_equal(contract["failure_policy"]["picture_render_allowed"], False, "Candidate02 picture policy")
    _require_equal(contract["failure_policy"]["subprocess_allowed"], False, "Candidate02 subprocess policy")
    _require_equal(contract["failure_policy"]["encode_allowed"], False, "Candidate02 encode policy")
    _require_equal(
        contract["candidate01_picture_reference"]["external_archive_required_for_audio_only_build"],
        False,
        "Candidate02 external picture availability policy",
    )
    _require_equal(
        contract["candidate01_picture_reference"]["external_archive_required_for_future_picture_audio_delivery_binding"],
        True,
        "future picture/audio archive availability policy",
    )
    for name, reference in contract["locks"].items():
        _locked_path(reference, f"locked {name}")
    receipt = contract["authorization"]["receipt"]
    if receipt is not None and not isinstance(receipt, dict):
        raise AudioRepairError("Candidate02 authorization receipt must be null or an exact path/hash lock")
    return contract


def _authorization(contract: dict[str, Any]) -> dict[str, str] | None:
    gate = contract["authorization"]
    reference = gate["receipt"]
    if reference is None:
        return None
    path = _repo_path(str(reference["path"]))
    payload = path.read_bytes()
    domain = reference.get("hash_domain", "raw_bytes")
    if domain == "lf_normalized_text":
        digest = hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()
    elif domain == "raw_bytes":
        digest = hashlib.sha256(payload).hexdigest()
    else:
        raise AudioRepairError("unsupported Candidate02 authorization hash domain")
    _require_equal(digest, reference["sha256"], "Candidate02 authorization receipt SHA-256")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AudioRepairError("Candidate02 authorization receipt is not UTF-8") from exc
    verdict_line = f"{gate['required_verdict_field']} {gate['required_verdict']}"
    lines = [line.strip() for line in text.splitlines()]
    verdict_prefix = f"{gate['required_verdict_field']} "
    verdict_lines = [line for line in lines if line.startswith(verdict_prefix)]
    _require_equal(verdict_lines, [verdict_line], "Candidate02 authorization verdict lines")
    for token in gate["required_binding_tokens"]:
        if str(token) not in text:
            raise AudioRepairError(f"Candidate02 authorization omits binding token {token}")
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "hash_domain": str(domain),
        "sha256": digest,
        "verdict": str(gate["required_verdict"]),
    }


def _candidate01_failure(contract: dict[str, Any]) -> dict[str, Any]:
    _, payload = _locked_payload(contract["locks"]["candidate01_failure_receipt"], "Candidate01 failure receipt")
    receipt = _strict_json_loads(payload, "Candidate01 failure receipt")
    _require_equal(receipt["candidate_id"], "phase36_ledger_pour_candidate_01", "Candidate01 failure candidate id")
    _require_equal(
        receipt["verdict"],
        "PHASE36_CANDIDATE01_REJECTED_AUDIO_CONTINUITY_NEW_BINDING_REQUIRED",
        "Candidate01 failure verdict",
    )
    disposition = receipt["disposition"]
    for key, expected in {
        "promotion_allowed": False,
        "encode_allowed": False,
        "candidate_immutable": True,
        "automatic_retry_allowed": False,
        "repair_requires_new_candidate_binding": True,
        "picture_may_be_reused_bit_exact": True,
    }.items():
        _require_equal(disposition[key], expected, f"Candidate01 failure disposition {key}")
    return receipt


def _candidate01_manifest(contract: dict[str, Any]) -> dict[str, Any]:
    reference = contract["locks"]["candidate01_manifest"]
    _, payload = _locked_payload(reference, "Candidate01 manifest")
    manifest = _strict_json_loads(payload, "Candidate01 manifest")
    picture = contract["candidate01_picture_reference"]
    _require_equal(_canonical_hash(manifest), picture["candidate01_manifest_canonical_sha256"], "Candidate01 manifest canonical SHA-256")
    _require_equal(manifest["machine_passed"], True, "Candidate01 historical machine result")
    _require_equal(manifest["measurements"]["frame_count"], 303, "Candidate01 frame count")
    _require_equal(len(manifest["frame_hashes"]), 303, "Candidate01 frame hash inventory length")
    _require_equal(_canonical_hash(manifest["frame_hashes"]), picture["frame_hash_inventory_canonical_sha256"], "Candidate01 frame hash inventory")
    archive_name = "june-phase36-ledger-pour-rgb24-xor-v1.gz"
    _require_equal(
        manifest["artifacts"][archive_name],
        {"sha256": picture["archive_sha256"], "bytes": picture["archive_bytes"]},
        "Candidate01 picture archive binding",
    )
    wav_name = "june-phase36-ledger-pour-mix-v1.wav"
    _require_equal(manifest["artifacts"][wav_name]["sha256"], contract["locks"]["candidate01_pcm_wav"]["sha256"], "Candidate01 WAV manifest binding")
    _require_equal(manifest["audio"]["probe"]["data_sha256"], contract["audio"]["candidate01_pcm_data_sha256"], "Candidate01 PCM manifest binding")
    return manifest


def _external_picture_archive(contract: dict[str, Any], *, required: bool = False) -> dict[str, Any]:
    reference = contract["candidate01_picture_reference"]
    path = _repo_path(str(reference["external_archive_path"]))
    expected = (REPO_ROOT / "../../outputs/edit/phase36-ledger-pour-lossless-v1-candidate-01/june-phase36-ledger-pour-rgb24-xor-v1.gz").resolve()
    _require_equal(path, expected, "Candidate01 external picture archive path")
    if not path.is_file():
        if required:
            raise AudioRepairError(f"Candidate01 external picture archive is missing: {path}")
        return {
            "path": str(path),
            "sha256": str(reference["archive_sha256"]),
            "bytes": int(reference["archive_bytes"]),
            "available": False,
            "verified": False,
        }
    _require_equal(path.stat().st_size, reference["archive_bytes"], "Candidate01 picture archive bytes")
    _require_equal(_sha256(path), reference["archive_sha256"], "Candidate01 picture archive SHA-256")
    return {
        "path": str(path),
        "sha256": str(reference["archive_sha256"]),
        "bytes": int(reference["archive_bytes"]),
        "available": True,
        "verified": True,
    }


def _read_pcm24_wave(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    file_size = path.stat().st_size
    with path.open("rb") as source:
        header = source.read(12)
        if len(header) != 12:
            raise AudioRepairError(f"PCM source has a truncated RIFF header: {path.name}")
        riff, riff_size, wave_id = struct.unpack("<4sI4s", header)
        if riff != b"RIFF" or wave_id != b"WAVE" or riff_size + 8 != file_size:
            raise AudioRepairError(f"PCM source has invalid RIFF geometry: {path.name}")
        fmt: bytes | None = None
        data: bytes | None = None
        while source.tell() < file_size:
            chunk_header = source.read(8)
            if len(chunk_header) != 8:
                raise AudioRepairError(f"PCM source has a truncated chunk: {path.name}")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            payload = source.read(chunk_size)
            if len(payload) != chunk_size:
                raise AudioRepairError(f"PCM source chunk is truncated: {path.name}")
            if chunk_size % 2 and source.read(1) == b"":
                raise AudioRepairError(f"PCM source chunk pad is missing: {path.name}")
            if chunk_id == b"fmt ":
                if fmt is not None:
                    raise AudioRepairError(f"PCM source has duplicate fmt chunks: {path.name}")
                fmt = payload
            elif chunk_id == b"data":
                if data is not None:
                    raise AudioRepairError(f"PCM source has duplicate data chunks: {path.name}")
                data = payload
    if fmt is None or data is None or len(fmt) < 16:
        raise AudioRepairError(f"PCM source omits fmt/data chunks: {path.name}")
    format_tag, channels, sample_rate, byte_rate, block_align, bits = struct.unpack("<HHIIHH", fmt[:16])
    if format_tag == 0xFFFE:
        if len(fmt) < 40 or struct.unpack("<H", fmt[16:18])[0] < 22:
            raise AudioRepairError(f"PCM extensible fmt is incomplete: {path.name}")
        valid_bits = struct.unpack("<H", fmt[18:20])[0]
        pcm_guid = bytes.fromhex("0100000000001000800000aa00389b71")
        if valid_bits != bits or fmt[24:40] != pcm_guid:
            raise AudioRepairError(f"PCM extensible subtype is not matching-width PCM: {path.name}")
    elif format_tag != 1:
        raise AudioRepairError(f"PCM source is compressed: {path.name}")
    if channels != 2 or bits != 24 or block_align != 6 or byte_rate != sample_rate * 6:
        raise AudioRepairError(f"PCM source is not stereo PCM24: {path.name}")
    if len(data) % block_align:
        raise AudioRepairError(f"PCM24 payload is not frame-aligned: {path.name}")
    packed = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
    values = packed[:, 0].astype(np.int32) | (packed[:, 1].astype(np.int32) << 8) | (packed[:, 2].astype(np.int32) << 16)
    values = np.where(values & 0x800000, values - 0x1000000, values).astype(np.int32)
    samples = values.reshape(-1, channels)
    return samples, {
        "sample_rate": sample_rate,
        "channels": channels,
        "bits_per_sample": bits,
        "sample_count": int(samples.shape[0]),
        "data_bytes": len(data),
        "data_sha256": hashlib.sha256(data).hexdigest(),
    }


def _pcm24_bytes(samples: np.ndarray) -> bytes:
    values = np.asarray(samples, dtype=np.int32)
    if values.ndim != 2 or values.shape[1] != 2:
        raise AudioRepairError("Candidate02 samples must be an N x 2 array")
    if np.any(values.astype(np.int64) < -8388608) or np.any(values.astype(np.int64) > PCM24_MAX):
        raise AudioRepairError("Candidate02 samples exceed signed PCM24")
    unsigned = values.reshape(-1).astype(np.int64) & 0xFFFFFF
    packed = np.empty((unsigned.size, 3), dtype=np.uint8)
    packed[:, 0] = unsigned & 0xFF
    packed[:, 1] = (unsigned >> 8) & 0xFF
    packed[:, 2] = (unsigned >> 16) & 0xFF
    return packed.tobytes()


def _write_pcm24_wave(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(2)
        destination.setsampwidth(3)
        destination.setframerate(sample_rate)
        destination.writeframes(_pcm24_bytes(samples))


def _source_state(contract: dict[str, Any], *, include_external_picture: bool) -> dict[str, Any]:
    contract_path = REPO_ROOT / CONTRACT_RELATIVE_PATH
    contract_payload = contract_path.read_bytes()
    parsed_contract = _strict_json_loads(contract_payload, "Candidate02 contract")
    canonical = _canonical_hash(parsed_contract)
    _require_equal(canonical, EXPECTED_CONTRACT_CANONICAL_SHA256, "Candidate02 source-state canonical contract SHA-256")
    locked: dict[str, str] = {}
    for name, reference in contract["locks"].items():
        _, payload = _locked_payload(reference, f"Candidate02 source-state locked {name}")
        locked[name] = hashlib.sha256(payload).hexdigest()
    state = {
        "contract_raw_sha256": hashlib.sha256(contract_payload).hexdigest(),
        "contract_canonical_sha256": canonical,
        "implementation_sha256": _sha256(Path(__file__).resolve()),
        "locked": locked,
        "authorization": _authorization(contract),
    }
    if include_external_picture:
        state["external_picture"] = _external_picture_archive(contract, required=False)
    return state


def _source_audio(contract: dict[str, Any], *, verify_phase26_provenance: bool) -> tuple[np.ndarray, np.ndarray]:
    audio = contract["audio"]
    candidate01, candidate01_probe = _read_pcm24_wave(_repo_path(contract["locks"]["candidate01_pcm_wav"]["path"]))
    bridge, bridge_probe = _read_pcm24_wave(_repo_path(contract["locks"]["candidate02_bridge_wav"]["path"]))
    phase26_source, phase26_source_probe = _read_pcm24_wave(
        _repo_path(contract["locks"]["candidate02_phase26_source_wav"]["path"])
    )
    phase33, phase33_probe = _read_pcm24_wave(_repo_path(contract["locks"]["phase33_delivery_mix"]["path"]))
    expected_geometry = {"sample_rate": 48000, "channels": 2, "bits_per_sample": 24}
    for name, probe, count in (
        ("Candidate01", candidate01_probe, 484800),
        ("Candidate02 bridge", bridge_probe, 39840),
        ("Candidate02 Phase26 source", phase26_source_probe, 39840),
        ("Phase33", phase33_probe, 364800),
    ):
        _require_equal({key: probe[key] for key in expected_geometry}, expected_geometry, f"{name} PCM geometry")
        _require_equal(probe["sample_count"], count, f"{name} sample count")
    _require_equal(candidate01_probe["data_sha256"], audio["candidate01_pcm_data_sha256"], "Candidate01 PCM data SHA-256")
    _require_equal(bridge_probe["data_sha256"], audio["bridge_pcm_data_sha256"], "Candidate02 bridge PCM data SHA-256")
    _require_equal(
        phase26_source_probe["data_sha256"],
        audio["source_provenance"]["committed_phase26_source_pcm_data_sha256"],
        "committed Phase26 source PCM data SHA-256",
    )
    _require_equal(candidate01[120000:].tobytes(), phase33.tobytes(), "Candidate01 Phase33 splice")
    _require_equal(candidate01[158400:].tobytes(), phase33[38400:].tobytes(), "unchanged dialogue suffix")
    if verify_phase26_provenance:
        provenance = audio["source_provenance"]
        start, end = (int(value) for value in provenance["phase26_master_sample_span"])
        _require_equal(end - start, 39840, "Phase26 bridge provenance span")
        count = int(audio["crossfade_samples"])
        _require_equal(count, 1440, "Candidate02 crossfade sample count")
        _require_equal(tuple(audio["crossfade_span"]), (118560, 120000), "Candidate02 crossfade span")
        _require_equal(tuple(audio["replacement_span"]), (118560, 158400), "Candidate02 replacement span")
        master_path = _repo_path(str(provenance["phase26_master_path"]))
        if master_path.is_file():
            _require_equal(_sha256(master_path), provenance["phase26_master_sha256"], "optional Phase26 master WAV SHA-256")
            master, master_probe = _read_pcm24_wave(master_path)
            _require_equal(master_probe["sample_count"], 1862400, "optional Phase26 master sample count")
            _require_equal(master[start:end].tobytes(), phase26_source.tobytes(), "committed Phase26 source slice")
        t = np.arange(count, dtype=np.float64) / float(count - 1)
        derived_crossfade = np.rint(
            candidate01[118560:120000].astype(np.float64) * np.cos(np.pi * t[:, None] / 2.0)
            + phase26_source[:count].astype(np.float64) * np.sin(np.pi * t[:, None] / 2.0)
        ).astype(np.int32)
        derived_bridge = np.concatenate((derived_crossfade, phase26_source[count:]), axis=0)
        _require_equal(derived_bridge.tobytes(), bridge.tobytes(), "derived Candidate02 bridge")
        _require_equal(
            hashlib.sha256(_pcm24_bytes(phase26_source[count:])).hexdigest(),
            provenance["phase26_missing_predecessor_pcm_sha256"],
            "Phase26 missing predecessor PCM SHA-256",
        )
        _require_equal(
            hashlib.sha256(_pcm24_bytes(np.concatenate((phase26_source[count:], candidate01[158400:]), axis=0))).hexdigest(),
            provenance["phase26_replacement_through_end_pcm_sha256"],
            "Phase26 replacement-through-end PCM SHA-256",
        )
        _require_equal(
            hashlib.sha256(_pcm24_bytes(candidate01[158400:])).hexdigest(),
            provenance["candidate01_phase33_phase26_unchanged_suffix_pcm_sha256"],
            "Candidate01/Phase33/Phase26 unchanged suffix PCM SHA-256",
        )
    return candidate01, bridge


def assemble_candidate02(contract: dict[str, Any], *, verify_phase26_provenance: bool = True) -> tuple[np.ndarray, np.ndarray]:
    candidate01, bridge = _source_audio(contract, verify_phase26_provenance=verify_phase26_provenance)
    prefix_start, prefix_end = (int(value) for value in contract["audio"]["unchanged_prefix"])
    suffix_start, suffix_end = (int(value) for value in contract["audio"]["unchanged_dialogue_suffix"])
    _require_equal(prefix_start, 0, "Candidate02 prefix start")
    _require_equal((prefix_end, suffix_start, suffix_end), (118560, 158400, 484800), "Candidate02 repair boundaries")
    candidate02 = np.concatenate((candidate01[:prefix_end], bridge, candidate01[suffix_start:suffix_end]), axis=0)
    _require_equal(candidate02.shape, (484800, 2), "Candidate02 sample shape")
    return candidate01, candidate02


def _longest_true_run(values: np.ndarray) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if bool(value) else 0
        longest = max(longest, current)
    return longest


def _rms_dbfs(samples: np.ndarray) -> float:
    normalized = samples.astype(np.float64) / PCM24_MAX
    rms = float(np.sqrt(np.mean(normalized * normalized)))
    return 20.0 * math.log10(max(rms, 1e-15))


def measure_candidate02(contract: dict[str, Any], candidate01: np.ndarray, candidate02: np.ndarray) -> dict[str, Any]:
    audio = contract["audio"]
    zero_pairs = np.all(candidate02 == 0, axis=1)
    frame_rms = [_rms_dbfs(candidate02[index:index + 1600]) for index in range(0, 484800, 1600)]
    cuts: dict[str, dict[str, float]] = {}
    for frame in (76, 238):
        start = (frame - 1) * 1600
        window = candidate02[start:start + 4800]
        cuts[str(frame)] = {
            "post_100ms_rms_dbfs": _rms_dbfs(window),
            "post_100ms_active_pair_ratio": float(np.count_nonzero(np.any(window != 0, axis=1)) / len(window)),
        }
    pre = _rms_dbfs(candidate02[115200:120000])
    post = _rms_dbfs(candidate02[120000:124800])
    peak = float(np.max(np.abs(candidate02.astype(np.int64))) / PCM24_MAX)
    return {
        "sample_count": int(candidate02.shape[0]),
        "pcm_data_sha256": hashlib.sha256(_pcm24_bytes(candidate02)).hexdigest(),
        "unchanged_prefix_channel_values": int(np.count_nonzero(candidate02[:118560] == candidate01[:118560])),
        "unchanged_dialogue_suffix_channel_values": int(np.count_nonzero(candidate02[158400:] == candidate01[158400:])),
        "changed_sample_frames": int(np.count_nonzero(np.any(candidate02 != candidate01, axis=1))),
        "maximum_stereo_exact_zero_run_samples": _longest_true_run(zero_pairs),
        "fully_zero_picture_frames": int(sum(np.all(candidate02[index:index + 1600] == 0) for index in range(0, 484800, 1600))),
        "hard_cuts": cuts,
        "minimum_hard_cut_post_100ms_rms_dbfs": min(item["post_100ms_rms_dbfs"] for item in cuts.values()),
        "minimum_hard_cut_post_100ms_active_pair_ratio": min(item["post_100ms_active_pair_ratio"] for item in cuts.values()),
        "minimum_output_frame_rms_dbfs": min(frame_rms),
        "minimum_output_frame_rms_frame": frame_rms.index(min(frame_rms)) + 1,
        "same_porch_cut_pre_100ms_rms_dbfs": pre,
        "same_porch_cut_post_100ms_rms_dbfs": post,
        "same_porch_cut_100ms_rms_difference_db": abs(pre - post),
        "clipped_channel_values": int(np.count_nonzero(np.abs(candidate02.astype(np.int64)) > PCM24_MAX)),
        "peak_dbfs": 20.0 * math.log10(max(peak, 1e-15)),
    }


def _gate_report(contract: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    gates = contract["gates"]
    checks = (
        ("picture_archive_reference_hash_unchanged", metrics["picture_archive_reference_hash_unchanged"], "==", gates["required_picture_archive_reference_hash_unchanged"]),
        ("picture_frame_hash_inventory_unchanged", metrics["picture_frame_hash_inventory_unchanged"], "==", gates["required_picture_frame_hash_inventory_unchanged"]),
        ("pcm24_readback_channel_values", metrics["pcm24_readback_channel_values"], "==", gates["required_pcm24_readback_channel_values"]),
        ("unchanged_prefix_channel_values", metrics["unchanged_prefix_channel_values"], "==", gates["required_unchanged_prefix_channel_values"]),
        ("unchanged_dialogue_suffix_channel_values", metrics["unchanged_dialogue_suffix_channel_values"], "==", gates["required_unchanged_dialogue_suffix_channel_values"]),
        ("changed_sample_frames", metrics["changed_sample_frames"], "==", gates["required_changed_sample_frames"]),
        ("maximum_stereo_exact_zero_run_samples", metrics["maximum_stereo_exact_zero_run_samples"], "<=", gates["maximum_stereo_exact_zero_run_samples"]),
        ("fully_zero_picture_frames", metrics["fully_zero_picture_frames"], "==", gates["required_fully_zero_picture_frames"]),
        ("minimum_hard_cut_post_100ms_rms_dbfs", metrics["minimum_hard_cut_post_100ms_rms_dbfs"], ">=", gates["minimum_hard_cut_post_100ms_rms_dbfs"]),
        ("minimum_hard_cut_post_100ms_active_pair_ratio", metrics["minimum_hard_cut_post_100ms_active_pair_ratio"], ">=", gates["minimum_hard_cut_post_100ms_active_pair_ratio"]),
        ("minimum_output_frame_rms_dbfs", metrics["minimum_output_frame_rms_dbfs"], ">=", gates["minimum_output_frame_rms_dbfs"]),
        ("same_porch_cut_100ms_rms_difference_db", metrics["same_porch_cut_100ms_rms_difference_db"], "<=", gates["maximum_same_porch_cut_100ms_rms_difference_db"]),
        ("clipped_channel_values", metrics["clipped_channel_values"], "==", gates["required_clipped_channel_values"]),
        ("peak_dbfs", metrics["peak_dbfs"], "<=", gates["maximum_peak_dbfs"]),
        ("output_files", metrics["output_files"], "==", gates["required_output_files"]),
        ("encoded_media_files", metrics["encoded_media_files"], "==", gates["required_encoded_media_files"]),
    )
    operators = {"==": lambda a, b: a == b, "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b}
    return [
        {"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(operators[operator](actual, threshold))}
        for name, actual, operator, threshold in checks
    ]


def _verify_written_candidate(contract: dict[str, Any], path: Path, intended: np.ndarray) -> dict[str, Any]:
    decoded, probe = _read_pcm24_wave(path)
    _require_equal(decoded.shape, intended.shape, "Candidate02 PCM readback shape")
    exact = int(np.count_nonzero(decoded == intended))
    _require_equal(exact, int(intended.size), "Candidate02 PCM readback channel values")
    _require_equal(probe["data_sha256"], contract["audio"]["expected_candidate02_pcm_data_sha256"], "Candidate02 PCM data SHA-256")
    _require_equal(_sha256(path), contract["audio"]["expected_candidate02_wav_sha256"], "Candidate02 WAV SHA-256")
    return {"probe": probe, "pcm24_readback_channel_values": exact, "wav_sha256": _sha256(path)}


def _output_path(contract: dict[str, Any]) -> Path:
    return _repo_path(str(contract["output"]["directory"]))


def preflight(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    contract = load_contract(path)
    output = _output_path(contract)
    output_before = output.exists()
    failure = _candidate01_failure(contract)
    manifest = _candidate01_manifest(contract)
    picture = _external_picture_archive(contract, required=False)
    candidate01, candidate02 = assemble_candidate02(contract, verify_phase26_provenance=True)
    with tempfile.TemporaryDirectory(prefix="phase36-c02-preflight-") as directory:
        wav = Path(directory) / str(contract["output"]["pcm_mix_filename"])
        _write_pcm24_wave(wav, candidate02, 48000)
        written = _verify_written_candidate(contract, wav, candidate02)
    metrics = measure_candidate02(contract, candidate01, candidate02)
    metrics.update({
        "picture_archive_reference_hash_unchanged": True,
        "picture_frame_hash_inventory_unchanged": True,
        "pcm24_readback_channel_values": written["pcm24_readback_channel_values"],
        "output_files": 2,
        "encoded_media_files": 0,
    })
    gates = _gate_report(contract, metrics)
    if any(not gate["passed"] for gate in gates):
        raise AudioRepairError("Candidate02 preflight gate failure: " + ", ".join(gate["name"] for gate in gates if not gate["passed"]))
    _require_equal(output.exists(), output_before, "Candidate02 preflight output state")
    authorization = _authorization(contract)
    return {
        "contract_id": contract["contract_id"],
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "candidate01_failure_verdict": failure["verdict"],
        "candidate01_manifest_sha256": contract["locks"]["candidate01_manifest"]["sha256"],
        "candidate01_picture_archive": picture,
        "picture_frame_count": len(manifest["frame_hashes"]),
        "picture_rerendered": False,
        "predicted_candidate02_wav_sha256": written["wav_sha256"],
        "predicted_candidate02_pcm_data_sha256": metrics["pcm_data_sha256"],
        "gate_count": len(gates),
        "machine_gates_passed": all(gate["passed"] for gate in gates),
        "authorization": authorization,
        "build_authorized": authorization is not None,
        "output_created": output.exists() != output_before,
        "encode_authorized": False,
    }


def write_audio_candidate(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    contract = load_contract(path)
    authorization = _authorization(contract)
    if authorization is None:
        raise AudioRepairError("Candidate02 audio-only build is blocked pending an exact Claude authorization receipt")
    output = _output_path(contract)
    stage = output.parent / f".{output.name}.stage"
    if output.exists() or stage.exists():
        raise AudioRepairError(f"immutable Candidate02 output already exists: {output if output.exists() else stage}")
    _candidate01_failure(contract)
    manifest01 = _candidate01_manifest(contract)
    initial_state = _source_state(contract, include_external_picture=True)
    candidate01, candidate02 = assemble_candidate02(contract, verify_phase26_provenance=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    stage.mkdir()
    try:
        wav = stage / str(contract["output"]["pcm_mix_filename"])
        _write_pcm24_wave(wav, candidate02, 48000)
        written = _verify_written_candidate(contract, wav, candidate02)
        metrics = measure_candidate02(contract, candidate01, candidate02)
        metrics.update({
            "picture_archive_reference_hash_unchanged": True,
            "picture_frame_hash_inventory_unchanged": True,
            "pcm24_readback_channel_values": written["pcm24_readback_channel_values"],
            "output_files": 2,
            "encoded_media_files": 0,
        })
        gates = _gate_report(contract, metrics)
        failed = [gate["name"] for gate in gates if not gate["passed"]]
        if failed:
            raise AudioRepairError("Candidate02 gate failure: " + ", ".join(failed))
        manifest = {
            "manifest_version": 1,
            "candidate_id": "phase36_ledger_pour_candidate_02_audio_only",
            "status": "unencoded_audio_only_machine_passed_human_audio_review_required",
            "machine_passed": True,
            "promotion_allowed": False,
            "encode_authorized": False,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": _sha256(path),
                "canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
            },
            "implementation": {"path": contract["implementation_path"], "sha256": _sha256(Path(__file__).resolve())},
            "authorization": authorization,
            "candidate01": {
                "manifest_sha256": contract["locks"]["candidate01_manifest"]["sha256"],
                "failure_receipt_sha256": contract["locks"]["candidate01_failure_receipt"]["sha256"],
                "picture_archive_sha256": contract["candidate01_picture_reference"]["archive_sha256"],
                "frame_hash_inventory_canonical_sha256": contract["candidate01_picture_reference"]["frame_hash_inventory_canonical_sha256"],
                "frame_count": len(manifest01["frame_hashes"]),
                "picture_reused_by_reference_bit_exact": True,
                "picture_files_written": 0,
            },
            "audio": {"wav_sha256": written["wav_sha256"], "probe": written["probe"], "metrics": metrics},
            "gates": gates,
            "failed_gates": failed,
            "artifacts": {str(contract["output"]["pcm_mix_filename"]): {"sha256": written["wav_sha256"], "bytes": wav.stat().st_size}},
        }
        manifest_path = stage / str(contract["output"]["manifest_filename"])
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        allowed = {str(contract["output"]["pcm_mix_filename"]), str(contract["output"]["manifest_filename"])}
        entries = list(stage.rglob("*"))
        if any(not candidate.is_file() for candidate in entries):
            raise AudioRepairError("Candidate02 output contains a non-file entry")
        actual = {candidate.relative_to(stage).as_posix() for candidate in entries}
        _require_equal(actual, allowed, "Candidate02 output file allowlist")
        _require_equal(_source_state(contract, include_external_picture=True), initial_state, "Candidate02 source state before publication")
        os.replace(stage, output)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        "output": str(output),
        "wav_sha256": written["wav_sha256"],
        "manifest_sha256": _sha256(output / str(contract["output"]["manifest_filename"])),
        "gate_count": len(gates),
        "machine_passed": True,
        "picture_rerendered": False,
        "encode_authorized": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="verify the audio-only repair without publishing")
    subparsers.add_parser("build-unencoded-audio", help="publish only the separately authorized PCM24 repair")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = preflight() if args.command == "preflight" else write_audio_candidate()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
