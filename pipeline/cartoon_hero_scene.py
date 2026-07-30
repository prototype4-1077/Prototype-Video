"""Render June's identity-locked facial performance inside a widescreen hero plate."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from pipeline.cartoon_expression_atlas import (
    expression_cells,
    expression_patch_mask,
    expression_performance_plan,
    load_expression_atlas_contract,
)
from pipeline.cartoon_gesture_atlas import (
    apply_gesture_pose,
    gesture_performance_plan,
    prepare_gesture_sources,
)
from pipeline.cartoon_viseme_atlas import (
    atlas_cells,
    load_viseme_atlas_contract,
    mouth_patch_mask,
    performance_viseme_plan,
)


HERO_CONTRACT_VERSION = 1
MOTION_CHANNELS = (
    "head_x_px",
    "head_y_px",
    "head_tilt_deg",
    "shoulder_x_px",
    "breath_y_px",
    "camera_push",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_asset(contract_path: Path, specification: dict[str, Any], label: str) -> Path:
    repo_root = contract_path.parents[2]
    path = repo_root / str(specification.get("path", ""))
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    if _sha256(path) != specification.get("sha256"):
        raise ValueError(f"{label} hash does not match")
    return path


def _valid_box(value: Any, width: int, height: int) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    left, top, right, bottom = (int(item) for item in value)
    return 0 <= left < right <= width and 0 <= top < bottom <= height


def load_hero_plate_contract(path: str | Path) -> tuple[dict[str, Any], Path]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != HERO_CONTRACT_VERSION:
        raise ValueError(f"hero contract_version must be {HERO_CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("hero plate must explicitly target June Oxley")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0 or generation.get("paid_runtime_dependency") is not False:
        raise ValueError("hero plate must preserve the zero-cash production contract")

    image_spec = contract.get("image") or {}
    image_path = _repo_asset(contract_path, image_spec, "hero plate")
    width = int(image_spec.get("width", 0))
    height = int(image_spec.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("hero plate dimensions must be positive")
    with Image.open(image_path) as image:
        if image.size != (width, height) or image.mode != image_spec.get("mode"):
            raise ValueError("hero plate image does not match its dimension/mode contract")

    for key, label in (
        ("canonical_identity_reference", "canonical identity reference"),
        ("paired_viseme_atlas", "paired viseme atlas"),
        ("paired_expression_atlas", "paired expression atlas"),
    ):
        _repo_asset(contract_path, contract.get(key) or {}, label)

    output = contract.get("output") or {}
    output_width = int(output.get("width", 0))
    output_height = int(output.get("height", 0))
    fps = int(output.get("fps", 0))
    if (output_width, output_height, fps) != (1920, 1080, 30):
        raise ValueError("hero output contract must be 1920x1080 at 30 fps")

    registration = contract.get("atlas_registration") or {}
    if (int(registration.get("cell_width", 0)), int(registration.get("cell_height", 0))) != (418, 418):
        raise ValueError("hero registration must target the canonical 418px atlas cells")
    scale = float(registration.get("scale", 0.0))
    offset = registration.get("offset") or []
    if not 0.5 <= scale <= 3.0 or len(offset) != 2:
        raise ValueError("hero atlas registration is invalid")
    strength = float(registration.get("patch_color_match_strength", -1.0))
    if not 0.0 <= strength <= 1.0:
        raise ValueError("patch_color_match_strength must be in [0, 1]")

    regions = contract.get("rig_regions") or {}
    for name in ("head", "shoulders", "wind_chime", "lantern"):
        if not _valid_box(regions.get(name), width, height):
            raise ValueError(f"hero rig region {name!r} is invalid")
    origin = regions.get("steam_origin") or []
    anchor = regions.get("camera_anchor") or []
    if len(origin) != 2 or not (0 <= int(origin[0]) < width and 0 <= int(origin[1]) < height):
        raise ValueError("steam_origin must stay inside the plate")
    if len(anchor) != 2 or not all(0.0 <= float(value) <= 1.0 for value in anchor):
        raise ValueError("camera_anchor must use normalized coordinates")

    bounds = contract.get("motion_bounds") or {}
    for channel in MOTION_CHANNELS:
        values = bounds.get(channel)
        if not isinstance(values, list) or len(values) != 2 or float(values[0]) > float(values[1]):
            raise ValueError(f"motion bound {channel!r} is invalid")
    return contract, image_path


def _ease_in_out_cubic(value: float) -> float:
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def load_body_motion_contract(
    path: str | Path,
    *,
    hero_contract: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, float]]]:
    source = Path(path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("contract_version") != HERO_CONTRACT_VERSION:
        raise ValueError("body motion contract_version does not match")
    if payload.get("plate_id") != hero_contract.get("plate_id"):
        raise ValueError("body motion contract targets the wrong hero plate")
    if payload.get("interpolation") != "cubic_ease":
        raise ValueError("body motion must use cubic_ease interpolation")
    fps = int(payload.get("fps", 0))
    frame_count = int(payload.get("frame_count", 0))
    duration = float(payload.get("duration_seconds", 0.0))
    if fps != int(hero_contract["output"]["fps"]) or frame_count != round(duration * fps):
        raise ValueError("body motion must use the hero plate's exact frame clock")
    keyframes = payload.get("keyframes") or []
    if len(keyframes) < 2:
        raise ValueError("body motion needs at least two keyframes")
    frame_numbers = [int(item.get("frame", 0)) for item in keyframes]
    if frame_numbers[0] != 1 or frame_numbers[-1] != frame_count:
        raise ValueError("body motion must key both the first and last frame")
    if frame_numbers != sorted(set(frame_numbers)):
        raise ValueError("body motion keyframes must be strictly increasing")
    bounds = hero_contract["motion_bounds"]
    for keyframe in keyframes:
        for channel in MOTION_CHANNELS:
            value = float(keyframe.get(channel, math.nan))
            low, high = (float(item) for item in bounds[channel])
            if not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"body motion {channel} exceeds the hero rig bound")

    plan: list[dict[str, float]] = []
    segment = 0
    for frame in range(1, frame_count + 1):
        while segment + 1 < len(keyframes) - 1 and frame > int(keyframes[segment + 1]["frame"]):
            segment += 1
        first = keyframes[segment]
        second = keyframes[segment + 1]
        span = int(second["frame"]) - int(first["frame"])
        progress = 1.0 if span <= 0 else (frame - int(first["frame"])) / span
        amount = _ease_in_out_cubic(max(0.0, min(1.0, progress)))
        entry: dict[str, float] = {"frame": float(frame)}
        for channel in MOTION_CHANNELS:
            start = float(first[channel])
            end = float(second[channel])
            entry[channel] = start + (end - start) * amount
        plan.append(entry)
    metadata = {
        "path": source,
        "sha256": _sha256(source),
        "performance_id": payload["performance_id"],
        "performance_version": payload["performance_version"],
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration,
        "keyframe_count": len(keyframes),
        "secondary_motion": payload.get("secondary_motion") or {},
    }
    return metadata, plan


def atlas_box_to_plate(box: tuple[int, int, int, int], hero_contract: dict[str, Any]) -> tuple[int, int, int, int]:
    registration = hero_contract["atlas_registration"]
    scale = float(registration["scale"])
    offset_x, offset_y = (float(value) for value in registration["offset"])
    left, top, right, bottom = box
    return (
        round(offset_x + left * scale),
        round(offset_y + top * scale),
        round(offset_x + right * scale),
        round(offset_y + bottom * scale),
    )


def _color_match_patch(
    patch: Image.Image,
    target: Image.Image,
    mask: Image.Image,
    strength: float,
) -> Image.Image:
    source_array = np.asarray(patch.convert("RGB"), dtype=np.float32)
    target_array = np.asarray(target.convert("RGB"), dtype=np.float32)
    alpha = np.asarray(mask.convert("L"), dtype=np.uint8) >= 80
    if not alpha.any():
        return patch.convert("RGB")
    adjusted = source_array.copy()
    for channel in range(3):
        source_values = source_array[:, :, channel][alpha]
        target_values = target_array[:, :, channel][alpha]
        source_mean = float(source_values.mean())
        target_mean = float(target_values.mean())
        source_std = max(1.0, float(source_values.std()))
        target_std = max(1.0, float(target_values.std()))
        corrected = (source_array[:, :, channel] - source_mean) * (target_std / source_std) + target_mean
        adjusted[:, :, channel] = source_array[:, :, channel] * (1.0 - strength) + corrected * strength
    return Image.fromarray(np.clip(adjusted, 0, 255).astype(np.uint8), "RGB")


def _prepare_registered_patches(
    plate: Image.Image,
    cells: dict[str, Image.Image],
    atlas_box: tuple[int, int, int, int],
    atlas_mask: Image.Image,
    hero_contract: dict[str, Any],
) -> tuple[dict[str, Image.Image], Image.Image, tuple[int, int, int, int]]:
    plate_box = atlas_box_to_plate(atlas_box, hero_contract)
    width = plate_box[2] - plate_box[0]
    height = plate_box[3] - plate_box[1]
    mask = atlas_mask.resize((width, height), Image.Resampling.LANCZOS)
    target = plate.crop(plate_box)
    strength = float(hero_contract["atlas_registration"]["patch_color_match_strength"])
    patches = {}
    for name, cell in cells.items():
        resized = cell.crop(atlas_box).resize((width, height), Image.Resampling.LANCZOS)
        patches[name] = _color_match_patch(resized, target, mask, strength)
    return patches, mask, plate_box


def _blend(source: Image.Image, target: Image.Image, amount: float) -> Image.Image:
    if amount >= 1.0:
        return target
    if amount <= 0.0:
        return source
    return Image.blend(source, target, amount)


def _warp_region(
    image: Image.Image,
    box: list[int],
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    rotation_deg: float = 0.0,
    scale_y: float = 1.0,
) -> None:
    left, top, right, bottom = (int(value) for value in box)
    crop = np.asarray(image.crop((left, top, right, bottom)).convert("RGB"))
    height, width = crop.shape[:2]
    y_grid, x_grid = np.mgrid[0:height, 0:width].astype(np.float32)
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    normalized = np.maximum(np.abs((x_grid - center_x) / max(1.0, center_x)), np.abs((y_grid - center_y) / max(1.0, center_y)))
    weight = np.clip((1.0 - normalized) / 0.38, 0.0, 1.0)
    weight = weight * weight * (3.0 - 2.0 * weight)
    angle = math.radians(rotation_deg)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    relative_x = x_grid - center_x - dx
    relative_y = y_grid - center_y - dy
    source_x = cosine * relative_x + sine * relative_y + center_x
    source_y = (-sine * relative_x + cosine * relative_y) / max(0.96, min(1.04, scale_y)) + center_y
    map_x = x_grid * (1.0 - weight) + source_x * weight
    map_y = y_grid * (1.0 - weight) + source_y * weight
    warped = cv2.remap(crop, map_x, map_y, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
    image.paste(Image.fromarray(warped, "RGB"), (left, top))


def _lantern_glow(image: Image.Image, box: list[int], amount: float) -> None:
    left, top, right, bottom = (int(value) for value in box)
    width = right - left
    height = bottom - top
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse((width * 0.18, height * 0.13, width * 0.82, height * 0.92), fill=round(255 * amount))
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(8.0, width * 0.16)))
    glow = Image.new("RGB", (width, height), (255, 178, 72))
    image.paste(glow, (left, top), mask)


def _secondary_overlay(
    image: Image.Image,
    frame_index: int,
    fps: int,
    regions: dict[str, Any],
    secondary: dict[str, Any],
) -> None:
    time_seconds = frame_index / fps
    steam = secondary.get("steam") or {}
    origin_x, origin_y = (float(value) for value in regions["steam_origin"])
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    strand_count = int(steam.get("strand_count", 0))
    rise = float(steam.get("rise_px", 0.0))
    period = max(0.5, float(steam.get("period_seconds", 2.4)))
    opacity = int(steam.get("opacity", 0))
    for strand in range(strand_count):
        phase = time_seconds / period * math.tau + strand * 1.91
        points = []
        for step in range(22):
            fraction = step / 21.0
            x = origin_x + (strand - (strand_count - 1) / 2.0) * 13.0 + math.sin(phase + fraction * 7.0) * (3.0 + 7.0 * fraction)
            y = origin_y - 8.0 - fraction * rise
            points.append((x, y))
        draw.line(points, fill=(228, 225, 210, max(0, round(opacity * (0.85 + 0.15 * math.sin(phase))))), width=3)

    dust = secondary.get("dust") or {}
    generator = random.Random(int(dust.get("seed", 0)))
    particle_count = int(dust.get("particle_count", 0))
    dust_opacity = int(dust.get("opacity", 0))
    width, height = image.size
    for index in range(particle_count):
        base_x = generator.uniform(width * 0.58, width * 0.96)
        base_y = generator.uniform(height * 0.12, height * 0.82)
        speed = generator.uniform(3.0, 11.0)
        x = base_x + math.sin(time_seconds * 0.65 + index) * 5.0
        y = (base_y - time_seconds * speed) % (height * 0.78) + height * 0.08
        radius = generator.choice((1.0, 1.4, 1.8, 2.2))
        pulse = 0.55 + 0.45 * math.sin(time_seconds * 1.7 + index * 1.13) ** 2
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 220, 145, round(dust_opacity * pulse)))
    composited = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    image.paste(composited)


def _camera_frame(image: Image.Image, push: float, contract: dict[str, Any]) -> Image.Image:
    output = contract["output"]
    output_width = int(output["width"])
    output_height = int(output["height"])
    scale = max(output_width / image.width, output_height / image.height) * (1.0 + push)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    anchor_x, anchor_y = (float(value) for value in contract["rig_regions"]["camera_anchor"])
    extra_x = resized.width - output_width
    extra_y = resized.height - output_height
    left = round(max(0.0, min(float(extra_x), extra_x * anchor_x)))
    top = round(max(0.0, min(float(extra_y), extra_y * anchor_y)))
    return resized.crop((left, top, left + output_width, top + output_height))


def prepare_hero_sources(
    hero_contract_path: str | Path,
    viseme_contract_path: str | Path,
    expression_contract_path: str | Path,
) -> dict[str, Any]:
    hero_contract, plate_path = load_hero_plate_contract(hero_contract_path)
    viseme_contract, viseme_path = load_viseme_atlas_contract(viseme_contract_path)
    expression_contract, expression_path = load_expression_atlas_contract(expression_contract_path)
    if hero_contract["paired_viseme_atlas"]["sha256"] != viseme_contract["image"]["sha256"]:
        raise ValueError("hero plate is paired to a different viseme atlas")
    if hero_contract["paired_expression_atlas"]["sha256"] != expression_contract["image"]["sha256"]:
        raise ValueError("hero plate is paired to a different expression atlas")
    with Image.open(plate_path) as source:
        plate = source.convert("RGB")
    with Image.open(viseme_path) as source:
        viseme_cells = atlas_cells(source, viseme_contract)
    with Image.open(expression_path) as source:
        expression_cell_map = expression_cells(source, expression_contract)
    mouth_box = tuple(int(value) for value in viseme_contract["mouth_patch_box"])
    expression_box = tuple(int(value) for value in expression_contract["expression_patch_box"])
    viseme_patches, viseme_mask, plate_mouth_box = _prepare_registered_patches(
        plate, viseme_cells, mouth_box, mouth_patch_mask(viseme_contract), hero_contract
    )
    expression_patches, expression_mask, plate_expression_box = _prepare_registered_patches(
        plate, expression_cell_map, expression_box, expression_patch_mask(expression_contract), hero_contract
    )
    return {
        "hero_contract": hero_contract,
        "plate_path": plate_path,
        "plate": plate,
        "viseme_contract": viseme_contract,
        "viseme_patches": viseme_patches,
        "viseme_mask": viseme_mask,
        "plate_mouth_box": plate_mouth_box,
        "expression_contract": expression_contract,
        "expression_patches": expression_patches,
        "expression_mask": expression_mask,
        "plate_expression_box": plate_expression_box,
    }


def compose_hero_frame(
    sources: dict[str, Any],
    viseme_entry: dict[str, Any],
    expression_entry: dict[str, Any],
    motion_entry: dict[str, float],
    *,
    secondary: dict[str, Any],
    frame_index: int,
    fps: int,
    gesture_sources: dict[str, Any] | None = None,
    gesture_entry: dict[str, Any] | None = None,
) -> Image.Image:
    contract = sources["hero_contract"]
    regions = contract["rig_regions"]
    frame = sources["plate"].copy()
    overlay_regions = dict(regions)

    if gesture_sources is not None and gesture_entry is not None:
        gesture_state, gesture_amount, raised_origin = apply_gesture_pose(frame, gesture_sources, gesture_entry)
        if gesture_state == "mug_lift" and raised_origin is not None:
            overlay_regions["steam_origin"] = list(raised_origin)

    _warp_region(
        frame,
        regions["shoulders"],
        dx=float(motion_entry["shoulder_x_px"]),
        dy=float(motion_entry["breath_y_px"]),
        scale_y=1.0 + float(motion_entry["breath_y_px"]) / 900.0,
    )
    chime = secondary.get("wind_chime") or {}
    chime_period = max(0.5, float(chime.get("period_seconds", 2.9)))
    chime_dx = float(chime.get("amplitude_px", 0.0)) * math.sin(frame_index / fps / chime_period * math.tau + float(chime.get("phase", 0.0)))
    _warp_region(frame, regions["wind_chime"], dx=chime_dx, rotation_deg=chime_dx * 0.12)

    expression_patch = _blend(
        sources["expression_patches"][expression_entry["from_state"]],
        sources["expression_patches"][expression_entry["to_state"]],
        float(expression_entry["blend"]),
    )
    frame.paste(expression_patch, sources["plate_expression_box"][:2], sources["expression_mask"])
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
    lantern_period = max(0.2, float(lantern.get("period_seconds", 0.63)))
    flicker = float(lantern.get("flicker_strength", 0.0))
    amount = flicker * (0.55 + 0.45 * math.sin(frame_index / fps / lantern_period * math.tau + float(lantern.get("phase", 0.0))))
    _lantern_glow(frame, regions["lantern"], max(0.0, amount))
    _secondary_overlay(frame, frame_index, fps, overlay_regions, secondary)
    return _camera_frame(frame, float(motion_entry["camera_push"]), contract)


def render_hero_performance(
    hero_contract_path: str | Path,
    viseme_contract_path: str | Path,
    cue_path: str | Path,
    expression_contract_path: str | Path,
    expression_cue_path: str | Path,
    motion_cue_path: str | Path,
    output_dir: str | Path,
    *,
    audio_path: str | Path | None = None,
    gesture_contract_path: str | Path | None = None,
    gesture_cue_path: str | Path | None = None,
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    if bool(gesture_contract_path) != bool(gesture_cue_path):
        raise ValueError("gesture_contract_path and gesture_cue_path must be supplied together")
    sources = prepare_hero_sources(hero_contract_path, viseme_contract_path, expression_contract_path)
    contract = sources["hero_contract"]
    fps = int(contract["output"]["fps"])
    viseme_metadata, viseme_plan = performance_viseme_plan(cue_path, fps=fps, transition_frames=2)
    expression_metadata, expression_plan = expression_performance_plan(
        expression_cue_path,
        expected_atlas_id=sources["expression_contract"]["atlas_id"],
    )
    motion_metadata, motion_plan = load_body_motion_contract(motion_cue_path, hero_contract=contract)
    gesture_metadata = None
    gesture_plan = None
    gesture_sources = None
    if gesture_contract_path and gesture_cue_path:
        gesture_sources = prepare_gesture_sources(
            gesture_contract_path,
            expected_plate_id=contract["plate_id"],
            expected_base_sha256=contract["image"]["sha256"],
        )
        gesture_metadata, gesture_plan = gesture_performance_plan(
            gesture_cue_path,
            expected_atlas_id=gesture_sources["contract"]["atlas_id"],
        )
    counts = {len(viseme_plan), len(expression_plan), len(motion_plan)}
    if gesture_plan is not None:
        counts.add(len(gesture_plan))
    durations = {
        round(float(viseme_metadata["duration_seconds"]), 6),
        round(float(expression_metadata["duration_seconds"]), 6),
        round(float(motion_metadata["duration_seconds"]), 6),
    }
    if gesture_metadata is not None:
        durations.add(round(float(gesture_metadata["duration_seconds"]), 6))
    if len(counts) != 1 or len(durations) != 1:
        raise ValueError("lip, expression, and body motion plans must share one exact frame clock")
    frame_count = len(viseme_plan)
    audio = Path(audio_path).resolve() if audio_path else None
    if audio and not audio.is_file():
        raise FileNotFoundError(f"performance audio not found: {audio}")
    executable = str(Path(ffmpeg)) if Path(ffmpeg).is_file() else shutil.which(ffmpeg)
    if not executable:
        raise FileNotFoundError(f"FFmpeg executable not found: {ffmpeg}")

    output = Path(output_dir).resolve()
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()
    video = output / "june-hero-expression-performance.mp4"
    partial_video = output / "june-hero-expression-performance.partial.mp4"
    partial_video.unlink(missing_ok=True)
    width = int(contract["output"]["width"])
    height = int(contract["output"]["height"])
    command = [
        executable, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s:v", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
    ]
    if audio:
        command.extend(["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"])
    command.extend([
        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
        "-frames:v", str(frame_count),
    ])
    if audio:
        command.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"])
    else:
        command.append("-an")
    command.extend(["-movflags", "+faststart", str(partial_video)])
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise RuntimeError("unable to open FFmpeg raw-video pipe")
    review_numbers = {1, 42, 90, 150, 250, 332, 381, 410, frame_count}
    saved: dict[int, Path] = {}
    frame_gestures = gesture_plan if gesture_plan is not None else [None] * frame_count
    try:
        for index, (viseme_entry, expression_entry, motion_entry, gesture_entry) in enumerate(
            zip(viseme_plan, expression_plan, motion_plan, frame_gestures), start=1
        ):
            frame = compose_hero_frame(
                sources,
                viseme_entry,
                expression_entry,
                motion_entry,
                secondary=motion_metadata["secondary_motion"],
                frame_index=index,
                fps=fps,
                gesture_sources=gesture_sources,
                gesture_entry=gesture_entry,
            )
            process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            if index in review_numbers:
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
        raise RuntimeError(f"FFmpeg hero render failed: {error_output.strip()}")
    if not partial_video.is_file() or partial_video.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create a usable hero performance")
    partial_video.replace(video)
    first_frame = saved[1]
    last_frame = saved[frame_count]
    report = {
        "contract_version": HERO_CONTRACT_VERSION,
        "gate": "identity_locked_1920x1080_hero_performance",
        "plate_id": contract["plate_id"],
        "plate_version": contract["plate_version"],
        "plate_sha256": contract["image"]["sha256"],
        "viseme_atlas_sha256": sources["viseme_contract"]["image"]["sha256"],
        "viseme_cue_sha256": viseme_metadata["sha256"],
        "expression_atlas_sha256": sources["expression_contract"]["image"]["sha256"],
        "expression_cue_sha256": expression_metadata["sha256"],
        "motion_cue_sha256": motion_metadata["sha256"],
        "motion_keyframe_count": motion_metadata["keyframe_count"],
        "gesture": {
            "atlas_id": gesture_sources["contract"]["atlas_id"],
            "atlas_version": gesture_sources["contract"]["atlas_version"],
            "cue_sha256": gesture_metadata["sha256"],
            "cue_count": gesture_metadata["cue_count"],
            "states": gesture_metadata["states"],
        } if gesture_metadata else None,
        "audio": {"file": audio.name, "sha256": _sha256(audio)} if audio else None,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": viseme_metadata["duration_seconds"],
        "width": width,
        "height": height,
        "review_frames": [path.name for _, path in sorted(saved.items())],
        "first_frame_sha256": _sha256(first_frame),
        "last_frame_sha256": _sha256(last_frame),
        "video": video.name,
        "video_sha256": _sha256(video),
    }
    (output / "june-hero-expression-performance-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's identity-locked 1920x1080 porch performance")
    parser.add_argument("hero_contract")
    parser.add_argument("viseme_contract")
    parser.add_argument("--cues", required=True)
    parser.add_argument("--expression-atlas", required=True)
    parser.add_argument("--expression-cues", required=True)
    parser.add_argument("--body-motion", required=True)
    parser.add_argument("--gesture-atlas")
    parser.add_argument("--gesture-cues")
    parser.add_argument("--audio")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--output-dir", default="build/edit/june-hero-expression-performance")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if bool(args.gesture_atlas) != bool(args.gesture_cues):
        raise SystemExit("--gesture-atlas and --gesture-cues must be supplied together")
    report = render_hero_performance(
        args.hero_contract,
        args.viseme_contract,
        args.cues,
        args.expression_atlas,
        args.expression_cues,
        args.body_motion,
        args.output_dir,
        audio_path=args.audio,
        gesture_contract_path=args.gesture_atlas,
        gesture_cue_path=args.gesture_cues,
        ffmpeg=args.ffmpeg,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
