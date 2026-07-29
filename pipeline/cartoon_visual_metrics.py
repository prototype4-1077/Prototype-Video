"""Measure temporal stability and selective-ink readability in cartoon renders.

The tool intentionally depends only on NumPy and FFmpeg so it can run in the
repository's free/local production environment and in lightweight CI workers.
It compares every candidate against one baseline using fixed normalized regions
of interest.  The JSON result is suitable for promotion gates and reward logs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable

import numpy as np


REGIONS: dict[str, tuple[float, float, float, float]] = {
    "full": (0.0, 0.0, 1.0, 1.0),
    # The close-up temporal gate keeps June in the middle three fifths.
    "face_and_torso": (0.20, 0.0, 0.80, 1.0),
    # These deliberately avoid the character and practical ceiling light.
    "left_wall": (0.0, 0.20, 0.16, 0.78),
    "right_wall": (0.84, 0.20, 1.0, 0.78),
    "upper_wall": (0.30, 0.04, 0.70, 0.20),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: Iterable[str | Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(item) for item in command],
        check=True,
        capture_output=True,
        text=True,
    )


def _probe(ffprobe: str, video: Path) -> tuple[int, int, int, float]:
    result = _run([
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,nb_frames,r_frame_rate",
        "-of",
        "json",
        video,
    ])
    stream = json.loads(result.stdout)["streams"][0]
    rate_num, rate_den = (int(part) for part in stream["r_frame_rate"].split("/"))
    return (
        int(stream["width"]),
        int(stream["height"]),
        int(stream["nb_frames"]),
        rate_num / rate_den,
    )


def _decode(ffmpeg: str, video: Path, width: int, height: int) -> np.ndarray:
    process = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    frame_bytes = width * height * 3
    if len(process.stdout) % frame_bytes:
        raise ValueError(f"decoded byte count is invalid for {video}")
    return np.frombuffer(process.stdout, dtype=np.uint8).reshape(
        (-1, height, width, 3)
    )


def _luma(frames: np.ndarray) -> np.ndarray:
    rgb = frames.astype(np.float32)
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def _crop(frames: np.ndarray, region: tuple[float, float, float, float]) -> np.ndarray:
    height, width = frames.shape[1:3]
    left, top, right, bottom = region
    return frames[
        :,
        round(top * height) : round(bottom * height),
        round(left * width) : round(right * width),
    ]


def _adjacent_luma_difference(luma: np.ndarray) -> float:
    if len(luma) < 2:
        return 0.0
    return float(np.abs(np.diff(luma, axis=0)).mean())


def _edge_density(luma: np.ndarray) -> float:
    horizontal = np.abs(np.diff(luma, axis=2))
    vertical = np.abs(np.diff(luma, axis=1))
    return float((horizontal.mean() + vertical.mean()) / 2.0)


def _global_ssim(left: np.ndarray, right: np.ndarray) -> float:
    """Compute global luminance SSIM without a SciPy dependency."""
    left = left.astype(np.float64)
    right = right.astype(np.float64)
    mean_left = left.mean()
    mean_right = right.mean()
    var_left = left.var()
    var_right = right.var()
    covariance = ((left - mean_left) * (right - mean_right)).mean()
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    return float(
        ((2 * mean_left * mean_right + c1) * (2 * covariance + c2))
        / ((mean_left**2 + mean_right**2 + c1) * (var_left + var_right + c2))
    )


def _metrics(frames: np.ndarray) -> dict[str, dict[str, float]]:
    luma = _luma(frames)
    return {
        name: {
            "adjacent_luma_difference": _adjacent_luma_difference(_crop(luma, bounds)),
            "edge_density": _edge_density(_crop(luma[:1], bounds)),
        }
        for name, bounds in REGIONS.items()
    }


def evaluate(
    baseline: Path,
    candidates: list[tuple[str, Path]],
    *,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    width, height, frame_count, fps = _probe(ffprobe, baseline)
    baseline_frames = _decode(ffmpeg, baseline, width, height)
    if len(baseline_frames) != frame_count:
        raise ValueError("baseline decoded frame count does not match its metadata")

    result: dict[str, Any] = {
        "contract_version": 1,
        "regions": {name: list(bounds) for name, bounds in REGIONS.items()},
        "video_contract": {
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
        },
        "renders": {},
    }
    renders: dict[str, Any] = result["renders"]
    renders["baseline"] = {
        "path": str(baseline),
        "sha256": _sha256(baseline),
        "metrics": _metrics(baseline_frames),
    }

    baseline_luma = _luma(baseline_frames)
    for label, path in candidates:
        candidate_contract = _probe(ffprobe, path)
        if candidate_contract != (width, height, frame_count, fps):
            raise ValueError(
                f"{label} contract {candidate_contract!r} does not match baseline "
                f"{(width, height, frame_count, fps)!r}"
            )
        frames = _decode(ffmpeg, path, width, height)
        luma = _luma(frames)
        renders[label] = {
            "path": str(path),
            "sha256": _sha256(path),
            "first_frame_luma_ssim_vs_baseline": _global_ssim(
                baseline_luma[:1], luma[:1]
            ),
            "metrics": _metrics(frames),
        }
    return result


def _candidate(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("candidate must be LABEL=VIDEO")
    label, raw_path = value.split("=", 1)
    if not label:
        raise argparse.ArgumentTypeError("candidate label cannot be empty")
    path = Path(raw_path).resolve()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"candidate video not found: {path}")
    return label, path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, action="append", type=_candidate)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    args = parser.parse_args()

    baseline = args.baseline.resolve()
    if not baseline.is_file():
        parser.error(f"baseline video not found: {baseline}")
    report = evaluate(
        baseline,
        args.candidate,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
