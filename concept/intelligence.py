"""Concept Engine v3 — editorial intelligence.

Joins concept DNA, realized performance, audience signals, the concept graph,
channel sequence and the influence constitution. The goal is not maximum reach.
The goal is the best next piece that is helpful, fresh, honest, producible and
unlikely to narrow the viewer's agency.

Usage:
    python3 concept/intelligence.py
    python3 concept/intelligence.py recommend
    python3 concept/intelligence.py --json
"""
from __future__ import annotations

import collections
import datetime as _dt
import glob
import json
import math
import os
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

WEIGHTS = {
    "autonomy_safety": 0.20,
    "help_potential": 0.18,
    "audience_need": 0.14,
    "science_integrity": 0.12,
    "conceptual_freshness": 0.10,
    "sequence_value": 0.10,
    "production_potential": 0.06,
    "channel_development": 0.05,
    "performance_fit": 0.05,
}


def load(path: str, default: Any = None, *, root: bool = False) -> Any:
    full = os.path.join(ROOT if root else HERE, path)
    try:
        with open(full, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def video_stats() -> Dict[str, Dict[str, Any]]:
    """slug -> YouTube analytics committed by the nightly sync."""
    out: Dict[str, Dict[str, Any]] = {}
    for filename in glob.glob(os.path.join(ROOT, "build", "*", "yt_stats.json")):
        slug = os.path.basename(os.path.dirname(filename))
        try:
            with open(filename, encoding="utf-8") as f:
                out[slug] = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def score(views: float, pct: float) -> float:
    """Backwards-compatible attention score.

    Log reach prevents one viral outlier from completely dominating; retention
    still carries the main quality signal. This is an attention metric, not a
    helpfulness metric.
    """
    views = max(float(views or 0), 0.0)
    pct = clamp(float(pct or 0), 0.0, 100.0)
    return round(math.log10(views + 1.0) * pct, 2)


def _lane_label(n: int) -> str:
    if n < 3:
        return "early signal"
    if n < 6:
        return "developing"
    return "repeatable signal"


def analyze() -> Tuple[List[Dict[str, Any]], Dict[str, List[Tuple[str, float, int, str]]], int]:
    """Return joined rows and confidence-shrunk lane estimates.

    v2 averaged observed scores directly, which overfit tiny samples. v3 shrinks
    every lane toward the global mean and always exposes sample size.
    """
    catalog = (load("catalog.json", {}) or {}).get("videos", {})
    stats = video_stats()
    rows: List[Dict[str, Any]] = []
    for slug, dna in catalog.items():
        item = stats.get(slug)
        if not item:
            continue
        rows.append({
            "slug": slug,
            "views": int(item.get("views", 0) or 0),
            "pct": float(item.get("avg_view_pct", 0) or 0),
            "avg_view_s": float(item.get("avg_view_s", 0) or 0),
            "score": score(item.get("views", 0), item.get("avg_view_pct", 0)),
            "dna": dna,
        })

    dimensions = ("pillars", "narration", "hook", "series")
    sums = {d: collections.defaultdict(lambda: [0.0, 0]) for d in dimensions}
    global_mean = (
        sum(row["score"] for row in rows) / len(rows)
        if rows else 0.0
    )
    prior_strength = 3.0

    for row in rows:
        for dimension in dimensions:
            values = row["dna"].get(dimension)
            values = values if isinstance(values, list) else [values]
            for value in values:
                if value is None:
                    continue
                sums[dimension][str(value)][0] += row["score"]
                sums[dimension][str(value)][1] += 1

    lanes: Dict[str, List[Tuple[str, float, int, str]]] = {}
    for dimension in dimensions:
        estimates = []
        for name, (total, n) in sums[dimension].items():
            shrunk = (total + prior_strength * global_mean) / (n + prior_strength)
            estimates.append((name, round(shrunk, 2), n, _lane_label(n)))
        lanes[dimension] = sorted(estimates, key=lambda item: (-item[1], -item[2], item[0]))
    return rows, lanes, len(stats)


def _published_order() -> List[str]:
    published = load(os.path.join("pipeline", "published_videos.json"), {}, root=True) or {}
    if not isinstance(published, dict):
        return []
    def key(item: Tuple[str, Any]) -> str:
        meta = item[1] if isinstance(item[1], dict) else {}
        return str(meta.get("published_at", ""))
    return [slug for slug, _ in sorted(published.items(), key=key)]


def _recent_dna(catalog: Mapping[str, Any], count: int = 5) -> List[Dict[str, Any]]:
    order = _published_order()
    slugs = [slug for slug in order if slug in catalog][-count:]
    if not slugs:
        slugs = list(catalog.keys())[-count:]
    return [catalog[slug] for slug in slugs]


def _audience_text() -> str:
    signal = load("audience_signal.json", {}) or {}
    chunks: List[str] = []
    # v3 structure.
    for video in (signal.get("by_video") or {}).values():
        if not isinstance(video, dict):
            continue
        for samples in (video.get("samples") or {}).values():
            if not isinstance(samples, list):
                continue
            for sample in samples:
                if isinstance(sample, dict):
                    chunks.append(str(sample.get("excerpt", "")))
                else:
                    chunks.append(str(sample))
    # v2 compatibility.
    for key in ("requests", "confused_about", "resonated"):
        for item in signal.get(key, []) or []:
            if isinstance(item, (list, tuple)) and item:
                chunks.append(str(item[-1]))
            elif isinstance(item, str):
                chunks.append(item)
    return " ".join(chunks).lower()


def _audience_need(node: Mapping[str, Any], signal_text: str) -> float:
    if not signal_text.strip():
        return 50.0
    terms = []
    for field in ("signal_terms", "human_situations"):
        terms.extend(str(x).replace("_", " ").lower() for x in node.get(field, []) or [])
    hits = sum(signal_text.count(term) for term in terms if len(term) >= 3)
    # Audience demand is informative but capped; comments do not become editorial authority.
    return clamp(45.0 + min(35.0, hits * 5.0), 0.0, 80.0)


def _freshness(concept_id: str, node: Mapping[str, Any], catalog: Mapping[str, Any], recent: Sequence[Mapping[str, Any]]) -> float:
    used = [dna for dna in catalog.values() if dna.get("frontier") == concept_id]
    if not used:
        base = 100.0
    elif any(dna.get("frontier") == concept_id for dna in recent):
        base = 15.0
    else:
        base = 55.0

    recent_pillars = [p for dna in recent for p in dna.get("pillars", [])]
    overlap = sum(1 for p in node.get("pillars", []) if p in recent_pillars)
    return clamp(base - overlap * 7.0)


def _sequence_value(node: Mapping[str, Any], recent: Sequence[Mapping[str, Any]]) -> float:
    if not recent:
        return 70.0
    recent_pillars = [set(dna.get("pillars", [])) for dna in recent]
    candidate = set(node.get("pillars", []))
    overlap = sum(len(candidate & pillars) for pillars in recent_pillars)
    value = 82.0 - overlap * 7.0

    # After several threshold/identity-heavy pieces, reward ordinary grounding.
    last_three = recent[-3:]
    heavy = sum(bool({"threshold", "self"} & set(dna.get("pillars", []))) for dna in last_three)
    if heavy >= 2 and "grounding" in candidate:
        value += 14.0
    if all("grounding" not in set(dna.get("pillars", [])) for dna in last_three) and "grounding" in candidate:
        value += 8.0
    return clamp(value)


def _help_potential(node: Mapping[str, Any]) -> float:
    modes = len(node.get("help_modes", []) or [])
    tests = len(node.get("practical_tests", []) or [])
    movement = bool(node.get("desired_movement"))
    formats = len(node.get("formats", []) or [])
    return clamp(42 + modes * 10 + tests * 8 + (12 if movement else 0) + min(10, formats * 2))


def _science_integrity(concept: Mapping[str, Any], node: Mapping[str, Any]) -> float:
    base = {"established": 100.0, "emerging": 78.0, "metaphor": 62.0}.get(concept.get("fidelity"), 45.0)
    if not node.get("evidence_boundary"):
        base -= 30
    if not node.get("risk_mitigations"):
        base -= 10
    return clamp(base)


def _production_potential(node: Mapping[str, Any]) -> float:
    production = node.get("production", {}) or {}
    value = float(production.get("motion_score", 60) or 60)
    human = float(production.get("human_ratio_target", 0.4) or 0.4)
    if human > 0.5:
        value -= 15
    if len(production.get("moving_subjects", []) or []) < 3:
        value -= 8
    return clamp(value)


def _channel_development(node: Mapping[str, Any], catalog: Mapping[str, Any]) -> float:
    patterns = (load("patterns.json", {}) or {}).get("pillars", [])
    target_weights = {p["id"]: float(p.get("weight", 0)) for p in patterns if isinstance(p, dict)}
    target_total = sum(target_weights.values()) or 1.0
    observed = collections.Counter(
        pillar for dna in catalog.values() for pillar in dna.get("pillars", [])
    )
    observed_total = sum(observed.values()) or 1

    scores = []
    for pillar in node.get("pillars", []) or []:
        target_share = target_weights.get(pillar, 0) / target_total
        actual_share = observed.get(pillar, 0) / observed_total
        if target_share <= 0:
            scores.append(50.0)
            continue
        gap = (target_share - actual_share) / target_share
        scores.append(clamp(50 + gap * 35, 10, 90))
    return sum(scores) / len(scores) if scores else 50.0


def _performance_fit(node: Mapping[str, Any], lanes: Mapping[str, Sequence[Tuple[str, float, int, str]]]) -> float:
    pillar_lanes = {name: (value, n) for name, value, n, _ in lanes.get("pillars", [])}
    values = []
    for pillar in node.get("pillars", []) or []:
        if pillar in pillar_lanes:
            values.append(pillar_lanes[pillar])
    if not values:
        return 50.0

    all_values = [value for _, value, _, _ in lanes.get("pillars", [])]
    high = max(all_values) if all_values else 1.0
    low = min(all_values) if all_values else 0.0
    span = max(high - low, 1.0)
    best_value, best_n = max(values, key=lambda item: item[0])
    normalized = 45 + ((best_value - low) / span) * 45
    confidence = min(1.0, best_n / 6.0)
    return clamp(50 + (normalized - 50) * confidence)


def _guard_candidate(concept: Mapping[str, Any], node: Mapping[str, Any]) -> Dict[str, Any]:
    candidate = dict(concept)
    candidate.update({
        "grounding": node.get("grounding"),
        "evidence_boundary": node.get("evidence_boundary"),
        "desired_movement": node.get("desired_movement"),
        "risks": node.get("risks", []),
        "risk_mitigations": node.get("risk_mitigations", []),
        "optimization_target": "belief_analysis",
    })
    try:
        from influence_guard import assess
        return assess(candidate)
    except Exception as exc:  # guard failure should force review, not silently pass.
        return {
            "decision": "REVIEW",
            "autonomy_score": 55,
            "issues": [{"code": "guard_unavailable", "severity": "review", "message": str(exc)}],
        }


def rank_candidates() -> List[Dict[str, Any]]:
    frontier = (load("frontier.json", {}) or {}).get("frontier", [])
    graph = (load("concept_graph.json", {}) or {}).get("nodes", {})
    catalog = (load("catalog.json", {}) or {}).get("videos", {})
    rows, lanes, stat_count = analyze()
    recent = _recent_dna(catalog)
    signal_text = _audience_text()

    ranked: List[Dict[str, Any]] = []
    for concept in frontier:
        concept_id = concept.get("id")
        node = graph.get(concept_id, {})
        if not concept_id or not node:
            continue
        guard = _guard_candidate(concept, node)
        components = {
            "autonomy_safety": float(guard.get("autonomy_score", 0)),
            "help_potential": _help_potential(node),
            "audience_need": _audience_need(node, signal_text),
            "science_integrity": _science_integrity(concept, node),
            "conceptual_freshness": _freshness(concept_id, node, catalog, recent),
            "sequence_value": _sequence_value(node, recent),
            "production_potential": _production_potential(node),
            "channel_development": _channel_development(node, catalog),
            "performance_fit": _performance_fit(node, lanes),
        }
        total = sum(components[name] * weight for name, weight in WEIGHTS.items())
        if guard.get("decision") == "BLOCK":
            total = 0.0
        ranked.append({
            "id": concept_id,
            "title": concept.get("title"),
            "fidelity": concept.get("fidelity"),
            "hook": concept.get("hook"),
            "metaphor": concept.get("metaphor"),
            "turn": concept.get("turn"),
            "invitation": concept.get("invitation"),
            "science": concept.get("science"),
            "node": node,
            "guard": guard,
            "components": {k: round(v, 1) for k, v in components.items()},
            "score": round(total, 1),
            "performance_sample": len(rows),
            "stat_files": stat_count,
        })
    return sorted(ranked, key=lambda item: (-item["score"], item["title"] or ""))


def select_portfolio(ranked: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Optional[Dict[str, Any]]]:
    ranked = list(ranked if ranked is not None else rank_candidates())
    if not ranked:
        return {"next": None, "experimental": None, "evergreen": None}
    safe = [item for item in ranked if item["guard"].get("decision") != "BLOCK"]
    next_pick = safe[0] if safe else ranked[0]

    remaining = [item for item in safe if item["id"] != next_pick["id"]]
    experimental = max(
        remaining,
        key=lambda item: (
            item["components"]["conceptual_freshness"]
            + item["components"]["channel_development"]
            + item["components"]["sequence_value"]
        ),
        default=None,
    )
    evergreen = max(
        remaining,
        key=lambda item: (
            item["components"]["help_potential"]
            + item["components"]["science_integrity"]
            + item["components"]["autonomy_safety"]
        ),
        default=None,
    )
    return {"next": next_pick, "experimental": experimental, "evergreen": evergreen}


def _reason(item: Dict[str, Any]) -> str:
    top = sorted(item["components"].items(), key=lambda kv: -kv[1])[:3]
    return ", ".join(f"{name.replace('_', ' ')} {value:.0f}" for name, value in top)


def recommend() -> str:
    ranked = rank_candidates()
    portfolio = select_portfolio(ranked)
    rows, lanes, stat_count = analyze()

    lines = ["## What to make next — multi-objective editorial steer"]
    if rows:
        lines.append(
            f"_Joined {len(rows)} videos with realized performance. Lane claims are "
            f"{'early' if len(rows) < 6 else 'developing'} and are confidence-shrunk._"
        )
    else:
        lines.append("_No joined performance yet; the selector is using mission, graph, sequence and production priors._")

    labels = (
        ("next", "Best next video"),
        ("experimental", "Best experimental bet"),
        ("evergreen", "Best evergreen/help-oriented piece"),
    )
    for key, label in labels:
        item = portfolio.get(key)
        if not item:
            continue
        lines.append(
            f"- **{label}: {item['title']}** [{item['fidelity']}] — score {item['score']}/100; "
            f"{_reason(item)}. Guard: {item['guard']['decision']}. Hook: {item['hook']}"
        )

    if lanes.get("pillars"):
        name, value, n, status = lanes["pillars"][0]
        lines.append(
            f"- Performance context: **{name}** is the current top pillar lane "
            f"({status}, n={n}); it contributes only {WEIGHTS['performance_fit']:.0%} of the decision."
        )
    lines.append(
        "- Constitutional rule: attention may break a tie; it may not overrule autonomy, science fidelity, grounding or help potential."
    )
    return "\n".join(lines)


def report() -> str:
    rows, lanes, stat_count = analyze()
    ranked = rank_candidates()
    lines = ["# Concept Engine — Intelligence Report", ""]
    lines.append(
        f"_Joined {len(rows)} catalog videos with performance data "
        f"({stat_count} stat files present)._"
    )
    lines.append("")
    if rows:
        lines.append("## Realized attention performance")
        for row in sorted(rows, key=lambda item: -item["score"]):
            dna = row["dna"]
            lines.append(
                f"- {row['slug']}: {row['views']} views @ {row['pct']:.1f}% "
                f"→ attention score {row['score']:.1f} "
                f"({'+'.join(dna.get('pillars', []))}; {dna.get('narration')}; {dna.get('hook')})"
            )
        lines.append("")
        lines.append("## Confidence-shrunk lanes")
        for dimension in ("pillars", "narration", "hook"):
            summary = ", ".join(
                f"{name} {value:.1f} ({status}, n={n})"
                for name, value, n, status in lanes.get(dimension, [])[:4]
            )
            lines.append(f"- {dimension}: {summary}")
        lines.append("")
    lines.append(recommend())
    lines.append("")
    lines.append("## Ranked frontier")
    for item in ranked:
        lines.append(
            f"- {item['title']}: {item['score']:.1f} — "
            f"help {item['components']['help_potential']:.0f}, "
            f"safety {item['components']['autonomy_safety']:.0f}, "
            f"science {item['components']['science_integrity']:.0f}, "
            f"freshness {item['components']['conceptual_freshness']:.0f}, "
            f"performance fit {item['components']['performance_fit']:.0f}; "
            f"guard {item['guard']['decision']}"
        )
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--json" in argv:
        print(json.dumps({"ranked": rank_candidates(), "portfolio": select_portfolio()}, indent=2, ensure_ascii=False))
    elif argv and argv[0] == "recommend":
        print(recommend())
    else:
        print(report(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
