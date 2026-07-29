"""Generate an original deterministic room-tone and foley stem for a cartoon."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    profile = args.profile.resolve()
    if not profile.is_file():
        raise FileNotFoundError(f"sound profile not found: {profile}")
    report = generate(profile, args.output.resolve(), args.report.resolve() if args.report else None)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
