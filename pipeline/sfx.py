"""Sound design layer (fully synthesized, free). Usage: python3 sfx.py <build_dir>
Reads script.json timings + music.wav, bakes events into the bed:
- sub-drop under the title (scene 0) and under the closing line
- whoosh INTO cuts that follow long contemplative holds (max 6)
- riser swelling into the final scene"""
import json, os, sys, wave
import numpy as np

SR = 44100


def _whoosh(dur=0.9, seed=1):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    spec = np.fft.rfft(rng.standard_normal(n).astype(np.float32))
    fr = np.fft.rfftfreq(n, 1 / SR)
    spec *= np.exp(-((np.log(fr + 1) - np.log(900)) ** 2) / 1.4)
    x = np.fft.irfft(spec, n)[:n].astype(np.float32)
    e = (np.linspace(0, 1, n) ** 2.2) * np.exp(-np.linspace(0, 1, n) * 0.001)
    e[-int(0.06 * SR):] *= np.linspace(1, 0, int(0.06 * SR))       # snap shut at the cut
    return x * e * 0.5


def _subdrop(dur=1.3):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 72 * np.exp(-t * 1.8) + 30
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t / 0.55)).astype(np.float32) * 0.55


def _riser(dur=3.0, seed=2):
    rng = np.random.default_rng(seed)
    n = int(dur * SR); t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * (180 + 420 * (t / dur) ** 2) * t)
    noise = rng.standard_normal(n).astype(np.float32) * 0.4
    e = (t / dur) ** 2.5
    return ((tone * 0.5 + noise) * e).astype(np.float32) * 0.35


def main(bd):
    s = json.load(open(f"{bd}/script.json"))
    mp = os.path.join(bd, s.get("music", "music.wav"))
    if not os.path.exists(mp):
        sys.exit(f"ERROR: {mp} missing | FIX: run prep first")
    w = wave.open(mp, "rb")
    nch, sw, sr, nfr = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    a = np.frombuffer(w.readframes(nfr), dtype=np.int16).astype(np.float32) / 32768
    w.close()
    a = a.reshape(-1, nch)
    scenes = s["scenes"]
    events = []

    def add(x, at):
        i0 = int(at * sr)
        if i0 < 0 or i0 >= len(a): return
        L = min(len(x), len(a) - i0)
        a[i0:i0 + L] += x[:L, None]

    add(_subdrop(), scenes[0]["start"] + 0.25); events.append("subdrop@title")
    last = scenes[-1]
    add(_subdrop(), last["start"]); events.append("subdrop@closer")
    add(_riser(), max(last["start"] - 3.0, 0)); events.append("riser->closer")
    wh = 0
    for i in range(1, len(scenes) - 1):
        if scenes[i - 1]["duration"] >= 7.0 and wh < 6:
            st = scenes[i]["start"]
            add(_whoosh(seed=i), max(st - 0.8, 0))
            events.append(f"whoosh@{st:.0f}s"); wh += 1
    a = np.clip(a, -1, 1)
    w = wave.open(mp, "wb")
    w.setnchannels(nch); w.setsampwidth(2); w.setframerate(sr)
    w.writeframes((a * 32000).astype(np.int16).tobytes()); w.close()
    print(f"sfx: {', '.join(events)}")


if __name__ == "__main__":
    main(sys.argv[1])
