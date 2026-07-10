"""Assemble final video from scenes. Resumable: each scene renders to its own segment file.
Usage:
  python3 assemble.py <build_dir> scene <i>   # render one scene segment
  python3 assemble.py <build_dir> concat      # concat segments + mix audio -> final.mp4
build_dir contains script.json:
{ "title": "...", "slug": "...",
  "scenes": [{"text","keywords":[],"clip":"path.mp4","duration":sec,"start":sec}],
  "voiceover": "vo.mp3", "music": "music.wav" }
"""
import json, os, subprocess, sys

FPS = 30
WIDTH, HEIGHT = 1080, 1920


def clip_duration(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", f], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FFMPEG FAIL: {' '.join(cmd)}\n{r.stderr[-2000:]}")


def render_scene(bd, i):
    s = json.load(open(f"{bd}/script.json"))
    sc = s["scenes"][i]
    seg = f"{bd}/seg_{i:02d}.mp4"
    if os.path.exists(seg):
        return print(f"seg {i} exists, skip")
    dur = sc["duration"]
    overlays = [(f"{bd}/cap_{i:02d}.png", None)]
    for ov in sc.get("kw_overlays", []):
        t = sc.get("kw_times", {}).get(ov["kw"])
        rel = max(0.0, round(t - sc["start"], 3)) if t is not None else 0.0
        overlays.append((f"{bd}/{ov['png']}", rel))
    if i == 0 and os.path.exists(f"{bd}/title.png"):
        overlays.append((f"{bd}/title.png", None))
    # geometry: letterbox 16:9 band on black 9:16 canvas (default) or fullbleed crop
    if s.get("layout") == "fullbleed":
        BW, BH, padf = WIDTH, HEIGHT, ""
    else:
        BW, BH, BY = 1080, 608, 656
        padf = f",pad={WIDTH}:{HEIGHT}:0:{BY}:black"
    geom = f"scale={BW}:{BH}:force_original_aspect_ratio=increase,crop={BW}:{BH}"
    zoom = (f"fps={FPS},zoompan=z='min(1.0+0.0009*on,1.13)':x='iw/2-(iw/zoom/2)'"
            f":y='ih/2-(ih/zoom/2)':d=1:s={BW}x{BH}:fps={FPS}{padf}")
    # timing: never restart/loop the clip mid-scene. If the clip is shorter than the
    # scene, stretch it (slow motion) or boomerang it (forward+reverse, seamless).
    cd = clip_duration(sc["clip"]) or dur
    f = dur / max(cd, 0.1)
    inputs = ["-i", sc["clip"]]
    if f <= 1.02:
        fc = f"[0:v]{geom},{zoom}[v0]"
    elif f <= 2.2:  # slow the clip just enough to cover the scene
        fc = f"[0:v]{geom},setpts={f:.4f}*PTS,{zoom}[v0]"
    elif cd <= 12 and f <= 4.4:  # boomerang doubles length, then slow the rest
        f2 = max(dur / (2 * cd), 1.0)
        fc = (f"[0:v]{geom}[fw];[fw]split[fa][fb];[fb]reverse[rv];"
              f"[fa][rv]concat=n=2:v=1:a=0,setpts={f2:.4f}*PTS,{zoom}[v0]")
    else:  # extreme mismatch (rare): loop as last resort
        inputs = ["-stream_loop", "-1", "-i", sc["clip"]]
        fc = f"[0:v]{geom},{zoom}[v0]"
    last = "v0"
    for j, (ov, en) in enumerate(overlays):
        inputs += ["-i", ov]
        opt = f":enable='gte(t,{en})'" if en else ""
        fc += f";[{last}][{j+1}:v]overlay=0:0{opt}[v{j+1}]"
        last = f"v{j+1}"
    run(["ffmpeg", "-v", "error", "-y"] + inputs +
        ["-filter_complex", fc, "-map", f"[{last}]", "-t", str(dur),
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-pix_fmt", "yuv420p", seg])
    print(f"seg {i} done")


def concat(bd):
    s = json.load(open(f"{bd}/script.json"))
    n = len(s["scenes"])
    with open(f"{bd}/list.txt", "w") as f:
        for i in range(n):
            f.write(f"file 'seg_{i:02d}.mp4'\n")
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", f"{bd}/list.txt", "-c", "copy", f"{bd}/video_noaudio.mp4"])
    vo, music = s.get("voiceover"), s.get("music")
    total = sum(sc["duration"] for sc in s["scenes"])
    if vo and music:
        af = ("[1:a]adelay=400|400,apad[voz];"
              "[2:a]volume=0.16,afade=t=out:st=%f:d=3[mz];"
              "[voz][mz]amix=inputs=2:duration=first:dropout_transition=0[a]" % (total - 3))
        run(["ffmpeg", "-v", "error", "-y", "-i", f"{bd}/video_noaudio.mp4",
             "-i", f"{bd}/{vo}", "-i", f"{bd}/{music}",
             "-filter_complex", af, "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", str(total),
             f"{bd}/final.mp4"])
    elif vo:
        run(["ffmpeg", "-v", "error", "-y", "-i", f"{bd}/video_noaudio.mp4",
             "-i", f"{bd}/{vo}", "-map", "0:v", "-map", "1:a", "-af", "adelay=400|400,apad",
             "-c:v", "copy", "-c:a", "aac", "-t", str(total), f"{bd}/final.mp4"])
    else:
        os.replace(f"{bd}/video_noaudio.mp4", f"{bd}/final.mp4")
    print("final.mp4 done")


if __name__ == "__main__":
    bd, cmd = sys.argv[1], sys.argv[2]
    if cmd == "scene":
        render_scene(bd, int(sys.argv[3]))
    elif cmd == "concat":
        concat(bd)
