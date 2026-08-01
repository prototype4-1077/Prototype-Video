"""Deterministic Real-ESRGAN finishing pass for an exact-frame cartoon render."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Sequence

from PIL import Image


FRAME_PATTERN = re.compile(r"frame_(\d{4})\.png\Z")
DEFAULT_MODEL = "realesr-animevideov3"


def _run(
    command: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: str | Path, label: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} not found: {resolved}")
    return resolved


def _probe(ffprobe: str | Path, video: Path) -> dict[str, Any]:
    result = _run([
        ffprobe, "-v", "error", "-show_streams", "-show_format",
        "-count_frames", "-of", "json", video,
    ])
    return json.loads(result.stdout)


def validate_video_contract(
    probe: dict[str, Any],
    *,
    frame_count: int,
    fps: int,
    width: int | None = None,
    height: int | None = None,
    require_audio: bool = False,
) -> dict[str, Any]:
    streams = probe.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if not video:
        raise ValueError("finished cartoon is missing video")
    if require_audio and not audio:
        raise ValueError("finished cartoon is missing audio")
    actual_frames = int(video.get("nb_read_frames") or video.get("nb_frames") or 0)
    if actual_frames != int(frame_count):
        raise ValueError(f"finished frame count {actual_frames} != {frame_count}")
    if str(video.get("avg_frame_rate")) not in {f"{fps}/1", f"{fps * 1000}/1000"}:
        raise ValueError(f"finished cartoon is not {fps} fps")
    actual_width = int(video.get("width") or 0)
    actual_height = int(video.get("height") or 0)
    if width is not None and actual_width != int(width):
        raise ValueError(f"finished width {actual_width} != {width}")
    if height is not None and actual_height != int(height):
        raise ValueError(f"finished height {actual_height} != {height}")
    return {
        "width": actual_width,
        "height": actual_height,
        "fps": int(fps),
        "frame_count": actual_frames,
        "duration_seconds": actual_frames / int(fps),
        "audio": bool(audio),
        "audio_sample_rate": int((audio or {}).get("sample_rate") or 0),
    }


def validate_numbered_frames(
    root: str | Path,
    *,
    frame_count: int,
    width: int,
    height: int,
) -> list[Path]:
    directory = Path(root).resolve()
    frames: dict[int, Path] = {}
    for path in directory.glob("frame_*.png"):
        match = FRAME_PATTERN.fullmatch(path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number in frames:
            raise ValueError(f"duplicate finish frame {number:04d}")
        if path.stat().st_size <= 0:
            raise ValueError(f"finish frame {number:04d} is empty")
        frames[number] = path
    expected = set(range(1, int(frame_count) + 1))
    if set(frames) != expected:
        missing = sorted(expected - set(frames))
        extra = sorted(set(frames) - expected)
        raise ValueError(f"finish frame sequence mismatch; missing={missing[:8]} extra={extra[:8]}")
    ordered = [frames[number] for number in sorted(frames)]
    for path in ordered:
        with Image.open(path) as image:
            if image.size != (int(width), int(height)):
                raise ValueError(f"finish frame {path.name} dimensions {image.size} != {(width, height)}")
    return ordered


def _subtitle_filter(captions: Path) -> str:
    return (
        f"subtitles={captions.name}:force_style='FontName=Arial,FontSize=28,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=3,"
        "BackColour=&H70000000,Outline=1,Shadow=0,MarginV=54,Alignment=2'"
    )


def finish_cartoon(
    input_video: str | Path,
    output_video: str | Path,
    *,
    upscaler: str | Path,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
    model: str = DEFAULT_MODEL,
    scale: int = 2,
    tile_size: int = 128,
    gpu_id: int = 0,
    frame_count: int = 453,
    fps: int = 30,
    audio_source: str | Path | None = None,
    captions: str | Path | None = None,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    if int(scale) not in {2, 3, 4}:
        raise ValueError("Real-ESRGAN scale must be 2, 3, or 4")
    if int(tile_size) != 0 and int(tile_size) < 32:
        raise ValueError("Real-ESRGAN tile size must be zero or at least 32")
    if int(frame_count) <= 0 or int(fps) <= 0:
        raise ValueError("frame_count and fps must be positive")
    source = _require_file(input_video, "input cartoon")
    executable = _require_file(upscaler, "Real-ESRGAN executable")
    destination = Path(output_video).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    audio = _require_file(audio_source, "audio source") if audio_source else None
    subtitle = _require_file(captions, "caption file") if captions else None
    if bool(audio) != bool(subtitle):
        raise ValueError("audio_source and captions must be supplied together")

    input_contract = validate_video_contract(
        _probe(ffprobe, source),
        frame_count=frame_count,
        fps=fps,
    )
    output_width = int(input_contract["width"]) * int(scale)
    output_height = int(input_contract["height"]) * int(scale)
    with tempfile.TemporaryDirectory(prefix="june-ai-finish-", dir=destination.parent) as temp:
        working = Path(temp)
        extracted = working / "input"
        enhanced = working / "enhanced"
        extracted.mkdir()
        enhanced.mkdir()
        _run([
            ffmpeg, "-y", "-v", "error", "-i", source, "-vsync", "0",
            extracted / "frame_%04d.png",
        ])
        validate_numbered_frames(
            extracted,
            frame_count=frame_count,
            width=int(input_contract["width"]),
            height=int(input_contract["height"]),
        )
        _run([
            executable,
            "-i", extracted,
            "-o", enhanced,
            "-s", str(int(scale)),
            "-t", str(int(tile_size)),
            "-n", model,
            "-g", str(int(gpu_id)),
            "-j", "1:2:2",
            "-f", "png",
        ], cwd=executable.parent, capture_output=False)
        validate_numbered_frames(
            enhanced,
            frame_count=frame_count,
            width=output_width,
            height=output_height,
        )
        picture = working / "picture.mp4"
        _run([
            ffmpeg, "-y", "-v", "error",
            "-framerate", str(int(fps)), "-start_number", "1",
            "-i", enhanced / "frame_%04d.png",
            "-frames:v", str(int(frame_count)),
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", picture,
        ])
        if audio and subtitle:
            _run([
                ffmpeg, "-y", "-v", "error", "-i", picture, "-i", audio,
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", _subtitle_filter(subtitle),
                "-c:v", "libx264", "-preset", "fast", "-crf", "15",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-frames:v", str(int(frame_count)),
                "-t", f"{int(frame_count) / int(fps):.6f}",
                "-movflags", "+faststart", destination,
            ], cwd=subtitle.parent)
        else:
            shutil.move(str(picture), str(destination))

    null_device = "NUL" if os.name == "nt" else "/dev/null"
    _run([ffmpeg, "-v", "error", "-i", destination, "-f", "null", null_device])
    output_contract = validate_video_contract(
        _probe(ffprobe, destination),
        frame_count=frame_count,
        fps=fps,
        width=output_width,
        height=output_height,
        require_audio=bool(audio),
    )
    if audio and output_contract["audio_sample_rate"] != 48000:
        raise ValueError("finished cartoon audio must be 48 kHz")
    report = {
        "contract_version": 1,
        "stage": "ai_cartoon_finish",
        "model": model,
        "scale": int(scale),
        "tile_size": int(tile_size),
        "input": {"path": source.name, "sha256": _sha256(source), **input_contract},
        "output": {"path": destination.name, "sha256": _sha256(destination), **output_contract},
        "upscaler": {"path": executable.name, "sha256": _sha256(executable)},
        "audio_source": {"path": audio.name, "sha256": _sha256(audio)} if audio else None,
        "captions": {"path": subtitle.name, "sha256": _sha256(subtitle)} if subtitle else None,
    }
    if report_path:
        report_destination = Path(report_path).resolve()
        report_destination.parent.mkdir(parents=True, exist_ok=True)
        report_destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply an exact-frame AI finish to a cartoon")
    parser.add_argument("input_video")
    parser.add_argument("output_video")
    parser.add_argument("--upscaler", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--tile-size", type=int, default=128)
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--frame-count", type=int, default=453)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--audio-source")
    parser.add_argument("--captions")
    parser.add_argument("--report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = finish_cartoon(
        args.input_video,
        args.output_video,
        upscaler=args.upscaler,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
        model=args.model,
        scale=args.scale,
        tile_size=args.tile_size,
        gpu_id=args.gpu_id,
        frame_count=args.frame_count,
        fps=args.fps,
        audio_source=args.audio_source,
        captions=args.captions,
        report_path=args.report,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
