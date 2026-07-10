"""Synthesize an eerie ambient bed. v2: VO-adaptive ("living" music).
Usage: python3 music.py <out.wav> <seconds> [vo.mp3]
With a voiceover given, the bed listens to the narration:
- swells gently in pauses between sentences, recedes under speech
- overall intensity follows a slow arc that peaks near the end (the realization)
- soft chime-like partials surface at the starts of long pauses"""
import subprocess, sys, wave
import numpy as np

SR = 44100


def vo_envelope(vo, seconds, n):
    """Smoothed speech-energy envelope of the VO, resampled to n samples, 0..1."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", vo, "-ac", "1", "-ar", "8000",
                        "-f", "s16le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < 8000:
        return None, None
    hop = 800  # 100ms frames
    frames = len(x) // hop
    rms = np.sqrt((x[:frames * hop].reshape(frames, hop) ** 2).mean(axis=1))
    rms = rms / (np.percentile(rms, 95) + 1e-9)
    k = 15  # 1.5s smoothing
    sm = np.convolve(rms, np.ones(k) / k, mode="same")
    sm = np.clip(sm, 0, 1)
    # pause onsets: frames where smoothed energy drops below 0.12 for >=0.8s
    quiet = sm < 0.12
    onsets = []
    run = 0
    for i, q in enumerate(quiet):
        run = run + 1 if q else 0
        if run == 8:
            onsets.append((i - 7) * hop / 8000.0)
    env = np.interp(np.linspace(0, len(sm) - 1, n), np.arange(len(sm)), sm)
    return env, onsets


def gen(path, seconds, vo=None):
    rng = np.random.default_rng(7)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    freqs = [55.0, 55.7, 82.4, 110.3, 164.8, 220.6]
    amps  = [0.22, 0.18, 0.10, 0.08, 0.05, 0.03]
    lfo_r = [0.023, 0.031, 0.017, 0.041, 0.013, 0.037]
    phases = rng.uniform(0, 2 * np.pi, len(freqs))
    v = np.zeros(n)
    for f, a, lr, ph in zip(freqs, amps, lfo_r, phases):
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * lr * t + ph)
        v += a * lfo * np.sin(2 * np.pi * f * t + ph)
    coarse = rng.uniform(-1, 1, max(int(seconds * 40), 2))
    air = np.interp(np.linspace(0, len(coarse) - 1, n), np.arange(len(coarse)), coarse)
    v += air * 0.05

    speech, onsets = (None, None)
    if vo:
        try:
            speech, onsets = vo_envelope(vo, seconds, n)
        except Exception:
            speech = None
    if speech is not None:
        if len(speech) < n:  # vo shorter than video: hold last value
            speech = np.pad(speech, (0, n - len(speech)), mode="edge")
        # duck under speech, swell in pauses (0.55x .. 1.15x)
        v *= 1.15 - 0.6 * speech[:n]
        # slow dramatic arc peaking ~92% through, +30% at peak
        arc = 1.0 + 0.3 * np.exp(-0.5 * ((t / seconds - 0.92) / 0.18) ** 2) * (t / seconds)
        v *= arc
        # chimes at long-pause onsets: soft high partial, 3s decay
        for i, on in enumerate(onsets or []):
            if on < 2 or on > seconds - 2:
                continue
            f = [329.6, 392.0, 440.0][i % 3]  # E4/G4/A4 over the A-rooted drone
            idx0 = int(on * SR)
            L = min(int(3.0 * SR), n - idx0)
            tt = np.arange(L) / SR
            v[idx0:idx0 + L] += 0.055 * np.exp(-tt / 1.1) * np.sin(2 * np.pi * f * tt) \
                                * np.minimum(1, tt / 0.12)
    env = np.minimum(1.0, np.minimum(t / 4.0, np.maximum((seconds - t), 0) / 4.0))
    s = (np.clip(v * env, -1, 1) * 32000).astype(np.int16)
    st = np.repeat(s[:, None], 2, axis=1)
    w = wave.open(path, "wb")
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(st.tobytes()); w.close()
    print(f"music: {seconds:.1f}s" + (" (VO-adaptive)" if speech is not None else " (static)"))


if __name__ == "__main__":
    gen(sys.argv[1], float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
