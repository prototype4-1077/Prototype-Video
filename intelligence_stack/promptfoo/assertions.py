"""Objective Promptfoo assertions for production promotion."""
from __future__ import annotations

import json
import re
from typing import Any

WORD_RE = re.compile(r"\b[\w’'-]+\b", re.UNICODE)
FIDELITY = {"established", "emerging", "metaphor", "mixed"}
DANGEROUS_VISUAL_COMBINATIONS = (
    "two hands touching",
    "hand gripping",
    "hand holding",
    "fingers merging",
    "body dissolving",
    "reflection of a person",
    "mirror reflection",
    "surgical hand",
)


def _result(checks: list[tuple[str, bool, str]]) -> dict[str, Any]:
    passed = all(item[1] for item in checks)
    score = sum(item[1] for item in checks) / max(len(checks), 1)
    failed = [f"{name}: {reason}" for name, ok, reason in checks if not ok]
    return {
        "pass": passed,
        "score": round(score, 4),
        "reason": "all competency checks passed" if passed else "; ".join(failed),
        "namedScores": {name: 1.0 if ok else 0.0 for name, ok, _ in checks},
        "componentResults": [
            {"pass": ok, "score": 1.0 if ok else 0.0, "reason": f"{name}: {reason}"}
            for name, ok, reason in checks
        ],
    }


def _parse(output: str) -> tuple[Any | None, str | None]:
    try:
        return json.loads(output), None
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"


def _validate_script(payload: dict[str, Any]) -> dict[str, Any]:
    scenes = payload.get("scenes") or []
    texts = [str(scene.get("text") or "") for scene in scenes if isinstance(scene, dict)]
    word_counts = [len(WORD_RE.findall(text)) for text in texts]
    total_words = sum(word_counts)
    human_count = sum(bool(scene.get("human_heavy")) for scene in scenes if isinstance(scene, dict))
    human_ratio = human_count / max(len(scenes), 1)
    final_text = texts[-1].strip() if texts else ""
    late = scenes[-5:] if scenes else []
    grounding = any(
        scene.get("visual_function") == "grounding"
        or any(term in str(scene.get("text") or "").lower() for term in ("chair", "feet", "breath", "room", "cup"))
        for scene in late if isinstance(scene, dict)
    )
    metaphor = str(payload.get("ruling_metaphor") or "").strip()
    metaphor_mentions = sum(metaphor.lower().split()[0] in text.lower() for text in texts) if metaphor else 0

    visual_blob = " ".join(
        str(scene.get("image_prompt") or scene.get("query") or "").lower()
        for scene in scenes if isinstance(scene, dict)
    )
    risky = [phrase for phrase in DANGEROUS_VISUAL_COMBINATIONS if phrase in visual_blob]

    checks = [
        ("scene_count", 18 <= len(scenes) <= 26, f"expected 18–26, got {len(scenes)}"),
        ("word_budget", 300 <= total_words <= 400, f"expected 300–400, got {total_words}"),
        ("short_scenes", bool(word_counts) and max(word_counts) <= 25, f"maximum scene words is {max(word_counts or [0])}"),
        ("fidelity", payload.get("science_fidelity") in FIDELITY, "missing valid science fidelity"),
        ("evidence_boundary", bool(str(payload.get("evidence_boundary") or "").strip()), "missing evidence boundary"),
        ("ruling_metaphor", bool(metaphor) and metaphor_mentions >= 3, "metaphor is absent or not held through the script"),
        ("human_ratio", human_ratio < 0.5, f"human-heavy ratio is {human_ratio:.1%}"),
        ("grounding", grounding, "no rendered grounding beat in final five scenes"),
        ("invitation", final_text.endswith("?") and payload.get("invitation") in {None, final_text}, "final line is not an open invitation"),
        ("visual_safety", not risky, f"unsafe visual combinations: {', '.join(risky)}"),
    ]
    return _result(checks)


def _validate_visual(payload: dict[str, Any]) -> dict[str, Any]:
    constraints = [str(item).lower() for item in payload.get("constraints") or []]
    prompt = str(payload.get("prompt") or "").lower()
    route = payload.get("route")
    checks = [
        ("route", route in {"stock", "comfyui", "nonhuman_geometry"}, f"unsupported route {route!r}"),
        ("one_subject", int(payload.get("subject_count", 0)) == 1, "subject_count must equal one"),
        ("one_action", int(payload.get("action_count", 0)) <= 1, "action_count must be at most one"),
        ("one_anomaly", int(payload.get("impossible_element_count", 0)) <= 1, "only one impossible element is allowed"),
        ("negative_constraints", len(constraints) >= 4, "at least four explicit constraints required"),
        ("no_complex_anatomy", not any(term in prompt for term in DANGEROUS_VISUAL_COMBINATIONS), "prompt contains high-risk anatomy/contact language"),
        ("deterministic", isinstance(payload.get("seed"), int), "deterministic seed required"),
    ]
    return _result(checks)


def _validate_revision(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    expected = str((context.get("vars") or {}).get("original_narration") or "")
    checks = [
        ("verbatim_narration", payload.get("narration") == expected, "revision changed supplied narration"),
        ("approved_untouched", payload.get("approved_scenes_untouched") is True, "approved scenes were not explicitly protected"),
        ("revision_scope", payload.get("revision_scope") == "visual_only", "revision scope must be visual_only"),
        ("safe_route", payload.get("route") in {"stock", "comfyui", "nonhuman_geometry"}, "revision lacks a safe route"),
    ]
    return _result(checks)


def validate(output: str, context) -> dict[str, Any]:
    payload, error = _parse(output)
    if error or not isinstance(payload, dict):
        return {"pass": False, "score": 0, "reason": error or "output must be a JSON object"}
    task_type = str((context.get("vars") or {}).get("task_type") or "")
    if task_type == "script":
        return _validate_script(payload)
    if task_type == "visual_plan":
        return _validate_visual(payload)
    if task_type == "revision":
        return _validate_revision(payload, context)
    return {"pass": False, "score": 0, "reason": f"unknown task_type {task_type!r}"}
