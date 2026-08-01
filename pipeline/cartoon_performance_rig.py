from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

import cv2

from pipeline.cartoon_golden_sound import _loudnorm_measure
from pipeline.cartoon_pose_layers import render_pose_layer_sequence
from pipeline.cartoon_pour_layers import render_pour_layer_sequence
from pipeline.cartoon_resolution_scene import render_resolution_scene


CONTRACT_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHANNELS = {
    "body_pose",
    "root_contact",
    "hand_contact",
    "prop_pose",
    "liquid",
    "viseme",
    "expression",
    "head",
    "camera",
    "atmosphere",
}
EXPECTED_ACTION_CLASSES = {
    "broad_body_mechanics",
    "constrained_prop_mechanics",
    "close_speaking_performance",
}
EXPECTED_ADAPTERS = {
    "registered_pose_layers",
    "registered_pour_layers",
    "registered_feature_atlases",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _asset_path(value: str) -> Path:
    path = (REPO_ROOT / value).resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise ValueError(f"rig asset escapes repository: {value}")
    return path


def _pinned_path(spec: dict[str, Any], label: str) -> Path:
    path = _asset_path(str(spec.get("path", "")))
    expected = str(spec.get("sha256", ""))
    if not path.is_file():
        raise FileNotFoundError(f"rig {label} is missing: {path}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or _sha256(path) != expected:
        raise ValueError(f"rig {label} failed its SHA-256 gate: {path}")
    return path


def _resolve_executable(value: str | Path) -> str:
    text = str(value)
    candidate = Path(text)
    if candidate.is_file():
        return str(candidate.resolve())
    resolved = shutil.which(text)
    if not resolved:
        raise FileNotFoundError(f"executable not found: {value}")
    return resolved


def _run(args: list[Any], *, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(value) for value in args],
        check=True,
        capture_output=capture_output,
        text=True,
    )


def compile_action_spans(contract: dict[str, Any]) -> list[dict[str, Any]]:
    actions = {str(action["id"]): action for action in contract["actions"]}
    cursor = 1
    spans: list[dict[str, Any]] = []
    for identifier in contract["sequence"]["action_ids"]:
        action = actions[str(identifier)]
        count = int(action["frame_count"])
        source_start, source_end = (int(value) for value in action["source_master_frames"])
        spans.append(
            {
                "action_id": action["id"],
                "action_class": action["action_class"],
                "view_id": action["view_id"],
                "output_start_frame": cursor,
                "output_end_frame": cursor + count - 1,
                "frame_count": count,
                "source_master_start_frame": source_start,
                "source_master_end_frame": source_end,
            }
        )
        cursor += count
    return spans


def compile_caption_cues(contract: dict[str, Any]) -> list[dict[str, Any]]:
    sound_path = _pinned_path(contract["sound"]["contract"], "sound contract")
    sound = json.loads(sound_path.read_text(encoding="utf-8"))
    cues: list[dict[str, Any]] = []
    for span in compile_action_spans(contract):
        source_start = int(span["source_master_start_frame"])
        source_end = int(span["source_master_end_frame"])
        output_start = int(span["output_start_frame"])
        for cue in sound.get("dialogue_cues", []):
            cue_start, cue_end = int(cue["start_frame"]), int(cue["end_frame"])
            overlaps = cue_end >= source_start and cue_start <= source_end
            contained = cue_start >= source_start and cue_end <= source_end
            if overlaps and not contained:
                raise ValueError(f"rig action cuts through dialogue cue: {cue['id']}")
            if contained:
                cues.append(
                    {
                        "id": cue["id"],
                        "text": cue["text"],
                        "action_id": span["action_id"],
                        "start_frame": output_start + cue_start - source_start,
                        "end_frame": output_start + cue_end - source_start,
                    }
                )
    if len(cues) != int(contract["sound"]["expected_caption_count"]):
        raise ValueError("rig proof caption count does not match its contract")
    previous_end = 0
    for cue in cues:
        if int(cue["start_frame"]) <= previous_end:
            raise ValueError("rig proof captions overlap after frame rebasing")
        previous_end = int(cue["end_frame"])
    return cues


def load_performance_rig_contract(path: str | Path) -> tuple[dict[str, Any], dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if int(contract.get("contract_version", 0)) != CONTRACT_VERSION:
        raise ValueError("unsupported performance rig contract version")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("performance rig must belong to June Oxley")
    if int(contract.get("cash_cost", -1)) != 0 or contract.get("paid_runtime_dependency") is not False:
        raise ValueError("performance rig must remain zero cash at runtime")

    output = contract.get("output") or {}
    if (
        int(output.get("width", 0)),
        int(output.get("height", 0)),
        int(output.get("fps", 0)),
        int(output.get("frame_count", 0)),
        float(output.get("duration_seconds", 0.0)),
    ) != (1920, 1080, 30, 657, 21.9):
        raise ValueError("performance rig proof must lock the exact 657-frame 1080p clock")
    if (
        output.get("codec"),
        output.get("pixel_format"),
        output.get("audio_codec"),
        int(output.get("audio_sample_rate", 0)),
        int(output.get("audio_channels", 0)),
        output.get("caption_codec"),
    ) != ("h264", "yuv420p", "aac", 48000, 2, "mov_text"):
        raise ValueError("performance rig media delivery contract is incomplete")

    channel_ids = [str(channel.get("id")) for channel in contract.get("semantic_channels", [])]
    if len(channel_ids) != len(set(channel_ids)) or set(channel_ids) != EXPECTED_CHANNELS:
        raise ValueError("performance rig semantic channel set is incomplete")
    required_channels = set((contract.get("quality_gate") or {}).get("required_semantic_channels", []))
    if required_channels != EXPECTED_CHANNELS:
        raise ValueError("performance rig quality gate does not require every semantic channel")

    assets: dict[str, Path] = {"canonical_identity": _pinned_path(contract["canonical_identity"], "identity")}
    views = contract.get("views") or []
    view_by_id = {str(view.get("id")): view for view in views}
    if len(view_by_id) != 3 or {str(view.get("adapter")) for view in views} != EXPECTED_ADAPTERS:
        raise ValueError("performance rig must provide all three view adapters")
    for view in views:
        identifier = str(view["id"])
        assets[f"{identifier}:contract"] = _pinned_path(view["contract"], f"{identifier} contract")
        channels = set(str(value) for value in view.get("channels", []))
        if not channels or not channels.issubset(EXPECTED_CHANNELS):
            raise ValueError(f"view has invalid semantic channels: {identifier}")
        for name, spec in (view.get("dependencies") or {}).items():
            assets[f"{identifier}:{name}"] = _pinned_path(spec, f"{identifier} {name}")

    actions = contract.get("actions") or []
    action_by_id = {str(action.get("id")): action for action in actions}
    sequence = contract.get("sequence") or {}
    action_ids = [str(value) for value in sequence.get("action_ids", [])]
    if len(action_ids) != 3 or len(set(action_ids)) != 3 or set(action_ids) != set(action_by_id):
        raise ValueError("performance rig sequence must use each action exactly once")
    if {str(action.get("action_class")) for action in actions} != EXPECTED_ACTION_CLASSES:
        raise ValueError("performance rig action-class coverage is incomplete")
    if set((contract.get("quality_gate") or {}).get("required_action_classes", [])) != EXPECTED_ACTION_CLASSES:
        raise ValueError("performance rig gate does not require all action classes")
    for action in actions:
        identifier = str(action["id"])
        if str(action.get("view_id")) not in view_by_id:
            raise ValueError(f"action references an unknown view: {identifier}")
        count = int(action.get("frame_count", 0))
        source_start, source_end = (int(value) for value in action.get("source_master_frames", [0, 0]))
        if count <= 0 or source_end - source_start + 1 != count:
            raise ValueError(f"action source clock does not match its output clock: {identifier}")
        review = [int(value) for value in action.get("review_local_frames", [])]
        if not review or min(review) < 1 or max(review) > count or review != sorted(set(review)):
            raise ValueError(f"action review frames are invalid: {identifier}")
        channels = set(str(value) for value in action.get("required_channels", []))
        view_channels = set(str(value) for value in view_by_id[str(action["view_id"])]["channels"])
        if not channels or not channels.issubset(view_channels):
            raise ValueError(f"action asks its view for unsupported channels: {identifier}")

    spans = compile_action_spans(contract)
    if spans[-1]["output_end_frame"] != 657:
        raise ValueError("performance rig actions do not cover all 657 output frames")
    expected_cuts = [int(span["output_start_frame"]) for span in spans[1:]]
    if [int(value) for value in sequence.get("cut_frames", [])] != expected_cuts:
        raise ValueError("performance rig cuts do not match compiled action spans")
    if (
        sequence.get("transition") != "hard_cuts_only"
        or sequence.get("cross_dissolve_allowed") is not False
        or sequence.get("optical_flow_allowed") is not False
        or sequence.get("implicit_retiming_allowed") is not False
    ):
        raise ValueError("performance rig must prohibit interpolation between view adapters")

    assets["sound_contract"] = _pinned_path(contract["sound"]["contract"], "sound contract")
    loudness = contract["sound"].get("delivery_loudness") or {}
    if (
        float(loudness.get("target_lufs_i", 0.0)) != -16.0
        or float(loudness.get("tolerance_lu", 0.0)) != 1.0
        or float(loudness.get("maximum_true_peak_dbtp", 0.0)) != -1.0
        or loudness.get("lra_is_informational_for_excerpt") is not True
    ):
        raise ValueError("performance rig delivery-loudness contract is incomplete")
    compile_caption_cues(contract)
    return contract, assets


def _format_srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000.0)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _write_captions(contract: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    fps = int(contract["output"]["fps"])
    cues = compile_caption_cues(contract)
    blocks: list[str] = []
    for index, cue in enumerate(cues, start=1):
        start = (int(cue["start_frame"]) - 1) / fps
        end = int(cue["end_frame"]) / fps
        blocks.append(f"{index}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{cue['text']}")
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return cues


def _media_probe(ffprobe: str, path: Path) -> dict[str, Any]:
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,pix_fmt,width,height,r_frame_rate,nb_frames,sample_rate,channels:format=duration,size",
            "-of",
            "json",
            path,
        ]
    )
    return json.loads(result.stdout)


