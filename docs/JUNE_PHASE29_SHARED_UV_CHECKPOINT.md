# June Oxley Phase 29 — Shared-UV Rig Checkpoint

Date: 2026-08-01

Branch: `agent/june-hero-unified-sculpt-phase-5`

Pre-checkpoint commit: `d35e054` (`Document competitive cartoon reverse engineering`)

## Executive decision

Phase 29 now has a deterministic, zero-cash, single-texture shared-UV puppet proof. It removes the most damaging defect in the dual-atlas experiment: independently drawn seated and standing textures no longer dissolve through one another.

The shared-UV proof passes its mechanical gate but is **rejected for the 171-frame Gate A promotion**. At full preview size June still rises like a segmented marionette. The current metrics prove mesh and source-policy correctness; they do not yet prove believable weight, floor contact, chair load, acting, or production finish.

Do not run the 171-frame Gate A or the 657-frame Gate B until the next bounded contact-and-acting proof passes creative review.

## What was built

### Phase 29 performance contract

- `concept/characters/june_oxley_deformable_performance_3q_v1.json`
- `pipeline/cartoon_deformable_performance_3q.py`
- `pipeline/tests/test_cartoon_deformable_performance_3q.py`

This preserves the exact 171-frame `STAND_UP` editorial clock and declares semantic body, hand, mug, chair, boot, anticipation, rise, release, and settle channels.

### Authored 14-part June atlases

- `concept/characters/rig_assets/june_oxley_puppet_atlas_v1.png`
  - 1536x1024 RGBA
  - SHA-256 `acc5f19cf666b3fb64997ba5ec352a7fb0b481128fa1505b1d5d0e9b30d4a55f`
  - exactly 14 substantial connected components
- `concept/characters/rig_assets/june_oxley_puppet_atlas_seated_v1.png`
  - 1536x1024 RGBA
  - SHA-256 `33e0cc580a6b9e80131802a85f58048cdadcb06224fcabb67a72ccb388d6d7d1`
  - exactly 14 substantial connected components
- `concept/characters/june_oxley_puppet_atlas_v1.json`
- `concept/characters/june_oxley_puppet_atlas_seated_v1.json`

Both atlases were authored with built-in ImageGen from accepted June references, then converted locally to deterministic transparent RGBA. No paid runtime API or hosted dependency is required. The standing prompt requested an exploded 14-part June puppet atlas on green with head, torso, paired upper arms, forearms, hands/mug, thighs, shins, and boots in the accepted June identity/style. The seated edit prompt kept the same layout and identity while adding compressed torso/coat, foreshortened thighs, bent knees, planted boots, and a chair-loaded left arm.

### Representation experiments retained as evidence

- `pipeline/cartoon_topology_transition_proof.py`
- `pipeline/cartoon_puppet_atlas_transition_proof.py`
- `pipeline/cartoon_puppet_atlas_performance.py`
- `pipeline/cartoon_dual_atlas_performance_proof.py`
- their focused test modules under `pipeline/tests/`

These experiments established, in order:

1. Whole-plate pose switching preserves style but creates source pops.
2. Crossblending separated pose parts creates ghosting.
3. One standing atlas cannot convincingly supply seated foreshortening.
4. Two corrective atlases improve endpoints but still create a visible mid-rise dissolve.
5. Socket cleanup can make the dual-atlas machine gate green, but cannot remove the dissolve by construction.

### Shared-UV proof

- `pipeline/cartoon_shared_uv_performance_proof.py`
- `pipeline/tests/test_cartoon_shared_uv_performance_proof.py`

The shared-UV renderer uses:

- the standing atlas as the sole RGB/alpha texture source;
- the seated atlas only as a geometry guide;
- one fixed 21-vertex, 24-triangle cage per semantic part;
- seven row-wise 2/50/98 alpha-profile stations;
- dense inverse piecewise-affine remapping;
- no seated RGB sampling, dual-RGBA blend, dual-alpha blend, or crossfade fallback;
- deterministic depth, chair occlusion, steam, light, and camera behavior from the existing adapter.

The strengthened tests include metamorphic provenance checks: extreme seated-RGB recoloring must not alter output, while standing-RGB recoloring must alter it.

## Bounded proof evidence

