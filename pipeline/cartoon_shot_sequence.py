"""Cut June's identity-locked performance into a high-detail multi-shot sequence."""
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


SEQUENCE_CONTRACT_VERSION = 1
SUPPORTED_EFFECTS = {"steam", "light_breathe"}


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


def _valid_focus(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, (int, float)) and 0.0 <= float(item) <= 1.0 for item in value)
    )


def _validate_camera(camera: dict[str, Any], shot_id: str) -> None:
    if camera.get("easing") != "ease_in_out_cubic":
        raise ValueError(f"{shot_id} must use ease_in_out_cubic camera timing")
    for key in ("start_zoom", "end_zoom"):
        value = float(camera.get(key, 0.0))
        if not 1.0 <= value <= 3.0:
            raise ValueError(f"{shot_id} {key} must stay in the bounded 1x-3x range")
    for key in ("focus_start", "focus_end"):
        if not _valid_focus(camera.get(key)):
            raise ValueError(f"{shot_id} {key} must be a normalized two-value point")


def load_multishot_contract(path: str | Path) -> tuple[dict[str, Any], dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != SEQUENCE_CONTRACT_VERSION:
        raise ValueError(f"sequence contract_version must be {SEQUENCE_CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("multi-shot contract must explicitly target June Oxley")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0 or generation.get("paid_runtime_dependency") is not False:
        raise ValueError("multi-shot sequence must preserve the zero-cash runtime contract")

    output = contract.get("output") or {}
    expected_output = (1920, 1080, 30, 453)
    actual_output = (
        int(output.get("width", 0)),
        int(output.get("height", 0)),
        int(output.get("fps", 0)),
        int(output.get("frame_count", 0)),
    )
    if actual_output != expected_output or not math.isclose(float(output.get("duration_seconds", 0.0)), 15.1):
        raise ValueError("multi-shot output must be exactly 1920x1080, 30 fps, 453 frames, and 15.1 seconds")

    base = contract.get("base_performance") or {}
    expected_base = (1920, 1080, 30, 453)
    actual_base = (
        int(base.get("required_width", 0)),
        int(base.get("required_height", 0)),
        int(base.get("required_fps", 0)),
        int(base.get("required_frame_count", 0)),
    )
    if actual_base != expected_base:
        raise ValueError("base performance contract must match the exact output clock")

    quality_gate = contract.get("encoded_quality_gate") or {}
    minimum_psnr = float(quality_gate.get("minimum_review_frame_psnr_db", 0.0))
    minimum_laplacian = float(quality_gate.get("minimum_review_frame_laplacian_variance", 0.0))
    if not 30.0 <= minimum_psnr <= 60.0 or not 1.0 <= minimum_laplacian <= 1000.0:
        raise ValueError("encoded quality gate must define bounded PSNR and detail floors")

    plate_paths: dict[str, Path] = {}
    plates = contract.get("plates") or {}
    if not isinstance(plates, dict) or not plates:
        raise ValueError("multi-shot contract must define at least one production plate")
    for plate_id, specification in plates.items():
        if not isinstance(specification, dict):
            raise ValueError(f"plate {plate_id} must be an object")
        plate_path = _repo_asset(contract_path, specification, f"plate {plate_id}")
        width = int(specification.get("width", 0))
        height = int(specification.get("height", 0))
        with Image.open(plate_path) as image:
            if image.size != (width, height) or image.mode != specification.get("mode"):
                raise ValueError(f"plate {plate_id} does not match its dimension/mode contract")
        generation_spec = specification.get("image_generation") or {}
        if generation_spec.get("cash_cost") != 0 or generation_spec.get("paid_runtime_dependency") is not False:
            raise ValueError(f"plate {plate_id} must preserve zero-cash provenance")
        for index, source in enumerate(specification.get("source_provenance") or [], start=1):
            _repo_asset(contract_path, source, f"plate {plate_id} provenance source {index}")
        plate_paths[plate_id] = plate_path

    shots = contract.get("shots") or []
    if not isinstance(shots, list) or not shots:
        raise ValueError("multi-shot contract must define an ordered shot list")
    expected_start = 1
    seen_ids: set[str] = set()
    for shot in shots:
        shot_id = str(shot.get("id", ""))
        if not shot_id or shot_id in seen_ids:
            raise ValueError("shot ids must be non-empty and unique")
        seen_ids.add(shot_id)
        start = int(shot.get("start_frame", 0))
        end = int(shot.get("end_frame", 0))
        if start != expected_start or end < start:
            raise ValueError("shots must be contiguous, ordered, and non-empty")
        expected_start = end + 1
        source = shot.get("source") or {}
        source_type = source.get("type")
        if source_type not in {"performance", "plate"}:
            raise ValueError(f"{shot_id} source type must be performance or plate")
        if source_type == "plate" and source.get("plate_id") not in plate_paths:
            raise ValueError(f"{shot_id} references an unknown production plate")
        _validate_camera(shot.get("camera") or {}, shot_id)
        effects = shot.get("effects") or {}
        if not isinstance(effects, dict) or not set(effects).issubset(SUPPORTED_EFFECTS):
            raise ValueError(f"{shot_id} declares an unsupported effect")
    if expected_start != int(output["frame_count"]) + 1:
        raise ValueError("shot list must cover every output frame exactly once")
    return contract, plate_paths


def shot_for_frame(shots: list[dict[str, Any]], frame_index: int) -> dict[str, Any]:
    for shot in shots:
        if int(shot["start_frame"]) <= frame_index <= int(shot["end_frame"]):
            return shot
    raise ValueError(f"frame {frame_index} is not covered by the shot contract")


def _ease_in_out_cubic(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def camera_crop_box(
    source_size: tuple[int, int],
    output_size: tuple[int, int],
    zoom: float,
    focus: tuple[float, float],
) -> tuple[int, int, int, int]:
    source_width, source_height = source_size
    output_width, output_height = output_size
    target_ratio = output_width / output_height
    source_ratio = source_width / source_height
    if source_ratio >= target_ratio:
        base_height = source_height
        base_width = int(round(base_height * target_ratio))
    else:
        base_width = source_width
        base_height = int(round(base_width / target_ratio))
    crop_width = max(2, min(source_width, int(round(base_width / zoom))))
    crop_height = max(2, min(source_height, int(round(base_height / zoom))))
    center_x = float(focus[0]) * source_width
    center_y = float(focus[1]) * source_height
    left = int(round(center_x - crop_width / 2.0))
    top = int(round(center_y - crop_height / 2.0))
    left = max(0, min(source_width - crop_width, left))
    top = max(0, min(source_height - crop_height, top))
    return left, top, left + crop_width, top + crop_height


def _camera_frame(
    image: Image.Image,
    camera: dict[str, Any],
    amount: float,
    output_size: tuple[int, int],
) -> Image.Image:
    eased = _ease_in_out_cubic(amount)
    start_zoom = float(camera["start_zoom"])
    end_zoom = float(camera["end_zoom"])
    zoom = start_zoom + (end_zoom - start_zoom) * eased
    start_focus = camera["focus_start"]
    end_focus = camera["focus_end"]
    focus = (
        float(start_focus[0]) + (float(end_focus[0]) - float(start_focus[0])) * eased,
        float(start_focus[1]) + (float(end_focus[1]) - float(start_focus[1])) * eased,
    )
    box = camera_crop_box(image.size, output_size, zoom, focus)
    return image.crop(box).resize(output_size, Image.Resampling.LANCZOS)


def _steam_overlay(image: Image.Image, specification: dict[str, Any], time_seconds: float) -> Image.Image:
    width, height = image.size
    origin = specification.get("origin") or [0.5, 0.2]
    strength = max(0.0, min(1.0, float(specification.get("strength", 0.5))))
    origin_x = float(origin[0]) * width
    origin_y = float(origin[1]) * height
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for index, phase in enumerate((0.0, 0.37, 0.71)):
        progress = (time_seconds * (0.20 + index * 0.018) + phase) % 1.0
        base_x = origin_x + (index - 1) * 22.0
        base_y = origin_y - progress * 82.0
        points: list[tuple[float, float]] = []
        for step in range(11):
            rise = step * (8.0 + index)
            wave = math.sin(time_seconds * 1.4 + phase * 6.0 + step * 0.58) * (5.0 + step * 0.65)
            points.append((base_x + wave, base_y - rise))
        alpha = int((96.0 - progress * 40.0) * strength)
        draw.line(points, fill=(248, 239, 221, max(6, alpha)), width=6)
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=4.5))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def apply_shot_effects(
    image: Image.Image,
    effects: dict[str, Any],
    frame_in_shot: int,
    fps: int,
) -> Image.Image:
    result = image.convert("RGB")
    time_seconds = frame_in_shot / fps
    if "steam" in effects:
        result = _steam_overlay(result, effects["steam"], time_seconds)
    if "light_breathe" in effects:
        strength = max(0.0, min(0.02, float(effects["light_breathe"].get("strength", 0.0))))
        factor = 1.0 + strength * math.sin(time_seconds * math.pi * 0.72)
        result = ImageEnhance.Brightness(result).enhance(factor)
    return result


def _resolve_executable(name: str) -> str:
    explicit = Path(name)
    executable = str(explicit) if explicit.is_file() else shutil.which(name)
    if not executable:
        raise FileNotFoundError(f"executable not found: {name}")
    return executable


def _has_audio(video: Path, ffprobe: str) -> bool:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def encoded_quality_metrics(
    video: Path,
    review_frames: dict[int, Path],
    expected_frame_count: int,
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"unable to decode encoded sequence for quality measurement: {video}")
    targets = set(review_frames)
    decoded: dict[int, np.ndarray] = {}
    frame_index = 0
    while True:
        success, frame = capture.read()
        if not success:
            break
        frame_index += 1
        if frame_index in targets:
            decoded[frame_index] = frame
    capture.release()
    if frame_index != expected_frame_count or set(decoded) != targets:
        raise RuntimeError("encoded quality measurement did not decode the exact review-frame clock")
    rows: list[dict[str, Any]] = []
    for target in sorted(targets):
        source = cv2.imread(str(review_frames[target]), cv2.IMREAD_COLOR)
        if source is None:
            raise RuntimeError(f"unable to read review frame for quality measurement: {review_frames[target]}")
        encoded = decoded[target]
        rows.append(
            {
                "frame": target,
                "psnr_db": round(float(cv2.PSNR(source, encoded)), 3),
                "encoded_laplacian_variance": round(float(cv2.Laplacian(encoded, cv2.CV_64F).var()), 3),
            }
        )
    return {
        "sample_count": len(rows),
        "minimum_psnr_db": min(row["psnr_db"] for row in rows),
        "mean_psnr_db": round(sum(row["psnr_db"] for row in rows) / len(rows), 3),
        "minimum_encoded_laplacian_variance": min(row["encoded_laplacian_variance"] for row in rows),
        "frames": rows,
    }


def render_multishot_sequence(
    sequence_contract_path: str | Path,
    base_performance_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    contract, plate_paths = load_multishot_contract(sequence_contract_path)
    base_video = Path(base_performance_path).resolve()
    if not base_video.is_file():
        raise FileNotFoundError(f"base performance is missing: {base_video}")
    output_spec = contract["output"]
    width = int(output_spec["width"])
    height = int(output_spec["height"])
    fps = int(output_spec["fps"])
    frame_count = int(output_spec["frame_count"])
    output_size = (width, height)

    capture = cv2.VideoCapture(str(base_video))
    if not capture.isOpened():
        raise ValueError(f"unable to decode base performance: {base_video}")
    actual_width = int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH)))
    actual_height = int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    actual_fps = float(capture.get(cv2.CAP_PROP_FPS))
    actual_frames = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    if (actual_width, actual_height, actual_frames) != (width, height, frame_count) or not math.isclose(
        actual_fps, fps, rel_tol=0.0, abs_tol=0.01
    ):
        capture.release()
        raise ValueError("base performance does not match the exact 1920x1080/30/453 sequence clock")

    ffmpeg_executable = _resolve_executable(ffmpeg)
    ffprobe_executable = _resolve_executable(ffprobe)
    has_audio = _has_audio(base_video, ffprobe_executable)
    plates = {plate_id: Image.open(path).convert("RGB") for plate_id, path in plate_paths.items()}
    output = Path(output_dir).resolve()
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()
    video = output / "june-golden-scene-multishot.mp4"
    partial_video = output / "june-golden-scene-multishot.partial.mp4"
    partial_video.unlink(missing_ok=True)

    command = [
        ffmpeg_executable,
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
    if has_audio:
        command.extend(["-i", str(base_video), "-map", "0:v:0", "-map", "1:a:0"])
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
    if has_audio:
        command.extend(["-c:a", "copy"])
    else:
        command.append("-an")
    command.extend(["-movflags", "+faststart", str(partial_video)])
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        capture.release()
        raise RuntimeError("unable to open FFmpeg multi-shot raw-video pipe")

    review_numbers: set[int] = set()
    for shot in contract["shots"]:
        start = int(shot["start_frame"])
        end = int(shot["end_frame"])
        review_numbers.update({start, (start + end) // 2, end})
    saved: dict[int, Path] = {}
    current_shot: dict[str, Any] | None = None
    try:
        for frame_index in range(1, frame_count + 1):
            success, bgr_frame = capture.read()
            if not success:
                raise RuntimeError(f"base performance decode stopped at frame {frame_index}")
            if current_shot is None or frame_index > int(current_shot["end_frame"]):
                current_shot = shot_for_frame(contract["shots"], frame_index)
            source = current_shot["source"]
            if source["type"] == "performance":
                source_image = Image.fromarray(cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB), mode="RGB")
            else:
                source_image = plates[source["plate_id"]]
            start = int(current_shot["start_frame"])
            end = int(current_shot["end_frame"])
            amount = 0.0 if start == end else (frame_index - start) / (end - start)
            frame = _camera_frame(source_image, current_shot["camera"], amount, output_size)
            frame = apply_shot_effects(frame, current_shot.get("effects") or {}, frame_index - start, fps)
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
        capture.release()
        for plate in plates.values():
            plate.close()
    if return_code != 0:
        partial_video.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg multi-shot render failed: {error_output.strip()}")
    if not partial_video.is_file() or partial_video.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create a usable multi-shot sequence")
    partial_video.replace(video)

    quality_metrics = encoded_quality_metrics(video, saved, frame_count)
    quality_gate = contract["encoded_quality_gate"]
    if quality_metrics["minimum_psnr_db"] < float(quality_gate["minimum_review_frame_psnr_db"]):
        raise RuntimeError("encoded sequence failed the minimum review-frame PSNR gate")
    if quality_metrics["minimum_encoded_laplacian_variance"] < float(
        quality_gate["minimum_review_frame_laplacian_variance"]
    ):
        raise RuntimeError("encoded sequence failed the minimum retained-detail gate")

    report = {
        "contract_version": SEQUENCE_CONTRACT_VERSION,
        "gate": "identity_locked_high_detail_multishot_sequence",
        "sequence_id": contract["sequence_id"],
        "sequence_contract_sha256": _sha256(Path(sequence_contract_path).resolve()),
        "base_performance": {
            "file": base_video.name,
            "sha256": _sha256(base_video),
            "audio_preserved": has_audio,
        },
        "plates": {
            plate_id: {"file": path.name, "sha256": contract["plates"][plate_id]["sha256"]}
            for plate_id, path in plate_paths.items()
        },
        "shots": [
            {
                "id": shot["id"],
                "start_frame": shot["start_frame"],
                "end_frame": shot["end_frame"],
                "frame_count": int(shot["end_frame"]) - int(shot["start_frame"]) + 1,
                "source": shot["source"],
            }
            for shot in contract["shots"]
        ],
        "cut_frames": [int(shot["start_frame"]) for shot in contract["shots"][1:]],
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": output_spec["duration_seconds"],
        "width": width,
        "height": height,
        "review_frames": [path.name for _, path in sorted(saved.items())],
        "encoded_quality": quality_metrics,
        "first_frame_sha256": _sha256(saved[1]),
        "last_frame_sha256": _sha256(saved[frame_count]),
        "video": video.name,
        "video_sha256": _sha256(video),
    }
    (output / "june-golden-scene-multishot-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's identity-locked high-detail multi-shot sequence")
    parser.add_argument("sequence_contract")
    parser.add_argument("base_performance")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--output-dir", default="build/edit/june-golden-scene-multishot")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_multishot_sequence(
        args.sequence_contract,
        args.base_performance,
        args.output_dir,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
