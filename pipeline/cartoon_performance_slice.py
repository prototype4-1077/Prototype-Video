"""Render a timed June performance proof from authored start/mid/end key poses.

This is an intentionally honest bridge between a style-frame story reel and a
continuously deforming hero rig.  It can render either a designed limited-
animation treatment (short pose dissolves plus eased camera motion) or an
experimental FFmpeg motion-compensated treatment.  Both modes use local tools,
pin every source image by SHA-256, preserve the source soundtrack timing, and
emit an exact-frame delivery report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
from typing import Any, Sequence

from pipeline.cartoon_story_reel import (
    _measure_loudness,
    _media_probe,
    _require_executable,
    caption_events,
    write_srt,
)
from pipeline.cartoon_vertical_slice import validate_config


PERFORMANCE_SLICE_CONTRACT_VERSION = 1
PERFORMANCE_SLICE_STATUS = "ai_assisted_key_pose_performance_prototype"
PERFORMANCE_SLICE_CLASSIFICATION = (
    "AI-assisted key-pose limited-animation performance slice; "
    "not final topology deformation."
)
SUPPORTED_MODES = {"designed", "motion", "pose"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"performance keyframe is not a valid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def _verified_image(entry: dict, root: Path, *, label: str) -> Path:
    path = (root / str(entry.get("path") or "")).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    expected_hash = str(entry.get("sha256") or "")
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise ValueError(f"{label} hash changed: {path.name}")
    dimensions = _png_dimensions(path)
    declared = (int(entry.get("width") or 0), int(entry.get("height") or 0))
    if dimensions != declared:
        raise ValueError(f"{label} dimensions {dimensions} != {declared}: {path.name}")
    return path


def validate_key_pose_timing(shot: dict) -> None:
    """Validate the three-pose timing contract without touching the filesystem."""
    shot_id = str(shot.get("id") or "<unknown>")
    frame_count = int(shot.get("frame_count") or 0)
    keyframes = shot.get("keyframes") or []
    phases = [str(keyframe.get("phase") or "") for keyframe in keyframes]
    frames = [int(keyframe.get("frame", -1)) for keyframe in keyframes]
    if phases != ["start", "mid", "end"]:
        raise ValueError(f"{shot_id} must declare exactly start, mid, end key poses")
    if len(frames) != len(set(frames)) or frames != sorted(frames):
        raise ValueError(f"{shot_id} key-pose frames must be unique and increasing")
    if frames[0] != 0 or frames[-1] != frame_count - 1 or not 0 < frames[1] < frame_count - 1:
        raise ValueError(f"{shot_id} key-pose timing does not span the shot")


def load_performance_spec(
    scene_path: str | Path,
    performance_manifest_path: str | Path,
) -> tuple[dict, dict, dict[str, list[Path]]]:
    """Load and strictly validate a performance manifest and all pinned artwork."""
    scene_file = Path(scene_path).resolve()
    manifest_file = Path(performance_manifest_path).resolve()
    scene = json.loads(scene_file.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    validate_config(scene)

    if scene.get("benchmark_class") != "golden_scene":
        raise ValueError("performance slice requires a golden_scene benchmark")
    if manifest.get("production") != scene.get("production"):
        raise ValueError("performance manifest production does not match the scene")
    if manifest.get("status") != PERFORMANCE_SLICE_STATUS:
        raise ValueError("performance manifest must retain its explicitly non-final status")
    if manifest.get("approval_required") is not True:
        raise ValueError("performance key poses must remain gated by explicit human approval")
    if manifest.get("profile") != "youtube":
        raise ValueError("performance slice v1 only supports the youtube profile")

    fps = int(manifest.get("fps") or 0)
    if fps != int(scene.get("fps") or 0) or fps != 30:
        raise ValueError("performance slice must use the shared 30 fps scene clock")
    if (int(manifest.get("width") or 0), int(manifest.get("height") or 0)) != (1920, 1080):
        raise ValueError("performance slice delivery must be 1920x1080")

    declared_source = (manifest_file.parent / str(manifest.get("source_scene") or "")).resolve()
    if declared_source != scene_file:
        raise ValueError("performance manifest source_scene does not resolve to the supplied scene")

    scene_shots = scene.get("shots") or []
    scene_by_id = {str(shot.get("id")): shot for shot in scene_shots}
    shots = manifest.get("shots") or []
    shot_ids = [str(shot.get("id") or "") for shot in shots]
    if not shot_ids or len(shot_ids) != len(set(shot_ids)):
        raise ValueError("performance manifest shot ids must be present and unique")
    if any(shot_id not in scene_by_id for shot_id in shot_ids):
        raise ValueError("performance manifest contains a shot not present in the source scene")

    source_order = [str(shot.get("id")) for shot in scene_shots]
    first_index = source_order.index(shot_ids[0])
    if source_order[first_index : first_index + len(shot_ids)] != shot_ids:
        raise ValueError("performance shots must be a contiguous source-scene range")
    expected_offset = sum(float(shot["duration_seconds"]) for shot in scene_shots[:first_index])
    declared_offset = float(manifest.get("source_timeline_offset_seconds") or 0)
    if abs(expected_offset - declared_offset) > 1 / fps:
        raise ValueError("performance source timeline offset does not match the selected shots")

    root = manifest_file.parent
    identity = manifest.get("identity_reference") or {}
    _verified_image(identity, root, label="canonical identity reference")

    resolved: dict[str, list[Path]] = {}
    total_frames = 0
    total_duration = 0.0
    for shot in shots:
        shot_id = str(shot["id"])
        source_shot = scene_by_id[shot_id]
        duration = float(shot.get("duration_seconds") or 0)
        frame_count = int(shot.get("frame_count") or 0)
        if duration != float(source_shot["duration_seconds"]):
            raise ValueError(f"performance duration changed for {shot_id}")
        if frame_count != round(duration * fps):
            raise ValueError(f"performance frame count is not exact for {shot_id}")

        keyframes = shot.get("keyframes") or []
        validate_key_pose_timing(shot)
        resolved[shot_id] = [
            _verified_image(keyframe, root, label=f"{shot_id} {keyframe['phase']} keyframe")
            for keyframe in keyframes
        ]
        total_frames += frame_count
        total_duration += duration

    if total_frames != int(manifest.get("frame_count") or 0):
        raise ValueError("performance manifest total frame count does not match its shots")
    if abs(total_duration - float(manifest.get("duration_seconds") or 0)) > 1 / fps:
        raise ValueError("performance manifest duration does not match its shots")
    if total_frames != round(total_duration * fps):
        raise ValueError("performance manifest duration is not frame-exact")
    return scene, manifest, resolved


def performance_caption_events(scene: dict, manifest: dict) -> list[dict[str, Any]]:
    """Return source captions retimed to the performance slice's output clock."""
    offset = float(manifest["source_timeline_offset_seconds"])
    duration = float(manifest["duration_seconds"])
    end = offset + duration
    selected = {str(shot["id"]) for shot in manifest["shots"]}
    shot_ranges: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for shot in scene["shots"]:
        shot_end = cursor + float(shot["duration_seconds"])
        shot_ranges[str(shot["id"])] = (cursor, shot_end)
        cursor = shot_end

    events: list[dict[str, Any]] = []
    for event in caption_events(scene, profile="youtube"):
        owning_shot = next(
            (
                shot_id
                for shot_id, (shot_start, shot_end) in shot_ranges.items()
                if event["start"] >= shot_start and event["start"] < shot_end
            ),
            None,
        )
        if owning_shot not in selected or event["end"] <= offset or event["start"] >= end:
            continue
        events.append(
            {
                "start": max(0.0, float(event["start"]) - offset),
                "end": min(duration, float(event["end"]) - offset),
                "text": str(event["text"]),
            }
        )
    if not events or any(event["end"] <= event["start"] for event in events):
        raise ValueError("performance slice captions are empty or invalid")
    return events


