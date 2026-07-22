"""Tier 3 — the daily invitation. The channel's mission distilled to its purest,
smallest form: one question a day that helps a person examine a belief. NOT a video —
a standalone, shareable micro-practice (community post / Substack line / Short caption /
one-a-day email). Audience-facing, where the concept brief is maker-facing.

Deterministic by date so a scheduled run is stable per day. Draws from the same
frontier bank and pillars, but outputs ONLY the invitation + a one-line frame — never
an explanation, never a lecture. Hand the test, not the verdict.

Usage: python3 concept/invitation.py [YYYY-MM-DD]
"""
import json, os, sys, datetime, hashlib, random

HERE = os.path.dirname(os.path.abspath(__file__))

def load(n): return json.load(open(os.path.join(HERE, n)))

def seed(date_str): return int(hashlib.sha256(("inv:"+date_str).encode()).hexdigest()[:8], 16)

def invitation(date_str):
    frontier = load("frontier.json")["frontier"]
    rng = random.Random(seed(date_str))
    c = rng.choice(frontier)
    # a single-breath frame (metaphor, no science jargon) + the invitation, then silence
    lines = [
        f"**{date_str} — one question**",
        "",
        f"_{c['metaphor']}_",
        "",
        c["invitation"],
        "",
        "— no right answer. just look.",
    ]
    return "\n".join(lines)

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    text = invitation(date_str)
    print(text)
    log = os.path.join(HERE, "INVITATION_LOG.md")
    with open(log, "a") as f:
        f.write(text + "\n\n---\n\n")

if __name__ == "__main__":
    main()
