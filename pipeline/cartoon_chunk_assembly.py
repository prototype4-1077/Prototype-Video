"""Validate and assemble parallel Blender NPR frame chunks."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


FRAME_PATTERN = re.compile(r"frame_(\d{4})\.png$")


def validate_frame_sequence(root: str | Path, *, frame_count: int = 453) -> dict[int, Path]:
    if int(frame_count) <= 0:
        raise ValueError("frame_count must be positive")
    frame_root = Path(root).resolve()
    frames: dict[int, Path] = {}
    for path in frame_root.rglob("frame_*.png"):
        match = FRAME_PATTERN.fullmatch(path.name)
        if not match:
            continue
        number = int(match.group(1))
        if number in frames:
            raise ValueError(f"duplicate promoted frame {number:04d}")
        if path.stat().st_size <= 0:
            raise ValueError(f"promoted frame {number:04d} is empty")
        frames[number] = path
    expected = set(range(1, int(frame_count) + 1))
    actual = set(frames)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(f"promoted frame sequence mismatch; missing={missing[:8]} extra={extra[:8]}")
    return frames


def validate_chunk_reports(root: str | Path, *, frame_count: int = 453) -> dict:
    reports = sorted(Path(root).resolve().rglob("chunk-*-report.json"))
    if not reports:
        raise ValueError("chunk promotion reports are required")
    ranges = []
    look_hashes = set()
    for path in reports:
        payload = json.loads(path.read_text(encoding="utf-8"))
        performance = payload.get("performance") or {}
        window = performance.get("chunk_window") or {}
        if performance.get("render_mode") != "chunk":
            raise ValueError(f"{path.name} is not a chunk promotion report")
        start = int(window.get("frame_start", 0))
        end = int(window.get("frame_end", 0))
        rendered = int(performance.get("rendered_frames", 0))
        if start < 1 or end < start or rendered != end - start + 1:
            raise ValueError(f"{path.name} has an invalid chunk window")
        ranges.append((start, end, path.name))
        look_hash = str((payload.get("look_profile") or {}).get("sha256") or "")
        if not look_hash:
            raise ValueError(f"{path.name} is missing its look-profile digest")
        look_hashes.add(look_hash)
    ranges.sort()
    cursor = 1
    for start, end, name in ranges:
        if start != cursor:
            raise ValueError(f"chunk coverage breaks before {name}: expected {cursor}, got {start}")
        cursor = end + 1
    if cursor != int(frame_count) + 1:
        raise ValueError(f"chunk coverage ends at {cursor - 1}, expected {frame_count}")
    if len(look_hashes) != 1:
        raise ValueError("chunk look-profile digests do not match")
    return {
        "chunk_count": len(ranges),
        "ranges": [
            {"frame_start": start, "frame_end": end, "report": name}
            for start, end, name in ranges
        ],
        "look_profile_sha256": next(iter(look_hashes)),
    }


def assemble_chunked_video(
    frames_root: str | Path,
    output_path: str | Path,
    *,
    ffmpeg: str = "ffmpeg",
    fps: int = 30,
    frame_count: int = 453,
    report_path: str | Path | None = None,
) -> dict:
    if int(fps) <= 0:
        raise ValueError("fps must be positive")
    frames = validate_frame_sequence(frames_root, frame_count=frame_count)
    chunk_evidence = validate_chunk_reports(frames_root, frame_count=frame_count)
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="june-npr-assemble-", dir=output.parent) as temp_dir:
        stage = Path(temp_dir)
        for number, source in sorted(frames.items()):
            target = stage / f"frame_{number:04d}.png"
            try:
                os.link(source, target)
            except OSError:
                shutil.copyfile(source, target)
        command = [
            ffmpeg,
            "-y",
            "-framerate",
            str(int(fps)),
            "-start_number",
            "1",
            "-i",
            str(stage / "frame_%04d.png"),
            "-frames:v",
            str(int(frame_count)),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
        subprocess.run(command, check=True)
    report = {
        "contract_version": 1,
        "gate": "chunked_npr_promotion",
        "fps": int(fps),
        "frame_count": int(frame_count),
        "duration_seconds": int(frame_count) / int(fps),
        "output": output.name,
        **chunk_evidence,
    }
    if report_path:
        destination = Path(report_path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble verified June NPR Blender chunks")
    parser.add_argument("frames_root")
    parser.add_argument("output")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--frame-count", type=int, default=453)
    parser.add_argument("--report")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = assemble_chunked_video(
        args.frames_root,
        args.output,
        ffmpeg=args.ffmpeg,
        fps=args.fps,
        frame_count=args.frame_count,
        report_path=args.report,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
