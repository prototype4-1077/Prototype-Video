"""Translate Rhubarb cues to the existing mouth art, without changing time.

The historical renderer/art contracts stay immutable. This adapter is an
unapproved experiment, not a new production renderer or an acting verdict.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterator

import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_scene_review as scene


direct_renderer = scene.acting.phase35
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-mouth-semantics-v1-cache-reuse"
CUE_SOURCE = "concept/style_frames/june_phase33_direct_address_rhubarb_v1.json"
SEMANTICS_SOURCE = "https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes"
# These are internal ART labels, not a renaming of the upstream cue standard.
RHUBARB_TO_ART = {"A": "X", "B": "C", "C": "D", "D": "B", "E": "A",
                  "F": "G", "G": "F", "H": "H", "X": "X"}
STUDY_FRAMES = tuple(range(25, 163))
CROP = (480, 290, 790, 535)
KEY_FRAMES = (27, 35, 49, 67, 73, 94)
NAME = "mouth-semantics-native-ab-v1"


def translated_plan(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep every frame/blend; translate names at the art boundary only."""
    result = deepcopy(plan)
    for row in result:
        if "rhubarb_from_shape" in row or "rhubarb_to_shape" in row:
            raise ValueError("mouth plan has already been translated")
        for key in ("from_shape", "to_shape"):
            raw = row[key]
            if raw not in RHUBARB_TO_ART:
                raise ValueError(f"unsupported Rhubarb shape: {raw!r}")
            row["rhubarb_" + key] = raw
            row[key] = RHUBARB_TO_ART[raw]
    return result


@contextmanager
def mouth_override(prepared: direct_renderer.PreparedDirectAddress) -> Iterator[None]:
    """Isolate both caches, restoring the caller's exact objects on failure."""
    translated = translated_plan(prepared.visemes)
    original = (prepared.visemes, prepared.native_cache, prepared.adapter_cache)
    prepared.visemes = translated
    prepared.native_cache, prepared.adapter_cache = {}, {}
    try:
        yield
    finally:
        prepared.visemes, prepared.native_cache, prepared.adapter_cache = original


def prospective_native_support(prepared: direct_renderer.PreparedDirectAddress) -> np.ndarray:
    support = np.zeros(prepared.face.plate.shape[:2], dtype=bool)
    x1, y1, x2, y2 = prepared.face.contract["semantic_geometry_native_xy"]["deformation_roi"]
    support[y1:y2, x1:x2] = True
    return support


def preview_excerpt(samples: np.ndarray, first: int, last: int) -> np.ndarray:
    """Same scene samples, with 30-ms listening-clip edges only; no gain fit."""
    if not 1 <= first <= last <= 228:
        raise ValueError("excerpt must stay within the dialogue scene")
    start, count = (first + 74) * 1600, (last - first + 1) * 1600
    segment = samples[start:start + count].copy()
    if segment.shape != (count, 2):
        raise ValueError("accepted audio cannot supply the requested scene window")
    fade = 1440
    ramp = np.linspace(0.0, 1.0, fade)
    segment[:fade] = np.rint(segment[:fade] * ramp[:, None]).astype(np.int32)
    segment[-fade:] = np.rint(segment[-fade:] * ramp[::-1, None]).astype(np.int32)
    return segment


def _panel(old: np.ndarray, new: np.ndarray, source_frame: int, raw: dict[str, Any], mapped: dict[str, Any]) -> Image.Image:
    x1, y1, x2, y2 = CROP
    width, height = x2 - x1, y2 - y1
    canvas = Image.new("RGB", (width * 2 + 40, height + 54), (17, 15, 12))
    canvas.paste(Image.fromarray(old[y1:y2, x1:x2]), (10, 30))
    canvas.paste(Image.fromarray(new[y1:y2, x1:x2]), (width + 30, 30))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 8), "EXISTING", fill=(245, 230, 210))
    draw.text((width + 30, 8), "CUE TRANSLATION ONLY", fill=(245, 230, 210))
    label = (f"source F{source_frame:03d} / output F{source_frame + 75:03d} | "
             f"cue {raw['to_shape']} -> art {mapped['to_shape']} | blend {raw['blend']:.2f}")
    draw.text((10, height + 36), label, fill=(245, 230, 210))
    return canvas


