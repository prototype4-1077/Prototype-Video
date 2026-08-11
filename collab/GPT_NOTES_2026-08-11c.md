# GPT notes 2026-08-11c - Phase36 Candidate03 audio static repair preflight

Worktree: `Prototype-Video-audio-candidate03`

Branch: `agent/phase36-candidate03-audio-repair-v1`

Base: `d5fb3c67f78e2e7d68f77f2d3a321fc24e031444`, fast-forwarded through only
`e7f2239c869b09899d23a1a391ef6cf035f0d7ea`, the content-identical ProRes-side
binding of James's original verdict commit `3a0227cfe06218f17486cfafc0db6a79b8adb9fa`.

Candidate02 is immutable and rejected. Its exact WAV remains
`f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781`.
The flagged 2.47-3.30 second interval is exactly its Phase26 mastered bridge;
the upstream porch generator explicitly adds high-passed Gaussian leaves and
cicada noise. The new repair reconstructs the same interval from locked raw
Phase26 stems and filters only the synthetic ambience with a 4 kHz, 257-tap
linear-phase low-pass. Prop/body detail and all audio outside the repair span are
preserved.

Preflight predicts Candidate03 WAV
`a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c`
and PCM data
`5cc890db17a2f38aac67fe26c6381b0eab43dd6ae1c4200097e3e98f06fd19f3`.
The rejected focus was classified static-like for 100% / 0.832 seconds; the
Candidate03 prediction measures 0% / 0 seconds. Across the complete 10.1-second
mix, the static-like ratio falls from 0.365466 to 0.283898 and maximum run from
0.938667 to 0.736 seconds. Nineteen tests and all 24 machine gates pass,
including direct-script and module invocation regression checks, static
injection at 6.0-6.8 seconds, a separate crackle injection, and one-shot claim
fault injection for fsync, partial-write, and close failures. The claim is
deterministic UTF-8 JSON created with final-path `O_EXCL`; post-create failures
preserve its path, consume authorization, leave output/stage absent, and prevent
a retry.

The proxy thresholds are deterministic artifact-regression gates for this
locked mix. They are not general perceptual-safety limits and do not establish
human acceptability.

Final pre-authorization binding surface:

- Contract raw LF SHA-256: `441b74b8d14edf935674e1714d176b5f6e78a2fcef8c302f2dd68df56bba65d0`
- Authorization-subject canonical SHA-256: `691ababbf8ede25e01ed3fea54c35b891da825e49ce5884e8e50d1262160061f`
- Implementation LF SHA-256: `3a60e4557d060cae50bcb3ae2e70e3c643bea8df1e594fe763f8ed089f441808`
- Noise-proxy LF SHA-256: `07e241f96f1702add749189e1bc8956ce6414789285d34b0b45106e58c789a18`
- Repair-tests LF SHA-256: `22b6c11be79c4dd11ddf1a7b5879fd28998500d3e93ec8d8e99df2d914dc0817`
- Proxy-tests LF SHA-256: `3ea8d03eeba8b4e79f042cc67f89df0e0f72114b753d3c63f2005e62a1219d85`

No Candidate03 output or attempt claim exists. Authorization is null and the
build command fails closed. A new separate authorization receipt must bind the
exact contract, implementation, proxy, tests, James verdict, rejected C02, and
predicted C03 hashes before one audio-only publication. After publication, James
must listen; no human acceptance or encode authorization is claimed.