Output directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase29-shared-uv-performance-proof`

Important files:

- `june-shared-uv-transition-proof.mp4`
- `june-shared-uv-transition-contact-sheet.jpg`
- `june-shared-uv-performance-report.json`
- `review_frames/frame_0064.png` through `review_frames/frame_0100.png`

Verified delivery:

- H.264 / yuv420p
- 960x540
- 30 fps
- 37 encoded and decoded frames
- 1.233333 seconds
- exactly one encoded proof attempt

Machine results:

- focused shared-UV tests: 18/18 passed;
- 14/14 components remained one substantial component;
- 0 mesh foldovers;
- minimum canonical-alpha cage coverage: 0.996523;
- maximum fixed-UV drift: 0.000275 px;
- all 13 declared joint pairs have local overlap;
- maximum local joint propagation: 2 preview px;
- maximum contact p95 socket residual: 1.118 px;
- minimum adjacent-frame alpha IoU: 0.882273;
- 26 non-frozen action pairs;
- seated endpoint IoU: 0.630565, above the 0.629396 dual-atlas baseline;
- standing endpoint IoU: 0.714232, above the 0.697278 dual-atlas baseline;
- report `machine_passed`: true;
- report `audience_quality.status`: `unevaluated`.

## Creative verdict: reject for promotion

The independent visual review rejected the proof for the 171-frame Gate A render.

Ranked defects:

1. Frames 64–95 do not communicate believable load, compression, push, or weight transfer. The body rises as rigid connected segments.
2. The chair hand, chair seat, boot soles, and static contact shadows do not agree visually even though the internal socket residuals are small.
3. Neck, shoulder, wrist, knee, and boot-cuff interfaces still reveal puppet construction, especially around frames 71–91.
4. Jacket shoulders, torso seams, the neck/collar wedge, and the right hand/mug unit deform mechanically.
5. Frames 71–96 are monotone and lack sufficient asymmetry, counter-rotation, effort, and complete settle.
6. The 960x540 fixture is intentionally a mechanics proof and is visibly below the accepted 1920x1080 Phase 27 presentation.

The critical measurement error is semantic: the present foot test measures one authored point inside each boot against that boot's own alpha. It does not measure heel, ball, toe, sole pitch, floor clearance, penetration, or sliding against the porch plane. Chair-hand and chair-seat tests have the same self-reference problem. The proof also stops at frame 100 while the authored settle continues through frame 108.

## Recommended next step

Build one **five-key, contact-constrained shared-UV performance proof** for frames 64–112. Do not tune textures and do not render the episode.

Keep:

- the 14 semantic components;
- the sole standing texture source;
- shared-UV cages and dense inverse remap;
- current background, camera, effects, and editorial contract;
- stream-copy plan for the accepted pour, direct-address, audio, and captions.

Add:

1. Geometry-only keys derived from the accepted Phase 27 pose 0/25/50/75/100 drawings.
2. Cubic interpolation of root, pelvis, chest, head, shoulders, elbows, wrists, hips, knees, ankles, contour anchors, and contact points.
3. A small lower-body IK/contact solver with heel, ball, toe, and seven sole samples per boot.
4. A porch contact segment, two-point foot locking, toe-pivot arcs, and shadows derived from rendered sole contact.
5. Continuous chair-seat and chair-hand load curves, with the palm pinned to actual chair geometry until release.
6. Render-derived center of mass and a heel-to-toe support hull.
7. Parent-driven neck, shoulder, wrist, knee, and ankle cap meshes; no broad alpha dilation.
8. Settle evidence through frame 112, including overshoot, knee recompression, torso/head lag, and final velocity.

Suggested motion keys in source coordinates:

| Frame | Stand | Pelvis | Torso | Root |
|---:|---:|---:|---:|---:|
| 64 | 0.00 | 0.00 | 0.00 | 600,642 |
| 70 | 0.00 | 0.00 | 0.00 | 610,648 |
| 73 | 0.04 | 0.08 | 0.01 | 624,644 |
| 78 | 0.20 | 0.32 | 0.12 | 630,600 |
| 82 | 0.38 | 0.52 | 0.25 | 632,560 |
| 86 | 0.60 | 0.70 | 0.45 | 633,526 |
| 90 | 0.79 | 0.86 | 0.65 | 633,495 |
| 94 | 0.92 | 0.96 | 0.82 | 633,474 |
| 96 | 0.985 | 1.00 | 0.93 | 633,466 |
| 98 | 1.00 | 1.00 | 0.98 | 633,463 |
| 100 | 1.00 | 1.00 | 1.00 | 633,466 |
| 102 | 1.00 | 1.00 | 1.00 | 633,471 |
| 106 | 1.00 | 1.00 | 1.00 | 633,467 |
| 108 | 1.00 | 1.00 | 1.00 | 633,468 |
| 112 | 1.00 | 1.00 | 1.00 | 633,468 |

Required next gates, measured after the final 960x540 camera transform:

- flat support: sole signed-distance p95 <=1.5 px, maximum clearance <=2 px, penetration <=1 px, at least 70% of sole within +/-1.5 px, pitch <=2 degrees;
- toe pivot: toe residual <=1 px, monotone heel lift, maximum 8 px left / 11 px right, contact endpoint motion <=2 px/frame;
- support: rendered COM remains inside the heel-to-toe hull with at least 4 px margin after seat release;
- anticipation: at least 10 preview px forward COM travel before pelvis rises more than 5 px;
- chair hand: hand-to-chair separation <=1 px and slip <=1 px while planted, then monotone release to at least 6 px by frame 84;
- settle: final pelvis error <=1 px and speed <=0.5 px/frame for four consecutive frames;
- preserve all existing shared-UV source, mesh, seam, endpoint, and no-ghost gates;
- explicit human verdict: same June, readable silent action, planted contacts, no conspicuous artifact.

## Resume instructions

1. Read this file and `docs/JUNE_PHASE29_REVERSE_ENGINEERING_CHECKPOINT.md`.
2. Run `git status --short` and confirm the Phase 29 checkpoint commit.
3. Do not rerun the dual-atlas or shared-UV v1 proofs unless investigating a regression.
4. Start with a new contract/test fixture for frames 64–112 and real heel/toe/sole/chair geometry.
5. Render once at 960x540 only after the focused tests pass.
6. Ask for an independent creative review.
7. Only if that review passes, adapt the solver to the 171-frame `STAND_UP` Gate A.
8. Gate B remains a surgical splice: new stand plus unchanged Phase 27 pour/direct, with audio and captions stream-copied and frames 172–657 pixel-identical.

## Explicit stopping point

This checkpoint is intentionally the stopping point. The representation problem is solved well enough to proceed; the remaining blocker is physical acting and contact mechanics. No full-resolution or episode render was spent on a creatively rejected rig.
