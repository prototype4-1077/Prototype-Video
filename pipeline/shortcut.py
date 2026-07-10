"""Auto 60-second cut: a second upload from the same script's strongest beats.
Usage: python3 shortcut.py <build_dir> [target_secs=58]
Requires the full build (segs + vo.mp3). Keeps the hook and the ending, fills the
middle with the punchiest beats (questions, short declaratives), re-cuts the VO at
sentence boundaries, lays a fresh music bed, masters to the same loudness."""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FFMPEG FAIL: {' '.join(map(str, cmd))}\n{r.stderr[-1500:]}")
    return r


def pick(scenes, target):
    def score(i, sc):
        t, n = sc["text"], len(sc["text"].split())
        s = 0.0
        if "?" in t: s += 3
        if n <= 12: s += 2
        if '"' in t or chr(8220) in t: s += 1
        if i < len(scenes) * 0.25: s += 1          # early beats keep the setup clear
        s -= max(0, sc["duration"] - 9) * 0.5      # long scenes cost budget
        return s
    first, last = 0, len(scenes) - 1
    chosen = {first, last}
    budget = target - scenes[first]["duration"] - scenes[last]["duration"]
    ranked = sorted((i for i in range(len(scenes)) if i not in chosen),
                    key=lambda i: -score(i, scenes[i]))
    for i in ranked:
        d = scenes[i]["duration"]
        if d <= budget:
            chosen.add(i)
            budget -= d
    return sorted(chosen)


def main(bd, target=58.0):
    s = json.load(open(f"{bd}/script.json"))
    scenes = s["scenes"]
    if any(not os.path.exists(f"{bd}/seg_{i:02d}.mp4") for i in range(len(scenes))):
        sys.exit("ERROR: segs missing; run build.py to completion first")
    idx = pick(scenes, target)
    total = sum(scenes[i]["duration"] for i in idx)
    tmp = tempfile.mkdtemp()
    # video: concat the chosen segments (dip-to-black edges make these cuts clean)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for i in idx:
            f.write(f"file '{os.path.abspath(bd)}/seg_{i:02d}.mp4'\n")
    noa = os.path.join(tmp, "noa.mp4")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", noa])
    # voiceover: slice at sentence boundaries and rejoin with micro-fades
    parts, fc = [], ""
    for k, i in enumerate(idx):
        st, d = scenes[i]["start"], scenes[i]["duration"]
        fc += (f"[0:a]atrim=start={st}:duration={d},asetpts=PTS-STARTPTS,"
               f"afade=t=in:d=0.04,afade=t=out:st={max(d-0.04,0)}:d=0.04[p{k}];")
        parts.append(f"[p{k}]")
    fc += f"{''.join(parts)}concat=n={len(parts)}:v=0:a=1[vo]"
    vos = os.path.join(tmp, "vo_short.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", f"{bd}/vo.mp3",
         "-filter_complex", fc, "-map", "[vo]", vos])
    # fresh music bed sized to the short cut
    mus = os.path.join(tmp, "music.wav")
    run([sys.executable, os.path.join(HERE, "music.py"), mus, str(total + 1), vos])
    raw = os.path.join(tmp, "raw.mp4")
    af = ("[1:a]acompressor=threshold=-18dB:ratio=3:attack=15:release=180:makeup=4,"
          "adelay=250|250,apad[voz];"
          f"[2:a]volume=0.26,afade=t=out:st={max(total-3,0)}:d=3[mz];"
          "[voz][mz]amix=inputs=2:duration=first:dropout_transition=0[a]")
    run(["ffmpeg", "-v", "error", "-y", "-i", noa, "-i", vos, "-i", mus,
         "-filter_complex", af, "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(total), raw])
    # loudness master (same recipe as build.py)
    r = subprocess.run(["ffmpeg", "-i", raw, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    try:
        meas = json.loads("{" + r.stderr.rsplit("{", 1)[1])
        gain = round(-14.0 - float(meas["input_i"]) + 1.5, 2)
        ln = f"volume={gain}dB,alimiter=limit=0.79:attack=2:release=80:level=false"
    except Exception:
        ln = "loudnorm=I=-14:TP=-1.5:LRA=11"
    run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", ln, "-map", "0:v", "-map", "0:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
         f"{bd}/final_short.mp4"])
    print(f"final_short.mp4 done: {total:.1f}s from {len(idx)}/{len(scenes)} scenes "
          f"(kept: {idx})")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 58.0)
