"""Render the newly human-approved eye/audio components in the full scene.

Reuses the existing pour, body, face, atmosphere and camera renderers. The
historical adapters/rejected files are never edited or invoked as deliveries.
Outputs are review candidates, not an automatic production promotion.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterator

import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_blink_refinement as blink
from pipeline import cartoon_recorded_foley as foley


integration = blink.integration
acting = integration.acting
picture = integration.eyes.v4.v3.phase36
REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = REPO_ROOT / "concept/characters/june_oxley_phase42_component_acceptance_v1.json"
ACCEPTANCE_SHA256 = "52c1f98020ff143ecb2d00f670284eb3cd79697e77aeee92107a100c7fc67e66"
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-integrated-scene-review-v1"
SHOTS = ((1, 75), (76, 237), (238, 303))
KEY_FRAMES = (1, 45, 75, 76, 100, 145, 200, 237, 238, 248, 270, 303)
SAMPLE_FRAMES = set(KEY_FRAMES) | set(range(74, 78)) | set(range(236, 240)) | set(range(242, 255))
NAME = "june-phase42-integrated-scene-review-v1"
FRAME_FILTERS = "scale=in_range=full:out_range=limited:out_color_matrix=bt709,format=yuv420p,setsar=1,setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709"
X264_PARAMS = "fullrange=off:colorprim=bt709:transfer=bt709:colormatrix=bt709"


def _hash(path: Path) -> str:
    return picture._sha256(path)


def _json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def accepted_components(path: Path = ACCEPTANCE) -> dict[str, Any]:
    if _hash(path) != ACCEPTANCE_SHA256:
        raise ValueError("human component acceptance binding changed")
    accepted = json.loads(path.read_text(encoding="utf-8"))
    if not accepted["scope"]["integrated_303_frame_review_allowed"]:
        raise ValueError("integrated review is not authorized")
    for name in ("verdict", "audio", "blink"):
        entry = accepted[name]
        if name != "verdict" and entry["human_accepted"] is not True:
            raise ValueError(f"{name} lacks human acceptance")
        for reference in (entry, *([entry["report"]] if "report" in entry else [])):
            if _hash(REPO_ROOT / reference["path"]) != reference["sha256"]:
                raise ValueError(f"accepted {name} artifact changed")
    blink_report = json.loads((REPO_ROOT / accepted["blink"]["report"]["path"]).read_text(encoding="utf-8"))
    if _hash(Path(blink.__file__)) != blink_report["implementation_sha256"]:
        raise ValueError("accepted blink implementation changed")
    expected = blink_report["candidate_closures"]
    actual = [blink.candidate_closure(frame) for frame in accepted["blink"]["source_frames"]]
    if actual != expected:
        raise ValueError("accepted blink schedule changed")
    foley._sources(foley.SOURCE_ROOT)
    return accepted


@contextmanager
def accepted_lids(prepared: integration.PreparedRepairedActing) -> Iterator[None]:
    direct = prepared.integration.direct
    original_contract, original_cache = direct.contract, direct.native_cache.copy()
    direct.contract = deepcopy(original_contract)
    direct.contract["performance"]["blink_curves"] = [{
        "id": "james_accepted_phase42_v3",
        "frames": list(range(167, 180)),
        "closures": [blink.candidate_closure(frame) for frame in range(167, 180)],
    }]
    direct.native_cache.clear()
    try:
        with integration.registered_lids(prepared), blink.shape_override(True):
            yield
    finally:
        direct.contract = original_contract
        direct.native_cache.clear()
        direct.native_cache.update(original_cache)


def compose_direct_frame(prepared: integration.PreparedRepairedActing, source_frame: int) -> tuple[np.ndarray, dict[str, Any]]:
    integrated = acting.compose_integrated_frame(prepared.integration, source_frame)
    metrics = integrated.metrics
    for key in ("changed_pixels_outside_transformed_phase39_support", "changed_pixels_in_transformed_face_feature_support", "changed_pixels_in_transformed_mug_support"):
        if metrics[key]:
            raise ValueError(f"integrated body damaged a protected region: {key}")
    closure = acting.phase35.production_blink_closure(prepared.integration.direct.contract, source_frame)
    if closure != blink.candidate_closure(source_frame):
        raise ValueError("scene did not use the accepted blink schedule")
    delivered = integration._editorial_frame(prepared, integrated.candidate, source_frame)
    if source_frame == 173 and acting._rgb_hash(delivered) != "155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40":
        raise ValueError("accepted full-close pixels changed in the integrated scene")
    return delivered, {
        **integration.editorial_window(source_frame),
        "blink_closure": closure, "body_active": bool(metrics["state_nonzero"]),
        "body_changed_pixels": int(metrics["changed_pixel_count"]),
        "protected_region_violations": 0,
    }


def scene_frames(prepared: integration.PreparedRepairedActing) -> Iterator[tuple[int, np.ndarray, dict[str, Any]]]:
    # Reuse the immutable lossless opening, not a retired delivery builder or
    # an encoded video. The existing reader verifies all 303 archived frames
    # and the archive digest, retaining only the 75 unaffected pour frames.
    reference = prepared.eye_contract["locks"]["phase36_candidate01_manifest"]
    manifest_path = REPO_ROOT / reference["path"]
    if _hash(manifest_path) != reference["sha256"]:
        raise ValueError("immutable opening inventory changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    retained, archive_audit = integration.eyes.v4.v3._read_picture_archive(prepared.eye_contract, manifest, set(range(1, 76)))
    for number in range(1, 76):
        pixels = retained.pop(number)
        yield number, pixels, {"output_frame": number, "pour_source_frame": number + 111, "original_pour_pixels_preserved": True, "archive_sha256": archive_audit["sha256"]}
    with accepted_lids(prepared):
        for source_frame in range(1, 229):
            pixels, metrics = compose_direct_frame(prepared, source_frame)
            yield source_frame + 75, pixels, metrics


def _run(command: list[str], log: Path) -> None:
    with log.open("wb") as destination:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=destination)


def _probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run([ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)], check=True, capture_output=True)
    return json.loads(result.stdout)


def _video_hash(path: Path, ffmpeg: str) -> str:
    return subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "hash", "-hash", "sha256", "-"], check=True, capture_output=True, text=True).stdout.strip()


def encoder_command(ffmpeg: str, destination: Path) -> list[str]:
    # Stream flags alone were insufficient with this FFmpeg build. Use the
    # project's previously verified frame-level setparams + x264 recipe.
    return [ffmpeg, "-nostdin", "-v", "error", "-n", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", "30", "-i", "pipe:0", "-an", "-vf", FRAME_FILTERS, "-c:v", "libx264", "-threads", "4", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv", "-x264-params", X264_PARAMS, "-video_track_timescale", "30000", "-movflags", "+faststart+write_colr", str(destination)]


def audit_media(output: Path, audio_path: Path, ffmpeg: str, ffprobe: str) -> dict[str, Any]:
    mov, mp4 = output / f"{NAME}.mov", output / f"{NAME}.mp4"
    probes = {path.suffix[1:]: _probe(path, ffprobe) for path in (mov, mp4)}
    for extension, probe in probes.items():
        video = next(stream for stream in probe["streams"] if stream["codec_type"] == "video")
        audio = next(stream for stream in probe["streams"] if stream["codec_type"] == "audio")
        if (int(video["nb_read_frames"]), int(video["width"]), int(video["height"]), Fraction(video["avg_frame_rate"])) != (303, 1920, 1080, Fraction(30)):
            raise ValueError(f"{extension} picture clock changed")
        if Fraction(video["duration_ts"]) * Fraction(video["time_base"]) != Fraction(101, 10):
            raise ValueError(f"{extension} picture duration changed")
        for field in ("color_space", "color_transfer", "color_primaries"):
            if video.get(field) != "bt709":
                raise ValueError(f"{extension} missing/incorrect {field}")
        if video.get("color_range") != "tv" or video.get("sample_aspect_ratio") != "1:1":
            raise ValueError(f"{extension} range or pixel aspect metadata changed")
        if (audio["sample_rate"], audio["channels"]) != ("48000", 2):
            raise ValueError(f"{extension} audio clock changed")
    if _video_hash(mov, ffmpeg) != _video_hash(mp4, ffmpeg):
        raise ValueError("portable preview re-encoded or changed the review picture")
    timestamps = json.loads(subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp", "-of", "json", str(mp4)], check=True, capture_output=True).stdout)["frames"]
    video = next(stream for stream in probes["mp4"]["streams"] if stream["codec_type"] == "video")
    if len(timestamps) != 303 or any(int(frame["best_effort_timestamp"]) * Fraction(video["time_base"]) != Fraction(index, 30) for index, frame in enumerate(timestamps)):
        raise ValueError("decoded preview frame timestamps have a gap, duplicate or offset")
    original, original_probe = picture._read_pcm24_wave(audio_path)
    pcm = subprocess.run([ffmpeg, "-v", "error", "-i", str(mov), "-map", "0:a:0", "-f", "s24le", "-acodec", "pcm_s24le", "-"], check=True, capture_output=True).stdout
    if hashlib.sha256(pcm).hexdigest() != original_probe["data_sha256"]:
        raise ValueError("MOV did not preserve the exact human-approved PCM")
    preview_audio = foley.audio.golden_sound._read_audio_f32(ffmpeg, mp4, channels=2, sample_rate=48000)
    if len(preview_audio) < len(original):
        raise ValueError("AAC preview truncated accepted audio")
    reference = original.astype(np.float64) / 8388608.0
    decoded = preview_audio[:len(original)].astype(np.float64)
    snr = 10 * np.log10(float(np.mean(reference**2)) / max(float(np.mean((reference - decoded)**2)), 1e-20))
    if snr < 40.0 or float(abs(decoded).max()) >= 1.0:
        raise ValueError(f"AAC preview quality/headroom failed: SNR {snr:.2f} dB")
    comparisons, retained = [], {}
    log = (output / "decode-video.log").open("wb")
    process = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(mp4), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=log)
    try:
        for number in range(1, 304):
            raw = process.stdout.read(1920 * 1080 * 3)
            if len(raw) != 1920 * 1080 * 3:
                raise ValueError(f"decoded video ended before F{number}")
            if number in SAMPLE_FRAMES:
                pixels = np.frombuffer(raw, dtype=np.uint8).reshape(1080, 1920, 3)
                with Image.open(output / "references" / f"f{number:03d}.png") as image:
                    reference_pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
                mse = float(np.mean((pixels.astype(np.float64) - reference_pixels.astype(np.float64))**2))
                value = 10 * np.log10(255**2 / max(mse, 1e-20))
                if value < 35.0:
                    raise ValueError(f"preview compression damaged sampled F{number}: {value:.2f} dB")
                comparisons.append({"frame": number, "rgb_psnr_db": float(value)})
                retained[number] = Image.fromarray(pixels.copy())
        if process.stdout.read(1) or process.wait() != 0:
            raise ValueError("decoded preview has extra frames or a decode failure")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()
        process.stdout.close()
        log.close()
    sheet = Image.new("RGB", (1440, 4 * 292), (14, 11, 9))
    draw = ImageDraw.Draw(sheet)
    for index, number in enumerate(KEY_FRAMES):
        x, y = (index % 3) * 480, (index // 3) * 292
        sheet.paste(retained[number].resize((480, 270), Image.Resampling.LANCZOS), (x, y + 22))
        draw.text((x + 8, y + 4), f"Decoded review F{number:03d} / {(number-1)/30:.2f}s", fill=(245, 227, 197))
    sheet.save(output / "decoded-scene-contact-sheet-v1.png")
    eye_frames = [retained[number].crop((500, 150, 1080, 550)) for number in range(242, 255)]
    durations = [round((index + 1) * 1000 / 30) - round(index * 1000 / 30) for index in range(13)]
    eye_frames[0].save(output / "decoded-blink-in-scene-30fps-v1.webp", save_all=True, append_images=eye_frames[1:], duration=durations, lossless=True, loop=0)
    return {
        "probes": probes, "all_303_frame_timestamps_exact": True,
        "mov_approved_audio_pcm_sha256": hashlib.sha256(pcm).hexdigest(), "mov_audio_bit_exact": True,
        "mp4_video_packets_equal_mov": True, "aac_preview_snr_db": float(snr),
        "aac_decoder_padding_samples": len(preview_audio) - len(original),
        "compression_sample_checks": comparisons,
        "note": "Every preview frame decoded; compression comparison is sampled, not a full pixel-reference audit. AAC is a convenience preview; MOV preserves the exact accepted PCM.",
    }


def build(output: Path = OUTPUT_DEFAULT, *, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite scene review: {output}")
    accepted = accepted_components()
    ffmpeg_bin, ffprobe_bin = shutil.which(ffmpeg), shutil.which(ffprobe)
    if not ffmpeg_bin or not ffprobe_bin:
        raise ValueError("installed local FFmpeg and FFprobe are required")
    prepared = integration.prepare_repaired_acting()
    audio_path = REPO_ROOT / accepted["audio"]["path"]
    prepared.audio_path = audio_path
    output.mkdir(parents=True)
    (output / "references").mkdir()
    rows = []
    frames = scene_frames(prepared)
    cache_path = output / "scene-rgb24-xor-v1.gz"
    cache = gzip.GzipFile(filename="", mode="wb", compresslevel=1, fileobj=cache_path.open("wb"), mtime=0)
    cache.write((json.dumps({"format": "phase42_rgb24_xor_previous_gzip_v1", "width": 1920, "height": 1080, "channels": 3, "frame_count": 303, "frame_bytes": 1920 * 1080 * 3, "component_acceptance_sha256": ACCEPTANCE_SHA256}, sort_keys=True) + "\n").encode("utf-8"))
    previous = np.zeros((1080, 1920, 3), dtype=np.uint8)
    try:
        for segment, (start, end) in enumerate(SHOTS, start=1):
            segment_path = output / f"shot{segment:02d}.mp4"
            command = encoder_command(ffmpeg_bin, segment_path)
            with (output / f"encode-shot{segment:02d}.log").open("wb") as log:
                encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
                try:
                    for expected in range(start, end + 1):
                        number, pixels, metrics = next(frames)
                        if number != expected:
                            raise ValueError("scene iterator changed frame order")
                        rows.append({**metrics, "rgb_sha256": acting._rgb_hash(pixels)})
                        cache.write(np.bitwise_xor(pixels, previous).tobytes())
                        previous = pixels
                        if number in SAMPLE_FRAMES:
                            Image.fromarray(pixels).save(output / "references" / f"f{number:03d}.png")
                        encoder.stdin.write(np.ascontiguousarray(pixels).tobytes())
                        if number % 30 == 0 or number == 303:
                            print(f"Rendered {number}/303 frames", flush=True)
                    encoder.stdin.close()
                    if encoder.wait() != 0:
                        raise ValueError(f"shot {segment} encoder failed; inspect its preserved log")
                finally:
                    if encoder.poll() is None:
                        encoder.terminate()
                        encoder.wait()
            print(f"Shot {segment} complete", flush=True)
        frames.close()
        cache.close()
        (output / "shots.ffconcat").write_text("ffconcat version 1.0\n" + "".join(f"file 'shot{index:02d}.mp4'\n" for index in range(1, 4)), encoding="utf-8", newline="\n")
        mov, mp4 = output / f"{NAME}.mov", output / f"{NAME}.mp4"
        _run([ffmpeg_bin, "-nostdin", "-v", "error", "-n", "-f", "concat", "-safe", "1", "-i", str(output / "shots.ffconcat"), "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "pcm_s24le", "-video_track_timescale", "30000", "-movflags", "+faststart+write_colr", str(mov)], output / "mux-mov.log")
        _run([ffmpeg_bin, "-nostdin", "-v", "error", "-n", "-i", str(mov), "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart+write_colr", str(mp4)], output / "mux-mp4.log")
        audit = audit_media(output, audio_path, ffmpeg_bin, ffprobe_bin)
        if accepted_components() != accepted:
            raise ValueError("accepted components changed during render")
        for name in ("ATTRIBUTION.md", "sources.json"):
            shutil.copyfile(foley.SOURCE_ROOT / name, output / name)
        shutil.copyfile(audio_path, output / "human-accepted-audio-v3.wav")
        _json(output / "source-frame-inventory-v1.json", rows)
        report = {
            "version": 1, "classification": "FULL_SCENE_REVIEW_HUMAN_PERFORMANCE_ACCEPTANCE_PENDING",
            "cash_cost": 0, "network_calls": 0, "cloud_render_jobs": 0,
            "implementation_sha256": _hash(Path(__file__)), "component_acceptance_sha256": ACCEPTANCE_SHA256,
            "component_acceptance": accepted, "frame_count": len(rows), "duration_seconds": 10.1,
            "hard_cut_output_frames": [76, 238], "rendered_blink_full_close_frames": [row["output_frame"] for row in rows if row.get("blink_closure") == 1.0],
            "body_acting_active_frames": sum(row.get("body_active", False) for row in rows),
            "all_75_pour_frames_match_original_pixels": all(row["original_pour_pixels_preserved"] for row in rows[:75]),
            "approved_audio_wav_sha256": _hash(audio_path), "audit": audit,
            "lossless_render_cache": {"file": cache_path.name, "sha256": _hash(cache_path), "bytes": cache_path.stat().st_size, "published_in_git": False},
            "integrated_performance_human_accepted": False, "production_release_allowed": False,
            "artifacts": {path.name: {"sha256": _hash(path), "bytes": path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file() and path.suffix in {".mov", ".mp4", ".wav", ".png", ".webp", ".json", ".md"}},
        }
        _json(output / "phase42-integrated-scene-review-report-v1.json", report)
        return report
    except Exception as exc:
        frames.close()
        cache.close()
        _json(output / "failure.json", {"error": str(exc), "rendered_frames": len(rows), "artifacts_preserved": True, "production_release_allowed": False})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    report = build(args.output)
    print(json.dumps({"frames": report["frame_count"], "audit": {key: value for key, value in report["audit"].items() if key not in {"probes", "compression_sample_checks"}}, "human_performance_accepted": False}, indent=2))


if __name__ == "__main__":
    main()
