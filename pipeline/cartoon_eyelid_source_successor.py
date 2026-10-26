"""Prototype registered closed-lid art after James rejected Phase37 V4.

The locked GS070 plate remains the background.  Only semantic lid-support
pixels are sampled from a separately provenance-tracked, AI-assisted closed-eye
source.  A direct and a locally tone-matched extraction are rendered beside the
rejected V4 frame.  Outputs are still-only review evidence; no video encoder
runs and no predecessor artifact is changed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pipeline import cartoon_eyelid_edge_diagnostic as v4


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-eyelid-inpaint-successor-v5"
AI_SOURCE_RELATIVE = "concept/characters/rig_assets/june_oxley_closed_eyes_gs070_source_v1.png"
AI_SOURCE_SHA256 = "0f9dd1366391cc050290f1bfd52af8379b688d7962a231638fb699cffa7d105c"
VARIANTS = ("rejected_v4", "ai_direct", "ai_tone_matched")


class EyelidSourceSuccessorError(RuntimeError):
    """Raised when a bounded eyelid-source invariant fails."""


def _hash_array(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def _eye_geometry(prepared: Any) -> tuple[dict[str, int], dict[str, int]]:
    geometry = prepared.face.contract["semantic_geometry_native_xy"]
    left = geometry["viewer_left_eye"]
    right = geometry["viewer_right_eye"]
    return (
        {"cx": int(left["center"][0]), "cy": int(left["center"][1]), "rx": int(left["radius"][0]), "ry": int(left["radius"][1])},
        {"cx": int(right["center"][0]), "cy": int(right["center"][1]), "rx": int(right["radius"][0]), "ry": int(right["radius"][1])},
    )


def _full_lid_support(prepared: Any, eye: dict[str, int]) -> np.ndarray:
    upper, lower, _ = v4.v3.phase35.phase34_candidate09._semantic_lid_alpha_masks(
        prepared.face.plate.shape[:2],
        (eye["cx"], eye["cy"]),
        (eye["rx"], eye["ry"]),
        1.0,
    )
    return (upper > 0) | (lower > 0)


def _ellipse(shape: tuple[int, int], eye: dict[str, int], expand: int) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    cv2.ellipse(
        mask,
        (eye["cx"], eye["cy"]),
        (eye["rx"] + expand, eye["ry"] + expand),
        0.0,
        0.0,
        360.0,
        255,
        -1,
        lineType=cv2.LINE_AA,
    )
    return mask > 128


def _load_ai_source(prepared: Any) -> tuple[np.ndarray, Path]:
    path = (REPO_ROOT / AI_SOURCE_RELATIVE).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise EyelidSourceSuccessorError("AI source escapes repository") from exc
    if not path.is_file():
        raise EyelidSourceSuccessorError(f"missing AI eyelid source: {path}")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != AI_SOURCE_SHA256:
        raise EyelidSourceSuccessorError(f"AI eyelid source hash mismatch: {actual_hash}")
    source = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
    if source.shape != prepared.face.plate.shape:
        raise EyelidSourceSuccessorError(
            f"AI eyelid source shape mismatch: {source.shape} != {prepared.face.plate.shape}"
        )
    return source, path


def _corrected_textures(prepared: Any) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    original = prepared.face.phase33_base.lid_texture.copy()
    source, source_path = _load_ai_source(prepared)
    direct = original.copy()
    matched = original.copy()
    combined_support = np.zeros(original.shape[:2], dtype=bool)
    per_eye: dict[str, Any] = {}
    for eye_name, eye in zip(("viewer_left_eye", "viewer_right_eye"), _eye_geometry(prepared)):
        semantic_support = _full_lid_support(prepared, eye)
        # Include a five-pixel socket handoff so full closure also replaces the
        # open-eye corner pixels that fall just outside the original lid ellipse.
        support = _ellipse(original.shape[:2], eye, 5)
        combined_support |= support
        direct[support] = source[support]

        # Estimate a conservative color handoff from the skin immediately
        # surrounding the lid.  The pupil/sclera interior and brow are excluded.
        outer = _ellipse(support.shape, eye, 10)
        inner = _ellipse(support.shape, eye, 6)
        ring = outer & ~inner
        if int(ring.sum()) < 300:
            raise EyelidSourceSuccessorError(f"insufficient tone-match ring for {eye_name}")
        delta = np.median(
            prepared.face.plate[ring].astype(np.float64) - source[ring].astype(np.float64),
            axis=0,
        )
        delta = np.clip(delta, -12.0, 12.0)
        adjusted = np.clip(np.rint(source.astype(np.float64) + delta[None, None, :]), 0, 255).astype(np.uint8)
        matched[support] = adjusted[support]
        per_eye[eye_name] = {
            "center_xy": [eye["cx"], eye["cy"]],
            "radius_xy": [eye["rx"], eye["ry"]],
            "semantic_lid_support_pixels": int(semantic_support.sum()),
            "extracted_socket_support_pixels": int(support.sum()),
            "tone_match_ring_pixels": int(ring.sum()),
            "clipped_median_rgb_delta": [float(value) for value in delta],
        }

    changes = {
        "ai_direct": np.any(direct != original, axis=2),
        "ai_tone_matched": np.any(matched != original, axis=2),
    }
    for name, changed in changes.items():
        if np.any(changed & ~combined_support):
            raise EyelidSourceSuccessorError(f"{name} changed pixels outside semantic lid support")
    audit = {
        "mapping": "same-size generated plate sampled only inside bilateral semantic lid support plus a five-pixel socket handoff",
        "locked_background": "GS070 source plate; generated frame is never used wholesale",
        "ai_source_path": source_path.relative_to(REPO_ROOT).as_posix(),
        "ai_source_file_sha256": AI_SOURCE_SHA256,
        "combined_extracted_socket_support_pixels": int(combined_support.sum()),
        "combined_extracted_socket_support_mask_sha256": _hash_array(combined_support),
        "per_eye": per_eye,
        "original_lid_texture_sha256": _hash_array(original),
        "ai_direct_changed_source_pixels": int(changes["ai_direct"].sum()),
        "ai_direct_lid_texture_sha256": _hash_array(direct),
        "ai_tone_matched_changed_source_pixels": int(changes["ai_tone_matched"].sum()),
        "ai_tone_matched_lid_texture_sha256": _hash_array(matched),
    }
    return {"rejected_v4": original, "ai_direct": direct, "ai_tone_matched": matched}, audit


def _successor_edge_spec(prepared: Any) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Any]]:
    shape = prepared.face.plate.shape[:2]
    hard: dict[str, np.ndarray] = {}
    soft: dict[str, np.ndarray] = {}
    audit: dict[str, Any] = {}
    for eye_name, eye in zip(("viewer_left_eye", "viewer_right_eye"), _eye_geometry(prepared)):
        hard_mask = _ellipse(shape, eye, 3)
        inner = _ellipse(shape, eye, 4) & ~hard_mask
        outer = _ellipse(shape, eye, 5) & ~_ellipse(shape, eye, 4)
        alpha = np.zeros(shape, dtype=np.uint8)
        alpha[inner] = 170
        alpha[outer] = 85
        hard[eye_name] = hard_mask
        soft[eye_name] = alpha
        audit[eye_name] = {
            "hard_pixels": int(hard_mask.sum()),
            "inner_feather_pixels": int(inner.sum()),
            "outer_feather_pixels": int(outer.sum()),
            "hard_mask_sha256": _hash_array(hard_mask),
            "soft_alpha_sha256": _hash_array(alpha),
        }
    return hard, soft, audit


@contextmanager
def _natural_blink_variant(prepared: Any) -> Iterator[dict[str, Any]]:
    """Temporarily use an upper-lid-led blink with a generated closed-eye target.

    The predecessor split upper/lower travel equally.  Human eyelids do not:
    the upper lid performs most of the closure and the lower lid rises only a
    little.  This override moves both edges toward the generated frame's lash
    line, approximately 70/30, and uses the feathered socket only at full close.
    """
    phase33 = v4.v3.phase35.phase34_candidate09.phase33
    phase34 = v4.v3.phase35.phase34_candidate09
    original_compose = phase33._compose_eye_lids
    original_masks = phase34._semantic_lid_alpha_masks
    hard_by_eye, soft_by_eye, edge_audit = _successor_edge_spec(prepared)
    eye_by_center = {
        (eye["cx"], eye["cy"]): (name, eye)
        for name, eye in zip(("viewer_left_eye", "viewer_right_eye"), _eye_geometry(prepared))
    }
    calls: list[dict[str, Any]] = []

    def masks(
        shape: tuple[int, int], center: tuple[int, int], radius: tuple[int, int], closure: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        upper = np.zeros(shape, dtype=np.uint8)
        lower = np.zeros(shape, dtype=np.uint8)
        crease = np.zeros(shape, dtype=np.uint8)
        if closure <= 0.0:
            return upper, lower, crease
        cx, cy = center
        rx, ry = radius
        x1, y1, x2, y2 = cx - rx - 5, cy - ry - 12, cx + rx + 6, cy + ry + 12
        yy, xx = np.indices((y2 - y1, x2 - x1), dtype=np.float32)
        local_cx, local_cy = cx - x1, cy - y1
        ellipse = (((xx - local_cx) / rx) ** 2 + ((yy - local_cy) / ry) ** 2) <= 1.0
        # The generated full-close lash line sits below the eye center.  Drive
        # the upper lid farther and the lower lid less so intermediate frames
        # read as a blink instead of a lower-lid wipe.
        meeting_y = local_cy + 0.30 * ry
        upper_start = local_cy - ry
        lower_start = local_cy + ry
        upper_edge = upper_start + closure * (meeting_y + 1.5 - upper_start)
        lower_edge = lower_start - closure * (lower_start - (meeting_y - 1.5))
        upper[y1:y2, x1:x2] = phase34._soft(
            (ellipse & (yy <= upper_edge)).astype(np.uint8) * 255, 0.7,
        )
        lower[y1:y2, x1:x2] = phase34._soft(
            (ellipse & (yy >= lower_edge)).astype(np.uint8) * 255, 0.7,
        )
        if closure >= 0.999:
            eye_name, _ = eye_by_center[tuple(center)]
            socket = np.zeros(shape, dtype=np.uint8)
            socket[hard_by_eye[eye_name]] = 255
            socket = np.maximum(socket, soft_by_eye[eye_name])
            lower = np.maximum(lower, socket)
        return upper, lower, crease

    def compose(
        canvas: np.ndarray,
        plate: np.ndarray,
        lid_texture: np.ndarray,
        owner: np.ndarray,
        center: tuple[int, int],
        radius: tuple[int, int],
        closure: float,
    ) -> tuple[float, int]:
        if closure <= 0.0:
            return 0.0, 0
        upper, lower, _ = masks(plate.shape[:2], center, radius, closure)
        cx, cy = center
        rx, ry = radius
        x1, y1, x2, y2 = cx - rx - 5, cy - ry - 12, cx + rx + 6, cy + ry + 12
        canvas_roi = canvas[y1:y2, x1:x2]
        source_roi = lid_texture[y1:y2, x1:x2]
        owner_roi = owner[y1:y2, x1:x2]
        upper_roi = upper[y1:y2, x1:x2]
        lower_roi = lower[y1:y2, x1:x2]
        phase33._blend_source(canvas_roi, source_roi, upper_roi)
        owner_roi[upper_roi >= 128] = 7
        phase33._blend_source(canvas_roi, source_roi, lower_roi)
        owner_roi[lower_roi >= 128] = 8

        yy, xx = np.indices((y2 - y1, x2 - x1), dtype=np.float32)
        local_cx, local_cy = cx - x1, cy - y1
        iris = (((xx - local_cx) / 11.5) ** 2 + ((yy - local_cy) / 14.0) ** 2) <= 1.0
        written = (upper_roi >= 128) | (lower_roi >= 128)
        ratio = float((iris & written).sum() / max(1, iris.sum()))
        eye_name, _ = eye_by_center[tuple(center)]
        calls.append({
            "eye_name": eye_name,
            "closure": float(closure),
            "upper_write_pixels": int((upper_roi >= 128).sum()),
            "lower_write_pixels": int((lower_roi >= 128).sum()),
            "combined_write_pixels": int(written.sum()),
            "iris_occlusion_ratio": ratio,
        })
        return ratio, int(written.sum())

    phase33._compose_eye_lids = compose
    phase34._semantic_lid_alpha_masks = masks
    try:
        yield {"eye_calls": calls, "crease_suppressions": [], "edge_spec": edge_audit}
    finally:
        phase34._semantic_lid_alpha_masks = original_masks
        phase33._compose_eye_lids = original_compose


def _render_focus(
    prepared: Any,
    contract: dict[str, Any],
    sclera: dict[str, dict[str, Any]],
    masks: dict[str, Any],
    texture: np.ndarray,
    variant_name: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    specs = v4._variant_specs(sclera, masks, prepared.face.plate.shape[:2])
    if variant_name == "rejected_v4":
        hard = specs["feather_2px"]["hard"]
        soft = specs["feather_2px"]["soft"]
        edge_spec_audit: dict[str, Any] = {"policy": "locked rejected V4 feather_2px"}
        context = v4._edge_variant(sclera, hard, soft, suppress_crease=True)
    else:
        _, _, edge_spec_audit = _successor_edge_spec(prepared)
        context = _natural_blink_variant(prepared)
    focus = int(contract["diagnostic"]["source_focus_frame"])
    original = prepared.face.phase33_base.lid_texture.copy()
    prepared.face.phase33_base.lid_texture[:] = texture
    prepared.native_cache.clear()
    try:
        with context as audit:
            source_image, native, evidence = v4.v3.phase35.compose_direct_address_frame(prepared, focus)
    finally:
        prepared.face.phase33_base.lid_texture[:] = original
        prepared.native_cache.clear()
    source = np.asarray(source_image.convert("RGB"), dtype=np.uint8)
    phase36_contract = v4.v3._strict_json(
        v4._repo_path(contract["locks"]["phase36_picture_contract"]["path"]), "Phase36 contract",
    )
    camera = next(row["camera"] for row in phase36_contract["shots"] if row["id"] == "LP030_COMPASSION_PUNCH")
    phase36, transform = v4.v3.phase36.compassion_camera(source, camera, focus)
    return native.copy(), source.copy(), phase36.copy(), {
        "edge_write_calls": len(audit["eye_calls"]),
        "crease_suppressions": len(audit["crease_suppressions"]),
        "transform": transform,
        "evidence": v4.v3._evidence(evidence),
        "edge_spec": edge_spec_audit,
    }


def _render_successor_sequence(
    prepared: Any,
    contract: dict[str, Any],
    sclera: dict[str, dict[str, Any]],
    texture: np.ndarray,
) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    original = prepared.face.phase33_base.lid_texture.copy()
    prepared.face.phase33_base.lid_texture[:] = texture
    prepared.native_cache.clear()
    frames: list[np.ndarray] = []
    metadata: list[dict[str, Any]] = []
    source_frames = [int(value) for value in contract["diagnostic"]["source_frames"]]
    phase36_frames = [int(value) for value in contract["diagnostic"]["phase36_frames"]]
    try:
        with _natural_blink_variant(prepared):
            for source_frame, phase36_frame in zip(source_frames, phase36_frames):
                source_image, _, evidence = v4.v3.phase35.compose_direct_address_frame(prepared, source_frame)
                phase36_contract = v4.v3._strict_json(
                    v4._repo_path(contract["locks"]["phase36_picture_contract"]["path"]),
                    "Phase36 contract",
                )
                camera = next(
                    row["camera"]
                    for row in phase36_contract["shots"]
                    if row["id"] == "LP030_COMPASSION_PUNCH"
                )
                phase36, transform = v4.v3.phase36.compassion_camera(
                    np.asarray(source_image.convert("RGB"), dtype=np.uint8), camera, source_frame,
                )
                frames.append(phase36.copy())
                metadata.append({
                    "source_frame": source_frame,
                    "phase36_frame": phase36_frame,
                    "blink_closure": float(evidence.blink_closure),
                    "rgb_sha256": _hash_array(phase36),
                    "transformed_eye_roi_xyxy": transform["transformed_eye_roi_xyxy"],
                })
    finally:
        prepared.face.phase33_base.lid_texture[:] = original
        prepared.native_cache.clear()
    return frames, metadata


def _sequence_review(
    frames: list[np.ndarray],
    metadata: list[dict[str, Any]],
    focus_box: tuple[int, int, int, int],
) -> tuple[Image.Image, list[Image.Image], dict[str, Any]]:
    x1, y1, x2, y2 = focus_box
    crops = [Image.fromarray(frame).crop(focus_box) for frame in frames]
    tile_w, tile_h = 320, 190
    columns = 6
    rows = int(np.ceil(len(crops) / columns))
    sheet = Image.new("RGB", (columns * tile_w, rows * tile_h), (12, 9, 7))
    draw = ImageDraw.Draw(sheet)
    font = _font(15)
    for index, (crop, row) in enumerate(zip(crops, metadata)):
        thumb = crop.copy()
        thumb.thumbnail((tile_w, tile_h - 28), Image.Resampling.LANCZOS)
        x = (index % columns) * tile_w + (tile_w - thumb.width) // 2
        y = (index // columns) * tile_h + 28
        sheet.paste(thumb, (x, y))
        draw.text(
            ((index % columns) * tile_w + 8, (index // columns) * tile_h + 6),
            f"F{row['phase36_frame']}  closure {row['blink_closure']:.2f}",
            fill=(244, 226, 196),
            font=font,
        )

    adjacent: list[dict[str, Any]] = []
    for first, second, first_meta, second_meta in zip(frames, frames[1:], metadata, metadata[1:]):
        first_crop = first[y1:y2, x1:x2]
        second_crop = second[y1:y2, x1:x2]
        delta = np.abs(first_crop.astype(np.float32) - second_crop.astype(np.float32)).mean(axis=2)
        local = cv2.boxFilter(delta, -1, (8, 8), normalize=True)
        adjacent.append({
            "phase36_frame_pair": [first_meta["phase36_frame"], second_meta["phase36_frame"]],
            "closure_pair": [first_meta["blink_closure"], second_meta["blink_closure"]],
            "eye_crop_mean_absolute_delta": float(delta.mean()),
            "eye_crop_maximum_8x8_mean_delta": float(local.max()),
        })
    return sheet, crops, {
        "frames": metadata,
        "eye_crop_xyxy": list(focus_box),
        "adjacent_eye_metrics": adjacent,
        "maximum_adjacent_eye_crop_mean_absolute_delta": max(
            row["eye_crop_mean_absolute_delta"] for row in adjacent
        ),
        "maximum_adjacent_eye_crop_8x8_mean_delta": max(
            row["eye_crop_maximum_8x8_mean_delta"] for row in adjacent
        ),
    }


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _grid(states: dict[str, np.ndarray], box: tuple[int, int, int, int], scale: int) -> Image.Image:
    crops = [Image.fromarray(states[name]).crop(box) for name in VARIANTS]
    cell_w, cell_h = crops[0].size
    label_h = 34
    sheet = Image.new("RGB", (cell_w * scale * len(crops), cell_h * scale + label_h), (12, 9, 7))
    draw = ImageDraw.Draw(sheet)
    font = _font(16)
    labels = {
        "rejected_v4": "REJECTED V4 — GRAY UPPER LID",
        "ai_direct": "AI LIDS — FEATHERED SOCKET EXTRACTION",
        "ai_tone_matched": "AI LIDS — FEATHERED + LOCAL TONE MATCH",
    }
    for index, (name, crop) in enumerate(zip(VARIANTS, crops)):
        if scale != 1:
            crop = crop.resize((cell_w * scale, cell_h * scale), Image.Resampling.NEAREST)
        x = index * cell_w * scale
        sheet.paste(crop, (x, label_h))
        draw.text((x + 8, 8), labels[name], fill=(244, 226, 196), font=font)
    return sheet


def _source_grid(textures: dict[str, np.ndarray], box: tuple[int, int, int, int]) -> Image.Image:
    states = {name: value for name, value in textures.items()}
    return _grid(states, box, 3)


def build(output_root: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output_root.resolve()
    if output.exists():
        raise EyelidSourceSuccessorError(f"refusing to overwrite existing prototype: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    contract = v4.load_contract()
    prepared = v4.v3.phase35.prepare_direct_address()
    sclera, masks = v4._edge_masks(prepared, contract)
    textures, source_audit = _corrected_textures(prepared)
    native: dict[str, np.ndarray] = {}
    source: dict[str, np.ndarray] = {}
    phase36: dict[str, np.ndarray] = {}
    render_audit: dict[str, Any] = {}
    for name in VARIANTS:
        native[name], source[name], phase36[name], render_audit[name] = _render_focus(
            prepared, contract, sclera, masks, textures[name], name
        )

    sequence_frames, sequence_metadata = _render_successor_sequence(
        prepared, contract, sclera, textures["ai_direct"],
    )

    native_support = v4.v3.phase35._native_eye_support_mask(prepared)
    native_box = v4.v3._bbox(native_support, 16)
    transform = render_audit["rejected_v4"]["transform"]
    eye = transform["transformed_eye_roi_xyxy"]
    phase36_box = (max(0, eye[0] - 16), max(0, eye[1] - 16), min(1920, eye[2] + 16), min(1080, eye[3] + 16))
    sequence_sheet, sequence_crops, sequence_audit = _sequence_review(
        sequence_frames, sequence_metadata, phase36_box,
    )
    with tempfile.TemporaryDirectory(prefix="phase42-lid-", dir=output.parent) as temporary:
        stage = Path(temporary)
        _grid(native, native_box, 1).save(stage / "phase42-eyelid-source-native-1x-v1.png")
        _grid(native, native_box, 3).save(stage / "phase42-eyelid-source-native-3x-v1.png")
        _grid(phase36, phase36_box, 1).save(stage / "phase42-eyelid-source-phase36-1x-v1.png")
        _grid(phase36, phase36_box, 3).save(stage / "phase42-eyelid-source-phase36-3x-v1.png")
        _source_grid(textures, native_box).save(stage / "phase42-eyelid-source-textures-3x-v1.png")
        sequence_sheet.save(stage / "phase42-eyelid-ai-direct-f240-f256-sequence-v1.png")
        sequence_crops[0].save(
            stage / "phase42-eyelid-ai-direct-f240-f256-loop-v1.webp",
            save_all=True,
            append_images=sequence_crops[1:],
            duration=[140] + [67] * (len(sequence_crops) - 2) + [140],
            loop=0,
            lossless=True,
            quality=100,
            method=3,
        )
        artifacts = {
            path.name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
            for path in sorted([*stage.glob("*.png"), *stage.glob("*.webp")])
        }
        report = {
            "report_version": 1,
            "classification": "STILL_ONLY_AI_ASSISTED_LID_SOURCE_SUCCESSORS_HUMAN_REVIEW_REQUIRED",
            "cash_cost": 0,
            "runtime_network_calls": 0,
            "source_art_generation_network_call": 1,
            "video_encoder_processes": 0,
            "rejected_v4_report_sha256": "fd08ee030123fc96585994825fc49942a937e9e631722478fa54bcee6bc36a7f",
            "source_audit": source_audit,
            "ai_direct_neighbor_sequence": sequence_audit,
            "variants": {
                name: {
                    "native_rgb_sha256": _hash_array(native[name]),
                    "phase35_rgb_sha256": _hash_array(source[name]),
                    "phase36_rgb_sha256": _hash_array(phase36[name]),
                    "native_changed_pixels_vs_rejected_v4": int(np.any(native[name] != native["rejected_v4"], axis=2).sum()),
                    "phase36_changed_pixels_vs_rejected_v4": int(np.any(phase36[name] != phase36["rejected_v4"], axis=2).sum()),
                    "render_audit": render_audit[name],
                }
                for name in VARIANTS
            },
            "artifacts": artifacts,
            "human_review_required": True,
            "human_accepted": False,
            "rebuild_authorized": False,
            "encode_authorized": False,
        }
        (stage / "phase42-eyelid-source-successor-report-v1.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        shutil.move(str(stage), str(output))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
