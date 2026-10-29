"""One normal-speed integrated mouth/hand A/B; never a full-scene promotion.

Reuse the verified lossless scene cache on the left and the existing approved
eye/body/camera stack plus isolated mouth/hand adapters on the right. The
comparison uses identical fixed delivery-pixel crops; final scene cuts and
framing are not edited. No new artwork, speech, cloud service or paid API.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pipeline import cartoon_mouth_semantics_refinement as mouth
from pipeline import cartoon_hand_motion_refinement as hand


scene = mouth.scene
REPO_ROOT = mouth.REPO_ROOT
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-mouth-hand-integrated-ab-v1"
CACHE_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-integrated-scene-review-v1/scene-rgb24-xor-v1.gz"
PACKAGE = REPO_ROOT / "collab/phase42_integrated_scene_review_v1"
SOURCE_FRAMES = tuple(range(25, 163))
DELIVERY_CROP = (400, 60, 1360, 1080)
SAMPLES = (25, 27, 67, 115, 162)
NAME = "june-mouth-hand-integrated-ab-v1"


def baseline_frames(cache_path: Path) -> Iterator[tuple[int, np.ndarray]]:
    report = json.loads((PACKAGE / "phase42-integrated-scene-review-report-v1.json").read_text(encoding="utf-8"))
    if scene._hash(cache_path) != report["lossless_render_cache"]["sha256"]:
        raise ValueError("lossless reviewed-scene cache hash changed")
    inventory = json.loads((PACKAGE / "source-frame-inventory-v1.json").read_text(encoding="utf-8"))
    with gzip.open(cache_path, "rb") as source:
        header = json.loads(source.readline())
        expected = {"format": "phase42_rgb24_xor_previous_gzip_v1", "width": 1920,
                    "height": 1080, "channels": 3, "frame_count": 303,
                    "frame_bytes": 1920 * 1080 * 3, "component_acceptance_sha256": scene.ACCEPTANCE_SHA256}
        if header != expected or len(inventory) != 303:
            raise ValueError("lossless reviewed-scene cache geometry changed")
        previous = np.zeros((1080, 1920, 3), dtype=np.uint8)
        for number in range(1, 304):
            delta = source.read(header["frame_bytes"])
            if len(delta) != header["frame_bytes"]:
                raise ValueError(f"lossless scene cache truncated at F{number}")
            pixels = np.bitwise_xor(previous, np.frombuffer(delta, dtype=np.uint8).reshape(previous.shape))
            if hashlib.sha256(pixels.tobytes()).hexdigest() != inventory[number - 1]["rgb_sha256"]:
                raise ValueError(f"lossless scene cache RGB mismatch at F{number}")
            previous = pixels
            yield number, pixels
        if source.read(1):
            raise ValueError("lossless scene cache has trailing frame data")


def candidate_preparation(prepared: Any) -> Any:
    direct = prepared.integration.direct
    adapted = replace(direct, visemes=mouth.translated_plan(direct.visemes), native_cache={}, adapter_cache={})
    return replace(prepared, integration=replace(prepared.integration, direct=adapted))


def allowed_support(prepared: Any, frame: int) -> np.ndarray:
    integration = prepared.integration
    mouth_support = scene.acting._transform_mask(mouth.prospective_native_support(integration.direct),
                                                 integration, frame, follow_head=True)
    # Same prospectively declared final-camera guard used by the body stack.
    guard = int(integration.body.contract["deformation"]["prospective_kernel_guard_px"])
    if guard:
        mouth_support = cv2.dilate(mouth_support.astype(np.uint8), np.ones((2 * guard + 1,) * 2, np.uint8)) > 0
    return mouth_support | hand.delivery_hand_support(integration, frame)


def compose_candidate(prepared: Any, frame: int) -> np.ndarray:
    with hand.hand_override(prepared.integration.body, frame):
        pixels, _ = scene.compose_direct_frame(prepared, frame)
    return pixels


def comparison_panel(old: np.ndarray, new: np.ndarray, frame: int) -> Image.Image:
    if old.shape != (1080, 1920, 3) or new.shape != old.shape:
        raise ValueError("comparison inputs must be full-HD delivery RGB")
    canvas = Image.new("RGB", (1920, 1080), (15, 13, 11))
    left, top, right, bottom = DELIVERY_CROP
    canvas.paste(Image.fromarray(old[top:bottom, left:right]), (0, 32))
    canvas.paste(Image.fromarray(new[top:bottom, left:right]), (960, 32))
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    draw = ImageDraw.Draw(canvas)
    draw.text((12, 3), "EXISTING", fill=(245, 230, 210), font=font)
    draw.text((972, 3), "MOUTH TRANSLATION + PLANTED HAND", fill=(245, 230, 210), font=font)
    draw.text((12, 1054), f"NORMAL SPEED | scene {(frame + 74) / 30:.3f}s | source F{frame:03d} / output F{frame + 75:03d} | identical native-pixel crops",
              fill=(245, 230, 210), font=font)
    return canvas


def build(output: Path = OUTPUT_DEFAULT, cache_path: Path = CACHE_DEFAULT) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"preserve previous evidence; output exists: {output}")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("local FFmpeg and FFprobe required")
    accepted = scene.accepted_components()
    prepared = candidate_preparation(scene.integration.prepare_repaired_acting())
    output.mkdir(parents=True)
    silent = output / f"{NAME}-silent.mp4"
    rows, retained = [], {}
    with (output / "encode.log").open("wb") as log:
        encoder = subprocess.Popen(scene.encoder_command(ffmpeg, silent), stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=log)
        try:
            with scene.accepted_lids(prepared):
                for number, old in baseline_frames(cache_path):
                    frame = number - 75
                    if frame not in SOURCE_FRAMES:
                        continue
                    support = allowed_support(prepared, frame)
                    candidate = compose_candidate(prepared, frame)
                    changed = np.any(old != candidate, axis=2)
                    outside = int(changed[~support].sum())
                    mug = scene.acting._transform_mask(prepared.integration.body.protected["mug"], prepared.integration, frame)
                    mug_changed = int(changed[mug].sum())
                    if outside or mug_changed:
                        raise ValueError(f"combined repair damaged protected pixels at source F{frame}: outside={outside}, mug={mug_changed}")
                    panel = comparison_panel(old, candidate, frame)
                    assert encoder.stdin is not None
                    encoder.stdin.write(panel.tobytes())
                    if frame in SAMPLES:
                        retained[frame] = np.asarray(panel).copy()
                    rows.append({"source_frame": frame, "output_frame": number,
                                 "baseline_rgb_sha256": hashlib.sha256(old.tobytes()).hexdigest(),
                                 "candidate_rgb_sha256": hashlib.sha256(candidate.tobytes()).hexdigest(),
                                 "comparison_rgb_sha256": hashlib.sha256(panel.tobytes()).hexdigest(),
                                 "changed_pixels": int(changed.sum()), "changed_outside_declared_mouth_hand_support": outside,
                                 "mug_changed_pixels": mug_changed, "hand_adapter_active": 91 <= frame < 148})
                    panel.close()
                    if len(rows) % 30 == 0:
                        print(f"Integrated comparison {len(rows)}/{len(SOURCE_FRAMES)} frames", flush=True)
                # The accepted full-close scene frame is outside the excerpt;
                # prove both adapters still leave that exact endpoint intact.
                late_eye = compose_candidate(prepared, 173)
                late_eye_hash = hashlib.sha256(late_eye.tobytes()).hexdigest()
                if late_eye_hash != "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40":
                    raise ValueError("combined adapters changed the accepted full-close frame")
            assert encoder.stdin is not None
            encoder.stdin.close()
            if encoder.wait(timeout=60):
                raise RuntimeError("integrated comparison encoder failed; inspect preserved log")
        finally:
            if encoder.poll() is None:
                encoder.kill()
                encoder.wait(timeout=10)
    if len(rows) != 138:
        raise ValueError("comparison did not cover the complete speech window")
    audio = REPO_ROOT / "collab/phase42_mouth_semantics_v1/accepted-audio-excerpt-with-preview-edge-fades.wav"
    full_audio, _ = scene.picture._read_pcm24_wave(REPO_ROOT / accepted["audio"]["path"])
    clip_audio, clip_probe = scene.picture._read_pcm24_wave(audio)
    if not np.array_equal(clip_audio, mouth.preview_excerpt(full_audio, 25, 162)):
        raise ValueError("comparison excerpt is not the approved scene samples plus preview-edge fades")
    for suffix, codec in (("mov", ["-c:a", "pcm_s24le"]), ("mp4", ["-c:a", "aac", "-b:a", "256k"])):
        subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-n", "-i", str(silent), "-i", str(audio),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", *codec,
                        "-video_track_timescale", "30000", "-movflags", "+faststart+write_colr",
                        str(output / f"{NAME}.{suffix}")], check=True, capture_output=True)
    mp4, mov = output / f"{NAME}.mp4", output / f"{NAME}.mov"
    probe = scene._probe(mp4, ffprobe)
    video = next(item for item in probe["streams"] if item["codec_type"] == "video")
    if int(video["nb_read_frames"]) != 138 or video["avg_frame_rate"] != "30/1":
        raise ValueError("decoded integrated comparison clock changed")
    if abs(float(probe["format"]["duration"]) - 4.6) > 0.001:
        raise ValueError("decoded integrated comparison duration changed")
    decoded_pcm = subprocess.run([ffmpeg, "-v", "error", "-i", str(mov), "-map", "0:a:0", "-f", "s24le", "-"],
                                 check=True, capture_output=True).stdout
    if hashlib.sha256(decoded_pcm).hexdigest() != clip_probe["data_sha256"]:
        raise ValueError("MOV excerpt audio differs from exact preview WAV")
    if scene._video_hash(mp4, ffmpeg) != scene._video_hash(mov, ffmpeg):
        raise ValueError("preview and exact-audio copies have different pictures")
    decoded = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(mp4), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    compression = []
    try:
        for frame in SOURCE_FRAMES:
            assert decoded.stdout is not None
            raw = decoded.stdout.read(1920 * 1080 * 3)
            if len(raw) != 1920 * 1080 * 3:
                raise ValueError(f"comparison decode stopped at F{frame}")
            if frame in retained:
                pixels = np.frombuffer(raw, np.uint8).reshape(1080, 1920, 3)
                mse = float(np.mean((pixels.astype(np.float64) - retained[frame].astype(np.float64)) ** 2))
                psnr = float(10 * np.log10(255 ** 2 / max(mse, 1e-20)))
                if psnr < 35:
                    raise ValueError(f"comparison encode damaged sampled F{frame}")
                Image.fromarray(pixels).save(output / f"decoded-source-f{frame:03d}.png")
                compression.append({"source_frame": frame, "rgb_psnr_db": psnr})
        if decoded.stdout.read(1) or decoded.wait(timeout=30):
            raise ValueError("comparison decode has extra frames or an error")
    finally:
        if decoded.poll() is None:
            decoded.kill()
            decoded.wait(timeout=10)
    for name in ("ATTRIBUTION.md", "sources.json"):
        shutil.copyfile(PACKAGE / name, output / name)
    report = {"classification": "INTEGRATED_MOUTH_HAND_AB_HUMAN_REVIEW_PENDING", "human_accepted": False,
              "production_promotion_allowed": False, "full_scene_rendered": False, "cash_cost": 0,
              "network_runtime_calls": 0, "frame_count": 138, "fps": 30, "duration_seconds": 4.6,
              "source_frames_inclusive": [25, 162], "scene_output_frames_inclusive": [100, 237],
              "scene_time_seconds_half_open": [3.3, 7.9], "comparison_crop_xyxy": DELIVERY_CROP,
              "comparison_resized": False, "original_scene_framing_and_cuts_modified": False,
              "cache_sha256": scene._hash(cache_path), "all_303_baseline_cache_frames_verified": True,
              "accepted_full_close_frame_rgb_sha256": late_eye_hash,
              "accepted_full_audio_wav_sha256": scene._hash(REPO_ROOT / accepted["audio"]["path"]),
              "mov_excerpt_pcm_sha256": hashlib.sha256(decoded_pcm).hexdigest(),
              "preview_only_audio_edge_fades_samples": 1440, "frames": rows, "compression_samples": compression,
              "implementation_sha256": scene._hash(Path(__file__)),
              "mouth_adapter_sha256": scene._hash(Path(mouth.__file__)),
              "hand_adapter_sha256": scene._hash(Path(hand.__file__)), "decoded_probe": probe,
              "limits": ["A diagnostic native-pixel crop, not a new final-scene edit.",
                         "Clip does not exercise the later camera cut/blink in motion; exact late endpoint checked separately.",
                         "Support, geometry and compression checks do not establish natural acting or lip-sync acceptance."],
              "artifacts": {path.name: {"sha256": scene._hash(path), "bytes": path.stat().st_size}
                            for path in sorted(output.iterdir()) if path.is_file()}}
    scene._json(output / "integrated-mouth-hand-review-report-v1.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--baseline-cache", type=Path, default=CACHE_DEFAULT)
    args = parser.parse_args()
    result = build(args.output, args.baseline_cache)
    print(json.dumps({"classification": result["classification"], "frame_count": result["frame_count"],
                      "maximum_outside_support": max(row["changed_outside_declared_mouth_hand_support"] for row in result["frames"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
