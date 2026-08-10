from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

import pipeline.cartoon_source_textured_face as phase34


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_RELATIVE_PATH = "concept/characters/june_oxley_phase34_source_textured_visemes_v1.json"
IMPLEMENTATION_RELATIVE_PATH = "pipeline/cartoon_source_textured_delivery.py"
RENDERER_RELATIVE_PATH = "pipeline/cartoon_source_textured_face.py"
RECEIPT_RELATIVE_PATH = "concept/characters/june_oxley_phase34_source_textured_preview_review_v1.json"
CLAUDE_REVIEW_RELATIVE_PATH = "collab/CLAUDE_REVIEW_2026-08-10_0430Z.md"
EVIDENCE_RELATIVE_DIRECTORY = "collab/phase34_candidate_08"

EXPECTED_MANIFEST_LF_SHA256 = "5fa917cd2fc8e1069a75b3696d81a80d45211e37f5c3e8626598b7efd9cb78fe"
EXPECTED_ARCHIVE_SHA256 = "30f17179fd4fe9cd0f531b559269e187d3b8c888d90b5a5f8a770356ff6cd705"
EXPECTED_CONTRACT_RAW_SHA256 = "87da5306148eac5e4d49bf6613c8912b58eb9c6434c9927bd0925de6f7d654de"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "992f5aeeb203119bd4d00373f0a5060ab1b5aa835100295db6beaf4d69a9ae20"
EXPECTED_RENDERER_SHA256 = "73cd8ab14a474019160ed88a321caaf2164cec35c370dec21c32afba1354c95e"
EXPECTED_CLAUDE_REVIEW_LF_SHA256 = "2ec35200da4add1fea0c5f3102497cba0895fc1f7feb555c3c652e93096e508a"
EXPECTED_RECEIPT_RAW_SHA256 = "b1456d8afafbe1250057f3badec0f5ddef9e45f697d49a38fe731c160e6dc8b8"
EXPECTED_REVIEW_COMMIT = "2ce846c593142c0da9a8f9c49115efc12fdaa8c3"
EXPECTED_FRAME_COUNT = 96
EXPECTED_WIDTH = 1920
EXPECTED_HEIGHT = 1080
EXPECTED_FPS = 24


class SourceTexturedDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorizedArchive:
    contract: dict[str, Any]
    contract_path: Path
    receipt: dict[str, Any]
    receipt_path: Path
    claude_review_path: Path
    manifest: dict[str, Any]
    manifest_path: Path
    archive_path: Path
    archive_header: dict[str, Any]
    frames: list[np.ndarray]


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
    resolved = (REPO_ROOT / relative).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SourceTexturedDeliveryError(f"repository evidence path escapes the repository: {relative}") from exc
    return resolved


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise SourceTexturedDeliveryError(f"Phase34 delivery authorization mismatch for {label}: {actual!r} != {expected!r}")


def _validate_review_artifacts(manifest: dict[str, Any], evidence_dir: Path) -> None:
    references = [manifest["all_96_contact_sheet"], manifest["key_pose_sheet"]]
    references.extend(manifest["review_sheets"].values())
    _require_equal(len(references), 7, "review artifact count")
    for reference in references:
        artifact = evidence_dir / reference["file"]
        if not artifact.is_file():
            raise SourceTexturedDeliveryError(f"review artifact is missing: {artifact}")
        _require_equal(_sha256(artifact), reference["sha256"], f"review artifact {artifact.name} SHA-256")


