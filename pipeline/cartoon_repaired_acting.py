"""Connect Phase42 eyelids to the existing Phase40 acting stack.

This reuses the existing body, face, head, atmosphere, and editorial camera
renderers.  Its CLI produces six diagnostic stills, never a scene or encoded
movie.  Body/eye/audio human review still gates any subsequent full delivery.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator

import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_eyelid_source_successor as eyes
from pipeline import cartoon_synchronized_acting_integration as acting


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-repaired-acting-integration-v1"
REVIEW_FRAMES = (70, 79, 81, 82, 148, 173)
REPORT_LOCKS = {
    "acting": ("collab/phase40_synchronized_acting_integration_v1/phase40-synchronized-acting-machine-report-v1.json", "360427112da5fc79fb173c18d1e6cf9fcaea38173614fcfb511d55a660921256"),
    "eyes": ("collab/phase42_continuous_blink_review_v2/phase42-eyelid-source-successor-report-v2.json", "4c3d7d1c85cf4d68e069bb45808b5597039fb1d0f03e912d1bdaf09b321f2bcf"),
    "audio": ("collab/phase42_human_rejected_gates_successors_v1/phase42-fullmix-audio-successor-report-v1.json", "4a84ea32ea6496d225d8fda76e003a4ff19652065fe6c4bc91bdd111438d0e46"),
}


class RepairedActingError(RuntimeError):
    pass


@dataclass
class PreparedRepairedActing:
    integration: acting.PreparedIntegration
    texture: np.ndarray
    reports: dict[str, Any]
    eye_contract: dict[str, Any]
    camera: dict[str, Any]
    audio_path: Path


@dataclass
class RepairedActingFrame:
    source_frame: int
    original: np.ndarray
    body_only: np.ndarray
    repaired: np.ndarray
    metrics: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def editorial_window(source_frame: int) -> dict[str, int | float]:
    if type(source_frame) is not int or not 1 <= source_frame <= 228:
        raise ValueError("direct-address frame must be an integer inside F001-F228")
    output_frame = source_frame + 75
    start = (output_frame - 1) * 1600
    return {
        "source_frame": source_frame, "output_frame": output_frame,
        "audio_start_sample": start, "audio_end_sample_exclusive": start + 1600,
        "output_start_seconds": start / 48000,
    }


def prepare_repaired_acting() -> PreparedRepairedActing:
    reports = {}
    for label, (relative, expected) in REPORT_LOCKS.items():
        path = REPO_ROOT / relative
        if _sha256(path) != expected:
            raise RepairedActingError(f"{label} predecessor report hash mismatch")
        reports[label] = json.loads(path.read_text(encoding="utf-8"))
    for label, module in (("source_successor", eyes), ("continuous_blink", eyes.cartoon_continuous_blink)):
        if _sha256(Path(module.__file__)) != reports["eyes"]["implementation_sha256"][label]:
            raise RepairedActingError(f"eyelid implementation drift: {label}")
    implementation = reports["acting"]["implementation"]
    if _sha256(REPO_ROOT / implementation["path"]) != implementation["sha256"]:
        raise RepairedActingError("acting implementation drift")
    integration = acting.prepare_integration()
    textures, _ = eyes._corrected_textures(integration.direct)
    eye_contract = eyes.v4.load_contract()
    picture = json.loads((REPO_ROOT / eye_contract["locks"]["phase36_picture_contract"]["path"]).read_text(encoding="utf-8"))
    camera = next(row["camera"] for row in picture["shots"] if row["id"] == "LP030_COMPASSION_PUNCH")
    audio = reports["audio"]["variants"]["balanced_air"]
    audio_path = (REPO_ROOT / REPORT_LOCKS["audio"][0]).parent / audio["file"]
    if _sha256(audio_path) != audio["wav_sha256"]:
        raise RepairedActingError("balanced-air WAV hash mismatch")
    _, probe = eyes.v4.v3.phase36._read_pcm24_wave(audio_path)
    if (probe["sample_rate"], probe["channels"], probe["sample_count"], probe["bits_per_sample"]) != (48000, 2, 484800, 24):
        raise RepairedActingError("audio/editorial clock mismatch")
    return PreparedRepairedActing(integration, textures["ai_direct"], reports, eye_contract, camera, audio_path)


@contextmanager
def registered_lids(prepared: PreparedRepairedActing) -> Iterator[None]:
    """Bound the mutable legacy adapter and restore the caller's exact cache."""
    direct = prepared.integration.direct
    texture = direct.face.phase33_base.lid_texture
    previous_texture = texture.copy()
    previous_cache = direct.native_cache.copy()
    texture[:] = prepared.texture
    direct.native_cache.clear()
    try:
        with eyes._natural_blink_variant(direct, continuous=True):
            yield
    finally:
        texture[:] = previous_texture
        direct.native_cache.clear()
        direct.native_cache.update(previous_cache)


def _editorial_frame(prepared: PreparedRepairedActing, image: np.ndarray, frame: int) -> np.ndarray:
    if frame <= 162:
        return image.copy()
    result, _ = eyes.v4.v3.phase36.compassion_camera(image, prepared.camera, frame)
    return result


