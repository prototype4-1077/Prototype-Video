"""Two real, credited Foley cues around the unchanged clean voice reference.

This audio-only audition replaces the rejected tonal effects. No chimes,
continuous bed, synthesized water/contact tones, or speech processing run.
It is not an accepted full mix and cannot encode or promote picture.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import numpy as np

from pipeline import cartoon_fullmix_audio_successor as audio


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "concept/audio/foley_sources_v1"
MANIFEST_SHA256 = "42eb293da43770457956fb4a336dfaa4b713274d063ecbe9641b17b1788b5d59"
CREDITS_SHA256 = "6117265570f227f86f3afb700d20650ffc9e7df9bd72d27fe8baa1e258e7afe6"
CONTRACT_SHA256 = "4d1f8592fb89eab950546b5c94de77f9bb19dfdc5d9d9edf377e5a4c590d5afe"
VOICE_PATH = REPO_ROOT / "collab/phase42_audio_source_isolation_v1/june-phase42-voice-only-v1.wav"
VOICE_SHA256 = "b9a2f402d9255397bf8cafec9170aca6e76c028b5cbd5ede0733d2ebc699f16a"
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-recorded-foley-v3"
RATE = 48000
FADE_SAMPLES = 1440
COUNT = 484800


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources(root: Path) -> dict[str, Any]:
    if _hash(root / "sources.json") != MANIFEST_SHA256:
        raise ValueError("recorded source manifest changed")
    if _hash(root / "ATTRIBUTION.md") != CREDITS_SHA256:
        raise ValueError("recorded source attribution changed")
    manifest = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    for source in manifest["sources"]:
        path = root / source["file"]
        if _hash(path) != source["sha256"] or path.stat().st_size != source["bytes"]:
            raise ValueError(f"recorded source bytes changed: {path.name}")
    return manifest


def _faded_excerpt(decoded: np.ndarray, source: dict[str, Any]) -> np.ndarray:
    start, count = int(source["decoded_start_sample"]), int(source["decoded_sample_count"])
    if start < 0 or count < 2 * FADE_SAMPLES or start + count > len(decoded):
        raise ValueError("recorded excerpt is outside its source")
    signal = decoded[start:start + count, 0].astype(np.float64).copy()
    if not np.all(np.isfinite(signal)) or not np.any(signal):
        raise ValueError("recorded excerpt is empty or non-finite")
    signal[:FADE_SAMPLES] *= np.linspace(0.0, 1.0, FADE_SAMPLES)
    signal[-FADE_SAMPLES:] *= np.linspace(1.0, 0.0, FADE_SAMPLES)
    signal *= audio._db(float(source["mono_peak_dbfs"])) / float(np.max(np.abs(signal)))
    return signal


def render_effects(manifest: dict[str, Any], source_root: Path, ffmpeg: str) -> tuple[np.ndarray, list[dict[str, Any]]]:
    if _hash(audio.SOUND_CONTRACT) != CONTRACT_SHA256:
        raise ValueError("source sound contract changed")
    contract = json.loads(audio.SOUND_CONTRACT.read_text(encoding="utf-8"))
    events = {event["id"]: event for event in contract["events"]}
    indices = audio._source_indices()
    effects = np.zeros((COUNT, 2), dtype=np.float64)
    used = []
    for source in manifest["sources"]:
        event = events[source["event_id"]]
        frames = [event["start_frame"], event["end_frame"]]
        if frames != source["global_frames_inclusive"] or event["type"] != source["event_type"]:
            raise ValueError("recorded Foley event clock changed")
        decoded = audio.golden_sound._read_audio_f32(
            ffmpeg, source_root / source["file"], channels=1, sample_rate=RATE,
        )
        signal = _faded_excerpt(decoded, source)
        if len(signal) != (int(frames[1]) - int(frames[0]) + 1) * 1600:
            raise ValueError("recorded excerpt does not match its event duration")
        global_start = (int(frames[0]) - 1) * 1600
        output_indices = np.flatnonzero((indices >= global_start) & (indices < global_start + len(signal)))
        if len(output_indices) != len(signal) or np.any(np.diff(output_indices) != 1):
            raise ValueError("recorded cue is cut or split by the editorial mapping")
        mono = signal[indices[output_indices] - global_start]
        pan = float(source["pan"])
        effects[output_indices, 0] += mono * math.sqrt((1.0 - pan) / 2.0)
        effects[output_indices, 1] += mono * math.sqrt((1.0 + pan) / 2.0)
        used.append({
            **source,
            "decoded_source_samples": len(decoded),
            "decoded_excerpt_float32_sha256": hashlib.sha256(decoded[int(source["decoded_start_sample"]):int(source["decoded_start_sample"]) + len(signal)].astype("<f4").tobytes()).hexdigest(),
            "output_sample_range_half_open": [int(output_indices[0]), int(output_indices[-1]) + 1],
            "output_seconds": [float(output_indices[0]) / RATE, float(output_indices[-1] + 1) / RATE],
            "fade_samples_each_edge": FADE_SAMPLES,
        })
    return audio._to_pcm24(effects), used


def build(output: Path = OUTPUT_DEFAULT, *, source_root: Path = SOURCE_ROOT, ffmpeg: str = "ffmpeg") -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite recorded Foley audition: {output}")
    manifest = _sources(source_root)
    if _hash(VOICE_PATH) != VOICE_SHA256:
        raise ValueError("clean voice reference changed")
    voice, probe = audio.ledger_pour._read_pcm24_wave(VOICE_PATH)
    if voice.shape != (COUNT, 2) or probe["sample_rate"] != RATE:
        raise ValueError("clean voice clock changed")
    ffmpeg_bin = shutil.which(ffmpeg)
    if ffmpeg_bin is None:
        raise ValueError("local FFmpeg audio decoder is required; no install or download is attempted")
    effects, events = render_effects(manifest, source_root, ffmpeg_bin)
    summed = voice.astype(np.int64) + effects.astype(np.int64)
    if np.max(np.abs(summed)) > audio._db(-1.0) * audio.PCM24_MAX:
        raise ValueError("Foley exceeds headroom; refusing to normalize the clean voice")
    candidate = summed.astype(np.int32)
    if not np.array_equal(candidate.astype(np.int64) - effects.astype(np.int64), voice.astype(np.int64)):
        raise ValueError("clean voice contribution changed")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase42-recorded-", dir=output.parent) as temporary:
        stage = Path(temporary)
        artifacts = {}
        for name, samples in (("recorded-foley", candidate), ("recorded-effects-only", effects)):
            path = stage / f"june-phase42-{name}-v3.wav"
            audio.ledger_pour._write_pcm24_wave(path, samples, RATE)
            decoded, readback_probe = audio.ledger_pour._read_pcm24_wave(path)
            if not np.array_equal(decoded, samples):
                raise ValueError("PCM readback changed the audition")
            artifacts[name] = {
                "file": path.name, "sha256": _hash(path), "bytes": path.stat().st_size,
                "probe": readback_probe,
                "peak_dbfs": 20.0 * math.log10(max(float(np.max(np.abs(samples))) / audio.PCM24_MAX, 1e-15)),
                "edit_boundary_max_sample_delta": {
                    str(boundary): float(np.max(np.abs(samples[boundary].astype(np.int64) - samples[boundary - 1].astype(np.int64)))) / audio.PCM24_MAX
                    for boundary in (120000, 158400)
                },
            }
        for name in ("sources.json", "ATTRIBUTION.md"):
            shutil.copyfile(source_root / name, stage / name)
        report = {
            "report_version": 3, "classification": "RECORDED_FOLEY_LISTENING_CANDIDATE_NOT_ACCEPTED",
            "cash_cost": 0, "network_calls_during_build": 0, "audio_decoder_processes": 2, "video_encoder_processes": 0,
            "runtime": {"numpy": np.__version__, "ffmpeg": subprocess.run([ffmpeg_bin, "-version"], check=True, capture_output=True, text=True).stdout.splitlines()[0]},
            "implementation_sha256": _hash(Path(__file__)), "sound_contract_sha256": CONTRACT_SHA256,
            "source_manifest_sha256": MANIFEST_SHA256, "attribution_sha256": CREDITS_SHA256,
            "voice": {"file": VOICE_PATH.relative_to(REPO_ROOT).as_posix(), "sha256": VOICE_SHA256, "pcm_contribution_preserved_exactly": True, "human_feedback": "NO_STATIC_HEARD_IN_VOICE_ONLY"},
            "events": events, "artifacts": artifacts,
            "omitted": ["all synthetic Foley", "all wind chimes", "continuous porch bed", "breath/cloth/scrape noise", "cut-out pot-set tail"],
            "previous_sparse_v2_verdict": "STATIC_CHECK_PASSED_EFFECT_CHARACTER_REJECTED",
            "human_accepted": False, "promotion_allowed": False,
            "note": "Waveform checks verify clock, samples, boundaries and headroom, not naturalness or absence of audible static in the new recordings. Two cues are a diagnostic sound treatment, not complete scene Foley.",
        }
        (stage / "phase42-recorded-foley-report-v3.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        if _hash(VOICE_PATH) != VOICE_SHA256 or _sources(source_root) != manifest:
            raise ValueError("an input changed during the build")
        shutil.move(str(stage), str(output))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    result = build(args.output, ffmpeg=args.ffmpeg)
    print(json.dumps({"artifacts": result["artifacts"], "human_accepted": False}, indent=2))


if __name__ == "__main__":
    main()
