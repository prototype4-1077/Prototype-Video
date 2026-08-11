"""Deterministic, full-mix proxies for audible broadband static and crackle.

The proxy deliberately reports measurements rather than claiming to replace a
human listen.  It is useful as a regression gate for exposed broadband noise:
low-level frames with both noise-like spectral flatness and a large high-band
power share.  A separate time-domain detector reports short impulsive crackle.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np


PCM24_MAX = 8_388_607


class AudioNoiseProxyError(ValueError):
    """Raised when audio cannot be measured under the fixed proxy contract."""


def _dbfs(value: float) -> float:
    return 20.0 * math.log10(max(float(value), 1e-15))


def _percentile(values: np.ndarray, percentile: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.percentile(values, percentile))


def _longest_true_run(values: np.ndarray) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if bool(value) else 0
        longest = max(longest, current)
    return longest


def _cluster_count(indices: np.ndarray, maximum_gap_samples: int) -> int:
    if indices.size == 0:
        return 0
    return 1 + int(np.count_nonzero(np.diff(indices) > maximum_gap_samples))


def audible_noise_proxy(
    samples: np.ndarray,
    *,
    sample_rate: int = 48_000,
    frame_samples: int = 2_048,
    hop_samples: int = 512,
    exposed_rms_ceiling_dbfs: float = -28.0,
    exposed_rms_floor_dbfs: float = -80.0,
    static_flatness_floor: float = 0.40,
    static_high_band_ratio_floor: float = 0.35,
    crackle_delta_floor_fs: float = 0.08,
) -> dict[str, Any]:
    """Measure the whole PCM mix and return JSON-safe audible-noise proxies.

    ``samples`` must be signed integer PCM with shape ``(sample_frames,
    channels)``.  Every source sample is covered: a final overlapping FFT frame
    is appended when the fixed hop does not land exactly on the tail.
    """

    values = np.asarray(samples)
    if values.ndim != 2 or values.shape[0] < frame_samples or values.shape[1] < 1:
        raise AudioNoiseProxyError("audio must be sample_frames x channels and at least one analysis frame")
    if not np.issubdtype(values.dtype, np.integer):
        raise AudioNoiseProxyError("audio noise proxy requires signed integer PCM")
    if sample_rate <= 0 or frame_samples <= 0 or hop_samples <= 0 or hop_samples > frame_samples:
        raise AudioNoiseProxyError("invalid audio-noise analysis geometry")

    normalized = values.astype(np.float64) / PCM24_MAX
    sample_count = int(normalized.shape[0])
    starts = list(range(0, sample_count - frame_samples + 1, hop_samples))
    final_start = sample_count - frame_samples
    if starts[-1] != final_start:
        starts.append(final_start)

    window = np.hanning(frame_samples).astype(np.float64)
    frequencies = np.fft.rfftfreq(frame_samples, d=1.0 / sample_rate)
    audible = (frequencies >= 80.0) & (frequencies <= 20_000.0)
    high_band = (frequencies >= 8_000.0) & (frequencies <= 20_000.0)
    if not np.any(audible) or not np.any(high_band):
        raise AudioNoiseProxyError("analysis FFT cannot represent the required audible bands")

    rms_dbfs: list[float] = []
    flatness: list[float] = []
    high_band_ratio: list[float] = []
    static_score: list[float] = []
    for start in starts:
        frame = normalized[start : start + frame_samples]
        rms = math.sqrt(float(np.mean(frame * frame)))
        rms_dbfs.append(_dbfs(rms))
        spectrum = np.fft.rfft(frame * window[:, None], axis=0)
        power = np.mean(np.abs(spectrum) ** 2, axis=1)
        audible_power = power[audible]
        epsilon = max(float(np.max(audible_power)) * 1e-15, 1e-30)
        arithmetic = float(np.mean(audible_power + epsilon))
        geometric = float(np.exp(np.mean(np.log(audible_power + epsilon))))
        frame_flatness = geometric / max(arithmetic, 1e-30)
        frame_high_ratio = float(np.sum(power[high_band]) / max(np.sum(audible_power), 1e-30))
        flatness.append(frame_flatness)
        high_band_ratio.append(frame_high_ratio)
        static_score.append(frame_flatness * frame_high_ratio)

    rms_array = np.asarray(rms_dbfs, dtype=np.float64)
    flatness_array = np.asarray(flatness, dtype=np.float64)
    high_ratio_array = np.asarray(high_band_ratio, dtype=np.float64)
    score_array = np.asarray(static_score, dtype=np.float64)
    exposed = (rms_array <= exposed_rms_ceiling_dbfs) & (rms_array >= exposed_rms_floor_dbfs)
    static_like = exposed & (flatness_array >= static_flatness_floor) & (
        high_ratio_array >= static_high_band_ratio_floor
    )
    static_run = _longest_true_run(static_like)
    static_run_seconds = (
        0.0
        if static_run == 0
        else (frame_samples + (static_run - 1) * hop_samples) / float(sample_rate)
    )

    first_delta = np.max(np.abs(np.diff(normalized, axis=0)), axis=1)
    delta_median = float(np.median(first_delta))
    delta_mad = float(np.median(np.abs(first_delta - delta_median)))
    adaptive_crackle_floor = max(crackle_delta_floor_fs, delta_median + 40.0 * max(delta_mad, 1e-12))
    crackle_indices = np.flatnonzero(first_delta >= adaptive_crackle_floor)

    exposed_scores = score_array[exposed]
    exposed_flatness = flatness_array[exposed]
    exposed_high_ratio = high_ratio_array[exposed]
    static_indices = np.flatnonzero(static_like)
    return {
        "method": "stft_2048_hann_hop512_exposed_flatness_highband_v1",
        "sample_rate": int(sample_rate),
        "sample_count": sample_count,
        "duration_seconds": sample_count / float(sample_rate),
        "channels": int(values.shape[1]),
        "frame_samples": int(frame_samples),
        "hop_samples": int(hop_samples),
        "analyzed_frame_count": int(len(starts)),
        "coverage_start_sample": 0,
        "coverage_end_sample_exclusive": sample_count,
        "coverage_complete": bool(starts[0] == 0 and starts[-1] + frame_samples == sample_count),
        "thresholds": {
            "exposed_rms_ceiling_dbfs": float(exposed_rms_ceiling_dbfs),
            "exposed_rms_floor_dbfs": float(exposed_rms_floor_dbfs),
            "static_flatness_floor": float(static_flatness_floor),
            "static_high_band_ratio_floor": float(static_high_band_ratio_floor),
            "crackle_delta_floor_fs": float(crackle_delta_floor_fs),
            "adaptive_crackle_delta_floor_fs": adaptive_crackle_floor,
        },
        "noise_floor": {
            "rms_dbfs_p10_all_frames": _percentile(rms_array, 10.0),
            "rms_dbfs_p20_all_frames": _percentile(rms_array, 20.0),
            "rms_dbfs_median_all_frames": _percentile(rms_array, 50.0),
        },
        "broadband_static": {
            "exposed_frame_count": int(np.count_nonzero(exposed)),
            "static_like_frame_count": int(np.count_nonzero(static_like)),
            "static_like_window_ratio_all_frames": float(np.mean(static_like)),
            "maximum_static_like_run_seconds": static_run_seconds,
            "first_static_like_start_seconds": (
                None if static_indices.size == 0 else starts[int(static_indices[0])] / float(sample_rate)
            ),
            "last_static_like_end_seconds": (
                None
                if static_indices.size == 0
                else (starts[int(static_indices[-1])] + frame_samples) / float(sample_rate)
            ),
            "spectral_flatness_median_exposed": _percentile(exposed_flatness, 50.0),
            "spectral_flatness_p95_exposed": _percentile(exposed_flatness, 95.0),
            "high_band_power_ratio_median_exposed": _percentile(exposed_high_ratio, 50.0),
            "high_band_power_ratio_p95_exposed": _percentile(exposed_high_ratio, 95.0),
            "static_score_median_exposed": _percentile(exposed_scores, 50.0),
            "static_score_p95_exposed": _percentile(exposed_scores, 95.0),
        },
        "crackle": {
            "maximum_adjacent_sample_delta_fs": float(np.max(first_delta)),
            "median_adjacent_sample_delta_fs": delta_median,
            "mad_adjacent_sample_delta_fs": delta_mad,
            "impulsive_delta_sample_count": int(crackle_indices.size),
            "impulsive_crackle_event_count": _cluster_count(crackle_indices, maximum_gap_samples=8),
        },
    }


def interval_noise_proxy(
    samples: np.ndarray,
    start_sample: int,
    end_sample: int,
    *,
    sample_rate: int = 48_000,
) -> dict[str, Any]:
    """Run the same proxy on a declared interval for secondary diagnosis."""

    values = np.asarray(samples)
    if not 0 <= start_sample < end_sample <= values.shape[0]:
        raise AudioNoiseProxyError("invalid interval")
    result = audible_noise_proxy(values[start_sample:end_sample], sample_rate=sample_rate)
    result["source_interval"] = {
        "start_sample": int(start_sample),
        "end_sample_exclusive": int(end_sample),
        "start_seconds": start_sample / float(sample_rate),
        "end_seconds": end_sample / float(sample_rate),
    }
    return result
