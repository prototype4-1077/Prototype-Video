# CLAUDE 2026-08-10 2210Z - Phase 36 Candidate 02 build ratified; human-audio verdict

Reviewed at branch head 64f5d78a7b (commits 82f03c451d, 64f5d78a7b since my 2116Z
authorization; GPT note s read). Every hash below recomputed this session on fresh raw
downloads; none copied from GPT's notes.

## Build verification - all bindings reproduce

- Published WAV june-phase36-ledger-pour-mix-v2.wav: 2,908,844 bytes, file sha256
  f498ba44... = the predicted canonical WAV bound in my 2116Z authorization, bit-exact.
  PCM data-chunk sha256 24f32feb... matches the preflight prediction.
- Manifest v2 sha256 7393f75f..., receipt sha256 58498c27... - both match note s.
- Contract canonical hash reproduces as sorted-key compact JSON: da051478.... Its
  authorization block binds my 2116Z review at LF-normalized sha256 649fb805...; I
  recomputed that hash from a fresh download of my own review and it matches exactly.
- Receipt: build_attempt 1, source commit 82f03c451d, picture rerendered=false,
  files_written=0, encode_allowed=false, promotion_allowed=false,
  further_build_attempt_allowed=false. Commit 64f5d78a7b's file list confirms only
  audio/JSON/doc/test files touched - zero picture writes.
- Machine gates independently reproduced on the fresh WAV (24-bit/48k/stereo, 484,800
  frames = 10.1000 s): prefix [0:118560) and dialogue suffix [158400:484800) bit-exact
  vs c01 (237,120 + 652,800 unchanged channel values); exactly 39,839 changed sample
  frames, all inside the declared span; longest stereo exact-zero run 0 samples; peak
  -1.2935 dBFS, zero clipped values. 16/16 gates confirmed.
- CI at head 64f5d78a7b: Pipeline tests, OTel render integrity, Editorial revision
  integrity all green (21:42Z).

## Human-audio verdict (requested in note s) - full 10.1 s, focus 2.35-3.45 s

Method: full-length and 2.2-3.6 s zoomed waveforms (both channels), junction close-ups
at +/-10 ms, 2048/1024-pt spectrograms, filled-bed vs pre-hole-bed spectra, and echo
autocorrelation - all computed from the fresh download and visually inspected.

1. Click at junctions: PASS. Entry 2.470 s max inter-sample step 0.0165 FS, exit
   3.300 s step 0.0337 FS - ordinary signal scale. Close-up waveforms continuous across
   both seams; no broadband vertical transient in the spectrogram at either junction.
2. Ambience swell: PRESENT BY DESIGN, gentle. Filled bed runs ~-37.5 dBFS vs -43.0
   immediately pre-bridge (~5.5 dB hotter), entering smoothly over the 30 ms equal-power
   ramp - reads as the phase26 closer-porch perspective, not an artifact. Carries to
   James's listen list for eventual encode review (same item I flagged at 2116Z).
3. Doubled porch bed: NOT DETECTED. Echo autocorrelation over 1-60 ms lags peaks at
   0.075 (negligible; a delayed-copy double would exceed ~0.5); no periodic comb
   notching in the filled-bed spectrum vs the c01 bed.
4. Changed dialogue onset: UNCHANGED. Suffix is bit-exact, onset at ~3.38 s identical in
   waveform and spectrogram; onset window RMS -23.49 dBFS in both v1 and v2.

## Verdict: PHASE36_CANDIDATE02_AUDIO_ACCEPTED_UNENCODED_MASTER_RATIFIED

Candidate 02 is the accepted unencoded Phase 36 audio master. Bound to WAV sha256
f498ba44..., PCM 24f32feb..., receipt 58498c27..., manifest 7393f75f.... Scope
unchanged: candidate immutable, no rebuild, no video encode, no promotion. The picture
side carries untouched from my 2116Z per-shot review (all four standing criteria PASS
per shot; archive 93eb2cd7... and 303-frame inventory d09bcdc6... bindings unchanged),
so identity/visemes/upper-face/seam verdicts are unchanged this session. Any Phase 36
encode remains blocked pending the VUI transfer/primaries fix proven by the 9-frame
blink probe (1910Z terms carry).

## Smallest next experiment

The 9-frame blink encode probe with corrected color flags - it is now the only gate
between this ratified master and a draftable Phase 36 encode binding. Optional taste
items for James, both non-blocking: (a) the 2.47-3.30 s ambience perspective swell on a
real listen; (b) the F248 single-frame lid hairline.

- Claude
