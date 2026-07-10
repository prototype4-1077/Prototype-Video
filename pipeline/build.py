"""One-command build orchestrator. Run repeatedly until it prints DONE.

    python3 build.py <build_dir>

Each run loads API keys from .env itself, checks fonts, validates script.json,
then advances the build as far as it can within a ~30s budget and exits with:
    RUN AGAIN  (progress note)      -> just run the same command again
    DONE -> <build_dir>/final.mp4   -> finished
    ERROR: <what> | FIX: <how>      -> fix, then run again
Every step is resumable; running again never breaks anything."""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request

T0 = time.time()
BUDGET = 30
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = {
    "Questrial-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/questrial/Questrial-Regular.ttf",
    "Baloo2-ExtraBold.ttf": None,  # instanced from variable font below
    "Baloo2.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/baloo2/Baloo2%5Bwght%5D.ttf",
}


def left(): return BUDGET - (time.time() - T0)


def out(msg): print(msg); sys.exit(0)


def err(what, fix): print(f"ERROR: {what} | FIX: {fix}"); sys.exit(1)


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return r


def load_env():
    envf = os.path.join(HERE, ".env")
    if os.path.exists(envf):
        for line in open(envf):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)
    for k in ("ELEVENLABS_API_KEY", "PEXELS_API_KEY"):
        if not os.environ.get(k):
            err(f"missing {k}", "add it to pipeline/.env")


def ensure_fonts():
    fdir = os.path.join(HERE, "fonts")
    os.makedirs(fdir, exist_ok=True)
    ua = [("User-Agent", "Mozilla/5.0")]
    op = urllib.request.build_opener(); op.addheaders = ua
    urllib.request.install_opener(op)
    for name, url in FONTS.items():
        p = os.path.join(fdir, name)
        if os.path.exists(p) or url is None:
            continue
        try:
            urllib.request.urlretrieve(url, p)
        except Exception as e:
            err(f"font download failed ({name}): {e}",
                "check network egress is 'All domains', then rerun")
    eb = os.path.join(fdir, "Baloo2-ExtraBold.ttf")
    if not os.path.exists(eb):
        r = sh([sys.executable, "-m", "fontTools.varLib.instancer",
                os.path.join(fdir, "Baloo2.ttf"), "wght=800", "-o", eb])
        if r.returncode != 0:  # fonttools missing -> variable font works too (regular weight)
            shutil.copy(os.path.join(fdir, "Baloo2.ttf"), eb)


def validate(bd):
    p = f"{bd}/script.json"
    if not os.path.exists(p):
        err("no script.json", f"write {p} per HANDOFF.md template")
    try:
        s = json.load(open(p))
    except Exception as e:
        err(f"script.json is not valid JSON: {e}", "fix the JSON syntax")
    if not s.get("title") or not s.get("slug"):
        err("script.json missing title/slug", "add them")
    sc = s.get("scenes") or []
    user_vo = os.path.exists(f"{bd}/vo.mp3") and not any(x.get("start") is not None for x in sc[:1]) \
              or s.get("user_vo")
    soft = err if not (os.path.exists(f"{bd}/vo.mp3") or s.get("user_vo")) else (
        lambda what, fix: print(f"note: {what} ({fix}) - allowed, VO is user-provided"))
    if not 14 <= len(sc) <= 30:
        soft(f"{len(sc)} scenes", "aim for 18-26 scenes (one sentence/beat each)")
    words = sum(len(x.get("text", "").split()) for x in sc)
    if not 250 <= words <= 450:
        soft(f"script is {words} words", "aim for 300-400 words total")
    for i, x in enumerate(sc):
        if not x.get("text"):
            err(f"scene {i} has no text", "every scene needs a 'text' sentence")
        if len(x["text"]) > 220:
            err(f"scene {i} text too long ({len(x['text'])} chars)", "split it into two scenes")
        low = x["text"].lower()
        for k in x.get("keywords", []):
            if k.lower().split()[0] not in low:
                print(f"note: scene {i} keyword '{k}' not found in text (won't highlight)")
    return s


def probe_ok(f):
    return sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", f]).returncode == 0


