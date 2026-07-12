"""Pexels stock clip search + download, auto-vetted for the mystical/eerie look.
Usage: python3 footage.py <build_dir> [scene_index]   (no index = all missing)
Env: PEXELS_API_KEY. Reads scene["query"], writes clip_XX.mp4, sets scene["clip"].

No human/AI judgment needed: every candidate's preview thumbnail is scored for
mood (dark, not garish) and the best one wins. Bad/empty queries fall back to
a curated MYSTICAL bank, so any query still yields on-style footage."""
import io, json, os, random, sys, urllib.request, urllib.parse

import profiles

KEY = os.environ["PEXELS_API_KEY"]
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
_op = urllib.request.build_opener()
_op.addheaders = [("User-Agent", UA)]
urllib.request.install_opener(_op)

MEM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
def memory():
    try: return json.load(open(MEM))
    except Exception: return {"used_ids": [], "banned_ids": [], "query_weights": {}}

DMT = [  # genre "dmt": vivid first-person visionary imagery (saturation is GOOD here)
    "kaleidoscope pattern animation", "fractal zoom psychedelic", "colorful nebula space",
    "plasma light abstract", "ink in water rainbow colors", "neon light tunnel abstract",
    "sacred geometry animation", "aurora borealis vivid night", "liquid light abstract macro",
    "mandala pattern colorful", "prism light refraction rainbow", "glowing jellyfish deep sea",
    "bioluminescence ocean night", "crystal macro colorful light", "smoke colorful backlit",
    "particle explosion colorful slow motion", "galaxy stars colorful timelapse",
]

MYSTICAL = [
    "surreal fog silhouette", "nebula space stars", "underwater sun rays dark",
    "silhouette tunnel light end", "fog city aerial dark", "smoke swirl black background",
    "light rays forest fog", "ink drop water black", "stars time lapse night sky",
    "eclipse moon dark clouds", "person walking fog field", "abstract particles dark",
    "candle flame dark", "ocean night moonlight", "desert lone figure dusk",
    "spiral galaxy animation", "light through door dark room", "clouds time lapse storm dark",
    "mirror reflection surreal", "glowing orb dark", "shadow figure hallway",
    "aurora night sky", "deep space travel", "rain window night bokeh",
]


def api(url):
    req = urllib.request.Request(url, headers={"Authorization": KEY, "User-Agent": UA})
    return json.load(urllib.request.urlopen(req, timeout=60))


def get_thumb(video, w=224):
    from PIL import Image
    u = video["image"].split("?")[0] + f"?auto=compress&w={w}"
    return Image.open(io.BytesIO(urllib.request.urlopen(u, timeout=20).read())).convert("RGB")


def mood_score(video, im=None, need=None, genre=None, profile=None):
    """Score a candidate thumbnail. Default: lit-but-moody, muted.
    genre="dmt": vivid saturated visionary imagery wins instead."""
    try:
        from PIL import ImageStat
        if im is None:
            im = get_thumb(video, 120)
        st = ImageStat.Stat(im)
        means = st.mean
        luma = sum(a * b for a, b in zip(means, (0.299, 0.587, 0.114)))
        sat = ImageStat.Stat(im.convert("HSV")).mean[1]
    except Exception:
        return 0.0
    score = 100.0
    if profile == profiles.JUNE_OXLEY:
        # June's world is readable, warm, and ordinary. A few strange shots are welcome,
        # but the profile must never drift back into a reel of near-black mysticism.
        if luma < 55: score -= (55 - luma) * 1.7
        if luma < 24: score -= (24 - luma) * 3.0
        if luma > 185: score -= (luma - 185) * 1.1
        if sat > 160: score -= (sat - 160) * .55
        warmth = means[0] - means[2]
        score += max(-5.0, min(8.0, warmth * .18))
    elif genre == "dmt":  # psychedelic mode: reward vivid color, allow deep blacks behind it
        if sat < 70: score -= (70 - sat) * 0.8      # too muted for a vision
        if luma > 170: score -= (luma - 170) * 1.0  # blown out
        if luma < 8: score -= (8 - luma) * 4        # pure black
    else:
        if luma > 140: score -= (luma - 140) * 1.2      # too bright = off-style
        elif luma > 115: score -= (luma - 115) * 0.4
        if luma < 45: score -= (45 - luma) * 1.0        # too dark: James wants visible lighting
        if luma < 15: score -= (15 - luma) * 3          # near-black = nothing to see
        if sat > 120: score -= (sat - 120) * 0.8        # garish colors
    d = video["duration"]
    if need:  # scene length known: clip must cover it without restarting
        if d < need: score -= (need - d) * 4
        else: score -= min((d - need) * 0.2, 10)
    else:
        score -= abs(d - 10) * 0.5
        if d < 5: score -= 25
    return score


