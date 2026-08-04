"""Dependency-free planning and validation for literal graphic compositions."""
from __future__ import annotations


GRAPHIC_KINDS = (
    "labels", "path", "counters", "clock", "perception", "evidence",
    "filter", "scale", "generic",
)


def graphic_kind(scene: dict) -> str:
    explicit = str(scene.get("graphic_kind") or "").strip().lower().replace("-", "_")
    if explicit:
        if explicit not in GRAPHIC_KINDS:
            raise ValueError(
                f"unknown graphic_kind {explicit!r}; expected one of: "
                + ", ".join(GRAPHIC_KINDS)
            )
        return explicit
    blob = " ".join(
        str(value or "").lower()
        for value in (
            scene.get("query"),
            scene.get("semantic_anchor"),
            " ".join(map(str, scene.get("keywords") or [])),
        )
    )
    if "filter" in blob or "setting" in blob or "toggle" in blob:
        return "filter"
    if "scale" in blob or ("deception" in blob and "inherit" in blob):
        return "scale"
    if any(word in blob for word in (
        "receipt", "evidence", "exhibit", "belief lens", "love note", "selfish",
    )):
        return "evidence"
    if any(word in blob for word in (
        "autofocus", "preset", "recognize", "viewfinder", "symbol recognition",
    )):
        return "perception"
    if any(word in blob for word in ("exhaustion", "ambition", "fear", "realistic")):
        return "clock"
    if any(word in blob for word in ("money", "popularity", "value", "worth", "counter")):
        return "counters"
    if any(word in blob for word in ("maze", "route", "path", "walk past", "guide")):
        return "path"
    if any(word in blob for word in (
        "label", "name tag", "stamp", "success", "failure", "normal", "impossible",
    )):
        return "labels"
    return "generic"


def diversity(script: dict) -> dict:
    scenes = [
        (index, scene)
        for index, scene in enumerate(script.get("scenes") or [])
        if str(scene.get("narrative_mode") or "").lower() in {
            "storyboard", "literal_graphic",
        }
    ]
    policy = script.get("graphic_policy") or {}
    active = str(script.get("visual_style") or "").lower() in {
        "literal_motion_graphics", "motion_graphics", "reality_motion_graphics",
    }
    kinds, missing, invalid = [], [], []
    for index, scene in scenes:
        if active and policy.get("require_explicit", True) and not scene.get("graphic_kind"):
            missing.append(index)
        try:
            kinds.append(graphic_kind(scene))
        except ValueError:
            invalid.append(index)
    counts = {kind: kinds.count(kind) for kind in GRAPHIC_KINDS if kind in kinds}
    longest_kind, longest_length, current_kind, current_length = None, 0, None, 0
    for kind in kinds:
        if kind == current_kind:
            current_length += 1
        else:
            current_kind, current_length = kind, 1
        if current_length > longest_length:
            longest_kind, longest_length = kind, current_length
    violations = []
    if active and scenes:
        minimum = min(int(policy.get("min_kinds", 8)), len(scenes))
        maximum = int(policy.get("max_kind_count", 2))
        max_run = int(policy.get("max_kind_run", 1))
        if missing:
            violations.append(
                "literal motion graphics require explicit graphic_kind on scenes: "
                + ", ".join(str(index) for index in missing)
            )
        if invalid:
            violations.append(
                "invalid graphic_kind on scenes: "
                + ", ".join(str(index) for index in invalid)
            )
        if len(counts) < minimum:
            violations.append(
                f"only {len(counts)} graphic compositions across {len(scenes)} storyboard scenes; "
                f"use at least {minimum}"
            )
        overused = [f"{kind}={count}" for kind, count in counts.items() if count > maximum]
        if overused:
            violations.append(
                f"graphic compositions exceed max {maximum}: " + ", ".join(overused)
            )
        if longest_length > max_run:
            violations.append(
                f"graphic composition {longest_kind!r} repeats {longest_length} times consecutively; "
                f"max is {max_run}"
            )
    return {
        "applicable": active,
        "scene_count": len(scenes),
        "kind_count": len(counts),
        "counts": counts,
        "longest_run": {"kind": longest_kind, "length": longest_length},
        "missing_explicit_scene_indexes": missing,
        "invalid_scene_indexes": invalid,
        "passed": not violations,
        "violations": violations,
    }
