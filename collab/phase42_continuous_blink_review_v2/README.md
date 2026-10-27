# Phase 42 — continuous blink review v2

**Human review pending. No full render, master encode, or production promotion.**

This supersedes the v1 blink-motion recommendation, not its artwork or audio.
The v1 package and both rejected predecessors remain unchanged.

## Watch first

- `phase42-eyelid-ai-direct-30fps-v2.webp`: actual 30-fps motion, 17 frames in
  567 ms on the WebP millisecond clock. Looping repeats this diagnostic excerpt;
  it does not represent the spacing of blinks in the complete scene.
- `phase42-eyelid-ai-direct-f240-f256-loop-v2.webp`: the same decoded pixels at
  slow inspection speed, 67-ms frames with 140-ms endpoint holds.
- `phase42-eyelid-ai-direct-f240-f256-sequence-v2.png`: every neighboring frame.

## What changed and why

The v1 control had a hidden threshold: closure 0.9989 to 0.9991 switched on an
entire socket ring. On the actual source geometry, its maximum opacity jump was
255/255, with 1,226 affected left-eye pixels and 1,262 right-eye pixels changing
by more than 20 opacity levels. A second discontinuity existed next to neutral.
The 0/.25/.5/.75/1 sampled sequence and artifact-only tests did not expose these
control defects.

The v2 control moves the same feathered coverage continuously with subpixel
upper/lower margin positions. A pixel is composited once with the maximum lid
alpha; overlapping feathered layers do not amplify each other's opacity.

The original natural closed-eye source is reused. No new image generation,
external runtime service, or cash spend was needed. The full-close frame is
byte-identical to the recommended Phase42 v1 direct-extraction frame:
`155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40`.

## Verified, and not verified

- Near neutral and near full closure, the measured tiny-control opacity jump
  is now 0. The .2499/.2501 probe changes at most 1 opacity level.
- Coverage is monotone over 101 closure values. Exact neutral bypass, full iris
  occlusion, invalid-input rejection, write bounds, and context restoration on
  exceptions are exercised by live renderer tests.
- Across the rendered 17-frame sequence: zero changes outside feature support,
  zero layer-depth violations, and full closure occludes both iris regions.
- Both WebP loops decode to the same 17 full-resolution review crops; their
  distinct playback durations are tested rather than inferred from labels.
- The focused audio/eye/proxy suites plus the predecessor eyelid regression
  suite pass 32 tests.

These checks do not establish that the blink looks lifelike or that the project
is production-quality. The measured final-delivery eye-crop 8x8 maximum delta is
116.07. The previously cited inherited 130 ceiling is a native-domain measure,
so it must not be treated as a calibrated artistic threshold for this
delivery-domain eye crop. James's motion verdict remains authoritative.

## Audio remains the same

Use `../phase42_human_rejected_gates_successors_v1/june-phase42-fullmix-balanced_air-v1.wav`
first; compare `june-phase42-fullmix-clean_warm-v1.wav` there if needed. The audio
was not changed during this pass. Its deterministic full-mix/static and
edit-boundary regression tests were rerun successfully. No human listening
acceptance is recorded.

## Next decision

Watch the normal-speed loop before the slow loop. Does it now look like a
natural blink, without an eyelid pop or pasted orange patch? Separately, does
the balanced-air mix sound clean while keeping the porch alive?

Only after both are accepted should a newly versioned integrated review render
be built. Do not retry or overwrite Candidate03 or Phase37 V4.