def _stream_hash(ffmpeg: str, path: Path, selector: str) -> str:
    result = _run([ffmpeg, "-v", "error", "-i", path, "-map", selector, "-c", "copy", "-f", "hash", "-hash", "sha256", "-"])
    match = re.search(r"SHA256=([0-9a-f]{64})", result.stdout)
    if not match:
        raise RuntimeError(f"unable to hash stream {selector}: {path}")
    return match.group(1)


def _validate_sound_master(contract: dict[str, Any], video: Path, report_path: Path) -> dict[str, Any]:
    if not video.is_file() or not report_path.is_file():
        raise FileNotFoundError("Phase 26 sound master and report are required")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    final = report.get("final") or {}
    if (
        report.get("gate") != contract["sound"]["source_gate"]
        or int(final.get("frame_count", 0)) != 1164
        or float(final.get("duration_seconds", 0.0)) != 38.8
        or final.get("audio_codec") != "aac"
        or int(final.get("audio_sample_rate", 0)) != 48000
        or int(final.get("audio_channels", 0)) != 2
        or final.get("subtitle_codec") != "mov_text"
        or _sha256(video) != str(final.get("sha256"))
    ):
        raise ValueError("Phase 26 sound master failed the reusable-rig source gate")
    return report


def _render_action_clips(
    contract: dict[str, Any],
    assets: dict[str, Path],
    output: Path,
    *,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, dict[str, Any]]:
    views = {str(view["id"]): view for view in contract["views"]}
    results: dict[str, dict[str, Any]] = {}
    for action in contract["actions"]:
        identifier = str(action["id"])
        view = views[str(action["view_id"])]
        action_dir = output / "actions" / identifier.lower()
        adapter = str(view["adapter"])
        if adapter == "registered_pose_layers":
            report = render_pose_layer_sequence(
                assets[f"{view['id']}:contract"],
                action_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            video = action_dir / "june-gs030-layered-stand.mp4"
            if report["gate"] != "registered_layered_body_mechanics" or report["audio"]["included"] is not False:
                raise RuntimeError("wide-body rig adapter failed its action gate")
        elif adapter == "registered_pour_layers":
            report = render_pour_layer_sequence(
                assets[f"{view['id']}:contract"],
                action_dir,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
            )
            video = action_dir / "june-gs060-layered-pour.mp4"
            if report["gate"] != "registered_pour_contact_and_liquid" or report["audio"]["included"] is not False:
                raise RuntimeError("table-action rig adapter failed its action gate")
        elif adapter == "registered_feature_atlases":
            report = render_resolution_scene(
                assets[f"{view['id']}:contract"],
                assets[f"{view['id']}:viseme_atlas"],
                assets[f"{view['id']}:viseme_cues"],
                assets[f"{view['id']}:expression_atlas"],
                assets[f"{view['id']}:expression_cues"],
                assets[f"{view['id']}:body_motion"],
                action_dir,
                ffmpeg=ffmpeg,
            )
            video = action_dir / "june-gs070-resolution.mp4"
            if report["gate"] != "gs070_registered_resolution_production_pixels" or report["audio"] is not None:
                raise RuntimeError("close-hero rig adapter failed its action gate")
        else:  # guarded by contract validation
            raise AssertionError(adapter)
        if int(report["frame_count"]) != int(action["frame_count"]):
            raise RuntimeError(f"rig adapter rendered the wrong frame count: {identifier}")
        results[identifier] = {"video": video, "report": report, "adapter": adapter, "view_id": view["id"]}
    return results


def _write_concat_file(action_results: dict[str, dict[str, Any]], sequence: list[str], path: Path) -> None:
    lines: list[str] = []
    for identifier in sequence:
        value = action_results[identifier]["video"].resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{value}'")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _render_rebased_audio(
    contract: dict[str, Any],
    source: Path,
    output: Path,
    *,
    ffmpeg: str,
) -> list[dict[str, Any]]:
    spans = compile_action_spans(contract)
    count = len(spans)
    split_labels = "".join(f"[source_{index}]" for index in range(count))
    filters = [f"[0:a:0]asplit={count}{split_labels}"]
    fade = int(contract["sound"]["boundary_fades_ms"]) / 1000.0
    for index, span in enumerate(spans):
        start = (int(span["source_master_start_frame"]) - 1) / 30.0
        duration = int(span["frame_count"]) / 30.0
        filters.append(
            f"[source_{index}]atrim=start={start:.9f}:duration={duration:.9f},"
            f"asetpts=PTS-STARTPTS,afade=t=in:st=0:d={fade:.6f},"
            f"afade=t=out:st={max(0.0, duration - fade):.9f}:d={fade:.6f}[action_{index}]"
        )
    concat_inputs = "".join(f"[action_{index}]" for index in range(count))
    duration = float(contract["output"]["duration_seconds"])
    filters.append(
        f"{concat_inputs}concat=n={count}:v=0:a=1,aresample=48000,"
        f"atrim=end={duration:.9f},apad=whole_dur={duration:.9f}[audio_out]"
    )
    _run(
        [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            source,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[audio_out]",
            "-c:a",
            "pcm_s24le",
            "-ar",
            "48000",
            "-ac",
            "2",
            output,
        ]
    )
    return spans