def bank_pick(m, genre=None, profile=None):
    """Prefer bank queries with the best track record (learned weights)."""
    w = (m.get("profile_query_weights", {}).get(profile, {}) if profile
         else m.get("query_weights", {}))
    bank = profiles.fallback_queries(profile, genre) or (DMT if genre == "dmt" else MYSTICAL)
    pool = sorted(bank, key=lambda q: w.get(q, 0), reverse=True)
    k = max(3, len(pool) // 3)
    return random.choice(pool[:k])


def rank(query, vids, need=None, genre=None, profile=None):
    """Rank candidates: mood (dark/muted) blended with CLIP semantic match if available."""
    thumbs = []
    for v in vids:
        try:
            thumbs.append(get_thumb(v))
        except Exception:
            thumbs.append(None)
    moods = [mood_score(v, im, need, genre, profile) if im is not None else 0.0
             for v, im in zip(vids, thumbs)]
    sems, embs_lut = None, {}
    try:
        import semantic
        semantic_q = profiles.semantic_query(query, profile)
        if semantic_q and semantic.available():
            ok = [(v, im) for v, im in zip(vids, thumbs) if im is not None]
            if ok:
                ss, embs = semantic.scores_and_embs(semantic_q, [im for _, im in ok])
                lut = {id(v): s for (v, _), s in zip(ok, ss)}
                embs_lut = {id(v): e for (v, _), e in zip(ok, embs)}
                sems = [lut.get(id(v), 0.0) for v in vids]
    except Exception:
        sems = None
    if sems is not None:
        try:  # learned taste vector: similarity to James's approved aesthetic
            import taste
            if taste.ready(profile):
                ts = {vid_id: t for vid_id, t in
                      zip(embs_lut.keys(), taste.score(list(embs_lut.values()), profile))}
                total = [0.38 * mo + 0.47 * se + 0.15 * ts.get(id(v), 50.0)
                         for mo, se, v in zip(moods, sems, vids)]
            else:
                total = [0.42 * mo + 0.58 * se for mo, se in zip(moods, sems)]
        except Exception:
            total = [0.42 * mo + 0.58 * se for mo, se in zip(moods, sems)]
    else:
        total = moods
    return sorted(zip(total, vids, thumbs,
                      [embs_lut.get(id(v)) for v in vids]), key=lambda t: -t[0])


def search(q, genre=None, profile=None, per_page=15):
    try:
        import sources
        extra = sources.supplement(q, genre)
    except Exception:
        extra = []
    found = list(extra)
    for variant in profiles.query_variants(q, profile) or [q]:
        qq = urllib.parse.quote(variant)
        res = api(f"https://api.pexels.com/videos/search?query={qq}&per_page={per_page}"
                  "&orientation=landscape")
        found.extend(res.get("videos") or [])
    # Styled and literal searches can return the same clip. Keep its first occurrence.
    out, seen = [], set()
    for video in found:
        if video.get("id") in seen:
            continue
        seen.add(video.get("id")); out.append(video)
    return out


def pick_file(video):
    cands = [f for f in video["video_files"]
             if (f.get("width") or 0) >= 1080]
    if not cands:
        cands = sorted(video["video_files"], key=lambda f: -(f.get("width") or 0))[:1]
    return sorted(cands, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0))[0]


