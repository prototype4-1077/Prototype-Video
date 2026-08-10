"""Assemble June's exact 1,164-frame Golden Scene picture master."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import cv2
import numpy as np
from PIL import Image

from pipeline.cartoon_shot_sequence import (
    SUPPORTED_EFFECTS,
    _camera_frame,
    _repo_asset,
    _resolve_executable,
    _validate_camera,
    apply_shot_effects,
    encoded_quality_metrics,
)


CONTRACT_VERSION = 1
SHOT_CLOCK = {
    "GS010": (1, 129, 4.3),
    "GS020": (130, 225, 3.2),
    "GS030": (226, 396, 5.7),
    "GS040": (397, 564, 5.6),
    "GS050": (565, 678, 3.8),
    "GS060": (679, 936, 8.6),
    "GS070": (937, 1164, 7.6),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_master_contract(path: str | Path) -> tuple[dict[str, Any], dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != CONTRACT_VERSION:
        raise ValueError(f"master contract_version must be {CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("Golden Scene master must explicitly target June Oxley")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0 or generation.get("paid_runtime_dependency") is not False:
        raise ValueError("Golden Scene master must preserve the zero-cash runtime contract")
    output = contract.get("output") or {}
    if (
        int(output.get("width", 0)),
        int(output.get("height", 0)),
        int(output.get("fps", 0)),
        int(output.get("frame_count", 0)),
        float(output.get("duration_seconds", 0.0)),
    ) != (1920, 1080, 30, 1164, 38.8):
        raise ValueError("Golden Scene master must be exactly 1920x1080/30/1164/38.8")
    quality = contract.get("encoded_quality_gate") or {}
    if not 30.0 <= float(quality.get("minimum_review_frame_psnr_db", 0.0)) <= 60.0:
        raise ValueError("master PSNR gate must be between 30 and 60 dB")
    if not 1.0 <= float(quality.get("minimum_encoded_laplacian_variance", 0.0)) <= 1000.0:
        raise ValueError("master encoded-detail gate is invalid")

    plate_paths: dict[str, Path] = {}
    for plate_id, specification in (contract.get("plates") or {}).items():
        plate_path = _repo_asset(contract_path, specification, f"master plate {plate_id}")
        with Image.open(plate_path) as image:
            expected = (int(specification.get("width", 0)), int(specification.get("height", 0)))
            if image.size != expected or image.mode != specification.get("mode"):
                raise ValueError(f"master plate {plate_id} does not match its image contract")
        plate_paths[plate_id] = plate_path
    if len(plate_paths) != 7:
        raise ValueError("Golden Scene master must pin all seven authored plate sources")

    rendered = contract.get("rendered_sources") or {}
    if set(rendered) != {"GS030", "GS060", "GS070"}:
        raise ValueError("master rendered sources must be GS030, GS060, and GS070")
    for source_id, expected_frames in (("GS030", 171), ("GS060", 258), ("GS070", 228)):
        source = rendered[source_id]
        if int(source.get("frame_count", 0)) != expected_frames:
            raise ValueError(f"rendered source {source_id} has the wrong frame clock")
        if not math.isclose(float(source.get("duration_seconds", 0.0)), expected_frames / 30.0):
            raise ValueError(f"rendered source {source_id} has the wrong duration")

    shots = contract.get("shots") or []
    if [shot.get("id") for shot in shots] != list(SHOT_CLOCK):
        raise ValueError("master shots must appear once in GS010-GS070 order")
    next_frame = 1
    for shot in shots:
        shot_id = str(shot["id"])
        expected_start, expected_end, expected_duration = SHOT_CLOCK[shot_id]
        if (
            int(shot.get("start_frame", 0)),
            int(shot.get("end_frame", 0)),
            float(shot.get("duration_seconds", 0.0)),
        ) != (expected_start, expected_end, expected_duration):
            raise ValueError(f"master shot {shot_id} does not match the locked Golden Scene clock")
        if expected_start != next_frame:
            raise ValueError("master shots must cover every frame contiguously")
        next_frame = expected_end + 1
        source = shot.get("source") or {}
        source_type = source.get("type")
        if source_type == "rendered_shot":
            if source.get("source_id") != shot_id or shot.get("segments"):
                raise ValueError(f"rendered master shot {shot_id} must map one-to-one without plate segments")
            continue
        if source_type != "plate_sequence":
            raise ValueError(f"master shot {shot_id} has an unsupported source type")
        segments = shot.get("segments") or []
        cursor = expected_start
        for segment in segments:
            start = int(segment.get("start_frame", 0))
            end = int(segment.get("end_frame", 0))
            if start != cursor or end < start or end > expected_end:
                raise ValueError(f"plate segments for {shot_id} must be contiguous and inside the shot")
            cursor = end + 1
            if segment.get("plate_id") not in plate_paths:
                raise ValueError(f"plate segment for {shot_id} references an unknown plate")
            _validate_camera(segment.get("camera") or {}, f"{shot_id} segment {start}")
            effects = segment.get("effects") or {}
            if not isinstance(effects, dict) or not set(effects).issubset(SUPPORTED_EFFECTS):
                raise ValueError(f"plate segment for {shot_id} declares an unsupported effect")
        if cursor != expected_end + 1:
            raise ValueError(f"plate segments for {shot_id} must cover the entire shot")
    if next_frame != 1165:
        raise ValueError("master shot map must end on frame 1164")
    if int(shots[4].get("minimum_post_dialogue_hold_frames", 0)) < 24:
        raise ValueError("GS050 must preserve at least 24 post-dialogue hold frames")
    return contract, plate_paths


def shot_for_frame(shots: list[dict[str, Any]], frame_index: int) -> dict[str, Any]:
    for shot in shots:
        if int(shot["start_frame"]) <= frame_index <= int(shot["end_frame"]):
            return shot
    raise ValueError(f"master frame {frame_index} is not covered")


def segment_for_frame(segments: list[dict[str, Any]], frame_index: int) -> dict[str, Any]:
    for segment in segments:
        if int(segment["start_frame"]) <= frame_index <= int(segment["end_frame"]):
            return segment
    raise ValueError(f"master plate frame {frame_index} is not covered")


def load_rendered_source(
    source_id: str,
    video_path: str | Path,
    report_path: str | Path,
    specification: dict[str, Any],
) -> tuple[cv2.VideoCapture, dict[str, Any], Path]:
    video = Path(video_path).resolve()
    report_file = Path(report_path).resolve()
    if not video.is_file() or not report_file.is_file():
        raise FileNotFoundError(f"rendered source {source_id} video/report is missing")
    report = json.loads(report_file.read_text(encoding="utf-8"))
    if report.get("gate") != specification.get("expected_gate"):
        raise ValueError(f"rendered source {source_id} has the wrong production gate")
    expected_frames = int(specification["frame_count"])
    if (
        int(report.get("frame_count", 0)),
        int(report.get("width", 0)),
        int(report.get("height", 0)),
        int(report.get("fps", 0)),
    ) != (expected_frames, 1920, 1080, 30):
        raise ValueError(f"rendered source {source_id} report has the wrong video clock")
    if not math.isclose(float(report.get("duration_seconds", 0.0)), float(specification["duration_seconds"])):
        raise ValueError(f"rendered source {source_id} report has the wrong duration")
    if _sha256(video) != report.get("video_sha256"):
        raise ValueError(f"rendered source {source_id} video hash does not match its report")
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError(f"unable to decode rendered source {source_id}")
    actual = (
        int(round(capture.get(cv2.CAP_PROP_FRAME_WIDTH))),
        int(round(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))),
        int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT))),
        float(capture.get(cv2.CAP_PROP_FPS)),
    )
    if actual[:3] != (1920, 1080, expected_frames) or not math.isclose(actual[3], 30.0, abs_tol=0.01):
        capture.release()
        raise ValueError(f"rendered source {source_id} media does not match its report")
    return capture, report, video


def compose_plate_frame(
    plate: Image.Image,
    segment: dict[str, Any],
    frame_index: int,
    output_size: tuple[int, int] = (1920, 1080),
) -> Image.Image:
    start = int(segment["start_frame"])
    end = int(segment["end_frame"])
    amount = 0.0 if start == end else (frame_index - start) / (end - start)
    frame = _camera_frame(plate, segment["camera"], amount, output_size)
    return apply_shot_effects(frame, segment.get("effects") or {}, frame_index - start, 30)


def render_golden_master(
    contract_path: str | Path,
    rendered_paths: dict[str, tuple[str | Path, str | Path]],
    output_dir: str | Path,
    *,
    audio_path: str | Path | None = None,
    ffmpeg: str = "ffmpeg",
) -> dict[str, Any]:
    contract, plate_paths = load_master_contract(contract_path)
    if set(rendered_paths) != {"GS030", "GS060", "GS070"}:
        raise ValueError("master renderer requires GS030, GS060, and GS070 video/report pairs")
    sources: dict[str, tuple[cv2.VideoCapture, dict[str, Any], Path]] = {}
    for source_id, (video, report) in rendered_paths.items():
        sources[source_id] = load_rendered_source(
            source_id,
            video,
            report,
            contract["rendered_sources"][source_id],
        )
    plates = {plate_id: Image.open(path).convert("RGB") for plate_id, path in plate_paths.items()}
    audio = Path(audio_path).resolve() if audio_path else None
    if audio and not audio.is_file():
        raise FileNotFoundError(f"master audio is missing: {audio}")
    ffmpeg_bin = _resolve_executable(ffmpeg)
    output = Path(output_dir).resolve()
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()
    video = output / "june-golden-scene-master.mp4"
    partial_video = output / "june-golden-scene-master.partial.mp4"
    partial_video.unlink(missing_ok=True)
    width = int(contract["output"]["width"])
    height = int(contract["output"]["height"])
    fps = int(contract["output"]["fps"])
    frame_count = int(contract["output"]["frame_count"])
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

    review_numbers: set[int] = set()
    internal_cuts: list[int] = []
    for shot in contract["shots"]:
        start = int(shot["start_frame"])
        end = int(shot["end_frame"])
        review_numbers.update({start, (start + end) // 2, end})
        for segment in (shot.get("segments") or [])[1:]:
            cut = int(segment["start_frame"])
            internal_cuts.append(cut)
            review_numbers.update({cut - 1, cut})
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise RuntimeError("unable to open FFmpeg master raw-video pipe")
    saved: dict[int, Path] = {}
    source_frame_counts = {source_id: 0 for source_id in sources}
    try:
        for frame_index in range(1, frame_count + 1):
            shot = shot_for_frame(contract["shots"], frame_index)
            source = shot["source"]
            if source["type"] == "rendered_shot":
                source_id = str(source["source_id"])
                success, bgr = sources[source_id][0].read()
                if not success:
                    raise RuntimeError(f"rendered source {source_id} stopped before its contracted end")
                source_frame_counts[source_id] += 1
                frame = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), "RGB")
            else:
                segment = segment_for_frame(shot["segments"], frame_index)
                frame = compose_plate_frame(plates[segment["plate_id"]], segment, frame_index)
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
        for capture, _, _ in sources.values():
            capture.release()
        for plate in plates.values():
            plate.close()
    if return_code != 0:
        partial_video.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg Golden Scene master render failed: {error_output.strip()}")
    if source_frame_counts != {"GS030": 171, "GS060": 258, "GS070": 228}:
        partial_video.unlink(missing_ok=True)
        raise RuntimeError("master did not consume every rendered shot frame exactly once")
    if not partial_video.is_file() or partial_video.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create a usable Golden Scene master")
    partial_video.replace(video)

    quality = encoded_quality_metrics(video, saved, frame_count)
    quality_gate = contract["encoded_quality_gate"]
    if quality["minimum_psnr_db"] < float(quality_gate["minimum_review_frame_psnr_db"]):
        raise RuntimeError("Golden Scene master encoded PSNR fell below the production gate")
    if quality["minimum_encoded_laplacian_variance"] < float(
        quality_gate["minimum_encoded_laplacian_variance"]
    ):
        raise RuntimeError("Golden Scene master encoded detail fell below the production gate")

    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "exact_1164_frame_golden_scene_picture_master",
        "master_id": contract["master_id"],
        "master_contract_sha256": _sha256(Path(contract_path).resolve()),
        "shots": [
            {
                "id": shot["id"],
                "start_frame": shot["start_frame"],
                "end_frame": shot["end_frame"],
                "frame_count": int(shot["end_frame"]) - int(shot["start_frame"]) + 1,
                "source": shot["source"],
                "segment_count": len(shot.get("segments") or []),
            }
            for shot in contract["shots"]
        ],
        "cut_frames": [130, 226, 397, 565, 679, 937],
        "internal_plate_cut_frames": internal_cuts,
        "rendered_sources": {
            source_id: {
                "video": source[2].name,
                "video_sha256": _sha256(source[2]),
                "report_gate": source[1]["gate"],
                "frames_consumed": source_frame_counts[source_id],
                "mapping": "source_frame_1_to_n_maps_one_to_one_to_master_shot_span",
                "retimed": False,
            }
            for source_id, source in sources.items()
        },
        "plate_sources": {
            plate_id: {"file": path.name, "sha256": contract["plates"][plate_id]["sha256"]}
            for plate_id, path in plate_paths.items()
        },
        "prohibited_interpolation": {
            "optical_flow_used": False,
            "cross_dissolve_used": False,
            "implicit_retiming_used": False,
        },
        "known_picture_boundaries": contract["known_picture_boundaries"],
        "audio": {"file": audio.name, "sha256": _sha256(audio)} if audio else None,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": 38.8,
        "width": width,
        "height": height,
        "review_frames": [path.name for _, path in sorted(saved.items())],
        "encoded_quality": quality,
        "first_frame_sha256": _sha256(saved[1]),
        "last_frame_sha256": _sha256(saved[1164]),
        "video": video.name,
        "video_sha256": _sha256(video),
    }
    (output / "june-golden-scene-master-report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble June's exact 38.8-second Golden Scene picture master")
    parser.add_argument("contract")
    for shot in ("gs030", "gs060", "gs070"):
        parser.add_argument(f"--{shot}-video", required=True)
        parser.add_argument(f"--{shot}-report", required=True)
    parser.add_argument("--audio")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--output-dir", default="build/edit/june-golden-scene-master")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rendered_paths = {
        "GS030": (args.gs030_video, args.gs030_report),
        "GS060": (args.gs060_video, args.gs060_report),
        "GS070": (args.gs070_video, args.gs070_report),
    }
    report = render_golden_master(
        args.contract,
        rendered_paths,
        args.output_dir,
        audio_path=args.audio,
        ffmpeg=args.ffmpeg,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
