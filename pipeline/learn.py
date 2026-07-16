"""The pipeline's memory. Makes every video improve the next one.
memory.json lives next to this file and persists across videos (keep it in the zip!).

Commands:
  python3 learn.py record <build_dir>          # after James approves a final video:
                                               #   remembers used clips (never reused),
                                               #   bumps weights of queries that survived
  python3 learn.py swap <build_dir> <scene_i>  # James dislikes a scene's footage:
                                               #   bans that clip forever, penalizes its query,
                                               #   clears clip+seg so the next build.py run redoes it
  python3 learn.py survey <build_dir> <feedback.json>\n                                               # apply per-scene survey learning\n  python3 learn.py note "free-text feedback"   # store James's feedback for future scriptwriters
  python3 learn.py show                        # print memory summary
"""
import glob, hashlib, json, os, sys
from datetime import datetime, timezone

import profiles

HERE = os.path.dirname(os.path.abspath(__file__))
MEM = os.path.join(HERE, "memory.json")


def load():
    if os.path.exists(MEM):
        with open(MEM) as f:
            return json.load(f)
    return {"used_ids": [], "banned_ids": [], "query_weights": {},
            "notes": [], "videos": []}


def save(m):
    with open(MEM, "w") as f:
        json.dump(m, f, indent=1)


def record(bd):
    m = load()
    with open(f"{bd}/script.json") as f:
        s = json.load(f)
    profile = profiles.resolve(s)
    weights = (m.setdefault("profile_query_weights", {}).setdefault(profile, {})
               if profile else m["query_weights"])
    kept = []
    for sc in s["scenes"]:
        pid = sc.get("pexels_id")
        if pid:
            kept.append(pid)
            if pid not in m["used_ids"]:
                m["used_ids"].append(pid)
        q = (sc.get("query") or "").strip().lower()
        if q:
            weights[q] = weights.get(q, 0) + 1
    entry = {"slug": s.get("slug"), "title": s.get("title"),
             "scenes": len(s["scenes"]), "clips": kept}
    if profile:
        entry["profile"] = profile
    m["videos"].append(entry)
    save(m)
    try:  # taste vector: this video's chosen-clip embeddings become "approved"
        import glob as _g, numpy as _np, taste
        vecs = [_np.load(f) for f in sorted(_g.glob(f"{bd}/emb_*.npy"))]
        if vecs:
            na, nr = taste.add("approved", _np.stack(vecs), profile)
            label = profiles.display_name(profile)
            print(f"taste [{label}]: +{len(vecs)} approved "
                  f"(now {na} approved / {nr} rejected)")
    except Exception as e:
        print(f"note: taste update skipped ({e})")
    print(f"recorded: {len(kept)} clips remembered, {len(m['videos'])} videos in memory")


def swap(bd, i):
    m = load()
    with open(f"{bd}/script.json") as f:
        s = json.load(f)
    profile = profiles.resolve(s)
    sc = s["scenes"][i]
    pid = sc.pop("pexels_id", None)
    if pid and pid not in m["banned_ids"]:
        m["banned_ids"].append(pid)
    q = (sc.get("query") or "").strip().lower()
    if q:
        weights = (m.setdefault("profile_query_weights", {}).setdefault(profile, {})
                   if profile else m["query_weights"])
        weights[q] = weights.get(q, 0) - 2
    sc.pop("clip", None)
    try:  # the rejected clip's embedding teaches the taste vector what to avoid
        import numpy as _np, taste
        ef = f"{bd}/emb_{i:02d}.npy"
        if os.path.exists(ef):
            taste.add("rejected", _np.load(ef)[None], profile)
            print(f"taste [{profiles.display_name(profile)}]: +1 rejected")
    except Exception:
        pass
    for f in (f"{bd}/clip_{i:02d}.mp4", f"{bd}/seg_{i:02d}.mp4", f"{bd}/final.mp4"):
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: print(f"note: could not delete {f} (enable deletion), delete manually")
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1)
    save(m)
    print(f"scene {i}: clip banned. Improve its 'query' in script.json if you can, then rerun build.py")



