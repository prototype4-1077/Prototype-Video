"""Produce an evidence-aware, novelty-weighted daily concept brief.

The default command is read-only. Use ``--record`` to record an issued brief,
or ``--mark`` to record that a concept was selected, produced, published, or
rejected. History is structured so selection and audience outcomes are not
confused with merely previewing a prompt.

Examples:
    python3 concept/daily_brief.py
    python3 concept/daily_brief.py 2026-08-01 --record
    python3 concept/daily_brief.py --concept-id body_ownership --mark selected --slug where-you-end
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import itertools
import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
HISTORY_PATH = os.path.join(HERE, "brief_history.json")


def load(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def stable_fraction(value: str) -> float:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16) / float(16 ** 12)


def concept_usage(repo_root: str = REPO_ROOT) -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}
    for path in sorted(glob.glob(os.path.join(repo_root, "build", "*", "script.json"))):
        script = load(path, {}) or {}
        concept_id = script.get("concept_id")
        if concept_id:
            usage.setdefault(str(concept_id), []).append(str(script.get("slug") or os.path.basename(os.path.dirname(path))))
    return usage


def history_events() -> list[dict]:
    return (load(HISTORY_PATH, {}) or {}).get("events") or []


def recent_ids(date_value: dt.date, days: int = 21) -> set[str]:
    cutoff = date_value - dt.timedelta(days=days)
    ids = set()
    for event in history_events():
        try:
            event_date = dt.date.fromisoformat(str(event.get("date")))
        except ValueError:
            continue
        if event_date >= cutoff:
            ids.update(str(item) for item in event.get("concept_ids") or [])
    return ids


def frontier_score(concept: dict, date_value: dt.date, usage: dict, evidence: dict, outcomes: dict) -> float:
    concept_id = str(concept["id"])
    used_count = len(usage.get(concept_id, []))
    recent = concept_id in recent_ids(date_value)
    claim = (evidence.get("claims") or {}).get(concept.get("evidence_id") or concept_id, {})
    source_count = len(claim.get("source_ids") or [])
    status_bonus = {"established": 0.75, "emerging": 0.35, "metaphor": 0.1}.get(claim.get("status"), 0)
    outcome = (outcomes.get("concepts") or {}).get(concept_id, {})
    audience_bonus = min(1.5, float(outcome.get("mean_watch_ratio") or 0) * 1.5)
    return (
        (4.0 if used_count == 0 else max(0.0, 2.0 - used_count))
        + (2.0 if not recent else 0.0)
        + min(2.0, source_count * 0.5)
        + status_bonus
        + audience_bonus
        + stable_fraction(f"{date_value.isoformat()}:{concept_id}") * 0.01
    )


def choose_frontier(date_value: dt.date, frontier: list[dict], evidence: dict, outcomes: dict) -> dict:
    usage = concept_usage()
    return max(frontier, key=lambda item: frontier_score(item, date_value, usage, evidence, outcomes))


def choose_cross_pollination(date_value: dt.date, pillars: list[dict]) -> tuple[dict, dict]:
    recent_pairs = {
        tuple(sorted(str(item) for item in event.get("concept_ids") or []))
        for event in history_events()
        if event.get("kind") == "cross_pollination"
    }
    candidates = []
    max_weight = max([int(item.get("weight") or 0) for item in pillars] or [1])
    for left, right in itertools.combinations(pillars, 2):
        pair = tuple(sorted((str(left["id"]), str(right["id"]))))
        coverage_gap = 2.0 - ((int(left.get("weight") or 0) + int(right.get("weight") or 0)) / max_weight)
        novelty = 2.0 if pair not in recent_pairs else 0.0
        tie = stable_fraction(f"{date_value.isoformat()}:{pair[0]}:{pair[1]}") * 0.01
        candidates.append((coverage_gap + novelty + tie, left, right))
    _, left, right = max(candidates, key=lambda item: item[0])
    return left, right


def source_lines(claim: dict, evidence: dict) -> list[str]:
    lines = []
    sources = evidence.get("sources") or {}
    for source_id in claim.get("source_ids") or []:
        source = sources.get(source_id) or {}
        if source.get("url"):
            lines.append(f"- {source.get('citation', source_id)} — {source['url']}")
    return lines


def build_brief(date_str: str) -> tuple[str, dict]:
    date_value = dt.date.fromisoformat(date_str)
    patterns = load(os.path.join(HERE, "patterns.json"), {}) or {}
    frontier = (load(os.path.join(HERE, "frontier.json"), {}) or {}).get("frontier") or []
    evidence = load(os.path.join(HERE, "evidence.json"), {}) or {}
    outcomes = load(os.path.join(HERE, "outcomes.json"), {}) or {}
    signatures = patterns.get("structural_signatures") or []

    # Two evidence-led frontier days, then one lower-coverage cross-pollination day.
    if date_value.toordinal() % 3 != 0:
        concept = choose_frontier(date_value, frontier, evidence, outcomes)
        claim = (evidence.get("claims") or {}).get(concept.get("evidence_id") or concept["id"], {})
        usage = concept_usage().get(concept["id"], [])
        body = [
            f"# Concept Brief — {date_str}",
            f"## Frontier: {concept['title']}  [{concept['fidelity']}]",
            f"**Why now:** {'Not yet represented by a concept-tagged script.' if not usage else 'Least-recent, evidence-ready candidate after coverage and history checks.'}",
            f"**Bounded evidence claim:** {claim.get('supported_claim', concept['science'])}",
            f"**Interpretation to explore:** {concept['science']}",
            f"**Ruling metaphor:** {concept['metaphor']}",
            f"**Strongest counterview:** {claim.get('strongest_counterview', 'Add the strongest plausible alternative explanation before drafting.')}",
            f"**Limits:** {claim.get('limitations', 'Keep uncertainty visible.')}",
            f"**Blind spots:** {', '.join(claim.get('blind_spots') or ['population and cultural scope'])}",
            f"**Hook:** {concept['hook']}",
            f"**The turn:** {concept['turn']}",
            f"**Invitation:** {concept['invitation']}",
            "**Sources:**",
            *source_lines(claim, evidence),
        ]
        if concept.get("note"):
            body.append(f"**Safety note:** {concept['note']}")
        event = {
            "date": date_str,
            "kind": "frontier",
            "concept_ids": [concept["id"]],
            "status": "issued",
        }
    else:
        left, right = choose_cross_pollination(date_value, patterns.get("pillars") or [])
        signature = signatures[int(stable_fraction(date_str) * len(signatures)) % len(signatures)] if signatures else "End on an invitation and return to the ordinary."
        body = [
            f"# Concept Brief — {date_str}",
            f"## Cross-pollination: {left['label']} × {right['label']}",
            f"**Why now:** These are among the lower-coverage pillars and this pair is not in the recent brief history.",
            f"**A ({left['id']}):** {left.get('essence', '')}",
            f"**B ({right['id']}):** {right.get('essence', '')}",
            f"**Prompt:** Explain {left['label'].lower()} through {right['label'].lower()} while preserving the difference between evidence and metaphor.",
            "**Counterview requirement:** Include one observation that would weaken the ruling interpretation.",
            "**Blind-spot requirement:** Consult a discipline, culture, or lived experience absent from the existing exemplars.",
            f"**Structural signature:** {signature}",
            "**Invitation:** End with a test the viewer can perform, not a conclusion they must adopt.",
        ]
        event = {
            "date": date_str,
            "kind": "cross_pollination",
            "concept_ids": [left["id"], right["id"]],
            "status": "issued",
        }

    body += ["", "_Hand the viewer the method, the uncertainty, and the invitation._"]
    return "\n".join(body), event


def save_event(event: dict) -> bool:
    data = load(HISTORY_PATH, {}) or {"schema_version": 1, "events": []}
    events = data.setdefault("events", [])
    identity = (event.get("date"), event.get("kind"), tuple(event.get("concept_ids") or []), event.get("status"), event.get("slug"))
    if any(
        (item.get("date"), item.get("kind"), tuple(item.get("concept_ids") or []), item.get("status"), item.get("slug")) == identity
        for item in events
    ):
        return False
    events.append(event)
    with open(HISTORY_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", nargs="?", default=dt.date.today().isoformat())
    parser.add_argument("--record", action="store_true", help="record the generated brief as issued")
    parser.add_argument("--mark", choices=("selected", "produced", "published", "rejected"))
    parser.add_argument("--concept-id")
    parser.add_argument("--slug")
    args = parser.parse_args(argv)

    if args.mark:
        if not args.concept_id:
            parser.error("--mark requires --concept-id")
        event = {
            "date": args.date,
            "kind": "concept_status",
            "concept_ids": [args.concept_id],
            "status": args.mark,
        }
        if args.slug:
            event["slug"] = args.slug
        print("recorded" if save_event(event) else "already recorded")
        return 0

    text, event = build_brief(args.date)
    print(text)
    if args.record:
        print("\n[brief history: recorded]" if save_event(event) else "\n[brief history: already recorded]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
