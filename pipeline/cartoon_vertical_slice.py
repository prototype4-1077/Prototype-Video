"""Compile and render the June Oxley porch-dialogue vertical slice."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from pipeline.cartoon_lipsync import cues_to_frames, normalize_rhubarb, run_rhubarb
from pipeline.cartoon_motion import render_profile


VERTICAL_SLICE_CONTRACT_VERSION = 1
REQUIRED_CHARACTER_ID = "june_oxley"


def _positive(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if number <= 0:
        raise ValueError(f"{field} must be positive")
    return number


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ValueError("vertical-slice config must be an object")
    character = config.get("character")
    if not isinstance(character, dict) or character.get("id") != REQUIRED_CHARACTER_ID:
        raise ValueError("vertical slice must explicitly select character.id 'june_oxley'")
    if character.get("profile") != "june_oxley":
        raise ValueError("vertical slice must explicitly select the June Oxley profile")
    dialogue = config.get("dialogue")
    if not isinstance(dialogue, dict) or not str(dialogue.get("text", "")).strip():
        raise ValueError("dialogue.text is required")
    shots = config.get("shots")
    if not isinstance(shots, list) or len(shots) < 3:
        raise ValueError("a production vertical slice requires at least three shots")
    seen = set()
    for index, shot in enumerate(shots):
        if not isinstance(shot, dict):
            raise ValueError(f"shots[{index}] must be an object")
        shot_id = str(shot.get("id", "")).strip()
        if not shot_id or shot_id in seen:
            raise ValueError(f"shots[{index}].id must be unique and non-empty")
        seen.add(shot_id)
        _positive(shot.get("duration_seconds"), f"shots[{index}].duration_seconds")
        if shot.get("camera") not in {"wide", "medium", "close"}:
            raise ValueError(f"shots[{index}].camera must be wide, medium, or close")


def compile_plan(
    config: dict,
    *,
    profile: str,
    quality: str,
    mouth_cues: dict | None = None,
) -> dict:
    """Create one deterministic, frame-accurate plan for a render profile."""
    validate_config(config)
    if quality not in {"proof", "production"}:
        raise ValueError("quality must be 'proof' or 'production'")
    scale = 0.25 if quality == "proof" else 1.0
    output = render_profile(profile, scale=scale)
    output.update(
        {
            "quality": quality,
            "engine": "BLENDER_WORKBENCH" if quality == "proof" else "BLENDER_EEVEE_NEXT",
            "samples": 16 if quality == "proof" else 64,
        }
    )
    fps = int(output["fps"])

    shots = []
    elapsed = 0.0
    previous_end = 0
    for source in config["shots"]:
        duration = _positive(source["duration_seconds"], f"shot {source['id']} duration")
        frame_start = previous_end + 1
        elapsed += duration
        frame_end = max(frame_start, round(elapsed * fps))
        shots.append({**source, "frame_start": frame_start, "frame_end": frame_end})
        previous_end = frame_end

    duration = previous_end / fps
    if mouth_cues is None:
        mouth_cues = {"metadata": {"duration": duration}, "mouthCues": []}
    normalized = normalize_rhubarb(mouth_cues, duration=duration)
    frame_cues = cues_to_frames(normalized, fps=fps, duration=duration)

    return {
        "version": VERTICAL_SLICE_CONTRACT_VERSION,
        "production": config.get("production", "june-porch-dialogue"),
        "character": config["character"],
        "set": config.get("set", {}),
        "dialogue": config["dialogue"],
        "render": output,
        "duration_seconds": duration,
        "frame_start": 1,
        "frame_end": previous_end,
        "shots": shots,
        "mouth_cues": frame_cues,
        "animation": config.get("animation", {}),
    }


def _require_executable(value: str, label: str) -> str:
    resolved = shutil.which(value) if not Path(value).is_file() else str(Path(value))
    if not resolved:
        raise FileNotFoundError(f"{label} executable not found: {value}")
    return resolved


def _render_frames(blender: str, plan_path: Path, frames_dir: Path) -> None:
    script = Path(__file__).resolve().parent / "blender" / "render_vertical_slice.py"
    frames_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            blender,
            "--background",
            "--python",
            str(script),
            "--",
            "--plan",
            str(plan_path),
            "--output-dir",
            str(frames_dir),
        ],
        check=True,
    )


def _assemble_video(ffmpeg: str, plan: dict, frames_dir: Path, output: Path, audio: Path | None) -> None:
    fps = str(plan["render"]["fps"])
    command = [
        ffmpeg,
        "-y",
        "-framerate",
        fps,
        "-start_number",
        "1",
        "-i",
        str(frames_dir / "frame_%04d.png"),
    ]
    if audio:
        command.extend(["-i", str(audio)])
    command.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"])
    if audio:
        command.extend(["-c:a", "aac", "-b:a", "160k", "-af", "apad"])
    command.extend(["-t", f"{plan['duration_seconds']:.3f}", "-movflags", "+faststart", str(output)])
    subprocess.run(command, check=True)


def _contact_sheet(ffmpeg: str, plan: dict, frames_dir: Path, output: Path) -> None:
    selected = []
    for shot in plan["shots"]:
        frame = (int(shot["frame_start"]) + int(shot["frame_end"])) // 2
        selected.append(frames_dir / f"frame_{frame:04d}.png")
    command = [ffmpeg, "-y"]
    for path in selected:
        command.extend(["-i", str(path)])
    labels = []
    filters = []
    for index in range(len(selected)):
        label = f"s{index}"
        labels.append(f"[{label}]")
        filters.append(f"[{index}:v]scale=480:-2[{label}]")
    filters.append("".join(labels) + f"hstack=inputs={len(selected)}[sheet]")
    command.extend(["-filter_complex", ";".join(filters), "-map", "[sheet]", "-frames:v", "1", str(output)])
    subprocess.run(command, check=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June Oxley's porch-dialogue cartoon proof")
    parser.add_argument("config")
    parser.add_argument("--audio")
    parser.add_argument("--cues", help="Existing Rhubarb JSON; generated from --audio when omitted")
    parser.add_argument("--rhubarb", default="rhubarb")
    parser.add_argument("--profiles", nargs="+", choices=("youtube", "portrait"), default=["youtube"])
    parser.add_argument("--quality", choices=("proof", "production"), default="proof")
    parser.add_argument("--output-dir", default="build/june-porch-vertical-slice")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    output_dir = Path(args.output_dir).resolve()
    plans_dir = output_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)

    audio = Path(args.audio).resolve() if args.audio else None
    cues_payload = None
    cues_path = Path(args.cues).resolve() if args.cues else output_dir / "june-mouth-cues.json"
    if args.cues:
        cues_payload = normalize_rhubarb(json.loads(cues_path.read_text(encoding="utf-8")))
    elif audio:
        cues_payload = run_rhubarb(
            audio,
            cues_path,
            dialogue=config["dialogue"]["text"],
            rhubarb_bin=_require_executable(args.rhubarb, "Rhubarb"),
        )

    compiled: dict[str, tuple[dict, Path]] = {}
    for profile in dict.fromkeys(args.profiles):
        plan = compile_plan(config, profile=profile, quality=args.quality, mouth_cues=cues_payload)
        plan_path = plans_dir / f"june-porch-{profile}.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        compiled[profile] = (plan, plan_path)

    if args.plan_only:
        print(f"Compiled {len(compiled)} plan(s) to {plans_dir}")
        return

    blender = _require_executable(args.blender, "Blender")
    ffmpeg = _require_executable(args.ffmpeg, "FFmpeg")
    manifest = {
        "production": config.get("production", "june-porch-dialogue"),
        "quality": args.quality,
        "audio": audio.name if audio else None,
        "outputs": [],
    }
    for profile, (plan, plan_path) in compiled.items():
        frames_dir = output_dir / "frames" / profile
        video = output_dir / f"june-porch-dialogue-{profile}.mp4"
        contact_sheet = output_dir / f"june-porch-dialogue-{profile}-contact-sheet.png"
        _render_frames(blender, plan_path, frames_dir)
        _assemble_video(ffmpeg, plan, frames_dir, video, audio)
        _contact_sheet(ffmpeg, plan, frames_dir, contact_sheet)
        manifest["outputs"].append(
            {
                "profile": profile,
                "width": plan["render"]["width"],
                "height": plan["render"]["height"],
                "fps": plan["render"]["fps"],
                "frames": plan["frame_end"],
                "video": video.name,
                "contact_sheet": contact_sheet.name,
            }
        )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {len(compiled)} profile(s) to {output_dir}")


if __name__ == "__main__":
    main()