def save_alts(bd, i, chosen, scored):
    """Persist top runner-up candidates (thumb + id) for one-command pinning later."""
    try:
        os.makedirs(f"{bd}/alts", exist_ok=True)
        p = f"{bd}/alts.json"
        manifest = json.load(open(p)) if os.path.exists(p) else {}
        entries = []
        k = 0
        for sc_score, v, im, _e in scored:
            if v["id"] == chosen["id"] or im is None:
                continue
            safe = str(v["id"]).replace(":", "_")
            im.convert("RGB").save(f"{bd}/alts/{i:02d}_{k}_{safe}.jpg")
            entries.append({"id": v["id"], "score": round(sc_score, 1),
                            "source": v.get("source", "pexels")})
            k += 1
            if k == 3:
                break
        manifest[str(i)] = entries
        json.dump(manifest, open(p, "w"), indent=1)
    except Exception:
        pass


def fetch_scene(bd, s, i, used_ids):
    m = memory()
    avoid = set(m["used_ids"]) | set(m["banned_ids"]) | used_ids
    sc = s["scenes"][i]
    out = f"{bd}/clip_{i:02d}.mp4"
    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        sc["clip"] = out
        return
    if sc.get("pexels_id"):  # reproducible re-runs: fetch the exact clip already chosen
        try:
            pid = sc["pexels_id"]
            if isinstance(pid, str) and ":" in pid:
                import sources
                v = sources.fetch_by_id(pid)
            else:
                v = api(f"https://api.pexels.com/videos/videos/{pid}")
            f = pick_file(v)
            urllib.request.urlretrieve(f["link"], out + ".part")
            os.replace(out + ".part", out)
            sc["clip"] = out
            print(f"scene {i}: re-fetched {sc['pexels_id']}")
            return
        except Exception as e:
            print(f"scene {i}: re-fetch failed ({e}); searching fresh")
    genre = s.get("genre")
    profile = profiles.resolve(s)
    vids = search(sc.get("query") or bank_pick(m, genre, profile), genre, profile)
    vids = [v for v in vids if v["id"] not in avoid]
    if not vids:
        vids = [v for v in search(bank_pick(m, genre, profile), genre, profile)
                if v["id"] not in avoid]
    if not vids:
        sys.exit(f"ERROR scene {i}: no results; edit its query in script.json and rerun")
    scored = rank(sc.get("query", ""), vids, sc.get("duration"), genre, profile)
    best, v, _, emb = scored[0]
    if best < 20 and sc.get("query"):  # everything off-style -> blend in bank term
        alt = [x for x in search(bank_pick(m, genre, profile), genre, profile)
               if x["id"] not in avoid]
        scored2 = rank(sc.get("query", ""), alt, sc.get("duration"), genre, profile) if alt else []
        if scored2 and scored2[0][0] > best:
            best, v, _, emb = scored2[0]
            scored = scored2
    save_alts(bd, i, v, scored)
    if emb is not None:  # feed the taste vector on approval/swap later
        import numpy as _np
        _np.save(f"{bd}/emb_{i:02d}.npy", _np.asarray(emb, _np.float32))
    used_ids.add(v["id"])
    f = pick_file(v)
    urllib.request.urlretrieve(f["link"], out + ".part")
    os.replace(out + ".part", out)  # atomic: a killed run never leaves a truncated clip
    sc["clip"] = out
    sc["pexels_id"] = v["id"]
    print(f"scene {i}: {v.get('source', 'pexels')} {v['id']} ({v['duration']}s, "
          f"score {best:.0f}, profile {profiles.display_name(profile)}) <- "
          f"{sc.get('query','(bank)')}")


def main(bd, idx=None):
    s = json.load(open(f"{bd}/script.json"))
    used = {sc.get("pexels_id") for sc in s["scenes"] if sc.get("pexels_id")}
    targets = [int(idx)] if idx is not None else range(len(s["scenes"]))
    for i in targets:
        fetch_scene(bd, s, i, used)
        json.dump(s, open(f"{bd}/script.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
