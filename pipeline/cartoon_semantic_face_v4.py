from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import numpy as np
from PIL import Image

import pipeline.cartoon_semantic_face as v3


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase33_semantic_face_v4.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_semantic_face_v4.py"


class SemanticFaceV4Error(RuntimeError):
    pass


@dataclass
class PreparedV4:
    contract: dict[str, Any]
    contract_path: Path
    base: v3.PreparedSemanticFace
    frame_hashes: list[str]
    preencode_measurements: dict[str, Any]


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SemanticFaceV4Error(f"complete Phase33 v4 contract required: {label}: {actual!r} != {expected!r}")


def _repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SemanticFaceV4Error(f"repository path escaped: {relative}") from exc
    return path


def _validate_contract(contract: dict[str, Any]) -> None:
    _require_equal(contract["contract_version"], 1, "contract version")
    _require_equal(contract["contract_id"], "june_oxley_phase33_semantic_face_v4", "contract id")
    _require_equal(contract["delivery_attempt_version"], 4, "attempt version")
    policy = contract["pixel_policy"]
    _require_equal(policy["visual_changes_from_reviewed_v3_allowed"], False, "visual changes")
    _require_equal(policy["required_raw_frame_count"], 60, "raw frame count")
    _require_equal(len(policy["required_exact_rgb_frame_hashes"]), 60, "raw frame hashes")
    _require_equal(contract["clock"], {
        "width": 1920, "height": 1080, "fps": 30, "frame_count": 60,
        "duration_seconds": 2.0, "audio_stream_count": 0,
    }, "clock")
    motion = contract["motion_evidence"]
    _require_equal(motion["v3_invalid_decoded_threshold"], 52.0, "v3 rejected threshold")
    _require_equal(motion["v4_predeclared_preencode_threshold"], 150.0, "v4 preencode threshold")
    _require_equal(motion["v4_predeclared_decoded_threshold"], 150.0, "v4 decoded threshold")
    _require_equal(motion["full_replacement_reference"], 255.0, "replacement reference")
    _require_equal(contract["decoded_gates"]["maximum_decoded_adjacent_face_8x8_mean_delta"], 150.0, "decoded local motion")
    _require_equal(contract["delivery"]["one_video_encode_without_retry"], True, "one encode")
    _require_equal(contract["delivery"]["staged_atomic_directory_publication"], True, "atomic publication")
    failure = contract["failure_policy"]
    _require_equal(failure["mode"], "fail_closed", "failure mode")
    _require_equal(failure["automatic_reencode_allowed"], False, "automatic reencode")
    _require_equal(failure["caller_selected_output_directory_allowed"], False, "caller output")
    _require_equal(contract["promotion_policy"]["voiced_reencode_allowed"], False, "voice")
    _require_equal(contract["promotion_policy"]["reinforcement_learning_allowed"], False, "RL")
    for name, reference in contract["locks"].items():
        path = _repo_path(reference["path"])
        if not path.is_file():
            raise SemanticFaceV4Error(f"missing lock {name}: {path}")
        actual = _sha256(path)
        if actual != reference["sha256"]:
            raise SemanticFaceV4Error(f"{name} SHA-256 mismatch: {actual} != {reference['sha256']}")


