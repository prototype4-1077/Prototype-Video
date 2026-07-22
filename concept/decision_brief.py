"""Build the pre-script editorial decision brief.

The brief explains why a concept belongs next, what capacity it should strengthen,
how the science is bounded, how it lands safely, and how the idea can become
something helpful beyond a video.

Usage:
    python3 concept/decision_brief.py
    python3 concept/decision_brief.py --concept constructed_emotion
    python3 concept/decision_brief.py --json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name: str, default: Any = None) -> Any:
    try:
        with open(os.path.join(HERE, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _state_details(ids: List[str]) -> List[Dict[str, str]]:
    states = (load("audience_states.json", {}) or {}).get("states", {})
    out = []
    for state_id in ids:
        item = states.get(state_id, {})
        if item:
            out.append({
                "id": state_id,
                "label": item.get("label", state_id),
                "movement": item.get("movement", ""),
                "safe_landing": item.get("safe_landing", ""),
            })
    return out


def _transformation_ladder(formats: List[str]) -> List[Dict[str, str]]:
    items = (load("transformations.json", {}) or {}).get("ladder", [])
    by_container = {item.get("container"): item for item in items}
    return [
        by_container[container]
        for container in formats
        if container in by_container
    ]


def _science_ledger(item: Dict[str, Any]) -> Dict[str, Any]:
    fidelity = item.get("fidelity")
    science = item.get("science")
    ledger = {
        "fidelity": fidelity,
        "established": [],
        "emerging": [],
        "metaphor": [item.get("metaphor")],
        "unknown_or_not_shown": [item["node"].get("evidence_boundary")],
    }
    if fidelity == "established":
        ledger["established"].append(science)
    elif fidelity == "emerging":
        ledger["emerging"].append(science)
    elif fidelity == "metaphor":
        ledger["metaphor"].append(science)
    return ledger


def _success_hypothesis(item: Dict[str, Any]) -> Dict[str, Any]:
    states = item["node"].get("audience_states", [])
    movement = item["node"].get("desired_movement")
    return {
        "attention": "Opening retention holds without increasing confusion or false certainty.",
        "reflection": "Comments show more observation, questioning, application or constructive disagreement—not agreement alone.",
        "capacity": movement,
        "autonomy": "Dependency, distress and certainty-transfer proxies remain low.",
        "production": "The ruling metaphor is legible through moving subjects; human and still-derived footage stay within pipeline limits.",
        "confidence_note": "This is a testable editorial hypothesis, not a prediction about any individual viewer.",
        "audience_state_hypotheses": states,
    }


def build_brief(concept_id: Optional[str] = None, date: Optional[str] = None) -> Dict[str, Any]:
    from intelligence import rank_candidates, select_portfolio

    ranked = rank_candidates()
    portfolio = select_portfolio(ranked)
    selected = None
    if concept_id:
        selected = next((item for item in ranked if item["id"] == concept_id), None)
        if selected is None:
            raise ValueError(f"unknown concept id: {concept_id}")
    else:
        selected = portfolio["next"]
    if not selected:
        raise RuntimeError("no selectable frontier concepts")

    node = selected["node"]
    alternatives = {
        key: (
            {"id": value["id"], "title": value["title"], "score": value["score"]}
            if value else None
        )
        for key, value in portfolio.items()
        if key != "next"
    }
    components = selected["components"]
    strongest = sorted(components.items(), key=lambda kv: -kv[1])[:3]

    brief = {
        "date": date or dt.date.today().isoformat(),
        "selected": {
            "id": selected["id"],
            "title": selected["title"],
            "score": selected["score"],
            "fidelity": selected["fidelity"],
            "hook": selected["hook"],
            "ruling_metaphor": selected["metaphor"],
            "turn": selected["turn"],
            "invitation": selected["invitation"],
            "science": selected["science"],
            "grounding": node.get("grounding"),
            "evidence_boundary": node.get("evidence_boundary"),
            "desired_movement": node.get("desired_movement"),
            "risks": node.get("risks", []),
            "risk_mitigations": node.get("risk_mitigations", []),
            "optimization_target": "belief_analysis",
        },
        "why_now": {
            "summary": "The selector chose this by balancing help, autonomy, science, freshness, sequence, production and only then performance.",
            "strongest_dimensions": [
                {"dimension": name, "score": value}
                for name, value in strongest
            ],
            "full_scorecard": components,
            "performance_weight": "5% of total; attention cannot overrule the constitution.",
            "sample_note": f"{selected.get('performance_sample', 0)} videos currently join to realized performance.",
        },
        "viewer_state": _state_details(node.get("audience_states", [])),
        "human_situations": node.get("human_situations", []),
        "mechanism": selected["science"],
        "science_ledger": _science_ledger(selected),
        "emotional_arc": {
            "start": (
                _state_details(node.get("audience_states", []))[0]["label"]
                if node.get("audience_states") else "Automatic certainty"
            ),
            "turn": selected["turn"],
            "landing": node.get("grounding"),
        },
        "visual_grammar": node.get("production", {}),
        "practical_tests": node.get("practical_tests", []),
        "help_modes": node.get("help_modes", []),
        "transformation_ladder": _transformation_ladder(node.get("formats", [])),
        "success_hypothesis": _success_hypothesis(selected),
        "influence_review": selected["guard"],
        "alternatives": alternatives,
    }
    return brief


def to_markdown(brief: Dict[str, Any]) -> str:
    selected = brief["selected"]
    lines = [
        "# Concept Engine — Decision Brief",
        "",
        f"**Date:** {brief['date']}",
        f"**Selected:** {selected['title']} [{selected['fidelity']}]",
        f"**Editorial score:** {selected['score']}/100",
        f"**Influence review:** {brief['influence_review']['decision']} "
        f"(autonomy {brief['influence_review']['autonomy_score']}/100)",
        "",
        "## Why now",
        brief["why_now"]["summary"],
    ]
    for item in brief["why_now"]["strongest_dimensions"]:
        lines.append(f"- {item['dimension'].replace('_', ' ')}: {item['score']}")
    lines.extend([
        f"- {brief['why_now']['performance_weight']}",
        f"- {brief['why_now']['sample_note']}",
        "",
        "## Viewer state and desired movement",
    ])
    for state in brief["viewer_state"]:
        lines.append(f"- **{state['label']}** — {state['movement']}")
    lines.extend([
        f"- Desired movement: {selected['desired_movement']}",
        "",
        "## Hook, mechanism and ruling metaphor",
        f"- Hook: {selected['hook']}",
        f"- Mechanism: {brief['mechanism']}",
        f"- Ruling metaphor: {selected['ruling_metaphor']}",
        f"- Turn: {selected['turn']}",
        "",
        "## Science ledger",
        f"- Fidelity: **{brief['science_ledger']['fidelity']}**",
    ])
    for label in ("established", "emerging", "metaphor", "unknown_or_not_shown"):
        for value in brief["science_ledger"].get(label, []):
            if value:
                lines.append(f"- {label.replace('_', ' ')}: {value}")
    lines.extend([
        "",
        "## Grounding and invitation",
        f"- Grounding: {selected['grounding']}",
        f"- Invitation: {selected['invitation']}",
        "",
        "## Visual grammar",
        f"- Motion score: {brief['visual_grammar'].get('motion_score')}",
        f"- Human ratio target: {brief['visual_grammar'].get('human_ratio_target')}",
        "- Moving subjects: " + ", ".join(brief["visual_grammar"].get("moving_subjects", [])),
        "- Avoid: " + ", ".join(brief["visual_grammar"].get("avoid", [])),
        "",
        "## Help beyond the video",
    ])
    for item in brief["transformation_ladder"]:
        lines.append(
            f"- **{item['id']} / {item['container']}** — {item['purpose']} "
            f"Boundary: {item['boundary']}"
        )
    lines.extend([
        "",
        "## Success hypothesis",
    ])
    for key, value in brief["success_hypothesis"].items():
        if isinstance(value, str):
            lines.append(f"- {key.replace('_', ' ')}: {value}")
    if brief["influence_review"]["issues"]:
        lines.extend(["", "## Influence review notes"])
        for issue in brief["influence_review"]["issues"]:
            lines.append(f"- **{issue['severity']} / {issue['code']}** — {issue['message']}")
    lines.extend([
        "",
        "## Alternatives",
    ])
    for key, value in brief["alternatives"].items():
        if value:
            lines.append(f"- {key}: {value['title']} ({value['score']})")
    return "\n".join(lines) + "\n"


def write_outputs(brief: Dict[str, Any]) -> None:
    with open(os.path.join(HERE, "LATEST_DECISION_BRIEF.json"), "w", encoding="utf-8") as f:
        json.dump(brief, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(HERE, "LATEST_DECISION_BRIEF.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(brief))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concept")
    parser.add_argument("--date")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    brief = build_brief(args.concept, args.date)
    write_outputs(brief)
    if args.json:
        print(json.dumps(brief, indent=2, ensure_ascii=False))
    else:
        print(to_markdown(brief), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
