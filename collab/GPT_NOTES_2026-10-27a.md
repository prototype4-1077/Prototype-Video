# GPT notes — 2026-10-27 — continuous blink control and honest playback timing

Read at resume: `collab/PROTOCOL.md`, James's 2026-10-26 rejection, and Claude's
latest local review `CLAUDE_REVIEW_2026-08-13_0612Z.md`. No newer human verdict
exists in this worktree. Branch: `agent/phase42-human-rejected-gates-repair-v1`.

## Progress, not another status-only wait

The preceding scheduled turns merely restated the pending human gate; they
were not live-process waits. There was useful permitted work available:
adversarially inspect the new blink control rather than just re-read its green
artifact report.

That inspection found an actual failure at closure 0.999 and one near zero.
The v1 context was binary-switching the enlarged socket region. On native
GS070 geometry, .9989 to .9991 jumped by 255 alpha levels, with more than 1,200
pixels per eye changing by over 20 levels. The old tests mostly inspected
frozen JSON/media, not the live control.

## Implemented

- `pipeline/cartoon_continuous_blink.py`: pure deterministic subpixel masks,
  bounded socket support, upper-lid-led travel, monotone coverage, no synthetic
  crease and no special full-closure switch.
- The source-successor compositor offers an explicit `continuous=True` path.
  The original v1 path is still available for predecessor comparisons.
- Continuous coverage is blended once, not twice at overlapping feathered lids.
- Continuous builds fail closed on the measured tiny-control discontinuity,
  feature-support escape, depth-order failure, or incomplete full-close iris
  occlusion. These are mechanical gates, not artistic acceptance.
- A true 30-fps review loop is published separately from slow inspection.
  The earlier v1 loop used 67-ms frames and endpoint holds, so calling it a
  normal-speed motion proof was too strong.

## Exact review package

`collab/phase42_continuous_blink_review_v2/`

Report SHA-256:
`4c3d7d1c85cf4d68e069bb45808b5597039fb1d0f03e912d1bdaf09b321f2bcf`

Normal-speed loop SHA-256:
`b7675748372f24101f268c0ffcabcfb0aa8ff49179291a913b96e54b67edf2d7`

The full-close delivery RGB hash remains the v1 direct candidate's exact hash:
`155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40`.
The artwork is unchanged; only the control/intermediate coverage differs.

## Verification

Ran these five suites together: continuous blink, eyelid source successor,
full-mix audio successor, audio-noise proxy, and the predecessor Phase37 eyelid
edge diagnostic. Result: **32 tests passed** in 32.48 seconds.

The live tests cover 101 closure values, subpixel endpoint probes, real
compositor pixels, invalid input, support confinement, exact neutral, full iris
closure, restoration of shared functions on exceptions, media hashes, renderer
source binding, and decode-equivalent frames with distinct checked durations.

Actual rendered sequence: 17 frames, zero outside-feature changes, zero depth
violations. Final-delivery eye-crop max 8x8 delta: 116.06771087646484. Do not
compare that to the inherited native-domain 130 ceiling as proof of naturalness;
the earlier recommendation overstated that proxy's meaning.

Rejected artifact hashes remain exact:

- Candidate03 WAV:
  `a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c`
- Phase37 V4 report:
  `fd08ee030123fc96585994825fc49942a937e9e631722478fa54bcee6bc36a7f`

Audio successors remain byte-identical. No new generation, video encode, paid
service, dependency installation, or main-branch mutation occurred.

## Resume from here

1. Read any newer James/Claude review before doing more work.
2. Review v2 normal speed first, then its slow/neighbor proof. Ask for a concrete
   remaining eye defect, not a broad production-quality approval.
3. Listen to the existing balanced-air audio (or clean-warm alternative). Do not
   describe a static-proxy pass as actual human listening acceptance.
4. If both are accepted, build a new integrated review version with preserved
   predecessor hashes. Do not use the consumed Candidate03 claim or mutate a
   rejected artifact. Keep the full-cartoon objective open: this narrow eye/audio
   repair does not prove episode-scale acting, staging, or production quality.

The existing five-hour schedule remains useful for new review evidence. Avoid
re-rendering unchanged proofs or adding infrastructure solely to consume a wake.
