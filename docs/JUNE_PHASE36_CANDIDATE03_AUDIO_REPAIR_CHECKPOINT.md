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

- Reviewed null-receipt contract raw LF SHA-256: `64d5326f9b1a93a73ae05ca790b503076ad90ea6835636527a79e9cb22ad5a0f`
- Stable authorization-subject canonical SHA-256: `bdec01e7d2f897ea06add2f4e1bb61aa74e47fc127b120ad3af6354105f61cd2`
- Implementation LF SHA-256: `950cfe1370d6d9d80c18e805ff7d545c1633b41ef58c8202da9c9776ed886161`
- Noise proxy LF SHA-256: `6af4ed82ea96ed5ce87f46aa4bd945ea4275d3fe609a09930c01827d86ace560`
- Repair tests LF SHA-256: `fbc776852c94917e26b0c2ccec24a49c4ffd00e89050cbaf6100722668db4a8f`
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
