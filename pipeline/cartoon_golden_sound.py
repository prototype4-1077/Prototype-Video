"""Build the exact-clock June Golden Scene dialogue, Foley, ambience, and delivery mix."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Sequence
import wave

import numpy as np


CONTRACT_VERSION = 1
SHOT_SPANS = {
    "GS010": (1, 129),
    "GS020": (130, 225),
    "GS030": (226, 396),
    "GS040": (397, 564),
    "GS050": (565, 678),
    "GS060": (679, 936),
    "GS070": (937, 1164),
}
STEM_CHANNELS = {
    "DX_JUNE_MONO": 1,
    "FOLEY_PROP_MONO": 1,
    "FOLEY_BODY_STEREO": 2,
    "AMB_PORCH_STEREO": 2,
    "MUSIC_EMPTY": 2,
    "MIX_PREMASTER_STEREO": 2,
    "MIX_MASTER_STEREO": 2,
}
EVENT_TYPES = {
    "porch_ambience",
    "wind_chime",
    "chair_creak",
    "cloth_rustle",
    "boot_plant",
    "breath",
    "mug_rub",
    "mug_place",
    "mug_slide",
    "ledger_rustle",
    "pencil_contact",
    "coffee_pot",
    "coffee_pour",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _asset_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else _repo_root() / path


def _resolve_executable(value: str | Path) -> str:
    candidate = Path(value)
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(str(value))
    if not resolved:
        raise FileNotFoundError(f"executable not found: {value}")
    return resolved


def _run(command: Sequence[str | Path], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(part) for part in command],
        input=input_text,
        check=True,
        capture_output=True,
        text=True,
    )


def _db(value: float) -> float:
    return 10.0 ** (float(value) / 20.0)


def load_sound_contract(
    path: str | Path,
    *,
    require_dialogue_source: bool = True,
) -> tuple[dict[str, Any], Path | None]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if int(contract.get("contract_version", 0)) != CONTRACT_VERSION:
        raise ValueError(f"sound contract_version must be {CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("Golden Scene sound must explicitly target June Oxley")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0 or generation.get("paid_runtime_dependency") is not False:
        raise ValueError("Golden Scene sound must preserve the zero-cash contract")
    if generation.get("music") != "none_intentional":
        raise ValueError("the Golden Scene intentionally has no music")

    master = contract.get("master") or {}
    expected_master = (1920, 1080, 30, 1164, 38.8, 48000, 1600, 1862400, 2)
    actual_master = (
        int(master.get("width", 0)),
        int(master.get("height", 0)),
        int(master.get("fps", 0)),
        int(master.get("frame_count", 0)),
        float(master.get("duration_seconds", 0.0)),
        int(master.get("sample_rate", 0)),
        int(master.get("samples_per_frame", 0)),
        int(master.get("sample_count", 0)),
        int(master.get("channels", 0)),
    )
    if actual_master != expected_master:
        raise ValueError("sound master must be exactly 1920x1080/30/1164/38.8/48k")
    if master.get("picture_gate") != "exact_1164_frame_golden_scene_picture_master":
        raise ValueError("sound contract must consume the exact picture-lock gate")

    voice = contract.get("voice") or {}
    if voice.get("engine") != "Piper" or voice.get("dataset_license") != "public domain":
        raise ValueError("release-candidate voice must be local Piper from a public-domain dataset")
    if voice.get("trained_from_scratch") is not True:
        raise ValueError("voice model must be declared trained from scratch")
    for key in ("model_sha256", "config_sha256", "model_card_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(voice.get(key, ""))):
            raise ValueError(f"voice {key} must be a SHA-256 digest")
    source_spec = voice.get("source") or {}
    if (
        int(source_spec.get("sample_rate", 0)),
        int(source_spec.get("channels", 0)),
        int(source_spec.get("sample_count", 0)),
    ) != (48000, 1, 1862400):
        raise ValueError("dialogue source must be exact-clock 48k mono")
    dialogue_source = _asset_path(str(source_spec.get("path", "")))
    expected_source_hash = str(source_spec.get("sha256", ""))
    if require_dialogue_source:
        if not dialogue_source.is_file():
            raise FileNotFoundError(f"dialogue source missing: {dialogue_source}")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_source_hash):
            raise ValueError("dialogue source SHA-256 is not pinned")
        if _sha256(dialogue_source) != expected_source_hash:
            raise ValueError("dialogue source hash does not match its contract")
    else:
        dialogue_source = dialogue_source if dialogue_source.is_file() else None

    cues = contract.get("dialogue_cues") or []
    if len(cues) != 18:
        raise ValueError("Golden Scene sound must contain eighteen phrase-level dialogue cues")
    cue_ids: set[str] = set()
    previous_end = 0
    for cue in cues:
        identifier = str(cue.get("id", ""))
        if not identifier or identifier in cue_ids:
            raise ValueError("dialogue cue ids must be unique and non-empty")
        cue_ids.add(identifier)
        shot_id = str(cue.get("shot_id", ""))
        if shot_id not in SHOT_SPANS:
            raise ValueError(f"dialogue cue has invalid shot: {identifier}")
        start, end = int(cue.get("start_frame", 0)), int(cue.get("end_frame", 0))
        shot_start, shot_end = SHOT_SPANS[shot_id]
        if start <= previous_end or start < shot_start or end < start or end > shot_end:
            raise ValueError(f"dialogue cue is not ordered inside its shot: {identifier}")
        if not str(cue.get("text", "")).strip():
            raise ValueError(f"dialogue cue has no text: {identifier}")
        if not -12.0 <= float(cue.get("gain_db", 0.0)) <= 6.0:
            raise ValueError(f"dialogue cue gain is outside the performance range: {identifier}")
        previous_end = end

    stems = contract.get("stems") or []
    actual_stems = {str(stem.get("id")): int(stem.get("channels", 0)) for stem in stems}
    if actual_stems != STEM_CHANNELS:
        raise ValueError("Golden Scene sound stem contract is incomplete")

    events = contract.get("events") or []
    event_ids: set[str] = set()
    for event in events:
        identifier = str(event.get("id", ""))
        if not identifier or identifier in event_ids:
            raise ValueError("sound event ids must be unique and non-empty")
        event_ids.add(identifier)
        if event.get("stem") not in {"FOLEY_PROP_MONO", "FOLEY_BODY_STEREO", "AMB_PORCH_STEREO"}:
            raise ValueError(f"sound event has invalid stem: {identifier}")
        if event.get("type") not in EVENT_TYPES:
            raise ValueError(f"unsupported sound event type: {event.get('type')}")
        start, end = int(event.get("start_frame", 0)), int(event.get("end_frame", 0))
        if start < 1 or end < start or end > 1164:
            raise ValueError(f"sound event is outside the master clock: {identifier}")
        if not -80.0 <= float(event.get("gain_db", 0.0)) <= 0.0:
            raise ValueError(f"sound event gain is invalid: {identifier}")
        if not -1.0 <= float(event.get("pan", 0.0)) <= 1.0:
            raise ValueError(f"sound event pan is invalid: {identifier}")
    required = contract.get("required_foley") or {}
    expected_required = {
        "mug_thumb_rub",
        "mug_place_and_slide",
        "chair_creak",
        "clothing",
        "boot_plant",
        "ledger",
        "pencil",
        "coffee_pot",
        "coffee_pour",
    }
    if set(required) != expected_required:
        raise ValueError("required Foley map is incomplete")
    for category, identifiers in required.items():
        if not identifiers or any(identifier not in event_ids for identifier in identifiers):
            raise ValueError(f"required Foley category is not backed by events: {category}")

    mix = contract.get("mix") or {}
    if not math.isclose(float(mix.get("target_lufs_i", 0.0)), -16.0):
        raise ValueError("master loudness target must be -16 LUFS-I")
    if not math.isclose(float(mix.get("true_peak_dbtp_max", 0.0)), -1.0):
        raise ValueError("master true-peak ceiling must be -1 dBTP")
    if not 0.1 <= float(mix.get("aac_true_peak_headroom_db", 0.0)) <= 1.0:
        raise ValueError("AAC true-peak headroom must be between 0.1 and 1.0 dB")
    if [float(value) for value in mix.get("accepted_lra_lu", [])] != [4.0, 8.0]:
        raise ValueError("master LRA acceptance window must be 4-8 LU")
    delivery = contract.get("delivery") or {}
    if delivery.get("picture_reencode_allowed") is not False:
        raise ValueError("sound delivery must prohibit picture re-encoding")
    if delivery.get("captions") != "soft_mov_text_plus_sidecar_srt":
        raise ValueError("sound delivery must add captions after picture and mix")
    return contract, dialogue_source


def _moving_average(signal: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return signal.astype(np.float64, copy=True)
    values = signal.astype(np.float64, copy=False)
    window = min(window, len(values))
    left = window // 2
    right = window - 1 - left
    padded = np.pad(values, (left, right), mode="edge")
    cumulative = np.cumsum(np.concatenate(([0.0], padded)), dtype=np.float64)
    return (cumulative[window:] - cumulative[:-window]) / window


def _envelope(size: int, attack: float = 0.08, release: float = 0.25) -> np.ndarray:
    result = np.ones(size, dtype=np.float64)
    attack_samples = min(size, max(1, round(size * attack)))
    release_samples = min(size, max(1, round(size * release)))
    result[:attack_samples] *= np.sin(np.linspace(0.0, math.pi / 2.0, attack_samples)) ** 2
    result[-release_samples:] *= np.cos(np.linspace(0.0, math.pi / 2.0, release_samples)) ** 2
    return result


def _colored_noise(size: int, rng: np.random.Generator, window: int) -> np.ndarray:
    raw = rng.normal(0.0, 1.0, size)
    return _moving_average(raw, max(1, window))


def _porch_ambience(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    wind = 0.58 * _colored_noise(size, rng, 96) + 0.20 * _colored_noise(size, rng, 900)
    leaves = rng.normal(0.0, 1.0, size) - _colored_noise(size, rng, 14)
    gust = 0.55 + 0.45 * np.sin(2.0 * math.pi * time / 7.9 + 0.4) ** 2
    cicada_gate = np.clip(np.sin(2.0 * math.pi * 6.7 * time) * 3.5, 0.0, 1.0)
    cicada = (rng.normal(0.0, 1.0, size) - _colored_noise(size, rng, 5)) * cicada_gate
    return (wind * gust + 0.075 * leaves + 0.018 * cicada) * _envelope(size, 0.02, 0.04)


def _wind_chime(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    result = np.zeros(size, dtype=np.float64)
    for index, frequency in enumerate((523.25, 659.25, 783.99, 987.77)):
        onset = min(size - 1, round((0.04 + index * 0.13 + rng.uniform(0.0, 0.035)) * sample_rate))
        local = time[: size - onset]
        decay = np.exp(-local * (2.9 + index * 0.28))
        partial = np.sin(2.0 * math.pi * frequency * local + rng.uniform(0.0, math.tau))
        partial += 0.28 * np.sin(2.0 * math.pi * frequency * 2.71 * local + 0.3)
        result[onset:] += partial * decay * (0.82 - index * 0.08)
    return result * _envelope(size, 0.015, 0.45)


def _chair_creak(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    progress = np.linspace(0.0, 1.0, size)
    frequency = 270.0 - 135.0 * progress + 16.0 * np.sin(math.tau * 2.2 * time)
    phase = math.tau * np.cumsum(frequency) / sample_rate
    grain = _colored_noise(size, rng, 11)
    return (np.sin(phase) + 0.31 * np.sin(2.07 * phase) + 0.12 * grain) * _envelope(size, 0.09, 0.44)


def _cloth_rustle(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    high = noise - _colored_noise(size, rng, max(3, sample_rate // 3500))
    time = np.arange(size, dtype=np.float64) / sample_rate
    flutter = 0.35 + 0.65 * np.sin(math.tau * (6.0 * time + 3.5 * time**2)) ** 2
    return high * flutter * _envelope(size, 0.12, 0.35)


def _boot_plant(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    thump = np.sin(math.tau * (74.0 * time - 36.0 * time**2)) * np.exp(-time * 14.0)
    leather = np.sin(math.tau * (620.0 - 210.0 * time) * time) * np.exp(-time * 18.0)
    dust = _colored_noise(size, rng, 15) * np.exp(-time * 24.0)
    return (thump + 0.19 * leather + 0.32 * dust) * _envelope(size, 0.012, 0.6)


def _breath(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    airy = _colored_noise(size, rng, 3) - _colored_noise(size, rng, 48)
    return (0.72 * airy + 0.08 * noise) * _envelope(size, 0.32, 0.43)


def _mug_rub(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    friction = noise - _colored_noise(size, rng, 12)
    time = np.arange(size, dtype=np.float64) / sample_rate
    pulses = 0.32 + 0.68 * np.sin(math.tau * 7.1 * time) ** 2
    enamel = 0.08 * np.sin(math.tau * 1280.0 * time) * np.exp(-time * 3.2)
    return (friction * pulses + enamel) * _envelope(size, 0.16, 0.25)


def _mug_place(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    ring = sum(
        weight * np.sin(math.tau * frequency * time + phase) * np.exp(-time * decay)
        for frequency, weight, decay, phase in (
            (880.0, 1.0, 15.0, 0.0),
            (1710.0, 0.44, 22.0, 0.3),
            (2530.0, 0.20, 29.0, 0.6),
        )
    )
    wood = _colored_noise(size, rng, 22) * np.exp(-time * 30.0)
    return (ring + 0.42 * wood) * _envelope(size, 0.008, 0.72)


def _mug_slide(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    scrape = noise - _colored_noise(size, rng, 9)
    time = np.arange(size, dtype=np.float64) / sample_rate
    chatter = 0.45 + 0.55 * np.sin(math.tau * 18.0 * time) ** 4
    return scrape * chatter * _envelope(size, 0.08, 0.22)


def _ledger_rustle(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    noise = rng.normal(0.0, 1.0, size)
    paper = noise - _colored_noise(size, rng, max(3, sample_rate // 4200))
    time = np.arange(size, dtype=np.float64) / sample_rate
    flutter = 0.25 + 0.75 * np.sin(math.tau * (8.5 * time + 4.0 * time**2)) ** 2
    cover = 0.09 * np.sin(math.tau * 190.0 * time) * np.exp(-time * 8.0)
    return (paper * flutter + cover) * _envelope(size, 0.14, 0.3)


def _pencil_contact(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    tick = rng.normal(0.0, 1.0, size) * np.exp(-time * 95.0)
    wood = (np.sin(math.tau * 1740.0 * time) + 0.36 * np.sin(math.tau * 3210.0 * time)) * np.exp(-time * 44.0)
    scratch = (rng.normal(0.0, 1.0, size) - _colored_noise(size, rng, 7)) * np.exp(-time * 9.0)
    return (0.34 * tick + 0.56 * wood + 0.10 * scratch) * _envelope(size, 0.006, 0.72)


def _coffee_pot(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    metal = (
        np.sin(math.tau * 690.0 * time)
        + 0.43 * np.sin(math.tau * 1370.0 * time + 0.2)
        + 0.20 * np.sin(math.tau * 2410.0 * time + 0.5)
    ) * np.exp(-time * 18.0)
    handle = _colored_noise(size, rng, 13) * np.exp(-time * 12.0)
    return (metal + 0.24 * handle) * _envelope(size, 0.01, 0.62)


def _coffee_pour(size: int, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / sample_rate
    noise = rng.normal(0.0, 1.0, size)
    liquid = _colored_noise(size, rng, 4) - _colored_noise(size, rng, 33)
    burble = 0.42 + 0.58 * np.sin(math.tau * (15.0 * time + 1.8 * np.sin(math.tau * 1.3 * time))) ** 2
    droplets = np.zeros(size, dtype=np.float64)
    count = max(2, round(size / sample_rate * 7.0))
    for onset in rng.integers(0, max(1, size - 1), count):
        length = min(size - onset, round(sample_rate * 0.055))
        local = np.arange(length, dtype=np.float64) / sample_rate
        droplets[onset : onset + length] += np.sin(math.tau * rng.uniform(650.0, 1050.0) * local) * np.exp(-local * 70.0)
    return (liquid * burble + 0.12 * noise + 0.22 * droplets) * _envelope(size, 0.18, 0.24)


SYNTHS = {
    "porch_ambience": _porch_ambience,
    "wind_chime": _wind_chime,
    "chair_creak": _chair_creak,
    "cloth_rustle": _cloth_rustle,
    "boot_plant": _boot_plant,
    "breath": _breath,
    "mug_rub": _mug_rub,
    "mug_place": _mug_place,
    "mug_slide": _mug_slide,
    "ledger_rustle": _ledger_rustle,
    "pencil_contact": _pencil_contact,
    "coffee_pot": _coffee_pot,
    "coffee_pour": _coffee_pour,
}


def render_procedural_stems(contract: dict[str, Any]) -> dict[str, np.ndarray]:
    sample_rate = int(contract["master"]["sample_rate"])
    samples_per_frame = int(contract["master"]["samples_per_frame"])
    sample_count = int(contract["master"]["sample_count"])
    stems = {
        "FOLEY_PROP_MONO": np.zeros((sample_count, 1), dtype=np.float64),
        "FOLEY_BODY_STEREO": np.zeros((sample_count, 2), dtype=np.float64),
        "AMB_PORCH_STEREO": np.zeros((sample_count, 2), dtype=np.float64),
        "MUSIC_EMPTY": np.zeros((sample_count, 2), dtype=np.float64),
    }
    master_rng = np.random.default_rng(int(contract["mix"]["seed"]))
    for event in contract["events"]:
        start = (int(event["start_frame"]) - 1) * samples_per_frame
        size = (int(event["end_frame"]) - int(event["start_frame"]) + 1) * samples_per_frame
        event_rng = np.random.default_rng(int(master_rng.integers(0, 2**32 - 1)))
        signal = SYNTHS[str(event["type"])](size, sample_rate, event_rng)
        peak = max(float(np.max(np.abs(signal))), 1e-12)
        signal = signal / peak * _db(float(event["gain_db"]))
        end = min(sample_count, start + size)
        signal = signal[: end - start]
        destination = stems[str(event["stem"])]
        if destination.shape[1] == 1:
            destination[start:end, 0] += signal
        else:
            pan = float(event.get("pan", 0.0))
            destination[start:end, 0] += signal * math.sqrt((1.0 - pan) / 2.0)
            destination[start:end, 1] += signal * math.sqrt((1.0 + pan) / 2.0)
    return {name: stem.astype(np.float32) for name, stem in stems.items()}


def _write_pcm24(path: Path, signal: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    signal = np.asarray(signal, dtype=np.float64)
    if signal.ndim == 1:
        signal = signal[:, None]
    integers = np.round(np.clip(signal, -1.0, 1.0) * 8388607.0).astype(np.int32)
    unsigned = integers.reshape(-1).astype(np.int64) & 0xFFFFFF
    packed = np.empty((unsigned.size, 3), dtype=np.uint8)
    packed[:, 0] = unsigned & 0xFF
    packed[:, 1] = (unsigned >> 8) & 0xFF
    packed[:, 2] = (unsigned >> 16) & 0xFF
    with wave.open(str(path), "wb") as destination:
        destination.setnchannels(signal.shape[1])
        destination.setsampwidth(3)
        destination.setframerate(sample_rate)
        destination.writeframes(packed.tobytes())


def _read_audio_f32(ffmpeg: str, path: Path, *, channels: int, sample_rate: int) -> np.ndarray:
    completed = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-",
        ],
        check=True,
        capture_output=True,
    )
    data = np.frombuffer(completed.stdout, dtype="<f4")
    if data.size % channels:
        raise ValueError(f"decoded audio has incomplete sample frames: {path}")
    return data.reshape(-1, channels).copy()


def _audio_probe(ffprobe: str, path: Path) -> dict[str, Any]:
    completed = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,channel_layout,duration:format=duration,size",
            "-of",
            "json",
            path,
        ]
    )
    payload = json.loads(completed.stdout)
    streams = payload.get("streams") or []
    if not streams:
        raise ValueError(f"audio stream is missing: {path}")
    stream = streams[0]
    return {
        "codec": str(stream.get("codec_name") or ""),
        "sample_rate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "channel_layout": str(stream.get("channel_layout") or ""),
        "duration_seconds": float(stream.get("duration") or payload["format"]["duration"]),
        "bytes": int(payload["format"].get("size") or path.stat().st_size),
    }


def build_dialogue_source(
    contract_path: str | Path,
    output: str | Path,
    *,
    piper: str | Path,
    model: str | Path,
    config: str | Path,
    model_card: str | Path,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
    work_dir: str | Path | None = None,
) -> dict[str, Any]:
    contract, _ = load_sound_contract(contract_path, require_dialogue_source=False)
    piper_bin = _resolve_executable(piper)
    ffmpeg_bin = _resolve_executable(ffmpeg)
    ffprobe_bin = _resolve_executable(ffprobe)
    model_path, config_path, card_path = Path(model).resolve(), Path(config).resolve(), Path(model_card).resolve()
    for path, key in (
        (model_path, "model_sha256"),
        (config_path, "config_sha256"),
        (card_path, "model_card_sha256"),
    ):
        if not path.is_file() or _sha256(path) != contract["voice"][key]:
            raise ValueError(f"Piper voice dependency failed its hash gate: {path}")
    card_text = card_path.read_text(encoding="utf-8")
    if "License: public domain" not in card_text or "Trained from scratch" not in card_text:
        raise ValueError("Piper model card does not prove the required public-domain source")

    sample_rate = int(contract["master"]["sample_rate"])
    samples_per_frame = int(contract["master"]["samples_per_frame"])
    sample_count = int(contract["master"]["sample_count"])
    voice = contract["voice"]
    dialogue = np.zeros(sample_count, dtype=np.float64)
    generated: list[dict[str, Any]] = []
    root = Path(work_dir).resolve() if work_dir else None
    temporary_owner = tempfile.TemporaryDirectory(prefix="june-golden-dialogue-") if root is None else None
    temporary = Path(temporary_owner.name if temporary_owner else root)
    temporary.mkdir(parents=True, exist_ok=True)
    try:
        for cue in contract["dialogue_cues"]:
            cue_id = str(cue["id"]).lower()
            raw = temporary / f"{cue_id}-raw.wav"
            fitted = temporary / f"{cue_id}-fitted.wav"
            _run(
                [
                    piper_bin,
                    "--model",
                    model_path,
                    "--config",
                    config_path,
                    "--output_file",
                    raw,
                    "--noise_scale",
                    voice["noise_scale"],
                    "--noise_w",
                    voice["noise_w"],
                    "--sentence_silence",
                    voice["sentence_silence_seconds"],
                    "--quiet",
                ],
                input_text=str(cue["text"]).strip() + "\n",
            )
            raw_duration = _audio_probe(ffprobe_bin, raw)["duration_seconds"]
            target_samples = (int(cue["end_frame"]) - int(cue["start_frame"]) + 1) * samples_per_frame
            target_duration = target_samples / sample_rate
            tempo = raw_duration / target_duration
            if not 0.65 <= tempo <= 1.55:
                raise ValueError(f"dialogue phrase requires unsafe time fitting: {cue['id']} {tempo:.3f}x")
            fade = float(voice["phrase_edge_fade_seconds"])
            filters = (
                f"atempo={tempo:.9f},aresample={sample_rate},"
                "highpass=f=70,lowpass=f=10800,"
                "equalizer=f=165:t=q:w=1.0:g=1.4,"
                "equalizer=f=3100:t=q:w=1.2:g=1.1,"
                f"apad=whole_dur={target_duration:.9f},atrim=end={target_duration:.9f},"
                f"afade=t=in:st=0:d={fade:.6f},"
                f"afade=t=out:st={max(0.0, target_duration - fade):.6f}:d={fade:.6f}"
            )
            _run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    raw,
                    "-af",
                    filters,
                    "-c:a",
                    "pcm_s16le",
                    "-ar",
                    sample_rate,
                    "-ac",
                    1,
                    fitted,
                ]
            )
            phrase = _read_audio_f32(ffmpeg_bin, fitted, channels=1, sample_rate=sample_rate)[:, 0]
            if len(phrase) < target_samples:
                phrase = np.pad(phrase, (0, target_samples - len(phrase)))
            phrase = phrase[:target_samples]
            active = phrase[np.abs(phrase) > 1e-5]
            rms = math.sqrt(float(np.mean(active**2))) if active.size else 0.0
            if rms <= 1e-9:
                raise ValueError(f"Piper produced an empty dialogue phrase: {cue['id']}")
            phrase *= _db(float(voice["phrase_rms_dbfs"])) / rms
            phrase_peak = float(np.max(np.abs(phrase)))
            if phrase_peak > _db(-3.0):
                phrase *= _db(-3.0) / phrase_peak
            start_sample = (int(cue["start_frame"]) - 1) * samples_per_frame
            dialogue[start_sample : start_sample + target_samples] += phrase
            generated.append(
                {
                    "id": cue["id"],
                    "text": cue["text"],
                    "start_frame": cue["start_frame"],
                    "end_frame": cue["end_frame"],
                    "raw_duration_seconds": round(raw_duration, 6),
                    "target_duration_seconds": round(target_duration, 6),
                    "atempo": round(tempo, 6),
                }
            )
    finally:
        if temporary_owner is not None:
            temporary_owner.cleanup()

    output_path = Path(output).resolve()
    _write_pcm24(output_path, dialogue[:, None], sample_rate)
    probe = _audio_probe(ffprobe_bin, output_path)
    if probe["sample_rate"] != 48000 or probe["channels"] != 1 or not math.isclose(probe["duration_seconds"], 38.8, abs_tol=1 / 48000):
        raise ValueError(f"dialogue source failed its exact audio contract: {probe}")
    return {
        "gate": "exact_frame_locked_public_domain_piper_dialogue",
        "output": {"path": output_path.name, "sha256": _sha256(output_path), **probe},
        "model": {
            "name": voice["voice"],
            "sha256": _sha256(model_path),
            "config_sha256": _sha256(config_path),
            "model_card_sha256": _sha256(card_path),
            "dataset": voice["dataset"],
            "dataset_license": voice["dataset_license"],
            "trained_from_scratch": voice["trained_from_scratch"],
        },
        "phrase_count": len(generated),
        "phrase_edge_fade_seconds": voice["phrase_edge_fade_seconds"],
        "phrases": generated,
    }


def _format_srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000.0)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def write_captions(contract: dict[str, Any], path: Path) -> None:
    fps = int(contract["master"]["fps"])
    blocks: list[str] = []
    for index, cue in enumerate(contract["dialogue_cues"], start=1):
        start = (int(cue["start_frame"]) - 1) / fps
        end = int(cue["end_frame"]) / fps
        blocks.append(
            f"{index}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{cue['text']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _json_from_ffmpeg(stderr: str) -> dict[str, Any]:
    matches = re.findall(r"\{\s*\"input_i\".*?\}", stderr, flags=re.DOTALL)
    if not matches:
        raise RuntimeError(f"FFmpeg loudnorm JSON was not found:\n{stderr[-2000:]}")
    return json.loads(matches[-1])


def _loudnorm_measure(ffmpeg: str, path: Path, *, target_i: float, target_lra: float, target_tp: float) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            f"loudnorm=I={target_i}:LRA={target_lra}:TP={target_tp}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return _json_from_ffmpeg(result.stderr)


def _stream_hash(ffmpeg: str, path: Path, selector: str) -> str:
    result = _run([ffmpeg, "-v", "error", "-i", path, "-map", selector, "-c", "copy", "-f", "hash", "-hash", "sha256", "-"])
    match = re.search(r"SHA256=([0-9a-f]{64})", result.stdout)
    if not match:
        raise RuntimeError(f"unable to hash stream {selector} in {path}")
    return match.group(1)


def _video_probe(ffprobe: str, path: Path) -> dict[str, Any]:
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,pix_fmt,width,height,r_frame_rate,nb_frames,sample_rate,channels:format=duration",
            "-of",
            "json",
            path,
        ]
    )
    return json.loads(result.stdout)


def render_sound_master(
    contract_path: str | Path,
    picture_video: str | Path,
    picture_report: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
) -> dict[str, Any]:
    contract, dialogue_path = load_sound_contract(contract_path, require_dialogue_source=True)
    assert dialogue_path is not None
    ffmpeg_bin, ffprobe_bin = _resolve_executable(ffmpeg), _resolve_executable(ffprobe)
    picture = Path(picture_video).resolve()
    report_path = Path(picture_report).resolve()
    if not picture.is_file() or not report_path.is_file():
        raise FileNotFoundError("picture-lock video and report are required")
    picture_contract = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        picture_contract.get("gate") != contract["master"]["picture_gate"]
        or int(picture_contract.get("frame_count", 0)) != 1164
        or float(picture_contract.get("duration_seconds", 0.0)) != 38.8
    ):
        raise ValueError("sound master input is not the exact Golden Scene picture lock")

    output = Path(output_dir).resolve()
    stems_dir = output / "stems"
    stems_dir.mkdir(parents=True, exist_ok=True)
    sample_rate = int(contract["master"]["sample_rate"])
    sample_count = int(contract["master"]["sample_count"])
    dialogue = _read_audio_f32(ffmpeg_bin, dialogue_path, channels=1, sample_rate=sample_rate)
    if dialogue.shape != (sample_count, 1):
        raise ValueError(f"dialogue stem does not match exact sample clock: {dialogue.shape}")
    stems = render_procedural_stems(contract)
    stems["DX_JUNE_MONO"] = dialogue.astype(np.float32)

    stem_files: dict[str, Path] = {}
    for stem_id in ("DX_JUNE_MONO", "FOLEY_PROP_MONO", "FOLEY_BODY_STEREO", "AMB_PORCH_STEREO", "MUSIC_EMPTY"):
        path = stems_dir / f"{stem_id}.wav"
        _write_pcm24(path, stems[stem_id], sample_rate)
        stem_files[stem_id] = path

    dx = dialogue[:, 0].astype(np.float64)
    dx_performed = dx.copy()
    samples_per_frame = int(contract["master"]["samples_per_frame"])
    for cue in contract["dialogue_cues"]:
        start = (int(cue["start_frame"]) - 1) * samples_per_frame
        end = int(cue["end_frame"]) * samples_per_frame
        dx_performed[start:end] *= _db(float(cue.get("gain_db", 0.0)))
    prop = stems["FOLEY_PROP_MONO"][:, 0].astype(np.float64)
    body = stems["FOLEY_BODY_STEREO"].astype(np.float64)
    ambience = stems["AMB_PORCH_STEREO"].astype(np.float64)
    mix = contract["mix"]
    activity = _moving_average(np.abs(dx_performed), max(1, round(sample_rate * 0.12)))
    activity /= max(float(np.percentile(activity, 95.0)), 1e-9)
    activity = np.clip(activity, 0.0, 1.0)
    amb_duck = 1.0 - activity * (1.0 - _db(float(mix["dialogue_ambience_duck_db"])))
    body_duck = 1.0 - activity * (1.0 - _db(float(mix["dialogue_body_duck_db"])))
    premaster = np.column_stack([dx_performed, dx_performed]) * _db(float(mix["dialogue_gain_db"])) / math.sqrt(2.0)
    premaster += np.column_stack([prop, prop]) * _db(float(mix["prop_gain_db"])) / math.sqrt(2.0)
    premaster += body * _db(float(mix["body_gain_db"])) * body_duck[:, None]
    premaster += ambience * _db(float(mix["ambience_gain_db"])) * amb_duck[:, None]
    peak = float(np.max(np.abs(premaster)))
    if peak > _db(-3.0):
        premaster *= _db(-3.0) / peak
    premaster_path = stems_dir / "MIX_PREMASTER_STEREO.wav"
    _write_pcm24(premaster_path, premaster, sample_rate)
    stem_files["MIX_PREMASTER_STEREO"] = premaster_path

    target_i = float(mix["target_lufs_i"])
    target_lra = float(mix["target_lra_lu"])
    delivery_tp = float(mix["true_peak_dbtp_max"])
    master_tp = delivery_tp - float(mix["aac_true_peak_headroom_db"])
    first_pass = _loudnorm_measure(ffmpeg_bin, premaster_path, target_i=target_i, target_lra=target_lra, target_tp=master_tp)
    master_path = stems_dir / "MIX_MASTER_STEREO.wav"
    second_filter = (
        f"loudnorm=I={target_i}:LRA={target_lra}:TP={master_tp}:"
        f"measured_I={first_pass['input_i']}:measured_LRA={first_pass['input_lra']}:"
        f"measured_TP={first_pass['input_tp']}:measured_thresh={first_pass['input_thresh']}:"
        f"offset={first_pass['target_offset']}:linear=true:print_format=json,"
        f"aresample={sample_rate},atrim=end=38.8,apad=whole_dur=38.8"
    )
    _run(
        [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            premaster_path,
            "-af",
            second_filter,
            "-c:a",
            "pcm_s24le",
            "-ar",
            sample_rate,
            "-ac",
            2,
            master_path,
        ]
    )
    stem_files["MIX_MASTER_STEREO"] = master_path
    measured = _loudnorm_measure(ffmpeg_bin, master_path, target_i=target_i, target_lra=target_lra, target_tp=master_tp)
    measured_i = float(measured["input_i"])
    measured_lra = float(measured["input_lra"])
    measured_tp = float(measured["input_tp"])
    if abs(measured_i - target_i) > float(mix["target_lufs_tolerance"]):
        raise RuntimeError(f"master loudness is outside tolerance: {measured_i} LUFS-I")
    accepted_lra = [float(value) for value in mix["accepted_lra_lu"]]
    if not accepted_lra[0] <= measured_lra <= accepted_lra[1]:
        raise RuntimeError(f"master LRA is outside 4-8 LU: {measured_lra}")
    if measured_tp > master_tp + 0.05:
        raise RuntimeError(f"master true peak consumed its AAC headroom: {measured_tp}")

    captions = output / "june-golden-scene-master.srt"
    write_captions(contract, captions)
    final_video = output / "june-golden-scene-sound-master.mp4"
    partial_video = output / "june-golden-scene-sound-master.partial.mp4"
    partial_video.unlink(missing_ok=True)
    _run(
        [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            picture,
            "-i",
            master_path,
            "-i",
            captions,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            mix["aac_bitrate"],
            "-ar",
            sample_rate,
            "-ac",
            2,
            "-c:s",
            "mov_text",
            "-metadata:s:a:0",
            "language=eng",
            "-metadata:s:s:0",
            "language=eng",
            "-metadata",
            "title=The Twelve-Dollar Mug",
            "-metadata",
            "artist=June Oxley",
            "-t",
            "38.8",
            "-movflags",
            "+faststart",
            partial_video,
        ]
    )
    partial_video.replace(final_video)
    _run([ffmpeg_bin, "-v", "error", "-i", final_video, "-f", "null", "-"])
    picture_stream_hash = _stream_hash(ffmpeg_bin, picture, "0:v:0")
    final_stream_hash = _stream_hash(ffmpeg_bin, final_video, "0:v:0")
    if final_stream_hash != picture_stream_hash:
        raise RuntimeError("sound mux changed the locked picture stream")
    probe = _video_probe(ffprobe_bin, final_video)
    video_streams = [stream for stream in probe["streams"] if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in probe["streams"] if stream.get("codec_type") == "audio"]
    subtitle_streams = [stream for stream in probe["streams"] if stream.get("codec_type") == "subtitle"]
    if len(video_streams) != 1 or len(audio_streams) != 1 or len(subtitle_streams) != 1:
        raise RuntimeError("sound delivery must contain one video, one audio, and one caption stream")
    video_stream, audio_stream = video_streams[0], audio_streams[0]
    if (
        video_stream.get("codec_name") != "h264"
        or video_stream.get("pix_fmt") != "yuv420p"
        or int(video_stream.get("width", 0)) != 1920
        or int(video_stream.get("height", 0)) != 1080
        or int(video_stream.get("nb_frames", 0)) != 1164
        or audio_stream.get("codec_name") != "aac"
        or int(audio_stream.get("sample_rate", 0)) != 48000
        or int(audio_stream.get("channels", 0)) != 2
        or not math.isclose(float(probe["format"]["duration"]), 38.8, abs_tol=0.001)
    ):
        raise RuntimeError(f"final sound delivery failed its media contract: {probe}")
    encoded = _loudnorm_measure(ffmpeg_bin, final_video, target_i=target_i, target_lra=target_lra, target_tp=delivery_tp)
    encoded_i = float(encoded["input_i"])
    encoded_lra = float(encoded["input_lra"])
    encoded_tp = float(encoded["input_tp"])
    if abs(encoded_i - target_i) > float(mix["target_lufs_tolerance"]):
        raise RuntimeError(f"encoded AAC loudness is outside tolerance: {encoded_i} LUFS-I")
    if not accepted_lra[0] <= encoded_lra <= accepted_lra[1]:
        raise RuntimeError(f"encoded AAC LRA is outside 4-8 LU: {encoded_lra}")
    if encoded_tp > delivery_tp + 0.02:
        raise RuntimeError(f"encoded AAC true peak exceeds -1 dBTP: {encoded_tp}")

    stem_report = {}
    for stem_id, path in stem_files.items():
        stem_report[stem_id] = {"file": path.name, "sha256": _sha256(path), **_audio_probe(ffprobe_bin, path)}
    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "exact_picture_locked_sound_finished_golden_scene",
        "sound_id": contract["sound_id"],
        "contract_sha256": _sha256(Path(contract_path).resolve()),
        "picture": {
            "file": picture.name,
            "report_gate": picture_contract["gate"],
            "video_stream_sha256": picture_stream_hash,
            "reencoded": False,
        },
        "voice": {
            "file": dialogue_path.name,
            "sha256": _sha256(dialogue_path),
            "engine": contract["voice"]["engine"],
            "voice": contract["voice"]["voice"],
            "dataset": contract["voice"]["dataset"],
            "dataset_license": contract["voice"]["dataset_license"],
            "human_casting_approval_required": True,
        },
        "stems": stem_report,
        "required_foley": contract["required_foley"],
        "event_count": len(contract["events"]),
        "dialogue_cue_count": len(contract["dialogue_cues"]),
        "captions": {"file": captions.name, "sha256": _sha256(captions), "cue_count": len(contract["dialogue_cues"]), "applied_after_picture_and_mix": True},
        "loudness": {
            "target_lufs_i": target_i,
            "delivery_true_peak_dbtp_max": delivery_tp,
            "aac_true_peak_headroom_db": float(mix["aac_true_peak_headroom_db"]),
            "master_target_true_peak_dbtp": master_tp,
            "measured_lufs_i": measured_i,
            "measured_lra_lu": measured_lra,
            "measured_true_peak_dbtp": measured_tp,
            "first_pass": first_pass,
            "verification": measured,
            "encoded_aac": {
                "measured_lufs_i": encoded_i,
                "measured_lra_lu": encoded_lra,
                "measured_true_peak_dbtp": encoded_tp,
                "verification": encoded,
            },
        },
        "final": {
            "file": final_video.name,
            "sha256": _sha256(final_video),
            "video_stream_sha256": final_stream_hash,
            "video_stream_matches_picture_lock": True,
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "frame_count": 1164,
            "duration_seconds": 38.8,
            "video_codec": "h264",
            "pixel_format": "yuv420p",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "subtitle_codec": str(subtitle_streams[0].get("codec_name")),
        },
        "music": "none_intentional",
        "paid_runtime_dependency": False,
    }
    report_file = output / "june-golden-scene-sound-master-report.json"
    report_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    voice = subparsers.add_parser("voice", help="generate exact-clock phrase-fitted Piper dialogue")
    voice.add_argument("contract")
    voice.add_argument("--output", required=True)
    voice.add_argument("--piper", required=True)
    voice.add_argument("--model", required=True)
    voice.add_argument("--config", required=True)
    voice.add_argument("--model-card", required=True)
    voice.add_argument("--ffmpeg", default="ffmpeg")
    voice.add_argument("--ffprobe", default="ffprobe")
    voice.add_argument("--work-dir")
    voice.add_argument("--report")
    sound = subparsers.add_parser("mix", help="render stems, master sound, captions, and final mux")
    sound.add_argument("contract")
    sound.add_argument("--picture-video", required=True)
    sound.add_argument("--picture-report", required=True)
    sound.add_argument("--output-dir", required=True)
    sound.add_argument("--ffmpeg", default="ffmpeg")
    sound.add_argument("--ffprobe", default="ffprobe")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "voice":
        report = build_dialogue_source(
            args.contract,
            args.output,
            piper=args.piper,
            model=args.model,
            config=args.config,
            model_card=args.model_card,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
            work_dir=args.work_dir,
        )
        if args.report:
            report_path = Path(args.report).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        report = render_sound_master(
            args.contract,
            args.picture_video,
            args.picture_report,
            args.output_dir,
            ffmpeg=args.ffmpeg,
            ffprobe=args.ffprobe,
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
