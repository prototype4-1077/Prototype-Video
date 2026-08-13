# GPT 2026-08-11 - STOP: Candidate03 commit 4e3b7d0 authorization request superseded

Do not authorize Candidate03 commit
`4e3b7d0e43136d111f52c810c5dd60c4bdfb7121`. The pointer in
`GPT_NOTES_2026-08-11d.md` is superseded before any authorization or build.

An independent adversarial audit found that the Candidate03 exclusive attempt claim
was not explicitly flushed and `fsync`-sealed before publication work. A simulated
claim-durability failure could therefore leave a partial/non-durable claim without the
typed consumed-attempt preservation already enforced by the VUI and ProRes paths.

The audio prediction itself remains promising, but transaction safety is part of the
authorization surface. The isolated branch is being corrected with deterministic
claim bytes, `O_EXCL`, flush plus `os.fsync`, preserved claim state on any post-create
failure, typed failure reporting, and injected failure tests. All subject, contract,
implementation, test, and note hashes will be recomputed afterward.

No Candidate03 WAV, output directory, stage directory, or claim exists. No audio or
video encoder ran. Wait for a new explicit GPT note with a successor commit and new
hash surface. No master authorization is requested. - GPT
