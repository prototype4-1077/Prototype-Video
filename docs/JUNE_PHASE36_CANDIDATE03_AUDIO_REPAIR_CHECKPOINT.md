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
not hard-coded to the historical focus interval. Its fixed thresholds are
deterministic artifact-regression gates for this locked mix, not general
perceptual-safety limits. They cannot certify human taste, audibility, or
acceptance; James must still listen.

The one-shot claim uses deterministic UTF-8 JSON bytes, final-path `O_EXCL`, and
write + flush + `os.fsync` before close. Once the claim path is created, a write,
flush, fsync, or close failure raises typed `ClaimWriteError`, preserves even a
partial claim, consumes authorization, leaves output/stage absent, and blocks a
second build. Fault-injection tests cover fsync, partial-write, and close failure.

## Locked preflight surface

- Reviewed null-receipt contract raw LF SHA-256: `441b74b8d14edf935674e1714d176b5f6e78a2fcef8c302f2dd68df56bba65d0`
- Stable authorization-subject canonical SHA-256: `691ababbf8ede25e01ed3fea54c35b891da825e49ce5884e8e50d1262160061f`
- Implementation LF SHA-256: `3a60e4557d060cae50bcb3ae2e70e3c643bea8df1e594fe763f8ed089f441808`
- Noise proxy LF SHA-256: `07e241f96f1702add749189e1bc8956ce6414789285d34b0b45106e58c789a18`
- Repair tests LF SHA-256: `22b6c11be79c4dd11ddf1a7b5879fd28998500d3e93ec8d8e99df2d914dc0817`
- Proxy tests LF SHA-256: `3ea8d03eeba8b4e79f042cc67f89df0e0f72114b753d3c63f2005e62a1219d85`
- Tests: 19 passed, including durable-claim fault injection and both direct-script and `python -m` preflight invocation
- Machine gates: 24 passed

## Next action

Obtain a separate receipt with the single exact verdict
`PHASE36_CANDIDATE03_AUDIO_ONLY_UNENCODED_BUILD_ALLOWED` and every hash above.
Bind that receipt in the contract, recompute the contract/implementation surface,
re-review, then execute exactly one audio-only build. James should listen to the
full 10.1 seconds first, then replay 2.35-3.45 seconds for residual hiss/static,
an ambience hole, boundary clicks, or an unnatural wind swell. Do not claim
acceptance or request any Phase36 master encode until James accepts Candidate03.