def _review_encoded_video(video: Path, review_frames: list[int], review_dir: Path) -> dict[str, Any]:
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()
    wanted = set(review_frames)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"unable to decode rig proof: {video}")
    decoded = 0
    sharpness: dict[str, float] = {}
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        decoded += 1
        if decoded in wanted:
            path = review_dir / f"frame_{decoded:04d}.png"
            if not cv2.imwrite(str(path), frame):
                raise RuntimeError(f"unable to write rig review frame: {path}")
            sharpness[str(decoded)] = round(float(cv2.Laplacian(frame, cv2.CV_64F).var()), 6)
    capture.release()
    if decoded != 657 or set(int(value) for value in sharpness) != wanted:
        raise RuntimeError("rig proof failed its full-decode or review-frame gate")
    return {
        "decoded_frame_count": decoded,
        "review_frame_count": len(review_frames),
        "minimum_encoded_laplacian_variance": min(sharpness.values()),
        "review_laplacian_variance": sharpness,
    }


def render_performance_rig_proof(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    sound_master: str | Path,
    sound_report: str | Path,
    ffmpeg: str | Path = "ffmpeg",
    ffprobe: str | Path = "ffprobe",
) -> dict[str, Any]:
    contract, assets = load_performance_rig_contract(contract_path)
    ffmpeg_bin = _resolve_executable(ffmpeg)
    ffprobe_bin = _resolve_executable(ffprobe)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    sound_video = Path(sound_master).resolve()
    sound_report_path = Path(sound_report).resolve()
    source_sound_report = _validate_sound_master(contract, sound_video, sound_report_path)

    action_results = _render_action_clips(contract, assets, output, ffmpeg=ffmpeg_bin, ffprobe=ffprobe_bin)
    concat_file = output / "action-concat.txt"
    _write_concat_file(action_results, contract["sequence"]["action_ids"], concat_file)
    video_only = output / "june-performance-rig-proof.video-only.mp4"
    partial_video = output / "june-performance-rig-proof.video-only.partial.mp4"
    partial_video.unlink(missing_ok=True)
    _run(
        [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-fflags",
            "+genpts",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file,
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            "-movflags",
            "+faststart",
            partial_video,
        ]
    )
    partial_video.replace(video_only)

    audio = output / "june-performance-rig-proof-audio.wav"
    spans = _render_rebased_audio(contract, sound_video, audio, ffmpeg=ffmpeg_bin)
    captions = output / "june-performance-rig-proof.srt"
    caption_cues = _write_captions(contract, captions)

    final = output / "june-performance-rig-proof.mp4"
    partial_final = output / "june-performance-rig-proof.partial.mp4"
    partial_final.unlink(missing_ok=True)
    _run(
        [
            ffmpeg_bin,
            "-y",
            "-v",
            "error",
            "-i",
            video_only,
            "-i",
            audio,
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
            "256k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:s",
            "mov_text",
            "-metadata:s:a:0",
            "language=eng",
            "-metadata:s:s:0",
            "language=eng",
            "-metadata",
            "title=June Oxley Performance Rig Proof",
            "-t",
            f"{contract['output']['duration_seconds']:.6f}",
            "-movflags",
            "+faststart",
            partial_final,
        ]
    )
    partial_final.replace(final)
    _run([ffmpeg_bin, "-v", "error", "-i", final, "-f", "null", "-"])

    probe = _media_probe(ffprobe_bin, final)
    video_streams = [value for value in probe["streams"] if value.get("codec_type") == "video"]
    audio_streams = [value for value in probe["streams"] if value.get("codec_type") == "audio"]
    subtitle_streams = [value for value in probe["streams"] if value.get("codec_type") == "subtitle"]
    if len(video_streams) != 1 or len(audio_streams) != 1 or len(subtitle_streams) != 1:
        raise RuntimeError("rig proof must contain one video, audio, and caption stream")
    video_stream, audio_stream, subtitle_stream = video_streams[0], audio_streams[0], subtitle_streams[0]
    if (
        video_stream.get("codec_name") != "h264"
        or video_stream.get("pix_fmt") != "yuv420p"
        or int(video_stream.get("width", 0)) != 1920
        or int(video_stream.get("height", 0)) != 1080
        or int(video_stream.get("nb_frames", 0)) != 657
        or audio_stream.get("codec_name") != "aac"
        or int(audio_stream.get("sample_rate", 0)) != 48000
        or int(audio_stream.get("channels", 0)) != 2
        or subtitle_stream.get("codec_name") != "mov_text"
        or not math.isclose(float(probe["format"]["duration"]), 21.9, abs_tol=0.001)
    ):
        raise RuntimeError(f"rig proof failed its final media gate: {probe}")
    video_only_hash = _stream_hash(ffmpeg_bin, video_only, "0:v:0")
    final_video_hash = _stream_hash(ffmpeg_bin, final, "0:v:0")
    if final_video_hash != video_only_hash:
        raise RuntimeError("audio/caption mux re-encoded the rig proof picture")

    loudness_contract = contract["sound"]["delivery_loudness"]
    loudness_raw = _loudnorm_measure(
        ffmpeg_bin,
        final,
        target_i=float(loudness_contract["target_lufs_i"]),
        target_lra=7.0,
        target_tp=float(loudness_contract["maximum_true_peak_dbtp"]),
    )
    measured_lufs = float(loudness_raw["input_i"])
    measured_lra = float(loudness_raw["input_lra"])
    measured_true_peak = float(loudness_raw["input_tp"])
    if abs(measured_lufs - float(loudness_contract["target_lufs_i"])) > float(
        loudness_contract["tolerance_lu"]
    ):
        raise RuntimeError("rig proof failed its integrated-loudness gate")
    if measured_true_peak > float(loudness_contract["maximum_true_peak_dbtp"]):
        raise RuntimeError("rig proof failed its encoded true-peak gate")

    action_by_id = {str(action["id"]): action for action in contract["actions"]}
    review_frames: list[int] = []
    for span in spans:
        output_start = int(span["output_start_frame"])
        for local_frame in action_by_id[str(span["action_id"])]["review_local_frames"]:
            review_frames.append(output_start + int(local_frame) - 1)
    review_frames = sorted(set(review_frames))
    quality = _review_encoded_video(final, review_frames, output / "review_frames")
    minimum_detail = float(contract["quality_gate"]["minimum_encoded_laplacian_variance"])
    if float(quality["minimum_encoded_laplacian_variance"]) < minimum_detail:
        raise RuntimeError("rig proof failed its retained-detail gate")

    action_report = {}
    for identifier in contract["sequence"]["action_ids"]:
        item = action_results[identifier]
        action_report[identifier] = {
            "action_class": action_by_id[identifier]["action_class"],
            "view_id": item["view_id"],
            "adapter": item["adapter"],
            "frame_count": item["report"]["frame_count"],
            "gate": item["report"]["gate"],
            "video": item["video"].name,
            "video_sha256": _sha256(item["video"]),
            "required_channels": action_by_id[identifier]["required_channels"],
            "acceptance": action_by_id[identifier]["acceptance"],
        }

    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "reusable_multiview_performance_rig_proof",
        "rig_id": contract["rig_id"],
        "classification": contract["classification"],
        "contract_sha256": _sha256(Path(contract_path).resolve()),
        "canonical_identity_sha256": contract["canonical_identity"]["sha256"],
        "semantic_channels": [value["id"] for value in contract["semantic_channels"]],
        "action_class_coverage": sorted(EXPECTED_ACTION_CLASSES),
        "view_adapter_count": 3,
        "actions": action_report,
        "sequence": {
            "frame_count": 657,
            "duration_seconds": 21.9,
            "cut_frames": contract["sequence"]["cut_frames"],
            "transition": "hard_cuts_only",
            "source_frame_spans": spans,
            "action_video_concat_codec_copy": True,
            "optical_flow_used": False,
            "cross_dissolve_used": False,
            "implicit_retiming_used": False,
        },
        "sound": {
            "source_gate": source_sound_report["gate"],
            "source_file": sound_video.name,
            "source_sha256": _sha256(sound_video),
            "source_frame_spans": [[value["source_master_start_frame"], value["source_master_end_frame"]] for value in spans],
            "boundary_fades_ms": contract["sound"]["boundary_fades_ms"],
            "audio_file": audio.name,
            "audio_sha256": _sha256(audio),
            "caption_file": captions.name,
            "caption_sha256": _sha256(captions),
            "caption_count": len(caption_cues),
            "caption_cues": caption_cues,
            "encoded_aac_loudness": {
                "measured_lufs_i": measured_lufs,
                "measured_lra_lu": measured_lra,
                "measured_true_peak_dbtp": measured_true_peak,
                "target_lufs_i": loudness_contract["target_lufs_i"],
                "tolerance_lu": loudness_contract["tolerance_lu"],
                "maximum_true_peak_dbtp": loudness_contract["maximum_true_peak_dbtp"],
                "lra_gate_applied": False,
                "lra_note": "Informational for this discontinuous excerpt; the source 38.8-second master owns the 4-8 LU delivery gate.",
            },
        },
        "quality": quality,
        "picture_stream": {
            "video_only_sha256": video_only_hash,
            "final_sha256": final_video_hash,
            "preserved_through_sound_and_caption_mux": True,
        },
        "final": {
            "file": final.name,
            "sha256": _sha256(final),
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "frame_count": 657,
            "duration_seconds": 21.9,
            "video_codec": "h264",
            "pixel_format": "yuv420p",
            "audio_codec": "aac",
            "audio_sample_rate": 48000,
            "audio_channels": 2,
            "subtitle_codec": "mov_text",
        },
        "known_limitations": contract["known_limitations"],
        "paid_runtime_dependency": False,
    }
    report_path = output / "june-performance-rig-proof-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's reusable three-action performance rig proof")
    parser.add_argument("contract")
    parser.add_argument("--sound-master", required=True)
    parser.add_argument("--sound-report", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_performance_rig_proof(
        args.contract,
        args.output_dir,
        sound_master=args.sound_master,
        sound_report=args.sound_report,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