def load_contract(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    contract = json.loads(Path(path).resolve().read_text(encoding="utf-8"))
    _validate_contract(contract)
    return contract


def compose_frame(prepared: PreparedV4, frame_number: int) -> Image.Image:
    return v3.compose_semantic_frame(prepared.base, frame_number)


def _measure_preencode(base: v3.PreparedSemanticFace) -> dict[str, Any]:
    face = [500, 185, 870, 620]
    maximum = 0.0
    pair = [1, 1]
    previous: np.ndarray | None = None
    for frame_number in range(1, 61):
        frame = np.asarray(v3.compose_semantic_frame(base, frame_number), dtype=np.uint8)
        crop = frame[face[1]:face[3], face[0]:face[2]]
        if previous is not None:
            value = v3._max_8x8_delta(previous, crop)
            if value > maximum:
                maximum = value
                pair = [frame_number - 1, frame_number]
        previous = crop
    return {
        "maximum_adjacent_face_8x8_mean_delta": maximum,
        "maximum_adjacent_face_8x8_mean_delta_frame_pair": pair,
        "threshold": 150.0,
        "passed": maximum <= 150.0,
        "full_replacement_reference": 255.0,
        "all_frame_hashes_verified": True,
    }


def prepare_v4(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> PreparedV4:
    contract_path = Path(path).resolve()
    contract = load_contract(contract_path)
    base = v3.prepare_semantic_face(_repo_path(contract["locks"]["v3_contract"]["path"]))
    required = contract["pixel_policy"]["required_exact_rgb_frame_hashes"]
    actual = []
    for frame_number, expected in enumerate(required, start=1):
        digest = v3._raw_frame_hash(np.asarray(v3.compose_semantic_frame(base, frame_number), dtype=np.uint8))
        if digest != expected:
            raise SemanticFaceV4Error(f"v4 frame {frame_number} is not byte-identical to reviewed v3")
        actual.append(digest)
    measurements = _measure_preencode(base)
    if not measurements["passed"]:
        raise SemanticFaceV4Error(f"v4 preencode local-motion gate failed: {measurements}")
    return PreparedV4(contract, contract_path, base, actual, measurements)


def _preview_path(contract: dict[str, Any]) -> Path:
    return (REPO_ROOT / contract["preview"]["directory"]).resolve()


def _output_path(contract: dict[str, Any]) -> Path:
    return (REPO_ROOT / contract["delivery"]["output_directory"]).resolve()


def write_preview(path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH) -> dict[str, Any]:
    prepared = prepare_v4(path)
    output = _preview_path(prepared.contract)
    if output.exists():
        raise SemanticFaceV4Error(f"immutable v4 preview exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    try:
        frames = [compose_frame(prepared, number) for number in range(1, 61)]
        all_sheet = v3._contact_sheet(frames, 12, (160, 90), [f"F{number:02d}" for number in range(1, 61)])
        all_path = stage / prepared.contract["preview"]["contact_sheet_filename"]
        all_sheet.save(all_path, format="PNG", optimize=True)
        key_numbers = [1, 8, 13, 14, 19, 22, 28, 33, 38, 43, 48, 52, 56, 60]
        crop = (557, 201, 919, 614)
        keys = [frames[number - 1].crop(crop) for number in key_numbers]
        key_sheet = v3._contact_sheet(keys, 7, (362, 413), [f"F{number:02d}" for number in key_numbers])
        key_path = stage / prepared.contract["preview"]["key_sheet_filename"]
        key_sheet.save(key_path, format="PNG", optimize=True)
        manifest = {
            "manifest_version": 1,
            "contract": {"path": CONTRACT_RELATIVE_PATH, "raw_sha256": _sha256(prepared.contract_path), "canonical_sha256": _canonical_hash(prepared.contract)},
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH)},
            "base_v3": {
                "contract_sha256": prepared.contract["locks"]["v3_contract"]["sha256"],
                "implementation_sha256": prepared.contract["locks"]["v3_implementation"]["sha256"],
                "rejection_receipt_sha256": prepared.contract["locks"]["v3_rejection_receipt"]["sha256"],
            },
            "clock": prepared.contract["clock"],
            "frame_hash_domain": "raw_rgb24_1920x1080_row_major",
            "frames": [{"frame": number, "rgb_sha256": digest} for number, digest in enumerate(prepared.frame_hashes, start=1)],
            "pixels_byte_identical_to_reviewed_v3": True,
            "preencode_measurements": prepared.preencode_measurements,
            "all_60_contact_sheet": {"file": all_path.name, "sha256": _sha256(all_path)},
            "key_pose_sheet": {"file": key_path.name, "sha256": _sha256(key_path)},
            "final_encode_allowed_without_bound_review_receipt": False,
        }
        manifest_path = stage / prepared.contract["preview"]["manifest_filename"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(stage, output)
        return {
            "preview_directory": str(output),
            "manifest": str(output / manifest_path.name),
            "manifest_sha256": _sha256(output / manifest_path.name),
            "contact_sheet": str(output / all_path.name),
            "key_sheet": str(output / key_path.name),
        }
    except Exception:
        if stage.exists():
            shutil.rmtree(stage)
        raise


def _verify_review(prepared: PreparedV4) -> tuple[dict[str, Any], dict[str, Any], Path]:
    directory = _preview_path(prepared.contract)
    manifest_path = directory / prepared.contract["preview"]["manifest_filename"]
    if not manifest_path.is_file():
        raise SemanticFaceV4Error("v4 preview manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["contract"]["raw_sha256"] != _sha256(prepared.contract_path):
        raise SemanticFaceV4Error("v4 preview contract changed")
    if manifest["implementation"]["sha256"] != _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH):
        raise SemanticFaceV4Error("v4 implementation changed after preview")
    if [entry["rgb_sha256"] for entry in manifest["frames"]] != prepared.frame_hashes:
        raise SemanticFaceV4Error("v4 preview frame hashes changed")
    for key in ("all_60_contact_sheet", "key_pose_sheet"):
        artifact = directory / manifest[key]["file"]
        if not artifact.is_file() or _sha256(artifact) != manifest[key]["sha256"]:
            raise SemanticFaceV4Error(f"v4 preview artifact changed: {key}")
    review_path = _repo_path(prepared.contract["preview"]["review_receipt"])
    if not review_path.is_file():
        raise SemanticFaceV4Error("v4 review receipt is missing")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review.get("status") != "byte_identical_v3_frames_reviewed_v4_encode_once_allowed":
        raise SemanticFaceV4Error("v4 review did not authorize encoding")
    if review.get("manifest_sha256") != _sha256(manifest_path):
        raise SemanticFaceV4Error("v4 review manifest hash changed")
    if review.get("contract_raw_sha256") != _sha256(prepared.contract_path):
        raise SemanticFaceV4Error("v4 review contract hash changed")
    if review.get("implementation_sha256") != _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH):
        raise SemanticFaceV4Error("v4 review implementation hash changed")
    return manifest, review, manifest_path


def _decoded_gates(contract: dict[str, Any], metrics: dict[str, Any], probe: dict[str, Any]) -> list[dict[str, Any]]:
    gates = contract["decoded_gates"]
    video = [stream for stream in probe["streams"] if stream.get("codec_type") == "video"]
    audio = [stream for stream in probe["streams"] if stream.get("codec_type") == "audio"]
    stream = video[0] if len(video) == 1 else {}
    checks = [
        ("one_video_stream", len(video), "==", 1),
        ("no_audio_stream", len(audio), "==", 0),
        ("codec_h264", stream.get("codec_name"), "==", "h264"),
        ("pixel_format_yuv420p", stream.get("pix_fmt"), "==", "yuv420p"),
        ("width", stream.get("width"), "==", 1920),
        ("height", stream.get("height"), "==", 1080),
        ("frame_count", int(stream.get("nb_frames", 0)), "==", 60),
        ("full_decode", metrics["decoded_frame_count"], "==", 60),
        ("full_psnr_all_frames", metrics["worst_full_frame_psnr_db"], ">=", gates["minimum_full_frame_psnr_db_all_frames"]),
        ("face_psnr_all_frames", metrics["worst_face_psnr_db"], ">=", gates["minimum_face_psnr_db_all_frames"]),
        ("face_ssim_all_frames", metrics["worst_face_ssim"], ">=", gates["minimum_face_ssim_all_frames"]),
        ("eye_psnr_all_frames", metrics["worst_eye_psnr_db"], ">=", gates["minimum_eye_psnr_db_all_frames"]),
        ("mouth_psnr_all_frames", metrics["worst_mouth_psnr_db"], ">=", gates["minimum_mouth_psnr_db_all_frames"]),
        ("sharpness_all_frames", metrics["minimum_encoded_laplacian_variance"], ">=", gates["minimum_encoded_laplacian_variance_all_frames"]),
        ("decoded_local_temporal_pop", metrics["maximum_decoded_adjacent_face_8x8_mean_delta"], "<=", gates["maximum_decoded_adjacent_face_8x8_mean_delta"]),
    ]
    results = []
    for name, actual, operator, threshold in checks:
        passed = actual == threshold if operator == "==" else actual >= threshold if operator == ">=" else actual <= threshold
        results.append({"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(passed)})
    return results


def render_v4(
    path: str | Path = REPO_ROOT / CONTRACT_RELATIVE_PATH,
    *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    prepared = prepare_v4(path)
    output = _output_path(prepared.contract)
    rejected = output.with_name(output.name + "-rejected-attempt-v4")
    if output.exists() or rejected.exists():
        raise SemanticFaceV4Error(f"immutable v4 attempt path exists: {output if output.exists() else rejected}")
    manifest, review, manifest_path = _verify_review(prepared)
    for frame_number, expected in enumerate(prepared.frame_hashes, start=1):
        actual = v3._raw_frame_hash(np.asarray(compose_frame(prepared, frame_number), dtype=np.uint8))
        if actual != expected:
            raise SemanticFaceV4Error(f"v4 frame {frame_number} changed after review")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    encode_count = 0
    try:
        delivery = prepared.contract["delivery"]
        video = stage / delivery["video_filename"]
        partial = stage / (video.stem + ".partial.mp4")
        encoding = delivery["encoding"]
        command = [
            ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s:v", "1920x1080", "-r", "30", "-i", "-", "-an",
            "-c:v", encoding["implementation"], "-preset", encoding["preset"], "-crf", str(encoding["crf"]),
            "-pix_fmt", encoding["pixel_format"], "-frames:v", "60", "-movflags", "+faststart", str(partial),
        ]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        encode_count += 1
        assert process.stdin is not None
        try:
            for frame_number in range(1, 61):
                frame = np.asarray(compose_frame(prepared, frame_number), dtype=np.uint8)
                process.stdin.write(np.ascontiguousarray(frame).tobytes())
            process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr is not None else ""
            code = process.wait()
        except Exception:
            process.kill()
            process.wait()
            raise
        if code != 0:
            raise SemanticFaceV4Error(f"single v4 encode failed: {stderr.strip()}")
        os.replace(partial, video)
        probe = v3._probe_video(video, ffprobe)
        metrics, _ = v3._decode_and_measure(prepared.base, video, stage)
        old_sheet = stage / prepared.base.contract["delivery"]["decoded_contact_sheet_filename"]
        new_sheet = stage / delivery["decoded_contact_sheet_filename"]
        os.replace(old_sheet, new_sheet)
        metrics["decoded_contact_sheet"] = {"file": new_sheet.name, "sha256": _sha256(new_sheet)}
        gates = _decoded_gates(prepared.contract, metrics, probe)
        machine_passed = all(gate["passed"] for gate in gates)
        report = {
            "report_version": 1,
            "status": "machine_delivery_gates_passed_human_decoded_review_required" if machine_passed else "machine_gates_failed",
            "machine_passed": machine_passed,
            "accepted_production_delivery": False,
            "contract": {"path": CONTRACT_RELATIVE_PATH, "raw_sha256": _sha256(prepared.contract_path), "canonical_sha256": _canonical_hash(prepared.contract)},
            "implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": _sha256(REPO_ROOT / IMPLEMENTATION_RELATIVE_PATH)},
            "base_v3": prepared.contract["locks"],
            "preview_manifest": {"path": str(manifest_path), "sha256": _sha256(manifest_path)},
            "preview_review": {"path": prepared.contract["preview"]["review_receipt"], "sha256": _sha256(_repo_path(prepared.contract["preview"]["review_receipt"]))},
            "pixels_byte_identical_to_reviewed_v3": manifest["pixels_byte_identical_to_reviewed_v3"],
            "preencode_measurements": prepared.preencode_measurements,
            "video": {"file": video.name, "sha256": _sha256(video), "bytes": video.stat().st_size, "encoding_process_count": encode_count},
            "probe": probe,
            "decoded_measurements": metrics,
            "gates": gates,
            "gate_count": len(gates),
            "gates_passed": sum(1 for gate in gates if gate["passed"]),
            "gates_failed": sum(1 for gate in gates if not gate["passed"]),
            "human_decoded_review_required": True,
            "voiced_reencode_allowed": False,
            "cash_cost": 0,
            "paid_runtime_dependency": False,
            "reinforcement_learning_used": False,
        }
        report_path = stage / delivery["report_filename"]
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not machine_passed:
            os.replace(stage, rejected)
            raise SemanticFaceV4Error(f"v4 failed and was preserved at {rejected}")
        os.replace(stage, output)
        return {
            "output_directory": str(output),
            "video": str(output / video.name),
            "video_sha256": _sha256(output / video.name),
            "report": str(output / report_path.name),
            "report_sha256": _sha256(output / report_path.name),
            "machine_passed": True,
            "human_review_required": True,
        }
    except Exception:
        if stage.exists():
            if encode_count:
                os.replace(stage, rejected)
            else:
                shutil.rmtree(stage)
        raise


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build June's Phase33 v4 semantic evidence correction")
    parser.add_argument("--contract", default=str(REPO_ROOT / CONTRACT_RELATIVE_PATH))
    parser.add_argument("--write-preview", action="store_true")
    parser.add_argument("--encode", action="store_true")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.write_preview == args.encode:
        raise SystemExit("choose exactly one of --write-preview or --encode")
    result = write_preview(args.contract) if args.write_preview else render_v4(args.contract, ffmpeg=args.ffmpeg, ffprobe=args.ffprobe)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