def _run(command: Sequence[str | Path], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(value) for value in command],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed ({result.returncode}): {detail[-4000:]}")
    return result


def _concat_file(paths: Sequence[Path], destination: Path) -> Path:
    lines = ["ffconcat version 1.0"]
    for path in paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return destination


def _camera_filter(frame_count: int, style: str, pose_index: int) -> str:
    last = max(1, frame_count - 1)
    q = f"(on/{last})"
    ease = f"(3*{q}^2-2*{q}^3)"
    if style == "grounded_rise":
        zoom = 0.010 + pose_index * 0.002
        pan_x = (-2 + pose_index * 2)
        pan_y = (3 - pose_index * 2)
    elif style == "prop_and_gaze":
        zoom = 0.014
        pan_x = (-3 + pose_index * 3)
        pan_y = 0
    else:
        zoom = 0.020
        pan_x = (pose_index - 1)
        pan_y = (1 - pose_index)
    return (
        "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
        f"zoompan=z='1+{zoom:.4f}*{ease}':"
        f"x='iw/2-(iw/zoom/2)+{pan_x}*{ease}':"
        f"y='ih/2-(ih/zoom/2)+{pan_y}*{ease}':"
        "d=1:s=1920x1080:fps=30,setsar=1,format=yuv420p,setpts=PTS-STARTPTS"
    )