def load_authorized_archive() -> AuthorizedArchive:
    contract_path = _repo_path(CONTRACT_RELATIVE_PATH)
    try:
        contract = phase34.load_contract(contract_path)
    except Exception as exc:
        raise SourceTexturedDeliveryError(f"locked Phase34 contract failed validation: {exc}") from exc
    _require_equal(_sha256(contract_path), EXPECTED_CONTRACT_RAW_SHA256, "contract raw SHA-256")
    _require_equal(_canonical_hash(contract), EXPECTED_CONTRACT_CANONICAL_SHA256, "contract canonical SHA-256")
    _require_equal(contract["clock"], {
        "source_width": 1672,
        "source_height": 941,
        "output_width": EXPECTED_WIDTH,
        "output_height": EXPECTED_HEIGHT,
        "fps": EXPECTED_FPS,
        "frame_count": EXPECTED_FRAME_COUNT,
        "duration_seconds": 4.0,
    }, "delivery clock")
    _require_equal(contract["preview"]["review_receipt"], RECEIPT_RELATIVE_PATH, "contract receipt path")
    _require_equal(contract["delivery"]["attempt_version"], 1, "delivery attempt version")
    _require_equal(contract["delivery"]["one_video_encode_without_retry"], True, "one encode without retry")
    _require_equal(contract["failure_policy"]["automatic_reencode_allowed"], False, "automatic re-encode")
    _require_equal(contract["failure_policy"]["failed_encoded_attempt_is_preserved"], True, "failed attempt preservation")

    renderer_path = _repo_path(RENDERER_RELATIVE_PATH)
    _require_equal(_sha256(renderer_path), EXPECTED_RENDERER_SHA256, "reviewed renderer SHA-256")

    receipt_path = _repo_path(RECEIPT_RELATIVE_PATH)
    if not receipt_path.is_file():
        raise SourceTexturedDeliveryError("machine-readable preview review receipt is missing")
    _require_equal(_sha256(receipt_path), EXPECTED_RECEIPT_RAW_SHA256, "receipt raw SHA-256")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    required_receipt = {
        "review_version": 1,
        "character_id": "june_oxley",
        "phase": "phase34_source_textured_viseme_deformation",
        "attempt_version": 1,
        "status": "all_96_archived_frames_reviewed_encode_once_allowed",
        "review_commit": EXPECTED_REVIEW_COMMIT,
        "reviewed_evidence_directory": EVIDENCE_RELATIVE_DIRECTORY,
        "manifest_lf_normalized_sha256": EXPECTED_MANIFEST_LF_SHA256,
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "contract_raw_sha256": EXPECTED_CONTRACT_RAW_SHA256,
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "renderer_sha256": EXPECTED_RENDERER_SHA256,
        "raw_frame_count_reviewed": EXPECTED_FRAME_COUNT,
        "promotion_granted": False,
        "human_decoded_review_required": True,
        "cash_cost": 0,
        "paid_runtime_dependency": False,
    }
    for key, expected in required_receipt.items():
        _require_equal(receipt.get(key), expected, f"receipt {key}")
    _require_equal(receipt["phase"], contract["phase"], "receipt phase equals contract phase")
    authorization = receipt.get("encode_authorization", {})
    required_authorization = {
        "allowed": True,
        "maximum_video_encoder_processes": 1,
        "source_must_be_exact_archived_rgb_frames": True,
        "output_directory_must_match_contract": True,
        "automatic_retry_allowed": False,
        "audio_allowed": False,
    }
    for key, expected in required_authorization.items():
        _require_equal(authorization.get(key), expected, f"receipt encode_authorization.{key}")

    claude_review_path = _repo_path(CLAUDE_REVIEW_RELATIVE_PATH)
    _require_equal(receipt.get("claude_review", {}).get("path"), CLAUDE_REVIEW_RELATIVE_PATH, "Claude review path")
    _require_equal(
        receipt.get("claude_review", {}).get("lf_normalized_sha256"),
        EXPECTED_CLAUDE_REVIEW_LF_SHA256,
        "receipt Claude review LF SHA-256",
    )
    _require_equal(_sha256_lf_normalized(claude_review_path), EXPECTED_CLAUDE_REVIEW_LF_SHA256, "Claude review LF SHA-256")
    review_text = claude_review_path.read_text(encoding="utf-8")
    for required_text in (
        "RECEIPT - one silent encode authorized",
        "I approve one silent encode of the exact 96 archived RGB frames of Candidate-08",
        EXPECTED_MANIFEST_LF_SHA256,
        "Any change of pose, renderer, frame content, or manifest voids this receipt.",
    ):
        if required_text not in review_text:
            raise SourceTexturedDeliveryError(f"Claude review authorization text is missing: {required_text}")

    evidence_dir = _repo_path(EVIDENCE_RELATIVE_DIRECTORY)
    manifest_path = evidence_dir / contract["preview"]["manifest_filename"]
    if not manifest_path.is_file():
        raise SourceTexturedDeliveryError("reviewed Candidate08 manifest is missing")
    _require_equal(_sha256_lf_normalized(manifest_path), EXPECTED_MANIFEST_LF_SHA256, "manifest LF SHA-256")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require_equal(manifest.get("manifest_version"), 1, "manifest version")
    _require_equal(manifest.get("development_label"), "candidate-08", "manifest candidate")
    _require_equal(manifest.get("contract", {}).get("path"), CONTRACT_RELATIVE_PATH, "manifest contract path")
    _require_equal(manifest.get("contract", {}).get("raw_sha256"), EXPECTED_CONTRACT_RAW_SHA256, "manifest contract raw SHA-256")
    _require_equal(manifest.get("contract", {}).get("canonical_sha256"), EXPECTED_CONTRACT_CANONICAL_SHA256, "manifest contract canonical SHA-256")
    _require_equal(manifest.get("implementation", {}).get("path"), RENDERER_RELATIVE_PATH, "manifest renderer path")
    _require_equal(manifest.get("implementation", {}).get("sha256"), EXPECTED_RENDERER_SHA256, "manifest renderer SHA-256")
    _require_equal(manifest.get("clock"), contract["clock"], "manifest clock")
    _require_equal(manifest.get("frame_hash_domain"), "raw_rgb24_1920x1080_row_major", "frame hash domain")
    _require_equal(manifest.get("all_96_raw_frame_hashes_present"), True, "all raw frame hashes present")
    _require_equal(manifest.get("lossless_review_frame_archive_present"), True, "lossless archive present")
    _require_equal(manifest.get("final_encode_allowed_without_bound_review_receipt"), False, "manifest encode policy")
    frames_manifest = manifest.get("frames", [])
    _require_equal(len(frames_manifest), EXPECTED_FRAME_COUNT, "manifest frame count")
    _require_equal([entry.get("frame") for entry in frames_manifest], list(range(1, EXPECTED_FRAME_COUNT + 1)), "ordered frame numbers")
    preflight_gates = manifest.get("preflight_gates", [])
    _require_equal(len(preflight_gates), 46, "pre-encode gate count")
    failed_preflight = [gate for gate in preflight_gates if gate.get("passed") is not True]
    if failed_preflight:
        raise SourceTexturedDeliveryError("reviewed Candidate08 contains failed pre-encode gates")
    _validate_review_artifacts(manifest, evidence_dir)

    archive_reference = manifest.get("lossless_review_frame_archive", {})
    archive_path = evidence_dir / archive_reference.get("file", "")
    if not archive_path.is_file():
        raise SourceTexturedDeliveryError("reviewed lossless RGB archive is missing")
    _require_equal(archive_reference.get("sha256"), EXPECTED_ARCHIVE_SHA256, "manifest archive SHA-256")
    _require_equal(_sha256(archive_path), EXPECTED_ARCHIVE_SHA256, "archive SHA-256")
    try:
        header, frames = phase34._read_lossless_frame_archive(archive_path)
    except Exception as exc:
        raise SourceTexturedDeliveryError(f"lossless RGB archive failed validation: {exc}") from exc
    expected_header = {
        "format": "phase34_rgb24_xor_previous_gzip_v1",
        "width": EXPECTED_WIDTH,
        "height": EXPECTED_HEIGHT,
        "channels": 3,
        "frame_count": EXPECTED_FRAME_COUNT,
        "frame_bytes": EXPECTED_WIDTH * EXPECTED_HEIGHT * 3,
        "xor_seed": "all_zero_rgb24_frame",
    }
    _require_equal(header, expected_header, "archive header")
    _require_equal(archive_reference, {"file": archive_path.name, "sha256": EXPECTED_ARCHIVE_SHA256, **expected_header}, "manifest archive declaration")
    _require_equal(len(frames), EXPECTED_FRAME_COUNT, "decoded archive frame count")
    expected_shape = (EXPECTED_HEIGHT, EXPECTED_WIDTH, 3)
    for frame_number, (frame, entry) in enumerate(zip(frames, frames_manifest), start=1):
        _require_equal(frame.dtype, np.dtype(np.uint8), f"archive frame {frame_number} dtype")
        _require_equal(frame.shape, expected_shape, f"archive frame {frame_number} shape")
        _require_equal(_raw_frame_hash(frame), entry["rgb_sha256"], f"archive frame {frame_number} raw RGB SHA-256")

    return AuthorizedArchive(
        contract=contract,
        contract_path=contract_path,
        receipt=receipt,
        receipt_path=receipt_path,
        claude_review_path=claude_review_path,
        manifest=manifest,
        manifest_path=manifest_path,
        archive_path=archive_path,
        archive_header=header,
        frames=frames,
    )


