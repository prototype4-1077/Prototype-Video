"""Concept Engine influence guard.

The guard converts James's influence ethic into an executable review:
help a viewer examine experience without installing a verdict, manufacturing
fear, or creating dependence. It is intentionally conservative and explainable.

Usage:
    python3 concept/influence_guard.py candidate.json
    python3 concept/influence_guard.py --text script.txt
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))

VALID_FIDELITY = {"established", "emerging", "metaphor", "mixed"}

TEXT_PATTERNS = {
    "verdict_installation": {
        "severity": "block",
        "patterns": [
            r"\bthe truth is\b",
            r"\bthis proves(?: that)?\b",
            r"\bthere is no other explanation\b",
            r"\byou must believe\b",
            r"\bnow you know(?: the truth)?\b",
            r"\bthis is how reality (?:really )?works\b",
        ],
        "message": "The language installs a conclusion instead of handing over a test.",
    },
    "dependency": {
        "severity": "block",
        "patterns": [
            r"\bonly (?:i|we|this channel) (?:can|understand|know)\b",
            r"\byou need (?:me|us|this channel)\b",
            r"\bkeep following (?:me|us) to (?:learn|know|wake up)\b",
            r"\bwithout (?:me|us|this channel),? you\b",
        ],
        "message": "The language creates authority dependence.",
    },
    "fear_leverage": {
        "severity": "review",
        "patterns": [
            r"\bthey don'?t want you to know\b",
            r"\byou are trapped\b",
            r"\bnothing is real\b",
            r"\byour reality is fake\b",
            r"\bwake up before it'?s too late\b",
            r"\bthe world is lying to you\b",
        ],
        "message": "Fear or destabilization may be doing the persuasive work.",
    },
    "manufactured_urgency": {
        "severity": "review",
        "patterns": [
            r"\bright now before\b",
            r"\btime is running out\b",
            r"\bdo this immediately\b",
            r"\byou cannot afford to ignore\b",
        ],
        "message": "The copy may be using urgency rather than relevance.",
    },
    "medical_overclaim": {
        "severity": "block",
        "patterns": [
            r"\bbelief (?:cures|heals) (?:disease|cancer|illness)\b",
            r"\byou can heal yourself with (?:thought|belief|mindset)\b",
            r"\bstop taking (?:your )?(?:medicine|medication)\b",
        ],
        "message": "The copy crosses the non-clinical boundary.",
    },
    "identity_pressure": {
        "severity": "review",
        "patterns": [
            r"\bif you were truly awake\b",
            r"\bpeople like us\b",
            r"\bonly asleep people\b",
            r"\byou are the kind of person who\b",
        ],
        "message": "The language pressures identity rather than inviting examination.",
    },
}

HIGH_CARE_TERMS = {
    "derealization", "dissociation", "psychosis", "trauma", "grief",
    "recovery", "medical", "medicine", "symptom", "minors", "teen"
}


def _load_json(name: str, default: Any) -> Any:
    path = os.path.join(HERE, name)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _issue(code: str, severity: str, message: str, evidence: Optional[str] = None) -> Dict[str, str]:
    item = {"code": code, "severity": severity, "message": message}
    if evidence:
        item["evidence"] = evidence[:180]
    return item


def _as_text(candidate: Dict[str, Any]) -> str:
    fields = (
        "title", "hook", "science", "metaphor", "turn", "invitation",
        "desired_movement", "grounding", "evidence_boundary", "why_now",
    )
    chunks: List[str] = []
    for field in fields:
        value = candidate.get(field)
        if isinstance(value, str):
            chunks.append(value)
    for field in ("risks", "risk_mitigations", "audience_states", "human_situations"):
        value = candidate.get(field)
        if isinstance(value, list):
            chunks.extend(str(v) for v in value)
    return "\n".join(chunks)


def scan_text(text: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for code, spec in TEXT_PATTERNS.items():
        for pattern in spec["patterns"]:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                issues.append(_issue(code, spec["severity"], spec["message"], match.group(0)))
                break
    return issues


def assess(candidate: Dict[str, Any], text: str = "") -> Dict[str, Any]:
    """Assess one concept, decision brief or script metadata object.

    This is a review aid, not a moral oracle. PASS means no configured issue was
    detected; it does not replace James's judgment.
    """
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
        issues.append(_issue(
            "invitation_not_open", "block",
            "The invitation is not phrased as an open question."
        ))

    grounding = str(candidate.get("grounding") or "").strip()
    if not grounding:
        issues.append(_issue(
            "grounding_missing", "block",
            "No return to the room, body, breath or ordinary object is specified."
        ))

    boundary = str(candidate.get("evidence_boundary") or "").strip()
    if not boundary:
        issues.append(_issue(
            "evidence_boundary_missing", "block",
            "The candidate does not state where the evidence stops."
        ))

    desired = str(candidate.get("desired_movement") or "").strip()
    if not desired:
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

    all_text = "\n".join(part for part in (_as_text(candidate), text) if part)
    issues.extend(scan_text(all_text))

    care_context = set(str(x).lower() for x in candidate.get("risks", []))
    lower_text = all_text.lower()
    if care_context.intersection(HIGH_CARE_TERMS) or any(term in lower_text for term in HIGH_CARE_TERMS):
        mitigations = candidate.get("risk_mitigations") or []
        if not mitigations:
            issues.append(_issue(
                "high_care_without_mitigation", "review",
                "A high-care topic needs explicit boundaries and grounding mitigations."
            ))

    # Avoid duplicate codes from metadata + script text.
    deduped: List[Dict[str, str]] = []
    seen = set()
    for item in issues:
        key = (item["code"], item.get("evidence", ""))
        if key not in seen:
            deduped.append(item)
            seen.add(key)
    issues = deduped

    severities = {item["severity"] for item in issues}
    if "block" in severities:
        decision = "BLOCK"
    elif "review" in severities:
        decision = "REVIEW"
    else:
        decision = "PASS"

    autonomy_score = max(
        0,
        100
        - 35 * sum(i["severity"] == "block" for i in issues)
        - 12 * sum(i["severity"] == "review" for i in issues),
    )

    return {
        "decision": decision,
        "autonomy_score": autonomy_score,
        "optimization_target": optimization_target,
        "issues": issues,
        "note": "Explainable heuristic review; human judgment remains final."
    }


def assess_file(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        if path.lower().endswith(".json"):
            candidate = json.load(f)
            if "selected" in candidate and isinstance(candidate["selected"], dict):
                candidate = candidate["selected"]
            return assess(candidate)
        text = f.read()
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
