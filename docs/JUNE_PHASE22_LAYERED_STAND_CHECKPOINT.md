# June Oxley Phase 22 layered stand checkpoint

Date: 2026-07-29

Status: GS030 now has a reproducible 5.7-second seated-to-standing performance built from five high-detail production drawings over one reconstructed clean porch plate. The renderer registers both boots, applies only a bounded lower-leg correction, preserves the mug, adds one-frame target-pose smears, and never asks optical flow to invent anatomy. The local audible master passes full decode, encoded-detail gates, and full-resolution visual review. Public reproduction remains pending until the branch workflow completes.

## Why this phase exists

The rejected Phase 8 pose slice treated widely separated full paintings as frames for whole-image optical-flow interpolation. Playback exposed double mugs, ghost arms, translucent legs and chair pieces, and a breathing background. Those frames were useful as a failure map but were not production animation.

Phase 22 changes the representation:

- The high-detail drawings become the actual character pixels.
- A clean plate supplies one stable set behind every pose.
- Pinned RGBA layers isolate June and the mug from each drawing.
- Contact registration owns foot placement instead of trusting independent paintings to line up.
- One-frame directional smears bridge pose changes without showing two bodies.
- Code still owns timing, camera, steam, shadows, encoding, validation, and delivery.

This is the direct answer to the style-frame gap: the paintings are no longer only a visual map. Their pixels now enter the render, while the contract makes them repeatable animation inputs.

## Production art and provenance

The three new in-between drawings and the clean plate were created with the built-in image generator from local June/GS030 references. They require no paid runtime or API key. The start and end drawings were already versioned GS030 targets.

| Asset | Function | SHA-256 |
| --- | --- | --- |
| `june-golden-scene-gs030-clean-porch-v1.png` | Empty stable porch with the complete rocking chair reconstructed | `c2ed99ead71cc526032908722916c67739d27741e1f1d4145fc276fe11f1e9dd` |
| `june-golden-scene-gs030-performance-quarter-v1.png` | Leverage pose: left hand on chair, mug protected, both boots readable | `edcf0ed84c36af6b3b9464a000d61ab3efcc1357c6beef01313516432e0b1334` |
| `june-golden-scene-gs030-performance-half-v1.png` | Mid-rise weight transfer | `aaec2910111111c48706fecc5902d3e2fde4577935f468f01aa092da3ed54f24` |
| `june-golden-scene-gs030-performance-threequarter-v1.png` | Near-standing release pose | `0e2be41e630eea13699fa5b0891ce9496beedbc4be1fe041e8713e9509a1ace6` |

Prompt intent was deliberately physical rather than decorative: exact full-body action drawings between adjacent registered poses; planted work boots; one left hand supporting on the chair arm until release; the cream enamel mug protected in the right hand; no duplicate anatomy, motion trail, alternate costume, or changed set. The clean-plate edit removed only June and the mug and reconstructed the occluded chair/porch.

Foreground layers were derived offline with `rembg[cpu]` 2.0.77 and the `u2net_human_seg` model (`01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c`). The production renderer does not require rembg: it consumes five content-addressed 1672x941 RGBA files directly. A first alpha-matting attempt exceeded practical memory, so the build used the neural human mask followed by a three-pixel max filter and 0.75-pixel feather. This is recorded as build provenance, not hidden runtime work.

## Motion contract

`concept/style_frames/june_golden_scene_gs030_layered_stand_v1.json` fixes the exact 1920x1080, 30 fps, 171-frame, 5.700-second clock.

| Frames | State | Purpose |
| --- | --- | --- |
| 1-70 | Seated | Establish balance, chair grip, mug, and planted boots. |
| 71 | Directional smear to 25% | Single-body acceleration accent. |
| 72-78 | Leverage | June pushes through the chair arm. |
| 79 | Directional smear to 50% | Weight-transfer accent. |
| 80-86 | Half rise | Hips and torso move over the boots. |
| 87 | Directional smear to 75% | Release accent. |
| 88-94 | Near standing | Left hand clears the chair. |
| 95 | Directional smear to 100% | Settle accent. |
| 96-171 | Standing | Stable held finish with mug and steam. |

