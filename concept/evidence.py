"""Shared audience-evidence semantics. Missing measurements are never zero."""
from __future__ import annotations
import datetime as dt
import math
from typing import Any, Mapping


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


def freshness(value: Any, *, now: dt.datetime | None = None, days: int = 14) -> str:
    if not value:
        return "unknown"
    try:
        timestamp = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return "unknown"
        age = ((now or dt.datetime.now(dt.timezone.utc)) - timestamp).total_seconds()
    except (ValueError, TypeError):
        return "unknown"
    if age < -300:
        return "invalid_future_timestamp"
    return "fresh" if age <= days * 86400 else "stale"


def audience_evidence(stats: Mapping[str, Any], *, now: dt.datetime | None = None) -> dict:
    views = number(stats.get("views"))
    pct = number(stats.get("avg_view_pct", stats.get("average_view_percentage")))
    timestamp = stats.get("retention_snapshot_at")
    if timestamp is None and pct is not None:
        timestamp = stats.get("snapshot_at") or stats.get("collected_at")
    score = round(math.log10(views + 1) * pct, 4) if views is not None and pct is not None else None
    state = freshness(timestamp, now=now) if pct is not None else "unavailable"
    return {
        "views": views, "avg_view_pct": pct, "score": score,
        "retention_available": pct is not None,
        "retention_snapshot_at": timestamp, "retention_freshness": state,
        "eligible_for_recommendation": score is not None and state == "fresh" and views >= 30,
        "boundary": "Observed association only; missing, undated, stale, and low-view samples cannot establish a winning lane.",
    }
