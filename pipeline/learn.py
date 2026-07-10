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
    for f in (f"{bd}/clip_{i:02d}.mp4", f"{bd}/seg_{i:02d}.mp4", f"{bd}/final.mp4"):
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: print(f"note: could not delete {f} (enable deletion), delete manually")
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1)
    save(m)
    print(f"scene {i}: clip banned. Improve its 'query' in script.json if you can, then rerun build.py")


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
    print("James's notes:")
    for n in m["notes"] or ["(none yet)"]:
        print(f"  - {n}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "record": record(sys.argv[2])
    elif cmd == "swap": swap(sys.argv[2], int(sys.argv[3]))
    elif cmd == "note": note(sys.argv[2])
    else: show()
