"""Build bounded, unencoded full-mix successors to rejected Candidate03 audio.

This module never overwrites or retries Candidate03.  It reconstructs the exact
10.1-second edit from the locked Phase26 dialogue/foley/ambience sources, then
applies stem-specific high-frequency shelves before a deterministic dialogue-
referenced level match.  The outputs are listening prototypes, not accepted or
promotion-authorized masters.
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

from pipeline import cartoon_audio_noise_proxy as noise_proxy
from pipeline import cartoon_golden_sound as golden_sound
from pipeline import cartoon_ledger_pour as ledger_pour


REPO_ROOT = Path(__file__).resolve().parents[1]
SOUND_CONTRACT = REPO_ROOT / "concept/style_frames/june_golden_scene_master_sound_v1.json"
REJECTED_WAV = REPO_ROOT / "collab/phase36_candidate_03/june-phase36-ledger-pour-mix-v3.wav"
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-fullmix-audio-successor-v2"
PCM24_MAX = 8_388_607
SAMPLE_RATE = 48_000


class FullMixSuccessorError(RuntimeError):
    """Raised when a bounded audio-successor invariant fails."""


VARIANTS: dict[str, dict[str, float]] = {
    "balanced_air": {
        "ambience_cutoff_hz": 4_500.0,
        "ambience_high_ratio": 0.18,
        "ambience_gain_db": -3.0,
        "body_cutoff_hz": 6_000.0,
        "body_high_ratio": 0.25,
        "prop_cutoff_hz": 8_000.0,
        "prop_high_ratio": 0.50,
    },
    "clean_warm": {
        "ambience_cutoff_hz": 4_200.0,
        "ambience_high_ratio": 0.10,
        "ambience_gain_db": -4.5,
        "body_cutoff_hz": 5_500.0,
        "body_high_ratio": 0.18,
        "prop_cutoff_hz": 7_500.0,
        "prop_high_ratio": 0.40,
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _db(value: float) -> float:
    return 10.0 ** (value / 20.0)


def _lowpass(values: np.ndarray, cutoff_hz: float, taps: int = 257) -> np.ndarray:
    if values.ndim == 1:
        values = values[:, None]
    positions = np.arange(taps, dtype=np.float64) - (taps - 1) / 2.0
    normalized_cutoff = float(cutoff_hz) / SAMPLE_RATE
    kernel = 2.0 * normalized_cutoff * np.sinc(2.0 * normalized_cutoff * positions)
    kernel *= np.blackman(taps)
    kernel /= np.sum(kernel)
    filtered = np.column_stack(
        [np.convolve(values[:, channel], kernel, mode="same") for channel in range(values.shape[1])]
    )
    return filtered


def _high_shelf(values: np.ndarray, cutoff_hz: float, high_ratio: float) -> np.ndarray:
    low = _lowpass(values.astype(np.float64), cutoff_hz)
    source = values.astype(np.float64)
    if source.ndim == 1:
        source = source[:, None]
    return low + (source - low) * float(high_ratio)


def _dialogue_and_stems() -> tuple[dict[str, Any], np.ndarray, dict[str, np.ndarray]]:
    contract, _ = golden_sound.load_sound_contract(SOUND_CONTRACT, require_dialogue_source=False)
    dialogue_path = REPO_ROOT / str(contract["voice"]["source"]["path"])
    dialogue, probe = ledger_pour._read_pcm24_wave(dialogue_path)
    expected = {
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "bits_per_sample": 24,
        "sample_count": int(contract["master"]["sample_count"]),
    }
    actual = {key: probe[key] for key in expected}
    if actual != expected:
        raise FullMixSuccessorError(f"dialogue geometry mismatch: {actual!r}")
    dialogue_float = dialogue[:, 0].astype(np.float64) / PCM24_MAX
    performed = dialogue_float.copy()
    samples_per_frame = int(contract["master"]["samples_per_frame"])
    for cue in contract["dialogue_cues"]:
        start = (int(cue["start_frame"]) - 1) * samples_per_frame
        end = int(cue["end_frame"]) * samples_per_frame
        performed[start:end] *= _db(float(cue.get("gain_db", 0.0)))
    stems = {name: value.astype(np.float64) for name, value in golden_sound.render_procedural_stems(contract).items()}
    return contract, performed, stems


def _source_indices() -> np.ndarray:
    # Phase36 editorial mapping: F790-F864 pour, F913-F936 bridge,
    # then the contiguous Phase33 direct-address source F937-F1140.
    spans = ((789 * 1600, 864 * 1600), (912 * 1600, 936 * 1600), (936 * 1600, 1140 * 1600))
    indices = np.concatenate([np.arange(start, end, dtype=np.int64) for start, end in spans])
    if indices.shape != (484_800,):
        raise FullMixSuccessorError(f"editorial sample mapping mismatch: {indices.shape!r}")
    return indices


def _assemble_float(variant: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    contract, dialogue, stems = _dialogue_and_stems()
    indices = _source_indices()
    dialogue_timeline = dialogue[indices].copy()
    # Phase36's pour and bridge are intentionally dialogue-free.  Direct address
    # begins at local sample 158400 (3.3 seconds).
    dialogue_timeline[:158_400] = 0.0

    ambience_all = _high_shelf(
        stems["AMB_PORCH_STEREO"],
        variant["ambience_cutoff_hz"],
        variant["ambience_high_ratio"],
    )
    body_all = _high_shelf(
        stems["FOLEY_BODY_STEREO"], variant["body_cutoff_hz"], variant["body_high_ratio"]
    )
    prop_all = _high_shelf(
        stems["FOLEY_PROP_MONO"], variant["prop_cutoff_hz"], variant["prop_high_ratio"]
    )[:, 0]

    ambience = ambience_all[indices]
    body = body_all[indices]
    prop = prop_all[indices]
    mix_spec = contract["mix"]
    activity = golden_sound._moving_average(np.abs(dialogue_timeline), round(SAMPLE_RATE * 0.12))
    activity /= max(float(np.percentile(activity, 95.0)), 1e-9)
    activity = np.clip(activity, 0.0, 1.0)
    amb_duck = 1.0 - activity * (1.0 - _db(float(mix_spec["dialogue_ambience_duck_db"])))
    body_duck = 1.0 - activity * (1.0 - _db(float(mix_spec["dialogue_body_duck_db"])))

    result = np.column_stack([dialogue_timeline, dialogue_timeline]) / math.sqrt(2.0)
    result += np.column_stack([prop, prop]) * _db(-1.0) / math.sqrt(2.0)
    result += body * _db(-1.5) * body_duck[:, None]
    result += ambience * _db(float(variant["ambience_gain_db"])) * amb_duck[:, None]

    # Prevent the editorial jump from the pour to the pre-dialogue bridge from
    # producing a click.  The second boundary is source-contiguous.
    fade = 1_440
    result[120_000 - fade : 120_000] *= np.linspace(1.0, 0.0, fade, endpoint=True)[:, None]
    result[120_000 : 120_000 + fade] *= np.linspace(0.0, 1.0, fade, endpoint=True)[:, None]

    rejected, _ = ledger_pour._read_pcm24_wave(REJECTED_WAV)
    rejected_float = rejected.astype(np.float64) / PCM24_MAX
    active = activity >= 0.20
    if int(active.sum()) < 10_000:
        raise FullMixSuccessorError("dialogue activity mask is unexpectedly empty")
    target_rms = float(np.sqrt(np.mean(rejected_float[active] ** 2)))
    source_rms = float(np.sqrt(np.mean(result[active] ** 2)))
    if source_rms <= 0.0:
        raise FullMixSuccessorError("successor dialogue reference has zero RMS")
    result *= target_rms / source_rms
    ceiling = _db(-1.3)
    peak = float(np.max(np.abs(result)))
    if peak > ceiling:
        result *= ceiling / peak
    return result, activity


def _to_pcm24(values: np.ndarray) -> np.ndarray:
    return np.rint(np.clip(values, -1.0, 1.0) * PCM24_MAX).astype(np.int32)


def _cluster_count(indices: np.ndarray, maximum_gap_samples: int = 8) -> int:
    if indices.size == 0:
        return 0
    return 1 + int(np.count_nonzero(np.diff(indices) > maximum_gap_samples))


def _transient_audit(values: np.ndarray, activity: np.ndarray) -> dict[str, Any]:
    normalized = values.astype(np.float64) / PCM24_MAX
    first_delta = np.max(np.abs(np.diff(normalized, axis=0)), axis=1)
    threshold = 0.08
    indices = np.flatnonzero(first_delta >= threshold)
    activity_at_delta = activity[1:]
    quiet_indices = indices[activity_at_delta[indices] < 0.05]
    active_indices = indices[activity_at_delta[indices] >= 0.20]
    transition_indices = indices[
        (activity_at_delta[indices] >= 0.05) & (activity_at_delta[indices] < 0.20)
    ]
    boundaries: dict[str, Any] = {}
    for name, sample in (("pour_to_bridge", 120_000), ("bridge_to_direct_address", 158_400)):
        radius = 480
        window_start = max(0, sample - radius)
        window_end = min(first_delta.shape[0], sample + radius)
        boundaries[name] = {
            "sample": sample,
            "seconds": sample / SAMPLE_RATE,
            "immediate_adjacent_sample_delta_fs": float(first_delta[sample - 1]),
            "maximum_adjacent_sample_delta_within_10ms_fs": float(
                np.max(first_delta[window_start:window_end])
            ),
            "rms_10ms_before_dbfs": 20.0 * math.log10(max(float(np.sqrt(np.mean(
                normalized[sample - radius : sample] ** 2
            ))), 1e-15)),
            "rms_10ms_after_dbfs": 20.0 * math.log10(max(float(np.sqrt(np.mean(
                normalized[sample : sample + radius] ** 2
            ))), 1e-15)),
        }
    return {
        "fixed_impulse_threshold_fs": threshold,
        "fixed_threshold_sample_count": int(indices.size),
        "fixed_threshold_event_count": _cluster_count(indices),
        "quiet_fixed_threshold_sample_count": int(quiet_indices.size),
        "quiet_fixed_threshold_event_count": _cluster_count(quiet_indices),
        "transition_fixed_threshold_sample_count": int(transition_indices.size),
        "transition_fixed_threshold_event_count": _cluster_count(transition_indices),
        "dialogue_active_fixed_threshold_sample_count": int(active_indices.size),
        "dialogue_active_fixed_threshold_event_count": _cluster_count(active_indices),
        "maximum_adjacent_sample_delta_fs": float(first_delta.max()),
        "edit_boundaries": boundaries,
    }


def _measure(values: np.ndarray, activity: np.ndarray) -> dict[str, Any]:
    floating = values.astype(np.float64) / PCM24_MAX
    proxy = noise_proxy.audible_noise_proxy(values)
    quiet = activity < 0.05
    active = activity >= 0.20
    return {
        "pcm_sha256": hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest(),
        "duration_seconds": values.shape[0] / SAMPLE_RATE,
        "peak_dbfs": 20.0 * math.log10(max(float(np.max(np.abs(floating))), 1e-15)),
        "full_rms_dbfs": 20.0 * math.log10(max(float(np.sqrt(np.mean(floating**2))), 1e-15)),
        "quiet_rms_dbfs": 20.0 * math.log10(max(float(np.sqrt(np.mean(floating[quiet] ** 2))), 1e-15)),
        "active_rms_dbfs": 20.0 * math.log10(max(float(np.sqrt(np.mean(floating[active] ** 2))), 1e-15)),
        "clipped_channel_values": int((np.abs(values.astype(np.int64)) > PCM24_MAX).sum()),
        "noise_proxy": proxy,
        "transient_audit": _transient_audit(values, activity),
    }


def build(output_root: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output_root.resolve()
    if output.exists():
        raise FullMixSuccessorError(f"refusing to overwrite existing prototype: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    rejected_hash_before = _sha256(REJECTED_WAV)
    with tempfile.TemporaryDirectory(prefix="phase42-audio-", dir=output.parent) as temporary:
        stage = Path(temporary)
        artifacts: dict[str, Any] = {}
        for name, spec in VARIANTS.items():
            floating, activity = _assemble_float(spec)
            pcm = _to_pcm24(floating)
            wav = stage / f"june-phase42-fullmix-{name}-v1.wav"
            ledger_pour._write_pcm24_wave(wav, pcm, SAMPLE_RATE)
            decoded, probe = ledger_pour._read_pcm24_wave(wav)
            if not np.array_equal(decoded, pcm):
                raise FullMixSuccessorError(f"{name} PCM24 readback mismatch")
            artifacts[name] = {
                "file": wav.name,
                "wav_sha256": _sha256(wav),
                "bytes": wav.stat().st_size,
                "probe": probe,
                "filter": spec,
                "measurements": _measure(decoded, activity),
            }

        rejected, _ = ledger_pour._read_pcm24_wave(REJECTED_WAV)
        _, rejected_activity = _assemble_float(VARIANTS["balanced_air"])
        report = {
            "report_version": 1,
            "classification": "UNENCODED_LISTENING_PROTOTYPES_HUMAN_REVIEW_REQUIRED",
            "cash_cost": 0,
            "network_calls": 0,
            "video_encoder_processes": 0,
            "rejected_predecessor": {
                "file": str(REJECTED_WAV.relative_to(REPO_ROOT)).replace("\\", "/"),
                "wav_sha256": rejected_hash_before,
                "immutable": True,
                "human_verdict": "REJECTED_AUDIBLE_STATIC",
            },
            "source_mapping": {
                "pour_global_frames": [790, 864],
                "bridge_global_frames": [913, 936],
                "direct_address_global_frames": [937, 1140],
                "output_samples": 484_800,
            },
            "rejected_measurements": _measure(rejected, rejected_activity),
            "variants": artifacts,
            "recommendation_rule": "Prefer the least-filtered variant whose full-mix static-like ratio and longest run materially beat Candidate03; human listening is final.",
            "human_review_required": True,
            "human_accepted": False,
            "promotion_allowed": False,
            "encode_allowed": False,
        }
        report_path = stage / "phase42-fullmix-audio-successor-report-v1.json"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        if _sha256(REJECTED_WAV) != rejected_hash_before:
            raise FullMixSuccessorError("rejected Candidate03 changed during successor build")
        shutil.move(str(stage), str(output))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
