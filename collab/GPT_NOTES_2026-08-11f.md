# GPT 2026-08-11 - Candidate03 durability successor ready for authorization review

The stop in `GPT_NOTES_2026-08-11e.md` remains final for commit `4e3b7d0`.
Its corrected successor is now public on
`agent/phase36-candidate03-audio-repair-v1` at exact commit
`95ceefbf51df114218c8f5320307f18445a1f94f`.

The one-shot claim now uses deterministic UTF-8 bytes, `O_EXCL` mode 0600,
write, flush, `os.fsync`, and close before build work. Any post-create failure
raises typed `ClaimWriteError`, preserves the claim as consumed-attempt evidence,
leaves output/stage absent, and blocks retry. Tests inject fsync, partial-write,
and close failures. Nineteen focused tests and both direct/module preflights pass;
all 24 machine gates pass. No Candidate03 output or claim exists.

Final authorization surface:

- controlling James verdict LF SHA-256:
  `9f3974ddcfc4715ea40501bcc46f60594da7021b342047eeed6d44992c729bb3`
- rejected Candidate02 WAV SHA-256:
  `f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781`
- predicted Candidate03 PCM SHA-256:
  `5cc890db17a2f38aac67fe26c6381b0eab43dd6ae1c4200097e3e98f06fd19f3`
- predicted Candidate03 WAV SHA-256:
  `a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c`
- stable authorization-subject canonical SHA-256:
  `691ababbf8ede25e01ed3fea54c35b891da825e49ce5884e8e50d1262160061f`
- reviewed null-receipt contract raw-LF SHA-256:
  `441b74b8d14edf935674e1714d176b5f6e78a2fcef8c302f2dd68df56bba65d0`
- implementation LF SHA-256:
  `3a60e4557d060cae50bcb3ae2e70e3c643bea8df1e594fe763f8ed089f441808`
- audible-noise proxy LF SHA-256:
  `07e241f96f1702add749189e1bc8956ce6414789285d34b0b45106e58c789a18`
- repair tests LF SHA-256:
  `22b6c11be79c4dd11ddf1a7b5879fd28998500d3e93ec8d8e99df2d914dc0817`
- proxy tests LF SHA-256:
  `3ea8d03eeba8b4e79f042cc67f89df0e0f72114b753d3c63f2005e62a1219d85`

The thresholds are deterministic regression gates for this exact predicted
artifact, not general perceptual-safety claims. Human acceptance remains James's
full 10.1-second listen plus focused 2.35-3.45-second replay.

Please independently review the successor and either issue exactly one audio-only
receipt containing every token above and verdict
`PHASE36_CANDIDATE03_AUDIO_ONLY_UNENCODED_BUILD_ALLOWED`, or document the mismatch.
No picture, master encode, retry, promotion, or human acceptance is requested. - GPT
