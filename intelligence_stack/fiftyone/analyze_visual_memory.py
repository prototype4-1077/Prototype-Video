#!/usr/bin/env python3
"""Analyze visual memory without confusing automated risk with James's feedback."""
from __future__ import annotations

from collections import defaultdict
import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "concept" / "visual_memory"
REVIEWED = {"approved", "approve", "revise", "revision", "needs_revision", "rejected"}
APPROVED = {"approved", "approve"}
REVISED = {"revise", "revision", "needs_revision", "rejected"}

USER_PATTERNS = {
    "semantic_mismatch": ("does not match", "doesn't match", "unrelated", "wrong visual", "reflect the concept"),
    "needs_literal_visual": ("literal", "actually walking", "represents what's being said", "represents what is being said"),
    "prefer_effects_still": ("still image", "special effects", "effects still"),
    "prefer_cartoon_animation": ("cartoon", "animated means", "cartoon animated"),
    "continuity_failure": ("connect", "same scene", "continuous", "continuity", "different world"),
    "character_solidity": ("ghost", "transparent", "solid", "pasted"),
    "lip_sync": ("lip", "mouth", "speaking", "narrator is speaking"),
    "depth_parallax": ("3d", "depth", "coming off the page", "parallax"),
    "title_layout": ("title", "cut off", "thumbnail", "placement", "caption"),
    "synthetic_appearance": ("fake-looking", "ai-looking", "synthetic", "mannequin"),
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def load_records(path: Path) -> list[dict[str, Any]]:
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    except (OSError, ValueError):
        pass
    return rows


def user_tags(comment: str) -> list[str]:
    low = str(comment or "").lower()
    return sorted(name for name, cues in USER_PATTERNS.items() if any(cue in low for cue in cues))


def risk_tags(record: dict[str, Any]) -> list[str]:
    return sorted({
        str(item.get("code"))
        for item in ((record.get("risk") or {}).get("findings") or [])
        if isinstance(item, dict) and item.get("code")
    })


def rate_rows(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"reviewed": 0, "approved": 0, "revised": 0})
    for record in records:
        decision = str(record.get("decision") or "unreviewed").lower()
        if decision not in REVIEWED:
            continue
        value = str(record.get(field) or "unknown")
        bucket = buckets[value]
        bucket["reviewed"] += 1
        if decision in APPROVED:
            bucket["approved"] += 1
        elif decision in REVISED:
            bucket["revised"] += 1
    rows = []
    for value, counts in buckets.items():
        reviewed = counts["reviewed"]
        rows.append({
            "value": value,
            **counts,
            "approval_rate": round(counts["approved"] / reviewed, 4) if reviewed else None,
            "evidence_strength": "developing" if reviewed >= 3 else "insufficient",
        })
    return sorted(rows, key=lambda item: (-item["reviewed"], item["value"]))


def build(memory_dir: Path = DEFAULT_DIR) -> dict[str, Any]:
    records = load_records(memory_dir / "manifest.jsonl")
    reviewed = [row for row in records if str(row.get("decision") or "").lower() in REVIEWED]
    approved = [row for row in reviewed if str(row.get("decision") or "").lower() in APPROVED]
    revised = [row for row in reviewed if str(row.get("decision") or "").lower() in REVISED]
    with_assets = [row for row in records if row.get("asset_path")]

    feedback_counts: dict[str, int] = defaultdict(int)
    risk_counts: dict[str, int] = defaultdict(int)
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reviewed:
        for tag in user_tags(str(row.get("comment") or "")):
            feedback_counts[tag] += 1
            if len(examples[tag]) < 8:
                examples[tag].append({
                    "slug": row.get("slug"),
                    "scene_number": row.get("scene_number"),
                    "decision": row.get("decision"),
                    "comment": row.get("comment"),
                })
    for row in records:
        for tag in risk_tags(row):
            risk_counts[tag] += 1

    review_queue = []
    for row in records:
        if str(row.get("decision") or "unreviewed").lower() in REVIEWED or not row.get("asset_path"):
            continue
        risk = row.get("risk") or {}
        score = float(risk.get("effective_risk_score") or risk.get("risk_score") or 0.0)
        review_queue.append({
            "slug": row.get("slug"),
            "scene_number": row.get("scene_number"),
            "asset_path": row.get("asset_path"),
            "risk_score": score,
            "automated_risk_tags": risk_tags(row),
            "visual_function": row.get("visual_function"),
            "provider": row.get("provider"),
            "generation_route": row.get("generation_route"),
        })
    review_queue.sort(key=lambda item: (-item["risk_score"], str(item["slug"]), int(item["scene_number"] or 0)))

    actions: list[dict[str, Any]] = []
    total = len(records)
    reviewed_ratio = len(reviewed) / total if total else 0.0
    asset_ratio = len(with_assets) / total if total else 0.0
    if reviewed_ratio < 0.10:
        actions.append({
            "priority": "high",
            "category": "evidence_coverage",
            "evidence": f"Only {len(reviewed)} of {total} scene records have a human decision ({reviewed_ratio:.1%}).",
            "action": "Do not convert automated risk frequency into house rules. Review the highest-risk asset-backed queue first.",
        })
    if asset_ratio < 0.25:
        actions.append({
            "priority": "medium",
            "category": "asset_coverage",
            "evidence": f"Only {len(with_assets)} of {total} records retain a reviewable asset ({asset_ratio:.1%}).",
            "action": "Persist representative frames or durable release references for completed scenes so historical feedback remains inspectable.",
        })
    for tag, count in sorted(feedback_counts.items(), key=lambda pair: (-pair[1], pair[0])):
        if count >= 2:
            actions.append({
                "priority": "high" if count >= 5 else "medium",
                "category": "reviewed_feedback_pattern",
                "key": tag,
                "evidence": f"{count} reviewed scene comments",
                "action": "Promote this pattern into a testable production rule only after checking the listed examples for the same root cause.",
                "examples": examples[tag],
            })
    for field in ("generation_route", "provider", "symbol_family"):
        for row in rate_rows(records, field):
            if row["reviewed"] >= 3 and row["approval_rate"] is not None and row["approval_rate"] < 0.60:
                actions.append({
                    "priority": "medium",
                    "category": "low_approval_cohort",
                    "key": f"{field}:{row['value']}",
                    "evidence": f"{row['approved']}/{row['reviewed']} approved ({row['approval_rate']:.0%})",
                    "action": "Inspect the cohort before changing global routing; topic and scene difficulty may be confounders.",
                })

    report = {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "records": total,
        "with_assets": len(with_assets),
        "asset_coverage": round(asset_ratio, 4),
        "reviewed": len(reviewed),
        "approved": len(approved),
        "revised": len(revised),
        "reviewed_coverage": round(reviewed_ratio, 4),
        "reviewed_feedback_tags": dict(sorted(feedback_counts.items(), key=lambda pair: (-pair[1], pair[0]))),
        "automated_risk_tags": dict(sorted(risk_counts.items(), key=lambda pair: (-pair[1], pair[0]))),
        "cohorts": {
            "generation_route": rate_rows(records, "generation_route"),
            "provider": rate_rows(records, "provider"),
            "symbol_family": rate_rows(records, "symbol_family"),
        },
        "review_queue": review_queue[:100],
        "actions": actions,
        "interpretation_boundary": "Reviewed comments are high-trust craft evidence. Automated risk tags are screening signals only and cannot become production rules by frequency alone.",
    }
    output = memory_dir / "action_report.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-dir", default=str(DEFAULT_DIR))
    args = parser.parse_args()
    print(json.dumps(build(Path(args.memory_dir)), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
