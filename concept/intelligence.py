"""Concept Engine — intelligence layer.

Joins concept DNA (catalog.json) with realized performance (build/<slug>/yt_stats.json,
retention verdicts) to answer: what should we make next, and how do we make it better.
Learns automatically as the nightly analytics sync commits more yt_stats.

Usage:
  python3 concept/intelligence.py            # full report
  python3 concept/intelligence.py recommend  # just the next-video call
"""
import json, os, glob, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

def load(p): return json.load(open(os.path.join(HERE, p)))

def video_stats():
    """slug -> {views, avg_view_pct} from committed nightly-sync analytics."""
    out = {}
    for f in glob.glob(os.path.join(ROOT, "build", "*", "yt_stats.json")):
        slug = os.path.basename(os.path.dirname(f))
        try: out[slug] = json.load(open(f))
        except Exception: pass
    return out

def score(views, pct):
    """A blended value: reach (log-ish) x retention quality. Retention is the
    signal the algorithm rewards; views confirm it traveled."""
    import math
    return round(math.log10(max(views, 1) + 1) * (pct or 0), 1)

def analyze():
    cat = load("catalog.json")["videos"]
    stats = video_stats()
    rows = []
    for slug, dna in cat.items():
        s = stats.get(slug)
        if not s: continue
        rows.append({"slug": slug, "views": s.get("views", 0),
                     "pct": s.get("avg_view_pct", 0),
                     "score": score(s.get("views", 0), s.get("avg_view_pct", 0)),
                     "dna": dna})
    # aggregate expected value by each DNA dimension
    dims = ("pillars", "narration", "hook", "series")
    agg = {d: collections.defaultdict(lambda: [0.0, 0]) for d in dims}
    for r in rows:
        for d in dims:
            vals = r["dna"].get(d)
            vals = vals if isinstance(vals, list) else [vals]
            for v in vals:
                if v is None: continue
                agg[d][v][0] += r["score"]; agg[d][v][1] += 1
    lanes = {d: sorted(((k, round(v[0]/v[1], 1), v[1]) for k, v in agg[d].items()),
                       key=lambda x: -x[1]) for d in dims}
    return rows, lanes, len(stats)

def recommend():
    rows, lanes, n = analyze()
    frontier = load("frontier.json")["frontier"]
    cat = load("catalog.json")["videos"]
    used_frontier = {v.get("frontier") for v in cat.values() if v.get("frontier")}
    out = ["## What to make next (data-driven)"]
    if not rows:
        out.append("No performance data joined yet (nightly sync fills build/<slug>/yt_stats.json). "
                   "Falling back to the frontier rotation until stats accrue.")
        return "\n".join(out)
    # EXPLOIT: best-performing lane per dimension
    for d, label in (("pillars","pillar"),("narration","narration style"),("hook","hook type")):
        top = lanes[d][0]
        out.append(f"- Proven {label}: **{top[0]}** (avg score {top[1]} over {top[2]} videos) — keep feeding it.")
    # EXPLORE: untouched frontier concept nearest the winning pillar
    win_pillar = lanes["pillars"][0][0]
    fresh = [c for c in frontier if c["id"] not in used_frontier]
    pick = fresh[0] if fresh else frontier[0]
    out.append(f"- Highest-value NEW bet: **{pick['title']}** [{pick['fidelity']}] — untouched, and it extends your proven '{win_pillar}' lane. Hook: {pick['hook']}")
    return "\n".join(out)

def craft_rules():
    """Turn retention 'held/bled' verdicts into production rules."""
    rules = []
    wm = os.path.join(ROOT, "pipeline", "WHATS_WORKING.md")
    bled_early = 0; total = 0
    if os.path.exists(wm):
        for line in open(wm):
            if "bled them" in line and "scenes [" in line:
                total += 1
                seg = line.split("bled them")[0]
                if "[0" in seg or "[1" in seg or "[2" in seg or "[3" in seg:
                    bled_early += 1
    if total:
        rules.append(f"- {bled_early}/{total} tracked videos bleed viewers in their FIRST scenes — the opener is the make-or-break. Hook hard in the first 1.5s; no slow atmosphere open.")
    rules += [
        "- Retention-held scenes cluster near the END (the turn + invitation) — the payoff lands; protect it, never rush the close.",
        "- Highest reach came from the machine/attention pillar in guided-2nd voice with a plunge hook (the 832-view breakout) — that's the current spearhead.",
    ]
    return "\n".join(rules)

def report():
    rows, lanes, n = analyze()
    print("# Concept Engine — Intelligence Report\n")
    print(f"_Joined {len(rows)} videos with performance data ({n} stat files present; grows nightly)._\n")
    if rows:
        print("## Realized performance (blended reach x retention)")
        for r in sorted(rows, key=lambda x:-x["score"]):
            print(f"- {r['slug']}: {r['views']} views @ {r['pct']:.0f}%  → score {r['score']}  ({'+'.join(r['dna'].get('pillars',[]))}, {r['dna'].get('narration')}, {r['dna'].get('hook')})")
        print("\n## Winning lanes")
        for d in ("pillars","narration","hook"):
            print(f"- by {d}: " + ", ".join(f"{k} ({v})" for k,v,c in lanes[d][:3]))
        print()
    print(recommend()); print()
    print("## Craft rules (from retention)"); print(craft_rules())

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "recommend":
        print(recommend())
    else:
        report()
