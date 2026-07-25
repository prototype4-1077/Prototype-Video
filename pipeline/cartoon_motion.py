"""Phase 1 motion planning for the local Blender cartoon renderer.

The module is intentionally Blender-independent so scripts can be validated in CI
without Blender installed. Existing scenes remain unchanged unless they opt into a
``motion_plan`` or request the ``blender_2_5d`` backend.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

MOTION_CONTRACT_VERSION = 1
BLENDER_BACKEND = "blender_2_5d"

STRATEGIES = {
    "rigged_character",
    "portrait_performance",
    "procedural_object",
    "layered_parallax",
    "keyframe_inbetween",
    "full_generated_video",
}
CAMERA_MOVES = {"locked", "push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down", "orbit"}

DEFAULT_CAMERA = {
    "move": "locked",
    "intensity": 0.0,
    "start": [0.0, -12.0, 1.5],
    "end": [0.0, -12.0, 1.5],
    "lens_mm": 50.0,
}
DEFAULT_LIGHTING = {
    "key_energy": 800.0,
    "fill_energy": 300.0,
    "rim_energy": 500.0,
    "world_strength": 0.35,
}
DEFAULT_ATMOSPHERE = {
    "dust": False,
    "fog": False,
    "steam": False,
    "wind": 0.0,
}


def _as_list(value: Any) -> list:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def default_motion_plan(scene: dict, index: int = 0) -> dict:
    """Return a conservative, deterministic motion plan for one scene."""
    character = bool(scene.get("animation_character_required"))
    strategy = "rigged_character" if character else "layered_parallax"
    primary = scene.get("primary_action") or ("subtle idle performance" if character else "slow environmental drift")
    return {
        "version": MOTION_CONTRACT_VERSION,
        "backend": BLENDER_BACKEND,
        "strategy": strategy,
        "scene_index": index,
        "duration_seconds": float(scene.get("duration") or scene.get("duration_seconds") or 5.0),
        "primary_action": primary,
        "action_phases": {
            "anticipation": "brief readable preparation",
            "action": primary,
            "settle": "small follow-through and return to rest",
        },
        "camera": deepcopy(DEFAULT_CAMERA),
        "lighting": deepcopy(DEFAULT_LIGHTING),
        "atmosphere": deepcopy(DEFAULT_ATMOSPHERE),
        "secondary_motion": [],
        "locked_elements": _as_list(scene.get("locked_elements")),
        "render": {
            "width": 1080,
            "height": 1920,
            "fps": 24,
            "engine": "BLENDER_EEVEE_NEXT",
            "transparent": False,
        },
    }


def normalize_motion_plan(scene: dict, index: int = 0) -> dict:
    """Merge a partial scene motion plan with safe Phase 1 defaults."""
    plan = default_motion_plan(scene, index)
    supplied = scene.get("motion_plan") or {}
    if not isinstance(supplied, dict):
        raise ValueError(f"scene {index} motion_plan must be an object")

    for key, value in supplied.items():
        if key in {"camera", "lighting", "atmosphere", "render", "action_phases"} and isinstance(value, dict):
            plan[key].update(value)
        else:
            plan[key] = deepcopy(value)
    plan["scene_index"] = index
    return plan


def apply_motion_defaults(script: dict) -> bool:
    """Populate plans only for explicitly opted-in scenes.

    Opt-in occurs when the top-level ``cartoon_motion_backend`` is ``blender_2_5d``,
    a scene sets ``motion_backend`` to that value, or a scene already has a
    ``motion_plan``. This protects all existing pipeline behavior.
    """
    changed = False
    top_backend = script.get("cartoon_motion_backend")
    for index, scene in enumerate(script.get("scenes") or []):
        opted_in = (
            top_backend == BLENDER_BACKEND
            or scene.get("motion_backend") == BLENDER_BACKEND
            or isinstance(scene.get("motion_plan"), dict)
        )
        if not opted_in:
            continue
        normalized = normalize_motion_plan(scene, index)
        if scene.get("motion_plan") != normalized:
            scene["motion_plan"] = normalized
            changed = True
        if scene.get("motion_backend") != BLENDER_BACKEND:
            scene["motion_backend"] = BLENDER_BACKEND
            changed = True
    if changed and script.get("cartoon_motion_contract_version") != MOTION_CONTRACT_VERSION:
        script["cartoon_motion_contract_version"] = MOTION_CONTRACT_VERSION
    return changed


def validate_motion_plan(plan: dict, scene_index: int = 0) -> list[str]:
    errors: list[str] = []
    if plan.get("version") != MOTION_CONTRACT_VERSION:
        errors.append(f"scene {scene_index} motion plan version must be {MOTION_CONTRACT_VERSION}")
    if plan.get("backend") != BLENDER_BACKEND:
        errors.append(f"scene {scene_index} motion backend must be {BLENDER_BACKEND}")
    if plan.get("strategy") not in STRATEGIES:
        errors.append(f"scene {scene_index} unknown motion strategy: {plan.get('strategy')!r}")
    try:
        duration = float(plan.get("duration_seconds", 0))
        if duration <= 0:
            errors.append(f"scene {scene_index} duration_seconds must be positive")
    except (TypeError, ValueError):
        errors.append(f"scene {scene_index} duration_seconds must be numeric")

    camera = plan.get("camera") or {}
    if camera.get("move") not in CAMERA_MOVES:
        errors.append(f"scene {scene_index} unknown camera move: {camera.get('move')!r}")
    try:
        intensity = float(camera.get("intensity", 0))
        if not 0.0 <= intensity <= 1.0:
            errors.append(f"scene {scene_index} camera intensity must be between 0 and 1")
    except (TypeError, ValueError):
        errors.append(f"scene {scene_index} camera intensity must be numeric")

    render = plan.get("render") or {}
    for field in ("width", "height", "fps"):
        try:
            if int(render.get(field, 0)) <= 0:
                errors.append(f"scene {scene_index} render.{field} must be positive")
        except (TypeError, ValueError):
            errors.append(f"scene {scene_index} render.{field} must be an integer")
    return errors


def validate_script_motion(script: dict) -> list[str]:
    errors: list[str] = []
    for index, scene in enumerate(script.get("scenes") or []):
        plan = scene.get("motion_plan")
        if plan is not None:
            if not isinstance(plan, dict):
                errors.append(f"scene {index} motion_plan must be an object")
            else:
                errors.extend(validate_motion_plan(plan, index))
    return errors
