"""Render June's GS060 pour from pinned RGBA poses and deterministic local liquid."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


POUR_LAYER_CONTRACT_VERSION = 1
EXPECTED_POSES = [
    "POSE_00_PENCIL_POISED",
    "POSE_15_PENCIL_DOWN",
    "POSE_30_GRASP_POT",
    "POSE_45_POT_LIFT",
    "POSE_55_PRE_POUR",
    "POSE_70_FULL_TILT",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_asset(contract_path: Path, specification: dict[str, Any], label: str) -> Path:
    repo_root = contract_path.parents[2]
    path = repo_root / str(specification.get("path", ""))
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    if _sha256(path) != specification.get("sha256"):
        raise ValueError(f"{label} hash does not match")
    return path


def _point(value: Any, label: str, size: tuple[int, int]) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be a two-value point")
    point = (float(value[0]), float(value[1]))
    if not 0.0 <= point[0] < size[0] or not 0.0 <= point[1] < size[1]:
        raise ValueError(f"{label} must stay inside the source canvas")
    return point


def _frame_range(value: Any, label: str, frame_count: int) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be a two-frame inclusive range")
    start, end = (int(item) for item in value)
    if not 1 <= start <= end <= frame_count:
        raise ValueError(f"{label} must stay inside the output clock")
    return start, end


def registration_offset(pose: dict[str, Any], registration: dict[str, Any]) -> tuple[float, float]:
    source = pose["source_contacts"]["mug_rim_center"]
    target = registration["target_mug_rim_center"]
    return float(target[0]) - float(source[0]), float(target[1]) - float(source[1])


def load_pour_layer_contract(
    path: str | Path,
) -> tuple[dict[str, Any], Path, dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != POUR_LAYER_CONTRACT_VERSION:
        raise ValueError(f"pour-layer contract_version must be {POUR_LAYER_CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley" or contract.get("shot_id") != "GS060":
        raise ValueError("pour-layer contract must explicitly target June Oxley GS060")
    if contract.get("gate") != "registered_pour_contact_and_liquid":
        raise ValueError("pour-layer contract must retain its registered contact and liquid gate")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0 or generation.get("paid_runtime_dependency") is not False:
        raise ValueError("pour-layer render must retain its zero-cash runtime contract")
    extraction = generation.get("foreground_extraction") or {}
    models = extraction.get("models") or []
    if [model.get("name") for model in models] != ["u2net", "u2net_human_seg"]:
        raise ValueError("pour-layer mattes must retain both pinned extraction model identities")
    for model in models:
        digest = str(model.get("sha256", ""))
        if len(digest) != 64:
            raise ValueError("every extraction model must retain a SHA-256 provenance digest")
    if extraction.get("runtime_required") is not False:
        raise ValueError("foreground extraction must remain a build-time, not runtime, dependency")

    canvas = contract.get("source_canvas") or {}
    source_size = (int(canvas.get("width", 0)), int(canvas.get("height", 0)))
    if source_size != (1672, 941):
        raise ValueError("pour-layer source canvas must remain exactly 1672x941")
    output = contract.get("output") or {}
    output_clock = (
        int(output.get("width", 0)),
        int(output.get("height", 0)),
        int(output.get("fps", 0)),
        int(output.get("frame_count", 0)),
    )
    if output_clock != (1920, 1080, 30, 258) or not math.isclose(
        float(output.get("duration_seconds", 0.0)), 8.6
    ):
        raise ValueError("pour-layer output must be exactly 1920x1080, 30 fps, 258 frames, and 8.6 seconds")
    review_frames = contract.get("review_frames") or []
    if review_frames != sorted(set(int(frame) for frame in review_frames)):
        raise ValueError("review frames must be ordered and unique")
    if len(review_frames) < 18 or review_frames[0] != 1 or review_frames[-1] != 258:
        raise ValueError("pour-layer review coverage must retain at least eighteen frames including both ends")

    _repo_asset(contract_path, contract.get("identity_reference") or {}, "canonical identity reference")
    _repo_asset(contract_path, contract.get("style_reference") or {}, "GS060 style reference")
    liquid_reference = contract.get("liquid_reference") or {}
    _repo_asset(contract_path, liquid_reference, "active-pour liquid reference")
    if liquid_reference.get("runtime_consumed") is not False:
        raise ValueError("active-pour reference must remain provenance-only")

    background_spec = contract.get("background") or {}
    background_path = _repo_asset(contract_path, background_spec, "clean GS060 porch background")
    with Image.open(background_path) as image:
        if image.size != source_size or image.mode != "RGB":
            raise ValueError("clean GS060 background does not match its RGB source-canvas contract")
    _repo_asset(contract_path, background_spec.get("source_provenance") or {}, "clean set provenance source")
    generation_spec = background_spec.get("image_generation") or {}
    if generation_spec.get("cash_cost") != 0 or generation_spec.get("paid_runtime_dependency") is not False:
        raise ValueError("clean GS060 background must retain zero-cash provenance")

    registration = contract.get("contact_registration") or {}
    target_mug = _point(registration.get("target_mug_rim_center"), "target mug rim center", source_size)
    maximum_residual = float(registration.get("maximum_mug_residual_px_source", -1.0))
    if not 0.0 <= maximum_residual <= 0.25:
        raise ValueError("mug registration residual gate must remain at or below a quarter source pixel")
    maximum_translation = float(registration.get("maximum_translation_px_source", 0.0))
    if not 1.0 <= maximum_translation <= 56.0:
        raise ValueError("mug registration translation bound must remain production-safe")
    grounded_pot = registration.get("grounded_pot_contact") or {}
    target_grounded_pot = _point(
        grounded_pot.get("target_registered_point"), "target registered pot-table contact", source_size
    )
    grounded_pose_ids = grounded_pot.get("pose_ids") or []
    if grounded_pose_ids != EXPECTED_POSES[:3]:
        raise ValueError("grounded pot gate must cover the three pre-lift production drawings")
    maximum_grounded_pot_residual = float(grounded_pot.get("maximum_residual_px_source", -1.0))
    if not 1.0 <= maximum_grounded_pot_residual <= 24.0:
        raise ValueError("grounded pot contact gate must remain at or below 24 source pixels")

    poses = contract.get("poses") or []
    if [pose.get("id") for pose in poses] != EXPECTED_POSES:
        raise ValueError("GS060 must retain its six ordered production drawings")
    if [float(pose.get("action_progress", -1.0)) for pose in poses] != [0.0, 0.15, 0.3, 0.45, 0.55, 0.7]:
        raise ValueError("GS060 production drawing progress markers changed")
    pose_paths: dict[str, Path] = {}
    for pose in poses:
        pose_id = str(pose["id"])
        foreground = pose.get("foreground") or {}
        foreground_path = _repo_asset(contract_path, foreground, f"foreground {pose_id}")
        with Image.open(foreground_path) as image:
            if image.size != source_size or image.mode != "RGBA":
                raise ValueError(f"foreground {pose_id} must remain a 1672x941 RGBA layer")
        _repo_asset(contract_path, pose.get("source_art") or {}, f"source art {pose_id}")
        source_contacts = pose.get("source_contacts") or {}
        source_mug = _point(source_contacts.get("mug_rim_center"), f"{pose_id} mug rim", source_size)
        dx, dy = registration_offset(pose, registration)
        if math.hypot(dx, dy) > maximum_translation:
            raise ValueError(f"{pose_id} exceeds the bounded mug registration translation")
        if not math.isclose(source_mug[0] + dx, target_mug[0], abs_tol=maximum_residual) or not math.isclose(
            source_mug[1] + dy, target_mug[1], abs_tol=maximum_residual
        ):
            raise ValueError(f"{pose_id} cannot satisfy the mug registration contact")
        for optional in ("spout_tip", "pot_table_contact"):
            if optional in source_contacts:
                _point(source_contacts[optional], f"{pose_id} {optional}", source_size)
        if pose_id in grounded_pose_ids:
            source_pot = _point(source_contacts.get("pot_table_contact"), f"{pose_id} pot-table contact", source_size)
            pot_residual = math.hypot(
                source_pot[0] + dx - target_grounded_pot[0],
                source_pot[1] + dy - target_grounded_pot[1],
            )
            if pot_residual > maximum_grounded_pot_residual:
                raise ValueError(f"{pose_id} exceeds the grounded pot contact gate")
        pose_paths[pose_id] = foreground_path

    timeline = contract.get("timeline") or []
    expected_start = 1
    for entry in timeline:
        start = int(entry.get("start_frame", 0))
        end = int(entry.get("end_frame", 0))
        if start != expected_start or end < start:
            raise ValueError("pour-layer timeline must be contiguous, ordered, and non-empty")
        expected_start = end + 1
        if entry.get("type") == "pose":
            if entry.get("pose_id") not in pose_paths:
                raise ValueError("pour-layer timeline references an unknown pose")
        elif entry.get("type") == "smear":
            if start != end:
                raise ValueError("every GS060 directional smear must be exactly one frame")
            if entry.get("from_pose_id") not in pose_paths or entry.get("to_pose_id") not in pose_paths:
                raise ValueError("pour-layer smear references an unknown pose")
            travel = entry.get("travel")
            if not isinstance(travel, list) or len(travel) != 2 or math.hypot(float(travel[0]), float(travel[1])) > 18.0:
                raise ValueError("pour-layer smear travel must remain a bounded two-axis vector")
        else:
            raise ValueError("pour-layer timeline supports only clean poses and one-frame smears")
    if expected_start != int(output["frame_count"]) + 1:
        raise ValueError("pour-layer timeline must cover every output frame exactly once")

    liquid = contract.get("liquid") or {}
    active_pose_id = liquid.get("active_pose_id")
    if active_pose_id not in pose_paths:
        raise ValueError("liquid active pose must reference a pinned GS060 drawing")
    onset = _frame_range(liquid.get("onset_frames"), "liquid onset", 258)
    continuous = _frame_range(liquid.get("continuous_frames"), "continuous liquid", 258)
    taper = _frame_range(liquid.get("taper_frames"), "liquid taper", 258)
    if not (onset[1] + 1 == continuous[0] and continuous[1] + 1 == taper[0]):
        raise ValueError("liquid onset, continuous pour, and taper must be contiguous")
    for frame_index in range(onset[0], taper[1] + 1):
        entry = timeline_entry_for_frame(timeline, frame_index)
        if entry.get("type") != "pose" or entry.get("pose_id") != active_pose_id:
            raise ValueError("the entire liquid interval must retain the registered full-tilt pose")
    active_pose = next(pose for pose in poses if pose["id"] == active_pose_id)
    source_spout = _point(active_pose["source_contacts"].get("spout_tip"), "active-pose spout tip", source_size)
    registered_spout = _point(liquid.get("registered_spout_tip"), "registered spout tip", source_size)
    dx, dy = registration_offset(active_pose, registration)
    start_error = math.hypot(source_spout[0] + dx - registered_spout[0], source_spout[1] + dy - registered_spout[1])
    contact_gate = liquid.get("contact_gate") or {}
    maximum_start_error = float(contact_gate.get("maximum_spout_start_error_px_source", -1.0))
    if not 0.0 <= maximum_start_error <= 0.25 or start_error > maximum_start_error:
        raise ValueError("registered liquid origin does not lock to the full-tilt spout")
    if int(contact_gate.get("maximum_spill_pixels_source", -1)) != 0:
        raise ValueError("GS060 liquid must retain a zero-rendered-spill gate")
    landing = _point(liquid.get("landing_point"), "liquid landing point", source_size)
    ellipse = liquid.get("receiving_ellipse") or {}
    ellipse_center = _point(ellipse.get("center"), "receiving ellipse center", source_size)
    radius_x = float(ellipse.get("radius_x", 0.0))
    radius_y = float(ellipse.get("radius_y", 0.0))
    if not 10.0 <= radius_x <= 90.0 or not 4.0 <= radius_y <= 24.0:
        raise ValueError("receiving ellipse radii are outside production bounds")
    normalized_landing = ((landing[0] - ellipse_center[0]) / radius_x) ** 2 + (
        (landing[1] - ellipse_center[1]) / radius_y
    ) ** 2
    if normalized_landing > 0.8:
        raise ValueError("liquid landing point must remain safely inside the mug receiving ellipse")
    stream = liquid.get("stream") or {}
    if not 3.0 <= float(stream.get("maximum_width_px_source", 0.0)) <= 16.0:
        raise ValueError("coffee stream width is outside the authored production range")
    occlusion = liquid.get("mug_front_occlusion") or {}
    bounds = occlusion.get("bounds")
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError("mug-front occlusion must define four source-canvas bounds")
    left, top, right, bottom = (int(value) for value in bounds)
    if not 0 <= left < right <= source_size[0] or not 0 <= top < bottom <= source_size[1]:
        raise ValueError("mug-front occlusion bounds must stay inside the source canvas")
    if int(occlusion.get("top_y", -1)) != top:
        raise ValueError("mug-front occlusion top must match its contracted bounds")

    camera = contract.get("camera") or {}
    if camera.get("easing") != "ease_in_out_cubic":
        raise ValueError("pour-layer camera must use cubic easing")
    for key in ("start_zoom", "end_zoom"):
        if not 1.0 <= float(camera.get(key, 0.0)) <= 1.1:
            raise ValueError("pour-layer camera zoom must stay within the subtle 1x-1.1x range")
    for key in ("focus_start", "focus_end"):
        focus = camera.get(key)
        if not isinstance(focus, list) or len(focus) != 2 or not all(0.0 <= float(item) <= 1.0 for item in focus):
            raise ValueError("pour-layer camera focus must be normalized")
    quality = contract.get("encoded_quality_gate") or {}
    if not 30.0 <= float(quality.get("minimum_review_frame_psnr_db", 0.0)) <= 60.0:
        raise ValueError("pour-layer quality gate must define a meaningful PSNR floor")
    if not 1.0 <= float(quality.get("minimum_review_frame_laplacian_variance", 0.0)) <= 1000.0:
        raise ValueError("pour-layer quality gate must define a meaningful retained-detail floor")
    visibility = contract.get("visibility_audit") or {}
    for item in ("face", "ledger", "pencil", "coffee_pot", "mug", "coffee_stream"):
        if visibility.get(item) is not True:
            raise ValueError(f"GS060 visibility audit lost required item: {item}")
    if visibility.get("support_foot") is not False or not str(visibility.get("support_foot_remediation", "")).strip():
        raise ValueError("GS060 must retain the honest support-foot exception and remediation")
    return contract, background_path, pose_paths


def timeline_entry_for_frame(timeline: list[dict[str, Any]], frame_index: int) -> dict[str, Any]:
    for entry in timeline:
        if int(entry["start_frame"]) <= frame_index <= int(entry["end_frame"]):
            return entry
    raise ValueError(f"frame {frame_index} is not covered by the pour-layer timeline")


def registered_pose_layer(
    image: Image.Image,
    pose: dict[str, Any],
    registration: dict[str, Any],
) -> tuple[Image.Image, dict[str, Any]]:
    dx, dy = registration_offset(pose, registration)
    if not math.isclose(dx, round(dx), abs_tol=1e-6) or not math.isclose(dy, round(dy), abs_tol=1e-6):
        raise ValueError("GS060 pinned mug anchors must resolve to integer-pixel registration")
    canvas = Image.new("RGBA", image.size, (0, 0, 0, 0))
    canvas.alpha_composite(image.convert("RGBA"), (int(round(dx)), int(round(dy))))
    source_mug = pose["source_contacts"]["mug_rim_center"]
    target_mug = registration["target_mug_rim_center"]
    residual = math.hypot(
        float(source_mug[0]) + dx - float(target_mug[0]),
        float(source_mug[1]) + dy - float(target_mug[1]),
    )
    transformed: dict[str, list[float]] = {}
    for name, point in pose["source_contacts"].items():
        transformed[name] = [round(float(point[0]) + dx, 3), round(float(point[1]) + dy, 3)]
    report = {
        "pose_id": pose["id"],
        "translation": [round(dx, 3), round(dy, 3)],
        "mug_rim_residual_px_source": round(residual, 6),
        "transformed_contacts": transformed,
    }
    return canvas, report


def _shift_array(source: np.ndarray, dx: int, dy: int) -> np.ndarray:
    result = np.zeros_like(source)
    height, width = source.shape[:2]
    source_x0 = max(0, -dx)
    source_x1 = min(width, width - dx)
    source_y0 = max(0, -dy)
    source_y1 = min(height, height - dy)
    if source_x1 <= source_x0 or source_y1 <= source_y0:
        return result
    destination_x0 = source_x0 + dx
    destination_x1 = source_x1 + dx
    destination_y0 = source_y0 + dy
    destination_y1 = source_y1 + dy
    result[destination_y0:destination_y1, destination_x0:destination_x1] = source[
        source_y0:source_y1, source_x0:source_x1
    ]
    return result


def directional_smear(layer: Image.Image, travel: tuple[int, int] | list[int]) -> Image.Image:
    dx, dy = (int(value) for value in travel)
    if math.hypot(dx, dy) <= 0.0 or math.hypot(dx, dy) > 18.0:
        raise ValueError("directional smear travel must stay between one and eighteen source pixels")
    rgba = np.asarray(layer.convert("RGBA"), dtype=np.float32) / 255.0
    alpha = rgba[:, :, 3:4]
    premultiplied = np.concatenate((rgba[:, :, :3] * alpha, alpha), axis=2)
    weights = np.array([0.06, 0.09, 0.14, 0.19, 0.23, 0.29], dtype=np.float32)
    result = np.zeros_like(premultiplied)
    for amount, weight in zip(np.linspace(1.0, 0.0, len(weights)), weights):
        result += _shift_array(premultiplied, int(round(dx * amount)), int(round(dy * amount))) * float(weight)
    output_alpha = np.clip(result[:, :, 3:4], 0.0, 1.0)
    output_rgb = np.zeros_like(result[:, :, :3])
    np.divide(result[:, :, :3], np.maximum(output_alpha, 1e-6), out=output_rgb, where=output_alpha > 1e-6)
    output = np.concatenate((np.clip(output_rgb, 0.0, 1.0), output_alpha), axis=2)
    return Image.fromarray(np.round(output * 255.0).astype(np.uint8), mode="RGBA")


def liquid_state(liquid: dict[str, Any], frame_index: int) -> dict[str, Any]:
    onset_start, onset_end = (int(value) for value in liquid["onset_frames"])
    continuous_start, continuous_end = (int(value) for value in liquid["continuous_frames"])
    taper_start, taper_end = (int(value) for value in liquid["taper_frames"])
    state = {
        "phase": "none",
        "strength": 0.0,
        "path_fraction": 0.0,
        "connected": False,
        "droplet_mode": False,
    }
    if onset_start <= frame_index <= onset_end:
        progress = (frame_index - onset_start + 1) / (onset_end - onset_start + 1)
        state.update(
            phase="onset",
            strength=0.24 + 0.76 * progress,
            path_fraction=min(1.0, progress / 0.625),
            connected=progress >= 0.625,
        )
    elif continuous_start <= frame_index <= continuous_end:
        state.update(
            phase="continuous",
            strength=0.96 + 0.04 * math.sin((frame_index - continuous_start) * 0.61),
            path_fraction=1.0,
            connected=True,
        )
    elif taper_start <= frame_index <= taper_end:
        progress = (frame_index - taper_start) / max(1, taper_end - taper_start)
        connected = progress < 0.57
        state.update(
            phase="taper",
            strength=max(0.12, 1.0 - progress * 0.88),
            path_fraction=1.0 if connected else 0.0,
            connected=connected,
            droplet_mode=not connected,
        )
    return state


def _bezier_points(
    start: tuple[float, float],
    end: tuple[float, float],
    curve_bias: float,
    wobble: float,
    frame_index: int,
    count: int = 36,
) -> list[tuple[float, float]]:
    control = (
        start[0] + (end[0] - start[0]) * (0.62 + curve_bias * 0.22),
        start[1] + (end[1] - start[1]) * 0.43,
    )
    points = []
    for index in range(count):
        amount = index / (count - 1)
        inverse = 1.0 - amount
        x = inverse * inverse * start[0] + 2.0 * inverse * amount * control[0] + amount * amount * end[0]
        y = inverse * inverse * start[1] + 2.0 * inverse * amount * control[1] + amount * amount * end[1]
        x += math.sin(frame_index * 0.47 + amount * 8.4) * wobble * math.sin(math.pi * amount)
        points.append((x, y))
    return points


def _ellipse_value(point: tuple[float, float], ellipse: dict[str, Any]) -> float:
    center_x, center_y = (float(value) for value in ellipse["center"])
    radius_x = float(ellipse["radius_x"])
    radius_y = float(ellipse["radius_y"])
    return ((point[0] - center_x) / radius_x) ** 2 + ((point[1] - center_y) / radius_y) ** 2


def render_liquid_layer(
    liquid: dict[str, Any],
    frame_index: int,
    size: tuple[int, int],
) -> tuple[Image.Image, dict[str, Any]]:
    state = liquid_state(liquid, frame_index)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    start = tuple(float(value) for value in liquid["registered_spout_tip"])
    landing = tuple(float(value) for value in liquid["landing_point"])
    report = {
        "frame": frame_index,
        **state,
        "start_point": [start[0], start[1]],
        "landing_point": [landing[0], landing[1]],
        "spout_start_error_px_source": 0.0,
        "candidate_spill_pixels_source": 0,
        "rendered_spill_pixels_source": 0,
    }
    if state["phase"] == "none":
        return layer, report
    stream = liquid["stream"]
    points = _bezier_points(
        start,
        landing,
        float(stream["curve_bias"]),
        float(stream["micro_wobble_px"]),
        frame_index,
    )
    draw = ImageDraw.Draw(layer)
    maximum_width = float(stream["maximum_width_px_source"])
    width = max(2, int(round(maximum_width * float(state["strength"]))))
    if state["droplet_mode"]:
        taper_start = int(liquid["taper_frames"][0])
        step = frame_index - taper_start
        for index in range(3):
            amount = min(0.94, 0.10 + ((step * 0.19 + index * 0.29) % 0.92))
            point = points[int(round(amount * (len(points) - 1)))]
            radius = max(2, int(round(width * (0.38 + index * 0.08))))
            draw.ellipse(
                (point[0] - radius, point[1] - radius * 1.35, point[0] + radius, point[1] + radius * 1.35),
                fill=tuple(int(value) for value in stream["mid_color"]),
            )
    else:
        point_count = max(2, int(round((len(points) - 1) * float(state["path_fraction"]))) + 1)
        visible = points[:point_count]
        draw.line(visible, fill=tuple(int(value) for value in stream["base_color"]), width=width, joint="curve")
        draw.line(
            visible,
            fill=tuple(int(value) for value in stream["mid_color"]),
            width=max(2, int(round(width * 0.62))),
            joint="curve",
        )
        draw.line(
            [(x - 1.2, y) for x, y in visible],
            fill=tuple(int(value) for value in stream["highlight_color"]),
            width=max(1, int(round(width * 0.19))),
            joint="curve",
        )
    contact_radius = max(1, int(round(width * 0.42)))
    draw.ellipse(
        (
            start[0] - contact_radius,
            start[1] - contact_radius,
            start[0] + contact_radius,
            start[1] + contact_radius,
        ),
        fill=tuple(int(value) for value in stream["mid_color"]),
    )

    alpha = np.asarray(layer.getchannel("A"), dtype=np.uint8).copy()
    ellipse = liquid["receiving_ellipse"]
    center_x, center_y = (float(value) for value in ellipse["center"])
    radius_x = float(ellipse["radius_x"])
    radius_y = float(ellipse["radius_y"])
    y_coordinates, x_coordinates = np.indices((size[1], size[0]))
    receiver_zone = y_coordinates >= int(math.floor(center_y - radius_y))
    ellipse_mask = ((x_coordinates - center_x) / radius_x) ** 2 + ((y_coordinates - center_y) / radius_y) ** 2 <= 1.0
    candidate_spill = (alpha > 0) & receiver_zone & ~ellipse_mask
    report["candidate_spill_pixels_source"] = int(np.count_nonzero(candidate_spill))
    alpha[candidate_spill] = 0
    layer.putalpha(Image.fromarray(alpha, mode="L"))
    rendered_alpha = np.asarray(layer.getchannel("A"), dtype=np.uint8)
    rendered_spill = (rendered_alpha > 0) & receiver_zone & ~ellipse_mask
    report["rendered_spill_pixels_source"] = int(np.count_nonzero(rendered_spill))
    report["landing_ellipse_value"] = round(_ellipse_value(landing, ellipse), 6)
    return layer, report


def _coffee_surface_overlay(
    image: Image.Image,
    liquid: dict[str, Any],
    frame_index: int,
) -> Image.Image:
    first_landing = int(liquid["onset_frames"][0]) + 4
    if frame_index < first_landing:
        return image.convert("RGBA")
    active_end = int(liquid["continuous_frames"][1])
    fill = min(1.0, (frame_index - first_landing + 1) / max(1, active_end - first_landing + 1))
    ellipse = liquid["receiving_ellipse"]
    center_x, center_y = (float(value) for value in ellipse["center"])
    radius_x = float(ellipse["radius_x"]) * (0.86 + fill * 0.08)
    radius_y = float(ellipse["radius_y"]) * (0.55 + fill * 0.18)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse(
        (center_x - radius_x, center_y - radius_y, center_x + radius_x, center_y + radius_y),
        fill=(72, 31, 14, int(118 + fill * 72)),
    )
    draw.arc(
        (center_x - radius_x + 5, center_y - radius_y + 2, center_x + radius_x - 5, center_y + radius_y - 2),
        190,
        345,
        fill=(220, 142, 60, int(74 + fill * 48)),
        width=2,
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.45))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def _mug_front_occlusion(image: Image.Image, registered_layer: Image.Image, liquid: dict[str, Any]) -> Image.Image:
    left, top, right, bottom = (int(value) for value in liquid["mug_front_occlusion"]["bounds"])
    patch = registered_layer.crop((left, top, right, bottom))
    result = image.convert("RGBA")
    result.alpha_composite(patch, (left, top))
    patch.close()
    return result


def _steam_overlay(
    image: Image.Image,
    specification: dict[str, Any],
    frame_index: int,
    fps: int,
) -> Image.Image:
    if frame_index < int(specification["start_frame"]):
        return image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    origin_x, origin_y = (float(value) for value in specification["origin"])
    time_seconds = (frame_index - int(specification["start_frame"])) / fps
    strength = float(specification["strength"])
    for strand in range(int(specification["strand_count"])):
        phase = strand * 0.43
        progress = (time_seconds * (0.23 + strand * 0.015) + phase) % 1.0
        points = []
        for step in range(11):
            rise = step * (7.2 + strand * 0.35) + progress * 18.0
            wave = math.sin(time_seconds * 1.55 + step * 0.66 + phase * 6.0) * (3.4 + step * 0.48)
            points.append((origin_x + (strand - 1) * 10.0 + wave, origin_y - rise))
        alpha = int((80.0 - progress * 30.0) * strength)
        draw.line(points, fill=(247, 240, 225, max(6, alpha)), width=4)
    overlay = overlay.filter(ImageFilter.GaussianBlur(3.2))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def _ease_in_out_cubic(amount: float) -> float:
    amount = max(0.0, min(1.0, float(amount)))
    if amount < 0.5:
        return 4.0 * amount * amount * amount
    return 1.0 - pow(-2.0 * amount + 2.0, 3.0) / 2.0


def _camera_crop_box(
    source_size: tuple[int, int],
    output_size: tuple[int, int],
    zoom: float,
    focus: tuple[float, float],
) -> tuple[int, int, int, int]:
    source_width, source_height = source_size
    output_width, output_height = output_size
    output_aspect = output_width / output_height
    source_aspect = source_width / source_height
    if source_aspect >= output_aspect:
        base_height = source_height
        base_width = int(round(base_height * output_aspect))
    else:
        base_width = source_width
        base_height = int(round(base_width / output_aspect))
    crop_width = max(2, min(source_width, int(round(base_width / zoom))))
    crop_height = max(2, min(source_height, int(round(base_height / zoom))))
    center_x = focus[0] * source_width
    center_y = focus[1] * source_height
    left = max(0, min(source_width - crop_width, int(round(center_x - crop_width / 2.0))))
    top = max(0, min(source_height - crop_height, int(round(center_y - crop_height / 2.0))))
    return left, top, left + crop_width, top + crop_height


def _camera_frame(
    image: Image.Image,
    camera: dict[str, Any],
    amount: float,
    output_size: tuple[int, int],
) -> Image.Image:
    eased = _ease_in_out_cubic(amount)
    zoom = float(camera["start_zoom"]) + (float(camera["end_zoom"]) - float(camera["start_zoom"])) * eased
    focus = tuple(
        float(camera["focus_start"][index])
        + (float(camera["focus_end"][index]) - float(camera["focus_start"][index])) * eased
        for index in range(2)
    )
    return image.crop(_camera_crop_box(image.size, output_size, zoom, focus)).resize(
        output_size, Image.Resampling.LANCZOS
    )


def compose_pour_frame(
    background: Image.Image,
    registered_layer: Image.Image,
    contract: dict[str, Any],
    frame_index: int,
) -> tuple[Image.Image, dict[str, Any]]:
    frame = Image.alpha_composite(background.convert("RGBA"), registered_layer)
    frame = _coffee_surface_overlay(frame, contract["liquid"], frame_index)
    liquid_layer, liquid_report = render_liquid_layer(contract["liquid"], frame_index, background.size)
    frame = Image.alpha_composite(frame, liquid_layer)
    frame = _mug_front_occlusion(frame, registered_layer, contract["liquid"])
    frame = _steam_overlay(frame, contract["effects"]["steam"], frame_index, int(contract["output"]["fps"]))
    light_strength = float(contract["effects"]["light_breathe"]["strength"])
    factor = 1.0 + light_strength * math.sin((frame_index - 1) / 30.0 * math.pi * 0.69)
    frame = ImageEnhance.Brightness(frame.convert("RGB")).enhance(factor)
    amount = (frame_index - 1) / max(1, int(contract["output"]["frame_count"]) - 1)
    output_size = (int(contract["output"]["width"]), int(contract["output"]["height"]))
    return _camera_frame(frame, contract["camera"], amount, output_size), liquid_report


def _resolve_executable(name: str) -> str:
    explicit = Path(name)
    resolved = str(explicit) if explicit.is_file() else shutil.which(name)
    if not resolved:
        raise FileNotFoundError(f"executable not found: {name}")
    return resolved


def _has_audio(path: Path, ffprobe: str) -> bool:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _media_probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,pix_fmt,r_frame_rate,nb_frames,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _laplacian_variance(rgb: np.ndarray) -> float:
    gray = rgb[:, :, 0].astype(np.float64) * 0.299 + rgb[:, :, 1].astype(np.float64) * 0.587 + rgb[:, :, 2].astype(np.float64) * 0.114
    laplacian = (
        gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
        - 4.0 * gray[1:-1, 1:-1]
    )
    return float(laplacian.var())


def encoded_quality_metrics(
    video: Path,
    review_frames: dict[int, Path],
    expected_frame_count: int,
    size: tuple[int, int],
    ffmpeg: str,
) -> dict[str, Any]:
    width, height = size
    frame_bytes = width * height * 3
    command = [ffmpeg, "-v", "error", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdout is None or process.stderr is None:
        raise RuntimeError("unable to open encoded-quality decode pipe")
    targets = set(review_frames)
    decoded: dict[int, np.ndarray] = {}
    frame_index = 0
    while True:
        payload = process.stdout.read(frame_bytes)
        if not payload:
            break
        if len(payload) != frame_bytes:
            process.kill()
            raise RuntimeError("encoded-quality decoder returned a partial frame")
        frame_index += 1
        if frame_index in targets:
            decoded[frame_index] = np.frombuffer(payload, dtype=np.uint8).reshape((height, width, 3)).copy()
    error_output = process.stderr.read().decode("utf-8", errors="replace")
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"encoded-quality decode failed: {error_output.strip()}")
    if frame_index != expected_frame_count or set(decoded) != targets:
        raise RuntimeError("encoded quality measurement did not decode the exact review-frame clock")
    rows = []
    for target in sorted(targets):
        source = np.asarray(Image.open(review_frames[target]).convert("RGB"), dtype=np.uint8)
        encoded = decoded[target]
        difference = source.astype(np.float64) - encoded.astype(np.float64)
        mse = float(np.mean(difference * difference))
        psnr = 99.0 if mse == 0.0 else 20.0 * math.log10(255.0 / math.sqrt(mse))
        rows.append(
            {
                "frame": target,
                "psnr_db": round(psnr, 3),
                "encoded_laplacian_variance": round(_laplacian_variance(encoded), 3),
            }
        )
    return {
        "sample_count": len(rows),
        "decoded_frame_count": frame_index,
        "minimum_psnr_db": min(row["psnr_db"] for row in rows),
        "mean_psnr_db": round(sum(row["psnr_db"] for row in rows) / len(rows), 3),
        "minimum_encoded_laplacian_variance": min(row["encoded_laplacian_variance"] for row in rows),
        "frames": rows,
    }


def render_pour_layer_sequence(
    contract_path: str | Path,
    output_dir: str | Path,
    *,
    audio_source: str | Path | None = None,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    contract, background_path, pose_paths = load_pour_layer_contract(contract_path)
    output = Path(output_dir).resolve()
    review_dir = output / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    for stale in review_dir.glob("frame_*.png"):
        stale.unlink()
    ffmpeg_bin = _resolve_executable(ffmpeg)
    ffprobe_bin = _resolve_executable(ffprobe)
    output_spec = contract["output"]
    width = int(output_spec["width"])
    height = int(output_spec["height"])
    fps = int(output_spec["fps"])
    frame_count = int(output_spec["frame_count"])
    background = Image.open(background_path).convert("RGB")
    pose_by_id = {pose["id"]: pose for pose in contract["poses"]}
    registered: dict[str, Image.Image] = {}
    contact_rows: list[dict[str, Any]] = []
    for pose_id, path in pose_paths.items():
        with Image.open(path) as source:
            layer, contact = registered_pose_layer(source, pose_by_id[pose_id], contract["contact_registration"])
        registered[pose_id] = layer
        contact_rows.append(contact)
    smears: dict[int, Image.Image] = {}
    for entry in contract["timeline"]:
        if entry["type"] == "smear":
            smears[int(entry["start_frame"])] = directional_smear(registered[entry["to_pose_id"]], entry["travel"])

    review_numbers = set(int(frame) for frame in contract["review_frames"])
    saved: dict[int, Path] = {}
    liquid_rows: list[dict[str, Any]] = []
    video_only = output / "june-gs060-layered-pour.video-only.partial.mp4"
    video_only.unlink(missing_ok=True)
    command = [
        ffmpeg_bin,
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "16",
        "-pix_fmt",
        "yuv420p",
        "-frames:v",
        str(frame_count),
        "-movflags",
        "+faststart",
        str(video_only),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdin is None or process.stderr is None:
        raise RuntimeError("unable to open FFmpeg GS060 raw-video pipe")
    try:
        for frame_index in range(1, frame_count + 1):
            entry = timeline_entry_for_frame(contract["timeline"], frame_index)
            if entry["type"] == "pose":
                pose_id = entry["pose_id"]
                layer = registered[pose_id]
            else:
                pose_id = entry["to_pose_id"]
                layer = smears[frame_index]
            frame, liquid_report = compose_pour_frame(background, layer, contract, frame_index)
            liquid_rows.append(liquid_report)
            process.stdin.write(np.asarray(frame, dtype=np.uint8).tobytes())
            if frame_index in review_numbers:
                destination = review_dir / f"frame_{frame_index:04d}.png"
                frame.save(destination, compress_level=2)
                saved[frame_index] = destination
        process.stdin.close()
        error_output = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
    except BaseException:
        process.kill()
        raise
    finally:
        background.close()
        for image in registered.values():
            image.close()
        for image in smears.values():
            image.close()
    if return_code != 0:
        video_only.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg GS060 render failed: {error_output.strip()}")
    if not video_only.is_file() or video_only.stat().st_size <= 0:
        raise RuntimeError("FFmpeg did not create a usable GS060 video")

    video = output / "june-gs060-layered-pour.mp4"
    partial = output / "june-gs060-layered-pour.partial.mp4"
    partial.unlink(missing_ok=True)
    audio_path = Path(audio_source).resolve() if audio_source else None
    audio_included = False
    if audio_path is not None:
        if not audio_path.is_file() or not _has_audio(audio_path, ffprobe_bin):
            raise ValueError("audio source must contain a readable audio stream")
        duration = float(output_spec["duration_seconds"])
        audio_filter = (
            f"atrim=start=0:end={duration:.6f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.03,afade=t=out:st={duration - 0.03:.6f}:d=0.03,"
            f"apad=pad_dur={duration:.6f}"
        )
        result = subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-v",
                "error",
                "-i",
                str(video_only),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-af",
                audio_filter,
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-t",
                f"{duration:.6f}",
                "-movflags",
                "+faststart",
                str(partial),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(f"FFmpeg GS060 audio mux failed: {result.stderr.strip()}")
        video_only.unlink(missing_ok=True)
        audio_included = True
    else:
        video_only.replace(partial)
    partial.replace(video)

    quality = encoded_quality_metrics(video, saved, frame_count, (width, height), ffmpeg_bin)
    quality_gate = contract["encoded_quality_gate"]
    if quality["minimum_psnr_db"] < float(quality_gate["minimum_review_frame_psnr_db"]):
        raise RuntimeError("encoded GS060 sequence failed its PSNR gate")
    if quality["minimum_encoded_laplacian_variance"] < float(
        quality_gate["minimum_review_frame_laplacian_variance"]
    ):
        raise RuntimeError("encoded GS060 sequence failed its retained-detail gate")
    maximum_mug_residual = max(float(row["mug_rim_residual_px_source"]) for row in contact_rows)
    if maximum_mug_residual > float(contract["contact_registration"]["maximum_mug_residual_px_source"]):
        raise RuntimeError("registered GS060 pose exceeds the mug contact gate")
    grounded_pot_contract = contract["contact_registration"]["grounded_pot_contact"]
    grounded_pot_target = tuple(float(value) for value in grounded_pot_contract["target_registered_point"])
    grounded_pot_pose_ids = set(grounded_pot_contract["pose_ids"])
    grounded_pot_rows = []
    for row in contact_rows:
        if row["pose_id"] not in grounded_pot_pose_ids:
            continue
        point = tuple(float(value) for value in row["transformed_contacts"]["pot_table_contact"])
        grounded_pot_rows.append(
            {
                "pose_id": row["pose_id"],
                "registered_point": [point[0], point[1]],
                "residual_px_source": round(
                    math.hypot(point[0] - grounded_pot_target[0], point[1] - grounded_pot_target[1]), 6
                ),
            }
        )
    maximum_grounded_pot_residual = max(float(row["residual_px_source"]) for row in grounded_pot_rows)
    if maximum_grounded_pot_residual > float(grounded_pot_contract["maximum_residual_px_source"]):
        raise RuntimeError("registered GS060 pre-lift drawing exceeds the grounded pot contact gate")
    maximum_spill = max(int(row["rendered_spill_pixels_source"]) for row in liquid_rows)
    if maximum_spill > int(contract["liquid"]["contact_gate"]["maximum_spill_pixels_source"]):
        raise RuntimeError("GS060 liquid exceeds the zero-spill gate")
    maximum_start_error = max(float(row["spout_start_error_px_source"]) for row in liquid_rows)
    if maximum_start_error > float(contract["liquid"]["contact_gate"]["maximum_spout_start_error_px_source"]):
        raise RuntimeError("GS060 liquid origin exceeds the spout contact gate")
    sample_frames = set(contract["review_frames"]) | {
        int(contract["liquid"]["onset_frames"][0]),
        int(contract["liquid"]["onset_frames"][1]),
        int(contract["liquid"]["continuous_frames"][0]),
        int(contract["liquid"]["continuous_frames"][1]),
        int(contract["liquid"]["taper_frames"][0]),
        int(contract["liquid"]["taper_frames"][1]),
    }
    liquid_samples = [row for row in liquid_rows if int(row["frame"]) in sample_frames]

    report = {
        "contract_version": POUR_LAYER_CONTRACT_VERSION,
        "gate": contract["gate"],
        "classification": contract["classification"],
        "performance_id": contract["performance_id"],
        "contract_sha256": _sha256(Path(contract_path).resolve()),
        "background": {"file": background_path.name, "sha256": _sha256(background_path)},
        "poses": [
            {
                "id": pose["id"],
                "foreground": Path(pose["foreground"]["path"]).name,
                "sha256": pose["foreground"]["sha256"],
                "action_progress": pose["action_progress"],
            }
            for pose in contract["poses"]
        ],
        "render_method": "stable clean set + mug-registered RGBA production drawings + one-frame directional smears + deterministic clipped Bezier liquid",
        "optical_flow_used": False,
        "cross_dissolve_used": False,
        "paid_runtime_generation_used": False,
        "contact_registration": contact_rows,
        "maximum_mug_residual_px_source": maximum_mug_residual,
        "grounded_pot_contact": {
            "target_registered_point": list(grounded_pot_target),
            "maximum_residual_px_source": maximum_grounded_pot_residual,
            "poses": grounded_pot_rows,
        },
        "liquid": {
            "reference_runtime_consumed": False,
            "onset_frames": contract["liquid"]["onset_frames"],
            "continuous_frames": contract["liquid"]["continuous_frames"],
            "taper_frames": contract["liquid"]["taper_frames"],
            "landing_ellipse_value": round(
                _ellipse_value(tuple(contract["liquid"]["landing_point"]), contract["liquid"]["receiving_ellipse"]),
                6,
            ),
            "maximum_spout_start_error_px_source": maximum_start_error,
            "maximum_rendered_spill_pixels_source": maximum_spill,
            "maximum_candidate_pixels_clipped_at_receiver": max(
                int(row["candidate_spill_pixels_source"]) for row in liquid_rows
            ),
            "samples": liquid_samples,
        },
        "visibility_audit": contract["visibility_audit"],
        "audio": {
            "included": audio_included,
            "source": audio_path.name if audio_path else None,
            "source_sha256": _sha256(audio_path) if audio_path else None,
            "boundary_fades_ms": 30 if audio_included else None,
        },
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": output_spec["duration_seconds"],
        "review_frames": [path.name for _, path in sorted(saved.items())],
        "encoded_quality": quality,
        "media_probe": _media_probe(video, ffprobe_bin),
        "video": video.name,
        "video_sha256": _sha256(video),
    }
    report_path = output / "june-gs060-layered-pour-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render June's registered GS060 layered coffee pour")
    parser.add_argument("contract")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--audio-source")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = render_pour_layer_sequence(
        args.contract,
        args.output_dir,
        audio_source=args.audio_source,
        ffmpeg=args.ffmpeg,
        ffprobe=args.ffprobe,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
