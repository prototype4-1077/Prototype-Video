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
0.938667 to 0.736 seconds. Seventeen tests and all 24 machine gates pass,
including direct-script and module invocation regression checks, static
injection at 6.0-6.8 seconds, and a separate crackle injection.

No Candidate03 output or attempt claim exists. Authorization is null and the
build command fails closed. A new separate authorization receipt must bind the
exact contract, implementation, proxy, tests, James verdict, rejected C02, and
predicted C03 hashes before one audio-only publication. After publication, James
must listen; no human acceptance or encode authorization is claimed.
