"""Generate caption + title overlay PNGs and (if missing) synth music bed.
Usage: python3 prep.py <build_dir>"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captions import caption_png, title_png


def prep(bd):
    s = json.load(open(f"{bd}/script.json"))
    for i, sc in enumerate(s["scenes"]):
        if sc.get("kw_times"):  # word-synced: keywords ignite when spoken
            ovs = caption_png(sc["text"], sc.get("keywords", []), f"{bd}/cap_{i:02d}.png",
                              kw_overlay_prefix=f"{bd}/cap_{i:02d}_kw")
            sc["kw_overlays"] = [{"kw": k, "png": os.path.basename(p)} for k, p in ovs]
        else:
            caption_png(sc["text"], sc.get("keywords", []), f"{bd}/cap_{i:02d}.png")
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1, ensure_ascii=False)
    title_png(s["title"], f"{bd}/title.png")
    if not s.get("music") or not os.path.exists(os.path.join(bd, s["music"])):
        s.pop("music", None)
        total = sum(sc.get("duration", 8) for sc in s["scenes"])
        subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "music.py"), f"{bd}/music.wav", str(total + 2)] +
                       ([f"{bd}/vo.mp3"] if os.path.exists(f"{bd}/vo.mp3") else ["-"]) +
                       ([s["genre"]] if s.get("genre") else []), check=True)
        s["music"] = "music.wav"
        json.dump(s, open(f"{bd}/script.json", "w"), indent=1)
        try:  # sound design: sub-drops, whooshes, riser baked into the bed
            subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "sfx.py"), bd], check=True)
        except Exception as e:
            print(f"note: sfx skipped ({e})")
    print(f"prep done: {len(s['scenes'])} captions + title + music")


if __name__ == "__main__":
    prep(sys.argv[1])