The left support boot is translated to one target. A smooth, spatially bounded lower-leg warp corrects the right boot by at most 40 source pixels. The actual five corrections range from 0 to 28 pixels, and both reported contact residuals are exactly 0 pixels. The final 1.2% camera push is applied after compositing so the feet, shadows, body, chair, and porch remain in the same camera space.

## Renderer and tests

`pipeline/cartoon_pose_layers.py` provides strict contract, hash, dimensions, provenance, pose, contact, timeline, camera, and quality validation; premultiplied-alpha registration; bounded smooth leg warping; contact shadows; steam; light breathing; deterministic one-frame smears; raw RGB streaming to H.264/yuv420p; optional 30 ms audio boundary fades; atomic publication; a second complete encoded decode; and fourteen exact review frames.

Seven focused tests cover contract loading, tampered-asset rejection, timeline gaps, loose-contact rejection, schedule boundaries, correction bounds/contact math, and deterministic registered/smear pixels. The complete repository regression passes 345 tests with one expected optional-dependency skip and zero failures.

## Local evidence

Output directory: `outputs/edit/phase22-gs030-layered`

| Property | Verified value |
| --- | --- |
| Video | `june-gs030-layered-stand.mp4` |
| Video SHA-256 | `aa36fd06c79401fdb7699605a86f80bf50bd2ab41b1e9561a3364cab7f60cc0f` |
| Picture | H.264/yuv420p, 1920x1080, 30 fps, 171 frames, 5.700 seconds |
| Audio | AAC, 48 kHz, stereo, 5.700 seconds; 30 ms boundary fades |
| Encoded size / bit rate | 2,951,252 bytes / 4,142,108 bits per second |
| Contract SHA-256 | `870ffd61fe25ba3702641eb0588379bff8628eaed186b08da521a40353507c22` |
| Minimum / mean encoded PSNR | 40.712 / 41.179 dB |
| Minimum encoded detail variance | 147.453 |
| Maximum contact residual | 0 source pixels |
| Review samples | 14: every clean/smear boundary plus first and last frame |

FFmpeg decodes the complete A/V master without error. Full-resolution inspection confirms one stable background, one readable June silhouette, no duplicate mug or limbs, no translucent chair, no planted-foot slide, clean pose holds, and one blurred target body on each smear frame. The mug stays upright and the left hand visibly progresses from chair leverage to release.

## Honest visual gate

Passed:

- High-detail drawing quality survives into the encoded moving shot because the production drawings supply the final character pixels.
- The catastrophic whole-frame interpolation artifacts are gone.
- Five authored body poses communicate anticipation, leverage, weight transfer, release, and settle.
- Both boot contacts are deterministic and measurable.
- June's identity, denim costume, cream mug, porch composition, golden-hour palette, and tactile surface detail remain coherent.
- The stable plate supports camera motion and effects without set shimmer.

Not passed yet:

- This is authored-pose limited animation, not continuous topology deformation or a reusable turnable skeletal body rig.
- The action changes on one smear plus seven-frame holds; it is readable and clean but not yet feature-density character animation.
- Hand/chair contact and the mug silhouette are painted separately in each pose, so small form drift remains possible.
- The porch is one camera plane rather than a deep multi-plane or 3D set.
- GS060 liquid/pour physics, GS070 final resolution, walking, three-quarter/profile speech atlases, and the complete 38.8-second edit remain unfinished.
- The audible local track is a timing mix, not the approved final June voice/Foley/ambience/music master.

## Recommended next gate

Build GS060 as a layered pour shot before assembling the 38.8-second master. It forces the next most valuable unsolved mechanics: a stable kettle/cup handoff, protected hand anatomy, a coherent liquid arc with contact-aware start/end points, steam interaction, foreground occlusion, and a second camera angle. Use authored contact poses for hands and props, but simulate the liquid locally as a deterministic ribbon/particle layer with collision and continuity gates. Then author GS070 coverage and join GS010-GS070 under one exact-clock scene contract.
