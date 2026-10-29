# Pickup — 2026-10-29 — short integrated mouth/hand proof ready for James

James resumed interactive project work: see `JAMES_VERDICT_2026-10-29.md`.
Current branch remains `agent/phase42-human-rejected-gates-repair-v1` in
`prototype4-1077/Prototype-Video`. No repository move, main change or merge.
The five-hour heartbeat remains paused; do not turn it on without James.

## Outcome: one reviewable 4.6-second performance A/B

`collab/phase42_mouth_hand_integrated_ab_v1/june-mouth-hand-integrated-ab-v1.mp4`
SHA-256 `28271846b609d97251caf56e5c1d3e02aac4d9d4a5b1419d5bfad2edf748e129`.

Existing left, repaired right. 138 frames at 30 fps / 4.6 seconds, same
complete speech window: scene 3.3-7.9 s, source F025-F162 / output F100-F237.
Both columns are identical fixed native-delivery-pixel crops (no resizing).
That close framing is diagnostic, not a changed final-scene camera or cut.
The current body, head, atmosphere and camera stack remains in both sides.

The left side reuses the current scene's lossless RGB cache, not a new
baseline render or a compressed-video comparison. Verified its cache hash,
all 303 RGB records against the published inventory, and exact EOF. Only
the 138 right-side repair frames plus one endpoint check were composed.
No unchanged full scene was rerendered or production-promoted.

Two independent prepared mouth caches reuse repeated drawings. The new
mouth adapter translates Rhubarb to existing internal art, retaining frame
times, two-frame blends and all artwork. P/B/M uses the exact relaxed rest
plate; rounded and long-L art remain approximations. The separate hand
adapter uses one restrained 0.65-degree contact-pivot rock during the late
gesture, with entry blending and an exact unchanged F148 endpoint.

## Verification and scope

- The two previously pending published-mouth tests now pass (2.562 s).
  Root inspected the native keyframe sheet and four decoded samples.
- Full mouth/hand regression run: **22 tests passed in 226.656 s**.
- New combined-adapter / crop / no-overwrite tests: **5 passed in 58.830 s**.
- New published integrated proof tests: **2 passed in 3.935 s**.
  These are 29 distinct focused tests, not a full-repository/CI pass.
- Every one of the 138 combined frames has **0 changes outside the declared
  transformed mouth/hand support union** and **0 mug changes**. 134 frames
  visibly differ; there is no global frozen-performance bypass.
- The accepted full-close output F248 (source F173) remains exactly
  `155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40`.
- All preview frames decode, 30-fps PTS are exact, SAR is 1:1 and color
  metadata is BT.709 / TV range. Five sampled encode comparisons have
  minimum RGB PSNR **39.975471 dB**. Root inspected all five decoded stills.
- MOV and MP4 have identical encoded picture packets. MOV PCM is the exact
  approved-scene excerpt with 30-ms review-only edge fades. Original full
  audio remains byte-locked. Separate AAC readback: 220800 intended stereo
  samples, 384 decoder-padding samples, **43.380394 dB SNR**, peak
  **0.851824105**. Metrics are not an audible-static or acting verdict.
- Source manifests and attribution accompany the derived media.

Report: `collab/phase42_mouth_hand_integrated_ab_v1/integrated-mouth-hand-review-report-v1.json`
SHA-256 `55c93f7573ddd0e29b92d95edc8d2117e9a1e71f365136a014dd1a9646f46e8d`.
Native component studies are now copied byte-for-byte to
`collab/phase42_mouth_semantics_v1/` and `collab/phase42_hand_refinement_v1/`.
The first incomplete native render and deferred historical source archive
remain preserved locally and are not promoted by this checkpoint.

## Actual Claude review — useful, but not an oracle

One new read-only Sonnet 4.6 / 200K review inspected four decoded integrated
PNGs and the current task/READMEs. Recorded verbatim in
`CLAUDE_REVIEW_2026-10-29_MOUTH_HAND_AB_V1.md`, with sanitized receipt metadata
in `CLAUDE_ACCESS_2026-10-29_MOUTH_HAND_AB_V1.json`. It recommends advancing
to James's normal-speed review. No video, WebP or audio playback was claimed.
Existing Pro login, extended context off, no new credits/API billing; CLI
token estimate is not a cash receipt. No shell/edit/agent/MCP tools exposed.

**Correction to Concern 1:** Claude says all four samples are open and the
P/B/M closure is absent. F067 is actually closed: raw A -> internal X,
blend 1.0, X weight 1.0, cavity area 0. Root confirmed the decoded PNG and
native report; the X renderer uses the exact source plate without perioral
deformation. Preserve the original review as evidence, but do not repeat
its incorrect absent-closure claim or spend another render on it. Whether
that closure lands naturally with the speech is still a human motion test.

**Concern 2:** the perceived lip/beard tonal edge remains worth watching in
motion, but the review's "mouth plate" description is not this renderer's
mechanism. It uses bounded source-textured deformation and oral layers,
not wholesale face/mouth bitmap swaps. At F067 there is no perioral warp;
visible neutral texture alone cannot establish a newly introduced seam.
Do not dismiss the perceptual question or invent a clean-motion verdict.

**Concern 3:** static samples cannot judge the hand's entry/release or
whether its restrained motion still feels like a flat cutout. Agreed.

## Next exact step — human judgment, no unchanged rerender

James should watch this exact A/B once at normal speed and judge the RIGHT
mouth and late hand. Ask which remains objectionable if either fails;
do not ask for an unrelated three-delta card or reopen passed eye/audio/cuts.
After that verdict, either repair the named remaining issue or integrate
the accepted adapters once into the 10.1-second scene and inspect the
mouth transition across the existing later cut before whole-performance
acceptance. This short clip does not prove that cut transition in motion.

No further automatic Claude review, identical proof render, production
promotion or main merge while waiting. No owned local render/test/Claude
session remains after this checkpoint. General fresh-checkout source packaging still
depends on the external baseline cache. The comparison-card label font uses
Windows Arial on this host; cross-platform label-font portability is not
established, and no Linux/full-CI claim is made. These review utilities are
not a new general episode-scale/free-turning 3-D renderer.
