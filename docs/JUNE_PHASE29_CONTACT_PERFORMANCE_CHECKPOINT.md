# June Oxley Phase 29 — Contact-Performance Checkpoint

Date: 2026-08-01

Branch: `agent/june-hero-unified-sculpt-phase-5`

Parent checkpoint commit: `d40a9ef` (`Add June shared-UV rig checkpoint`)

## Executive decision

The bounded contact-performance experiment is complete and **rejected for Gate A promotion**.

The experiment repaired the previous proof's dishonest contact measurements. It now measures the final rendered boot alpha against independent porch receiver segments, the hand and pelvis against independent chair geometry, and rendered center of mass against active rendered supports. Those systems pass. The character representation does not.

At full preview size the generated exploded atlas reconstructs June as a marionette with oversized hollow pant tubes, tiny boots, open knee/cuff cavities, rubbery arms, and a teleporting chair hand. The fail-closed report also rejects motion. Do not render the 171-frame Gate A or the 657-frame Gate B from this representation.

Phase 27 remains the audience-facing control and the better finished cartoon.

## What was built

- `concept/characters/june_oxley_contact_performance_v1.json`
- `pipeline/cartoon_contact_performance_proof.py`
- `pipeline/tests/test_cartoon_contact_performance_proof.py`

The new fixture covers source frames 64–112, exactly 49 frames at 960×540 and 30 fps. It adds:

- all five Phase 27 pose keys registered with the original per-pose translation and right-leg warp before interpolation;
- one standing RGB texture source and zero seated RGB samples;
- alpha-iso-contour heel/ball/toe and seven-sample sole evidence after the final camera;
- two independent depth-specific porch receiver tracks;
- staggered heel rolls with one stable foot support;
- contact shadows derived from final rendered boot alpha;
- chair-hand contact-patch tracking and a separate chair-seat top-edge collision receiver;
- rendered component-alpha center of mass and a true two-dimensional active-contact hull;
- raw and bounded-causal alpha-centroid root evidence through frame 112;
- fail-closed aggregation for every one of the 53 threshold leaves;
- report gates that cannot be initialized to `true` or satisfied by target/cage coordinates.

## Validation before encoding

- static contract, gate-evaluator, and pose-registration tests: 19/19 passed;
- complete code-only fixture, with the media-encoding test intentionally excluded: 31 tests and 261 subtests passed;
- exactly one encoded proof attempt was then made;
- no paid API, service, runtime dependency, or cash cost was used.

## Single bounded artifact

