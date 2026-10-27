# GPT notes — 2026-10-27 — human rejection and controlled audio source isolation

Parent checkpoint: `f70b614de50fcbe48b7f2a6c37222e0bec68fabd`.
Branch: `agent/phase42-human-rejected-gates-repair-v1`.

## New human evidence controls the next step

James: "Blink still needs a little work but really good. It almost passes.
The audio still has static". Asked when, he answered **"Throughout"**.
Recorded exactly in `collab/JAMES_VERDICT_2026-10-27.md`.

Blink v2 remains near-pass, not accepted. Balanced-air audio is rejected for
static remaining. There is no new clean-warm verdict. Do not interpret the
old proxy zero as acceptance, and do not regenerate the nearly accepted eye
art while diagnosing audio. A question about blink shape/speed/reopening was
sent asynchronously; check any reply before selecting a blink adjustment.

## Hypothesis, not a confirmed cure

Because the defect is throughout, including a dialogue-free opening, prioritize
the continuous background before filtering or replacing the voice. Source
inspection shows deliberate noise-based leaves/cicadas in the procedural bed.
Earlier shelving left that source present. The voice could still have its own
defect; it is not declared clean without listening evidence.

Added `pipeline/cartoon_audio_stem_isolation.py`. It reconstructs the reviewed
balanced-air PCM with zero sample error, replays the bed's exact original seed,
preserves all other event seeds, uses one common original gain, and exports:

- porch-bed-removed (main causal audition),
- voice-only (starts at 3.3 s, with intentional silence before it),
- porch-bed-only (not boosted).

All files remain 484,800 stereo PCM24 frames at 48 kHz. No video, image edit,
new service, dependency, or cash spend. The old references stay immutable.

## Proof

Folder: `collab/phase42_audio_source_isolation_v1/`.
Report SHA-256:
`2abfe387758726e4be5cb7960e6f487d0d49fa1e9b8a2864d941b5d643447f54`

Bed-removed WAV SHA-256:
`8ab4281813b6d42d5dba3eb5a8d863ff47725e98f345c3ebd9c545486cbe0bc7`

Voice-only WAV SHA-256:
`b9a2f402d9255397bf8cafec9170aca6e76c028b5cbd5ede0733d2ebc699f16a`

The isolated bed is nonzero across all 303 frames; opening RMS -45.36 dBFS.
Its old static-proxy result is still zero, so that proxy is not sufficient for
the defect James hears. These energy descriptions do not establish audibility
or identify a confirmed cause by themselves.

Six new tests plus predecessor audio/proxy checks pass: **16 tests in 13.35 s**.
They verify exact reference reconstruction, shared unaltered voice gain,
voice timing, causal subtraction within PCM rounding, unchanged reviewed
reference, no clipping, exact formats, deterministic regeneration, source-bound
evidence, and refusal to overwrite. Renamed the old test's "remove static"
wording to describe its actual old-proxy scope; its assertions are unchanged.

## Resume from the listening answer, not another filter sweep

The bed-removed comparison was displayed inline. Asked whether steady static
disappears, reduces, or stays unchanged. Await that reply; it is the causal
experiment's deciding evidence. Voice-only and bed-only are available as
references. Do not show another metric-green "cleaned" master as a resolution.

If bed removal resolves the defect, rebuild a restrained non-hissy soundstage
around the preserved voice/actions and obtain listening acceptance. If noise
remains only with effects, isolate those events. If voice-only also has the
defect, work on the speech source. Keep original speech timing unless a new
timing/lip-sync proof is explicitly made. No full render or promotion yet.

## Subsequent replies — supersede the pending questions above

James said bed removal made **"No real change"**. Do not continue the bed-only
cause claim. For the voice-only reference he explicitly corrected the earlier
silent-opening answer: **"correction there is not static."** Treat the voice
as clean, not the original mix. This rules out proceeding with unnecessary
voice filtering/replacement. New source-targeted work is in the sparse-Foley
audition; check its separate listening reply. Blink direction is slightly
slower, less frequent, and only a small shape change; do not regenerate art.
