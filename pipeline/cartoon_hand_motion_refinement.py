"""One late table-hand study; no locked renderer, contract, or scene mutation.

Source F091-F148 is output F166-F223 (5.500-7.433 seconds exclusive).
The candidate replaces independent spread/compression with a coherent planar
rock around the planted index-tip. A short, smooth entry inherits F090 exactly;
the original field is returned unchanged from F148 onward. This is an animation
study requiring human review, not proof of anatomical 3-D motion or acceptance.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline import cartoon_close_body_acting_rig as body


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = REPO_ROOT.parents[1] / "outputs/edit/phase42-hand-refinement-v1"
STUDY_FRAMES = tuple(range(91, 149))
NATIVE_CROP = (620, 700, 1010, 941)
ENTRY_END = 102
CONTACT_NAME = "index_tip"
PEAK_DEGREES = 0.65


def _quintic(value: float) -> float:
    value = min(1.0, max(0.0, float(value)))
    return value ** 3 * (10.0 + value * (-15.0 + 6.0 * value))


def entry_weight(frame: int) -> float:
    """C2 entry; not another repeated per-keyframe ease-and-stop motion."""
    if frame <= 90 or frame >= 148:
        return 0.0
    return _quintic((frame - 90) / (ENTRY_END - 90))


def rock_degrees(frame: int) -> float:
    """One deliberate press, a five-frame hold, then a longer quiet release."""
    if frame <= 90 or frame >= 148:
        return 0.0
    if frame < 111:
        return PEAK_DEGREES * _quintic((frame - 90) / 21)
    if frame <= 116:
        return PEAK_DEGREES
    return PEAK_DEGREES * (1.0 - _quintic((frame - 116) / 32))


def _rotation(degrees: float) -> np.ndarray:
    radians = math.radians(degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    return np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64)


def coherent_control_offsets(prepared: body.PreparedRig, frame: int) -> np.ndarray:
    region = prepared.regions["table_hand"]
    pivot = region.points[region.names.index(CONTACT_NAME)].astype(np.float64)
    points = region.points.astype(np.float64)
    target = (points - pivot) @ _rotation(rock_degrees(frame)).T + pivot
    return (target - points).astype(np.float32)


def coherent_inverse_field(prepared: body.PreparedRig, frame: int) -> np.ndarray:
    """Evaluate the exact inverse Euclidean map, not Gaussian-averaged deltas."""
    region = prepared.regions["table_hand"]
    left, top, right, bottom = region.bbox
    yy, xx = np.mgrid[top:bottom, left:right]
    grid = np.stack((xx, yy), axis=-1).astype(np.float64)
    pivot = region.points[region.names.index(CONTACT_NAME)].astype(np.float64)
    source = (grid - pivot) @ _rotation(rock_degrees(frame)) + pivot
    return (grid - source).astype(np.float32)


@contextmanager
def hand_override(prepared: body.PreparedRig, frame: int) -> Iterator[None]:
    """Temporarily adapt the existing body and synchronized integration paths.

    Only this exact prepared rig/state is adapted. The old compositor still
    owns torso/arm priority, protected regions, resampling and camera fusion.
    The hand alpha/support remains the existing prospectively declared region.
    Context restoration also runs for exceptions and nested callers.
    """
    if type(frame) is not int or not 1 <= frame <= 228:
        raise ValueError("source frame must be an integer inside F001-F228")
    weight = entry_weight(frame)
    if weight == 0.0:
        yield
        return
    original_hand = body._hand_offsets
    original_compose = body._compose_displacement
    region = prepared.regions["table_hand"]
    expected_state = prepared.states[frame - 1]
    old_offsets = original_hand(prepared, expected_state)
    new_offsets = coherent_control_offsets(prepared, frame)
    mixed_offsets = old_offsets * (1.0 - weight) + new_offsets * weight
    old_local = np.tensordot(region.weights, old_offsets, axes=(2, 0)).astype(np.float32)
    new_local = coherent_inverse_field(prepared, frame)

    def hand_offsets(rig: body.PreparedRig, state: dict[str, float]) -> np.ndarray:
        if rig is prepared and state is expected_state:
            return mixed_offsets.copy()
        return original_hand(rig, state)

    def compose(rig: body.PreparedRig, offsets: dict[str, np.ndarray]) -> np.ndarray:
        if rig is not prepared or not np.array_equal(offsets["table_hand"], mixed_offsets):
            return original_compose(rig, offsets)
        # Evaluate the original field with its original hand, then replace only
        # that hand contribution. The original torso and arm bytes survive.
        old = dict(offsets)
        old["table_hand"] = old_offsets
        result = original_compose(rig, old)
        left, top, right, bottom = region.bbox
        result[top:bottom, left:right] += (new_local - old_local) * (region.alpha * weight)[:, :, None]
        for protected in rig.protected.values():
            result[protected] = 0.0
        return result

    body._hand_offsets = hand_offsets
    body._compose_displacement = compose
    try:
        yield
    finally:
        body._hand_offsets = original_hand
        body._compose_displacement = original_compose


def native_hand_support(prepared: body.PreparedRig) -> np.ndarray:
    """Declared before comparing RGB; includes the existing resampler guard."""
    region = prepared.regions["table_hand"]
    left, top, right, bottom = region.bbox
    support = np.zeros(prepared.plate.shape[:2], dtype=np.uint8)
    support[top:bottom, left:right] = (region.alpha > 0).astype(np.uint8)
    guard = int(prepared.contract["deformation"]["prospective_kernel_guard_px"])
    if guard:
        support = cv2.dilate(support, np.ones((2 * guard + 1,) * 2, dtype=np.uint8))
    return support > 0


def delivery_hand_support(prepared: Any, frame: int) -> np.ndarray:
    """Use both guards of the existing synchronized camera compositor."""
    from pipeline import cartoon_synchronized_acting_integration as integration
    support = integration._transform_mask(native_hand_support(prepared.body), prepared, frame)
    guard = int(prepared.body.contract["deformation"]["prospective_kernel_guard_px"])
    if guard:
        support = cv2.dilate(support.astype(np.uint8), np.ones((2 * guard + 1,) * 2, dtype=np.uint8)) > 0
    return support


def peak_inverse_map_strain(prepared: body.PreparedRig) -> dict[str, Any]:
    """Local length/area check on declared opaque hand core at source F115."""
    region = prepared.regions["table_hand"]
    old_local = np.tensordot(region.weights, body._hand_offsets(prepared, prepared.states[114]), axes=(2, 0))
    core = region.alpha[1:-1, 1:-1] > 0.9999
    result: dict[str, Any] = {"source_frame": 115, "opaque_core_pixel_count": int(core.sum())}
    for label, field in (("old", old_local), ("candidate", coherent_inverse_field(prepared, 115))):
        dx = (field[1:-1, 2:] - field[1:-1, :-2]) / 2
        dy = (field[2:, 1:-1] - field[:-2, 1:-1]) / 2
        jacobian = np.empty((*core.shape, 2, 2), dtype=np.float64)
        jacobian[:, :, 0, 0], jacobian[:, :, 0, 1] = 1 - dx[:, :, 0], -dy[:, :, 0]
        jacobian[:, :, 1, 0], jacobian[:, :, 1, 1] = -dx[:, :, 1], 1 - dy[:, :, 1]
        selected = jacobian[core]
        singular = np.linalg.svd(selected, compute_uv=False)
        result[label] = {"maximum_local_length_change_percent": float(abs(singular - 1).max() * 100),
                         "minimum_inverse_map_determinant": float(np.linalg.det(selected).min())}
    return result


def geometry_measurements(prepared: body.PreparedRig) -> dict[str, Any]:
    region = prepared.regions["table_hand"]
    original_hand = body._hand_offsets
    points = region.points.astype(np.float64)
    distances = np.linalg.norm(points[:, None] - points[None, :], axis=2)
    contact = region.names.index(CONTACT_NAME)
    rows = []
    previous = None
    max_step = 0.0
    for frame in STUDY_FRAMES:
        old_offsets = original_hand(prepared, prepared.states[frame - 1])
        new_offsets = coherent_control_offsets(prepared, frame)
        weight = entry_weight(frame)
        mixed = old_offsets * (1.0 - weight) + new_offsets * weight
        candidate = points + mixed
        old_points = points + old_offsets
        old_error = float(abs(np.linalg.norm(old_points[:, None] - old_points[None, :], axis=2) - distances).max())
        candidate_error = float(abs(np.linalg.norm(candidate[:, None] - candidate[None, :], axis=2) - distances).max())
        if previous is not None:
            max_step = max(max_step, float(np.linalg.norm(candidate - previous, axis=1).max()))
        previous = candidate
        rows.append({"source_frame": frame, "output_frame": frame + 75,
                     "entry_weight": weight, "rock_degrees": rock_degrees(frame),
                     "old_max_pairwise_distance_change_px": old_error,
                     "candidate_max_pairwise_distance_change_px": candidate_error,
                     "contact_displacement_px": float(np.linalg.norm(mixed[contact])),
                     "maximum_control_excursion_px": float(np.linalg.norm(mixed, axis=1).max())})
    coherent = [row for row in rows if ENTRY_END <= row["source_frame"] <= 147]
    return {"rows": rows,
            "old_max_pairwise_distance_change_px": max(row["old_max_pairwise_distance_change_px"] for row in rows),
            "candidate_coherent_max_pairwise_distance_change_px": max(row["candidate_max_pairwise_distance_change_px"] for row in coherent),
            "candidate_entry_max_pairwise_distance_change_px": max(row["candidate_max_pairwise_distance_change_px"] for row in rows),
            "candidate_coherent_max_contact_displacement_px": max(row["contact_displacement_px"] for row in coherent),
            "candidate_max_adjacent_control_step_px": max_step,
            "candidate_max_control_excursion_px": max(row["maximum_control_excursion_px"] for row in rows),
            "peak_inverse_map_strain": peak_inverse_map_strain(prepared)}


def build_evidence(output: Path = OUTPUT_DEFAULT) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise ValueError(f"refusing to overwrite hand study: {output}")
    prepared = body.prepare_rig()
    support = native_hand_support(prepared)
    frames, sample_rows = [], []
    contact_sheet = Image.new("RGB", (780, 271 * 6), (12, 10, 9))
    sample_numbers = (91, 98, 104, 115, 130, 148)
    crop = NATIVE_CROP
    maximum_outside = 0
    maximum_protected = {name: 0 for name in prepared.protected}
    changed_frames = []
    for frame in STUDY_FRAMES:
        old = body.render_frame(prepared, frame)
        with hand_override(prepared, frame):
            candidate = body.render_frame(prepared, frame)
        changed = np.any(old.image != candidate.image, axis=2)
        outside = int((changed & ~support).sum())
        maximum_outside = max(maximum_outside, outside)
        for name, mask in prepared.protected.items():
            maximum_protected[name] = max(maximum_protected[name], int((changed & mask).sum()))
        if changed.any():
            changed_frames.append(frame)
        canvas = Image.new("RGB", (780, 271), (12, 10, 9))
        for column, (label, pixels) in enumerate((("Existing", old.image), ("Planted rock candidate", candidate.image))):
            canvas.paste(Image.fromarray(pixels[crop[1]:crop[3], crop[0]:crop[2]]), (column * 390, 30))
            ImageDraw.Draw(canvas).text((column * 390 + 6, 7), f"{label} / source {frame} / output {frame + 75}", fill=(245, 230, 210))
        frames.append(canvas)
        if frame in sample_numbers:
            contact_sheet.paste(canvas, (0, sample_numbers.index(frame) * 271))
            sample_rows.append({"source_frame": frame, "old_rgb_sha256": body._rgb_hash(old.image),
                                "candidate_rgb_sha256": body._rgb_hash(candidate.image),
                                "changed_pixels": int(changed.sum())})
    if maximum_outside or any(maximum_protected.values()):
        raise ValueError("hand study changed pixels outside its prospective support or protected pixels")
    if len(changed_frames) < 45 or 148 in changed_frames:
        raise ValueError("candidate must sustain an active gesture and exactly restore F148")
    output.mkdir(parents=True)
    durations = [round((index + 1) * 1000 / 30) - round(index * 1000 / 30) for index in range(len(frames))]
    sequence = output / "late-hand-native-ab-30fps-v1.webp"
    frames[0].save(sequence, save_all=True, append_images=frames[1:], duration=durations, lossless=True, loop=1)
    contact_sheet.save(output / "late-hand-native-keyframes-v1.png")
    for image in frames:
        image.close()
    contact_sheet.close()
    with Image.open(sequence) as readback:
        total_ms = 0
        for index in range(readback.n_frames):
            readback.seek(index)
            readback.load()
            total_ms += readback.info["duration"]
        if readback.n_frames != 58 or total_ms != 1933:
            raise ValueError("native sequence clock/readback mismatch")
    report = {"classification": "LOCAL_NATIVE_HAND_STUDY_HUMAN_REVIEW_PENDING",
              "human_accepted": False, "promotion_allowed": False, "full_scene_rendered": False,
              "source_frames_inclusive": [91, 148], "output_frames_inclusive": [166, 223],
              "output_time_seconds_half_open": [5.5, 223 / 30], "frame_count": 58,
              "native_crop_xyxy": list(crop), "native_scale": "1 source pixel per display pixel",
              "sequence_duration_ms": total_ms, "audio_included": False,
              "method": "late-only exact inverse Euclidean contact-pivot rock; C2 entry blend F091-F101",
              "peak_degrees": PEAK_DEGREES, "contact_control": CONTACT_NAME,
              "geometry": geometry_measurements(prepared), "sampled_native_hashes": sample_rows,
              "all_58_native_comparisons": {"maximum_changed_pixels_outside_hand_support": maximum_outside,
                                           "maximum_protected_changed_pixels": maximum_protected,
                                           "changed_source_frames": changed_frames,
                                           "rasterization_quiet_source_frames": [frame for frame in STUDY_FRAMES if frame not in changed_frames]},
              "cash_cost": 0, "network_calls": 0, "video_encoder_processes": 0,
              "limitations": ["Planar source-art motion, not a 3-D finger/contact model.",
                              "The entry blend temporarily retains the old geometry; the exact rigid phase starts F102.",
                              "Native geometry/support checks are not human proof of natural acting.",
                              "No full-scene encode or audio review; integration is tested separately at selected frames."],
              "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "artifacts": {path.name: {"bytes": path.stat().st_size,
                                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                            for path in sorted(output.iterdir())}}
    (output / "late-hand-study-report-v1.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    report = build_evidence(parser.parse_args().output)
    print(json.dumps({"classification": report["classification"], "frame_count": report["frame_count"],
                      "geometry": {key: value for key, value in report["geometry"].items() if key != "rows"}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
