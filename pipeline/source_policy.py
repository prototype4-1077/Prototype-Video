"""Shared, dependency-free source policy used before and after rendering."""
from __future__ import annotations

import math

MAX_STILL_SOURCE_RATIO = 0.35


def still_source_cap(script: dict) -> float:
    """A package may tighten the house limit, never raise it."""
    raw = script.get("max_still_source_ratio", script.get("max_static_ratio"))
    if raw is None:
        return MAX_STILL_SOURCE_RATIO
    try:
        cap = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("still-source cap must be a finite ratio between 0 and 1") from exc
    if isinstance(raw, bool) or not math.isfinite(cap) or not 0 <= cap <= 1:
        raise ValueError("still-source cap must be a finite ratio between 0 and 1")
    return min(cap, MAX_STILL_SOURCE_RATIO)


def still_derived(scene: dict) -> bool:
    """Source provenance outranks an author-supplied 'video' label."""
    mode = str(scene.get("motion_mode") or "").lower()
    source = str(scene.get("motion_source") or "").lower()
    return bool(
        source == "blender_3d_storyboard"
        or scene.get("graphic_render_strategy") == "keyframe_composite"
        or scene.get("keyframes")
        or scene.get("source_image")
        or scene.get("still")
        or scene.get("hero_generated")
        or mode in {"static", "still", "pan", "zoom", "ken_burns", "depth",
                    "parallax", "cinemagraph", "keyframes", "flow", "portrait",
                    "animated", "animated_still"}
        or scene.get("motion_kind") in {"static", "still", "animated_still", "cinemagraph"}
    )
