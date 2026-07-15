"""ElevenLabs TTS with character timestamps -> per-sentence durations.
Usage: python3 tts.py <build_dir>   (reads script.json, writes vo.mp3 + updates durations)
Env: ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID (default: Daniel - deep calm narration)
Per-video overrides: script.json may include voice_settings and elevenlabs_model."""
import base64, json, os, sys, urllib.request

VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")  # Daniel
KEY = os.environ["ELEVENLABS_API_KEY"]
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")


def tts(bd):
    s = json.load(open(f"{bd}/script.json"))
    full_text = " ".join(sc["text"] for sc in s["scenes"])
    voice_settings = {
        "stability": 0.55,
        "similarity_boost": 0.75,
        "style": 0.35,
        "speed": 0.92,
    }
    voice_settings.update(s.get("voice_settings", {}))
    model = s.get("elevenlabs_model", MODEL)
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps",
        data=json.dumps({
            "text": full_text,
            "model_id": model,
            "voice_settings": voice_settings,
        }).encode(),
        headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    resp = json.load(urllib.request.urlopen(req, timeout=300))
    open(f"{bd}/vo.mp3", "wb").write(base64.b64decode(resp["audio_base64"]))
    al = resp["alignment"]
    chars, starts, ends = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    # map each scene's text span to audio time
    pos = 0
    joined = full_text
    for sc in s["scenes"]:
        i = joined.index(sc["text"], pos)
        j = i + len(sc["text"])
        # find char indices covering [i, j)
        sc["_t0"] = starts[min(i, len(starts) - 1)]
        sc["_t1"] = ends[min(j - 1, len(ends) - 1)]
        pos = j
    # scene duration = gap until next scene starts (keeps VO pauses inside the same shot)
    for k, sc in enumerate(s["scenes"]):
        nxt = s["scenes"][k + 1]["_t0"] if k + 1 < len(s["scenes"]) else sc["_t1"] + 2.0
        sc["start"] = round(sc["_t0"], 3)
        sc["duration"] = round(max(2.0, nxt - sc["_t0"]) + (0.4 if k == 0 else 0), 3)
        del sc["_t0"], sc["_t1"]
    s["voiceover"] = "vo.mp3"
    json.dump(s, open(f"{bd}/script.json", "w"), indent=1)
    total = sum(sc["duration"] for sc in s["scenes"])
    print(f"vo.mp3 written, {len(s['scenes'])} scenes, total {total:.1f}s")


if __name__ == "__main__":
    tts(sys.argv[1])
