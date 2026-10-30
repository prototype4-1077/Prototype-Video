"""Render a new, audio-clocked porch scene with the existing June raster rig.

New authored performance, not an approval of new dialogue/acting. Historical
contracts and passed films remain unchanged. This adapter creates a runtime
view of validated source assets; it never rewrites or relaxes their loaders.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from fractions import Fraction
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_working_model as bank
from pipeline.cartoon_viseme_atlas import performance_viseme_plan
from pipeline.cartoon_hero_scene import load_body_motion_contract, MOTION_CHANNELS


ROOT = Path(__file__).resolve().parents[1]
scene, acting, blink = bank.scene, bank.scene.acting, bank.scene.blink
HERO = ROOT / "concept/style_frames/june_golden_scene_gs070_resolution_v1.json"
AAC_BITRATE = "512k"


def locked_asset(item: dict) -> Path:
    path = (ROOT / item["path"]).resolve()
    if not path.is_relative_to(ROOT.resolve()) or scene._hash(path) != item["sha256"]:
        raise ValueError("Scene asset missing, changed, or outside the project")
    return path


def compile_scene(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("version") != 1 or config.get("character") != "june_oxley" or config.get("mode") != "new_performance_review_only":
        raise ValueError("Explicit June prototype performance scope required")
    if config.get("production_release_allowed") is not False:
        raise ValueError("New authored performance cannot grant production release")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", config.get("id", "")):
        raise ValueError("Scene id must be lowercase kebab-case")
    if config.get("hand_pose") != "resting_source_pose":
        raise ValueError("This adapter currently supports the resting source hand only")
    audio, cues = locked_asset(config["audio"]), locked_asset(config["cues"])
    samples, probe = scene.picture._read_pcm24_wave(audio)
    if probe["sample_rate"] != 48000 or probe["channels"] not in (1, 2) or len(samples) % 1600:
        raise ValueError("Audio must be 48kHz mono/stereo PCM24, aligned to 30fps")
    count = len(samples) // 1600
    if not 30 <= count <= 1800 or not np.any(samples):
        raise ValueError("Authored scene needs non-silent audio and 1-60 seconds")
    payload = json.loads(cues.read_text(encoding="utf-8"))
    if payload["metadata"].get("sourceAudioSha256") != config["audio"]["sha256"] or payload["metadata"].get("dialogueHint") != config.get("dialogue"):
        raise ValueError("Cues must belong to this exact audio and dialogue")
    metadata, visemes = performance_viseme_plan(cues, fps=30, transition_frames=2)
    if len(visemes) != count or not math.isclose(metadata["duration_seconds"], count / 30, abs_tol=1e-9):
        raise ValueError("Audio, cues and scene have different clocks")
    if len(metadata["shapes"]) < 3:
        raise ValueError("Speech needs a nontrivial mouth plan")
    # A one-second real quiet tail, not a static hold that interrupts speech.
    if np.any(samples[-48000:]) or any(row["to_shape"] != "X" for row in visemes[-30:]):
        raise ValueError("Scene needs one second of digital silence and a resting mouth at the end")
    keys = config.get("motion_keys", [])
    bounds = json.loads(HERO.read_text(encoding="utf-8"))["motion_bounds"]
    phases = [row.get("phase") for row in keys]
    if len(keys) < 2 or phases != sorted(set(phases)) or phases[0] != 0 or phases[-1] != 1:
        raise ValueError("Motion keys must have ordered unique phases from zero to one")
    keyframes = []
    for row in keys:
        values = {key: float(row.get(key, 0)) for key in MOTION_CHANNELS}
        for key, value in values.items():
            if not math.isfinite(value) or not bounds[key][0] <= value <= bounds[key][1]:
                raise ValueError(f"Motion outside inherited rig bounds: {key}")
        # Do not revive the historical rectangular shoulder/hand warp here.
        if values["shoulder_x_px"] or values["breath_y_px"]:
            raise ValueError("New scene torso/hand acting needs a separate authored rig plan")
        keyframes.append({"frame": 1 + round(float(row["phase"]) * (count - 1)), **values})
    if len({row["frame"] for row in keyframes}) != len(keyframes):
        raise ValueError("Motion keys collapse on this scene clock")
    starts, occupied = [], set()
    for seconds in config.get("blink_starts_seconds", []):
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
            raise ValueError("Blink start must be finite seconds")
        start = round(seconds * 30) + 1
        span = set(range(start, start + 13))
        if min(span) < 1 or max(span) > count or occupied & span:
            raise ValueError("Blink curves overlap or leave the scene")
        starts.append(start)
        occupied |= span
    return {"config": config, "audio": audio, "cues": cues, "samples": samples,
            "frame_count": count, "visemes": bank.mouth.translated_plan(visemes),
            "keyframes": keyframes, "blink_starts": starts, "recipe_sha256": scene._hash(path)}


def runtime_prepared(source, plan: dict, output: Path):
    """Independent runtime descriptors, never passed off as original contracts."""
    count = plan["frame_count"]
    direct = source.integration.direct
    motion_spec = {"contract_version": 1, "plate_id": direct.scene_contract["plate_id"],
                   "performance_id": plan["config"]["id"], "performance_version": "runtime-v1",
                   "fps": 30, "frame_count": count, "duration_seconds": count / 30,
                   "interpolation": "cubic_ease", "keyframes": plan["keyframes"],
                   "secondary_motion": direct.motion_metadata["secondary_motion"]}
    motion_path = output / "compiled-motion-v1.json"
    scene._json(motion_path, motion_spec)
    motion_meta, motion = load_body_motion_contract(motion_path, hero_contract=direct.scene_contract)
    contract = deepcopy(direct.contract)
    contract.update({"runtime_scene_id": plan["config"]["id"], "runtime_performance_human_accepted": False})
    contract["clock"].update({"frame_count": count, "duration_seconds": count / 30, "audio_sample_count": count * 1600})
    contract["performance"]["blink_curves"] = [{"id": f"reused-v3-shape-{start}", "frames": list(range(start, start + 13)),
        "closures": [blink.candidate_closure(blink.CURVE_START + i) for i in range(13)]} for start in plan["blink_starts"]]
    candidate_direct = replace(direct, contract=contract, visemes=plan["visemes"], motion=motion,
                               motion_metadata=motion_meta, native_cache={}, adapter_cache={})
    body = source.integration.body
    body_contract = deepcopy(body.contract)
    body_contract["clock"].update({"frame_count": count, "duration_seconds": count / 30})
    candidate_body = replace(body, contract=body_contract,
        states=[{channel: 0.0 for channel in body.contract["motion_channels"]} for _ in range(count)])
    integration_contract = deepcopy(source.integration.contract)
    integration_contract["clock"]["frame_count"] = count
    integration_contract["runtime_performance_human_accepted"] = False
    return replace(source, integration=replace(source.integration, contract=integration_contract,
                   direct=candidate_direct, body=candidate_body), audio_path=plan["audio"])


def frames(prepared, plan: dict):
    with scene.integration.registered_lids(prepared), blink.shape_override(True):
        for number in range(1, plan["frame_count"] + 1):
            composed = acting.compose_integrated_frame(prepared.integration, number)
            if any(composed.metrics[key] for key in ("changed_pixels_outside_transformed_phase39_support",
                   "changed_pixels_in_transformed_face_feature_support", "changed_pixels_in_transformed_mug_support")):
                raise ValueError("Runtime scene violated a protected region")
            yield number, composed.candidate, {"frame": number, "pts": [number - 1, 30],
                "mouth": plan["visemes"][number - 1], "blink_closure": acting.phase35.production_blink_closure(prepared.integration.direct.contract, number),
                "protected_region_violations": 0, "rgb_sha256": acting._rgb_hash(composed.candidate)}


def audit(output: Path, plan: dict, reference_frames: list[int]) -> dict:
    mov, mp4 = output / "scene.mov", output / "scene.mp4"
    count = plan["frame_count"]
    for path in (mov, mp4):
        probe = scene._probe(path, "ffprobe")
        video = next(row for row in probe["streams"] if row["codec_type"] == "video")
        audio = next(row for row in probe["streams"] if row["codec_type"] == "audio")
        if (int(video["nb_read_frames"]), video["width"], video["height"], Fraction(video["avg_frame_rate"])) != (count, 1920, 1080, Fraction(30)):
            raise ValueError("New scene export changed its picture clock")
        if Fraction(video["duration_ts"]) * Fraction(video["time_base"]) != Fraction(count, 30):
            raise ValueError("New scene export changed duration")
        if any(video.get(key) != "bt709" for key in ("color_space", "color_transfer", "color_primaries")) or video.get("color_range") != "tv" or video.get("sample_aspect_ratio") != "1:1":
            raise ValueError("New scene color/aspect metadata changed")
        if (audio["sample_rate"], audio["channels"]) != ("48000", 2):
            raise ValueError("New scene export changed audio geometry")
    video = next(row for row in scene._probe(mp4, "ffprobe")["streams"] if row["codec_type"] == "video")
    pts = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp", "-of", "json", str(mp4)], capture_output=True, check=True).stdout)["frames"]
    if len(pts) != count or any(int(row["best_effort_timestamp"]) * Fraction(video["time_base"]) != Fraction(i, 30) for i, row in enumerate(pts)):
        raise ValueError("Export has missing/duplicate/offset timestamps")
    expected = plan["samples"]
    if expected.shape[1] == 1:
        expected = np.repeat(expected, 2, axis=1)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mov), "-map", "0:a:0", "-f", "s32le", "-"], check=True, capture_output=True).stdout
    decoded = np.frombuffer(raw, np.int32).reshape(-1, 2) // 256
    if not np.array_equal(decoded, expected):
        raise ValueError("MOV did not preserve exact dialogue PCM (mono duplicated to stereo)")
    if scene._video_hash(mov, "ffmpeg") != scene._video_hash(mp4, "ffmpeg"):
        raise ValueError("MP4 re-encoded the picture")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp4), "-map", "0:a:0", "-f", "f32le", "-"], check=True, capture_output=True).stdout
    decoded = np.frombuffer(raw, np.float32).reshape(-1, 2)
    if len(decoded) < len(expected):
        raise ValueError("AAC output truncated")
    ref = expected.astype(np.float64) / 8388608
    delta = ref - decoded[:len(ref)]
    snr = float(10 * np.log10(np.mean(ref**2) / max(np.mean(delta**2), 1e-20)))
    if snr < 40 or np.abs(decoded[:len(ref)]).max() >= 1:
        raise ValueError("AAC preview quality/headroom failed")
    capture, comparisons, retained, decoded_inventory = cv2.VideoCapture(str(mp4)), [], {}, []
    try:
        for number in range(1, count + 1):
            ok, pixels = capture.read()
            if not ok:
                raise ValueError(f"New scene ended before frame{number}")
            pixels = cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)
            decoded_inventory.append({"frame": number, "rgb_sha256": acting._rgb_hash(pixels),
                                      "hash_domain": "decoded_preview_rgb24_not_source_pixels"})
            if number in reference_frames:
                with Image.open(output / "references" / f"f{number:04d}.png") as image:
                    reference = np.array(image.convert("RGB"))
                mse = np.mean((pixels.astype(np.float64) - reference)**2)
                psnr = float(10 * np.log10(255**2 / max(mse, 1e-20)))
                if psnr < 38:
                    raise ValueError("New scene sampled compression quality failed")
                comparisons.append({"frame": number, "psnr_db": psnr})
                retained[number] = Image.fromarray(pixels)
        if capture.read()[0]:
            raise ValueError("New scene has extra frames")
    finally:
        capture.release()
    sheet = Image.new("RGB", (1440, math.ceil(len(retained)/3)*292), (14,11,9))
    draw = ImageDraw.Draw(sheet)
    for i, (number, image) in enumerate(retained.items()):
        x, y = i%3*480, i//3*292
        sheet.paste(image.resize((480,270), Image.Resampling.LANCZOS), (x,y+22))
        draw.text((x+5,y+4), f"Decoded F{number:04d} / {(number-1)/30:.2f}s", fill="white")
    sheet.save(output / "decoded-contact-sheet.png")
    scene._json(output / "decoded-frame-inventory.json", decoded_inventory)
    return {"all_frame_timestamps_exact": True, "all_frames_decoded": count,
            "mov_source_audio_exact_with_mono_stereo_duplication": True,
            "mp4_picture_packets_equal_mov": True, "aac_snr_db": snr,
            "aac_padding_samples": len(decoded)-len(expected), "compression_samples": comparisons}


def build(recipe: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Preserve existing scene output: {output}")
    approved = bank.approval()
    plan = compile_scene(recipe)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise FileNotFoundError("Local FFmpeg/FFprobe required")
    source = scene.integration.prepare_repaired_acting()
    output.mkdir(parents=True)
    (output / "references").mkdir()
    encoder = None
    stream = None
    try:
        prepared = runtime_prepared(source, plan, output)
        count = plan["frame_count"]
        samples = sorted({1, count//4, count//2, count*3//4, count, *[start+5 for start in plan["blink_starts"]]})
        inventory = []
        with (output / "encode.log").open("wb") as log:
            encoder = subprocess.Popen(scene.encoder_command("ffmpeg", output / "silent.mp4"), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
            stream = frames(prepared, plan)
            for number, pixels, metrics in stream:
                inventory.append(metrics)
                if number in samples:
                    Image.fromarray(pixels).save(output / "references" / f"f{number:04d}.png")
                encoder.stdin.write(np.ascontiguousarray(pixels).tobytes())
                if number % 30 == 0 or number == count:
                    print(f"New scene: {number}/{count} frames", flush=True)
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise ValueError("New scene encoder failed; preserved encode.log")
        # Preserve native source-frame provenance even if a later media gate fails.
        scene._json(output / "frame-inventory.json", inventory)
        audio_options = ["-af", "pan=stereo|c0=c0|c1=c0"] if plan["samples"].shape[1] == 1 else ["-ac", "2"]
        scene._run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-i", str(output / "silent.mp4"), "-i", str(plan["audio"]), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "pcm_s24le", *audio_options, "-movflags", "+faststart+write_colr", str(output / "scene.mov")], output / "mux-mov.log")
        scene._run(["ffmpeg", "-nostdin", "-v", "error", "-n", "-i", str(output / "scene.mov"), "-c:v", "copy", "-c:a", "aac", "-b:a", AAC_BITRATE, "-movflags", "+faststart+write_colr", str(output / "scene.mp4")], output / "mux-mp4.log")
        measured = audit(output, plan, samples)
        if compile_scene(recipe)["recipe_sha256"] != plan["recipe_sha256"] or bank.approval() != approved:
            raise ValueError("Recipe or frozen components changed during render")
        scene._json(output / "frame-inventory.json", inventory)
        report = {"classification": "NEW_AUDIO_CLOCKED_AUTHORED_SCENE_TECHNICALLY_COMPLETE_HUMAN_REVIEW_PENDING",
                  "scene_id": plan["config"]["id"], "recipe_sha256": plan["recipe_sha256"],
                  "frame_count": count, "duration_seconds": count/30, "fps": 30,
                  "source_built": True, "old_scene_cache_used": False, "cash_cost": 0, "network_calls": 0,
                  "implementation_sha256": scene._hash(Path(__file__)), "audio": plan["config"]["audio"],
                  "cues": plan["config"]["cues"], "runtime_contracts_are_new_unapproved_views": True,
                  "voice_status": "LOCAL_SCRATCH_NON_CANONICAL_NOT_HUMAN_ACCEPTED", "new_performance_human_accepted": False,
                  "production_release_allowed": False, "main_branch_merge_allowed": False,
                  "hand_acting": "source resting pose; no new hand deformation", "audit": measured,
                  "limits": ["One porch view and source pose; no new full-body action or arbitrary camera angle.",
                             "New dialogue/head/camera/blink timings, not reuse of the old accepted performance verdict.",
                             "Torso/hand action authoring and final voice/acting remain open."],
                  "artifacts": {path.name: scene._hash(path) for path in output.iterdir() if path.is_file()}}
        scene._json(output / "new-scene-report.json", report)
        print(f"New authored scene ready: {output / 'scene.mp4'}", flush=True)
        return report
    except BaseException as exc:
        scene._json(output / "failure.json", {"error": str(exc), "artifacts_preserved": True, "production_release_allowed": False})
        raise
    finally:
        if stream is not None:
            stream.close()
        if encoder is not None and encoder.poll() is None:
            encoder.terminate()
            encoder.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        plan = compile_scene(args.scene)
        bank.approval()
        print(json.dumps({"scene_id": plan["config"]["id"], "frames": plan["frame_count"],
                          "duration_seconds": plan["frame_count"]/30, "new_performance_approved": False}, indent=2))
    else:
        destination = args.output or ROOT / "outputs/edit" / ("authored-june-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
        build(args.scene.resolve(), destination.resolve())


if __name__ == "__main__":
    main()
