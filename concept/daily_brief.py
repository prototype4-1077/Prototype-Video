"""The daily concept draw. Deterministic by date so a scheduled run is stable
within a day but rotates. Emits ONE fresh angle to spark today's scripts:
either an untouched frontier concept, or a cross-pollination of two pillars.

Usage: python3 concept/daily_brief.py [YYYY-MM-DD]
Prints a brief and appends it to concept/BRIEF_LOG.md.
"""
import json, os, sys, datetime, hashlib, random

HERE=os.path.dirname(os.path.abspath(__file__))

def load(name): return json.load(open(os.path.join(HERE,name)))

def seed_for(date_str):
    return int(hashlib.sha256(date_str.encode()).hexdigest()[:8],16)

def brief(date_str):
    patterns=load("patterns.json"); frontier=load("frontier.json")["frontier"]
    pillars=patterns["pillars"]; sigs=patterns["structural_signatures"]
    rng=random.Random(seed_for(date_str))
    # 60% draw an untouched frontier concept; 40% cross-pollinate two pillars
    if rng.random()<0.6:
        c=rng.choice(frontier)
        body=[
          f"# Concept Brief — {date_str}",
          f"## Frontier draw: {c['title']}  [{c['fidelity']}]",
          f"**Science:** {c['science']}",
          f"**Hook:** {c['hook']}",
          f"**Ruling metaphor:** {c['metaphor']}",
          f"**The turn:** {c['turn']}",
          f"**Invitation (hand this to the viewer):** {c['invitation']}",
        ]
        if c.get("note"): body.append(f"**Note:** {c['note']}")
    else:
        a,b=rng.sample(pillars,2)
        sig=rng.choice(sigs)
        body=[
          f"# Concept Brief — {date_str}",
          f"## Cross-pollination: {a['label']}  ×  {b['label']}",
          f"**A ({a['id']}):** {a['essence']}",
          f"**B ({b['id']}):** {b['essence']}",
          f"**Prompt:** Write a script where {a['label'].lower()} is explained THROUGH {b['label'].lower()} — one ruling metaphor, held all the way.",
          f"**Structural signature to honor:** {sig}",
          f"**Remember the ethos:** end on an invitation, not an instruction; land back in the ordinary.",
        ]
    body+=["", "_Draw one thread. Don't lead the viewer — hand them the test._"]
    return "\n".join(body)

def performance_lead(date_str):
    """If we have realized performance, lead the brief with the data-driven call."""
    try:
        import intelligence
        rows, lanes, n = intelligence.analyze()
        if not rows:
            return ""
        return "## Today's data-driven steer\n" + intelligence.recommend() + "\n\n"
    except Exception:
        return ""


def main():
    date_str=sys.argv[1] if len(sys.argv)>1 else datetime.date.today().isoformat()
    text=performance_lead(date_str) + brief(date_str)
    print(text)
    log=os.path.join(HERE,"BRIEF_LOG.md")
    with open(log,"a") as f: f.write(text+"\n\n---\n\n")

if __name__=="__main__":
    main()
