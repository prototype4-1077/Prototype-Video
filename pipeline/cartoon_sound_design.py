"""Generate an original deterministic room-tone and foley stem for a cartoon."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave
from typing import Any, Callable, Sequence

import numpy as np


EVENT_TYPES = {
    "room_tone",
    "chair_creak",
    "foot_plant",
    "paper_rustle",
    "pencil_tap",
    "breath",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _db(gain_db: float) -> float:
    return 10.0 ** (float(gain_db) / 20.0)


def _moving_average(signal: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return signal.astype(np.float64, copy=True)
    padded = np.pad(signal.astype(np.float64), (window, 0), mode="edge")
    cumulative = np.cumsum(padded, dtype=np.float64)
    return (cumulative[window:] - cumulative[:-window]) / window


def _envelope(size: int, attack: float = 0.15, release: float = 0.35) -> np.ndarray:
    envelope = np.ones(size, dtype=np.float64)
    attack_samples = max(1, round(size * attack))
    release_samples = max(1, round(size * release))
    envelope[:attack_samples] = np.sin(
        np.linspace(0.0, math.pi / 2.0, attack_samples)
    ) ** 2
    envelope[-release_samples:] *= np.cos(
        np.linspace(0.0, math.pi / 2.0, release_samples)
    ) ** 2
    return envelope


def _room_tone(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    soft = _moving_average(noise, max(8, sample_rate // 650))
    slow = _moving_average(noise, max(16, sample_rate // 180))
    time = np.arange(size, dtype=np.float64) / sample_rate
    electrical = 0.08 * np.sin(2.0 * math.pi * 60.0 * time + 0.3)
    return (0.72 * soft + 0.28 * slow + electrical) * _envelope(size, 0.02, 0.04)


def _chair_creak(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    progress = np.linspace(0.0, 1.0, size)
    frequency = 310.0 - 175.0 * progress + 18.0 * np.sin(2.0 * math.pi * 2.3 * time)
    phase = 2.0 * math.pi * np.cumsum(frequency) / sample_rate
    wood = np.sin(phase) + 0.34 * np.sin(2.03 * phase + 0.4)
    grain = _moving_average(rng.normal(0.0, 1.0, size), 9)
    return (0.86 * wood + 0.14 * grain) * _envelope(size, 0.12, 0.42)


def _foot_plant(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    phase = 2.0 * math.pi * (72.0 * time - 38.0 * time**2)
    body = np.sin(phase) * np.exp(-time * 12.0)
    contact = _moving_average(rng.normal(0.0, 1.0, size), 17) * np.exp(-time * 24.0)
    return (body + 0.38 * contact) * _envelope(size, 0.015, 0.55)


def _paper_rustle(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    high = noise - _moving_average(noise, max(3, sample_rate // 4000))
    time = np.arange(size, dtype=np.float64) / sample_rate
    flutter = 0.38 + 0.62 * np.sin(2.0 * math.pi * (7.0 * time + 5.0 * time**2)) ** 2
    return high * flutter * _envelope(size, 0.18, 0.38)


def _pencil_tap(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    ring = (
        np.sin(2.0 * math.pi * 1850.0 * time)
        + 0.45 * np.sin(2.0 * math.pi * 3170.0 * time)
    ) * np.exp(-time * 42.0)
    tick = rng.normal(0.0, 1.0, size) * np.exp(-time * 95.0)
    return (0.72 * ring + 0.28 * tick) * _envelope(size, 0.005, 0.75)


def _breath(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    soft = _moving_average(noise, max(3, sample_rate // 5400))
    low = _moving_average(noise, max(24, sample_rate // 700))
    return (soft - low) * _envelope(size, 0.38, 0.46)


SYNTHS: dict[str, Callable[[int, int, np.random.Generator], np.ndarray]] = {
    "room_tone": _room_tone,
    "chair_creak": _chair_creak,
    "foot_plant": _foot_plant,
    "paper_rustle": _paper_rustle,
    "pencil_tap": _pencil_tap,
    "breath": _breath,
}


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if int(profile.get("contract_version", 0)) != 1:
        raise ValueError("sound contract_version must be 1")
    duration = float(profile.get("duration_seconds", 0.0))
    sample_rate = int(profile.get("sample_rate", 0))
    if duration <= 0.0 or sample_rate < 8000:
        raise ValueError("sound duration and sample rate must be positive")
    if int(profile.get("channels", 0)) != 2:
        raise ValueError("sound design output must be stereo")
    if not isinstance(profile.get("seed"), int):
        raise ValueError("sound design seed must be an integer")
    events = profile.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("sound profile must contain events")
    identifiers: set[str] = set()
    for event in events:
        identifier = str(event.get("id", ""))
        if not identifier or identifier in identifiers:
            raise ValueError("sound event ids must be unique and non-empty")
        identifiers.add(identifier)
        if event.get("type") not in EVENT_TYPES:
            raise ValueError(f"unsupported sound event type: {event.get('type')}")
        start = float(event.get("time_seconds", -1.0))
        event_duration = float(event.get("duration_seconds", 0.0))
        if start < 0.0 or event_duration <= 0.0 or start + event_duration > duration + 1e-9:
            raise ValueError(f"sound event is outside the scene clock: {identifier}")
        pan = float(event.get("pan", 0.0))
        if not -1.0 <= pan <= 1.0:
            raise ValueError(f"sound event pan is outside [-1, 1]: {identifier}")
        gain = float(event.get("gain_db", 0.0))
        if not -80.0 <= gain <= 0.0:
            raise ValueError(f"sound event gain is outside [-80, 0] dB: {identifier}")
    mix = profile.get("mix")
    if not isinstance(mix, dict):
        raise ValueError("sound profile must contain mix settings")
    if int(mix.get("sample_rate", 0)) != sample_rate:
        raise ValueError("sound mix sample rate must match the stem")
    for key in ("dialogue_gain_db", "foley_gain_db"):
        value = float(mix.get(key, 0.0))
        if not -80.0 <= value <= 12.0:
            raise ValueError(f"sound mix {key} is outside [-80, 12] dB")
    limiter_peak = float(mix.get("limiter_peak", 0.0))
    if not 0.1 <= limiter_peak <= 1.0:
        raise ValueError("sound mix limiter_peak must be inside [0.1, 1.0]")
    return profile


def render_stem(profile: dict[str, Any]) -> np.ndarray:
    profile = validate_profile(profile)
    duration = float(profile["duration_seconds"])
    sample_rate = int(profile["sample_rate"])
    sample_count = round(duration * sample_rate)
    stem = np.zeros((sample_count, 2), dtype=np.float64)
    master_rng = np.random.default_rng(int(profile["seed"]))

    for event in profile["events"]:
        start = round(float(event["time_seconds"]) * sample_rate)
        size = round(float(event["duration_seconds"]) * sample_rate)
        seed = int(master_rng.integers(0, np.iinfo(np.int64).max))
        signal = SYNTHS[str(event["type"])](
            size, sample_rate, np.random.default_rng(seed)
        )
        peak = float(np.max(np.abs(signal)))
        if peak > 0.0:
            signal = signal / peak
        gain = _db(float(event["gain_db"]))
        pan = float(event.get("pan", 0.0))
        left = math.sqrt((1.0 - pan) / 2.0)
        right = math.sqrt((1.0 + pan) / 2.0)
        end = min(sample_count, start + size)
        stem[start:end, 0] += signal[: end - start] * gain * left
        stem[start:end, 1] += signal[: end - start] * gain * right

    target_peak = _db(float(profile.get("target_peak_dbfs", -12.0)))
    observed_peak = float(np.max(np.abs(stem)))
    if observed_peak > target_peak:
        stem *= target_peak / observed_peak
    return stem.astype(np.float32)


def write_wav(path: Path, stem: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(stem, -1.0, 1.0)
    pcm = np.round(pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(2)
        destination.setsampwidth(2)
        destination.setframerate(sample_rate)
        destination.writeframes(pcm.tobytes())


def _run(command: Sequence[str | Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        check=True,
        capture_output=True,
        text=True,
    )


def _probe_audio(ffprobe: str | Path, path: Path) -> dict[str, Any]:
    result = _run([
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,sample_rate,channels,duration:format=duration,size",
        "-of",
        "json",
        path,
    ])
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    if not streams:
        raise ValueError(f"audio stream missing: {path}")
    stream = streams[0]
    return {
        "codec": str(stream.get("codec_name") or ""),
        "sample_rate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "duration_seconds": float(
            stream.get("duration") or (payload.get("format") or {}).get("duration") or 0.0
        ),
        "bytes": int((payload.get("format") or {}).get("size") or path.stat().st_size),
    }


def mix_dialogue_and_foley(
    dialogue_source: Path,
    foley_stem: Path,
    output: Path,
    *,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
    sample_rate: int = 48000,
    limiter_peak: float = 0.95,
    dialogue_gain_db: float = 0.0,
    foley_gain_db: float = 0.0,
    expected_duration: float = 15.1,
) -> dict[str, Any]:
    if not dialogue_source.is_file() or not foley_stem.is_file():
        raise FileNotFoundError("dialogue source and foley stem must exist")
    if not 0.1 <= float(limiter_peak) <= 1.0:
        raise ValueError("limiter peak must be inside [0.1, 1.0]")
    output.parent.mkdir(parents=True, exist_ok=True)
    filter_graph = (
        f"[0:a:0]aresample={sample_rate},volume={float(dialogue_gain_db):.3f}dB[dialogue];"
        f"[1:a:0]aresample={sample_rate},volume={float(foley_gain_db):.3f}dB[foley];"
        "[dialogue][foley]"
        "amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        f"alimiter=limit={float(limiter_peak):.6f}:attack=5:release=50:level=disabled,"
        f"atrim=end={float(expected_duration):.9f},asetpts=N/SR/TB[mix]"
    )
    _run([
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-i",
        dialogue_source,
        "-i",
        foley_stem,
        "-filter_complex",
        filter_graph,
        "-map",
        "[mix]",
        "-c:a",
        "pcm_s24le",
        "-ar",
        str(sample_rate),
        "-ac",
        "2",
        output,
    ])
    contract = _probe_audio(ffprobe, output)
    if contract["sample_rate"] != sample_rate or contract["channels"] != 2:
        raise ValueError(f"mixed audio contract is invalid: {contract}")
    if abs(contract["duration_seconds"] - expected_duration) > 1.0 / sample_rate:
        raise ValueError(
            f"mixed audio duration {contract['duration_seconds']} does not match "
            f"{expected_duration}"
        )
    return {
        "dialogue_source": {
            "path": dialogue_source.name,
            "sha256": _sha256(dialogue_source),
        },
        "foley_stem": {"path": foley_stem.name, "sha256": _sha256(foley_stem)},
        "output": {"path": output.name, "sha256": _sha256(output), **contract},
        "limiter_peak": float(limiter_peak),
        "dialogue_gain_db": float(dialogue_gain_db),
        "foley_gain_db": float(foley_gain_db),
    }


def generate(profile_path: Path, output: Path, report_path: Path | None) -> dict[str, Any]:
    profile = validate_profile(json.loads(profile_path.read_text(encoding="utf-8")))
    stem = render_stem(profile)
    write_wav(output, stem, int(profile["sample_rate"]))
    report = {
        "contract_version": 1,
        "stage": "cartoon_sound_design",
        "sound_id": profile.get("sound_id"),
        "sound_version": profile.get("sound_version"),
        "profile": {"path": profile_path.name, "sha256": _sha256(profile_path)},
        "output": {
            "path": output.name,
            "sha256": _sha256(output),
            "sample_rate": int(profile["sample_rate"]),
            "channels": 2,
            "sample_count": len(stem),
            "duration_seconds": len(stem) / int(profile["sample_rate"]),
            "peak_dbfs": 20.0 * math.log10(max(float(np.max(np.abs(stem))), 1e-12)),
        },
        "event_count": len(profile["events"]),
        "events": [event["id"] for event in profile["events"]],
    }
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--dialogue-source", type=Path)
    parser.add_argument("--mixed-output", type=Path)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    profile = args.profile.resolve()
    if not profile.is_file():
        raise FileNotFoundError(f"sound profile not found: {profile}")
    if bool(args.dialogue_source) != bool(args.mixed_output):
        raise ValueError("dialogue-source and mixed-output must be supplied together")
    output = args.output.resolve()
    report = generate(profile, output, None)
    if args.dialogue_source:
        source = args.dialogue_source.resolve()
        mixed = args.mixed_output.resolve()
        profile_payload = json.loads(profile.read_text(encoding="utf-8"))
        mix_settings = profile_payload["mix"]
        report["mix"] = mix_dialogue_and_foley(
            source,
            output,
            mixed,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
            sample_rate=int(mix_settings["sample_rate"]),
            limiter_peak=float(mix_settings["limiter_peak"]),
            dialogue_gain_db=float(mix_settings["dialogue_gain_db"]),
            foley_gain_db=float(mix_settings["foley_gain_db"]),
            expected_duration=float(profile_payload["duration_seconds"]),
        )
    if args.report:
        report_path = args.report.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
