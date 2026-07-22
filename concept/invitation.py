"""Tier 3 — daily invitation.

A small, audience-facing belief-analysis practice. It uses the v3 selector rather
than blind random choice, but rotates safely among the top candidates so the daily
practice does not become an engagement echo chamber.

Usage: python3 concept/invitation.py [YYYY-MM-DD]
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import random
import sys
from typing import Any, Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))


def seed(date_str: str) -> int:
    return int(hashlib.sha256(("inv-v3:" + date_str).encode()).hexdigest()[:8], 16)


def choose(date_str: str) -> Dict[str, Any]:
    from intelligence import rank_candidates

    ranked = [
        item for item in rank_candidates()
        if item.get("guard", {}).get("decision") == "PASS"
        and not {"psychosis_vulnerability", "medical_misinformation"} & set(item["node"].get("risks", []))
    ]
    if not ranked:
        ranked = [
            item for item in rank_candidates()
            if item.get("guard", {}).get("decision") != "BLOCK"
        ]
    if not ranked:
        raise RuntimeError("no safe invitation candidates")

    # Rotate inside the top safe set; score still determines membership, date chooses the day.
    pool = ranked[: min(5, len(ranked))]
    rng = random.Random(seed(date_str))
    return rng.choice(pool)


def invitation(date_str: str) -> str:
    item = choose(date_str)
    grounding = item["node"].get("grounding", "Return to the room and notice what is here.")
    lines = [
        f"**{date_str} — one question**",
        "",
        f"_{item['metaphor']}_",
        "",
        item["invitation"],
        "",
        f"_Landing: {grounding}_",
        "",
        "There is no answer to perform. Notice what you notice.",
    ]
    return "\n".join(lines)


def main() -> int:
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    text = invitation(date_str)
    print(text)
    with open(os.path.join(HERE, "INVITATION_LOG.md"), "a", encoding="utf-8") as f:
        f.write(text + "\n\n---\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
