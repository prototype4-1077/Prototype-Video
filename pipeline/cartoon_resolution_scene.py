"""Render GS070 as a registered mug-offer cut and direct-address performance."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from pipeline.cartoon_expression_atlas import (
    expression_cells,
    expression_performance_plan,
    load_expression_atlas_contract,
)
from pipeline.cartoon_hero_scene import (
    _blend,
    _camera_frame,
    _color_match_patch,
    _lantern_glow,
    _repo_asset,
    _secondary_overlay,
    _warp_region,
    load_body_motion_contract,
    load_hero_plate_contract,
)
from pipeline.cartoon_shot_sequence import encoded_quality_metrics
from pipeline.cartoon_viseme_atlas import (
    atlas_cells,
    load_viseme_atlas_contract,
    performance_viseme_plan,
)


CONTRACT_VERSION = 1
REVIEW_FRAMES = (1, 30, 45, 46, 90, 143, 157, 168, 180, 201, 202, 228)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def _load_resolution_contract(path: str | Path) -> tuple[dict[str, Any], Path, Path]:
    contract_path = Path(path).resolve()
    contract, plate_path = load_hero_plate_contract(contract_path)
    if contract.get("shot_id") != "GS070":
        raise ValueError("resolution contract must target GS070")
    output = contract["output"]
    if (
        int(output.get("frame_count", 0)),
        float(output.get("duration_seconds", 0.0)),
    ) != (228, 7.6):
        raise ValueError("GS070 must use the locked 228-frame/7.6-second clock")
    sequence = contract.get("sequence") or {}
    expected = {
        "offer_insert_start_frame": 1,
        "offer_insert_end_frame": 45,
        "direct_address_start_frame": 46,
        "dialogue_end_frame": 143,
        "final_hold_start_frame": 202,
        "final_hold_frames": 27,
        "mouth_returns_to_authored_plate_frame": 145,
    }
    for key, value in expected.items():
        if int(sequence.get(key, 0)) != value:
            raise ValueError(f"GS070 sequence field {key!r} must equal {value}")
    if int(sequence.get("nod_start_frame", 0)) >= int(sequence.get("nod_end_frame", 0)):
        raise ValueError("GS070 compact nod needs a positive frame window")
    if int(sequence["final_hold_start_frame"]) + int(sequence["final_hold_frames"]) - 1 != 228:
        raise ValueError("GS070 final hold must end on frame 228")
    quality = contract.get("encoded_quality_gate") or {}
    if not 30.0 <= float(quality.get("minimum_review_frame_psnr_db", 0.0)) <= 60.0:
        raise ValueError("GS070 PSNR gate must be between 30 and 60 dB")
    if not 1.0 <= float(quality.get("minimum_encoded_laplacian_variance", 0.0)) <= 1000.0:
        raise ValueError("GS070 encoded-detail gate is invalid")

    insert_spec = contract.get("offer_insert") or {}
    insert_path = _repo_asset(contract_path, insert_spec, "GS070 held-mug insert")
    with Image.open(insert_path) as image:
        expected_size = (int(insert_spec.get("width", 0)), int(insert_spec.get("height", 0)))
        if image.size != expected_size or image.mode != insert_spec.get("mode"):
            raise ValueError("GS070 held-mug insert does not match its image contract")

    matrix = np.asarray(contract["atlas_registration"].get("affine_matrix"), dtype=np.float64)
    if matrix.shape != (2, 3) or not np.isfinite(matrix).all():
        raise ValueError("GS070 atlas registration needs one finite 2x3 affine matrix")
    determinant = float(np.linalg.det(matrix[:, :2]))
    if not 0.25 <= determinant <= 9.0:
        raise ValueError("GS070 affine registration has an unsafe scale")
    return contract, plate_path, insert_path


def _affine_patch_box(
    atlas_box: tuple[int, int, int, int],
    matrix: np.ndarray,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = atlas_box
    corners = np.asarray(
        [[left, top, 1.0], [right, top, 1.0], [right, bottom, 1.0], [left, bottom, 1.0]],
        dtype=np.float64,
    )
    transformed = corners @ matrix.T
    return (
        math.floor(float(transformed[:, 0].min())),
        math.floor(float(transformed[:, 1].min())),
        math.ceil(float(transformed[:, 0].max())),
        math.ceil(float(transformed[:, 1].max())),
    )


def _prepare_affine_patches(
    plate: Image.Image,
    cells: dict[str, Image.Image],
    atlas_box: tuple[int, int, int, int],
    atlas_mask: Image.Image,
    contract: dict[str, Any],
) -> tuple[dict[str, Image.Image], Image.Image, tuple[int, int, int, int]]:
    matrix = np.asarray(contract["atlas_registration"]["affine_matrix"], dtype=np.float64)
    plate_box = _affine_patch_box(atlas_box, matrix)
    if not (
        0 <= plate_box[0] < plate_box[2] <= plate.width
        and 0 <= plate_box[1] < plate_box[3] <= plate.height
    ):
        raise ValueError("registered atlas patch leaves the GS070 production plate")
    width = plate_box[2] - plate_box[0]
    height = plate_box[3] - plate_box[1]
    left, top, _, _ = atlas_box
    local = matrix.copy()
    local[:, 2] += matrix[:, :2] @ np.asarray([left, top], dtype=np.float64)
    local[:, 2] -= np.asarray([plate_box[0], plate_box[1]], dtype=np.float64)
    warped_mask = cv2.warpAffine(
        np.asarray(atlas_mask.convert("L"), dtype=np.uint8),
        local.astype(np.float32),
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    mask = Image.fromarray(warped_mask, "L")
    target = plate.crop(plate_box)
    strength = float(contract["atlas_registration"]["patch_color_match_strength"])
    patches: dict[str, Image.Image] = {}
    for name, cell in cells.items():
        crop = np.asarray(cell.crop(atlas_box).convert("RGB"), dtype=np.uint8)
        warped = cv2.warpAffine(
            crop,
            local.astype(np.float32),
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        patches[name] = _color_match_patch(Image.fromarray(warped, "RGB"), target, mask, strength)
    return patches, mask, plate_box


def _mouth_feature_mask(box: tuple[int, int, int, int], feather: int) -> Image.Image:
    width = box[2] - box[0]
    height = box[3] - box[1]
    mask = Image.new("L", (width, height), 0)
    inset = feather + 2
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset, inset, width - inset - 1, height - inset - 1),
        radius=max(18, height // 3),
        fill=255,
    )
    return mask.filter(ImageFilter.GaussianBlur(radius=feather / 2.0))


def _eye_feature_mask(box: tuple[int, int, int, int], feather: int) -> Image.Image:
    width = box[2] - box[0]
    height = box[3] - box[1]
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    pad = feather + 1
    middle = width // 2
    draw.rounded_rectangle(
        (pad, pad, middle - 3, height - pad - 1),
        radius=max(14, height // 3),
        fill=255,
    )
    draw.rounded_rectangle(
        (middle + 3, pad, width - pad - 1, height - pad - 1),
        radius=max(14, height // 3),
        fill=255,
    )
    return mask.filter(ImageFilter.GaussianBlur(radius=feather / 2.0))


def prepare_resolution_sources(
    contract_path: str | Path,
    viseme_contract_path: str | Path,
    expression_contract_path: str | Path,
) -> dict[str, Any]:
    contract, plate_path, insert_path = _load_resolution_contract(contract_path)
    viseme_contract, viseme_path = load_viseme_atlas_contract(viseme_contract_path)
    expression_contract, expression_path = load_expression_atlas_contract(expression_contract_path)
    if contract["paired_viseme_atlas"]["sha256"] != viseme_contract["image"]["sha256"]:
        raise ValueError("GS070 plate is paired to a different viseme atlas")
    if contract["paired_expression_atlas"]["sha256"] != expression_contract["image"]["sha256"]:
        raise ValueError("GS070 plate is paired to a different expression atlas")
    with Image.open(plate_path) as source:
        plate = source.convert("RGB")
    with Image.open(insert_path) as source:
        insert = source.convert("RGB")
    with Image.open(viseme_path) as source:
        viseme_cells = atlas_cells(source, viseme_contract)
    with Image.open(expression_path) as source:
        expressions = expression_cells(source, expression_contract)
    registration = contract["atlas_registration"]
    mouth_box = tuple(int(value) for value in registration["mouth_patch_box"])
    expression_box = tuple(int(value) for value in registration["expression_patch_box"])
    feather = int(registration["feature_mask_feather_px"])
    if not 4 <= feather <= 24:
        raise ValueError("GS070 feature mask feather must be between four and twenty-four pixels")
    viseme_patches, viseme_mask, plate_mouth_box = _prepare_affine_patches(
        plate,
        viseme_cells,
        mouth_box,
        _mouth_feature_mask(mouth_box, feather),
        contract,
    )
    expression_patches, expression_mask, plate_expression_box = _prepare_affine_patches(
        plate,
        expressions,
        expression_box,
        _eye_feature_mask(expression_box, feather),
        contract,
    )
    return {
        "contract": contract,
        "plate": plate,
        "plate_path": plate_path,
        "insert": insert,
        "insert_path": insert_path,
        "viseme_contract": viseme_contract,
        "viseme_patches": viseme_patches,
        "viseme_mask": viseme_mask,
        "plate_mouth_box": plate_mouth_box,
        "expression_contract": expression_contract,
        "expression_patches": expression_patches,
        "expression_mask": expression_mask,
        "plate_expression_box": plate_expression_box,
    }


def _insert_camera_frame(source: Image.Image, progress: float, width: int, height: int) -> Image.Image:
    amount = _ease(progress)
    push = 0.006 + amount * 0.018
    scale = max(width / source.width, height / source.height) * (1.0 + push)
    resized = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    extra_x = resized.width - width
    extra_y = resized.height - height
    anchor_x = 0.50 + amount * 0.10
    anchor_y = 0.48 + amount * 0.04
    left = round(max(0.0, min(float(extra_x), extra_x * anchor_x)))
    top = round(max(0.0, min(float(extra_y), extra_y * anchor_y)))
    return resized.crop((left, top, left + width, top + height))


def compose_resolution_frame(
    sources: dict[str, Any],
    viseme_entry: dict[str, Any],
    expression_entry: dict[str, Any],
    motion_entry: dict[str, float],
    *,
    frame_index: int,
    fps: int,
    secondary: dict[str, Any],
) -> Image.Image:
    contract = sources["contract"]
    output = contract["output"]
    sequence = contract["sequence"]
    cut_end = int(sequence["offer_insert_end_frame"])
    if frame_index <= cut_end:
        progress = (frame_index - 1) / max(1, cut_end - 1)
        return _insert_camera_frame(
            sources["insert"],
            progress,
            int(output["width"]),
            int(output["height"]),
        )

    regions = contract["rig_regions"]
    frame = sources["plate"].copy()
    _warp_region(
        frame,
        regions["shoulders"],
        dx=float(motion_entry["shoulder_x_px"]),
        dy=float(motion_entry["breath_y_px"]),
        scale_y=1.0 + float(motion_entry["breath_y_px"]) / 900.0,
    )
    chime = secondary.get("wind_chime") or {}
    chime_period = max(0.5, float(chime.get("period_seconds", 3.1)))
    chime_dx = float(chime.get("amplitude_px", 0.0)) * math.sin(
        frame_index / fps / chime_period * math.tau + float(chime.get("phase", 0.0))
    )
    _warp_region(frame, regions["wind_chime"], dx=chime_dx, rotation_deg=chime_dx * 0.10)

    expression_patch = _blend(
        sources["expression_patches"][expression_entry["from_state"]],
        sources["expression_patches"][expression_entry["to_state"]],
        float(expression_entry["blend"]),
    )
    frame.paste(expression_patch, sources["plate_expression_box"][:2], sources["expression_mask"])
    if frame_index < int(sequence["mouth_returns_to_authored_plate_frame"]):
        mouth_patch = _blend(
            sources["viseme_patches"][viseme_entry["from_shape"]],
            sources["viseme_patches"][viseme_entry["to_shape"]],
            float(viseme_entry["blend"]),
        )
        frame.paste(mouth_patch, sources["plate_mouth_box"][:2], sources["viseme_mask"])

    _warp_region(
        frame,
        regions["head"],
        dx=float(motion_entry["head_x_px"]),
        dy=float(motion_entry["head_y_px"]),
        rotation_deg=float(motion_entry["head_tilt_deg"]),
    )
    lantern = secondary.get("lantern") or {}
    period = max(0.2, float(lantern.get("period_seconds", 0.71)))
    flicker = float(lantern.get("flicker_strength", 0.0))
    glow = flicker * (
        0.55
        + 0.45
        * math.sin(frame_index / fps / period * math.tau + float(lantern.get("phase", 0.0)))
    )
    _lantern_glow(frame, regions["lantern"], max(0.0, glow))
    _secondary_overlay(frame, frame_index, fps, regions, secondary)
    return _camera_frame(frame, float(motion_entry["camera_push"]), contract)


def _laplacian_variance(path: Path) -> float:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"unable to read review frame: {path}")
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def render_resolution_scene(
    contract_path: str | Path,
    viseme_contract_path: str | Path,
    cue_path: str | Path,
    expression_contract_path: str | Path,
    expression_cue_path: str | Path,
    motion_cue_path: str | Path,
    output_dir: str | Path,
    *,
    audio_path: str | Path | None = None,
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    sources = prepare_resolution_sources(contract_path, viseme_contract_path, expression_contract_path)
    contract = sources["contract"]
    fps = int(contract["output"]["fps"])
    viseme_metadata, viseme_plan = performance_viseme_plan(cue_path, fps=fps, transition_frames=2)
    expression_metadata, expression_plan = expression_performance_plan(
        expression_cue_path,
        expected_atlas_id=sources["expression_contract"]["atlas_id"],
    )
    motion_metadata, motion_plan = load_body_motion_contract(motion_cue_path, hero_contract=contract)
    frame_count = int(contract["output"]["frame_count"])
    if {len(viseme_plan), len(expression_plan), len(motion_plan), frame_count} != {frame_count}:
        raise ValueError("GS070 lip expression and motion plans must share the 228-frame clock")
    durations = {
        round(float(viseme_metadata["duration_seconds"]), 6),
        round(float(expression_metadata["duration_seconds"]), 6),
        round(float(motion_metadata["duration_seconds"]), 6),
        round(float(contract["output"]["duration_seconds"]), 6),
    }
    if durations != {7.6}:
        raise ValueError("GS070 animation contracts must share the exact 7.6-second duration")

    audio = Path(audio_path).resolve() if audio_path else None
    if audio and not audio.is_file():
        raise FileNotFoundError(f"GS070 scratch audio not found: {audio}")
    executable = str(Path(ffmpeg)) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"FFmpeg executable not found: {ffmpeg}")

    output = Path(output_dir).resolve()
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()
    video = output / "june-gs070-resolution.mp4"
    partial_video = output / "june-gs070-resolution.partial.mp4"
    partial_video.unlink(missing_ok=True)
    width = int(contract["output"]["width"])
    height = int(contract["output"]["height"])
    command = [
        executable,
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
    ]
    if audio:
        command.extend(["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            "-frames:v",
            str(frame_count),
        ]
    )
    if audio:
        command.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"])
    else:
        command.append("-an")
    command.extend(["-movflags", "+faststart", str(partial_video)])
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise RuntimeError("unable to open FFmpeg raw-video pipe")
    saved: dict[int, Path] = {}
    try:
        for index, (viseme, expression, motion) in enumerate(
            zip(viseme_plan, expression_plan, motion_plan),
            start=1,
        ):
            frame = compose_resolution_frame(
                sources,
                viseme,
                expression,
                motion,
                frame_index=index,
                fps=fps,
                secondary=motion_metadata["secondary_motion"],
            )
            process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            if index in REVIEW_FRAMES:
                destination = review_dir / f"frame_{index:04d}.png"
                frame.save(destination, compress_level=2)
                saved[index] = destination
        process.stdin.close()
        error_output = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    if return_code != 0:
        partial_video.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg GS070 render failed: {error_output.strip()}")
    if not partial_video.is_file() or partial_video.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create a usable GS070 render")
    partial_video.replace(video)

    encoded_quality = encoded_quality_metrics(video, saved, frame_count)
    quality_gate = contract["encoded_quality_gate"]
    if encoded_quality["minimum_psnr_db"] < float(quality_gate["minimum_review_frame_psnr_db"]):
        raise RuntimeError("GS070 encoded PSNR fell below the production gate")
    if encoded_quality["minimum_encoded_laplacian_variance"] < float(
        quality_gate["minimum_encoded_laplacian_variance"]
    ):
        raise RuntimeError("GS070 encoded detail fell below the production gate")

    final_hold_start = int(contract["sequence"]["final_hold_start_frame"])
    final_motion = motion_plan[final_hold_start - 1 :]
    body_channels = ("head_x_px", "head_y_px", "head_tilt_deg", "shoulder_x_px", "breath_y_px")
    body_locked = all(
        all(abs(float(entry[channel])) <= 1e-9 for channel in body_channels)
        for entry in final_motion
    )
    hold_live = _sha256(saved[final_hold_start]) != _sha256(saved[frame_count])
    sharpness = {str(frame): _laplacian_variance(path) for frame, path in saved.items()}
    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "gs070_registered_resolution_production_pixels",
        "shot_id": "GS070",
        "plate_id": contract["plate_id"],
        "plate_sha256": contract["image"]["sha256"],
        "offer_insert_sha256": contract["offer_insert"]["sha256"],
        "viseme_atlas_sha256": sources["viseme_contract"]["image"]["sha256"],
        "viseme_cue_sha256": viseme_metadata["sha256"],
        "expression_atlas_sha256": sources["expression_contract"]["image"]["sha256"],
        "expression_cue_sha256": expression_metadata["sha256"],
        "motion_cue_sha256": motion_metadata["sha256"],
        "atlas_registration": {
            "affine_matrix": contract["atlas_registration"]["affine_matrix"],
            "mouth_box": list(sources["plate_mouth_box"]),
            "expression_box": list(sources["plate_expression_box"]),
        },
        "sequence": {
            **contract["sequence"],
            "transition": "hard_cut_on_frame_46",
            "interpolated_source_frames": 0,
        },
        "production_pixel_sources": [sources["insert_path"].name, sources["plate_path"].name],
        "final_hold": {
            "start_frame": final_hold_start,
            "frame_count": int(contract["sequence"]["final_hold_frames"]),
            "body_locked": body_locked,
            "secondary_motion_live": hold_live,
        },
        "audio": {"file": audio.name, "sha256": _sha256(audio)} if audio else None,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": 7.6,
        "width": width,
        "height": height,
        "review_frames": [path.name for _, path in sorted(saved.items())],
        "review_laplacian_variance": sharpness,
        "minimum_review_laplacian_variance": min(sharpness.values()),
        "encoded_quality": encoded_quality,
        "first_frame_sha256": _sha256(saved[1]),
        "cut_out_frame_sha256": _sha256(saved[45]),
        "cut_in_frame_sha256": _sha256(saved[46]),
        "last_frame_sha256": _sha256(saved[frame_count]),
        "video": video.name,
        "video_sha256": _sha256(video),
    }
    if not body_locked or not hold_live:
        raise RuntimeError("GS070 final hold failed its locked-body/live-porch gate")
    (output / "june-gs070-resolution-report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's exact-clock GS070 resolution performance")
    parser.add_argument("contract")
    parser.add_argument("viseme_contract")
    parser.add_argument("--cues", required=True)
    parser.add_argument("--expression-atlas", required=True)
    parser.add_argument("--expression-cues", required=True)
    parser.add_argument("--body-motion", required=True)
    parser.add_argument("--audio")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--output-dir", default="build/edit/june-gs070-resolution")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_resolution_scene(
        args.contract,
        args.viseme_contract,
        args.cues,
        args.expression_atlas,
        args.expression_cues,
        args.body_motion,
        args.output_dir,
        audio_path=args.audio,
        ffmpeg=args.ffmpeg,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
