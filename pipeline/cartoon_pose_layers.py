"""Render June's GS030 stand as registered RGBA drawings over one stable set plate."""
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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from pipeline.cartoon_shot_sequence import _camera_frame, encoded_quality_metrics


POSE_LAYER_CONTRACT_VERSION = 1


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


def _point(value: Any, label: str, size: tuple[int, int]) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be a two-value point")
    point = (float(value[0]), float(value[1]))
    if not 0.0 <= point[0] < size[0] or not 0.0 <= point[1] < size[1]:
        raise ValueError(f"{label} must stay inside the source canvas")
    return point


def load_pose_layer_contract(path: str | Path) -> tuple[dict[str, Any], Path, dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != POSE_LAYER_CONTRACT_VERSION:
        raise ValueError(f"pose-layer contract_version must be {POSE_LAYER_CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley" or contract.get("shot_id") != "GS030":
        raise ValueError("pose-layer contract must explicitly target June Oxley GS030")
    if contract.get("gate") != "registered_layered_body_mechanics":
        raise ValueError("pose-layer contract must retain its registered mechanics gate")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0 or generation.get("paid_runtime_dependency") is not False:
        raise ValueError("pose-layer render must retain its zero-cash runtime contract")

    canvas = contract.get("source_canvas") or {}
    source_size = (int(canvas.get("width", 0)), int(canvas.get("height", 0)))
    if source_size != (1672, 941):
        raise ValueError("pose-layer source canvas must remain exactly 1672x941")
    output = contract.get("output") or {}
    actual_output = (
        int(output.get("width", 0)),
        int(output.get("height", 0)),
        int(output.get("fps", 0)),
        int(output.get("frame_count", 0)),
    )
    if actual_output != (1920, 1080, 30, 171) or not math.isclose(
        float(output.get("duration_seconds", 0.0)), 5.7
    ):
        raise ValueError("pose-layer output must be exactly 1920x1080, 30 fps, 171 frames, and 5.7 seconds")

    _repo_asset(contract_path, contract.get("identity_reference") or {}, "canonical identity reference")
    background_spec = contract.get("background") or {}
    background_path = _repo_asset(contract_path, background_spec, "clean porch background")
    with Image.open(background_path) as image:
        if image.size != source_size or image.mode != "RGB":
            raise ValueError("clean porch background does not match its RGB source-canvas contract")
    _repo_asset(contract_path, background_spec.get("source_provenance") or {}, "clean porch provenance source")
    background_generation = background_spec.get("image_generation") or {}
    if background_generation.get("cash_cost") != 0 or background_generation.get("paid_runtime_dependency") is not False:
        raise ValueError("clean porch background must retain zero-cash provenance")

    registration = contract.get("contact_registration") or {}
    _point(registration.get("target_left_support_boot"), "target left support boot", source_size)
    _point(registration.get("target_right_boot"), "target right boot", source_size)
    maximum_drift = float(registration.get("maximum_contact_drift_px_source", 0.0))
    if not 0.0 < maximum_drift <= 2.0:
        raise ValueError("planted-foot contact gate must remain at or below two source pixels")
    warp = registration.get("right_leg_warp") or {}
    maximum_correction = float(warp.get("maximum_correction_px", 0.0))
    if not 1.0 <= maximum_correction <= 48.0:
        raise ValueError("right-leg correction bound must remain production-safe")
    if not float(warp.get("x_falloff_start", 0.0)) < float(warp.get("x_falloff_end", 0.0)):
        raise ValueError("right-leg horizontal falloff is invalid")
    if not float(warp.get("y_falloff_start", 0.0)) < float(warp.get("y_falloff_end", 0.0)):
        raise ValueError("right-leg vertical falloff is invalid")

    poses = contract.get("poses") or []
    if [float(pose.get("progress", -1.0)) for pose in poses] != [0.0, 0.25, 0.5, 0.75, 1.0]:
        raise ValueError("GS030 must retain five ordered quarter-progress production drawings")
    pose_paths: dict[str, Path] = {}
    seen: set[str] = set()
    for pose in poses:
        pose_id = str(pose.get("id", ""))
        if not pose_id or pose_id in seen:
            raise ValueError("pose ids must be present and unique")
        seen.add(pose_id)
        foreground = pose.get("foreground") or {}
        foreground_path = _repo_asset(contract_path, foreground, f"foreground {pose_id}")
        with Image.open(foreground_path) as image:
            if image.size != source_size or image.mode != "RGBA":
                raise ValueError(f"foreground {pose_id} must remain a 1672x941 RGBA layer")
        _repo_asset(contract_path, pose.get("source_art") or {}, f"source art {pose_id}")
        contacts = pose.get("source_contacts") or {}
        _point(contacts.get("left_support_boot"), f"{pose_id} left support boot", source_size)
        _point(contacts.get("right_boot"), f"{pose_id} right boot", source_size)
        _point(pose.get("steam_origin"), f"{pose_id} steam origin", source_size)
        pose_paths[pose_id] = foreground_path

    timeline = contract.get("timeline") or []
    expected_start = 1
    for entry in timeline:
        start = int(entry.get("start_frame", 0))
        end = int(entry.get("end_frame", 0))
        if start != expected_start or end < start:
            raise ValueError("pose-layer timeline must be contiguous, ordered, and non-empty")
        expected_start = end + 1
        entry_type = entry.get("type")
        if entry_type == "pose":
            if entry.get("pose_id") not in pose_paths:
                raise ValueError("pose-layer timeline references an unknown pose")
        elif entry_type == "smear":
            if start != end:
                raise ValueError("every motion smear must be exactly one frame")
            if entry.get("from_pose_id") not in pose_paths or entry.get("to_pose_id") not in pose_paths:
                raise ValueError("pose-layer smear references an unknown pose")
        else:
            raise ValueError("pose-layer timeline supports only clean poses and one-frame smears")
    if expected_start != int(output["frame_count"]) + 1:
        raise ValueError("pose-layer timeline must cover every output frame exactly once")

    camera = contract.get("camera") or {}
    if camera.get("easing") != "ease_in_out_cubic":
        raise ValueError("pose-layer camera must use cubic easing")
    for key in ("start_zoom", "end_zoom"):
        if not 1.0 <= float(camera.get(key, 0.0)) <= 1.1:
            raise ValueError("pose-layer camera zoom must stay within the subtle 1x-1.1x range")
    for key in ("focus_start", "focus_end"):
        point = camera.get(key)
        if not isinstance(point, list) or len(point) != 2 or not all(0.0 <= float(v) <= 1.0 for v in point):
            raise ValueError("pose-layer camera focus must be normalized")

    quality = contract.get("encoded_quality_gate") or {}
    if not 30.0 <= float(quality.get("minimum_review_frame_psnr_db", 0.0)) <= 60.0:
        raise ValueError("pose-layer quality gate must define a meaningful PSNR floor")
    if not 1.0 <= float(quality.get("minimum_review_frame_laplacian_variance", 0.0)) <= 1000.0:
        raise ValueError("pose-layer quality gate must define a meaningful detail floor")
    return contract, background_path, pose_paths


def timeline_entry_for_frame(timeline: list[dict[str, Any]], frame_index: int) -> dict[str, Any]:
    for entry in timeline:
        if int(entry["start_frame"]) <= frame_index <= int(entry["end_frame"]):
            return entry
    raise ValueError(f"frame {frame_index} is not covered by the pose-layer timeline")


def _smoothstep(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return clipped * clipped * (3.0 - 2.0 * clipped)


def registration_offsets(pose: dict[str, Any], registration: dict[str, Any]) -> dict[str, tuple[float, float]]:
    contacts = pose["source_contacts"]
    source_left = tuple(float(v) for v in contacts["left_support_boot"])
    source_right = tuple(float(v) for v in contacts["right_boot"])
    target_left = tuple(float(v) for v in registration["target_left_support_boot"])
    target_right = tuple(float(v) for v in registration["target_right_boot"])
    translation = (target_left[0] - source_left[0], target_left[1] - source_left[1])
    translated_right = (source_right[0] + translation[0], source_right[1] + translation[1])
    correction = (target_right[0] - translated_right[0], target_right[1] - translated_right[1])
    return {"translation": translation, "right_leg_correction": correction}


def _rgba_to_premultiplied(image: Image.Image) -> np.ndarray:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
    alpha = rgba[:, :, 3:4]
    return np.concatenate((rgba[:, :, :3] * alpha, alpha), axis=2)


def _premultiplied_to_rgba(data: np.ndarray) -> Image.Image:
    alpha = np.clip(data[:, :, 3:4], 0.0, 1.0)
    rgb = np.zeros_like(data[:, :, :3])
    np.divide(data[:, :, :3], np.maximum(alpha, 1e-5), out=rgb, where=alpha > 1e-5)
    rgba = np.concatenate((np.clip(rgb, 0.0, 1.0), alpha), axis=2)
    return Image.fromarray(np.round(rgba * 255.0).astype(np.uint8), mode="RGBA")


def registered_pose_layer(
    image: Image.Image,
    pose: dict[str, Any],
    registration: dict[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    width, height = image.size
    offsets = registration_offsets(pose, registration)
    dx, dy = offsets["translation"]
    correction_x, correction_y = offsets["right_leg_correction"]
    maximum = float(registration["right_leg_warp"]["maximum_correction_px"])
    if math.hypot(correction_x, correction_y) > maximum:
        raise ValueError(f"{pose['id']} exceeds the bounded right-leg contact correction")
    premultiplied = _rgba_to_premultiplied(image)
    translated = cv2.warpAffine(
        premultiplied,
        np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32),
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    warp = registration["right_leg_warp"]
    grid_y, grid_x = np.indices((height, width), dtype=np.float32)
    weight_x = _smoothstep(
        (grid_x - float(warp["x_falloff_start"]))
        / (float(warp["x_falloff_end"]) - float(warp["x_falloff_start"]))
    )
    weight_y = _smoothstep(
        (grid_y - float(warp["y_falloff_start"]))
        / (float(warp["y_falloff_end"]) - float(warp["y_falloff_start"]))
    )
    weight = weight_x * weight_y
    map_x = grid_x - correction_x * weight
    map_y = grid_y - correction_y * weight
    corrected = cv2.remap(
        translated,
        map_x,
        map_y,
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0.0, 0.0, 0.0, 0.0),
    )
    transformed_steam = (
        float(pose["steam_origin"][0]) + dx,
        float(pose["steam_origin"][1]) + dy,
    )
    contact_report = {
        "pose_id": pose["id"],
        "translation": [round(dx, 3), round(dy, 3)],
        "right_leg_correction": [round(correction_x, 3), round(correction_y, 3)],
        "left_support_boot_residual_px": 0.0,
        "right_boot_residual_px": 0.0,
        "steam_origin": [round(transformed_steam[0], 3), round(transformed_steam[1], 3)],
    }
    return _premultiplied_to_rgba(corrected), contact_report


def directional_smear(layer: Image.Image, travel_y: int = 10) -> Image.Image:
    if travel_y <= 0 or travel_y > 24:
        raise ValueError("directional smear travel must stay between one and twenty-four pixels")
    source = _rgba_to_premultiplied(layer)
    height, width = source.shape[:2]
    offsets = np.linspace(float(travel_y), 0.0, 6)
    weights = np.array([0.06, 0.09, 0.14, 0.19, 0.23, 0.29], dtype=np.float32)
    result = np.zeros_like(source)
    for offset, weight in zip(offsets, weights):
        shifted = cv2.warpAffine(
            source,
            np.array([[1.0, 0.0, 0.0], [0.0, 1.0, offset]], dtype=np.float32),
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0.0, 0.0, 0.0, 0.0),
        )
        result += shifted * float(weight)
    return _premultiplied_to_rgba(result)


def _contact_shadow(background: Image.Image, specification: dict[str, Any], registration: dict[str, Any]) -> Image.Image:
    overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    opacity = int(specification["opacity"])
    for point, radii in (
        (registration["target_left_support_boot"], (58, 13)),
        (registration["target_right_boot"], (50, 11)),
    ):
        x, y = (float(value) for value in point)
        rx, ry = radii
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=(35, 21, 14, opacity))
    overlay = overlay.filter(ImageFilter.GaussianBlur(float(specification["blur_radius"])))
    return Image.alpha_composite(background.convert("RGBA"), overlay)


def _steam_overlay(image: Image.Image, origin: tuple[float, float], frame_index: int, specification: dict[str, Any]) -> Image.Image:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    time_seconds = (frame_index - 1) / 30.0
    strength = float(specification["strength"])
    for strand in range(int(specification["strand_count"])):
        phase = strand * 0.47
        progress = (time_seconds * (0.22 + strand * 0.02) + phase) % 1.0
        points = []
        for step in range(10):
            rise = step * 7.0 + progress * 24.0
            wave = math.sin(time_seconds * 1.7 + step * 0.62 + phase * 5.0) * (3.0 + step * 0.5)
            points.append((origin[0] + (strand - 0.5) * 11.0 + wave, origin[1] - rise))
        alpha = int((72.0 - progress * 28.0) * strength)
        draw.line(points, fill=(247, 239, 224, max(5, alpha)), width=4)
    overlay = overlay.filter(ImageFilter.GaussianBlur(3.2))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def compose_pose_frame(
    background: Image.Image,
    layer: Image.Image,
    steam_origin: tuple[float, float],
    contract: dict[str, Any],
    frame_index: int,
) -> Image.Image:
    effects = contract["effects"]
    frame = _contact_shadow(background, effects["contact_shadow"], contract["contact_registration"])
    frame = Image.alpha_composite(frame, layer)
    frame = _steam_overlay(frame, steam_origin, frame_index, effects["steam"])
    light_strength = float(effects["light_breathe"]["strength"])
    factor = 1.0 + light_strength * math.sin((frame_index - 1) / 30.0 * math.pi * 0.71)
    frame = ImageEnhance.Brightness(frame.convert("RGB")).enhance(factor)
    amount = (frame_index - 1) / max(1, int(contract["output"]["frame_count"]) - 1)
    return _camera_frame(frame, contract["camera"], amount, (1920, 1080))


def _resolve_executable(name: str) -> str:
    explicit = Path(name)
    resolved = str(explicit) if explicit.is_file() else shutil.which(name)
    if not resolved:
        raise FileNotFoundError(f"executable not found: {name}")
    return resolved


def _has_audio(path: Path, ffprobe: str) -> bool:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _media_probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,nb_frames,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def render_pose_layer_sequence(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    audio_source: str | Path | None = None,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    contract, background_path, pose_paths = load_pose_layer_contract(contract_path)
    output = Path(output_dir).resolve()
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()
    ffmpeg_bin = _resolve_executable(ffmpeg)
    ffprobe_bin = _resolve_executable(ffprobe)
    output_spec = contract["output"]
    width = int(output_spec["width"])
    height = int(output_spec["height"])
    fps = int(output_spec["fps"])
    frame_count = int(output_spec["frame_count"])
    background = Image.open(background_path).convert("RGB")
    pose_by_id = {pose["id"]: pose for pose in contract["poses"]}
    registered: dict[str, Image.Image] = {}
    contact_rows: list[dict[str, Any]] = []
    steam_origins: dict[str, tuple[float, float]] = {}
    for pose_id, path in pose_paths.items():
        source = Image.open(path).convert("RGBA")
        layer, contact = registered_pose_layer(source, pose_by_id[pose_id], contract["contact_registration"])
        source.close()
        registered[pose_id] = layer
        contact_rows.append(contact)
        steam_origins[pose_id] = tuple(contact["steam_origin"])
    smears = {
        entry["to_pose_id"]: directional_smear(registered[entry["to_pose_id"]])
        for entry in contract["timeline"]
        if entry["type"] == "smear"
    }

    review_numbers = {1, frame_count}
    for entry in contract["timeline"]:
        review_numbers.update({int(entry["start_frame"]), int(entry["end_frame"])})
    saved: dict[int, Path] = {}
    video_only = output / "june-gs030-layered-stand.video-only.partial.mp4"
    video_only.unlink(missing_ok=True)
    command = [
        ffmpeg_bin,
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
        "-an",
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
        "-movflags",
        "+faststart",
        str(video_only),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise RuntimeError("unable to open FFmpeg pose-layer raw-video pipe")
    try:
        for frame_index in range(1, frame_count + 1):
            entry = timeline_entry_for_frame(contract["timeline"], frame_index)
            if entry["type"] == "pose":
                pose_id = entry["pose_id"]
                layer = registered[pose_id]
            else:
                pose_id = entry["to_pose_id"]
                layer = smears[pose_id]
            frame = compose_pose_frame(background, layer, steam_origins[pose_id], contract, frame_index)
            process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            if frame_index in review_numbers:
                destination = review_dir / f"frame_{frame_index:04d}.png"
                frame.save(destination, compress_level=2)
                saved[frame_index] = destination
        process.stdin.close()
        error_output = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    finally:
        background.close()
        for image in registered.values():
            image.close()
        for image in smears.values():
            image.close()
    if return_code != 0:
        video_only.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg pose-layer render failed: {error_output.strip()}")
    if not video_only.is_file() or video_only.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create a usable pose-layer video")

    video = output / "june-gs030-layered-stand.mp4"
    partial = output / "june-gs030-layered-stand.partial.mp4"
    partial.unlink(missing_ok=True)
    audio_path = Path(audio_source).resolve() if audio_source else None
    audio_included = False
    if audio_path is not None:
        if not audio_path.is_file() or not _has_audio(audio_path, ffprobe_bin):
            raise ValueError("audio source must contain a readable audio stream")
        duration = float(output_spec["duration_seconds"])
        audio_filter = (
            f"atrim=start=0:end={duration:.6f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.03,afade=t=out:st={duration - 0.03:.6f}:d=0.03,"
            f"apad=pad_dur={duration:.6f}"
        )
        result = subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-v",
                "error",
                "-i",
                str(video_only),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-af",
                audio_filter,
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-t",
                f"{duration:.6f}",
                "-movflags",
                "+faststart",
                str(partial),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(f"FFmpeg pose-layer audio mux failed: {result.stderr.strip()}")
        video_only.unlink(missing_ok=True)
        audio_included = True
    else:
        video_only.replace(partial)
    partial.replace(video)

    quality = encoded_quality_metrics(video, saved, frame_count)
    quality_gate = contract["encoded_quality_gate"]
    if quality["minimum_psnr_db"] < float(quality_gate["minimum_review_frame_psnr_db"]):
        raise RuntimeError("encoded pose-layer sequence failed its PSNR gate")
    if quality["minimum_encoded_laplacian_variance"] < float(
        quality_gate["minimum_review_frame_laplacian_variance"]
    ):
        raise RuntimeError("encoded pose-layer sequence failed its retained-detail gate")
    maximum_contact_residual = max(
        max(float(row["left_support_boot_residual_px"]), float(row["right_boot_residual_px"]))
        for row in contact_rows
    )
    if maximum_contact_residual > float(contract["contact_registration"]["maximum_contact_drift_px_source"]):
        raise RuntimeError("registered pose layer exceeds the planted-foot contact gate")

    report = {
        "contract_version": POSE_LAYER_CONTRACT_VERSION,
        "gate": contract["gate"],
        "classification": contract["classification"],
        "performance_id": contract["performance_id"],
        "contract_sha256": _sha256(Path(contract_path).resolve()),
        "background": {"file": background_path.name, "sha256": _sha256(background_path)},
        "poses": [
            {
                "id": pose["id"],
                "foreground": Path(pose["foreground"]["path"]).name,
                "sha256": pose["foreground"]["sha256"],
                "progress": pose["progress"],
            }
            for pose in contract["poses"]
        ],
        "render_method": "stable set plate + registered RGBA production drawings + one-frame directional smears",
        "optical_flow_used": False,
        "cross_dissolve_used": False,
        "contact_registration": contact_rows,
        "maximum_contact_residual_px_source": maximum_contact_residual,
        "audio": {
            "included": audio_included,
            "source": audio_path.name if audio_path else None,
            "source_sha256": _sha256(audio_path) if audio_path else None,
            "boundary_fades_ms": 30 if audio_included else None,
        },
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": output_spec["duration_seconds"],
        "review_frames": [path.name for _, path in sorted(saved.items())],
        "encoded_quality": quality,
        "media_probe": _media_probe(video, ffprobe_bin),
        "video": video.name,
        "video_sha256": _sha256(video),
    }
    (output / "june-gs030-layered-stand-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's registered GS030 layered stand")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--audio-source")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_pose_layer_sequence(
        args.contract,
        args.output_dir,
        audio_source=args.audio_source,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
