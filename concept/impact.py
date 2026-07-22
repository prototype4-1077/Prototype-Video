"""Refresh the Concept Engine impact ledger.

Attention is only one layer. This ledger also records low-confidence proxies for
belief analysis, application, confusion and autonomy risk, while preserving
James's manual scene-feedback fields as the highest-trust craft evidence.

Usage: python3 concept/impact.py
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
from typing import Any, Dict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(path: str, default: Any, *, root: bool = False) -> Any:
    full = os.path.join(ROOT if root else HERE, path)
    try:
        with open(full, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def stats() -> Dict[str, Dict[str, Any]]:
    output = {}
    for filename in glob.glob(os.path.join(ROOT, "build", "*", "yt_stats.json")):
        slug = os.path.basename(os.path.dirname(filename))
        try:
            with open(filename, encoding="utf-8") as f:
                output[slug] = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return output


def confidence(comment_count: int, has_stats: bool, has_manual: bool) -> str:
    if has_manual and comment_count >= 50 and has_stats:
        return "high"
    if comment_count >= 20 and has_stats:
        return "developing"
    return "low"


def main() -> int:
    catalog = (load("catalog.json", {}) or {}).get("videos", {})
    signal = load("audience_signal.json", {}) or {}
    by_video = signal.get("by_video", {}) or {}
    performance = stats()
    ledger = load("impact_ledger.json", {}) or {
        "_note": "Concept Engine impact ledger",
        "metric_definitions": {},
        "entries": {},
    }
    entries = ledger.setdefault("entries", {})

    for slug, dna in catalog.items():
        previous = entries.get(slug, {})
        comments = by_video.get(slug, {}) if isinstance(by_video.get(slug, {}), dict) else {}
        yt = performance.get(slug, {})
        manual = previous.get("manual_scene_feedback", {
            "status": "not_imported",
            "approved_scenes": None,
            "rejected_scenes": None,
            "reasons": [],
            "note": "Import James's numbered survey decisions when available.",
        })
        comment_count = int(comments.get("total_comments_scanned", 0) or 0)
        entries[slug] = {
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "concept_dna": dna,
            "attention": {
                "views": int(yt.get("views", 0) or 0),
                "avg_view_pct": float(yt.get("avg_view_pct", 0) or 0),
                "avg_view_s": float(yt.get("avg_view_s", 0) or 0),
                "minutes_watched": float(yt.get("minutes_watched", 0) or 0),
            },
            "helpfulness_proxies": {
                "comments_scanned": comment_count,
                "tag_counts": comments.get("tag_counts", {}),
                "belief_analysis_yield_proxy": float(comments.get("belief_analysis_yield_proxy", 0) or 0),
                "autonomy_risk_proxy": float(comments.get("autonomy_risk_proxy", 0) or 0),
                "helpfulness_score_proxy": float(comments.get("helpfulness_score_proxy", 0) or 0),
                "method_note": comments.get(
                    "method_note",
                    "No comment signal yet; absence is not evidence of no impact.",
                ),
            },
            "manual_scene_feedback": manual,
            "prediction": previous.get("prediction", {
                "viewer_state": None,
                "desired_movement": None,
                "attention_hypothesis": None,
                "helpfulness_hypothesis": None,
                "risk_hypothesis": None,
            }),
            "postmortem": previous.get("postmortem", {
                "what_held": [],
                "what_bled": [],
                "what_helped": [],
                "what_confused": [],
                "what_to_change": [],
            }),
            "confidence": confidence(
                comment_count,
                bool(yt),
                manual.get("status") == "complete",
            ),
        }

    ledger["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with open(os.path.join(HERE, "impact_ledger.json"), "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"impact_ledger.json: refreshed {len(entries)} video entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
