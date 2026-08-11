# June Phase36 Candidate03 audio repair checkpoint

## State

Candidate03 is an audio-only, zero-cash, local preflight scaffold. It is not yet
built. Its authorization receipt is deliberately `null`, so the publish command
fails closed without creating either the output directory or the one-shot claim.
No picture was decoded, rendered, copied, or modified; no video or lossy audio was
encoded. Candidate02 remains byte-exact at WAV SHA-256
`f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781`.

The controlling human document is `collab/JAMES_VERDICT_2026-08-10.md`, bound in
the contract by LF-normalized SHA-256
`9f3974ddcfc4715ea40501bcc46f60594da7021b342047eeed6d44992c729bb3`.
It rejects Candidate02 for audible static and revokes the earlier ratification.

## Diagnosis

The human-flagged 2.47-3.30 second span is exactly Candidate02's committed
Phase26 replacement. The Phase26 porch generator creates its exposed bed from
Gaussian noise and explicitly adds high-passed `leaves` and gated high-passed
`cicada` components. Candidate02 inserted the loudness-mastered Phase26 slice,
while its preceding pour used the quieter raw procedural stems. This explains
both the audible static character and the level/source-family discontinuity.

The rejected bridge measures as broadband noise throughout the entire flagged
interval: static-like window ratio `1.0`, maximum run `0.832 s`, median spectral
flatness about `0.503`, and median power above 8 kHz about `0.489`.

## Candidate03 prediction

Candidate03 reconstructs the same source-time interval from the locked Phase26
raw prop, body, and ambience stems. A 257-tap linear-phase Blackman-windowed sinc
low-pass at 4 kHz is applied only to the ambience stem. Prop and body detail are
not filtered. The filtered ambience is raised 6 dB to avoid recreating the
Candidate01 ambience hole, and 1,440-sample equal-power fades bind both ends to
the immutable Candidate02 timeline.

- Predicted WAV SHA-256: `a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c`
- Predicted PCM-data SHA-256: `5cc890db17a2f38aac67fe26c6381b0eab43dd6ae1c4200097e3e98f06fd19f3`
- PCM geometry: 48 kHz, stereo, signed 24-bit, 484,800 frames, 10.1 seconds
- Changed interval only: `[118560,158400)`; 39,838 sample frames / 79,676 channel values differ
- Prefix and suffix remain bit-exact to rejected Candidate02

Full-mix and focus measurements:

| Metric | Rejected C02 | Predicted C03 |
| --- | ---: | ---: |
| Full-mix static-like window ratio | 0.365466 | 0.283898 |
| Full-mix maximum static-like run | 0.938667 s | 0.736000 s |
| Full-mix exposed-static score p95 | 0.271529 | 0.257552 |
| Flagged-interval static-like ratio | 1.000000 | 0.000000 |
| Flagged-interval maximum static run | 0.832000 s | 0.000000 s |
| Flagged-interval exposed-static score p95 | 0.296082 | 0.000860 |
| Full-mix impulsive crackle events | 0 | 0 |
| Flagged-interval maximum adjacent delta | 0.073605 FS | 0.054034 FS |

Candidate03 repair-span RMS is `-42.1791 dBFS`; whole-mix peak remains
`-1.2935 dBFS`; boundary deltas are `0.016542 FS` and `0.033682 FS`.

The proxy covers every source sample with overlapping 2,048-sample Hann windows
at a 512-sample hop. Tests inject broadband static at 6.0-6.8 seconds, outside the
known defect, and inject a separate impulsive click. This proves the detector is
not hard-coded to the historical focus interval. A machine proxy cannot certify
human taste or audibility; James must still listen.

## Locked preflight surface

- Contract raw LF SHA-256: `d56fa0a2f0ca70b9537a3f6a977383210a5414a3d24f8b3ebf80750a7363a516`
- Contract canonical SHA-256: `595a0949d2129aa636fb089bb0d38021ba72f2f0c89a83bb152767e9fcb0da2c`
- Implementation LF SHA-256: `194038e9b90cf568045c1d513ef678313c7713a803a6923fa0dad6200153a168`
- Noise proxy LF SHA-256: `6af4ed82ea96ed5ce87f46aa4bd945ea4275d3fe609a09930c01827d86ace560`
- Repair tests LF SHA-256: `7c95b3e8b242a04656786147456c27cb49b289f9f58846e2e66c2759ded1b7b7`
- Proxy tests LF SHA-256: `3ea8d03eeba8b4e79f042cc67f89df0e0f72114b753d3c63f2005e62a1219d85`
- Tests: 17 passed, including both direct-script and `python -m` preflight invocation
- Machine gates: 24 passed

## Next action

Obtain a separate receipt with the single exact verdict
`PHASE36_CANDIDATE03_AUDIO_ONLY_UNENCODED_BUILD_ALLOWED` and every hash above.
Bind that receipt in the contract, recompute the contract/implementation surface,
re-review, then execute exactly one audio-only build. James should listen to the
full 10.1 seconds first, then replay 2.35-3.45 seconds for residual hiss/static,
an ambience hole, boundary clicks, or an unnatural wind swell. Do not claim
acceptance or request any Phase36 master encode until James accepts Candidate03.
