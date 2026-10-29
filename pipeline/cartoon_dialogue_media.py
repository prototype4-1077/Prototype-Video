"""Make cached, explicitly non-canonical dialogue with existing local tools only."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

from pipeline.cartoon_lipsync import run_rhubarb


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def executable(value: str) -> str:
    path = str(Path(value).resolve()) if Path(value).is_file() else shutil.which(value)
    if not path:
        raise FileNotFoundError(f"Local executable required; no download/service fallback: {value}")
    return path


def prepare(text: str, output: Path, *, piper: str, voice: Path, rhubarb: str) -> dict:
    if not text.strip():
        raise ValueError("Dialogue text is required")
    if output.exists():
        raise FileExistsError(f"Keep existing media: {output}")
    piper, rhubarb, ffmpeg = executable(piper), executable(rhubarb), executable("ffmpeg")
    ffprobe = executable("ffprobe")
    voice = voice.resolve()
    config = Path(str(voice) + ".json")
    if not voice.is_file() or not config.is_file():
        raise FileNotFoundError("Both local voice model and its JSON config are required")
    output.mkdir(parents=True)
    raw = output / "piper-raw.wav"
    subprocess.run([piper, "--model", str(voice), "--output_file", str(raw),
                    "--length_scale", "1.08", "--sentence_silence", "0.18", "--quiet"],
                   input=text.strip() + "\n", text=True, check=True)
    with wave.open(str(raw), "rb") as source:
        source_seconds = source.getnframes() / source.getframerate()
    lead, tail = .4, 1.0
    frames = math.ceil((lead + source_seconds + tail) * 30)
    duration = frames / 30
    audio = output / "dialogue.wav"
    subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-n", "-i", str(raw),
                    "-af", f"aresample=48000,afade=t=in:st=0:d=0.03,afade=t=out:st={max(0,source_seconds-.03):.9f}:d=0.03,adelay=400:all=1,apad,atrim=end_sample={frames*1600}",
                    "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", str(audio)], check=True)
    stream = json.loads(subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(audio)],
                                       check=True, capture_output=True).stdout)["streams"][0]
    if (stream["sample_rate"], stream["channels"]) != ("48000", 1) or Fraction(stream["duration_ts"]) * Fraction(stream["time_base"]) != Fraction(frames, 30):
        raise ValueError("Prepared audio does not have the exact 48kHz frame clock")
    cue_path = output / "rhubarb.json"
    payload = run_rhubarb(audio, cue_path, dialogue=text, rhubarb_bin=rhubarb)
    if abs(float(payload["metadata"]["duration"]) - duration) > .02:
        raise ValueError("Rhubarb audio duration drifted")
    for cue in payload["mouthCues"]:
        if float(cue["end"]) > duration + .02:
            raise ValueError("Cue extends beyond the sample clock")
        cue["end"] = min(float(cue["end"]), duration)
    payload["mouthCues"] = [cue for cue in payload["mouthCues"] if cue["end"] > cue["start"]]
    # Rhubarb's decimal duration is rounded; pin the exact sample/frame clock.
    payload["metadata"].update({"duration": duration, "sourceAudioSha256": sha(audio),
                                "dialogueHint": text, "voice_status": "NON_CANONICAL_LOCAL_SCRATCH_VOICE"})
    cue_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    report = {"dialogue": text, "frame_count": frames, "duration_seconds": duration,
              "audio_sample_count": frames * 1600, "lead_seconds": lead, "tail_seconds_minimum": tail,
              "voice_status": "NON_CANONICAL_LOCAL_SCRATCH_VOICE_NOT_HUMAN_ACCEPTED",
              "voice_model_sha256": sha(voice), "voice_config_sha256": sha(config),
              "piper_executable_sha256": sha(Path(piper)), "rhubarb_executable_sha256": sha(Path(rhubarb)),
              "audio_sha256": sha(audio), "cues_sha256": sha(cue_path), "raw_audio_sha256": sha(raw),
              "cash_cost": 0, "network_calls": 0, "speech_time_stretch_used": False,
              "accepted_original_scene_modified": False, "production_release_allowed": False}
    (output / "dialogue-media-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--piper", required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--rhubarb", required=True)
    args = parser.parse_args()
    prepare(args.text, args.output.resolve(), piper=args.piper, voice=args.voice, rhubarb=args.rhubarb)


if __name__ == "__main__":
    main()
