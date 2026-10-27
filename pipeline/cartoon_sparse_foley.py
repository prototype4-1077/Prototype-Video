"""Sparse, tonal Foley audition around James's clean voice-only reference.

Noise-based breath, cloth, continuous leaves/cicadas and scraping are not fed
back into this audition. The exact reviewed voice PCM is an immutable additive
component. This is an audio-only listening candidate, not an accepted master.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
from typing import Any

import numpy as np

from pipeline import cartoon_audio_stem_isolation as isolation


REPO_ROOT = Path(__file__).resolve().parents[1]
VOICE_PATH = REPO_ROOT / "collab/phase42_audio_source_isolation_v1/june-phase42-voice-only-v1.wav"
VOICE_SHA256 = "b9a2f402d9255397bf8cafec9170aca6e76c028b5cbd5ede0733d2ebc699f16a"
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-sparse-foley-v2"
RATE = 48000
SYNTHETIC_TYPES = {"coffee_pot", "coffee_pour", "mug_place", "mug_slide", "wind_chime"}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contact(size: int, frequencies: tuple[float, ...], decay: float) -> np.ndarray:
    time = np.arange(size, dtype=np.float64) / RATE
    result = sum((0.40**index) * np.sin(math.tau * frequency * time + index * 0.2) * np.exp(-time * decay * (1.0 + 0.4 * index)) for index, frequency in enumerate(frequencies))
    return result * isolation.predecessor.golden_sound._envelope(size, 0.008, 0.50)


def _water(size: int, rng: np.random.Generator) -> np.ndarray:
    """Small damped water resonances; no per-sample noise generator."""
    result = np.zeros(size, dtype=np.float64)
    onset = 0
    while onset < size:
        length = min(size - onset, round(0.095 * RATE))
        time = np.arange(length, dtype=np.float64) / RATE
        frequency = float(rng.uniform(430.0, 1100.0))
        phase = math.tau * (frequency * time - 650.0 * time**2)
        drop = np.sin(phase) * np.exp(-time * float(rng.uniform(38.0, 65.0)))
        drop += 0.20 * np.sin(phase * 1.82 + 0.3) * np.exp(-time * 80.0)
        drop *= isolation.predecessor.golden_sound._envelope(length, 0.025, 0.30)
        result[onset:onset + length] += float(rng.uniform(0.35, 0.75)) * drop
        onset += int(rng.integers(round(0.055 * RATE), round(0.13 * RATE)))
    return result * isolation.predecessor.golden_sound._envelope(size, 0.18, 0.25)


def render_effects(contract: dict[str, Any], gain: float) -> tuple[np.ndarray, list[dict[str, Any]]]:
    effects = np.zeros((int(contract["master"]["sample_count"]), 2), dtype=np.float64)
    master_rng = np.random.default_rng(int(contract["mix"]["seed"]))
    used = []
    for event in contract["events"]:
        rng = np.random.default_rng(int(master_rng.integers(0, 2**32 - 1)))
        kind = str(event["type"])
        if kind not in SYNTHETIC_TYPES:
            continue
        size = (int(event["end_frame"]) - int(event["start_frame"]) + 1) * 1600
        if kind == "wind_chime":
            signal = isolation.predecessor.golden_sound._wind_chime(size, RATE, rng)
            reduction = -5.0
        elif kind == "coffee_pour":
            signal, reduction = _water(size, rng), -8.0
        elif kind == "coffee_pot":
            signal, reduction = _contact(size, (690.0, 1370.0, 2410.0), 20.0), -7.0
        elif kind == "mug_place":
            signal, reduction = _contact(size, (880.0, 1710.0, 2530.0), 20.0), -7.0
        else:
            # Keep a soft contact cue for the mug gesture, not a sustained
            # noise-based scrape under the dialogue.
            signal, reduction = _contact(size, (190.0, 540.0, 1080.0), 17.0), -10.0
        signal *= isolation.predecessor._db(float(event["gain_db"]) + reduction) / max(float(np.max(np.abs(signal))), 1e-12)
        start = (int(event["start_frame"]) - 1) * 1600
        end = min(len(effects), start + size)
        pan = float(event.get("pan", 0.0))
        effects[start:end, 0] += signal[:end - start] * math.sqrt((1.0 - pan) / 2.0)
        effects[start:end, 1] += signal[:end - start] * math.sqrt((1.0 + pan) / 2.0)
        used.append({"id": event["id"], "type": kind, "source_frames": [event["start_frame"], event["end_frame"]], "gain_reduction_db": reduction})
    result = effects[isolation.predecessor._source_indices()] * gain
    result[120000 - 1440:120000] *= np.linspace(1.0, 0.0, 1440)[:, None]
    result[120000:120000 + 1440] *= np.linspace(0.0, 1.0, 1440)[:, None]
    return result, used


def build(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite sparse Foley audition: {output}")
    if _hash(VOICE_PATH) != VOICE_SHA256:
        raise ValueError("clean voice reference changed")
    voice, probe = isolation.predecessor.ledger_pour._read_pcm24_wave(VOICE_PATH)
    if voice.shape != (484800, 2) or probe["sample_rate"] != RATE:
        raise ValueError("voice clock changed")
    report_path = VOICE_PATH.parent / "phase42-audio-source-isolation-report-v1.json"
    isolation_report = json.loads(report_path.read_text(encoding="utf-8"))
    contract, _ = isolation.predecessor.golden_sound.load_sound_contract(isolation.predecessor.SOUND_CONTRACT, require_dialogue_source=False)
    if _hash(isolation.predecessor.SOUND_CONTRACT) != isolation_report["source_audit"]["sound_contract_sha256"]:
        raise ValueError("source sound contract changed")
    effects_float, used = render_effects(contract, float(isolation_report["source_audit"]["shared_reference_gain"]))
    effects = isolation.predecessor._to_pcm24(effects_float)
    summed = voice.astype(np.int64) + effects.astype(np.int64)
    ceiling = isolation.predecessor._db(-1.0) * isolation.MAX_PCM
    if float(np.max(np.abs(summed))) > ceiling:
        raise ValueError("Foley exceeded headroom; refusing to normalize the accepted voice")
    candidate = summed.astype(np.int32)
    if not np.array_equal(candidate.astype(np.int64) - effects.astype(np.int64), voice.astype(np.int64)):
        raise ValueError("accepted voice contribution was altered")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase42-foley-", dir=output.parent) as temporary:
        stage = Path(temporary)
        artifacts = {}
        for name, samples in (("sparse-foley", candidate), ("sparse-effects-only", effects)):
            path = stage / f"june-phase42-{name}-v2.wav"
            isolation.predecessor.ledger_pour._write_pcm24_wave(path, samples, RATE)
            decoded, decoded_probe = isolation.predecessor.ledger_pour._read_pcm24_wave(path)
            if not np.array_equal(samples, decoded):
                raise ValueError("PCM readback changed the audition")
            artifacts[name] = {"file": path.name, "sha256": _hash(path), "bytes": path.stat().st_size, "probe": decoded_probe, "peak_dbfs": 20.0 * math.log10(max(float(np.max(np.abs(samples))) / isolation.MAX_PCM, 1e-15))}
        report = {
            "report_version": 2, "classification": "SPARSE_FOLEY_LISTENING_CANDIDATE_NOT_ACCEPTED",
            "cash_cost": 0, "network_calls": 0, "video_encoder_processes": 0,
            "voice": {"file": VOICE_PATH.relative_to(REPO_ROOT).as_posix(), "sha256": VOICE_SHA256, "human_feedback": "NO_STATIC_HEARD_IN_VOICE_ONLY", "pcm_contribution_preserved_exactly": True},
            "isolation_report_sha256": _hash(report_path), "implementation_sha256": _hash(Path(__file__)),
            "events": used, "omitted_types": sorted({str(event["type"]) for event in contract["events"]} - SYNTHETIC_TYPES),
            "artifacts": artifacts, "human_accepted": False, "promotion_allowed": False,
            "note": "Sparse tonal contacts, water drops, and chimes are an audition, not evidence that the original effects have been repaired or that the whole scene passes listening.",
        }
        (stage / "phase42-sparse-foley-report-v2.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        if _hash(VOICE_PATH) != VOICE_SHA256:
            raise ValueError("clean voice reference changed during build")
        shutil.move(str(stage), str(output))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    result = build(parser.parse_args().output)
    print(json.dumps({"artifacts": result["artifacts"], "voice_preserved": True, "human_accepted": False}, indent=2))


if __name__ == "__main__":
    main()
