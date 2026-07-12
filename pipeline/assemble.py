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

import profiles

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
    with open(f"{bd}/script.json") as f:
        s = json.load(f)
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
    title = f"{bd}/title.png" if i == 0 and os.path.exists(f"{bd}/title.png") else None
    # geometry: letterbox 16:9 band on black 9:16 canvas (default) or fullbleed crop
    if s.get("layout") == "fullbleed":
        BW, BH, padf = WIDTH, HEIGHT, ""
    else:
        BW, BH, BY = 1080, 608, 656
        padf = f",pad={WIDTH}:{HEIGHT}:0:{BY}:black"
    geom = f"scale={BW}:{BH}:force_original_aspect_ratio=increase,crop={BW}:{BH}"
    # cinematic cohesion: a narration-controlled color arc. Museum mode begins
    # cold/uncanny, keeps blacks readable, then opens into warm gold at acceptance.
    mode = s.get("visual_mode")
    profile = profiles.resolve(s)
    tone = sc.get("tone", "cold")
    if profile == profiles.JUNE_OXLEY:
        # Warm, readable documentary color: weathered rather than glossy, with enough
        # daylight to preserve the reference video's everyday front-porch character.
        grade = ("eq=brightness=0.036:saturation=0.96:contrast=1.025:gamma=1.055,"
                 "colorbalance=rs=0.018:bs=-0.028:rh=0.075:bh=-0.055,"
                 "curves=all='0/0.045 0.5/0.525 1/0.985',"
                 "vignette=angle=PI/8.5")
        grain = 3
    elif mode == "eerie_museum":
        grades = {
            "cold": ("eq=brightness=0.018:saturation=0.76:contrast=1.10:gamma=1.04,"
                     "colorbalance=rs=-0.07:bs=0.11:rh=0.035:bh=-0.035,"),
            "neutral": ("eq=brightness=0.026:saturation=0.80:contrast=1.08:gamma=1.04,"
                        "colorbalance=rs=-0.045:bs=0.075:rh=0.05:bh=-0.045,"),
            "warm": ("eq=brightness=0.038:saturation=0.86:contrast=1.07:gamma=1.05,"
                     "colorbalance=rs=-0.02:bs=0.045:rh=0.09:bh=-0.07,"),
            "gold": ("eq=brightness=0.055:saturation=0.94:contrast=1.06:gamma=1.06,"
                     "colorbalance=rs=0.00:bs=0.02:rh=0.14:bh=-0.10,"),
        }
        grade = (grades.get(tone, grades["cold"]) +
                 "curves=all='0/0.045 0.48/0.515 1/0.985',vignette=angle=PI/7.5")
        grain = 3
    else:
        grade = ("eq=saturation=0.88:contrast=1.05,"
                 "colorbalance=rs=-0.04:bs=0.06:rh=0.05:bh=-0.05,"
                 "curves=all='0/0.035 0.5/0.51 1/0.975',"
                 "vignette=angle=PI/6.5")
        grain = 5
    # camera motion varies per scene: zoom-in, zoom-out, or lateral drift
    frames = max(int(dur * FPS), 1)
    mv = {"push": 0, "pull": 1, "drift": 2}.get(sc.get("motion"), i % 3)
    if mv == 0:   # slow push in
        zexpr = "z='min(1.0+0.0009*on,1.13)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif mv == 1:  # slow pull out
        zexpr = "z='max(1.13-0.0009*on,1.0)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    else:          # lateral drift at light zoom
        zexpr = (f"z=1.08:x='(iw-iw/zoom)*on/{frames}':y='ih/2-(ih/zoom/2)'")
    zoom = (f"fps={FPS},zoompan={zexpr}:d=1:s={BW}x{BH}:fps={FPS},{grade}{padf},"
            f"noise=alls={grain}:allf=t+u")
    # timing: never restart/loop the clip mid-scene. If the clip is shorter than the
    # scene, stretch it (slow motion) or boomerang it (forward+reverse, seamless).
    cd = clip_duration(sc["clip"]) or dur
    f = dur / max(cd, 0.1)
    # The Pexels cover image often comes from inside a clip. For a long source,
    # begin slightly into it so the chosen semantic moment appears immediately.
    offset = 0.0
    if sc.get("trim_start") is not None:
        offset = max(float(sc["trim_start"]), 0.0)
    elif mode == "eerie_museum" and cd > dur + 1.5:
        offset = min(max((cd - dur) * 0.35, 0.0), 3.0)
    inputs = (["-ss", f"{offset:.3f}"] if offset else []) + ["-i", sc["clip"]]
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
    if title:
        j = len(overlays) + 1
        inputs += ["-loop", "1", "-t", str(dur), "-i", title]
        # Scene 0 doubles as the social thumbnail: show its title from frame one.
        # Later scene behavior is unchanged; only the opening skips the fade-in.
        title_fade = ("format=rgba," if i == 0 else
                      "format=rgba,fade=t=in:st=0.3:d=0.8:alpha=1,")
        fc += (f";[{j}:v]{title_fade}"
               f"fade=t=out:st={max(dur-0.7, 1.2):.2f}:d=0.6:alpha=1[tf]"
               f";[{last}][tf]overlay=0:0[vt]")
        last = "vt"
    # dip-to-black at scene edges: soft filmic cuts instead of hard jumps
    # Do not fade scene 0 in: the first encoded frame must contain the opening
    # picture and title so platforms cannot generate a blank thumbnail.
    if mode == "eerie_museum":
        # Clean editorial cuts preserve visible detail and avoid a black flash
        # every few seconds. The narration itself supplies the scene boundary.
        fc += f";[{last}]null[vf]"
        last = "vf"
    else:
        edge_fade = ("" if i == 0 else "fade=t=in:st=0:d=0.14,")
        fc += (f";[{last}]{edge_fade}"
               f"fade=t=out:st={max(dur-0.14, 0):.2f}:d=0.14[vf]")
        last = "vf"
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