def _render_designed_shot(
    shot: dict,
    images: Sequence[Path],
    *,
    ffmpeg: str,
    destination: Path,
) -> Path:
    fps = 30
    frame_count = int(shot["frame_count"])
    duration = frame_count / fps
    mid_frame = int(shot["keyframes"][1]["frame"])
    dissolve = min(0.60, max(0.36, duration * 0.11))
    first_offset = max(0.0, mid_frame / fps - dissolve)
    second_offset = max(first_offset + dissolve, duration - dissolve - 1 / fps)

    command: list[str | Path] = [ffmpeg, "-y", "-v", "error"]
    for image in images:
        command.extend(["-loop", "1", "-framerate", str(fps), "-t", f"{duration + 0.1:.6f}", "-i", image])
    filters = []
    for index in range(3):
        filters.append(
            f"[{index}:v]{_camera_filter(frame_count, str(shot['transition_style']), index)}[k{index}]"
        )
    filters.extend(
        [
            f"[k0][k1]xfade=transition=fade:duration={dissolve:.6f}:offset={first_offset:.6f}[x1]",
            f"[x1][k2]xfade=transition=fade:duration={dissolve:.6f}:offset={second_offset:.6f}[out]",
        ]
    )
    command.extend(
        [
            "-filter_complex", ";".join(filters), "-map", "[out]",
            "-frames:v", str(frame_count), "-r", str(fps), "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-pix_fmt", "yuv420p", "-video_track_timescale", "30000", destination,
        ]
    )
    _run(command)
    return destination


def _motion_filter_available(ffmpeg: str) -> bool:
    result = _run([ffmpeg, "-hide_banner", "-filters"])
    return "minterpolate" in (result.stdout + result.stderr)


def _write_motion_concat(shot: dict, images: Sequence[Path], destination: Path) -> Path:
    fps = 30
    frames = [int(keyframe["frame"]) for keyframe in shot["keyframes"]]
    durations = [
        max(1 / fps, (frames[1] - frames[0]) / fps),
        max(1 / fps, (frames[2] - frames[1]) / fps),
        1 / fps,
    ]
    lines = ["ffconcat version 1.0"]
    for image, duration in zip(images, durations):
        escaped = str(image.resolve()).replace("'", "'\\''")
        lines.extend([f"file '{escaped}'", f"duration {duration:.9f}"])
    escaped_last = str(images[-1].resolve()).replace("'", "'\\''")
    lines.append(f"file '{escaped_last}'")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return destination


