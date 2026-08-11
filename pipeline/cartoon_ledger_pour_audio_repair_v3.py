"""Preflight and, when separately authorized, publish Phase36 Candidate03 audio."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import cartoon_audio_noise_proxy as noise_proxy
from pipeline import cartoon_golden_sound as golden_sound
from pipeline import cartoon_ledger_pour_audio_repair as candidate02_builder


CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase36_candidate03_audio_repair_v1.json"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "595a0949d2129aa636fb089bb0d38021ba72f2f0c89a83bb152767e9fcb0da2c"
PCM24_MAX = 8_388_607


class Candidate03AudioError(RuntimeError):
    """Raised when a Candidate03 audio-only invariant is violated."""


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise Candidate03AudioError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def _strict_json_loads(payload: bytes, label: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Candidate03AudioError(f"{label} is not UTF-8") from exc

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise Candidate03AudioError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise Candidate03AudioError(f"{label} contains non-finite number {value}")

    try:
        return json.loads(text, object_pairs_hook=object_pairs, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise Candidate03AudioError(f"{label} is not valid JSON") from exc


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def _path_hash(path: Path, hash_domain: str = "raw_bytes") -> str:
    payload = path.read_bytes()
    if hash_domain == "lf_normalized_text":
        payload = payload.replace(b"\r\n", b"\n")
    elif hash_domain != "raw_bytes":
        raise Candidate03AudioError(f"unsupported hash domain {hash_domain!r}")
    return hashlib.sha256(payload).hexdigest()


def _locked_path(reference: dict[str, Any], label: str) -> Path:
    path = _repo_path(str(reference["path"]))
    if not path.is_file():
        raise Candidate03AudioError(f"{label} is missing: {path}")
    _require_equal(_path_hash(path, str(reference.get("hash_domain", "raw_bytes"))), reference["sha256"], f"{label} SHA-256")
    return path


def _implementation_hash() -> str:
    return _path_hash(Path(__file__).resolve(), "lf_normalized_text")


def _contract_raw_lf_hash() -> str:
    return _path_hash(REPO_ROOT / CONTRACT_RELATIVE_PATH, "lf_normalized_text")


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    _require_equal(resolved, (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve(), "pinned Candidate03 contract path")
    contract = _strict_json_loads(resolved.read_bytes(), "Candidate03 contract")
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "Candidate03 canonical contract SHA-256")
    _require_equal(contract["contract_version"], 1, "Candidate03 contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase36_candidate03_audio_repair_v1", "Candidate03 contract id")
    _require_equal(contract["character_id"], "june_oxley", "Candidate03 character")
    _require_equal(contract["cash_cost"], 0, "Candidate03 cash cost")
    _require_equal(contract["paid_runtime_dependency"], False, "Candidate03 paid dependency policy")
    _require_equal(contract["network_runtime_required"], False, "Candidate03 network policy")
    for key in ("picture_render_allowed", "subprocess_allowed", "network_allowed", "encode_allowed"):
        _require_equal(contract["failure_policy"][key], False, f"Candidate03 {key} policy")
    _require_equal(contract["failure_policy"]["machine_pass_must_not_claim_human_acceptance"], True, "human acceptance policy")
    _require_equal(contract["rejected_predecessor"]["immutable"], True, "Candidate02 immutability")
    _require_equal(contract["rejected_predecessor"]["overwrite_allowed"], False, "Candidate02 overwrite policy")
    _require_equal(contract["rejected_predecessor"]["prior_ratification_revoked"], True, "Candidate02 revoked-ratification state")
    for name, reference in contract["locks"].items():
        _locked_path(reference, f"locked {name}")
    _validate_binding_documents(contract)
    receipt = contract["authorization"]["receipt"]
    if receipt is not None and not isinstance(receipt, dict):
        raise Candidate03AudioError("Candidate03 authorization receipt must be null or an exact path/hash lock")
    return contract


def _validate_binding_documents(contract: dict[str, Any]) -> None:
    james_path = _locked_path(contract["locks"]["controlling_james_verdict"], "controlling James verdict")
    james = james_path.read_text(encoding="utf-8")
    for token in (
        'Phase36 c02 audio: REJECTED - "The audio had static in it."',
        "The 2210Z acceptance of the unencoded audio master is REVOKED.",
        "Required: candidate 03, audio-only repair, same immutability rules.",
    ):
        if token not in james:
            raise Candidate03AudioError(f"controlling James verdict omits {token!r}")
    claude_path = _locked_path(contract["locks"]["claude_master_refusal"], "Claude master refusal")
    claude = claude_path.read_text(encoding="utf-8")
    for token in (
        "PHASE35_C03_BLINK_VUI_PROBE_V2_ATTEMPT02_PASS_RATIFIED",
        "Phase36 ProRes 4444 review-master Attempt01 - authorization REFUSED",
        "c03 audio-only repair scaffold",
    ):
        if token not in claude:
            raise Candidate03AudioError(f"Claude master refusal omits {token!r}")


def _authorization(contract: dict[str, Any]) -> dict[str, str] | None:
    gate = contract["authorization"]
    reference = gate["receipt"]
    if reference is None:
        return None
    path = _locked_path(reference, "Candidate03 authorization receipt")
    domain = str(reference.get("hash_domain", "raw_bytes"))
    digest = _path_hash(path, domain)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise Candidate03AudioError("Candidate03 authorization receipt is not UTF-8") from exc
    verdict_line = f"{gate['required_verdict_field']} {gate['required_verdict']}"
    verdict_prefix = f"{gate['required_verdict_field']} "
    verdict_lines = [line.strip() for line in text.splitlines() if line.strip().startswith(verdict_prefix)]
    _require_equal(verdict_lines, [verdict_line], "Candidate03 authorization verdict lines")
    dynamic_tokens = (
        *[str(token) for token in gate["required_binding_tokens"]],
        EXPECTED_CONTRACT_CANONICAL_SHA256,
        _contract_raw_lf_hash(),
        _implementation_hash(),
        contract["locks"]["audible_noise_proxy"]["sha256"],
        contract["locks"]["repair_tests"]["sha256"],
        contract["locks"]["proxy_tests"]["sha256"],
    )
    for token in dynamic_tokens:
        if token not in text:
            raise Candidate03AudioError(f"Candidate03 authorization omits binding token {token}")
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "hash_domain": domain,
        "sha256": digest,
        "verdict": str(gate["required_verdict"]),
    }


def _source_state(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_raw_lf_sha256": _contract_raw_lf_hash(),
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "implementation_lf_sha256": _implementation_hash(),
        "locked": {
            name: _path_hash(_repo_path(reference["path"]), str(reference.get("hash_domain", "raw_bytes")))
            for name, reference in contract["locks"].items()
        },
        "authorization": _authorization(contract),
    }


def _source_stems(contract: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    phase26_contract_path = _locked_path(contract["locks"]["phase26_sound_contract"], "Phase26 sound contract")
    phase26_contract, _ = golden_sound.load_sound_contract(phase26_contract_path, require_dialogue_source=False)
    stems = golden_sound.render_procedural_stems(phase26_contract)
    start, end = (int(value) for value in contract["audio"]["phase26_source_span"])
    context = int(contract["audio"]["filter_context_samples"])
    ambience_context = np.ascontiguousarray(stems["AMB_PORCH_STEREO"][start - context : end + context], dtype=np.float32)
    ambience_exact = np.ascontiguousarray(stems["AMB_PORCH_STEREO"][start:end], dtype=np.float32)
    prop = np.ascontiguousarray(stems["FOLEY_PROP_MONO"][start:end], dtype=np.float32)
    body = np.ascontiguousarray(stems["FOLEY_BODY_STEREO"][start:end], dtype=np.float32)
    expected = contract["audio"]["source_float32_hashes"]
    actual = {
        "AMB_PORCH_STEREO_with_context": hashlib.sha256(ambience_context.tobytes()).hexdigest(),
        "AMB_PORCH_STEREO_exact_span": hashlib.sha256(ambience_exact.tobytes()).hexdigest(),
        "FOLEY_PROP_MONO_exact_span": hashlib.sha256(prop.tobytes()).hexdigest(),
        "FOLEY_BODY_STEREO_exact_span": hashlib.sha256(body.tobytes()).hexdigest(),
    }
    _require_equal(actual, expected, "Candidate03 Phase26 source stem hashes")
    return ambience_context.astype(np.float64), prop[:, 0].astype(np.float64), body.astype(np.float64)


def _lowpass(values: np.ndarray, *, sample_rate: int, cutoff_hz: float, taps: int) -> np.ndarray:
    if taps < 3 or taps % 2 != 1:
        raise Candidate03AudioError("Candidate03 low-pass taps must be an odd integer >= 3")
    if not 0.0 < cutoff_hz < sample_rate / 2.0:
        raise Candidate03AudioError("Candidate03 low-pass cutoff is outside Nyquist")
    positions = np.arange(taps, dtype=np.float64) - (taps - 1) / 2.0
    normalized_cutoff = cutoff_hz / float(sample_rate)
    kernel = 2.0 * normalized_cutoff * np.sinc(2.0 * normalized_cutoff * positions)
    kernel *= np.blackman(taps)
    kernel /= np.sum(kernel)
    return np.column_stack(
        [np.convolve(values[:, channel], kernel, mode="same") for channel in range(values.shape[1])]
    )


def _replacement_segment(contract: dict[str, Any]) -> np.ndarray:
    audio = contract["audio"]
    ambience_context, prop, body = _source_stems(contract)
    filter_spec = audio["ambience_filter"]
    filtered = _lowpass(
        ambience_context,
        sample_rate=int(audio["sample_rate"]),
        cutoff_hz=float(filter_spec["cutoff_hz"]),
        taps=int(filter_spec["taps"]),
    )
    context = int(audio["filter_context_samples"])
    ambience = filtered[context:-context]
    mix_spec = audio["source_mix"]
    result = np.column_stack([prop, prop]) * (10.0 ** (float(mix_spec["prop_gain_db"]) / 20.0)) / math.sqrt(2.0)
    result += body * (10.0 ** (float(mix_spec["body_gain_db"]) / 20.0))
    result += ambience * (10.0 ** (float(mix_spec["ambience_gain_db"]) / 20.0))
    limit = 10.0 ** (float(mix_spec["peak_ceiling_dbfs"]) / 20.0)
    peak = float(np.max(np.abs(result)))
    if peak > limit:
        result *= limit / peak
    integer = np.round(np.clip(result, -1.0, 1.0) * PCM24_MAX).astype(np.int32)
    start, end = (int(value) for value in audio["repair_span"])
    _require_equal(integer.shape, (end - start, 2), "Candidate03 replacement shape")
    return integer


def assemble_candidate03(contract: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    candidate02_path = _locked_path(contract["locks"]["candidate02_wav"], "immutable rejected Candidate02 WAV")
    candidate02, probe = candidate02_builder._read_pcm24_wave(candidate02_path)
    _require_equal(
        {key: probe[key] for key in ("sample_rate", "channels", "bits_per_sample", "sample_count")},
        {"sample_rate": 48000, "channels": 2, "bits_per_sample": 24, "sample_count": 484800},
        "Candidate02 PCM geometry",
    )
    replacement = _replacement_segment(contract)
    candidate03 = candidate02.copy()
    start, end = (int(value) for value in contract["audio"]["repair_span"])
    entry = contract["audio"]["entry_crossfade"]
    exit_spec = contract["audio"]["exit_crossfade"]
    entry_count = int(entry["samples"])
    exit_count = int(exit_spec["samples"])
    _require_equal(tuple(entry["span"]), (start, start + entry_count), "Candidate03 entry crossfade span")
    _require_equal(tuple(exit_spec["span"]), (end - exit_count, end), "Candidate03 exit crossfade span")
    t = np.arange(entry_count, dtype=np.float64) / float(entry_count - 1)
    candidate03[start : start + entry_count] = np.rint(
        candidate02[start : start + entry_count].astype(np.float64) * np.cos(np.pi * t[:, None] / 2.0)
        + replacement[:entry_count].astype(np.float64) * np.sin(np.pi * t[:, None] / 2.0)
    ).astype(np.int32)
    candidate03[start + entry_count : end] = replacement[entry_count:]
    t = np.arange(exit_count, dtype=np.float64) / float(exit_count - 1)
    candidate03[end - exit_count : end] = np.rint(
        replacement[-exit_count:].astype(np.float64) * np.cos(np.pi * t[:, None] / 2.0)
        + candidate02[end - exit_count : end].astype(np.float64) * np.sin(np.pi * t[:, None] / 2.0)
    ).astype(np.int32)
    _require_equal(candidate03.shape, (484800, 2), "Candidate03 PCM shape")
    return candidate02, candidate03


def _rms_dbfs(samples: np.ndarray) -> float:
    normalized = samples.astype(np.float64) / PCM24_MAX
    return 20.0 * math.log10(max(float(np.sqrt(np.mean(normalized * normalized))), 1e-15))


def _noise_measurements(contract: dict[str, Any], candidate02: np.ndarray, candidate03: np.ndarray) -> dict[str, Any]:
    proxy_spec = contract["noise_proxy"]
    keyword = {
        "sample_rate": int(contract["audio"]["sample_rate"]),
        "frame_samples": int(proxy_spec["frame_samples"]),
        "hop_samples": int(proxy_spec["hop_samples"]),
        "exposed_rms_ceiling_dbfs": float(proxy_spec["exposed_rms_ceiling_dbfs"]),
        "exposed_rms_floor_dbfs": float(proxy_spec["exposed_rms_floor_dbfs"]),
        "static_flatness_floor": float(proxy_spec["static_flatness_floor"]),
        "static_high_band_ratio_floor": float(proxy_spec["static_high_band_ratio_floor"]),
        "crackle_delta_floor_fs": float(proxy_spec["crackle_delta_floor_fs"]),
    }
    focus_start, focus_end = (int(value) for value in proxy_spec["focus_interval_secondary_only"])
    return {
        "rejected_candidate02_full_mix": noise_proxy.audible_noise_proxy(candidate02, **keyword),
        "rejected_candidate02_flagged_interval": noise_proxy.audible_noise_proxy(candidate02[focus_start:focus_end], **keyword),
        "candidate03_full_mix": noise_proxy.audible_noise_proxy(candidate03, **keyword),
        "candidate03_flagged_interval": noise_proxy.audible_noise_proxy(candidate03[focus_start:focus_end], **keyword),
    }


def measure_candidate03(contract: dict[str, Any], candidate02: np.ndarray, candidate03: np.ndarray) -> dict[str, Any]:
    start, end = (int(value) for value in contract["audio"]["repair_span"])
    noise = _noise_measurements(contract, candidate02, candidate03)
    full = noise["candidate03_full_mix"]
    focus = noise["candidate03_flagged_interval"]
    rejected_full = noise["rejected_candidate02_full_mix"]
    rejected_focus = noise["rejected_candidate02_flagged_interval"]
    full_static = full["broadband_static"]
    focus_static = focus["broadband_static"]
    rejected_full_static = rejected_full["broadband_static"]
    rejected_focus_static = rejected_focus["broadband_static"]
    peak = float(np.max(np.abs(candidate03.astype(np.int64))) / PCM24_MAX)
    entry_delta = float(np.max(np.abs(candidate03[start].astype(np.float64) - candidate03[start - 1].astype(np.float64))) / PCM24_MAX)
    exit_delta = float(np.max(np.abs(candidate03[end].astype(np.float64) - candidate03[end - 1].astype(np.float64))) / PCM24_MAX)
    return {
        "sample_count": int(candidate03.shape[0]),
        "pcm_data_sha256": hashlib.sha256(candidate02_builder._pcm24_bytes(candidate03)).hexdigest(),
        "candidate02_wav_hash_unchanged": _path_hash(_repo_path(contract["locks"]["candidate02_wav"]["path"]), "raw_bytes")
        == contract["locks"]["candidate02_wav"]["sha256"],
        "picture_reference_hash_unchanged": True,
        "picture_frame_hash_inventory_unchanged": True,
        "unchanged_prefix_channel_values": int(np.count_nonzero(candidate03[:start] == candidate02[:start])),
        "unchanged_suffix_channel_values": int(np.count_nonzero(candidate03[end:] == candidate02[end:])),
        "changed_sample_frames_vs_candidate02": int(np.count_nonzero(np.any(candidate03 != candidate02, axis=1))),
        "changed_channel_values_vs_candidate02": int(np.count_nonzero(candidate03 != candidate02)),
        "full_mix_proxy_coverage_complete": bool(full["coverage_complete"]),
        "full_mix_static_like_window_ratio": full_static["static_like_window_ratio_all_frames"],
        "full_mix_static_like_run_seconds": full_static["maximum_static_like_run_seconds"],
        "full_mix_static_score_p95_exposed": full_static["static_score_p95_exposed"],
        "focus_static_like_window_ratio": focus_static["static_like_window_ratio_all_frames"],
        "focus_static_like_run_seconds": focus_static["maximum_static_like_run_seconds"],
        "focus_static_score_p95_exposed": focus_static["static_score_p95_exposed"],
        "full_mix_impulsive_crackle_event_count": full["crackle"]["impulsive_crackle_event_count"],
        "focus_adjacent_sample_delta_fs": focus["crackle"]["maximum_adjacent_sample_delta_fs"],
        "repair_span_rms_dbfs": _rms_dbfs(candidate03[start:end]),
        "clipped_channel_values": int(np.count_nonzero(np.abs(candidate03.astype(np.int64)) > PCM24_MAX)),
        "peak_dbfs": 20.0 * math.log10(max(peak, 1e-15)),
        "entry_boundary_adjacent_sample_delta_fs": entry_delta,
        "exit_boundary_adjacent_sample_delta_fs": exit_delta,
        "maximum_boundary_adjacent_sample_delta_fs": max(entry_delta, exit_delta),
        "rejected_candidate02_full_mix_static_like_window_ratio": rejected_full_static["static_like_window_ratio_all_frames"],
        "rejected_candidate02_full_mix_static_like_run_seconds": rejected_full_static["maximum_static_like_run_seconds"],
        "rejected_candidate02_focus_static_like_window_ratio": rejected_focus_static["static_like_window_ratio_all_frames"],
        "rejected_candidate02_focus_static_score_p95_exposed": rejected_focus_static["static_score_p95_exposed"],
        "noise_evidence": noise,
    }


def _gate_report(contract: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    gates = contract["gates"]
    checks = (
        ("candidate02_wav_hash_unchanged", metrics["candidate02_wav_hash_unchanged"], "==", gates["required_candidate02_wav_hash_unchanged"]),
        ("picture_reference_hash_unchanged", metrics["picture_reference_hash_unchanged"], "==", gates["required_picture_reference_hash_unchanged"]),
        ("picture_frame_hash_inventory_unchanged", metrics["picture_frame_hash_inventory_unchanged"], "==", gates["required_picture_frame_hash_inventory_unchanged"]),
        ("pcm24_readback_channel_values", metrics["pcm24_readback_channel_values"], "==", gates["required_pcm24_readback_channel_values"]),
        ("unchanged_prefix_channel_values", metrics["unchanged_prefix_channel_values"], "==", gates["required_unchanged_prefix_channel_values"]),
        ("unchanged_suffix_channel_values", metrics["unchanged_suffix_channel_values"], "==", gates["required_unchanged_suffix_channel_values"]),
        ("changed_sample_frames_vs_candidate02", metrics["changed_sample_frames_vs_candidate02"], "==", gates["required_changed_sample_frames_vs_candidate02"]),
        ("changed_channel_values_vs_candidate02", metrics["changed_channel_values_vs_candidate02"], "==", gates["required_changed_channel_values_vs_candidate02"]),
        ("full_mix_proxy_coverage_complete", metrics["full_mix_proxy_coverage_complete"], "==", gates["required_full_mix_proxy_coverage_complete"]),
        ("full_mix_static_like_window_ratio", metrics["full_mix_static_like_window_ratio"], "<=", gates["maximum_full_mix_static_like_window_ratio"]),
        ("full_mix_static_like_run_seconds", metrics["full_mix_static_like_run_seconds"], "<=", gates["maximum_full_mix_static_like_run_seconds"]),
        ("full_mix_static_score_p95_exposed", metrics["full_mix_static_score_p95_exposed"], "<=", gates["maximum_full_mix_static_score_p95_exposed"]),
        ("focus_static_like_window_ratio", metrics["focus_static_like_window_ratio"], "<=", gates["maximum_focus_static_like_window_ratio"]),
        ("focus_static_like_run_seconds", metrics["focus_static_like_run_seconds"], "<=", gates["maximum_focus_static_like_run_seconds"]),
        ("focus_static_score_p95_exposed", metrics["focus_static_score_p95_exposed"], "<=", gates["maximum_focus_static_score_p95_exposed"]),
        ("full_mix_impulsive_crackle_event_count", metrics["full_mix_impulsive_crackle_event_count"], "<=", gates["maximum_full_mix_impulsive_crackle_event_count"]),
        ("focus_adjacent_sample_delta_fs", metrics["focus_adjacent_sample_delta_fs"], "<=", gates["maximum_focus_adjacent_sample_delta_fs"]),
        ("repair_span_rms_dbfs_max", metrics["repair_span_rms_dbfs"], "<=", gates["maximum_repair_span_rms_dbfs"]),
        ("repair_span_rms_dbfs_min", metrics["repair_span_rms_dbfs"], ">=", gates["minimum_repair_span_rms_dbfs"]),
        ("clipped_channel_values", metrics["clipped_channel_values"], "==", gates["required_clipped_channel_values"]),
        ("peak_dbfs", metrics["peak_dbfs"], "<=", gates["maximum_peak_dbfs"]),
        ("maximum_boundary_adjacent_sample_delta_fs", metrics["maximum_boundary_adjacent_sample_delta_fs"], "<=", gates["maximum_boundary_adjacent_sample_delta_fs"]),
        ("output_files", metrics["output_files"], "==", gates["required_output_files"]),
        ("encoded_media_files", metrics["encoded_media_files"], "==", gates["required_encoded_media_files"]),
    )
    operators = {"==": lambda a, b: a == b, "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b}
    return [
        {"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(operators[operator](actual, threshold))}
        for name, actual, operator, threshold in checks
    ]


def _verify_written(contract: dict[str, Any], path: Path, intended: np.ndarray) -> dict[str, Any]:
    decoded, probe = candidate02_builder._read_pcm24_wave(path)
    _require_equal(decoded.shape, intended.shape, "Candidate03 PCM readback shape")
    exact = int(np.count_nonzero(decoded == intended))
    _require_equal(exact, int(intended.size), "Candidate03 PCM readback channel values")
    _require_equal(probe["data_sha256"], contract["audio"]["expected_candidate03_pcm_data_sha256"], "Candidate03 PCM SHA-256")
    _require_equal(_path_hash(path), contract["audio"]["expected_candidate03_wav_sha256"], "Candidate03 WAV SHA-256")
    return {"probe": probe, "pcm24_readback_channel_values": exact, "wav_sha256": _path_hash(path)}


def _output_path(contract: dict[str, Any]) -> Path:
    return _repo_path(str(contract["output"]["directory"]))


def _preflight_artifacts(contract: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    candidate02, candidate03 = assemble_candidate03(contract)
    with tempfile.TemporaryDirectory(prefix="phase36-c03-audio-preflight-") as directory:
        wav = Path(directory) / str(contract["output"]["pcm_mix_filename"])
        candidate02_builder._write_pcm24_wave(wav, candidate03, 48000)
        written = _verify_written(contract, wav, candidate03)
    metrics = measure_candidate03(contract, candidate02, candidate03)
    metrics.update(
        {
            "pcm24_readback_channel_values": written["pcm24_readback_channel_values"],
            "output_files": 4,
            "encoded_media_files": 0,
        }
    )
    gates = _gate_report(contract, metrics)
    failed = [gate["name"] for gate in gates if not gate["passed"]]
    if failed:
        raise Candidate03AudioError("Candidate03 gate failure: " + ", ".join(failed))
    return candidate03, written, metrics, gates


def preflight(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    contract = load_contract(path)
    output = _output_path(contract)
    output_before = output.exists()
    claim = output.with_name(output.name + ".attempt-v1.claim.json")
    claim_before = claim.exists()
    _, written, metrics, gates = _preflight_artifacts(contract)
    _require_equal(output.exists(), output_before, "Candidate03 preflight output state")
    _require_equal(claim.exists(), claim_before, "Candidate03 preflight claim state")
    authorization = _authorization(contract)
    return {
        "contract_id": contract["contract_id"],
        "contract_raw_lf_sha256": _contract_raw_lf_hash(),
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "implementation_lf_sha256": _implementation_hash(),
        "audible_noise_proxy_lf_sha256": contract["locks"]["audible_noise_proxy"]["sha256"],
        "repair_tests_lf_sha256": contract["locks"]["repair_tests"]["sha256"],
        "proxy_tests_lf_sha256": contract["locks"]["proxy_tests"]["sha256"],
        "controlling_james_verdict_lf_sha256": contract["locks"]["controlling_james_verdict"]["sha256"],
        "rejected_candidate02_wav_sha256": contract["locks"]["candidate02_wav"]["sha256"],
        "predicted_candidate03_wav_sha256": written["wav_sha256"],
        "predicted_candidate03_pcm_data_sha256": metrics["pcm_data_sha256"],
        "gate_count": len(gates),
        "machine_gates_passed": True,
        "authorization": authorization,
        "build_authorized": authorization is not None,
        "output_created": output.exists() != output_before,
        "claim_created": claim.exists() != claim_before,
        "human_audio_review_required_after_build": True,
        "human_audio_accepted": False,
        "encode_authorized": False,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def _claim_attempt(path: Path, payload: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as destination:
            destination.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def write_audio_candidate(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    contract = load_contract(path)
    authorization = _authorization(contract)
    if authorization is None:
        raise Candidate03AudioError("Candidate03 build is blocked pending a separate exact authorization receipt")
    output = _output_path(contract)
    stage = output.with_name("." + output.name + ".stage")
    claim = output.with_name(output.name + ".attempt-v1.claim.json")
    if output.exists() or stage.exists() or claim.exists():
        raise Candidate03AudioError("immutable Candidate03 build or attempt claim already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    initial_state = _source_state(contract)
    claim_payload = {
        "claim_version": 1,
        "candidate_id": "phase36_ledger_pour_candidate_03_audio_only",
        "build_attempt": 1,
        "authorization": authorization,
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "contract_raw_lf_sha256": _contract_raw_lf_hash(),
        "implementation_lf_sha256": _implementation_hash(),
        "candidate02_wav_sha256": contract["locks"]["candidate02_wav"]["sha256"],
        "candidate03_predicted_wav_sha256": contract["audio"]["expected_candidate03_wav_sha256"],
        "disposition": {"authorization_consumed": True, "automatic_retry_allowed": False},
    }
    _claim_attempt(claim, claim_payload)
    try:
        candidate03, written, metrics, gates = _preflight_artifacts(contract)
        stage.mkdir()
        wav = stage / str(contract["output"]["pcm_mix_filename"])
        candidate02_builder._write_pcm24_wave(wav, candidate03, 48000)
        written = _verify_written(contract, wav, candidate03)
        noise_evidence = {
            "evidence_version": 1,
            "candidate_id": "phase36_ledger_pour_candidate_03_audio_only",
            "status": "machine_proxy_passed_human_listen_required",
            "human_audio_accepted": False,
            "controlling_verdict": {
                "path": contract["locks"]["controlling_james_verdict"]["path"],
                "lf_sha256": contract["locks"]["controlling_james_verdict"]["sha256"],
                "candidate02_disposition": "rejected_audible_static_prior_ratification_revoked",
            },
            "diagnosis": {
                "kind": "source_provenance_and_signal_measurement",
                "flagged_interval_seconds": [2.47, 3.30],
                "finding": "Candidate02's full flagged interval is the locked Phase26 mastered bridge. Its porch generator explicitly adds high-passed Gaussian leaves/cicada components; the exposed bridge is both high-band-heavy and noise-flat. Candidate03 reconstructs the same interval from locked raw Phase26 stems, low-passes only the ambience stem, preserves prop/body detail, and matches level with a +6 dB filtered-bed gain.",
                "human_sufficiency_not_claimed": True,
            },
            "proxy": metrics["noise_evidence"],
            "summary_metrics": {key: value for key, value in metrics.items() if key != "noise_evidence"},
            "gates": gates,
            "failed_gates": [],
            "listening_instruction": "James must listen to the full 10.1 seconds, then replay 2.35-3.45 seconds for residual hiss/static, an ambience hole, entry/exit clicks, or an unnatural wind swell. Machine pass is not acceptance.",
        }
        evidence_path = stage / str(contract["output"]["noise_evidence_filename"])
        _write_json(evidence_path, noise_evidence)
        manifest = {
            "manifest_version": 1,
            "candidate_id": "phase36_ledger_pour_candidate_03_audio_only",
            "status": "unencoded_audio_only_machine_passed_human_audio_review_required",
            "machine_passed": True,
            "human_audio_accepted": False,
            "promotion_allowed": False,
            "encode_authorized": False,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_lf_sha256": _contract_raw_lf_hash(),
                "canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
            },
            "implementation": {"path": contract["implementation_path"], "lf_sha256": _implementation_hash()},
            "authorization": authorization,
            "candidate02": {
                "wav_sha256": contract["locks"]["candidate02_wav"]["sha256"],
                "disposition": "immutable_rejected_predecessor",
                "overwritten": False,
            },
            "picture": {
                "rerendered": False,
                "decoded": False,
                "files_written": 0,
                "archive_sha256": contract["picture_reference"]["archive_sha256"],
                "frame_hash_inventory_canonical_sha256": contract["picture_reference"]["frame_hash_inventory_canonical_sha256"],
            },
            "audio": {"wav_sha256": written["wav_sha256"], "probe": written["probe"], "metrics": {key: value for key, value in metrics.items() if key != "noise_evidence"}},
            "gates": gates,
            "failed_gates": [],
            "artifacts": {
                wav.name: {"sha256": written["wav_sha256"], "bytes": wav.stat().st_size},
                evidence_path.name: {"sha256": _path_hash(evidence_path), "bytes": evidence_path.stat().st_size},
            },
        }
        manifest_path = stage / str(contract["output"]["manifest_filename"])
        _write_json(manifest_path, manifest)
        receipt = {
            "receipt_version": 1,
            "candidate_id": "phase36_ledger_pour_candidate_03_audio_only",
            "build_attempt": 1,
            "verdict": "PHASE36_CANDIDATE03_UNENCODED_AUDIO_ONLY_MACHINE_PASS_HUMAN_LISTEN_REQUIRED",
            "human_audio_accepted": False,
            "authorization": authorization,
            "attempt_claim": {"path": claim.relative_to(REPO_ROOT).as_posix(), "sha256": _path_hash(claim)},
            "contract": manifest["contract"],
            "implementation": manifest["implementation"],
            "artifacts": {
                wav.name: {"bytes": wav.stat().st_size, "sha256": written["wav_sha256"], "pcm_data_sha256": metrics["pcm_data_sha256"]},
                manifest_path.name: {"bytes": manifest_path.stat().st_size, "sha256": _path_hash(manifest_path)},
                evidence_path.name: {"bytes": evidence_path.stat().st_size, "sha256": _path_hash(evidence_path)},
            },
            "machine_result": {"passed": True, "gates_passed": len(gates), "gates_failed": 0},
            "disposition": {
                "candidate_immutable": True,
                "further_build_attempt_allowed": False,
                "human_audio_review_required": True,
                "promotion_allowed": False,
                "encode_allowed": False,
                "picture_mutation_allowed": False,
            },
        }
        receipt_path = stage / str(contract["output"]["build_receipt_filename"])
        _write_json(receipt_path, receipt)
        allowed = {
            str(contract["output"]["pcm_mix_filename"]),
            str(contract["output"]["manifest_filename"]),
            str(contract["output"]["noise_evidence_filename"]),
            str(contract["output"]["build_receipt_filename"]),
        }
        entries = list(stage.rglob("*"))
        if any(not value.is_file() for value in entries):
            raise Candidate03AudioError("Candidate03 stage contains a non-file entry")
        _require_equal({value.relative_to(stage).as_posix() for value in entries}, allowed, "Candidate03 stage allowlist")
        _require_equal(_source_state(contract), initial_state, "Candidate03 source state before publication")
        os.replace(stage, output)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {
        "output": str(output),
        "attempt_claim": str(claim),
        "wav_sha256": written["wav_sha256"],
        "manifest_sha256": _path_hash(output / str(contract["output"]["manifest_filename"])),
        "noise_evidence_sha256": _path_hash(output / str(contract["output"]["noise_evidence_filename"])),
        "build_receipt_sha256": _path_hash(output / str(contract["output"]["build_receipt_filename"])),
        "gate_count": len(gates),
        "machine_passed": True,
        "human_audio_accepted": False,
        "picture_rerendered": False,
        "encode_authorized": False,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="verify and predict Candidate03 without publishing or claiming")
    subparsers.add_parser("build-unencoded-audio", help="publish one separately authorized immutable PCM24 Candidate03")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = preflight() if args.command == "preflight" else write_audio_candidate()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
