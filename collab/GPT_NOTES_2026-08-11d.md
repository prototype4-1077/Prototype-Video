# GPT 2026-08-11 - Hardened Candidate03 exact authorization request

This note is a collaboration pointer only. It does not alter the stable
authorization subject and grants no build, encode, retry, promotion, or human
acceptance authority.

Please independently review the dormant audio-only repair scaffold at exact
commit `95ceefbf51df114218c8f5320307f18445a1f94f` on branch
`agent/phase36-candidate03-audio-repair-v1`. The earlier commit `4e3b7d0` is
permanently superseded and must not be authorized or built.

Independent adversarial review of the hardened successor is green:

- 19/19 focused tests pass.
- Direct-script and module preflights each pass all 24 gates.
- The one-shot claim uses deterministic UTF-8 bytes, `O_EXCL` mode 0600,
  write, flush, `os.fsync`, and close.
- Every post-create failure raises typed `ClaimWriteError`, preserves the
  consumed claim, leaves output/stage absent, and blocks retry.
- Candidate02 remains byte- and timestamp-identical.
- Candidate03 authorization is null and output/claim are absent.
- Noise thresholds are exact-artifact regression gates only; James must still
  listen to the full 10.1 seconds and the 2.35-3.45-second focus.

Exact binding tokens:

- James verdict LF SHA-256: `9f3974ddcfc4715ea40501bcc46f60594da7021b342047eeed6d44992c729bb3`
- Rejected Candidate02 WAV SHA-256: `f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781`
- Predicted Candidate03 PCM SHA-256: `5cc890db17a2f38aac67fe26c6381b0eab43dd6ae1c4200097e3e98f06fd19f3`
- Predicted Candidate03 WAV SHA-256: `a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c`
- Authorization-subject canonical SHA-256: `691ababbf8ede25e01ed3fea54c35b891da825e49ce5884e8e50d1262160061f`
- Null-receipt contract raw-LF SHA-256: `441b74b8d14edf935674e1714d176b5f6e78a2fcef8c302f2dd68df56bba65d0`
- Implementation LF SHA-256: `3a60e4557d060cae50bcb3ae2e70e3c643bea8df1e594fe763f8ed089f441808`
- Noise proxy LF SHA-256: `07e241f96f1702add749189e1bc8956ce6414789285d34b0b45106e58c789a18`
- Repair tests LF SHA-256: `22b6c11be79c4dd11ddf1a7b5879fd28998500d3e93ec8d8e99df2d914dc0817`
- Proxy tests LF SHA-256: `3ea8d03eeba8b4e79f042cc67f89df0e0f72114b753d3c63f2005e62a1219d85`

If and only if every binding and behavior independently matches, please issue
one receipt containing every token above and exactly one verdict line:

`## Verdict: PHASE36_CANDIDATE03_AUDIO_ONLY_UNENCODED_BUILD_ALLOWED`

The receipt may authorize at most one unencoded PCM24 audio-only build. It may
not authorize picture decode/render/mutation, a video encoder, retry, promotion,
or human acceptance. - GPT
