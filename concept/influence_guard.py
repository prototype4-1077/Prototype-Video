"""Concept Engine influence guard.

Converts James's influence ethic into an explainable PASS / REVIEW / BLOCK check.
It reviews concept metadata and, when given a build script, every spoken scene.
The guard is a conservative aid; James's judgment remains final.

Usage:
    python3 concept/influence_guard.py candidate.json
    python3 concept/influence_guard.py --text script.txt
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
VALID_FIDELITY = {"established", "emerging", "metaphor", "mixed"}
HIGH_CARE_TERMS = {
    "derealization", "dissociation", "psychosis", "trauma", "grief",
    "recovery", "medical", "medicine", "symptom", "minors", "teen",
}

TEXT_PATTERNS = {
    "verdict_installation": (
        "block",
        "The language installs a conclusion instead of handing over a test.",
        [
            r"\bthe truth is\b", r"\bthis proves(?: that)?\b",
            r"\bthere is no other explanation\b", r"\byou must believe\b",
            r"\bnow you know(?: the truth)?\b",
            r"\bthis is how reality (?:really )?works\b",
        ],
    ),
    "dependency": (
        "block",
        "The language creates authority dependence.",
        [
            r"\bonly (?:i|we|this channel) (?:can|understand|know)\b",
            r"\byou need (?:me|us|this channel)\b",
            r"\bkeep following (?:me|us) to (?:learn|know|wake up)\b",
            r"\bwithout (?:me|us|this channel),? you\b",
        ],
    ),
    "fear_leverage": (
        "review",
        "Fear or destabilization may be doing the persuasive work.",
        [
            r"\bthey don'?t want you to know\b", r"\byou are trapped\b",
            r"\bnothing is real\b", r"\byour reality is fake\b",
            r"\bwake up before it'?s too late\b", r"\bthe world is lying to you\b",
        ],
    ),
    "manufactured_urgency": (
        "review",
        "The copy may be using urgency rather than relevance.",
        [
            r"\bright now before\b", r"\btime is running out\b",
            r"\bdo this immediately\b", r"\byou cannot afford to ignore\b",
        ],
    ),
    "medical_overclaim": (
        "block",
        "The copy crosses the non-clinical boundary.",
        [
            r"\bbelief (?:cures|heals) (?:disease|cancer|illness)\b",
            r"\byou can heal yourself with (?:thought|belief|mindset)\b",
            r"\bstop taking (?:your )?(?:medicine|medication)\b",
        ],
    ),
    "identity_pressure": (
        "review",
        "The language pressures identity rather than inviting examination.",
        [
            r"\bif you were truly awake\b", r"\bpeople like us\b",
            r"\bonly asleep people\b", r"\byou are the kind of person who\b",
        ],
    ),
}


def _load_json(name: str, default: Any) -> Any:
    try:
        with open(os.path.join(HERE, name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default


def _issue(code: str, severity: str, message: str, evidence: Optional[str] = None) -> Dict[str, str]:
    item = {"code": code, "severity": severity, "message": message}
    if evidence:
        item["evidence"] = evidence[:180]
    return item


def _metadata_text(candidate: Dict[str, Any]) -> str:
    fields = (
        "title", "hook", "science", "metaphor", "turn", "invitation",
        "desired_movement", "grounding", "evidence_boundary", "why_now",
    )
    chunks = [str(candidate[field]) for field in fields if isinstance(candidate.get(field), str)]
    for field in ("risks", "risk_mitigations", "audience_states", "human_situations"):
        value = candidate.get(field)
        if isinstance(value, list):
            chunks.extend(str(item) for item in value)
    return "\n".join(chunks)


def scan_text(text: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for code, (severity, message, patterns) in TEXT_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                issues.append(_issue(code, severity, message, match.group(0)))
                break
    return issues


def _script_data(candidate: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]], Dict[str, Any]]:
    scenes = candidate.get("scenes")
    if not isinstance(scenes, list):
        return "", [], {}

    spoken = []
    issues: List[Dict[str, str]] = []
    human_scenes = 0
    evidence_scenes = 0
    max_scene_words = 0

    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            issues.append(_issue("invalid_scene", "block", f"Scene {index + 1} is not an object."))
            continue
        text = str(scene.get("text") or "").strip()
        spoken.append(text)
        words = len(re.findall(r"\b[\w’'-]+\b", text))
        max_scene_words = max(max_scene_words, words)
        if words > 25:
            issues.append(_issue(
                "scene_too_dense", "review",
                f"Scene {index + 1} has {words} words; short scenes are easier to hear and render."
            ))
        if scene.get("human_role"):
            human_scenes += 1
        if scene.get("epistemic_role") == "evidence":
            evidence_scenes += 1
            if not scene.get("source_ids"):
                issues.append(_issue(
                    "uncited_evidence_scene", "block",
                    f"Evidence scene {index + 1} has no source_ids."
                ))

    total_words = len(re.findall(r"\b[\w’'-]+\b", " ".join(spoken)))
    scene_count = len(scenes)
    human_ratio = round(human_scenes / scene_count, 3) if scene_count else 0.0
    if scene_count and human_ratio > 0.5:
        issues.append(_issue(
            "human_visual_ratio", "review",
            f"Human-coded scenes are {human_ratio:.0%}; target is under half."
        ))
    if scene_count and not any(
        isinstance(scene, dict) and scene.get("visual_function") == "grounding"
        for scene in scenes[-5:]
    ):
        issues.append(_issue(
            "grounding_not_embodied", "block",
            "The final five scenes do not contain a rendered grounding beat."
        ))
    final_text = spoken[-1] if spoken else ""
    if final_text and "?" not in final_text:
        issues.append(_issue(
            "final_line_not_open", "block",
            "The final spoken scene is not an open question."
        ))

    metrics = {
        "scene_count": scene_count,
        "word_count": total_words,
        "estimated_duration_seconds": round(
            total_words / max(float(candidate.get("estimated_words_per_second") or 2.1), 0.1), 1
        ),
        "human_scene_ratio": human_ratio,
        "evidence_scene_count": evidence_scenes,
        "max_scene_words": max_scene_words,
    }
    return "\n".join(spoken), issues, metrics


def assess(candidate: Dict[str, Any], text: str = "") -> Dict[str, Any]:
    constitution = _load_json("constitution.json", {})
    issues: List[Dict[str, str]] = []

    fidelity = candidate.get("fidelity") or candidate.get("science_fidelity")
    if fidelity not in VALID_FIDELITY:
        issues.append(_issue(
            "science_fidelity_missing", "block",
            "The governing claim needs an established, emerging, metaphor or mixed label."
        ))

    invitation = str(candidate.get("invitation") or "").strip()
    if not invitation:
        issues.append(_issue("invitation_missing", "block", "No viewer-owned question or test is present."))
    elif "?" not in invitation:
        issues.append(_issue("invitation_not_open", "block", "The invitation is not phrased as an open question."))

    if not str(candidate.get("grounding") or "").strip():
        issues.append(_issue(
            "grounding_missing", "block",
            "No return to the room, body, breath or ordinary object is specified."
        ))
    if not str(candidate.get("evidence_boundary") or "").strip():
        issues.append(_issue(
            "evidence_boundary_missing", "block",
            "The candidate does not state where the evidence stops."
        ))
    if not str(candidate.get("desired_movement") or "").strip():
        issues.append(_issue(
            "desired_movement_missing", "review",
            "The piece does not state what capacity it should strengthen."
        ))

    optimization_target = candidate.get("optimization_target", "belief_analysis")
    prohibited = set(constitution.get("prohibited_optimization_targets", []))
    if optimization_target in prohibited:
        issues.append(_issue(
            "prohibited_optimization_target", "block",
            f"Optimization target '{optimization_target}' conflicts with the constitution."
        ))

    scene_text, scene_issues, script_metrics = _script_data(candidate)
    issues.extend(scene_issues)
    all_text = "\n".join(part for part in (_metadata_text(candidate), scene_text, text) if part)
    issues.extend(scan_text(all_text))

    lower_text = all_text.lower()
    care_context = {str(item).lower() for item in candidate.get("risks", [])}
    if care_context.intersection(HIGH_CARE_TERMS) or any(term in lower_text for term in HIGH_CARE_TERMS):
        if not candidate.get("risk_mitigations"):
            issues.append(_issue(
                "high_care_without_mitigation", "review",
                "A high-care topic needs explicit boundaries and grounding mitigations."
            ))

    deduped: List[Dict[str, str]] = []
    seen = set()
    for item in issues:
        key = (item["code"], item.get("evidence", ""), item["message"])
        if key not in seen:
            deduped.append(item)
            seen.add(key)
    issues = deduped

    severities = {item["severity"] for item in issues}
    decision = "BLOCK" if "block" in severities else "REVIEW" if "review" in severities else "PASS"
    autonomy_score = max(
        0,
        100
        - 35 * sum(item["severity"] == "block" for item in issues)
        - 12 * sum(item["severity"] == "review" for item in issues),
    )
    return {
        "decision": decision,
        "autonomy_score": autonomy_score,
        "optimization_target": optimization_target,
        "issues": issues,
        "script_metrics": script_metrics,
        "note": "Explainable heuristic review; human judgment remains final.",
    }


def assess_file(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        if path.lower().endswith(".json"):
            candidate = json.load(handle)
            if "selected" in candidate and isinstance(candidate["selected"], dict):
                candidate = candidate["selected"]
            if not isinstance(candidate, dict):
                raise ValueError("JSON review target must be an object")
            return assess(candidate)
        text = handle.read()
    return assess({
        "fidelity": "mixed",
        "invitation": "What do you notice?",
        "grounding": "Return to the room and body.",
        "evidence_boundary": "Text-only scan; metadata was not supplied.",
        "desired_movement": "From automatic acceptance to examination.",
    }, text=text)


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: influence_guard.py candidate.json | --text script.txt", file=sys.stderr)
        return 2
    if argv[0] == "--text":
        if len(argv) < 2:
            print("--text requires a path", file=sys.stderr)
            return 2
        result = assess_file(argv[1])
    else:
        result = assess_file(argv[0])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result["decision"] == "BLOCK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
