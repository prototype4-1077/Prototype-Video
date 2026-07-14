"""Generate caption + title overlay PNGs and (if missing) synth music bed.
Usage: python3 prep.py <build_dir>"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from captions import caption_png, title_png
import audio_variants
import music as score
import profiles


def _is_generated_music(name):
    base = os.path.basename(name or "")
    return base == "music.wav" or (base.startswith("music_") and base.endswith(".wav"))


def prepare_music(bd, s):
    """Guarantee at least three selectable score beds and record their labels."""
    total = sum(sc.get("duration", 8) for sc in s["scenes"])
    count = max(audio_variants.MIN_MUSIC_VARIANTS, int(s.get("music_variant_count", 3)))
    profile = profiles.resolve(s)
    variants, seen = [], set()

    # Preserve genuinely custom score files. Generated names from an earlier runner
    # are rebuilt deterministically because WAVs are intentionally not committed.
    declared = s.get("music_variants") or []
    for item in declared:
        if isinstance(item, str):
            item = {"file": item}
        elif isinstance(item, dict):
            item = dict(item)
        else:
            continue
        name = item.get("file")
        if (name and name not in seen and not _is_generated_music(name)
                and os.path.exists(os.path.join(bd, name))):
            variants.append({"file": name, "label": item.get("label", "Custom Score"),
                             "source": "custom"})
            seen.add(name)
    current = s.get("music")
    if (current and current not in seen and not _is_generated_music(current)
            and os.path.exists(os.path.join(bd, current))):
        variants.insert(0, {"file": current, "label": "Custom Score", "source": "custom"})
        seen.add(current)

    generated = []
    while len(variants) < count:
        slot = len(variants) + 1
        # Keep the long-standing first-bed filename so older scripts, tests,
        # and manual tools still find choice 1 without knowing about variants.
        name = "music.wav" if slot == 1 else f"music_{slot:02d}.wav"
        path = os.path.join(bd, name)
        variant = slot
        if not os.path.exists(path):
            subprocess.run([
                sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.py"),
                path, str(total + 2), f"{bd}/vo.mp3" if os.path.exists(f"{bd}/vo.mp3") else "-",
                s.get("genre") or "-", profile or "-", str(variant),
            ], check=True)
        row = {"file": name, "label": score.variant_label(variant, s.get("genre"), profile),
               "source": "generated", "variant": variant}
        variants.append(row)
        generated.append(row)

    s["music_variant_count"] = count
    s["music_variants"] = variants[:count]
    s["music"] = s["music_variants"][0]["file"]
    with open(f"{bd}/script.json", "w") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)

    # Bake identical narrative sound-design cues into every generated choice once.
    for item in generated:
        marker = os.path.join(bd, item["file"] + ".sfx-ok")
        if os.path.exists(marker):
            continue
        try:
            subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "sfx.py"), bd, item["file"]], check=True)
            with open(marker, "w") as f:
                f.write("ok\n")
        except Exception as e:
            print(f"note: sfx skipped for {item['file']} ({e})")
    return s


def prep(bd):
    with open(f"{bd}/script.json") as f:
        s = json.load(f)
    for i, sc in enumerate(s["scenes"]):
        if sc.get("kw_times"):  # word-synced: keywords ignite when spoken
            ovs = caption_png(sc["text"], sc.get("keywords", []), f"{bd}/cap_{i:02d}.png",
                              kw_overlay_prefix=f"{bd}/cap_{i:02d}_kw")
            sc["kw_overlays"] = [{"kw": k, "png": os.path.basename(p)} for k, p in ovs]
        else:
            caption_png(sc["text"], sc.get("keywords", []), f"{bd}/cap_{i:02d}.png")
    with open(f"{bd}/script.json", "w") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    title_png(s["title"], f"{bd}/title.png")
    s = prepare_music(bd, s)
    print(f"prep done: {len(s['scenes'])} captions + title + "
          f"{len(s['music_variants'])} music choices")


if __name__ == "__main__":
    prep(sys.argv[1])