def _delivery_output_path(contract: dict[str, Any]) -> Path:
    output = (REPO_ROOT / contract["delivery"]["output_directory"]).resolve()
    expected = (REPO_ROOT / "../../outputs/edit/phase34-source-textured-visemes-proof-v1").resolve()
    _require_equal(output, expected, "contract-pinned output directory")
    return output


def _psnr(first: np.ndarray, second: np.ndarray) -> float:
    mse = float(np.mean((first.astype(np.float32) - second.astype(np.float32)) ** 2))
    if mse <= 1e-12:
        return 99.0
    return float(10.0 * math.log10((255.0 * 255.0) / mse))


def _ssim(first: np.ndarray, second: np.ndarray) -> float:
    first_f = first.astype(np.float32)
    second_f = second.astype(np.float32)
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    scores = []
    for channel in range(3):
        a = first_f[:, :, channel]
        b = second_f[:, :, channel]
        mu_a = cv2.GaussianBlur(a, (11, 11), 1.5)
        mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)
        sigma_a = cv2.GaussianBlur(a * a, (11, 11), 1.5) - mu_a * mu_a
        sigma_b = cv2.GaussianBlur(b * b, (11, 11), 1.5) - mu_b * mu_b
        sigma_ab = cv2.GaussianBlur(a * b, (11, 11), 1.5) - mu_a * mu_b
        numerator = (2.0 * mu_a * mu_b + c1) * (2.0 * sigma_ab + c2)
        denominator = (mu_a * mu_a + mu_b * mu_b + c1) * (sigma_a + sigma_b + c2)
        scores.append(float(np.mean(numerator / np.maximum(denominator, 1e-12))))
    return float(np.mean(scores))


def _max_8x8_delta(first: np.ndarray, second: np.ndarray) -> float:
    delta = np.abs(first.astype(np.float32) - second.astype(np.float32)).mean(axis=2)
    return float(cv2.boxFilter(delta, -1, (8, 8), normalize=True).max())