def _render_motion_shot(
    shot: dict,
    images: Sequence[Path],
    *,
    ffmpeg: str,
    destination: Path,
    working: Path,
) -> Path:
    if not _motion_filter_available(ffmpeg):
        raise RuntimeError("this FFmpeg build does not provide the minterpolate filter")
    frame_count = int(shot["frame_count"])
    normalized: list[Path] = []
    for index, image in enumerate(images):
        normalized_image = working / f"{shot['id']}-motion-key-{index}.png"
        _run(
            [
                ffmpeg, "-y", "-v", "error", "-i", image,
                "-vf", "scale=960:540:force_original_aspect_ratio=increase,crop=960:540,setsar=1",
                "-frames:v", "1", normalized_image,
            ]
        )
        normalized.append(normalized_image)
    concat = _write_motion_concat(shot, normalized, working / f"{shot['id']}-motion.ffconcat")
    video_filter = (
        "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
        "tpad=stop_mode=clone:stop_duration=0.10,"
        "scale=1920:1080:flags=lanczos,format=yuv420p"
    )
    _run(
        [
            ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", concat,
            "-vf", video_filter, "-frames:v", str(frame_count), "-r", "30", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-pix_fmt", "yuv420p", "-video_track_timescale", "30000", destination,
        ]
    )
    return destination


def _validate_picture_segment(ffprobe: str, path: Path, *, expected_frames: int) -> None:
    probe = _media_probe(ffprobe, path)
    video = next((stream for stream in probe["streams"] if stream.get("codec_type") == "video"), None)
    actual_frames = int((video or {}).get("nb_frames") or 0)
    if actual_frames != expected_frames:
        raise ValueError(f"picture segment {path.name} has {actual_frames} frames; expected {expected_frames}")


def _render_hold_clip(
    image: Path,
    *,
    frame_count: int,
    style: str,
    pose_index: int,
    ffmpeg: str,
    destination: Path,
) -> Path:
    _run(
        [
            ffmpeg, "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", image,
            "-vf", _camera_filter(frame_count, style, pose_index),
            "-frames:v", str(frame_count), "-r", "30", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-pix_fmt", "yuv420p", "-video_track_timescale", "30000", destination,
        ]
    )
    return destination


def _render_sampled_transition(
    motion_source: Path,
    *,
    source_start: int,
    source_end: int,
    frame_count: int,
    ffmpeg: str,
    destination: Path,
) -> Path:
    if source_end - source_start <= frame_count:
        raise ValueError("pose transition source range must exceed its output frame count")
    indices = [
        round(source_start + (index + 1) * (source_end - source_start) / (frame_count + 1))
        for index in range(frame_count)
    ]
    if len(indices) != len(set(indices)):
        raise ValueError("pose transition sampling produced duplicate source frames")
    expression = "+".join(f"eq(n\\,{frame})" for frame in indices)
    video_filter = f"select='{expression}',setpts=N/(30*TB),format=yuv420p"
    _run(
        [
            ffmpeg, "-y", "-v", "error", "-i", motion_source,
            "-vf", video_filter, "-frames:v", str(frame_count), "-r", "30", "-an",
            "-c:v", "libx264", "-preset", "medium", "-crf", "15",
            "-pix_fmt", "yuv420p", "-video_track_timescale", "30000", destination,
        ]
    )
    return destination


def _pose_timing(shot: dict) -> tuple[int, int, int, int, int]:
    style = str(shot["transition_style"])
    if style == "grounded_rise":
        first_transition, second_transition, end_hold = 7, 7, 12
    elif style == "prop_and_gaze":
        first_transition, second_transition, end_hold = 6, 5, 12
    else:
        first_transition, second_transition, end_hold = 10, 10, 18
    frame_count = int(shot["frame_count"])
    mid_frame = int(shot["keyframes"][1]["frame"])
    start_hold = mid_frame - first_transition
    mid_hold = frame_count - end_hold - second_transition - mid_frame
    if min(start_hold, mid_hold, end_hold) <= 0:
        raise ValueError(f"pose timing leaves no readable hold for {shot['id']}")
    return start_hold, first_transition, mid_hold, second_transition, end_hold