def compose_repaired_frame(prepared: PreparedRepairedActing, source_frame: int) -> RepairedActingFrame:
    window = editorial_window(source_frame)
    direct = prepared.integration.direct
    # Declare eye support from geometry and resampler footprints before looking
    # at any candidate RGB differences.  Never fit a mask to the observed delta.
    native_support = eyes.v4.v3.phase35._native_eye_support_mask(direct)
    kernel = prepared.eye_contract["diagnostic"]["prospective_transform_support"]
    allowed, _ = eyes.v4.v3._prospective_support_to_phase35(direct, source_frame, native_support, kernel)
    if source_frame > 162:
        allowed, _ = eyes.v4.v3._prospective_support_to_phase36(allowed, prepared.camera, source_frame, kernel)
    baseline = acting.compose_integrated_frame(prepared.integration, source_frame)
    expected = prepared.reports["acting"]["measurements"]["candidate_frame_hashes"][source_frame - 1]
    if acting._rgb_hash(baseline.candidate) != expected:
        raise RepairedActingError(f"existing acting render changed at source F{source_frame}")
    with registered_lids(prepared):
        candidate = acting.compose_integrated_frame(prepared.integration, source_frame)
    original = _editorial_frame(prepared, baseline.baseline, source_frame)
    body_only = _editorial_frame(prepared, baseline.candidate, source_frame)
    repaired = _editorial_frame(prepared, candidate.candidate, source_frame)
    changed = np.any(repaired != body_only, axis=2)
    closure = acting.phase35.production_blink_closure(direct.contract, source_frame)
    metrics = {
        **window, "blink_closure": closure, "body_active": bool(candidate.metrics["state_nonzero"]),
        "original_rgb_sha256": acting._rgb_hash(original),
        "body_only_rgb_sha256": acting._rgb_hash(body_only),
        "repaired_rgb_sha256": acting._rgb_hash(repaired),
        "eye_repair_changed_pixels": int(changed.sum()),
        "eye_repair_changes_outside_prospective_eye_support": int((changed & ~allowed).sum()),
        "body_changed_pixels": int(candidate.metrics["changed_pixel_count"]),
        "body_changes_inside_repaired_face_support": candidate.metrics["changed_pixels_in_transformed_face_feature_support"],
        "body_changes_inside_mug_support": candidate.metrics["changed_pixels_in_transformed_mug_support"],
        "body_changes_outside_body_support": candidate.metrics["changed_pixels_outside_transformed_phase39_support"],
    }
    if metrics["eye_repair_changes_outside_prospective_eye_support"]:
        raise RepairedActingError("eye repair changed body/set pixels outside its declared support")
    if any(metrics[key] for key in ("body_changes_inside_repaired_face_support", "body_changes_inside_mug_support", "body_changes_outside_body_support")):
        raise RepairedActingError("body integration damaged a protected region")
    if closure == 0.0 and not np.array_equal(body_only, repaired):
        raise RepairedActingError("neutral eye repair did not bypass exactly")
    if closure > 0.0 and not np.any(changed):
        raise RepairedActingError("eye repair was lost during body/camera integration")
    if source_frame == 173 and metrics["repaired_rgb_sha256"] != prepared.reports["eyes"]["variants"]["ai_direct"]["phase36_rgb_sha256"]:
        raise RepairedActingError("late blink no longer matches the reviewed Phase42 eye frame")
    return RepairedActingFrame(source_frame, original, body_only, repaired, metrics)


def build_evidence(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise RepairedActingError(f"refusing to overwrite evidence: {output}")
    prepared = prepare_repaired_acting()
    frames = [compose_repaired_frame(prepared, number) for number in REVIEW_FRAMES]
    if not any(frame.metrics["body_active"] and frame.metrics["blink_closure"] == 1.0 for frame in frames):
        raise RepairedActingError("evidence never exercised a full blink during body acting")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phase42-acting-", dir=output.parent) as temporary:
        stage = Path(temporary)
        width, height = 640, 384
        sheet = Image.new("RGB", (width * 3, height * len(frames)), (14, 11, 9))
        draw = ImageDraw.Draw(sheet)
        font = eyes._font(16)
        for row, frame in enumerate(frames):
            for column, (label, pixels) in enumerate((("Original", frame.original), ("Body acting only", frame.body_only), ("Body acting + repaired eyes", frame.repaired))):
                sheet.paste(Image.fromarray(pixels).resize((640, 360), Image.Resampling.LANCZOS), (column * width, row * height + 24))
                draw.text((column * width + 8, row * height + 3), f"F{frame.metrics['output_frame']} / source {frame.source_frame}: {label}", font=font, fill=(245, 227, 197))
            if frame.source_frame in (81, 173):
                Image.fromarray(frame.repaired).save(stage / f"phase42-integrated-source-f{frame.source_frame:03d}-v1.png")
        sheet.save(stage / "phase42-acting-eye-integration-comparison-v1.png")
        report = {
            "report_version": 1, "classification": "SAMPLED_STILL_INTEGRATION_ONLY_HUMAN_REVIEW_PENDING",
            "cash_cost": 0, "network_calls": 0, "video_encoder_processes": 0,
            "full_scene_rendered": False, "human_accepted": False, "promotion_allowed": False,
            "sampled_source_frames": list(REVIEW_FRAMES), "frames": [frame.metrics for frame in frames],
            "predecessor_report_locks": REPORT_LOCKS,
            "implementation_sha256": _sha256(Path(__file__)),
            "audio_binding": {"file": prepared.audio_path.relative_to(REPO_ROOT).as_posix(), "wav_sha256": _sha256(prepared.audio_path), "sample_rate": 48000, "sample_count": 484800, "samples_per_output_frame": 1600, "human_listening_accepted": False},
            "artifacts": {path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size} for path in sorted(stage.glob("*.png"))},
        }
        (stage / "phase42-repaired-acting-integration-report-v1.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        shutil.move(str(stage), str(output))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    report = build_evidence(args.output)
    print(json.dumps({"sampled_source_frames": report["sampled_source_frames"], "artifacts": report["artifacts"], "full_scene_rendered": False}, indent=2))


if __name__ == "__main__":
    main()