def _contact_sheet(
    frames: list[Image.Image],
    destination: Path,
    focus_sections: list[dict[str, Any]],
) -> None:
    columns = 12
    tile = (160, 90)
    rows = math.ceil(len(frames) / columns)
    width = columns * tile[0]
    all_frames_height = rows * tile[1]
    section_layouts: list[tuple[dict[str, Any], int, int, int]] = []
    total_height = 32 + all_frames_height
    for section in focus_sections:
        items = section["items"]
        section_columns = section["columns"]
        scale = section["scale"]
        cell_width = int(round(items[0][1].width * scale)) + 12
        cell_height = int(round(items[0][1].height * scale)) + 28
        section_rows = math.ceil(len(items) / section_columns)
        section_height = 34 + section_rows * cell_height
        section_layouts.append((section, cell_width, cell_height, section_height))
        total_height += section_height
    sheet = Image.new("RGB", (width, total_height), (16, 13, 10))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), "PHASE34 CANDIDATE08 — ALL 96 DECODED FRAMES", fill=(246, 227, 186))
    for index, frame in enumerate(frames):
        thumbnail = frame.copy()
        thumbnail.thumbnail(tile, Image.Resampling.LANCZOS)
        x = (index % columns) * tile[0] + (tile[0] - thumbnail.width) // 2
        y = 32 + (index // columns) * tile[1] + (tile[1] - thumbnail.height) // 2
        sheet.paste(thumbnail, (x, y))
        draw.rectangle((x + 3, y + 3, x + 48, y + 18), fill=(15, 12, 10))
        draw.text((x + 7, y + 5), f"F{index + 1:02d}", fill=(246, 227, 186))
    cursor_y = 32 + all_frames_height
    for section, cell_width, cell_height, section_height in section_layouts:
        draw.rectangle((0, cursor_y, width, cursor_y + 33), fill=(34, 27, 20))
        draw.text((12, cursor_y + 10), section["title"], fill=(246, 227, 186))
        content_width = section["columns"] * cell_width
        x_origin = max(0, (width - content_width) // 2)
        for index, (label, image) in enumerate(section["items"]):
            resized = image.resize(
                (int(round(image.width * section["scale"])), int(round(image.height * section["scale"]))),
                Image.Resampling.NEAREST,
            )
            x = x_origin + (index % section["columns"]) * cell_width + 6
            y = cursor_y + 34 + (index // section["columns"]) * cell_height + 22
            sheet.paste(resized, (x, y))
            draw.text((x, y - 17), label, fill=(226, 204, 165))
        cursor_y += section_height
    sheet.save(destination, format="PNG", optimize=True)


def _probe_video(video: Path, ffprobe: str) -> dict[str, Any]:
    command = [
        ffprobe, "-v", "error", "-count_frames", "-show_entries",
        "stream=index,codec_type,codec_name,pix_fmt,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,start_time,duration:format=duration",
        "-of", "json", str(video),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _decode_and_measure(
    video: Path,
    source_frames: list[np.ndarray],
    contract: dict[str, Any],
    contact_sheet_path: Path,
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SourceTexturedDeliveryError("OpenCV could not open the encoded proof")
    gates = contract["decoded_gates"]
    for roi_name in ("face_roi_xyxy", "eye_roi_xyxy", "mouth_roi_xyxy"):
        roi = gates[roi_name]
        if (
            not isinstance(roi, list) or len(roi) != 4
            or not all(isinstance(value, int) for value in roi)
            or not (0 <= roi[0] < roi[2] <= EXPECTED_WIDTH)
            or not (0 <= roi[1] < roi[3] <= EXPECTED_HEIGHT)
        ):
            raise SourceTexturedDeliveryError(f"invalid decoded gate ROI {roi_name}: {roi}")
    face = gates["face_roi_xyxy"]
    eyes = gates["eye_roi_xyxy"]
    mouth = gates["mouth_roi_xyxy"]
    full_psnr: list[float] = []
    face_psnr: list[float] = []
    face_ssim: list[float] = []
    eye_psnr: list[float] = []
    mouth_psnr: list[float] = []
    sharpness: list[float] = []
    temporal: list[float] = []
    thumbnails: list[Image.Image] = []
    previous_face: np.ndarray | None = None
    first_decoded: np.ndarray | None = None
    last_decoded: np.ndarray | None = None
    decoded_count = 0
    per_frame: list[dict[str, Any]] = []
    decoded_hashes: list[dict[str, Any]] = []
    eye_focus: list[tuple[str, Image.Image]] = []
    fg_focus: list[tuple[str, Image.Image]] = []
    h_focus: list[tuple[str, Image.Image]] = []
    triptychs: list[tuple[str, Image.Image]] = []
    try:
        while True:
            ok, bgr = capture.read()
            if not ok:
                break
            if decoded_count >= len(source_frames):
                raise SourceTexturedDeliveryError("encoded proof contains more than 96 decoded frames")
            if bgr.shape != (EXPECTED_HEIGHT, EXPECTED_WIDTH, 3):
                raise SourceTexturedDeliveryError(f"decoded frame {decoded_count + 1} has wrong shape: {bgr.shape}")
            encoded = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            expected = source_frames[decoded_count]
            decoded_count += 1
            if first_decoded is None:
                first_decoded = encoded.copy()
            last_decoded = encoded.copy()
            expected_face = expected[face[1]:face[3], face[0]:face[2]]
            encoded_face = encoded[face[1]:face[3], face[0]:face[2]]
            full_psnr.append(_psnr(expected, encoded))
            face_psnr.append(_psnr(expected_face, encoded_face))
            face_ssim.append(_ssim(expected_face, encoded_face))
            eye_psnr.append(_psnr(expected[eyes[1]:eyes[3], eyes[0]:eyes[2]], encoded[eyes[1]:eyes[3], eyes[0]:eyes[2]]))
            mouth_psnr.append(_psnr(expected[mouth[1]:mouth[3], mouth[0]:mouth[2]], encoded[mouth[1]:mouth[3], mouth[0]:mouth[2]]))
            gray = cv2.cvtColor(encoded, cv2.COLOR_RGB2GRAY)
            sharpness.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            decoded_hashes.append({"frame": decoded_count, "rgb_sha256": _raw_frame_hash(encoded)})
            per_frame.append({
                "frame": decoded_count,
                "full_frame_psnr_db": full_psnr[-1],
                "face_psnr_db": face_psnr[-1],
                "face_ssim": face_ssim[-1],
                "eye_psnr_db": eye_psnr[-1],
                "mouth_psnr_db": mouth_psnr[-1],
                "encoded_laplacian_variance": sharpness[-1],
            })
            if previous_face is not None:
                temporal.append(_max_8x8_delta(previous_face, encoded_face))
                per_frame[-1]["adjacent_face_8x8_mean_delta_from_previous"] = temporal[-1]
            else:
                per_frame[-1]["adjacent_face_8x8_mean_delta_from_previous"] = None
            previous_face = encoded_face.copy()
            thumbnail = Image.fromarray(encoded, "RGB")
            thumbnail.thumbnail((160, 90), Image.Resampling.LANCZOS)
            thumbnails.append(thumbnail)
            if 4 <= decoded_count <= 12:
                eye_crop = encoded[eyes[1]:eyes[3], eyes[0]:eyes[2]]
                eye_focus.append((f"F{decoded_count:02d}", Image.fromarray(eye_crop, "RGB")))
            if 64 <= decoded_count <= 67:
                core = encoded[430:520, 640:810]
                fg_focus.append((f"F{decoded_count:02d}", Image.fromarray(core, "RGB")))
            if 80 <= decoded_count <= 83:
                mouth_crop = encoded[mouth[1]:mouth[3], mouth[0]:mouth[2]]
                h_focus.append((f"F{decoded_count:02d}", Image.fromarray(mouth_crop, "RGB")))
            if decoded_count in {65, 66, 80, 81}:
                source_core = expected[430:520, 640:810]
                decoded_core = encoded[430:520, 640:810]
                amplified_difference = np.clip(
                    np.abs(source_core.astype(np.int16) - decoded_core.astype(np.int16)) * 4,
                    0,
                    255,
                ).astype(np.uint8)
                triptych = np.concatenate((source_core, decoded_core, amplified_difference), axis=1)
                triptychs.append((f"F{decoded_count:02d}  SOURCE | DECODED | 4x ABS DIFF", Image.fromarray(triptych, "RGB")))
    finally:
        capture.release()
    if decoded_count != EXPECTED_FRAME_COUNT:
        raise SourceTexturedDeliveryError(f"full decode required 96 frames, got {decoded_count}")
    assert first_decoded is not None and last_decoded is not None
    _contact_sheet(thumbnails, contact_sheet_path, [
        {
            "title": "BLINK WINDOW F004–F012 — DECODED EYE ROI [625,235,850,360]",
            "items": eye_focus,
            "columns": 9,
            "scale": 0.85,
        },
        {
            "title": "F→G TRANSITION F064–F067 — DECODED MOUTH CORE [640,430,810,520] AT 4x",
            "items": fg_focus,
            "columns": 2,
            "scale": 4.0,
        },
        {
            "title": "H PLATEAU / EXIT F080–F083 — DECODED CONTRACT MOUTH ROI AT 2x",
            "items": h_focus,
            "columns": 2,
            "scale": 2.0,
        },
        {
            "title": "CODEC CHECKS — SOURCE / DECODED / AMPLIFIED DIFFERENCE",
            "items": triptychs,
            "columns": 1,
            "scale": 2.0,
        },
    ])
    numeric_values = full_psnr + face_psnr + face_ssim + eye_psnr + mouth_psnr + sharpness + temporal
    if not all(math.isfinite(value) for value in numeric_values):
        raise SourceTexturedDeliveryError("decoded measurements contain a non-finite value")

    def worst(values: list[float], mode: str = "min") -> dict[str, Any]:
        value = min(values) if mode == "min" else max(values)
        return {"value": value, "frame": values.index(value) + (1 if mode == "min" else 2)}

    return {
        "decoded_frame_count": decoded_count,
        "metric_algorithm": {
            "psnr": "RGB uint8 exact-pixel MSE, data range 255",
            "ssim": "RGB channel mean, Gaussian 11x11 sigma 1.5, data range 255",
            "sharpness": "grayscale OpenCV Laplacian CV_64F variance",
            "temporal": "maximum 8x8 box-filtered mean absolute RGB delta in decoded face ROI",
        },
        "per_frame": per_frame,
        "decoded_rgb24_hashes": decoded_hashes,
        "worst_full_frame_psnr_db": min(full_psnr),
        "worst_full_frame_psnr": worst(full_psnr),
        "worst_face_psnr_db": min(face_psnr),
        "worst_face_psnr": worst(face_psnr),
        "worst_face_ssim": min(face_ssim),
        "worst_face_ssim_frame": worst(face_ssim),
        "worst_eye_psnr_db": min(eye_psnr),
        "worst_eye_psnr": worst(eye_psnr),
        "worst_mouth_psnr_db": min(mouth_psnr),
        "worst_mouth_psnr": worst(mouth_psnr),
        "minimum_encoded_laplacian_variance": min(sharpness),
        "minimum_encoded_laplacian_variance_frame": worst(sharpness),
        "maximum_decoded_adjacent_face_8x8_mean_delta": max(temporal),
        "maximum_decoded_adjacent_face_8x8_mean_delta_frame_pair": [temporal.index(max(temporal)) + 1, temporal.index(max(temporal)) + 2],
        "first_last_decoded_psnr_db": _psnr(first_decoded, last_decoded),
        "all_frames_evaluated": True,
        "decoded_contact_sheet": {"file": contact_sheet_path.name, "sha256": _sha256(contact_sheet_path)},
    }


def _fraction_equal(value: Any, expected: Fraction) -> bool:
    try:
        return Fraction(str(value)) == expected
    except (ValueError, ZeroDivisionError):
        return False


def _decoded_gates(contract: dict[str, Any], metrics: dict[str, Any], probe: dict[str, Any]) -> list[dict[str, Any]]:
    gates = contract["decoded_gates"]
    streams = probe.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    other_streams = [stream for stream in streams if stream.get("codec_type") not in {"video", "audio"}]
    stream = video_streams[0] if len(video_streams) == 1 else {}
    try:
        nb_frames = int(stream.get("nb_frames", 0))
    except (TypeError, ValueError):
        nb_frames = 0
    try:
        nb_read_frames = int(stream.get("nb_read_frames", 0))
    except (TypeError, ValueError):
        nb_read_frames = 0
    try:
        start_time = float(stream.get("start_time", "nan"))
    except (TypeError, ValueError):
        start_time = math.nan
    try:
        stream_duration = float(stream.get("duration", "nan"))
        format_duration = float(probe.get("format", {}).get("duration", "nan"))
    except (TypeError, ValueError):
        stream_duration = math.nan
        format_duration = math.nan
    checks = [
        ("one_video_stream", len(video_streams), "==", 1, len(video_streams) == 1),
        ("no_audio_stream", len(audio_streams), "==", 0, len(audio_streams) == 0),
        ("no_other_streams", len(other_streams), "==", 0, len(other_streams) == 0),
        ("codec_h264", stream.get("codec_name"), "==", "h264", stream.get("codec_name") == "h264"),
        ("pixel_format_yuv420p", stream.get("pix_fmt"), "==", "yuv420p", stream.get("pix_fmt") == "yuv420p"),
        ("width", stream.get("width"), "==", EXPECTED_WIDTH, stream.get("width") == EXPECTED_WIDTH),
        ("height", stream.get("height"), "==", EXPECTED_HEIGHT, stream.get("height") == EXPECTED_HEIGHT),
        ("reported_frame_count", nb_frames, "==", EXPECTED_FRAME_COUNT, nb_frames == EXPECTED_FRAME_COUNT),
        ("ffprobe_decoded_frame_count", nb_read_frames, "==", EXPECTED_FRAME_COUNT, nb_read_frames == EXPECTED_FRAME_COUNT),
        ("OpenCV_full_decode", metrics["decoded_frame_count"], "==", EXPECTED_FRAME_COUNT, metrics["decoded_frame_count"] == EXPECTED_FRAME_COUNT),
        ("r_frame_rate", stream.get("r_frame_rate"), "==", "24/1", _fraction_equal(stream.get("r_frame_rate"), Fraction(24, 1))),
        ("avg_frame_rate", stream.get("avg_frame_rate"), "==", "24/1", _fraction_equal(stream.get("avg_frame_rate"), Fraction(24, 1))),
        ("start_time", start_time, "==", 0.0, math.isfinite(start_time) and abs(start_time) <= 1e-6),
        ("stream_duration_seconds", stream_duration, "==", 4.0, math.isfinite(stream_duration) and abs(stream_duration - 4.0) <= 1e-6),
        ("format_duration_seconds", format_duration, "==", 4.0, math.isfinite(format_duration) and abs(format_duration - 4.0) <= 1e-6),
        ("all_frame_full_psnr", metrics["worst_full_frame_psnr_db"], ">=", gates["minimum_full_frame_psnr_db_all_frames"], math.isfinite(metrics["worst_full_frame_psnr_db"]) and metrics["worst_full_frame_psnr_db"] >= gates["minimum_full_frame_psnr_db_all_frames"]),
        ("all_frame_face_psnr", metrics["worst_face_psnr_db"], ">=", gates["minimum_face_psnr_db_all_frames"], math.isfinite(metrics["worst_face_psnr_db"]) and metrics["worst_face_psnr_db"] >= gates["minimum_face_psnr_db_all_frames"]),
        ("all_frame_face_ssim", metrics["worst_face_ssim"], ">=", gates["minimum_face_ssim_all_frames"], math.isfinite(metrics["worst_face_ssim"]) and metrics["worst_face_ssim"] >= gates["minimum_face_ssim_all_frames"]),
        ("all_frame_eye_psnr", metrics["worst_eye_psnr_db"], ">=", gates["minimum_eye_psnr_db_all_frames"], math.isfinite(metrics["worst_eye_psnr_db"]) and metrics["worst_eye_psnr_db"] >= gates["minimum_eye_psnr_db_all_frames"]),
        ("all_frame_mouth_psnr", metrics["worst_mouth_psnr_db"], ">=", gates["minimum_mouth_psnr_db_all_frames"], math.isfinite(metrics["worst_mouth_psnr_db"]) and metrics["worst_mouth_psnr_db"] >= gates["minimum_mouth_psnr_db_all_frames"]),
        ("all_frame_sharpness", metrics["minimum_encoded_laplacian_variance"], ">=", gates["minimum_encoded_laplacian_variance_all_frames"], math.isfinite(metrics["minimum_encoded_laplacian_variance"]) and metrics["minimum_encoded_laplacian_variance"] >= gates["minimum_encoded_laplacian_variance_all_frames"]),
        ("decoded_local_temporal_pop", metrics["maximum_decoded_adjacent_face_8x8_mean_delta"], "<=", gates["maximum_decoded_adjacent_face_8x8_mean_delta"], math.isfinite(metrics["maximum_decoded_adjacent_face_8x8_mean_delta"]) and metrics["maximum_decoded_adjacent_face_8x8_mean_delta"] <= gates["maximum_decoded_adjacent_face_8x8_mean_delta"]),
    ]
    return [
        {"name": name, "actual": actual, "operator": operator, "threshold": threshold, "passed": bool(passed)}
        for name, actual, operator, threshold, passed in checks
    ]


def _resolved_tool(executable: str) -> Path:
    located = shutil.which(executable)
    if located is None:
        candidate = Path(executable).resolve()
        if not candidate.is_file():
            raise SourceTexturedDeliveryError(f"required executable was not found: {executable}")
        located = str(candidate)
    return Path(located).resolve()


def _validate_report(report_path: Path, stage: Path, claim: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("machine_passed") is not True or report.get("accepted_production_delivery") is not False:
        raise SourceTexturedDeliveryError("delivery report acceptance state is invalid")
    if report.get("video", {}).get("encoding_process_count") != 1:
        raise SourceTexturedDeliveryError("delivery report does not prove exactly one encoder process")
    if report.get("gates_failed") != 0 or report.get("gates_passed") != report.get("gate_count"):
        raise SourceTexturedDeliveryError("delivery report contains failed or missing gates")
    if len(report.get("preencode_gates", [])) != 46 or len(report.get("decoded_gates", [])) != 22:
        raise SourceTexturedDeliveryError("delivery report gate inventory is incomplete")
    all_gates = report["preencode_gates"] + report["decoded_gates"]
    gate_names = [gate.get("name") for gate in all_gates]
    if len(set(gate_names)) != 68 or not all(gate.get("passed") is True for gate in all_gates):
        raise SourceTexturedDeliveryError("delivery report gate identities are duplicated or failed")
    if report.get("probe_canonical_sha256") != _canonical_hash(report.get("probe", {})):
        raise SourceTexturedDeliveryError("delivery report probe hash is invalid")
    if report.get("preview_manifest", {}).get("lf_normalized_sha256") != EXPECTED_MANIFEST_LF_SHA256:
        raise SourceTexturedDeliveryError("delivery report manifest binding is invalid")
    if report.get("lossless_source_archive", {}).get("sha256") != EXPECTED_ARCHIVE_SHA256:
        raise SourceTexturedDeliveryError("delivery report archive binding is invalid")
    if report.get("contract", {}).get("canonical_sha256") != EXPECTED_CONTRACT_CANONICAL_SHA256:
        raise SourceTexturedDeliveryError("delivery report contract binding is invalid")
    if report.get("reviewed_renderer", {}).get("sha256") != EXPECTED_RENDERER_SHA256:
        raise SourceTexturedDeliveryError("delivery report renderer binding is invalid")
    source_hashes = report.get("source_rgb24_hashes", [])
    decoded_hashes = report.get("decoded_measurements", {}).get("decoded_rgb24_hashes", [])
    if [entry.get("frame") for entry in source_hashes] != list(range(1, 97)):
        raise SourceTexturedDeliveryError("delivery report source frame inventory is invalid")
    if [entry.get("frame") for entry in decoded_hashes] != list(range(1, 97)):
        raise SourceTexturedDeliveryError("delivery report decoded frame inventory is invalid")
    for entry in source_hashes + decoded_hashes:
        value = entry.get("rgb_sha256", "")
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise SourceTexturedDeliveryError("delivery report contains an invalid RGB frame hash")
    references = [report["video"], report["decoded_measurements"]["decoded_contact_sheet"]]
    for reference in references:
        artifact = stage / reference["file"]
        if not artifact.is_file() or _sha256(artifact) != reference["sha256"]:
            raise SourceTexturedDeliveryError(f"delivery report artifact integrity failed: {artifact.name}")
    stderr_reference = report.get("encoder_stderr", {})
    stderr_path = stage / stderr_reference.get("file", "")
    if not stderr_path.is_file() or _sha256(stderr_path) != stderr_reference.get("sha256"):
        raise SourceTexturedDeliveryError("delivery report encoder stderr integrity failed")
    if not claim.is_file() or _sha256(claim) != report.get("attempt_claim", {}).get("sha256"):
        raise SourceTexturedDeliveryError("delivery report attempt claim integrity failed")


def _claim_attempt(output: Path, authorized: AuthorizedArchive) -> Path:
    claim = output.parent / f".{output.name}.attempt-v1.claim.json"
    payload = {
        "claim_version": 1,
        "attempt_version": 1,
        "maximum_video_encoder_processes": 1,
        "source_manifest_lf_sha256": EXPECTED_MANIFEST_LF_SHA256,
        "source_archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "renderer_sha256": EXPECTED_RENDERER_SHA256,
        "receipt_sha256": _sha256(authorized.receipt_path),
        "state": "claimed_before_encoder_launch",
    }
    encoded = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise SourceTexturedDeliveryError(f"the single Phase34 encode attempt was already claimed: {claim}") from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return claim


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
        "status": "single_encode_attempt_rejected_no_retry_allowed",
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
        raise SourceTexturedDeliveryError(f"cannot preserve rejected attempt because immutable path exists: {rejected}") from error
    stage.rename(rejected)


def render_authorized_proof(*, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    authorized = load_authorized_archive()
    contract = authorized.contract
    output = _delivery_output_path(contract)
    rejected = output.with_name(output.name + "-rejected-attempt-v1")
    claim = output.parent / f".{output.name}.attempt-v1.claim.json"
    for immutable in (output, rejected, claim):
        if immutable.exists():
            raise SourceTexturedDeliveryError(f"immutable Phase34 delivery state already exists: {immutable}")
    old_partials = list(output.parent.glob(f".{output.name}.partial-*")) if output.parent.exists() else []
    if old_partials:
        raise SourceTexturedDeliveryError(f"an earlier Phase34 partial state exists: {old_partials[0]}")
    ffmpeg_path = _resolved_tool(ffmpeg)
    ffprobe_path = _resolved_tool(ffprobe)
    captured_hashes = {
        "contract_raw_sha256": _sha256(authorized.contract_path),
        "contract_canonical_sha256": _canonical_hash(contract),
        "renderer_sha256": _sha256(_repo_path(RENDERER_RELATIVE_PATH)),
        "delivery_implementation_sha256": _sha256(_repo_path(IMPLEMENTATION_RELATIVE_PATH)),
        "receipt_sha256": _sha256(authorized.receipt_path),
        "claude_review_lf_sha256": _sha256_lf_normalized(authorized.claude_review_path),
        "manifest_raw_sha256": _sha256(authorized.manifest_path),
        "manifest_lf_sha256": _sha256_lf_normalized(authorized.manifest_path),
        "archive_sha256": _sha256(authorized.archive_path),
        "ffmpeg_sha256": _sha256(ffmpeg_path),
        "ffprobe_sha256": _sha256(ffprobe_path),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.partial-", dir=output.parent))
    encoder_started = False
    claim_created = False
    encode_count = 0
    process: subprocess.Popen[bytes] | None = None
    command: list[str] = []
    return_code: int | None = None
    attempt_context: dict[str, Any] = {
        "source_review_commit": EXPECTED_REVIEW_COMMIT,
        "captured_hashes": captured_hashes,
        "encoder_command": command,
        "encoding_process_count": encode_count,
        "encoder_return_code": return_code,
    }
    try:
        claim = _claim_attempt(output, authorized)
        claim_created = True
        delivery = contract["delivery"]
        video = stage / delivery["video_filename"]
        partial_video = stage / f"{video.stem}.partial.mp4"
        encoding = delivery["encoding"]
        command = [
            str(ffmpeg_path), "-hide_banner", "-loglevel", "error", "-xerror",
            "-abort_on", "empty_output+empty_output_stream", "-f", "rawvideo",
            "-pixel_format", "rgb24", "-video_size", f"{EXPECTED_WIDTH}x{EXPECTED_HEIGHT}",
            "-framerate", str(EXPECTED_FPS), "-i", "pipe:0", "-map", "0:v:0",
            "-an", "-sn", "-dn", "-frames:v", str(EXPECTED_FRAME_COUNT),
            "-c:v", encoding["implementation"], "-preset", encoding["preset"],
            "-crf", str(encoding["crf"]), "-pix_fmt", encoding["pixel_format"],
            "-fps_mode", "cfr", "-movflags", "+faststart", "-n", str(partial_video),
        ]
        attempt_context["encoder_command"] = command
        stderr_path = stage / "ffmpeg-stderr-v1.txt"
        with stderr_path.open("wb") as stderr_handle:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=stderr_handle,
            )
            encoder_started = True
            encode_count = 1
            attempt_context["encoding_process_count"] = encode_count
            if process.stdin is None:
                raise SourceTexturedDeliveryError("ffmpeg stdin pipe was not created")
            bytes_written = 0
            frames_written = 0
            for frame, manifest_entry in zip(authorized.frames, authorized.manifest["frames"]):
                _require_equal(_raw_frame_hash(frame), manifest_entry["rgb_sha256"], f"streamed frame {frames_written + 1} raw RGB SHA-256")
                payload = np.ascontiguousarray(frame).tobytes()
                _require_equal(len(payload), EXPECTED_WIDTH * EXPECTED_HEIGHT * 3, f"encoder input frame {frames_written + 1} byte count")
                process.stdin.write(payload)
                bytes_written += len(payload)
                frames_written += 1
            process.stdin.close()
            return_code = process.wait()
            attempt_context["encoder_return_code"] = return_code
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
        _require_equal(frames_written, EXPECTED_FRAME_COUNT, "encoder input frame count")
        _require_equal(bytes_written, EXPECTED_FRAME_COUNT * EXPECTED_WIDTH * EXPECTED_HEIGHT * 3, "encoder input byte count")
        if return_code != 0:
            raise SourceTexturedDeliveryError(f"single ffmpeg encode failed with exit {return_code}: {stderr.strip()}")
        if not partial_video.is_file() or partial_video.stat().st_size == 0:
            raise SourceTexturedDeliveryError("single ffmpeg encode produced no video")
        os.replace(partial_video, video)

        current_hashes = {
            "contract_raw_sha256": _sha256(authorized.contract_path),
            "contract_canonical_sha256": _canonical_hash(json.loads(authorized.contract_path.read_text(encoding="utf-8"))),
            "renderer_sha256": _sha256(_repo_path(RENDERER_RELATIVE_PATH)),
            "delivery_implementation_sha256": _sha256(_repo_path(IMPLEMENTATION_RELATIVE_PATH)),
            "receipt_sha256": _sha256(authorized.receipt_path),
            "claude_review_lf_sha256": _sha256_lf_normalized(authorized.claude_review_path),
            "manifest_raw_sha256": _sha256(authorized.manifest_path),
            "manifest_lf_sha256": _sha256_lf_normalized(authorized.manifest_path),
            "archive_sha256": _sha256(authorized.archive_path),
            "ffmpeg_sha256": _sha256(ffmpeg_path),
            "ffprobe_sha256": _sha256(ffprobe_path),
        }
        _require_equal(current_hashes, captured_hashes, "post-encode fixed input hashes")

        probe = _probe_video(video, str(ffprobe_path))
        contact_sheet = stage / delivery["decoded_contact_sheet_filename"]
        metrics = _decode_and_measure(video, authorized.frames, contract, contact_sheet)
        decoded_gates = _decoded_gates(contract, metrics, probe)
        preflight_gates = authorized.manifest["preflight_gates"]
        all_gates = preflight_gates + decoded_gates
        machine_passed = all(gate["passed"] is True for gate in all_gates)
        report = {
            "report_version": 1,
            "status": "machine_delivery_gates_passed_human_motion_review_required" if machine_passed else "machine_delivery_gates_failed_no_retry_allowed",
            "machine_passed": machine_passed,
            "accepted_production_delivery": False,
            "human_full_size_motion_review_required": True,
            "scope": "silent Phase34 facial-motion proof only",
            "source_review_commit": EXPECTED_REVIEW_COMMIT,
            "contract": {
                "path": CONTRACT_RELATIVE_PATH,
                "raw_sha256": captured_hashes["contract_raw_sha256"],
                "canonical_sha256": captured_hashes["contract_canonical_sha256"],
            },
            "reviewed_renderer": {"path": RENDERER_RELATIVE_PATH, "sha256": captured_hashes["renderer_sha256"]},
            "delivery_implementation": {"path": IMPLEMENTATION_RELATIVE_PATH, "sha256": captured_hashes["delivery_implementation_sha256"]},
            "preview_manifest": {
                "path": EVIDENCE_RELATIVE_DIRECTORY + "/" + authorized.manifest_path.name,
                "raw_sha256": captured_hashes["manifest_raw_sha256"],
                "lf_normalized_sha256": captured_hashes["manifest_lf_sha256"],
            },
            "source_rgb24_hashes": authorized.manifest["frames"],
            "preview_review_receipt": {"path": RECEIPT_RELATIVE_PATH, "sha256": captured_hashes["receipt_sha256"]},
            "claude_review": {"path": CLAUDE_REVIEW_RELATIVE_PATH, "lf_normalized_sha256": captured_hashes["claude_review_lf_sha256"]},
            "lossless_source_archive": {"path": EVIDENCE_RELATIVE_DIRECTORY + "/" + authorized.archive_path.name, "sha256": captured_hashes["archive_sha256"]},
            "attempt_claim": {"file": claim.name, "sha256": _sha256(claim)},
            "toolchain": {
                "ffmpeg": {"path": str(ffmpeg_path), "sha256": captured_hashes["ffmpeg_sha256"]},
                "ffprobe": {"path": str(ffprobe_path), "sha256": captured_hashes["ffprobe_sha256"]},
                "opencv": cv2.__version__,
                "numpy": np.__version__,
            },
            "encoder_command": command,
            "encoder_stderr": {"file": stderr_path.name, "sha256": _sha256(stderr_path), "text": stderr},
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
            "preflight_measurements": authorized.manifest["preflight_measurements"],
            "decoded_measurements": metrics,
            "preencode_gates": preflight_gates,
            "decoded_gates": decoded_gates,
            "gate_count": len(all_gates),
            "gates_passed": sum(1 for gate in all_gates if gate["passed"]),
            "gates_failed": sum(1 for gate in all_gates if not gate["passed"]),
            "review_motion_questions": authorized.receipt["motion_questions"],
            "constraints": {
                "audio_used": False,
                "renderer_invoked": False,
                "source_was_exact_reviewed_archive": True,
                "automatic_retry_used": False,
                "reinforcement_learning_used": False,
                "paid_service_or_api_used": False,
                "voiced_reencode_allowed_before_human_acceptance": False,
                "production_promotion_granted": False,
            },
        }
        report_path = stage / delivery["report_filename"]
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        if not machine_passed:
            raise SourceTexturedDeliveryError("decoded Phase34 delivery gates failed; the attempt is preserved and cannot be retried")
        _validate_report(report_path, stage, claim)
        if output.exists():
            raise SourceTexturedDeliveryError(f"immutable output appeared before publication: {output}")
        stage.rename(output)
        return {
            "output_directory": str(output),
            "video": str(output / video.name),
            "video_sha256": report["video"]["sha256"],
            "report": str(output / report_path.name),
            "decoded_contact_sheet": str(output / contact_sheet.name),
            "machine_passed": True,
            "human_motion_review_required": True,
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
    parser = argparse.ArgumentParser(description="Encode the one authorized Phase34 Candidate08 silent proof.")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    print(json.dumps(render_authorized_proof(ffmpeg=args.ffmpeg, ffprobe=args.ffprobe), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