def main(bd):
    bd = bd.rstrip("/")
    load_env()
    ensure_fonts()
    s = validate(bd)
    n = len(s["scenes"])
    py = sys.executable

    # 1. voiceover (generate) or align (user-provided vo.mp3 without timings)
    if not os.path.exists(f"{bd}/vo.mp3"):
        r = sh([py, os.path.join(HERE, "tts.py"), bd])
        if r.returncode != 0:
            err(f"tts failed: {r.stderr[-300:]}", "check ELEVENLABS_API_KEY / credits, rerun")
        out(f"RUN AGAIN (voiceover done, {n} scenes timed)")
    # 1b. local word-level transcription (word-synced captions), if faster-whisper exists
    need_words = not os.path.exists(f"{bd}/words.json") and not os.path.exists(f"{bd}/final.mp4")
    if need_words:
        try:
            import faster_whisper  # noqa
            while not os.path.exists(f"{bd}/words.json"):
                if left() < 12:
                    out("RUN AGAIN (transcribing VO for word-synced captions)")
                r = sh([py, os.path.join(HERE, "transcribe.py"), bd])
                if r.returncode != 0:
                    print(f"note: transcription failed ({r.stderr[-160:]}); captions will be static")
                    break
            # re-time scenes with word-level data
            for x in s["scenes"]:
                x.pop("duration", None)
            json.dump(s, open(f"{bd}/script.json", "w"), indent=1, ensure_ascii=False)
        except ImportError:
            print("note: faster-whisper not installed; captions will be static-highlight")

    if any(x.get("duration") is None for x in s["scenes"]):
        r = sh([py, os.path.join(HERE, "align.py"), bd])
        if r.returncode != 0:
            err(f"align failed: {r.stderr[-300:]}", "rerun; fallback timing needs only ffprobe")
        print(r.stdout.strip())
        out(f"RUN AGAIN (user VO aligned to {n} scenes)")

    s = json.load(open(f"{bd}/script.json"))

    # 2. footage (scene by scene, resumable)
    missing = [i for i in range(n)
               if not (os.path.exists(f"{bd}/clip_{i:02d}.mp4")
                       and os.path.getsize(f"{bd}/clip_{i:02d}.mp4") > 100_000)]
    for i in missing:
        if left() < 12:
            out(f"RUN AGAIN (footage {n - len([j for j in missing if j >= i])}/{n})")
        r = sh([py, os.path.join(HERE, "footage.py"), bd, str(i)])
        if r.returncode != 0:
            err(f"footage scene {i}: {r.stderr[-300:]}",
                f"edit scene {i} query in script.json, rerun")
    if missing:
        out(f"RUN AGAIN (footage complete {n}/{n})")

    # 3. overlays + music
    if not os.path.exists(f"{bd}/cap_{n-1:02d}.png") or not os.path.exists(f"{bd}/title.png"):
        if left() < 15: out("RUN AGAIN (next: overlays)")
        r = sh([py, os.path.join(HERE, "prep.py"), bd])
        if r.returncode != 0:
            err(f"prep failed: {r.stderr[-300:]}", "rerun; if fonts missing delete fonts/ and rerun")
        out("RUN AGAIN (captions + title + music ready)")

    # 4. render segments
    for i in range(n):
        seg = f"{bd}/seg_{i:02d}.mp4"
        if os.path.exists(seg):
            continue
        if left() < 12:
            out(f"RUN AGAIN (rendered {i}/{n} scenes)")
        r = sh([py, os.path.join(HERE, "assemble.py"), bd, "scene", str(i)])
        if r.returncode != 0:
            err(f"render scene {i}: {r.stderr[-300:]}", "rerun; if it repeats, delete that seg file")

    # 4b. verify segments (catch truncated files from timeouts)
    for i in range(n):
        seg = f"{bd}/seg_{i:02d}.mp4"
        if not probe_ok(seg):
            try:
                os.remove(seg)
                out(f"RUN AGAIN (seg {i} was corrupt, will re-render)")
            except OSError:
                err(f"seg {i} corrupt and undeletable", "enable file deletion, delete it, rerun")

    # 5. concat + audio mix (fast temp disk, then copy to build dir)
    final = f"{bd}/final.mp4"
    if not (os.path.exists(final) and probe_ok(final)):
        if left() < 20: out("RUN AGAIN (next: final assembly)")
        tmp = tempfile.mkdtemp()
        lst = os.path.join(tmp, "list.txt")
        with open(lst, "w") as f:
            for i in range(n):
                f.write(f"file '{os.path.abspath(bd)}/seg_{i:02d}.mp4'\n")
        noa = os.path.join(tmp, "noaudio.mp4")
        r = sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                "-i", lst, "-c", "copy", noa])
        if r.returncode != 0: err(f"concat: {r.stderr[-300:]}", "rerun")
        total = sum(x["duration"] for x in s["scenes"])
        music = s.get("music", "music.wav")
        af = ("[1:a]acompressor=threshold=-18dB:ratio=3:attack=15:release=180:makeup=4,"
              "adelay=400|400,apad[voz];"
              f"[2:a]volume=0.16,afade=t=out:st={total-3}:d=3[mz];"
              "[voz][mz]amix=inputs=2:duration=first:dropout_transition=0[a]")
        raw = os.path.join(tmp, "raw.mp4")
        r = sh(["ffmpeg", "-v", "error", "-y", "-i", noa, "-i", f"{bd}/vo.mp3",
                "-i", f"{bd}/{music}", "-filter_complex", af, "-map", "0:v", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(total), raw])
        if r.returncode != 0: err(f"audio mix: {r.stderr[-300:]}", "rerun")
        # two-pass loudness master to -14 LUFS (TikTok reference level)
        r = sh(["ffmpeg", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                "-f", "null", "-"])
        fin = os.path.join(tmp, "final.mp4")
        try:
            meas = json.loads("{" + r.stderr.rsplit("{", 1)[1])
            gain = round(-14.0 - float(meas["input_i"]) + 1.5, 2)  # +1.5 offsets limiter loss
            ln = (f"volume={gain}dB,"
                  "alimiter=limit=0.79:attack=2:release=80:level=false")  # ~-14.5 LUFS, TP ~-1dB
        except Exception:
            ln = "loudnorm=I=-14:TP=-1.5:LRA=11"
        r = sh(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", ln, "-map", "0:v", "-map", "0:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", fin])
        if r.returncode != 0: err(f"loudness master: {r.stderr[-300:]}", "rerun")
        shutil.copy(fin, final)
        shutil.rmtree(tmp, ignore_errors=True)
    if not probe_ok(final):
        try: os.remove(final)
        except OSError: pass
        out("RUN AGAIN (final was incomplete, will redo)")
    print(f"DONE -> {final}")
    print(f"After James approves: python3 {os.path.join(HERE, 'learn.py')} record {bd}")
    print(f"If he dislikes scene i's footage: python3 {os.path.join(HERE, 'learn.py')} swap {bd} <i>")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        err("no build dir given", "run: python3 build.py build/<slug>")
    main(sys.argv[1])
