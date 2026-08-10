# June Oxley Phase 31 — Connected-Region Mechanics Checkpoint

Date: 2026-08-08

Branch: `agent/june-hero-unified-sculpt-phase-5`

Starting commit: `776a896999ea7ee124925808b74d2683937e1681`

## Outcome

Phase 31 is complete as a bounded flat-color mechanics proof. It is not a beauty render and is not audience-ready cartoon footage.

The accepted Phase 30 pose-100 foreground now drives a deterministic 49-frame, nine-region mechanics loop with one continuous lower garment, two continuous sleeves, absolute head/hand/mug transforms, identity-locked boots, one stable render order, and one unchanged Phase 27 registration. All 82 machine gates pass after one and only one H.264 encode.

Independent review of all nine decoded motion keys found:

- one continuous trouser mass;
- connected sleeves and hands;
- no visible socket crack or double edge;
- no boot slide;
- no mug flex;
- a clean closed micro-settle loop.

The creative verdict is `mechanics_visual_review_passed_not_audience_ready`. Flat color still hides texture stretch, painted-feature drift, lighting discontinuity, fabric behavior, facial acting, lip sync, and depth staging.

## Production repairs

Repository files:

- `concept/characters/june_oxley_connected_region_mechanics_v1.json`
- `pipeline/cartoon_connected_region_mechanics.py`
- `pipeline/tests/test_cartoon_connected_region_mechanics.py`

Key repairs and protections:

1. The TPS inverse residual now evaluates `forward(inverse(destination)) - destination` only at destination queries whose inverse remap samples lower-garment support.
2. TPS Jacobians are audited on an even 4×4 interior grid plus every garment boundary pixel; non-finite or nonpositive evidence fails closed.
3. Each semantic mask travels through the exact shared registration geometry in discrete ID channels. Topology no longer depends on blended diagnostic RGB or render-order occlusion.
4. Registered semantic connectivity is checked at full source resolution and at 960×540 preview resolution.
5. Locked Phase 30 patch injection is rejected unless every scalar, mask, coordinate hash, bbox, and RGBA array is exact.
6. Boot anchors and sole contacts come from final registered masks. Contact endpoints, temporal motion, and shadow separation are measured rather than declared.
7. Balance uses the final registered character-alpha centroid and the measured rendered boot-contact endpoints.
8. Seam overlap, connected overlap corridors, socket gaps, and secondary overlap edges are measured after registration.
9. Pelvis, head, hand, mug, rotation, cage, centroid, jerk, and settle evidence comes from actual matrices, cages, or final masks. The 4.0-preview-pixel motion gates were not loosened.
10. Diagnostic pixel counts are counted from produced frames; palette violations and pixels outside transformed locked supports fail closed.
11. The report schema now pins its proof payload and decoded per-frame evidence.
12. Delivery refuses overwrites, performs one encode without retry, probes exact stream metadata, fully decodes exactly 49 frames, segments the character from known opaque background colors, compares every decoded frame with its reference, and creates the contact sheet from all nine decoded keyframes.
13. Video, decoded contact sheet, and report are built in a unique sibling staging directory. A failed probe, decode, audit, report, or publication removes staging and leaves no partial final directory; the complete directory is published only after every gate passes.
14. The machine report records and validates the exact Phase 31 contract and auditor-module paths and SHA-256 values.

## Validation

Final production regression:

- Phase 30 plus Phase 31: 45 tests passed in one invocation;
- runtime: 184.703 seconds;
- the suite includes the semantic-mask, corrupt-middle-frame, and subject-ROI adversarial tests;
- it also includes three fast release-transaction tests covering one-encode count, atomic publication, failure cleanup, overwrite protection, and the machine-report false-to-true transition;
- module and tests compile;
- `git diff --check` passes.

The additional adversarial tests prove that:

- changing only a locked semantic mask is rejected;
- corrupting decoded frame 25 fails even when the loop endpoints remain valid;
- subject-only PSNR is not inflated by the large constant background.

## In-memory mechanics evidence

