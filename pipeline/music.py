"""Generative cinematic score engine v3 (fully synthesized - no licensing, no APIs).
Usage: python3 music.py <out.wav> <seconds> [vo.mp3] [genre]
- slow minor chord pads with detuned voices + synthetic reverb (real stereo)
- deep root drone + filtered-noise swells that bloom in the VO's pauses
- subtle heartbeat pulse (philosophy) / shimmering plucks (dmt)
- VO-adaptive: recedes under speech, swells in gaps, builds toward the ending"""
import subprocess, sys, wave
import numpy as np

SR = 44100


def vo_envelope(vo, seconds, n):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", vo, "-ac", "1", "-ar", "8000",
                        "-f", "s16le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < 8000:
        return None, None
    hop = 800
    frames = len(x) // hop
    rms = np.sqrt((x[:frames * hop].reshape(frames, hop) ** 2).mean(axis=1))
    rms = rms / (np.percentile(rms, 95) + 1e-9)
    sm = np.clip(np.convolve(rms, np.ones(15) / 15, mode="same"), 0, 1)
    quiet, onsets, run = sm < 0.12, [], 0
    for i, q in enumerate(quiet):
        run = run + 1 if q else 0
        if run == 8:
            onsets.append((i - 7) * hop / 8000.0)
    env = np.interp(np.linspace(0, len(sm) - 1, n), np.arange(len(sm)), sm)
    return env, onsets


def _reverb(x, decay=2.2, mix=0.22, seed=3):
    rng = np.random.default_rng(seed)
    L = int(decay * SR)
    t = np.arange(L) / SR
    ir = rng.standard_normal(L).astype(np.float32) * np.exp(-t / (decay * 0.35))
    ir /= np.abs(ir).sum() ** 0.5 * 40
    m = 1 << int(np.ceil(np.log2(len(x) + L)))
    wet = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m))[:len(x)]
    return x * (1 - mix) + wet.astype(np.float32) * mix


def _pad(freqs, n, rng):
    t = np.arange(n) / SR
    v = np.zeros(n, np.float32)
    for f in freqs:
        for det in (-0.15, 0.0, 0.15):                     # detuned voices = width/warmth
            ph = rng.uniform(0, 2 * np.pi)
            for h, a in ((1, 1.0), (2, 0.35), (3, 0.12), (4, 0.05)):
                v += (a / len(freqs)) * np.sin(2 * np.pi * (f + det) * h * t + ph)
    return v * 0.22


def _swell_noise(n, seconds, rng):
    spec = np.fft.rfft(rng.standard_normal(n).astype(np.float32))
    fr = np.fft.rfftfreq(n, 1 / SR)
    spec *= np.exp(-((np.log(fr + 1) - np.log(400)) ** 2) / 1.1)   # airy band ~200-900Hz
    return np.fft.irfft(spec, n)[:n].astype(np.float32) * 0.9


CHORDS = {
    None: [(110.0, 220.0, 261.63, 329.63), (87.31, 174.61, 261.63, 349.23),
           (130.81, 196.0, 261.63, 392.0), (98.0, 196.0, 293.66, 392.0)],   # Am F C G
    "dmt": [(130.81, 196.0, 293.66, 392.0), (146.83, 220.0, 329.63, 440.0),
            (98.0, 196.0, 246.94, 369.99), (110.0, 220.0, 277.18, 415.30)],  # lydian-ish
}


def gen(path, seconds, vo=None, genre=None):
    rng = np.random.default_rng(11)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    # 1. chord pads, 14s bars with 4s equal-power crossfades
    chords = CHORDS.get(genre, CHORDS[None])
    bar, xf = 14.0, 4.0
    pads = np.zeros(n, np.float32)
    i, pos = 0, 0.0
    while pos < seconds:
        seg_n = min(int((bar + xf) * SR), n - int(pos * SR))
        if seg_n <= 0: break
        seg = _pad(chords[i % len(chords)], seg_n, rng)
        w = np.ones(seg_n, np.float32)
        f = min(int(xf * SR), seg_n // 2)
        w[:f] = np.sin(np.linspace(0, np.pi / 2, f)) ** 2
        w[-f:] = np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        s0 = int(pos * SR)
        pads[s0:s0 + seg_n] += seg * w
        pos += bar; i += 1
    # 2. root drone (octave below chord roots)
    drone = 0.16 * np.sin(2 * np.pi * 55.0 * t) + 0.08 * np.sin(2 * np.pi * 55.7 * t)
    # 3. airy noise swells (slow LFO; later re-shaped by VO pauses)
    swell_lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.021 * t + 1.2)
    air = _swell_noise(n, seconds, rng) * swell_lfo * 0.14
    v = pads + drone + air
    # 4. genre motion layer
    if genre == "dmt":  # slow pentatonic plucks, long tails
        scale = [523.25, 587.33, 659.26, 783.99, 880.0, 1046.5]
        for st in np.arange(2.0, seconds - 3, 4.5):
            f = scale[int(rng.integers(len(scale)))]
            i0 = int(st * SR); L = min(int(3.5 * SR), n - i0)
            tt = np.arange(L) / SR
            v[i0:i0 + L] += 0.05 * np.exp(-tt / 1.4) * np.sin(2 * np.pi * f * tt)
    else:               # sparse deep heartbeat ~ every 2.2s
        beat = np.zeros(n, np.float32)
        for st in np.arange(1.0, seconds - 1, 2.2):
            i0 = int(st * SR); L = min(int(0.35 * SR), n - i0)
            tt = np.arange(L) / SR
            beat[i0:i0 + L] += np.exp(-tt / 0.09) * np.sin(2 * np.pi * 52 * tt)
        v += beat * 0.10
    v = _reverb(v, decay=2.6 if genre == "dmt" else 2.2)
    # 5. VO adaptation: duck under speech, bloom in pauses, arc to the ending
    speech, onsets = (None, None)
    if vo:
        try: speech, onsets = vo_envelope(vo, seconds, n)
        except Exception: speech = None
    if speech is not None:
        if len(speech) < n: speech = np.pad(speech, (0, n - len(speech)), mode="edge")
        v *= 1.15 - 0.6 * speech[:n]
        v *= 1.0 + 0.3 * np.exp(-0.5 * ((t / seconds - 0.92) / 0.18) ** 2) * (t / seconds)
        for k, on in enumerate(onsets or []):
            if 2 < on < seconds - 2:
                f = [329.63, 392.0, 440.0][k % 3]
                i0 = int(on * SR); L = min(int(3 * SR), n - i0)
                tt = np.arange(L) / SR
                v[i0:i0 + L] += 0.05 * np.exp(-tt / 1.1) * np.sin(2 * np.pi * f * tt) \
                                * np.minimum(1, tt / 0.12)
    # 6. stereo (Haas micro-delay) + fades + write
    env = np.minimum(1.0, np.minimum(t / 4.0, np.maximum(seconds - t, 0) / 4.0))
    v = np.clip(v * env * 0.9, -1, 1)
    d = int(0.011 * SR)
    left = v
    right = np.concatenate([np.zeros(d, np.float32), v[:-d]])
    st2 = (np.stack([left, right], 1) * 32000).astype(np.int16)
    w = wave.open(path, "wb")
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(st2.tobytes()); w.close()
    print(f"music: {seconds:.1f}s score ({'dmt' if genre=='dmt' else 'cinematic'}"
          f"{', VO-adaptive' if speech is not None else ''})")


if __name__ == "__main__":
    gen(sys.argv[1], float(sys.argv[2]),
        sys.argv[3] if len(sys.argv) > 3 else None,
        sys.argv[4] if len(sys.argv) > 4 else None)
