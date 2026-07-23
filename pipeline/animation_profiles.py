"""Selectable animation contracts for premium and June Oxley animated videos.

The top-level ``animation_profile`` field is independent of ``profile``:
``profile`` selects the recurring character; ``animation_profile`` selects how the
film moves and is art-directed. Unprofiled videos remain unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

ANIMATED_TIER1 = "animated_tier1"
JUNE_TIER1 = "june_oxley_animated_tier1"
JUNE_STANDARD = "june_oxley_animated_standard"
CONTRACT_VERSION = 1

_DATA = Path(__file__).with_name("animation_style_profiles.json")

_ALIASES = {
    "animated": ANIMATED_TIER1,
    "tier_1_animated": ANIMATED_TIER1,
    "tier1_animated": ANIMATED_TIER1,
    "animated_tier1": ANIMATED_TIER1,
    "premium_animated": ANIMATED_TIER1,
    "june_oxley_tier1": JUNE_TIER1,
    "tier1_june_oxley": JUNE_TIER1,
    "june_oxley_animated_tier1": JUNE_TIER1,
    "premium_june_oxley_animated": JUNE_TIER1,
    "june_oxley_animated": JUNE_STANDARD,
    "june_oxley_standard": JUNE_STANDARD,
    "june_oxley_animated_standard": JUNE_STANDARD,
    "regular_june_oxley_animated": JUNE_STANDARD,
}


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def profiles() -> dict[str, dict[str, Any]]:
    payload = json.loads(_DATA.read_text(encoding="utf-8"))
    return payload["profiles"]


def resolve(script: dict | None, strict: bool = False) -> str | None:
    script = script or {}
    raw = next((script.get(k) for k in ("animation_profile", "animation_style", "animated_style")
                if script.get(k)), None)
    if raw is None:
        return None
    found = _ALIASES.get(_key(raw))
    if found is None and strict:
        choices = ", ".join(sorted(profiles()))
        raise ValueError(f"unknown animation_profile {raw!r}; supported: {choices}")
    return found


def contract(name: str | None) -> dict[str, Any] | None:
    if name is None:
        return None
    return dict(profiles()[name])


def display_name(name: str | None) -> str:
    data = contract(name)
    return data["display_name"] if data else "default"


def is_june(name: str | None) -> bool:
    return name in {JUNE_TIER1, JUNE_STANDARD}


def is_tier1(name: str | None) -> bool:
    data = contract(name)
    return bool(data and int(data["quality_tier"]) == 1)


def _append_once(text: str, suffix: str) -> str:
    base = " ".join(str(text or "").split()).strip()
    if not base:
        return suffix
    marker = suffix.split(",", 1)[0].lower()
    if marker and marker in base.lower():
        return base
    return f"{base}, {suffix}"


def _merge_visual_policy(script: dict, data: dict) -> bool:
    changed = False
    raw = script.get("visual_policy")
    policy = dict(raw) if isinstance(raw, dict) else {}
    desired = {
        "mode": "diverse_symbols",
        "max_human_ratio": data["max_human_ratio"],
        "max_family_run": data["max_family_run"],
        "max_generic_human_run": data["max_generic_human_run"],
        "animation_profile": script["animation_profile"],
    }
    for key, value in desired.items():
        if policy.get(key) != value:
            policy[key] = value
            changed = True
    if raw != policy:
        script["visual_policy"] = policy
        changed = True
    return changed


def apply_defaults(script: dict, character_profile: str | None = None, strict: bool = True) -> bool:
    """Apply one idempotent animation contract to a script in memory.

    This does not choose concepts, rewrite narration, or generate media. It makes the
    requested animation mode machine-readable and constrains later acquisition,
    generation, motion accounting, and review.
    """
    name = resolve(script, strict=strict)
    if name is None:
        return False
    data = contract(name)
    assert data is not None
    required_character = data.get("character_profile")
    if required_character:
        existing = character_profile or script.get("profile")
        if existing and _key(existing) not in {_key(required_character), "june_oxley"}:
            raise ValueError(
                f"animation_profile {name!r} requires profile: june_oxley; got {existing!r}"
            )
        script["profile"] = required_character
    elif character_profile == "june_oxley":
        # A regular Tier 1 animation may contain June, but the explicit June modes
        # should be selected when character continuity is intended.
        script.setdefault("animation_profile_note", (
            "June Oxley detected with regular Tier 1 animation; use a June-specific "
            "animation profile when recurring character continuity is required."
        ))

    changed = False
    canonical = name
    desired_top = {
        "animation_profile": canonical,
        "animation_contract_version": CONTRACT_VERSION,
        "animation_quality_tier": data["quality_tier"],
        "animation_display_name": data["display_name"],
        "animation_character_reference_id": data.get("character_reference_id"),
        "animation_source_priority": data["source_priority"],
        "animation_camera_language": data["camera_language"],
        "animation_design_language": data["design_language"],
        "caption_policy": data["caption_policy"],
        "max_still_source_ratio": data["max_still_source_ratio"],
        "minimum_true_motion_ratio": data["minimum_true_motion_ratio"],
    }
    for key, value in desired_top.items():
        if value is None:
            continue
        if script.get(key) != value:
            script[key] = value
            changed = True
    changed = _merge_visual_policy(script, data) or changed

    suffix = data["prompt_suffix"]
    for index, scene in enumerate(script.get("scenes") or []):
        desired_scene = {
            "animation_profile": canonical,
            "animation_quality_tier": data["quality_tier"],
            "animation_source_preference": data["source_priority"],
            "animation_camera_language": data["camera_language"],
            "animation_design_language": data["design_language"],
            "animation_character_reference_id": data.get("character_reference_id"),
            "animation_scene_index": index,
        }
        for key, value in desired_scene.items():
            if value is None:
                continue
            if scene.get(key) != value:
                scene[key] = value
                changed = True
        # Preserve the human-authored literal query while giving every downstream
        # generator and stock search a separate styled query.
        base_query = scene.get("animation_base_query") or scene.get("query") or scene.get("image_prompt") or scene.get("text") or ""
        if scene.get("animation_base_query") != base_query:
            scene["animation_base_query"] = base_query
            changed = True
        styled = _append_once(base_query, suffix)
        if scene.get("animation_query") != styled:
            scene["animation_query"] = styled
            changed = True
        if scene.get("hero") or scene.get("image_prompt"):
            base_prompt = scene.get("animation_base_prompt") or scene.get("image_prompt") or base_query
            if scene.get("animation_base_prompt") != base_prompt:
                scene["animation_base_prompt"] = base_prompt
                changed = True
            styled_prompt = _append_once(base_prompt, suffix)
            if scene.get("image_prompt") != styled_prompt:
                scene["image_prompt"] = styled_prompt
                changed = True
        # Animated profiles favor genuine temporal footage. Existing explicit still
        # and keyframe contracts are respected and counted under the stricter cap.
        if not scene.get("motion_kind") and scene.get("query"):
            scene["motion_kind"] = "video"
            scene.setdefault("motion_mode", "stock")
            changed = True
    return changed


def effective_query(scene: dict, name: str | None) -> str:
    if name is None:
        return str(scene.get("query") or "")
    return str(scene.get("animation_query") or scene.get("query") or "")


def hero_style(name: str | None) -> str:
    data = contract(name)
    return f", {data['prompt_suffix']}" if data else ""


def writer_context(name: str | None) -> str:
    data = contract(name)
    if not data:
        return ""
    return (
        f"ANIMATION PROFILE: {name} ({data['display_name']})\n"
        f"- Design language: {data['design_language']}\n"
        f"- Camera language: {data['camera_language']}\n"
        f"- True-motion floor: {data['minimum_true_motion_ratio']:.0%}; still-derived cap: "
        f"{data['max_still_source_ratio']:.0%}.\n"
        f"- Captions: {data['caption_policy']}.\n"
        "- Use one ruling visual system, one strong symbol per beat, and no cheap template animation.\n"
        f"- Set top-level JSON field exactly to \"animation_profile\": \"{name}\"."
    )


def validate(script: dict, character_profile: str | None = None) -> list[str]:
    name = resolve(script, strict=True)
    if name is None:
        return []
    data = contract(name)
    assert data is not None
    errors: list[str] = []
    if script.get("animation_contract_version") != CONTRACT_VERSION:
        errors.append("animation_contract_version must be 1")
    if float(script.get("max_still_source_ratio", 1.0)) > float(data["max_still_source_ratio"]) + 1e-9:
        errors.append(
            f"{name} still-derived cap must be <= {data['max_still_source_ratio']:.0%}"
        )
    if is_june(name):
        resolved_character = character_profile or script.get("profile")
        if _key(resolved_character or "") != "june_oxley":
            errors.append(f"{name} requires profile: june_oxley")
        if script.get("animation_character_reference_id") != "june_oxley_v1":
            errors.append("June animation must lock animation_character_reference_id: june_oxley_v1")
    for index, scene in enumerate(script.get("scenes") or []):
        if scene.get("animation_profile") != name:
            errors.append(f"scene {index} missing canonical animation_profile")
        if not scene.get("animation_query"):
            errors.append(f"scene {index} missing animation_query")
    return errors
