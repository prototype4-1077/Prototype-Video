"""Level-matched source isolation after James still heard static throughout.

Remove the continuous procedural porch bed as a controlled experiment, not
another blanket filter or a claimed clean master. Voice and discrete actions
retain their exact timing and shared reference gain. No video route exists.
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

from pipeline import cartoon_fullmix_audio_successor as predecessor


REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / "collab/phase42_human_rejected_gates_successors_v1/june-phase42-fullmix-balanced_air-v1.wav"
REFERENCE_SHA256 = "d25975e13d1b1fc873214b342e8abb5065ef7409a2a98b523eee846523ba4357"
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-audio-source-isolation-v1"
RATE = 48000
MAX_PCM = predecessor.PCM24_MAX


class AudioIsolationError(RuntimeError):
    pass


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bed_source(contract: dict[str, Any]) -> np.ndarray:
    """Replay the bed event with its original per-event seed and normalization."""
    count = int(contract["master"]["sample_count"])
    result = np.zeros((count, 2), dtype=np.float64)
    rng = np.random.default_rng(int(contract["mix"]["seed"]))
    found = 0
    for event in contract["events"]:
        event_seed = int(rng.integers(0, 2**32 - 1))
        if event["type"] != "porch_ambience":
            continue
        found += 1
        start = (int(event["start_frame"]) - 1) * 1600
        size = (int(event["end_frame"]) - int(event["start_frame"]) + 1) * 1600
        signal = predecessor.golden_sound.SYNTHS["porch_ambience"](size, RATE, np.random.default_rng(event_seed))
        signal = signal / max(float(np.max(np.abs(signal))), 1e-12) * predecessor._db(float(event["gain_db"]))
        end = min(count, start + size)
        pan = float(event.get("pan", 0.0))
        result[start:end, 0] += signal[:end - start] * math.sqrt((1.0 - pan) / 2.0)
        result[start:end, 1] += signal[:end - start] * math.sqrt((1.0 + pan) / 2.0)
    if found != 1:
        raise AudioIsolationError(f"expected one continuous porch bed, found {found}")
    return result.astype(np.float32).astype(np.float64)


def _components() -> tuple[dict[str, np.ndarray], np.ndarray, dict[str, Any]]:
    if _hash(REFERENCE) != REFERENCE_SHA256:
        raise AudioIsolationError("reviewed balanced-air WAV changed")
    contract, dialogue, stems = predecessor._dialogue_and_stems()
    voice_path = REPO_ROOT / contract["voice"]["source"]["path"]
    if _hash(voice_path) != contract["voice"]["source"]["sha256"]:
        raise AudioIsolationError("locked dialogue source changed")
    index = predecessor._source_indices()
    timeline = dialogue[index].copy()
    timeline[:158400] = 0.0
    activity = predecessor.golden_sound._moving_average(np.abs(timeline), round(RATE * 0.12))
    activity = np.clip(activity / max(float(np.percentile(activity, 95)), 1e-9), 0.0, 1.0)
    spec = predecessor.VARIANTS["balanced_air"]
    amb_duck = 1.0 - activity * (1.0 - predecessor._db(float(contract["mix"]["dialogue_ambience_duck_db"])))
    body_duck = 1.0 - activity * (1.0 - predecessor._db(float(contract["mix"]["dialogue_body_duck_db"])))
    voice = np.column_stack((timeline, timeline)) / math.sqrt(2.0)
    prop = predecessor._high_shelf(stems["FOLEY_PROP_MONO"], spec["prop_cutoff_hz"], spec["prop_high_ratio"])[index, 0]
    prop = np.column_stack((prop, prop)) * predecessor._db(-1.0) / math.sqrt(2.0)
    body = predecessor._high_shelf(stems["FOLEY_BODY_STEREO"], spec["body_cutoff_hz"], spec["body_high_ratio"])[index]
    body *= predecessor._db(-1.5) * body_duck[:, None]
    ambience = predecessor._high_shelf(stems["AMB_PORCH_STEREO"], spec["ambience_cutoff_hz"], spec["ambience_high_ratio"])[index]
    ambience *= predecessor._db(spec["ambience_gain_db"]) * amb_duck[:, None]
    bed = predecessor._high_shelf(_bed_source(contract), spec["ambience_cutoff_hz"], spec["ambience_high_ratio"])[index]
    bed *= predecessor._db(spec["ambience_gain_db"]) * amb_duck[:, None]
    fade = np.ones(len(index), dtype=np.float64)
    fade[120000 - 1440:120000] = np.linspace(1.0, 0.0, 1440, endpoint=True)
    fade[120000:120000 + 1440] = np.linspace(0.0, 1.0, 1440, endpoint=True)
    components = {"voice": voice, "prop": prop, "body": body, "ambience": ambience, "porch_bed": bed}
    for component in components.values():
        component *= fade[:, None]
    basis = components["voice"] + components["prop"] + components["body"] + components["ambience"]
    rejected, _ = predecessor.ledger_pour._read_pcm24_wave(predecessor.REJECTED_WAV)
    active = activity >= 0.20
    target_rms = float(np.sqrt(np.mean((rejected[active].astype(np.float64) / MAX_PCM) ** 2)))
    source_rms = float(np.sqrt(np.mean(basis[active] ** 2)))
    gain = target_rms / source_rms
    ceiling = predecessor._db(-1.3)
    peak = float(np.max(np.abs(basis * gain)))
    if peak > ceiling:
        gain *= ceiling / peak
    for component in components.values():
        component *= gain
    reference, _ = predecessor.ledger_pour._read_pcm24_wave(REFERENCE)
    reconstructed = predecessor._to_pcm24(basis * gain)
    maximum_error = int(np.max(np.abs(reconstructed.astype(np.int64) - reference.astype(np.int64))))
    if maximum_error > 1:
        raise AudioIsolationError(f"component reconstruction differs from reviewed mix by {maximum_error} PCM units")
    components["reference_reconstruction"] = basis * gain
    return components, activity, {
        "shared_reference_gain": gain,
        "maximum_reconstruction_error_pcm24_units": maximum_error,
        "voice_source_sha256": _hash(voice_path),
        "sound_contract_sha256": _hash(predecessor.SOUND_CONTRACT),
        "dialogue_start_sample": 158400,
        "normalization": "one shared reviewed-mix gain; no per-file or per-stem level boost",
    }


def _band_rms_dbfs(values: np.ndarray) -> dict[str, float]:
    count = len(values)
    spectrum = np.fft.rfft(values, axis=0)
    frequencies = np.fft.rfftfreq(count, 1.0 / RATE)
    weights = np.full(len(frequencies), 2.0)
    weights[0] = 1.0
    if count % 2 == 0:
        weights[-1] = 1.0
    power = np.mean(np.abs(spectrum) ** 2, axis=1) * weights / count**2
    bands = {"below_1khz": (0, 1000), "1_to_8khz": (1000, 8000), "above_8khz": (8000, 24001)}
    return {name: 10.0 * math.log10(max(float(power[(frequencies >= low) & (frequencies < high)].sum()), 1e-30)) for name, (low, high) in bands.items()}


def build(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise AudioIsolationError(f"refusing to overwrite isolation proof: {output}")
    components, activity, audit = _components()
    files = {
        "voice_only": components["voice"],
        "porch_bed_only": components["porch_bed"],
        "porch_bed_removed": components["reference_reconstruction"] - components["porch_bed"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase42-isolation-", dir=output.parent) as temporary:
        stage = Path(temporary)
        artifacts = {}
        for name, floating in files.items():
            if float(np.max(np.abs(floating))) > 1.0:
                raise AudioIsolationError(f"{name} would clip; refusing silent automatic renormalization")
            pcm = predecessor._to_pcm24(floating)
            path = stage / f"june-phase42-{name.replace('_', '-')}-v1.wav"
            predecessor.ledger_pour._write_pcm24_wave(path, pcm, RATE)
            decoded, probe = predecessor.ledger_pour._read_pcm24_wave(path)
            if not np.array_equal(decoded, pcm):
                raise AudioIsolationError(f"{name} PCM readback mismatch")
            frame_rms = np.sqrt(np.mean(floating.reshape(303, 1600, 2) ** 2, axis=(1, 2)))
            artifacts[name] = {
                "file": path.name, "sha256": _hash(path), "bytes": path.stat().st_size,
                "probe": probe, "band_rms_dbfs": _band_rms_dbfs(floating),
                "nonzero_output_frames": int((frame_rms > 1e-12).sum()),
                "opening_rms_dbfs": 20 * math.log10(max(float(np.sqrt(np.mean(floating[:158400] ** 2))), 1e-15)),
                "measurements": predecessor._measure(decoded, activity),
            }
        report = {
            "report_version": 1, "classification": "CONTROLLED_SOURCE_ISOLATION_NOT_ACCEPTED_CLEAN_MASTER",
            "cash_cost": 0, "network_calls": 0, "video_encoder_processes": 0,
            "reviewed_reference": {"file": REFERENCE.relative_to(REPO_ROOT).as_posix(), "sha256": REFERENCE_SHA256, "human_verdict": "STATIC_REMAINS_THROUGHOUT"},
            "source_audit": audit, "artifacts": artifacts,
            "implementation_sha256": _hash(Path(__file__)),
            "human_accepted": False, "promotion_allowed": False,
            "interpretation": "Removing only the continuous porch bed is a causal listening comparison. It retains the exact voice and discrete actions/chimes; those may still contain objectionable noise. Band energy and old proxy scores are descriptive, not listening acceptance.",
        }
        (stage / "phase42-audio-source-isolation-report-v1.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        if _hash(REFERENCE) != REFERENCE_SHA256:
            raise AudioIsolationError("reviewed reference changed during isolation")
        shutil.move(str(stage), str(output))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps({"source_audit": result["source_audit"], "files": {name: entry["file"] for name, entry in result["artifacts"].items()}, "human_accepted": False}, indent=2))


if __name__ == "__main__":
    main()
