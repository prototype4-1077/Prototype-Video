"""Audit an exact-frame cartoon master and build human-review matrices."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Sequence

import numpy as np
from PIL import Image, ImageDraw

from pipeline.cartoon_visual_metrics import (
    _decoded_frames,
    _global_ssim,
    _luma,
)


DEFAULT_REVIEW_FRAMES = (1, 93, 171, 172, 260, 339, 340, 398, 453)
DEFAULT_HOLD_FRAMES = (430, 434, 438, 442, 446, 450, 453)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: Sequence[str | Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        check=True,
        capture_output=True,
        text=True,
    )


def probe_video(ffprobe: str | Path, video: Path) -> dict[str, Any]:
    result = _run([
        ffprobe,
        "-v",
        "error",
        "-count_frames",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        video,
    ])
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    picture = next((item for item in streams if item.get("codec_type") == "video"), None)
    sound = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if not picture:
        raise ValueError("cartoon delivery has no video stream")
    rate_num, rate_den = (
        int(part) for part in str(picture.get("r_frame_rate") or "0/1").split("/")
    )
    return {
        "codec": str(picture.get("codec_name") or ""),
        "width": int(picture.get("width") or 0),
        "height": int(picture.get("height") or 0),
        "pixel_format": str(picture.get("pix_fmt") or ""),
        "fps": rate_num / rate_den,
        "frame_count": int(picture.get("nb_read_frames") or picture.get("nb_frames") or 0),
        "duration_seconds": float((payload.get("format") or {}).get("duration") or 0.0),
        "bytes": int((payload.get("format") or {}).get("size") or video.stat().st_size),
        "audio": bool(sound),
        "audio_codec": str((sound or {}).get("codec_name") or ""),
        "audio_sample_rate": int((sound or {}).get("sample_rate") or 0),
        "audio_channels": int((sound or {}).get("channels") or 0),
    }


def validate_contract(
    contract: dict[str, Any],
    *,
    width: int,
    height: int,
    fps: int,
    frame_count: int,
    require_audio: bool,
) -> None:
    expected = {
        "width": int(width),
        "height": int(height),
        "fps": float(fps),
        "frame_count": int(frame_count),
    }
    actual = {key: contract[key] for key in expected}
    if actual != expected:
        raise ValueError(f"cartoon delivery contract mismatch: {actual} != {expected}")
    if abs(float(contract["duration_seconds"]) - frame_count / fps) > 1.0 / fps:
        raise ValueError("cartoon delivery duration is outside one frame")
    if require_audio:
        if not contract["audio"]:
            raise ValueError("cartoon delivery is missing required audio")
        if contract["audio_sample_rate"] != 48000 or contract["audio_channels"] != 2:
            raise ValueError("cartoon delivery audio must be 48 kHz stereo")


def _labeled_sheet(
    frames: dict[int, np.ndarray],
    order: Sequence[int],
    output: Path,
    *,
    columns: int,
    tile_width: int,
    tile_height: int,
) -> None:
    rows = (len(order) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), "black")
    for index, frame_number in enumerate(order):
        frame = Image.fromarray(frames[frame_number], "RGB")
        frame.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (tile_width, tile_height), "black")
        top = (tile_height - frame.height) // 2
        tile.paste(frame, ((tile_width - frame.width) // 2, top))
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, 0, 132, 27), fill=(0, 0, 0))
        draw.text((8, 7), f"FRAME {frame_number:03d}", fill=(255, 255, 255))
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        sheet.paste(tile, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def hold_metrics(frames: Sequence[np.ndarray]) -> dict[str, float]:
    if len(frames) < 2:
        raise ValueError("final-hold audit needs at least two frames")
    height, width = frames[0].shape[:2]
    upper_face = [
        _luma(frame[: round(height * 0.62), round(width * 0.20) : round(width * 0.80)])
        for frame in frames
    ]
    left_wall = [
        _luma(frame[: round(height * 0.82), : round(width * 0.18)])
        for frame in frames
    ]
    upper_differences = [
        float(np.abs(right - left).mean())
        for left, right in zip(upper_face, upper_face[1:])
    ]
    wall_differences = [
        float(np.abs(right - left).mean())
        for left, right in zip(left_wall, left_wall[1:])
    ]
    return {
        "upper_face_first_last_ssim": _global_ssim(upper_face[0], upper_face[-1]),
        "upper_face_adjacent_luma_mean": float(np.mean(upper_differences)),
        "upper_face_adjacent_luma_max": float(np.max(upper_differences)),
        "left_wall_adjacent_luma_mean": float(np.mean(wall_differences)),
        "left_wall_adjacent_luma_max": float(np.max(wall_differences)),
    }


def audit_cartoon(
    video: Path,
    output_dir: Path,
    *,
    ffmpeg: str | Path,
    ffprobe: str | Path,
    width: int,
    height: int,
    fps: int,
    frame_count: int,
    require_audio: bool,
) -> dict[str, Any]:
    contract = probe_video(ffprobe, video)
    validate_contract(
        contract,
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        require_audio=require_audio,
    )
    wanted = set(DEFAULT_REVIEW_FRAMES) | set(DEFAULT_HOLD_FRAMES) | set(range(430, 454))
    selected: dict[int, np.ndarray] = {}
    for index, frame in enumerate(
        _decoded_frames(str(ffmpeg), video, width, height, frame_count), start=1
    ):
        if index in wanted:
            selected[index] = frame.copy()
    missing = sorted(wanted - set(selected))
    if missing:
        raise ValueError(f"audit decode missed frames: {missing}")

    matrix = output_dir / "june-cartoon-delivery-nine-pose-matrix.png"
    hold_strip = output_dir / "june-cartoon-delivery-final-hold-strip.png"
    _labeled_sheet(
        selected,
        DEFAULT_REVIEW_FRAMES,
        matrix,
        columns=3,
        tile_width=640,
        tile_height=360,
    )
    _labeled_sheet(
        selected,
        DEFAULT_HOLD_FRAMES,
        hold_strip,
        columns=4,
        tile_width=480,
        tile_height=270,
    )
    report = {
        "contract_version": 1,
        "stage": "cartoon_delivery_audit",
        "input": {"path": video.name, "sha256": _sha256(video), **contract},
        "full_decode": {"passed": True, "decoded_frames": frame_count},
        "review_frames": list(DEFAULT_REVIEW_FRAMES),
        "matrix": {"path": matrix.name, "sha256": _sha256(matrix)},
        "final_hold": {
            "frame_start": 430,
            "frame_end": 453,
            "sampled_frames": list(DEFAULT_HOLD_FRAMES),
            "strip": {"path": hold_strip.name, "sha256": _sha256(hold_strip)},
            "metrics": hold_metrics([selected[number] for number in range(430, 454)]),
        },
    }
    report_path = output_dir / "june-cartoon-delivery-audit.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--frame-count", type=int, default=453)
    parser.add_argument("--require-audio", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    video = args.video.resolve()
    if not video.is_file():
        raise FileNotFoundError(f"cartoon video not found: {video}")
    report = audit_cartoon(
        video,
        args.output_dir.resolve(),
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
        width=args.width,
        height=args.height,
        fps=args.fps,
        frame_count=args.frame_count,
        require_audio=args.require_audio,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
