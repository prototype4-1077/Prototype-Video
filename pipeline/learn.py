"""The pipeline's memory. Makes every video improve the next one.
memory.json lives next to this file and persists across videos (keep it in the zip!).

Commands:
  python3 learn.py record <build_dir>          # after James approves a final video:
                                               #   remembers used clips (never reused),
                                               #   bumps weights of queries that survived
  python3 learn.py swap <build_dir> <scene_i>  # James dislikes a scene's footage:
                                               #   bans that clip forever, penalizes its query,
                                               #   clears clip+seg so the next build.py run redoes it
  python3 learn.py note "free-text feedback"   # store James's feedback for future scriptwriters
  python3 learn.py show                        # print memory summary
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MEM = os.path.join(HERE, "memory.json")


def load():
    if os.path.exists(MEM):
        return json.load(open(MEM))
    return {"used_ids": [], "banned_ids": [], "query_weights": {},
            "notes": [], "videos": []}


def save(m):
    json.dump(m, open(MEM, "w"), indent=1)


def record(bd):
    m = load()
    s = json.load(open(f"{bd}/script.json"))
    kept = []
    for sc in s["scenes"]:
        pid = sc.get("pexels_id")
        if pid:
            kept.append(pid)
            if pid not in m["used_ids"]:
                m["used_ids"].append(pid)
        q = (sc.get("query") or "").strip().lower()
        if q:
            m["query_weights"][q] = m["query_weights"].get(q, 0) + 1
    m["videos"].append({"slug": s.get("slug"), "title": s.get("title"),
                        "scenes": len(s["scenes"]), "clips": kept})
    save(m)
    try:  # taste vector: this video's chosen-clip embeddings become "approved"
        import glob as _g, numpy as _np, taste
        vecs = [_np.load(f) for f in sorted(_g.glob(f"{bd}/emb_*.npy"))]
        if vecs:
            na, nr = taste.add("approved", _np.stack(vecs))
            print(f"taste: +{len(vecs)} approved (now {na} approved / {nr} rejected)")
    except Exception as e:
        print(f"note: taste update skipped ({e})")
    print(f"recorded: {len(kept)} clips remembered, {len(m['videos'])} videos in memory")


def swap(bd, i):
    m = load()
    s = json.load(open(f"{bd}/script.json"))
    sc = s["scenes"][i]
    pid = sc.pop("pexels_id", None)
    if pid and pid not in m["banned_ids"]:
        m["banned_ids"].append(pid)
    q = (sc.get("query") or "").strip().lower()
    if q:
        m["query_weights"][q] = m["query_weights"].get(q, 0) - 2
    sc.pop("clip", None)
    try:  # the rejected clip's embedding teaches the taste vector what to avoid
        import numpy as _np, taste
        ef = f"{bd}/emb_{i:02d}.npy"
        if os.path.exists(ef):
            taste.add("rejected", _np.load(ef)[None])
            print("taste: +1 rejected")
    except Exception:
        pass
    for f in (f"{bd}/clip_{i:02d}.mp4", f"{bd}/seg_{i:02d}.mp4", f"{bd}/final.mp4"):
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: print(f"note: could not delete {f} (enable deletion), delete manually")
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1)
    save(m)
    print(f"scene {i}: clip banned. Improve its 'query' in script.json if you can, then rerun build.py")


def motif(slug, name, line):
    m = load()
    m.setdefault("motifs", []).append({"video": slug, "name": name, "line": line})
    save(m)
    print(f"motif saved ({len(m['motifs'])}). Scripts should echo ONE earlier motif per video.")


def retention(bd, stamps):
    """Map retention drop-off timestamps (from James's TikTok analytics) to scenes."""
    m = load()
    s = json.load(open(f"{bd}/script.json"))
    lessons = []
    for t in stamps:
        t = float(t)
        for i, sc in enumerate(s["scenes"]):
            if sc["start"] <= t < sc["start"] + sc["duration"]:
                lessons.append(f"scene {i} ({sc['duration']:.0f}s, '{sc['text'][:60]}...') loses viewers at {t:.0f}s")
                break
    entry = f"retention({s.get('slug')}): " + "; ".join(lessons)
    m["notes"].append(entry)
    save(m)
    print(entry)
    print("Recorded. Future scripts should shorten/energize beats like these.")


def pin(bd, i, vid):
    """Pin scene i to a specific clip id (from alts.json or manual curation)."""
    s = json.load(open(f"{bd}/script.json"))
    sc = s["scenes"][i]
    sc["pexels_id"] = int(vid) if str(vid).isdigit() else str(vid)
    sc.pop("clip", None)
    for f in (f"{bd}/clip_{i:02d}.mp4", f"{bd}/seg_{i:02d}.mp4", f"{bd}/final.mp4",
              f"{bd}/final_short.mp4"):
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1)
    print(f"scene {i} pinned to {sc['pexels_id']}. Rerun build.py (or re-dispatch) to render.")


def note(text):
    m = load()
    m["notes"].append(text)
    save(m)
    print(f"noted ({len(m['notes'])} notes). Future scriptwriters read these.")


def show():
    m = load()
    print(f"videos made: {len(m['videos'])} -> {[v['slug'] for v in m['videos']]}")
    print(f"clips remembered (won't reuse): {len(m['used_ids'])}, banned: {len(m['banned_ids'])}")
    top = sorted(m["query_weights"].items(), key=lambda kv: -kv[1])[:10]
    print("top queries:", ", ".join(f"{q} ({w:+d})" for q, w in top) or "(none yet)")
    for mo in m.get("motifs", []):
        print(f"motif [{mo['video']}] {mo['name']}: \"{mo['line']}\"")
    print("James's notes:")
    for n in m["notes"] or ["(none yet)"]:
        print(f"  - {n}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "record": record(sys.argv[2])
    elif cmd == "swap": swap(sys.argv[2], int(sys.argv[3]))
    elif cmd == "note": note(sys.argv[2])
    elif cmd == "pin": pin(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif cmd == "motif": motif(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "retention": retention(sys.argv[2], sys.argv[3].split(","))
    else: show()