def build(output: Path = OUTPUT_DEFAULT, *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"preserve previous evidence; output already exists: {output}")
    encoder_bin, probe_bin = shutil.which(ffmpeg), shutil.which(ffprobe)
    if not encoder_bin or not probe_bin:
        raise RuntimeError("local FFmpeg and FFprobe are required")
    accepted = scene.accepted_components()
    prepared = scene.integration.prepare_repaired_acting()
    direct = prepared.integration.direct
    old_plan, new_plan = direct.visemes, translated_plan(direct.visemes)
    # Keep two independent adapters alive for the entire study. Resetting a
    # candidate cache once per frame needlessly rerenders repeated drawings.
    candidate = replace(direct, visemes=new_plan, native_cache={}, adapter_cache={})
    support = prospective_native_support(direct)
    output.mkdir(parents=True)
    width, height = (CROP[2] - CROP[0]) * 2 + 40, CROP[3] - CROP[1] + 54
    # Even dimensions are required for yuv420p; pad one black bottom row.
    encoded_height = height + height % 2
    silent = output / f"{NAME}-silent.mp4"
    command = [encoder_bin, "-nostdin", "-v", "error", "-n", "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-s", f"{width}x{encoded_height}", "-r", "30",
               "-i", "pipe:0", "-an", "-vf", scene.FRAME_FILTERS, "-c:v", "libx264",
               "-threads", "4", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
               "-x264-params", scene.X264_PARAMS, "-video_track_timescale", "30000",
               "-movflags", "+faststart+write_colr", str(silent)]
    rows, stills = [], []
    maximum_outside, maximum_folded, maximum_depth = 0, 0, 0
    minimum_triangle = float("inf")
    with (output / "encode.log").open("wb") as log:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
        try:
            with scene.accepted_lids(prepared):
                for frame in STUDY_FRAMES:
                    raw, mapped = old_plan[frame - 1], new_plan[frame - 1]
                    closure = scene.blink.candidate_closure(frame)
                    old, old_evidence = direct_renderer.controlled_native_frame(direct, raw, closure)
                    new, evidence = direct_renderer.controlled_native_frame(candidate, mapped, closure)
                    changed = np.any(old != new, axis=2)
                    outside = int(changed[~support].sum())
                    maximum_outside = max(maximum_outside, outside)
                    maximum_folded = max(maximum_folded, evidence.folded_triangles)
                    maximum_depth = max(maximum_depth, evidence.depth_order_violation_pixels)
                    minimum_triangle = min(minimum_triangle, evidence.minimum_triangle_area_ratio)
                    if outside or evidence.folded_triangles or evidence.depth_order_violation_pixels:
                        raise ValueError(f"mouth candidate violated native safety at F{frame}")
                    rows.append({"source_frame": frame, "raw": raw, "translated": mapped,
                                 "old_rgb_sha256": hashlib.sha256(old.tobytes()).hexdigest(),
                                 "candidate_rgb_sha256": hashlib.sha256(new.tobytes()).hexdigest(),
                                 "changed_pixels": int(changed.sum()), "changed_outside_perioral_roi": outside,
                                 "old_cavity_area": old_evidence.cavity_area, "candidate_cavity_area": evidence.cavity_area,
                                 "candidate_weights": evidence.pose_weights})
                    panel = _panel(old, new, frame, raw, mapped)
                    padded = Image.new("RGB", (width, encoded_height))
                    padded.paste(panel, (0, 0))
                    assert encoder.stdin is not None
                    encoder.stdin.write(padded.tobytes())
                    if frame in KEY_FRAMES:
                        stills.append(panel.copy())
                    panel.close()
                    padded.close()
            assert encoder.stdin is not None
            encoder.stdin.close()
            if encoder.wait(timeout=60):
                raise RuntimeError("short native comparison encode failed; inspect encode.log")
        finally:
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait(timeout=10)
    sheet = Image.new("RGB", (width, height * len(stills)))
    for index, still in enumerate(stills):
        sheet.paste(still, (0, index * height))
        still.close()
    sheet.save(output / "mouth-semantics-keyframes-v1.png")
    sheet.close()
    audio_path = REPO_ROOT / accepted["audio"]["path"]
    samples, _ = scene.picture._read_pcm24_wave(audio_path)
    excerpt = preview_excerpt(samples, STUDY_FRAMES[0], STUDY_FRAMES[-1])
    wav = output / "accepted-audio-excerpt-with-preview-edge-fades.wav"
    scene.picture._write_pcm24_wave(wav, excerpt, 48000)
    pcm, _ = scene.picture._read_pcm24_wave(wav)
    if not np.array_equal(excerpt, pcm):
        raise ValueError("short preview audio PCM readback differs")
    mp4, mov = output / f"{NAME}.mp4", output / f"{NAME}.mov"
    for destination, codec in ((mov, ["-c:a", "pcm_s24le"]), (mp4, ["-c:a", "aac", "-b:a", "256k"])):
        subprocess.run([encoder_bin, "-nostdin", "-v", "error", "-n", "-i", str(silent),
                        "-i", str(wav), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                        *codec, "-video_track_timescale", "30000", "-movflags", "+faststart+write_colr",
                        str(destination)], check=True, capture_output=True)
    probe = scene._probe(mp4, probe_bin)
    video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
    decoded_frames = subprocess.run([encoder_bin, "-v", "error", "-i", str(mp4), "-map", "0:v:0",
                                    "-f", "null", "-"], check=True, capture_output=True)
    del decoded_frames
    if (int(video["nb_frames"]), video["avg_frame_rate"]) != (len(STUDY_FRAMES), "30/1"):
        raise ValueError("native preview frame count/rate changed")
    if abs(float(probe["format"]["duration"]) - len(STUDY_FRAMES) / 30) > 0.001:
        raise ValueError("native preview duration changed")
    if scene._video_hash(mov, encoder_bin) != scene._video_hash(mp4, encoder_bin):
        raise ValueError("lossless-audio and browser copies have different pictures")
    (output / "ATTRIBUTION.md").write_bytes((REPO_ROOT / "collab/phase42_integrated_scene_review_v1/ATTRIBUTION.md").read_bytes())
    report = {"classification": "MOUTH_SEMANTICS_NATIVE_STUDY_REVIEW_PENDING", "human_accepted": False,
              "full_scene_rendered": False, "production_promotion_allowed": False, "cash_cost": 0,
              "network_runtime_calls": 0, "rhubarb_semantics_source": SEMANTICS_SOURCE,
              "mapping": RHUBARB_TO_ART, "source_frames_inclusive": [25, 162], "frame_count": len(rows),
              "output_frames_inclusive": [100, 237], "output_time_seconds_half_open": [3.3, 7.9],
              "fps": 30, "cue_times_and_two_frame_blends_changed": False,
              "artwork_geometry_changed": False, "native_crop_xyxy": CROP,
              "maximum_changed_pixels_outside_perioral_roi": maximum_outside,
              "maximum_folded_triangles": maximum_folded, "minimum_triangle_area_ratio": minimum_triangle,
              "maximum_depth_order_violation_pixels": maximum_depth,
              "accepted_audio_source_sha256": scene._hash(audio_path),
              "excerpt_audio_samples": len(excerpt), "preview_only_edge_fades_samples": 1440,
              "accepted_audio_source_modified": False, "blink_schedule_modified": False,
              "implementation_sha256": scene._hash(Path(__file__)),
              "upstream_cue_sha256": scene._hash(REPO_ROOT / CUE_SOURCE),
              "frames": rows, "decoded_preview": probe,
              "limitations": ["Native fixed-face crop, not sustained whole-scene performance.",
                              "Existing rounded and long-L drawings are only approximate semantic matches after translation.",
                              "Closed P/B/M uses relaxed X; no independently authored pressure pose.",
                              "Cue recognition and two-frame interpolation are unchanged, not proven correct.",
                              "Preview audio alone has 30-ms edge fades; accepted full mix is untouched."],
              "artifacts": {path.name: {"sha256": scene._hash(path), "bytes": path.stat().st_size}
                            for path in sorted(output.iterdir()) if path.is_file()}}
    scene._json(output / "mouth-semantics-study-report-v1.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps({key: result[key] for key in ("classification", "frame_count", "maximum_changed_pixels_outside_perioral_roi", "maximum_folded_triangles")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
