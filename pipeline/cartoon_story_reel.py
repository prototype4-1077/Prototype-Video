"""Build a timed, captioned June Golden Scene story reel from approved style frames.

The reel is an editorial benchmark, not a replacement for deformation animation.
It uses local executables only: Piper for a clearly labelled non-canonical scratch
voice and FFmpeg for motion, procedural ambience, captions, and final encoding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Sequence

from pipeline.cartoon_vertical_slice import compile_plan, validate_config


STORY_REEL_CONTRACT_VERSION = 1
DEFAULT_LEAD_SECONDS = 0.10


def _require_executable(value: str | Path, label: str) -> str:
    candidate = Path(value)
    resolved = str(candidate.resolve()) if candidate.is_file() else shutil.which(str(value))
    if not resolved:
        raise FileNotFoundError(f"{label} executable not found: {value}")
    return resolved


def load_story_reel_spec(scene_path: str | Path, style_manifest_path: str | Path) -> tuple[dict, dict]:
    scene = json.loads(Path(scene_path).read_text(encoding="utf-8"))
    styles = json.loads(Path(style_manifest_path).read_text(encoding="utf-8"))
    validate_config(scene)
    if scene.get("benchmark_class") != "golden_scene":
        raise ValueError("story reel requires a golden_scene benchmark")
    if styles.get("production") != scene.get("production"):
        raise ValueError("style manifest production does not match the scene")
    if styles.get("status") != "provisional_art_direction_targets":
        raise ValueError("style manifest must remain explicitly provisional")
    return scene, styles


def style_frames_for_profile(
    styles: dict,
    *,
    profile: str,
    manifest_path: str | Path,
) -> dict[str, Path]:
    frames: dict[str, Path] = {}
    root = Path(manifest_path).resolve().parent
    for frame in styles.get("frames") or []:
        if frame.get("profile") != profile:
            continue
        shot = str(frame.get("shot") or "")
        path = root / str(frame.get("path") or "")
        if not shot or shot in frames:
            raise ValueError(f"style manifest has invalid or duplicate {profile} shot: {shot!r}")
        if not path.is_file():
            raise FileNotFoundError(f"style frame not found: {path}")
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != frame.get("sha256"):
            raise ValueError(f"style frame hash changed: {path.name}")
        frames[shot] = path
    return frames


def caption_chunks(text: str, *, max_words: int, max_chars: int) -> list[str]:
    """Split a caption into readable one-line phrases without changing its words."""
    words = str(text).strip().split()
    if not words:
        return []
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and (len(current) >= max_words or len(candidate) > max_chars):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def caption_events(scene: dict, *, profile: str) -> list[dict[str, Any]]:
    max_chars = 42 if profile == "youtube" else 28
    fps = int(scene.get("fps", 30))
    events: list[dict[str, Any]] = []
    elapsed = 0.0
    for shot in scene["shots"]:
        duration = float(shot["duration_seconds"])
        end_hold = int(shot.get("end_hold_frames", 0)) / fps
        caption_duration = max(0.25, duration - end_hold)
        chunks = caption_chunks(shot.get("line", ""), max_words=6, max_chars=max_chars)
        if chunks:
            weights = [max(1, len(chunk.split())) for chunk in chunks]
            total_weight = sum(weights)
            cursor = elapsed + 0.08
            available = max(0.1, caption_duration - 0.16)
            for index, (chunk, weight) in enumerate(zip(chunks, weights)):
                end = cursor + available * weight / total_weight
                events.append({"start": cursor, "end": min(end, elapsed + caption_duration), "text": chunk})
                cursor = end
        elapsed += duration
    return events


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def write_srt(events: Sequence[dict[str, Any]], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    for index, event in enumerate(events, 1):
        blocks.append(
            f"{index}\n{_srt_time(event['start'])} --> {_srt_time(event['end'])}\n{event['text']}\n"
        )
    destination.write_text("\n".join(blocks), encoding="utf-8", newline="\n")
    return destination


def _media_probe(ffprobe: str, path: Path) -> dict:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _duration(ffprobe: str, path: Path) -> float:
    payload = _media_probe(ffprobe, path)
    return float(payload["format"]["duration"])


def _parse_loudnorm_output(text: str) -> dict[str, float]:
    start = text.rfind("{")
    end = text.find("}", start)
    if start < 0 or end < 0:
        raise ValueError("FFmpeg loudnorm output did not contain JSON measurements")
    payload = json.loads(text[start : end + 1])
    return {
        "integrated_lufs": float(payload["input_i"]),
        "true_peak_dbtp": float(payload["input_tp"]),
        "loudness_range_lu": float(payload["input_lra"]),
    }


def _measure_loudness(ffmpeg: str, path: Path) -> dict[str, float]:
    result = subprocess.run(
        [
            ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-vn",
            "-af", "loudnorm=I=-16:TP=-1:LRA=7:print_format=json", "-f", "null",
            "NUL" if os.name == "nt" else "/dev/null",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return _parse_loudnorm_output(result.stderr + result.stdout)


def _atempo_filter(speed: float) -> str:
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("audio speed must be positive and finite")
    factors: list[float] = []
    while speed > 2.0:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={factor:.8f}" for factor in factors)


def _concat_file(paths: Sequence[Path], destination: Path) -> Path:
    lines = ["file '" + str(path.resolve()).replace("'", "'\\''") + "'" for path in paths]
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return destination


def _speech_tail_seconds(shot: dict, fps: int) -> float:
    declared = max(
        int(shot.get("end_hold_frames", 0)),
        int(shot.get("minimum_post_dialogue_hold_frames", 0)),
    ) / fps
    return max(0.18, declared)


def _render_voice(
    scene: dict,
    *,
    piper: str,
    voice_model: Path,
    ffmpeg: str,
    ffprobe: str,
    working: Path,
) -> tuple[Path, list[dict[str, Any]]]:
    audio_segments: list[Path] = []
    timings: list[dict[str, Any]] = []
    fps = int(scene.get("fps", 30))
    for index, shot in enumerate(scene["shots"], 1):
        raw = working / f"voice-{index:02d}-raw.wav"
        fitted = working / f"voice-{index:02d}.wav"
        shot_duration = float(shot["duration_seconds"])
        tail = _speech_tail_seconds(shot, fps)
        target_speech = max(0.35, shot_duration - DEFAULT_LEAD_SECONDS - tail)
        dialogue = str(shot.get("line", "")).strip() + "\n"

        def synthesize(length_scale: float) -> None:
            subprocess.run(
                [
                    piper,
                    "--model", str(voice_model),
                    "--output_file", str(raw),
                    "--length_scale", f"{length_scale:.6f}",
                    "--sentence_silence", "0.08",
                    "--quiet",
                ],
                input=dialogue,
                check=True,
                text=True,
            )

        # Prefer phoneme-duration control over aggressive post time-stretching.
        # The second pass estimates a shot-specific speaking cadence from the
        # first synthesis, then atempo only removes the small remaining error.
        length_scale = 1.08
        synthesize(length_scale)
        raw_duration = _duration(ffprobe, raw)
        fitted_scale = min(1.85, max(0.85, length_scale * target_speech / raw_duration))
        if abs(fitted_scale - length_scale) > 0.03:
            length_scale = fitted_scale
            synthesize(length_scale)
            raw_duration = _duration(ffprobe, raw)
        speed = raw_duration / target_speech
        audio_filter = (
            f"{_atempo_filter(speed)},"
            f"adelay={round(DEFAULT_LEAD_SECONDS * 1000)}:all=1,"
            f"apad,atrim=0:{shot_duration:.6f}"
        )
        subprocess.run(
            [
                ffmpeg, "-y", "-v", "error", "-i", str(raw),
                "-af", audio_filter,
                "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(fitted),
            ],
            check=True,
        )
        audio_segments.append(fitted)
        timings.append(
            {
                "shot": shot["id"],
                "raw_seconds": raw_duration,
                "piper_length_scale": length_scale,
                "target_speech_seconds": target_speech,
                "speed_factor": speed,
                "shot_seconds": shot_duration,
                "tail_hold_seconds": tail,
            }
        )
    concat_path = _concat_file(audio_segments, working / "voice-concat.txt")
    voice = working / "voice-dialogue.wav"
    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(voice),
        ],
        check=True,
    )
    return voice, timings


def _video_filter(shot: dict, frame_count: int) -> str:
    move = str(shot.get("camera_move", "locked")).lower().replace("_", " ")
    base = "scale=2048:1152:force_original_aspect_ratio=increase"
    if "push" in move:
        increment = 0.030 / max(1, frame_count)
        return (
            f"{base},zoompan=z='min(max(zoom,pzoom)+{increment:.10f},1.03)':"
            "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30"
        )
    if "lateral" in move or "drift" in move:
        return (
            f"{base},crop=1920:1080:"
            f"x='(in_w-out_w)*n/{max(1, frame_count - 1)}':y='(in_h-out_h)/2'"
        )
    if "vertical" in move or "tilt" in move:
        return (
            f"{base},crop=1920:1080:x='(in_w-out_w)/2':"
            f"y='(in_h-out_h)*(1-n/{max(1, frame_count - 1)})'"
        )
    return f"{base},crop=1920:1080:x='(in_w-out_w)/2':y='(in_h-out_h)/2'"


def _render_picture(
    plan: dict,
    frames: dict[str, Path],
    *,
    ffmpeg: str,
    working: Path,
) -> Path:
    segments: list[Path] = []
    for index, shot in enumerate(plan["shots"], 1):
        source = frames.get(str(shot["id"]))
        if source is None:
            raise ValueError(f"missing youtube style target for shot {shot['id']}")
        frame_count = int(shot["frame_end"]) - int(shot["frame_start"]) + 1
        destination = working / f"picture-{index:02d}.mp4"
        subprocess.run(
            [
                ffmpeg, "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(source),
                "-vf", _video_filter(shot, frame_count),
                "-frames:v", str(frame_count), "-r", "30", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", destination,
            ],
            check=True,
        )
        segments.append(destination)
    concat_path = _concat_file(segments, working / "picture-concat.txt")
    picture = working / "picture.mp4"
    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-c", "copy", picture,
        ],
        check=True,
    )
    return picture


def _mix_audio(voice: Path, duration: float, *, ffmpeg: str, destination: Path) -> Path:
    pour_delay_ms = round(28.0 * 1000)
    filter_graph = (
        f"anoisesrc=color=pink:amplitude=0.018:duration={duration:.6f}:sample_rate=48000,"
        "highpass=f=160,lowpass=f=3600,volume=0.10[amb];"
        "anoisesrc=color=white:amplitude=0.030:duration=1.8:sample_rate=48000,"
        f"highpass=f=450,lowpass=f=2600,afade=t=in:d=0.20,afade=t=out:st=1.25:d=0.55,adelay={pour_delay_ms}:all=1[pour];"
        "[0:a]aformat=sample_rates=48000:channel_layouts=mono,"
        "volume='if(between(t,18.8,22.6),0.56,if(between(t,7.5,13.2),0.88,"
        "if(between(t,22.6,31.2),0.80+0.20*(t-22.6)/8.6,1.05)))':eval=frame[dx];"
        "[dx][amb][pour]amix=inputs=3:duration=first:normalize=0,"
        "loudnorm=I=-16.2:LRA=7:TP=-1,alimiter=limit=0.89[mix]"
    )
    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error", "-i", str(voice),
            "-filter_complex", filter_graph, "-map", "[mix]",
            "-ar", "48000", "-ac", "2", "-c:a", "pcm_s24le", str(destination),
        ],
        check=True,
    )
    return destination


def _burn_and_mux(
    picture: Path,
    mix: Path,
    captions: Path,
    *,
    ffmpeg: str,
    output: Path,
    duration: float,
) -> Path:
    subtitle_filter = (
        "subtitles=captions.srt:force_style='FontName=Arial,FontSize=28,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=3,"
        "BackColour=&H70000000,Outline=1,Shadow=0,MarginV=54,Alignment=2'"
    )
    subprocess.run(
        [
            ffmpeg, "-y", "-v", "error", "-i", str(picture), "-i", str(mix),
            "-vf", subtitle_filter,
            "-af", "apad",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{duration:.6f}",
            "-movflags", "+faststart",
            str(output),
        ],
        check=True,
        cwd=output.parent,
    )
    return output


def _validate_delivery(probe: dict, *, expected_frames: int, expected_duration: float) -> dict:
    video = next((stream for stream in probe["streams"] if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in probe["streams"] if stream.get("codec_type") == "audio"), None)
    if not video or not audio:
        raise ValueError("story reel must contain video and audio")
    actual_frames = int(video.get("nb_frames") or 0)
    duration = float(probe["format"]["duration"])
    checks = {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": video.get("avg_frame_rate"),
        "frames": actual_frames,
        "duration_seconds": duration,
        "audio_sample_rate": int(audio["sample_rate"]),
    }
    if checks["width"] != 1920 or checks["height"] != 1080:
        raise ValueError("story reel must be 1920x1080")
    if actual_frames != expected_frames:
        raise ValueError(f"story reel frame count {actual_frames} != {expected_frames}")
    if abs(duration - expected_duration) > 0.05:
        raise ValueError(f"story reel duration {duration} != {expected_duration}")
    if checks["audio_sample_rate"] != 48000:
        raise ValueError("story reel audio must be 48 kHz")
    return checks


def render_story_reel(
    scene_path: str | Path,
    style_manifest_path: str | Path,
    *,
    output_dir: str | Path,
    piper: str | Path,
    voice_model: str | Path,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict:
    scene, styles = load_story_reel_spec(scene_path, style_manifest_path)
    output = Path(output_dir).resolve()
    working = output / "working"
    working.mkdir(parents=True, exist_ok=True)
    piper_bin = _require_executable(piper, "Piper")
    ffmpeg_bin = _require_executable(ffmpeg, "FFmpeg")
    ffprobe_bin = _require_executable(ffprobe, "FFprobe")
    model = Path(voice_model).resolve()
    if not model.is_file() or not Path(str(model) + ".json").is_file():
        raise FileNotFoundError(f"Piper voice model or config missing: {model}")

    plan = compile_plan(scene, profile="youtube", quality="production")
    frames = style_frames_for_profile(styles, profile="youtube", manifest_path=style_manifest_path)
    captions = write_srt(caption_events(scene, profile="youtube"), output / "captions.srt")
    voice, voice_timings = _render_voice(
        scene,
        piper=piper_bin,
        voice_model=model,
        ffmpeg=ffmpeg_bin,
        ffprobe=ffprobe_bin,
        working=working,
    )
    picture = _render_picture(plan, frames, ffmpeg=ffmpeg_bin, working=working)
    mix = _mix_audio(
        voice,
        float(plan["duration_seconds"]),
        ffmpeg=ffmpeg_bin,
        destination=output / "june-golden-scene-mix.wav",
    )
    video = _burn_and_mux(
        picture,
        mix,
        captions,
        ffmpeg=ffmpeg_bin,
        output=output / "june-golden-scene-story-reel-youtube.mp4",
        duration=float(plan["duration_seconds"]),
    )
    checks = _validate_delivery(
        _media_probe(ffprobe_bin, video),
        expected_frames=int(plan["frame_end"]),
        expected_duration=float(plan["duration_seconds"]),
    )
    loudness = _measure_loudness(ffmpeg_bin, video)
    sound_contract = scene.get("sound") or {}
    lufs_target = float(sound_contract.get("target_lufs_i", -16))
    lufs_tolerance = float(sound_contract.get("target_lufs_tolerance", 1))
    true_peak_max = float(sound_contract.get("true_peak_dbtp_max", -1))
    lra_range = sound_contract.get("target_lra_lu") or [4, 8]
    loudness.update(
        {
            "integrated_lufs_pass": abs(loudness["integrated_lufs"] - lufs_target) <= lufs_tolerance,
            "true_peak_pass": loudness["true_peak_dbtp"] <= true_peak_max,
            "loudness_range_pass": float(lra_range[0]) <= loudness["loudness_range_lu"] <= float(lra_range[1]),
        }
    )
    report = {
        "contract_version": STORY_REEL_CONTRACT_VERSION,
        "production": scene["production"],
        "classification": "style-frame story reel; not final deformation animation",
        "cost_policy": "local/open-source tools only; no paid runtime API",
        "video": video.name,
        "mix": mix.name,
        "captions": captions.name,
        "style_manifest": str(Path(style_manifest_path).resolve()),
        "voice": {
            "canonical": False,
            "engine": "Piper 1.2.0",
            "model": model.name,
            "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
            "purpose": "non-canonical scratch performance for timing and editorial evaluation",
            "shot_fits": voice_timings,
        },
        "delivery_checks": checks,
        "audio_checks": loudness,
        "known_limits": [
            "Style-frame motion is editorial camera motion, not final character deformation.",
            "The free local scratch voice is not June's canonical performance.",
            *([] if loudness["loudness_range_pass"] else ["Scratch-voice loudness range remains below the 4–8 LU final-mix target."]),
        ],
    }
    (output / "story-reel-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the June Golden Scene style-frame story reel")
    parser.add_argument("scene")
    parser.add_argument("style_manifest")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--piper", required=True)
    parser.add_argument("--voice-model", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = render_story_reel(
        args.scene,
        args.style_manifest,
        output_dir=args.output_dir,
        piper=args.piper,
        voice_model=args.voice_model,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