- `mechanics_passed=true`;
- 49 evaluated frames;
- disconnected registered region frames: 0;
- disconnected registered union frames: 0;
- lower-garment minimum sampled TPS Jacobian: `0.948025496909266`;
- lower-garment maximum inverse fixed-point residual: `0.000002033838172301557` source pixels;
- maximum non-boot centroid step: `3.322596446673827` preview pixels/frame, gate `4.0`;
- maximum cage-vertex step: `3.5843521444582` preview pixels/frame, gate `4.0`;
- maximum rotation step: `0.33703703703703713` degrees/frame, gate `0.35`;
- maximum root third difference: `0.9750243110674279`, gate `2.0`;
- boot maximum sole P95 distance: `0.6416605323203559` preview pixels, gate `0.75`;
- boot minimum contact fraction: `1.0`, gate `0.85`;
- maximum boot endpoint motion: `0.0`;
- minimum seam overlap retention: `0.9149075795690692`, gate `0.25`;
- zero-alpha seam paths: 0;
- right-hand/mug registered area change: `0.00009955201592837248`, gate `0.0025`;
- minimum balance margin: `47.7477070986663` preview pixels, gate `12.0`.

## Single encoded delivery

Output directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase31-connected-region-mechanics-v1`

Video:

- file: `june-phase31-connected-region-mechanics-v1.mp4`;
- SHA-256: `21777b5ad4b02d7be5ccf0e183243bcd974673a944f8f6ed4df0979da4180b36`;
- H.264 / yuv420p;
- 960×540;
- 30/1 fps;
- 49 encoded and decoded frames;
- no audio stream;
- time base `1/90000`;
- duration `147000/90000 = 49/30` seconds;
- full independent FFmpeg decode passes.

Decoded fidelity:

- worst per-frame character-mask IoU: `0.9928481461642031`, gate `0.985`;
- worst per-frame subject-ROI PSNR: `32.49736006906059 dB`, gate `30.0 dB`;
- decoded first/last IoU: `0.9990008688097307`, gate `0.995`;
- decoded first/last subject-ROI PSNR: `49.65024057365409 dB`, gate `45.0 dB`.

Contact sheet:

- file: `june-phase31-connected-region-mechanics-contact-sheet-v1.png`;
- SHA-256: `b43e6c1a31a184df1c3f2779414fb989207f7d31d4e090962baf5ceb14cad32b`;
- decoded frames: `1, 7, 13, 19, 25, 31, 37, 43, 49`.

Machine report:

- file: `june-phase31-connected-region-mechanics-report-v1.json`;
- SHA-256 after creative verdict and Phase 31 provenance binding: `6ac15cdbee9908f282c7943d2db94e1fefab73c74c5b4f922a97b6abcc242863`;
- `machine_passed=true`;
- 82/82 gates pass;
- exact contract SHA-256: `24e9c6962b57a3de0cf0b37d8928549a9883a3afc30c817f3e4c68d97248863c`;
- exact auditor-module SHA-256: `0f085a96db8d32c3a0fad994c95e19b0bf25a569a70dd7f69a03a2d1d7792cb7`;
- audience status remains explicitly not audience-ready.

Cash cost and paid runtime dependency are both zero. No network generation, paid API, inpainting, or new character texture was used.

## Exact resume sequence — Phase 32

1. Keep this Phase 31 MP4 and report immutable. Do not spend a second Phase 31 encode.
2. Apply the same validated mechanics to the nine Phase 30 patch-local RGBA textures.
3. Use premultiplied-alpha deformation with explicit overlap ownership; do not recolor, regenerate, inpaint, or infer hidden limb surfaces.
4. Add texture-fidelity gates at every frame: source-pixel provenance, transformed alpha topology, palette-independent seam evidence, local SSIM/PSNR, edge doubling, texture stretch, and first/last exactness before H.264.
5. Add decoded subject-ROI comparisons for all 49 frames and use all nine keyframes plus difference/crack overlays for review.
6. Promote only if the textured proof preserves June’s accepted identity, clothing silhouette, hand/mug unit, boots, and painted detail without visible rubber-sheet distortion.
7. If the textured proof passes, bind the close-face viseme/expression atlas and produce a 6–10 second voiced acting shot. Keep Phase 27 as the audience-facing control.
8. Continue deferring reinforcement learning. Begin bounded local optimization only after blinded human A/B preferences exist for textured timing, gaze, anticipation, overshoot, and corrective weights.

## Recommended next step

Build Phase 32 as a reconstruction-locked textured version of this exact 49-frame loop. This is the shortest honest bridge from “the mechanics work” to “June still looks like June while moving.” Do not start a longer scene until that proof survives full-size human review.