def _render_pose_shot(
    shot: dict,
    images: Sequence[Path],
    *,
    motion_source: Path,
    ffmpeg: str,
    destination: Path,
    working: Path,
) -> Path:
    timing = _pose_timing(shot)
    style = str(shot["transition_style"])
    mid_frame = int(shot["keyframes"][1]["frame"])
    last_frame = int(shot["frame_count"]) - 1
    clips = [
        working / f"{shot['id']}-pose-hold-start.mp4",
        working / f"{shot['id']}-pose-transition-one.mp4",
        working / f"{shot['id']}-pose-hold-mid.mp4",
        working / f"{shot['id']}-pose-transition-two.mp4",
        working / f"{shot['id']}-pose-hold-end.mp4",
    ]
    _render_hold_clip(
        images[0], frame_count=timing[0], style=style, pose_index=0,
        ffmpeg=ffmpeg, destination=clips[0],
    )
    _render_sampled_transition(
        motion_source,
        source_start=0,
        source_end=mid_frame,
        frame_count=timing[1],
        ffmpeg=ffmpeg,
        destination=clips[1],
    )
    _render_hold_clip(
        images[1], frame_count=timing[2], style=style, pose_index=1,
        ffmpeg=ffmpeg, destination=clips[2],
    )
    _render_sampled_transition(
        motion_source,
        source_start=mid_frame,
        source_end=last_frame,
        frame_count=timing[3],
        ffmpeg=ffmpeg,
        destination=clips[3],
    )
    _render_hold_clip(
        images[2], frame_count=timing[4], style=style, pose_index=2,
        ffmpeg=ffmpeg, destination=clips[4],
    )
    concat = _concat_file(clips, working / f"{shot['id']}-pose.ffconcat")
    _run([ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", destination])
    return destination


def _render_picture(
    manifest: dict,
    resolved: dict[str, list[Path]],
    *,
    mode: str,
    ffmpeg: str,
    ffprobe: str,
    working: Path,
    resume: bool = False,
) -> Path:
    segments: list[Path] = []
    for index, shot in enumerate(manifest["shots"], 1):
        destination = working / f"{index:02d}-{shot['id']}-{mode}.mp4"
        if resume and destination.is_file():
            try:
                _validate_picture_segment(ffprobe, destination, expected_frames=int(shot["frame_count"]))
                segments.append(destination)
                continue
            except (ValueError, RuntimeError, subprocess.SubprocessError):
                pass
        if mode == "motion":
            _render_motion_shot(
                shot,
                resolved[str(shot["id"])],
                ffmpeg=ffmpeg,
                destination=destination,
                working=working,
            )
        elif mode == "pose":
            motion_source = working / f"{index:02d}-{shot['id']}-motion.mp4"
            try:
                _validate_picture_segment(
                    ffprobe,
                    motion_source,
                    expected_frames=int(shot["frame_count"]),
                )
            except (FileNotFoundError, ValueError, RuntimeError, subprocess.SubprocessError):
                _render_motion_shot(
                    shot,
                    resolved[str(shot["id"])],
                    ffmpeg=ffmpeg,
                    destination=motion_source,
                    working=working,
                )
                _validate_picture_segment(
                    ffprobe,
                    motion_source,
                    expected_frames=int(shot["frame_count"]),
                )
            _render_pose_shot(
                shot,
                resolved[str(shot["id"])],
                motion_source=motion_source,
                ffmpeg=ffmpeg,
                destination=destination,
                working=working,
            )
        else:
            _render_designed_shot(
                shot,
                resolved[str(shot["id"])],
                ffmpeg=ffmpeg,
                destination=destination,
            )
        _validate_picture_segment(ffprobe, destination, expected_frames=int(shot["frame_count"]))
        segments.append(destination)

    concat = _concat_file(segments, working / f"picture-{mode}.ffconcat")
    picture = working / f"picture-{mode}.mp4"
    _run([ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", picture])
    return picture


def _extract_audio(
    source: Path,
    *,
    offset: float,
    duration: float,
    ffmpeg: str,
    destination: Path,
) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"performance audio source not found: {source}")
    fade_out = max(0.0, duration - 0.03)
    audio_filter = (
        f"atrim=start={offset:.6f}:duration={duration:.6f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d=0.03,afade=t=out:st={fade_out:.6f}:d=0.03"
    )
    _run(
        [
            ffmpeg, "-y", "-v", "error", "-i", source,
            "-af", audio_filter, "-ar", "48000", "-ac", "2",
            "-c:a", "pcm_s24le", destination,
        ]
    )
    return destination


def _mux_delivery(
    picture: Path,
    audio: Path,
    captions: Path,
    *,
    duration: float,
    frame_count: int,
    ffmpeg: str,
    destination: Path,
) -> Path:
    subtitle_filter = (
        f"subtitles={captions.name}:force_style='FontName=Arial,FontSize=28,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=3,"
        "BackColour=&H70000000,Outline=1,Shadow=0,MarginV=54,Alignment=2'"
    )
    _run(
        [
            ffmpeg, "-y", "-v", "error", "-i", picture, "-i", audio,
            "-vf", subtitle_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-frames:v", str(frame_count), "-t", f"{duration:.6f}",
            "-movflags", "+faststart", destination,
        ],
        cwd=destination.parent,
    )
    return destination


def _validate_delivery(probe: dict, *, expected_frames: int, expected_duration: float) -> dict:
    video = next((stream for stream in probe["streams"] if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in probe["streams"] if stream.get("codec_type") == "audio"), None)
    if not video or not audio:
        raise ValueError("performance slice must contain video and audio")
    checks = {
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": str(video.get("avg_frame_rate") or ""),
        "frames": int(video.get("nb_frames") or 0),
        "duration_seconds": float(probe["format"]["duration"]),
        "audio_sample_rate": int(audio.get("sample_rate") or 0),
    }
    if (checks["width"], checks["height"]) != (1920, 1080):
        raise ValueError("performance slice must be 1920x1080")
    if checks["fps"] not in {"30/1", "30000/1000"}:
        raise ValueError(f"performance slice frame rate is not 30 fps: {checks['fps']}")
    if checks["frames"] != expected_frames:
        raise ValueError(f"performance slice frame count {checks['frames']} != {expected_frames}")
    if abs(checks["duration_seconds"] - expected_duration) > 0.05:
        raise ValueError("performance slice duration is not frame-exact")
    if checks["audio_sample_rate"] != 48000:
        raise ValueError("performance slice audio must be 48 kHz")
    return checks


def _full_decode(video: Path, *, ffmpeg: str) -> None:
    null_device = "NUL" if os.name == "nt" else "/dev/null"
    _run([ffmpeg, "-v", "error", "-i", video, "-f", "null", null_device])


def _contact_sheet(
    video: Path,
    manifest: dict,
    *,
    ffmpeg: str,
    destination: Path,
) -> Path:
    selected: list[int] = []
    offset = 0
    for shot in manifest["shots"]:
        selected.extend(offset + int(keyframe["frame"]) for keyframe in shot["keyframes"])
        offset += int(shot["frame_count"])
    expression = "+".join(f"eq(n\\,{frame})" for frame in selected)
    video_filter = (
        f"select='{expression}',scale=640:360:flags=lanczos,"
        "tile=3x3:padding=4:margin=4:color=0x241b17"
    )
    _run([ffmpeg, "-y", "-v", "error", "-i", video, "-vf", video_filter, "-frames:v", "1", destination])
    return destination


def render_performance_slice(
    scene_path: str | Path,
    performance_manifest_path: str | Path,
    *,
    audio_source: str | Path,
    output_dir: str | Path,
    mode: str = "designed",
    resume: bool = False,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
) -> dict:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"performance render mode must be one of {sorted(SUPPORTED_MODES)}")
    scene, manifest, resolved = load_performance_spec(scene_path, performance_manifest_path)
    ffmpeg_bin = _require_executable(ffmpeg, "FFmpeg")
    ffprobe_bin = _require_executable(ffprobe, "FFprobe")
    output = Path(output_dir).resolve()
    working = output / "working"
    working.mkdir(parents=True, exist_ok=True)

    duration = float(manifest["duration_seconds"])
    frame_count = int(manifest["frame_count"])
    captions = write_srt(performance_caption_events(scene, manifest), output / "performance-captions.srt")
    cached_picture = working / f"picture-{mode}.mp4"
    picture: Path | None = None
    if resume and cached_picture.is_file():
        try:
            _validate_picture_segment(ffprobe_bin, cached_picture, expected_frames=frame_count)
            picture = cached_picture
        except (ValueError, RuntimeError, subprocess.SubprocessError):
            picture = None
    if picture is None:
        picture = _render_picture(
            manifest,
            resolved,
            mode=mode,
            ffmpeg=ffmpeg_bin,
            ffprobe=ffprobe_bin,
            working=working,
            resume=resume,
        )
    cached_audio = output / "performance-mix.wav"
    if resume and cached_audio.is_file():
        audio = cached_audio
    else:
        audio = _extract_audio(
            Path(audio_source).resolve(),
            offset=float(manifest["source_timeline_offset_seconds"]),
            duration=duration,
            ffmpeg=ffmpeg_bin,
            destination=cached_audio,
        )
    video = _mux_delivery(
        picture,
        audio,
        captions,
        duration=duration,
        frame_count=frame_count,
        ffmpeg=ffmpeg_bin,
        destination=output / f"june-golden-scene-performance-slice-{mode}.mp4",
    )
    checks = _validate_delivery(
        _media_probe(ffprobe_bin, video),
        expected_frames=frame_count,
        expected_duration=duration,
    )
    _full_decode(video, ffmpeg=ffmpeg_bin)
    contact_sheet = _contact_sheet(
        video,
        manifest,
        ffmpeg=ffmpeg_bin,
        destination=output / f"june-golden-scene-performance-slice-{mode}-contact-sheet.png",
    )
    loudness = _measure_loudness(ffmpeg_bin, video)
    report = {
        "contract_version": PERFORMANCE_SLICE_CONTRACT_VERSION,
        "production": scene["production"],
        "classification": PERFORMANCE_SLICE_CLASSIFICATION,
        "mode": mode,
        "cost_policy": "local/open-source tools and built-in image generation only; no paid runtime API",
        "source_timeline": {
            "offset_seconds": float(manifest["source_timeline_offset_seconds"]),
            "duration_seconds": duration,
            "shots": [shot["id"] for shot in manifest["shots"]],
        },
        "video": {"path": video.name, "sha256": _sha256(video)},
        "mix": {"path": audio.name, "sha256": _sha256(audio)},
        "captions": {"path": captions.name, "sha256": _sha256(captions)},
        "contact_sheet": {"path": contact_sheet.name, "sha256": _sha256(contact_sheet)},
        "delivery_checks": {**checks, "full_decode_pass": True},
        "audio_checks": loudness,
        "source_keyframes": {
            shot_id: [{"path": path.name, "sha256": _sha256(path)} for path in paths]
            for shot_id, paths in resolved.items()
        },
        "known_limits": list(manifest.get("known_limits") or []),
    }
    report_path = output / f"performance-slice-{mode}-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the June GS030-GS050 performance slice")
    parser.add_argument("scene")
    parser.add_argument("performance_manifest")
    parser.add_argument("--audio-source", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=sorted(SUPPORTED_MODES), default="designed")
    parser.add_argument("--resume", action="store_true", help="Reuse completed picture/audio intermediates")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = render_performance_slice(
        args.scene,
        args.performance_manifest,
        audio_source=args.audio_source,
        output_dir=args.output_dir,
        mode=args.mode,
        resume=args.resume,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
