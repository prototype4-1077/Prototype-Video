"""Shared helpers for rendering multiple selectable score versions."""
import json
import os
import shutil
import subprocess
import tempfile


MIN_MUSIC_VARIANTS = 3


def entries(script):
    """Return normalized music-variant dictionaries in declared order."""
    raw = script.get("music_variants") or []
    out = []
    for index, item in enumerate(raw, 1):
        if isinstance(item, str):
            item = {"file": item}
        if not isinstance(item, dict) or not item.get("file"):
            continue
        row = dict(item)
        row.setdefault("index", index)
        row.setdefault("label", f"Music Choice {index}")
        out.append(row)
    if not out and script.get("music"):
        out = [{"index": 1, "label": "Music Choice 1", "file": script["music"]}]
    return out


def require(script, build_dir, minimum=MIN_MUSIC_VARIANTS):
    found = entries(script)
    if len(found) < minimum:
        raise ValueError(f"expected at least {minimum} music variants; found {len(found)}")
    missing = [x["file"] for x in found if not os.path.exists(os.path.join(build_dir, x["file"]))]
    if missing:
        raise ValueError("missing music variants: " + ", ".join(missing))
    return found


def video_name(index, short=False):
    prefix = "final_short_music" if short else "final_music"
    return f"{prefix}_{index:02d}.mp4"


def youtube_video_name(index):
    """Return the native 16:9 YouTube filename for a music choice."""
    return f"final_youtube_music_{index:02d}.mp4"


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:] or "ffmpeg failed")
    return r


def mix(noaudio, voiceover, music_path, total, output, delay_ms=400, music_gain=.26):
    """Mix and loudness-master one score choice without re-encoding video."""
    tmp = tempfile.mkdtemp(prefix="music-variant-")
    try:
        raw = os.path.join(tmp, "raw.mp4")
        af = ("[1:a]acompressor=threshold=-18dB:ratio=3:attack=15:release=180:makeup=4,"
              f"adelay={delay_ms}|{delay_ms},apad[voz];"
              f"[2:a]volume={music_gain},afade=t=out:st={max(total-3, 0)}:d=3[mz];"
              "[voz][mz]amix=inputs=2:duration=first:dropout_transition=0[a]")
        _run(["ffmpeg", "-v", "error", "-y", "-i", noaudio, "-i", voiceover,
              "-i", music_path, "-filter_complex", af, "-map", "0:v", "-map", "[a]",
              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", str(total), raw])
        measured = subprocess.run(
            ["ffmpeg", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
             "-f", "null", "-"], capture_output=True, text=True)
        try:
            values = json.loads("{" + measured.stderr.rsplit("{", 1)[1])
            gain = round(-14.0 - float(values["input_i"]) + 1.5, 2)
            master = f"volume={gain}dB,alimiter=limit=0.79:attack=2:release=80:level=false"
        except Exception:
            master = "loudnorm=I=-14:TP=-1.5:LRA=11"
        final_tmp = os.path.join(tmp, "final.mp4")
        _run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", master,
              "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-c:a", "aac",
              "-b:a", "160k", "-movflags", "+faststart", final_tmp])
        shutil.copy(final_tmp, output)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def write_manifest(build_dir, variants, default_index=1):
    data = {
        "minimum_choices": MIN_MUSIC_VARIANTS,
        "default_index": default_index,
        "variants": [
            {**item, "video": video_name(i), "youtube_video": youtube_video_name(i)}
            for i, item in enumerate(variants, 1)
        ],
    }
    with open(os.path.join(build_dir, "music_variants.json"), "w") as f:
        json.dump(data, f, indent=2)
    return data
