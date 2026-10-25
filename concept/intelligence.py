"""Evidence-aware Concept Engine intelligence; no model calls or auto-publishing.

Public reach and authenticated retention remain separate measurements. Only dated,
fresh retention can influence recommendations. Historical evidence is retained
and labelled; small samples are exploratory, not proof of a creative rule.
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import statistics

try:
    from .evidence import audience_evidence, freshness, number
except ImportError:
    from evidence import audience_evidence, freshness, number

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def read(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {} if default is None else default


def load(name):
    return read(Path(HERE) / name)


def video_stats(root=None):
    output = {}
    for build in sorted((Path(root or ROOT) / "build").glob("*")):
        public = read(build / "yt_stats.json")
        retention = read(build / "retention_stats.json") or read(build / "legacy_retention_stats.json")
        if public or retention:
            # Public-count refreshes cannot erase authenticated retention.
            output[build.name] = {**public, **retention}
    return output


def score(views, pct):
    v, p = number(views), number(pct)
    return round(math.log10(v + 1) * p, 1) if v is not None and p is not None else None


def analyze(root=None, *, now=None):
    root = Path(root or ROOT)
    catalog = read(root / "concept/catalog.json").get("videos") or {}
    stats = video_stats(root)
    rows = []
    for slug, dna in catalog.items():
        if slug not in stats:
            continue
        evidence = audience_evidence(stats[slug], now=now)
        rows.append({"slug": slug, "views": evidence["views"],
                     "pct": evidence["avg_view_pct"], "score": evidence["score"],
                     "dna": dna, **evidence})
    dimensions = ("pillars", "narration", "hook", "series")
    groups = {dimension: collections.defaultdict(list) for dimension in dimensions}
    eligible = [row for row in rows if row["eligible_for_recommendation"]]
    prior = statistics.mean(row["score"] for row in eligible) if eligible else 0
    for row in eligible:
        for dimension in dimensions:
            values = row["dna"].get(dimension)
            for value in values if isinstance(values, list) else [values]:
                if value is not None:
                    groups[dimension][str(value)].append(row["score"])
    lanes = {dimension: sorted(
        ((key, round((sum(values) + 3 * prior) / (len(values) + 3), 1), len(values))
         for key, values in groups[dimension].items()), key=lambda item: (-item[1], item[0])
    ) for dimension in dimensions}
    return rows, lanes, len(stats)


def _frontier_pick(root: Path, now: dt.datetime):
    catalog = read(root / "concept/catalog.json").get("videos") or {}
    used = {item.get("frontier") for item in catalog.values()}
    frontier = read(root / "concept/frontier.json").get("frontier") or []
    options = [item for item in frontier if item.get("id") not in used] or frontier
    if not options:
        return None
    seed = int(hashlib.sha256(now.date().isoformat().encode()).hexdigest()[:8], 16)
    return options[seed % len(options)]


def recommend(root=None, *, now=None):
    root = Path(root or ROOT)
    now = now or dt.datetime.now(dt.timezone.utc)
    rows, lanes, _ = analyze(root, now=now)
    out = ["## What to make next"]
    eligible = [row for row in rows if row["eligible_for_recommendation"]]
    if not eligible:
        out.append("No fresh, dated retention evidence is eligible. Use editorial judgment and frontier exploration; do not infer poor performance from missing data.")
    for dimension, label in (("pillars", "pillar"), ("narration", "narration style"), ("hook", "hook type")):
        candidates = [item for item in lanes[dimension] if item[2] >= 3]
        if candidates:
            key, value, count = candidates[0]
            out.append(f"- Provisional {label} association: **{key}** (regularized score {value}; {count} fresh videos). This is observational and may be confounded.")
        elif eligible:
            out.append(f"- {label.title()}: fewer than three eligible examples per cohort; no winning-lane claim.")
    pick = _frontier_pick(root, now)
    if pick:
        out.append(f"- Editorial exploration: **{pick['title']}** [{pick.get('fidelity', 'unlabelled')}]. Hook: {pick.get('hook', '')} This is a frontier rotation, not a predicted audience winner.")
    out.append("James selects the concept and approves the script. Recommendations never start a render or publish a video.")
    return "\n".join(out)


def craft_rules(root=None):
    memory = read(Path(root or ROOT) / "pipeline/memory.json")
    feedback = memory.get("audience_feedback") or []
    if not feedback:
        return "- No structured retention feedback supports new craft rules. Preserve James's approved style."
    return (f"- {len(feedback)} historical audience-feedback records are available for review. "
            "Scene retention is observational; test a specific change before promoting it into a house rule.")


def learning_state(root):
    memory = read(root / "pipeline/memory.json")
    approvals = [read(path) for path in sorted((root / "build").glob("*/approval-record.json"))]
    recorded = [item for item in approvals if item.get("decision") == "approved"]
    missing_vectors = [item.get("slug") for item in recorded if item.get("taste_embedding_count") == 0]
    return {
        "historical_video_approval_records": len(memory.get("videos") or []),
        "scene_feedback_records": len(memory.get("scene_feedback") or []),
        "explicit_approval_audits": len(recorded),
        "approval_audits_without_new_taste_embeddings": missing_vectors,
        "boundary": "Whole-video approval, per-scene feedback, and learned image embeddings are separate evidence. An approved video need not have produced new embeddings; never infer per-scene judgments from a global approval.",
    }


def build_report(root=None, *, now=None):
    root = Path(root or ROOT)
    now = now or dt.datetime.now(dt.timezone.utc)
    rows, lanes, count = analyze(root, now=now)
    signals = read(root / "concept/external_signals/LATEST.json")
    signal_freshness = freshness(signals.get("generated_at"), now=now, days=7)
    records = signals.get("records") or []
    review_signals = [
        {key: record.get(key) for key in ("title", "url", "source", "topic_matches", "claim_status")}
        for record in records[:8]
    ] if signal_freshness == "fresh" else []
    return {
        "schema_version": 2, "generated_at": now.isoformat(),
        "stats_file_count": count, "joined_video_count": len(rows),
        "eligible_video_count": sum(row["eligible_for_recommendation"] for row in rows),
        "missing_retention_count": sum(not row["retention_available"] for row in rows),
        "stale_or_undated_retention_count": sum(row["retention_available"] and row["retention_freshness"] != "fresh" for row in rows),
        "videos": rows, "lanes": lanes, "learning_state": learning_state(root),
        "collection_health": {
            "public_statistics": read(root / "pipeline/youtube_stats_status.json"),
            "retention": read(root / "pipeline/analytics_status.json"),
            "external_signals": {"freshness": signal_freshness, "status": signals.get("status"), "record_count": len(records)},
        },
        "external_signals_for_review": review_signals,
        "recommendation": recommend(root, now=now), "craft_rules": craft_rules(root),
        "authority_boundary": "Read-only decision support. No narration edits, model promotion, render requests, or publication. External signals remain unverified reference material.",
        "model_boundary": "This upgrades the pipeline's evidence and decision logic; it does not retrain a foundation model or claim an offline fixture is a live model evaluation.",
    }


def render_report(data):
    lines = ["# Concept Engine — Evidence-aware Intelligence", "",
             f"Generated: {data['generated_at']}", "",
             f"Joined {data['joined_video_count']} videos; {data['eligible_video_count']} eligible for current recommendations.",
             f"Missing retention: {data['missing_retention_count']}; stale or undated retention: {data['stale_or_undated_retention_count']}.", "",
             data["recommendation"], "", "## Measurement inventory", ""]
    for row in sorted(data["videos"], key=lambda row: (row["score"] is None, -(row["score"] or 0), row["slug"])):
        pct = "unknown" if row["pct"] is None else f"{row['pct']:.1f}%"
        lines.append(f"- {row['slug']}: views={row['views']}; retention={pct}; freshness={row['retention_freshness']}; eligible={row['eligible_for_recommendation']}")
    lines.extend(["", "## Collection health", ""])
    for name, status in data["collection_health"].items():
        lines.append(f"- {name}: {status.get('status') or status.get('freshness') or 'not recorded'}")
    lines.extend(["", "## Research signals awaiting review", ""])
    for signal in data["external_signals_for_review"]:
        lines.append(f"- [{signal.get('title')}]({signal.get('url')}) — unverified reference; verify the primary source before use.")
    if not data["external_signals_for_review"]:
        lines.append("- No fresh external signal ledger is available.")
    learning = data["learning_state"]
    lines.extend(["", "## Learning coverage", "",
                  f"Historical whole-video approval records: {learning['historical_video_approval_records']}; scene feedback records: {learning['scene_feedback_records']}; explicit approval audits: {learning['explicit_approval_audits']}.",
                  f"Approval audits with no new taste embeddings: {learning['approval_audits_without_new_taste_embeddings']}.", learning["boundary"]])
    lines.extend(["", "## Craft evidence", "", data["craft_rules"], "", data["authority_boundary"], "", data["model_boundary"]])
    return "\n".join(lines) + "\n"


def report():
    print(render_report(build_report()), end="")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["report", "recommend"], default="report")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    args = parser.parse_args()
    data = build_report(args.root)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_report(data), encoding="utf-8")
    print(recommend(args.root) if args.command == "recommend" else render_report(data), end="\n")