Output directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase29-contact-performance-proof`

Files:

- `june-contact-performance-proof.mp4`
- `june-contact-performance-report.json`
- `june-contact-performance-contact-sheet.jpg`
- twelve decoded review frames under `review_frames/`

Delivery verification:

- H.264 / yuv420p;
- 960×540;
- 30 fps;
- exactly 49 encoded and decoded frames;
- 1.633333 seconds;
- video SHA-256 `ddf16d823f285103e8d5591fc05401730af35105002e8c369f8c1d70821751c6`;
- report SHA-256 `6fffd8acd670145969d24ebf396b28ebd50aa91f99f352f9ad3d53dbefba65e8`;
- contact-sheet SHA-256 `999ee0f6e2e306e0b388b2a6d9f62da34ea6f6fe04447c896e936012c2fa62d7`.

## Fail-closed machine result

`machine_passed` is `false`.

Passing named gates:

- delivery;
- source policy;
- feet;
- chair;
- balance;
- joints;
- topology;
- no ghost.

Failing named gate:

- motion.

Selected honest measurements:

| Measurement | Result | Gate |
|---|---:|---:|
| Flat-sole signed-distance p95 | 0.878 px | ≤1.5 px |
| Flat-sole penetration | 0.988 px | ≤1.0 px |
| Toe residual | 0.726 px | ≤1.0 px |
| Contact endpoint motion | 1.711 px/frame | ≤2.0 px/frame |
| Minimum support-hull margin | 4.001 px | ≥4.0 px |
| Root jerk | 1.771 px/frame³ | ≤2.0 px/frame³ |
| Settle upward overshoot | 2.825 px | ≥2.0 px |
| Settle downward compression | 1.082 px | ≥1.0 px |
| Final root speed | 0.0016 px/frame | ≤0.5 px/frame |
| Maximum component-centroid motion | **63.954 px/frame** | **≤14 px/frame** |
| Ascent acceleration reversals | **9** | **≤1** |

The top-level feet summary includes raised-heel frames and therefore reports larger all-frame p95 values; the named flat-foot gate correctly aggregates only declared flat-support frames.

## Visual verdict: reject

The proof is materially worse than the accepted Phase 27 production drawings.

Ranked defects:

1. Both shins inflate into oversized open trouser cylinders. Their dark hollow tops remain visible at the knees throughout the shot.
2. The boots are tiny relative to the cuffs and no longer read as weight-bearing continuations of the legs, even though the sole/floor measurements are correct.
3. Thin local joint bridges can make gap and overlap metrics pass while large visible cavities remain.
4. The left hand teleports from the chair toward the abdomen at frame 79→80.
5. Forearms and sleeves behave as broad rubber tubes and do not preserve wrist tangent, width, or volume.
6. The body motion contains repeated acceleration reversals around the release, ascent keys, and settle transition.
7. June's identity survives, but the body construction and acting do not meet the Phase 27 quality floor.

## Root causes

This is a representation failure, not a parameter-tuning failure.

- The generated exploded atlas is not a pixel-perfect decomposition of the accepted June painting. Each shin source is already painted as an open garment cuff and is then stretched across an entire knee-to-ankle bone.
- Generic 7×3 percentile strip cages treat arms and legs as deformable tubes. They do not understand garment volume, joint arcs, silhouette continuity, or occlusion.
- The local joint repair only needs a small pixel bridge to report overlap. It cannot close a large visible cuff cavity or restore anatomical volume.
- The chair-hand release uses `1-(1-t)^5`. At the first release step, `t=0.2`, so the hand traverses 67.232% of a 160-source-pixel offset in one frame. The resulting left-hand displacement is the 63.954 px report failure.
- The motion curve is C1 while multiple torso, pelvis, limb, release, and settle keys change curvature. Shape morphing also moves alpha centroids even when the authored root is smooth.

## Recommended next architecture

Build a **reconstruction-locked, one-texture, multi-bone patch mesh** from the accepted registered pose-100 foreground. Do not reuse the generated hollow-tube atlas.

The next bounded proof should proceed in this order:

1. Cut overlapping source-space patches directly from `june_gs030_pose_100_foreground_v1.png`.
2. Require a rest-pose recomposition gate that is near-pixel-identical to the accepted foreground before any animation is attempted.
3. Use one continuous weighted mesh for each full pants leg from hip to cuff and one continuous two-bone mesh for each sleeve from shoulder to wrist.
4. Keep separate head, torso, hands/mug, and boots only at real clothing or object boundaries.
5. Replace strip cages with denser silhouette-aware triangulation and five registered pose-space corrective vertex keys.
6. Match collar, wrist, and ankle seam arcs in position, tangent, width, and color; use hidden underlay caps sampled from the same accepted texture.
7. Drive the chair hand with two-bone IK and one C2 Bézier release lasting at least 8–10 frames. Remove the 160-pixel override and orientation mode switch.
8. Prove mechanics first with a flat-color/silhouette render, then apply the accepted texture only after silhouette, volume, contact, and motion gates pass.

Required new gates:

- rest-pose reconstruction error and retained detail;
- per-part area, aspect ratio, and maximum stretch;
- maximum visible cuff/knee cavity area;
- lower and upper joint-overlap bounds, not only minimum overlap;
- seam tangent, width, and local color discontinuity;
- persistent UV/material-point velocity and acceleration;
- unfiltered pelvis/root motion, with filtered motion shown only as diagnostic evidence;
- component-motion argmax with component, from-frame, to-frame, and displacement;
- acceleration-reversal indices with hysteresis and maximum key acceleration discontinuity;
- monotonic 8–10 frame chair-hand release with bounded velocity, acceleration, and jerk.

## RL and agent decision

Do not use reinforcement learning on this renderer. Its source topology cannot express the required body, so an optimizer would only learn to exploit metrics around a visibly broken atlas.

After a reconstruction-locked patch mesh passes human review, agents may search bounded timing, Bézier handles, anticipation, settle, gaze, and corrective weights. Hard identity, reconstruction, topology, contact, and motion gates remain non-negotiable. Preference learning still requires a library of blinded A/B decisions.

## Explicit stopping point

This is the stopping point for the shared-UV exploded-atlas branch.

- Do not rerender this 49-frame proof.
- Do not run Gate A or Gate B.
- Keep Phase 27 as the production control.
- Resume by building the reconstruction-only accepted-pixel patch asset and its rest-pose test. The first new render should be a flat-color/silhouette mechanics proof, not another textured episode render.

