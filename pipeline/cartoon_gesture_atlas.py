"""Validate and interpolate registered June hand/prop pose plates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


GESTURE_CONTRACT_VERSION = 1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _asset(contract_path: Path, specification: dict[str, Any], label: str) -> Path:
    path = contract_path.parents[2] / str(specification.get("path", ""))
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    if _sha256(path) != specification.get("sha256"):
        raise ValueError(f"{label} hash does not match")
    return path


def load_gesture_atlas_contract(path: str | Path) -> tuple[dict[str, Any], dict[str, Path]]:
    contract_path = Path(path).resolve()
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("contract_version") != GESTURE_CONTRACT_VERSION:
        raise ValueError(f"gesture contract_version must be {GESTURE_CONTRACT_VERSION}")
    if contract.get("character_id") != "june_oxley":
        raise ValueError("gesture atlas must explicitly target June Oxley")
    if contract.get("neutral_state") != "neutral":
        raise ValueError("gesture neutral_state must be neutral")
    generation = contract.get("generation") or {}
    if generation.get("cash_cost") != 0 or generation.get("paid_runtime_dependency") is not False:
        raise ValueError("gesture atlas must preserve the zero-cash production contract")
    base_spec = contract.get("base_image") or {}
    base_path = _asset(contract_path, base_spec, "gesture base image")
    width = int(base_spec.get("width", 0))
    height = int(base_spec.get("height", 0))
    if (width, height) != (1672, 941) or base_spec.get("mode") != "RGB":
        raise ValueError("gesture base image must match the 1672x941 RGB hero plate")
    with Image.open(base_path) as image:
        if image.size != (width, height) or image.mode != "RGB":
            raise ValueError("gesture base image dimensions/mode do not match")
    base_origin = contract.get("base_steam_origin") or []
    if len(base_origin) != 2 or not (0 <= int(base_origin[0]) < width and 0 <= int(base_origin[1]) < height):
        raise ValueError("gesture base_steam_origin must stay inside the plate")
    poses = contract.get("poses") or {}
    if set(poses) != {"mug_lift", "pencil_hold"}:
        raise ValueError("gesture atlas must contain the mug_lift and pencil_hold poses")
    paths: dict[str, Any] = {"neutral": base_path}
    for state, pose in poses.items():
        box = pose.get("patch_box") or []
        if len(box) != 4:
            raise ValueError(f"gesture pose {state} patch_box is invalid")
        left, top, right, bottom = (int(value) for value in box)
        if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
            raise ValueError(f"gesture pose {state} patch_box leaves the plate")
        feather = int(pose.get("patch_feather_px", 0))
        if not 8 <= feather <= 64 or right - left <= feather * 3 or bottom - top <= feather * 3:
            raise ValueError(f"gesture pose {state} feather is invalid")
        keyframes = pose.get("keyframes") or []
        if len(keyframes) < 2:
            raise ValueError(f"gesture pose {state} requires registered in-between keyframes")
        amounts = [float(keyframe.get("amount", -1.0)) for keyframe in keyframes]
        if amounts != sorted(set(amounts)) or amounts[0] <= 0.0 or amounts[-1] != 1.0:
            raise ValueError(f"gesture pose {state} keyframe amounts must increase to 1.0")
        pose_paths = []
        for index, keyframe in enumerate(keyframes):
            image_spec = keyframe.get("image") or {}
            image_path = _asset(contract_path, image_spec, f"gesture pose {state} keyframe {index}")
            with Image.open(image_path) as image:
                if image.size != (width, height) or image.mode != "RGB":
                    raise ValueError(f"gesture pose {state} keyframe {index} must match the base plate")
            if state == "mug_lift":
                origin = keyframe.get("steam_origin") or []
                if len(origin) != 2 or not (0 <= int(origin[0]) < width and 0 <= int(origin[1]) < height):
                    raise ValueError("every mug_lift keyframe needs an on-plate steam_origin")
            pose_paths.append(image_path)
        paths[state] = pose_paths
    interpolation = contract.get("interpolation") or {}
    if interpolation.get("engine") not in {"registered_stepped_inbetweens", "opencv_dis_medium"}:
        raise ValueError("gesture interpolation engine is unsupported")
    strength = float(interpolation.get("patch_color_match_strength", -1.0))
    if not 0.0 <= strength <= 1.0:
        raise ValueError("gesture patch color-match strength must be in [0, 1]")
    return contract, paths


def _ease_in_out_cubic(value: float) -> float:
    if value < 0.5:
        return 4.0 * value * value * value
    return 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0


def gesture_performance_plan(
    path: str | Path,
    *,
    expected_atlas_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = Path(path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("contract_version") != GESTURE_CONTRACT_VERSION:
        raise ValueError("gesture cue contract_version does not match")
    if payload.get("character_id") != "june_oxley" or payload.get("atlas_id") != expected_atlas_id:
        raise ValueError("gesture cues target the wrong character or atlas")
    fps = int(payload.get("fps", 0))
    duration = float(payload.get("duration_seconds", 0.0))
    frame_count = int(payload.get("frame_count", 0))
    if fps <= 0 or frame_count != round(duration * fps):
        raise ValueError("gesture cues must declare one exact positive frame clock")
    default_transition = int(payload.get("default_transition_frames", 0))
    if not 2 <= default_transition <= 24:
        raise ValueError("gesture default transition must be between 2 and 24 frames")
    cues = payload.get("cues") or []
    if not cues:
        raise ValueError("gesture cues cannot be empty")
    states = {"neutral", "mug_lift", "pencil_hold"}
    expected_start = 0.0
    for cue in cues:
        start = float(cue.get("start", -1.0))
        end = float(cue.get("end", -1.0))
        state = str(cue.get("state", ""))
        transition = int(cue.get("transition_frames", default_transition))
        if abs(start - expected_start) > 1e-6 or end <= start:
            raise ValueError("gesture cues must be positive contiguous ranges")
        if state not in states:
            raise ValueError(f"unknown gesture state: {state}")
        if not 2 <= transition <= 24 or transition > round((end - start) * fps):
            raise ValueError("gesture transition does not fit its cue")
        expected_start = end
    if abs(expected_start - duration) > 1e-6:
        raise ValueError("gesture cues must cover the complete performance")
    if {str(cue["state"]) for cue in cues} != states:
        raise ValueError("gesture cues must exercise neutral and both production poses")

    targets = []
    cue_indices = []
    cue_index = 0
    for frame_index in range(frame_count):
        sample_time = (frame_index + 0.5) / fps
        while cue_index + 1 < len(cues) and sample_time >= float(cues[cue_index]["end"]):
            cue_index += 1
        targets.append(str(cues[cue_index]["state"]))
        cue_indices.append(cue_index)
    active = targets[0]
    transition_from = active
    transition_start = 0
    plan = []
    for frame_index, target in enumerate(targets):
        if target != active:
            transition_from = active
            active = target
            transition_start = frame_index
        transition_frames = int(cues[cue_indices[frame_index]].get("transition_frames", default_transition))
        transition_offset = frame_index - transition_start
        if transition_from == active or transition_offset >= transition_frames:
            amount = 1.0
            transition_from = active
        else:
            amount = _ease_in_out_cubic((transition_offset + 1) / transition_frames)
        plan.append({
            "frame": frame_index + 1,
            "from_state": transition_from,
            "to_state": active,
            "blend": amount,
        })
    metadata = {
        "path": source,
        "sha256": _sha256(source),
        "performance_id": payload["performance_id"],
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": duration,
        "cue_count": len(cues),
        "states": sorted(states),
    }
    return metadata, plan


def _patch_mask(width: int, height: int, feather: int) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    inset = feather + 2
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset, inset, width - inset - 1, height - inset - 1),
        radius=max(18, min(width, height) // 7),
        fill=255,
    )
    return mask.filter(ImageFilter.GaussianBlur(radius=feather / 2.0))


def _color_match(pose: np.ndarray, base: np.ndarray, mask: np.ndarray, strength: float) -> np.ndarray:
    source = pose.astype(np.float32)
    target = base.astype(np.float32)
    selected = mask >= 80
    adjusted = source.copy()
    for channel in range(3):
        source_values = source[:, :, channel][selected]
        target_values = target[:, :, channel][selected]
        source_mean = float(source_values.mean())
        target_mean = float(target_values.mean())
        source_std = max(1.0, float(source_values.std()))
        target_std = max(1.0, float(target_values.std()))
        corrected = (source[:, :, channel] - source_mean) * (target_std / source_std) + target_mean
        adjusted[:, :, channel] = source[:, :, channel] * (1.0 - strength) + corrected * strength
    return np.clip(adjusted, 0, 255).astype(np.uint8)


def _dis_flow(source: np.ndarray, target: np.ndarray, settings: dict[str, Any]) -> np.ndarray:
    engine = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    engine.setFinestScale(int(settings.get("finest_scale", 1)))
    engine.setGradientDescentIterations(int(settings.get("gradient_descent_iterations", 28)))
    engine.setVariationalRefinementIterations(int(settings.get("variational_refinement_iterations", 5)))
    source_gray = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
    target_gray = cv2.cvtColor(target, cv2.COLOR_RGB2GRAY)
    return engine.calc(source_gray, target_gray, None)


def prepare_gesture_sources(
    atlas_contract_path: str | Path,
    *,
    expected_plate_id: str,
    expected_base_sha256: str,
) -> dict[str, Any]:
    contract, paths = load_gesture_atlas_contract(atlas_contract_path)
    if contract.get("plate_id") != expected_plate_id:
        raise ValueError("gesture atlas targets a different hero plate")
    if contract["base_image"]["sha256"] != expected_base_sha256:
        raise ValueError("gesture atlas base hash does not match the loaded hero plate")
    with Image.open(paths["neutral"]) as image:
        base_image = image.convert("RGB")
    settings = contract["interpolation"]
    engine = str(settings["engine"])
    strength = float(settings["patch_color_match_strength"])
    prepared: dict[str, Any] = {}
    for state, pose in contract["poses"].items():
        box = tuple(int(value) for value in pose["patch_box"])
        width = box[2] - box[0]
        height = box[3] - box[1]
        mask_image = _patch_mask(width, height, int(pose["patch_feather_px"]))
        mask = np.asarray(mask_image, dtype=np.uint8)
        base = np.asarray(base_image.crop(box), dtype=np.uint8)
        nodes = [{
            "amount": 0.0,
            "image": base,
            "steam_origin": contract.get("base_steam_origin"),
        }]
        for keyframe, image_path in zip(pose["keyframes"], paths[state]):
            with Image.open(image_path) as image:
                raw_pose = np.asarray(image.convert("RGB").crop(box), dtype=np.uint8)
            nodes.append({
                "amount": float(keyframe["amount"]),
                "image": _color_match(raw_pose, base, mask, strength),
                "steam_origin": keyframe.get("steam_origin"),
            })
        segments = []
        for source_node, target_node in zip(nodes, nodes[1:]):
            segments.append({
                "start": source_node["amount"],
                "end": target_node["amount"],
                "source": source_node["image"],
                "target": target_node["image"],
                "source_steam_origin": source_node.get("steam_origin"),
                "target_steam_origin": target_node.get("steam_origin"),
                "engine": engine,
                "flow_forward": _dis_flow(source_node["image"], target_node["image"], settings)
                if engine == "opencv_dis_medium" else None,
                "flow_backward": _dis_flow(target_node["image"], source_node["image"], settings)
                if engine == "opencv_dis_medium" else None,
            })
        prepared[state] = {
            "box": box,
            "mask": mask_image,
            "segments": segments,
        }
    return {"contract": contract, "poses": prepared}


def _morph_segment(segment: dict[str, Any], amount: float) -> Image.Image:
    source = segment["source"]
    target = segment["target"]
    if segment["engine"] == "registered_stepped_inbetweens":
        return Image.fromarray(source if amount < 0.5 else target, "RGB")
    if amount <= 0.0:
        return Image.fromarray(source, "RGB")
    if amount >= 1.0:
        return Image.fromarray(target, "RGB")
    height, width = source.shape[:2]
    y_grid, x_grid = np.mgrid[0:height, 0:width].astype(np.float32)
    forward = segment["flow_forward"]
    backward = segment["flow_backward"]
    source_warp = cv2.remap(
        source,
        x_grid - forward[:, :, 0] * amount,
        y_grid - forward[:, :, 1] * amount,
        cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    target_warp = cv2.remap(
        target,
        x_grid - backward[:, :, 0] * (1.0 - amount),
        y_grid - backward[:, :, 1] * (1.0 - amount),
        cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    blended = cv2.addWeighted(source_warp, 1.0 - amount, target_warp, amount, 0.0)
    return Image.fromarray(blended, "RGB")


def _pose_frame(pose: dict[str, Any], amount: float) -> tuple[Image.Image, tuple[float, float] | None]:
    segments = pose["segments"]
    segment = next((item for item in segments if amount <= float(item["end"]) + 1e-9), segments[-1])
    start = float(segment["start"])
    end = float(segment["end"])
    local_amount = 1.0 if end <= start else max(0.0, min(1.0, (amount - start) / (end - start)))
    patch = _morph_segment(segment, local_amount)
    source_origin = segment.get("source_steam_origin")
    target_origin = segment.get("target_steam_origin")
    origin = None
    if target_origin is not None:
        if source_origin is None:
            source_origin = target_origin
        origin = tuple(
            float(source_origin[index]) + (float(target_origin[index]) - float(source_origin[index])) * local_amount
            for index in range(2)
        )
    return patch, origin


def gesture_pose_amount(entry: dict[str, Any]) -> tuple[str | None, float]:
    source = str(entry["from_state"])
    target = str(entry["to_state"])
    amount = float(entry["blend"])
    if source == target == "neutral":
        return None, 0.0
    if source == target:
        return source, 1.0
    if source == "neutral":
        return target, amount
    if target == "neutral":
        return source, 1.0 - amount
    raise ValueError("direct transitions between two non-neutral gestures are forbidden")


def apply_gesture_pose(
    frame: Image.Image,
    prepared: dict[str, Any],
    entry: dict[str, Any],
) -> tuple[str | None, float, tuple[float, float] | None]:
    state, amount = gesture_pose_amount(entry)
    if state is None or amount <= 0.0:
        return state, 0.0, None
    pose = prepared["poses"][state]
    patch, origin = _pose_frame(pose, amount)
    frame.paste(patch, pose["box"][:2], pose["mask"])
    return state, amount, origin