def survey(bd, feedback_file):
    """Apply an exported scene-review survey as durable, idempotent training data."""
    with open(feedback_file, encoding="utf-8") as f:
        feedback = json.load(f)
    with open(f"{bd}/script.json", encoding="utf-8") as f:
        script = json.load(f)
    if feedback.get("slug") and feedback["slug"] != script.get("slug"):
        raise ValueError("feedback slug does not match build directory")

    review_id = hashlib.sha256(
        json.dumps(feedback, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    m = load()
    applied = m.setdefault("scene_review_ids", [])
    if review_id in applied:
        print("scene survey already applied; no memory changes made")
        return

    profile = profiles.resolve(script)
    weights = (m.setdefault("profile_query_weights", {}).setdefault(profile, {})
               if profile else m.setdefault("query_weights", {}))
    scene_feedback = m.setdefault("scene_feedback", [])
    approved_vectors, rejected_vectors = [], []
    approved_ids, revised = [], []
    seen = set()
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    for item in feedback.get("scenes", []):
        decision = str(item.get("decision") or "unreviewed").strip().lower()
        if decision in ("approve", "approved"):
            decision = "approved"
        elif decision in ("revision", "revise", "rejected", "needs_revision"):
            decision = "revise"
        else:
            continue
        index = item.get("scene_index")
        if index is None:
            index = int(item.get("scene_number", 0)) - 1
        index = int(index)
        if index < 0 or index >= len(script["scenes"]) or index in seen:
            raise ValueError(f"invalid or duplicate scene index: {index}")
        seen.add(index)

        scene = script["scenes"][index]
        source_id = scene.get("pexels_id") or scene.get("stock_id")
        query = (scene.get("query") or "").strip().lower()
        comments = str(item.get("comments") or "").strip()
        if decision == "revise" and not comments:
            raise ValueError(f"scene {index + 1} needs a revision comment")

        if decision == "approved":
            if source_id and source_id not in m.setdefault("used_ids", []):
                m["used_ids"].append(source_id)
            if source_id:
                approved_ids.append(source_id)
            if query:
                weights[query] = weights.get(query, 0) + 1
        else:
            if source_id and source_id not in m.setdefault("banned_ids", []):
                m["banned_ids"].append(source_id)
            if query:
                weights[query] = weights.get(query, 0) - 2
            revised.append(index)
            for key in (
                "pexels_id", "stock_id", "clip", "motion_source", "motion_verified",
                "motion_evidence", "stock_frame_url", "stock_frame_url_checked",
                "source_url", "storyboard_generated", "storyboard_version",
            ):
                scene.pop(key, None)

        scene_feedback.append({
            "review_id": review_id,
            "reviewed_at": feedback.get("reviewed_at") or timestamp,
            "slug": script.get("slug"),
            "scene_index": index,
            "scene_number": index + 1,
            "decision": decision,
            "comments": comments,
            "query": scene.get("query"),
            "source_id": source_id,
            "profile": profile,
        })
        if comments:
            m.setdefault("notes", []).append(
                f"survey({script.get('slug')}) scene {index + 1} {decision}: {comments}"
            )

        try:
            import numpy as _np
            emb = f"{bd}/emb_{index:02d}.npy"
            if os.path.exists(emb):
                (approved_vectors if decision == "approved" else rejected_vectors).append(
                    _np.load(emb)
                )
        except Exception:
            pass

    overall = feedback.get("overall") or {}
    overall_decision = str(overall.get("decision") or "unreviewed").lower()
    overall_comments = str(overall.get("comments") or "").strip()
    if overall_comments:
        m.setdefault("notes", []).append(
            f"survey({script.get('slug')}) overall {overall_decision}: {overall_comments}"
        )
    if overall_decision in ("approve", "approved") and not revised:
        videos = m.setdefault("videos", [])
        if not any(v.get("slug") == script.get("slug") for v in videos):
            entry = {
                "slug": script.get("slug"),
                "title": script.get("title"),
                "scenes": len(script["scenes"]),
                "clips": approved_ids,
                "review_source": "scene_survey",
            }
            if profile:
                entry["profile"] = profile
            videos.append(entry)

    try:
        import numpy as _np, taste
        if approved_vectors:
            taste.add("approved", _np.stack(approved_vectors), profile)
        if rejected_vectors:
            taste.add("rejected", _np.stack(rejected_vectors), profile)
    except Exception as error:
        print(f"note: taste update skipped ({error})")

    if revised:
        for index in revised:
            for filename in (
                f"{bd}/clip_{index:02d}.mp4",
                f"{bd}/seg_{index:02d}.mp4",
                f"{bd}/youtube_seg_{index:02d}.mp4",
            ):
                if os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except OSError:
                        print(f"note: could not delete {filename}; delete it manually")
        for pattern in (
            f"{bd}/final*.mp4", f"{bd}/scene-review.html", f"{bd}/scene-review.json"
        ):
            for filename in glob.glob(pattern):
                try:
                    os.remove(filename)
                except OSError:
                    pass

    applied.append(review_id)
    with open(f"{bd}/script.json", "w", encoding="utf-8") as f:
        json.dump(script, f, indent=1)
        f.write("\n")
    with open(f"{bd}/scene-review-feedback.json", "w", encoding="utf-8") as f:
        json.dump(feedback, f, indent=2)
        f.write("\n")
    save(m)
    print(
        f"scene survey applied: {len(seen) - len(revised)} approved, "
        f"{len(revised)} revisions"
    )
    if revised:
        print("Rejected clips were banned and cleared. Update their queries if needed, then rerender.")
    elif overall_decision in ("approve", "approved"):
        print("Video approval recorded from the completed scene survey.")

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
    elif cmd == "survey": survey(sys.argv[2], sys.argv[3])
    elif cmd == "note": note(sys.argv[2])
    elif cmd == "pin": pin(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif cmd == "motif": motif(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "retention": retention(sys.argv[2], sys.argv[3].split(","))
    else: show()
