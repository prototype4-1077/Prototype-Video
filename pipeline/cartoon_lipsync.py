"""Rhubarb Lip Sync bridge for Blender cartoon renders.

Rhubarb emits timed mouth letters.  This module validates that output and
converts it to the repository's shared frame clock before Blender sees it.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Any


MOUTH_SHAPES = frozenset("ABCDEFGHX")


def _number(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def normalize_rhubarb(payload: dict, *, duration: float | None = None) -> dict:
    """Validate cues, fill silent gaps with ``X``, and merge equal neighbours."""
    if not isinstance(payload, dict):
        raise ValueError("Rhubarb payload must be an object")
    source_cues = payload.get("mouthCues", [])
    if not isinstance(source_cues, list):
        raise ValueError("mouthCues must be a list")

    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    if duration is None:
        duration = _number(metadata.get("duration", 0.0), "metadata.duration")
    else:
        duration = _number(duration, "duration")
    if duration < 0:
        raise ValueError("duration cannot be negative")

    parsed: list[dict] = []
    for index, cue in enumerate(source_cues):
        if not isinstance(cue, dict):
            raise ValueError(f"mouthCues[{index}] must be an object")
        start = _number(cue.get("start"), f"mouthCues[{index}].start")
        end = _number(cue.get("end"), f"mouthCues[{index}].end")
        shape = str(cue.get("value", "")).upper()
        if start < 0 or end <= start:
            raise ValueError(f"mouthCues[{index}] must have 0 <= start < end")
        if shape not in MOUTH_SHAPES:
            raise ValueError(f"mouthCues[{index}] has unsupported mouth shape {shape!r}")
        parsed.append({"start": start, "end": end, "value": shape})

    parsed.sort(key=lambda item: (item["start"], item["end"]))
    if parsed:
        duration = max(duration, parsed[-1]["end"])

    filled: list[dict] = []
    cursor = 0.0
    for index, cue in enumerate(parsed):
        if cue["start"] < cursor - 1e-6:
            raise ValueError(f"mouthCues overlap at sorted index {index}")
        if cue["start"] > cursor + 1e-6:
            filled.append({"start": cursor, "end": cue["start"], "value": "X"})
        filled.append(cue)
        cursor = cue["end"]
    if duration > cursor + 1e-6:
        filled.append({"start": cursor, "end": duration, "value": "X"})
    if not filled and duration > 0:
        filled.append({"start": 0.0, "end": duration, "value": "X"})

    merged: list[dict] = []
    for cue in filled:
        if merged and merged[-1]["value"] == cue["value"] and abs(merged[-1]["end"] - cue["start"]) <= 1e-6:
            merged[-1]["end"] = cue["end"]
        else:
            merged.append(dict(cue))

    return {
        "metadata": {**metadata, "duration": duration},
        "mouthCues": merged,
    }


def cues_to_frames(payload: dict, *, fps: int, duration: float | None = None) -> list[dict]:
    """Convert second-based Rhubarb cues into inclusive one-based frame spans."""
    if int(fps) <= 0:
        raise ValueError("fps must be positive")
    normalized = normalize_rhubarb(payload, duration=duration)
    total_frames = max(1, round(float(normalized["metadata"]["duration"]) * int(fps)))
    result = []
    for cue in normalized["mouthCues"]:
        frame_start = min(total_frames, max(1, math.floor(cue["start"] * fps) + 1))
        frame_end = min(total_frames, max(frame_start, math.ceil(cue["end"] * fps)))
        result.append(
            {
                "frame_start": frame_start,
                "frame_end": frame_end,
                "shape": cue["value"],
                "start": cue["start"],
                "end": cue["end"],
            }
        )
    return result


def run_rhubarb(
    audio_path: str | Path,
    output_path: str | Path,
    *,
    dialogue: str,
    rhubarb_bin: str | Path = "rhubarb",
) -> dict:
    """Run Rhubarb with a dialogue hint and return normalized JSON output."""
    audio = Path(audio_path)
    output = Path(output_path)
    if not audio.is_file():
        raise FileNotFoundError(f"audio not found: {audio}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cartoon-rhubarb-") as temp_dir:
        dialogue_path = Path(temp_dir) / "dialogue.txt"
        dialogue_path.write_text(dialogue.strip() + "\n", encoding="utf-8")
        command = [
            str(rhubarb_bin),
            "-f",
            "json",
            "-o",
            str(output),
            "-d",
            str(dialogue_path),
            str(audio),
        ]
        subprocess.run(command, check=True)
    payload = normalize_rhubarb(json.loads(output.read_text(encoding="utf-8")))
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate validated Rhubarb mouth cues")
    parser.add_argument("audio")
    parser.add_argument("output")
    parser.add_argument("--dialog-file", required=True)
    parser.add_argument("--rhubarb", default="rhubarb")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dialogue = Path(args.dialog_file).read_text(encoding="utf-8")
    run_rhubarb(args.audio, args.output, dialogue=dialogue, rhubarb_bin=args.rhubarb)


if __name__ == "__main__":
    main()
