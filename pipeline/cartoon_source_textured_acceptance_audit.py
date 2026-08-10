from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

import cv2
import numpy as np

import pipeline.cartoon_source_textured_face as phase34


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase34_successor_audit_v2.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_source_textured_acceptance_audit.py"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "82ffc3845ace5b38f4ca0490ad87db83abb573c60c183b57c7b05955c6dfc40e"


class SourceTexturedAcceptanceAuditError(RuntimeError):
    pass


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_lf_normalized(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_frame_hash(frame: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SourceTexturedAcceptanceAuditError(f"locked audit path escapes repository: {relative}") from exc
    return path


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SourceTexturedAcceptanceAuditError(f"successor audit mismatch for {label}: {actual!r} != {expected!r}")


def _locked_hash(reference: dict[str, Any]) -> str:
    path = _repo_path(reference["path"])
    if not path.is_file():
        raise SourceTexturedAcceptanceAuditError(f"locked successor-audit input is missing: {path}")
    domain = reference.get("hash_domain", "raw_bytes")
    if domain == "raw_bytes":
        return _sha256(path)
    if domain == "lf_normalized_text":
        return _sha256_lf_normalized(path)
    raise SourceTexturedAcceptanceAuditError(f"unsupported hash domain: {domain}")


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    resolved = Path(path).resolve()
    expected = (REPO_ROOT / CONTRACT_RELATIVE_PATH).resolve()
    _require_equal(resolved, expected, "pinned contract path")
    contract = json.loads(resolved.read_text(encoding="utf-8"))
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "canonical contract SHA-256")
    _require_equal(contract["contract_version"], 2, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase34_successor_audit_v2", "contract id")
    _require_equal(contract["clock"], {
        "width": 1920, "height": 1080, "fps": 24, "frame_count": 96, "duration_seconds": 4.0,
    }, "clock")
    temporal = contract["temporal_codec_gate"]
    _require_equal(temporal["face_roi_xyxy"], [500, 185, 870, 620], "face ROI")
    _require_equal(temporal["pair_count"], 95, "temporal pair count")
    _require_equal(temporal["maximum_absolute_pairwise_decoded_minus_source_delta"], 2.0, "codec delta ceiling")
    _require_equal(temporal["absolute_ceiling_is_advisory_only"], True, "absolute ceiling policy")
    _require_equal(contract["original_attempt_state"]["retry_allowed"], False, "retry policy")
    _require_equal(contract["promotion"]["new_render_or_encode_authorized"], False, "render/encode authorization")
    _require_equal(contract["promotion"]["accept_full_cartoon_production_delivery"], False, "production promotion")
    for name, reference in contract["locks"].items():
        _require_equal(_locked_hash(reference), reference["sha256"], f"locked {name} SHA-256")
    return contract


def _maximum_8x8_mean_absolute_rgb_delta(first: np.ndarray, second: np.ndarray) -> float:
    delta = np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(axis=2)
    return float(cv2.boxFilter(delta, -1, (8, 8), normalize=True).max())


def _output_path(contract: dict[str, Any]) -> Path:
    path = (REPO_ROOT / contract["output"]["directory"]).resolve()
    expected = (REPO_ROOT / "../../outputs/edit/phase34-candidate08-successor-audit-v2").resolve()
    _require_equal(path, expected, "pinned output directory")
    return path


def _original_attempt_gates(contract: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    state = contract["original_attempt_state"]
    failed = [gate for gate in report["decoded_gates"] if gate.get("passed") is not True]
    non_temporal = [gate for gate in report["decoded_gates"] if gate.get("name") != state["required_failed_gate"]]
    checks = [
        ("original_machine_rejection_preserved", report.get("machine_passed"), "==", state["required_machine_passed"]),
        ("original_gate_count", report.get("gate_count"), "==", state["required_gate_count"]),
        ("original_gates_passed", report.get("gates_passed"), "==", state["required_gates_passed"]),
        ("original_gates_failed", report.get("gates_failed"), "==", state["required_gates_failed"]),
        ("only_expected_original_gate_failed", [gate.get("name") for gate in failed], "==", [state["required_failed_gate"]]),
        ("all_original_non_temporal_decoded_gates_pass", all(gate.get("passed") is True for gate in non_temporal), "==", True),
        ("one_original_encoder_process", report.get("video", {}).get("encoding_process_count"), "==", state["required_encoder_process_count"]),
        ("original_attempt_not_production_accepted", report.get("accepted_production_delivery"), "==", False),
    ]
    return [
        {"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": actual == threshold}
        for name, actual, operator, threshold in checks
    ]


def run_successor_audit() -> dict[str, Any]:
    contract = load_contract()
    locks = contract["locks"]
    manifest_path = _repo_path(locks["candidate08_manifest"]["path"])
    archive_path = _repo_path(locks["candidate08_archive"]["path"])
    video_path = _repo_path(locks["attempt01_video"]["path"])
    original_report_path = _repo_path(locks["attempt01_report"]["path"])
    failure_path = _repo_path(locks["attempt01_failure_receipt"]["path"])
    claude_review_path = _repo_path(locks["claude_motion_review"]["path"])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_report = json.loads(original_report_path.read_text(encoding="utf-8"))
    failure = json.loads(failure_path.read_text(encoding="utf-8"))
    review_text = claude_review_path.read_text(encoding="utf-8")
    _require_equal(manifest["development_label"], "candidate-08", "Candidate08 manifest label")
    _require_equal(len(manifest["frames"]), 96, "manifest frame count")
    _require_equal(original_report["video"]["sha256"], locks["attempt01_video"]["sha256"], "original report video SHA-256")
    _require_equal(failure["status"], "single_encode_attempt_rejected_no_retry_allowed", "failure receipt status")
    _require_equal(failure["attempt"]["encoding_process_count"], 1, "failure receipt encoder count")
    required_verdict = contract["human_motion_review"]["required_verdict"]
    if f"VERDICT: {required_verdict}" not in review_text:
        raise SourceTexturedAcceptanceAuditError("Claude review does not contain the required motion verdict")
    for criterion in ("Identity stability: PASS", "Viseme legibility: PASS", "Upper-face stillness: PASS", "Jawline/beard seam: PASS"):
        if criterion not in review_text:
            raise SourceTexturedAcceptanceAuditError(f"Claude review is missing standing criterion: {criterion}")

    try:
        header, source_frames = phase34._read_lossless_frame_archive(archive_path)
    except Exception as exc:
        raise SourceTexturedAcceptanceAuditError(f"Candidate08 archive failed decoding: {exc}") from exc
    _require_equal(header, {
        "format": "phase34_rgb24_xor_previous_gzip_v1",
        "width": 1920,
        "height": 1080,
        "channels": 3,
        "frame_count": 96,
        "frame_bytes": 6220800,
        "xor_seed": "all_zero_rgb24_frame",
    }, "archive header")
    source_hashes = [
        {"frame": index, "rgb_sha256": _raw_frame_hash(frame)}
        for index, frame in enumerate(source_frames, start=1)
    ]
    _require_equal(source_hashes, manifest["frames"], "all source RGB hashes")

    expected_decoded_hashes = original_report["decoded_measurements"]["decoded_rgb24_hashes"]
    _require_equal([item["frame"] for item in expected_decoded_hashes], list(range(1, 97)), "reported decoded frame order")
    roi = contract["temporal_codec_gate"]["face_roi_xyxy"]
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise SourceTexturedAcceptanceAuditError("OpenCV could not open the locked attempt MP4")
    pair_measurements: list[dict[str, Any]] = []
    decoded_hashes: list[dict[str, Any]] = []
    previous_source_face: np.ndarray | None = None
    previous_decoded_face: np.ndarray | None = None
    decoded_count = 0
    try:
        while True:
            ok, bgr = capture.read()
            if not ok:
                break
            if decoded_count >= 96:
                raise SourceTexturedAcceptanceAuditError("attempt MP4 contains more than 96 decoded frames")
            if bgr.shape != (1080, 1920, 3):
                raise SourceTexturedAcceptanceAuditError(f"decoded frame {decoded_count + 1} shape changed: {bgr.shape}")
            decoded = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            decoded_count += 1
            decoded_hash = {"frame": decoded_count, "rgb_sha256": _raw_frame_hash(decoded)}
            decoded_hashes.append(decoded_hash)
            _require_equal(decoded_hash, expected_decoded_hashes[decoded_count - 1], f"decoded frame {decoded_count} hash")
            source_face = source_frames[decoded_count - 1][roi[1]:roi[3], roi[0]:roi[2]]
            decoded_face = decoded[roi[1]:roi[3], roi[0]:roi[2]]
            if previous_source_face is not None and previous_decoded_face is not None:
                source_pop = _maximum_8x8_mean_absolute_rgb_delta(previous_source_face, source_face)
                decoded_pop = _maximum_8x8_mean_absolute_rgb_delta(previous_decoded_face, decoded_face)
                pair_measurements.append({
                    "frames": [decoded_count - 1, decoded_count],
                    "source_pop": source_pop,
                    "decoded_pop": decoded_pop,
                    "decoded_minus_source": decoded_pop - source_pop,
                    "absolute_codec_delta": abs(decoded_pop - source_pop),
                })
            previous_source_face = source_face.copy()
            previous_decoded_face = decoded_face.copy()
    finally:
        capture.release()
    _require_equal(decoded_count, 96, "full decoded frame count")
    _require_equal(len(pair_measurements), 95, "evaluated temporal pair count")

    maximum_codec = max(item["absolute_codec_delta"] for item in pair_measurements)
    maximum_codec_item = next(item for item in pair_measurements if item["absolute_codec_delta"] == maximum_codec)
    maximum_source = max(item["source_pop"] for item in pair_measurements)
    maximum_source_item = next(item for item in pair_measurements if item["source_pop"] == maximum_source)
    maximum_decoded = max(item["decoded_pop"] for item in pair_measurements)
    maximum_decoded_item = next(item for item in pair_measurements if item["decoded_pop"] == maximum_decoded)
    if not all(math.isfinite(value) for item in pair_measurements for value in (
        item["source_pop"], item["decoded_pop"], item["decoded_minus_source"], item["absolute_codec_delta"],
    )):
        raise SourceTexturedAcceptanceAuditError("successor temporal metrics contain a non-finite value")

    gates = _original_attempt_gates(contract, original_report)
    gates.extend([
        {
            "name": "all_source_frame_hashes_match_manifest",
            "actual": len(source_hashes), "operator": "==", "threshold": 96,
            "passed": source_hashes == manifest["frames"],
        },
        {
            "name": "all_decoded_frame_hashes_match_original_report",
            "actual": len(decoded_hashes), "operator": "==", "threshold": 96,
            "passed": decoded_hashes == expected_decoded_hashes,
        },
        {
            "name": "same_domain_pairwise_codec_delta",
            "actual": maximum_codec, "operator": "<=",
            "threshold": contract["temporal_codec_gate"]["maximum_absolute_pairwise_decoded_minus_source_delta"],
            "passed": maximum_codec <= contract["temporal_codec_gate"]["maximum_absolute_pairwise_decoded_minus_source_delta"],
        },
        {
            "name": "human_motion_verdict",
            "actual": required_verdict, "operator": "==", "threshold": required_verdict,
            "passed": True,
        },
        {
            "name": "no_new_render_or_encode",
            "actual": False, "operator": "==", "threshold": False,
            "passed": True,
        },
    ])
    machine_passed = all(gate["passed"] is True for gate in gates)

    output = _output_path(contract)
    if output.exists():
        raise SourceTexturedAcceptanceAuditError(f"immutable successor audit already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    try:
        report = {
            "audit_version": 2,
            "status": "successor_machine_audit_and_human_motion_review_passed" if machine_passed else "successor_audit_failed",
            "machine_passed": machine_passed,
            "human_motion_accepted": required_verdict in review_text,
            "original_attempt_remains_mechanically_rejected": True,
            "accepted_reusable_silent_facial_motion_subsystem": machine_passed,
            "accepted_full_cartoon_production_delivery": False,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": _sha256(REPO_ROOT / CONTRACT_RELATIVE_PATH),
                "canonical_sha256": _canonical_hash(contract),
            },
            "implementation": {
                "path": IMPLEMENTATION_RELATIVE_PATH,
                "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH),
            },
            "locked_inputs": contract["locks"],
            "clock": contract["clock"],
            "metric": contract["temporal_codec_gate"],
            "measurements": {
                "source_frame_count": len(source_hashes),
                "decoded_frame_count": len(decoded_hashes),
                "pair_count": len(pair_measurements),
                "maximum_source_pop": maximum_source,
                "maximum_source_pop_frame_pair": maximum_source_item["frames"],
                "maximum_decoded_pop": maximum_decoded,
                "maximum_decoded_pop_frame_pair": maximum_decoded_item["frames"],
                "maximum_absolute_pairwise_codec_delta": maximum_codec,
                "maximum_absolute_pairwise_codec_delta_frame_pair": maximum_codec_item["frames"],
                "source_absolute_ceiling_advisory_passed": maximum_source <= contract["temporal_codec_gate"]["absolute_source_or_decoded_pop_ceiling"],
                "decoded_absolute_ceiling_advisory_passed": maximum_decoded <= contract["temporal_codec_gate"]["absolute_source_or_decoded_pop_ceiling"],
                "pair_measurements": pair_measurements,
                "source_rgb24_hashes": source_hashes,
                "decoded_rgb24_hashes": decoded_hashes,
            },
            "gates": gates,
            "gate_count": len(gates),
            "gates_passed": sum(gate["passed"] is True for gate in gates),
            "gates_failed": sum(gate["passed"] is not True for gate in gates),
            "promotion_scope": {
                "reusable_silent_facial_motion_subsystem": machine_passed,
                "full_cartoon": False,
                "new_render_or_encode_performed": False,
                "voice_body_camera_scene_sound_integration_still_required": True,
                "reinforcement_learning_used": False,
                "paid_service_or_api_used": False,
            },
        }
        report_path = stage / contract["output"]["report_filename"]
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        reread = json.loads(report_path.read_text(encoding="utf-8"))
        _require_equal(reread["machine_passed"], True, "published audit machine result")
        _require_equal(reread["gates_failed"], 0, "published audit failed gate count")
        if output.exists():
            raise SourceTexturedAcceptanceAuditError(f"immutable audit output appeared during publication: {output}")
        stage.rename(output)
        return {
            "output_directory": str(output),
            "report": str(output / report_path.name),
            "report_sha256": _sha256(output / report_path.name),
            "machine_passed": True,
            "human_motion_accepted": True,
            "accepted_reusable_silent_facial_motion_subsystem": True,
            "accepted_full_cartoon_production_delivery": False,
            "maximum_absolute_pairwise_codec_delta": maximum_codec,
            "no_new_render_or_encode": True,
        }
    except BaseException:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Candidate08 attempt 01 under the Phase34 same-domain codec-delta successor contract.")
    parser.parse_args()
    print(json.dumps(run_successor_audit(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
