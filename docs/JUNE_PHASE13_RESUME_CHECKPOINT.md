# June Oxley Phase 13 resume checkpoint

Date: 2026-07-29  
Status: safe stopping point; public v6 render passes, mouth anatomy remains the next blocker.

## Repository state

- Public repository: `https://github.com/prototype4-1077/Prototype-Video`
- Branch: `agent/june-hero-unified-sculpt-phase-5`
- Pull request: `https://github.com/prototype4-1077/Prototype-Video/pull/8`
- PR base: `agent/june-hero-asset-v2-phase-4`
- Implementation head: `c3a6938d88cc62a11054457dbf718c0c6edd33ee`
- `main` remains untouched.
- Phase 12 master remains the latest promoted full 1920x1080, 15.1-second delivery.

## What Phase 13 added

- Hero asset contract `concept/characters/june_oxley_asset_v6.json`.
- Look contract `concept/style_frames/june_oxley_npr_look_v6.json`.
- Ten distal digit bones so every modeled finger and thumb has two articulated joints.
- Six authored hand shapes: relaxed, mug grip, chair support, ledger support, pencil tripod, and open empathy.
- Six localized facial coarticulation correctives: asymmetric mouth corners, mouth press, inner-brow raise, lower-lid engagement, and jaw softening.
- A skull-locked upper lip and upper teeth plus a separately jaw-driven lower lip.
- Beard shape deformation and moustache overlap transforms driven by jaw and expression cues.
- Eased facial cue transitions instead of constant interpolation.
- Additive deterministic breath, clavicle overlap, and gaze saccades that settle to stillness before the ending.
- A real `June_Micro_Performance_v1` action and persistent required actions in the generated `.blend` library.
- A public GitHub Actions Blender 4.2 gate that renders frames 388-453.

## Validation evidence

Local validation:

- `43 passed` focused asset-library tests.
- `312 passed, 3 skipped, 23 subtests passed` across pytest.
- `296 tests`, `OK (skipped=3)` under the same unittest discovery command used by GitHub.
- Python compilation and `git diff --check` passed.

Public GitHub validation:

- Successful run: `https://github.com/prototype4-1077/Prototype-Video/actions/runs/30484565295`
- Head: `c3a6938d88cc62a11054457dbf718c0c6edd33ee`
- `test`: success in 1m39s.
- `blender-v6-deformation-temporal`: success in 23m17s.
- Blender 4.2 reopened the generated asset library before rendering.
- Output: H.264/yuv420p, 960x540, 30 fps, 66 frames, 2.2 seconds.
- Source window: frames 388-453 of the unchanged 453-frame performance clock.
- Workflow artifact: `june-golden-performance-deformation-temporal-v6`.

Artifact hashes:

| Artifact | SHA-256 |
| --- | --- |
| Temporal video | `6ff57e2c1917ee8362068b435575c653b660028e52455054b00ed5081d9ae35e` |
| Temporal matrix | `d1dbae8614d1be939408d73e34141da2688ad8b1f310a82863907c3e74b0179a` |
| Generated v6 `.blend` | `36c700e2238b78297ad05c70cec181d6bef85e7487208fad7ea62dfecfd538cd` |
| Quality report | `2ab8410270a04e67a03841f726bc007f58d480fc7aa52bab6e355855839425ed` |
| Compiled plan | `acba8c3cc7ed4be6b16815717798ec536e66afaf086b99296a0a0bee529d9474` |
| Phase 13 transition/hold strip | `e29002ffbbd1c8b3c4a265710137670d6a977c316712c1150909c0a997fbce0f` |
| Phase 12/13 comparison | `4da2cc649a8ab7cb1805772f98d6305dbdc56c0664ddcd6a34f643ec43a95b00` |

Local evidence paths outside the repository:

- `outputs/june-phase13-coarticulation-temporal-v1.mp4`
- `outputs/june-phase13-coarticulation-matrix-v1.png`
- `outputs/june-phase13-transition-hold-strip-v1.png`
- `outputs/june-phase12-phase13-transition-compare-v1.png`
- Raw downloaded artifact: `work/phase13-run30484565295`

## Visual verdict

Passed:

- Identity and overall close-up silhouette remain stable.
- The expression change at frame 397 is now spread across the anticipation/settle window instead of popping on one frame.
- On a deterministic 240x135 upper-face ROI, frame 397 mean absolute channel change falls from `2.443` in Phase 12 to `0.906` in Phase 13, a 62.9% reduction.
- Phase 13 upper-face changes remain in a continuous `0.578-0.927` band from frames 393-400.
- Final-hold upper-face motion is stable: mean `0.166`, maximum `0.273` from frames 430-453. Phase 12 was mean `0.166`, maximum `0.305`.
- The v6 asset builds, saves, reopens, animates, renders, encodes, and uploads entirely with free/open local tooling and public GitHub Actions.

Not passed:

- The mouth cavity still reads as a flat, detached oval on strong open visemes. This is the most important visible blocker.
- Beard jaw-follow magnifies the cavity change around frames 401-402. Mouth/beard ROI changes are `8.680` and `8.631` in Phase 13 versus `5.986` and `5.461` in Phase 12.
- The current lip system still relies too heavily on object scaling around a radial rim instead of a volumetric mouth bag and authored lip contours.
- There is no lower-teeth, gum, or tongue structure to preserve depth during `B`, `D`, and `G` visemes.
- The 66-frame close-up does not show the hands. The hand contracts pass, but the six hand shapes still require a visual matrix before promotion.
- Phase 13 is therefore an engineering and temporal-continuity success, not a final-art promotion.

## Recommended next step: Phase 14 volumetric mouth

Do this before reinforcement learning or another full render:

1. Replace the flat cavity/radial-rim presentation with a nested volumetric mouth assembly: recessed mouth bag, upper and lower lip surfaces, gums, lower teeth, and tongue.
2. Author per-viseme deformation targets for lip corners, lip roll, jaw drop, teeth exposure, and tongue placement instead of scaling one rim.
3. Keep upper teeth skull-locked and lower lip/teeth jaw-driven, but add soft tissue correctives between them.
4. Reduce beard `jaw_follow` on wide-open shapes and add a mouth-clearance corrective so the beard frames the lips rather than separating below them.
5. Render a cheap 17-frame gate for frames 399-415, where the current defect peaks, plus a nine-viseme square matrix.
6. Promote only after cavity depth, dental continuity, beard clearance, lip silhouette, and frame-to-frame continuity pass.
7. Then render a dedicated hand-pose/contact matrix before returning to a full 453-frame master.

Reinforcement learning should follow the representation fix, not precede it. A useful zero-cost later experiment is a bounded local preference optimizer over viseme/corrective weights, rewarded by human pairwise ratings plus continuity and silhouette metrics. RL cannot make a flat mouth representation volumetric.

## Resume checklist

1. Confirm the branch is clean and still tracks the public remote.
2. Read this file, `concept/characters/june_oxley_asset_v6.json`, and `concept/style_frames/june_oxley_npr_look_v6.json`.
3. Inspect the Phase 12/13 comparison image and Phase 13 temporal video.
4. Start Phase 14 in `pipeline/blender/render_vertical_slice.py` at `_make_mouth_v5`, `_make_june_v6`, and `_animate_mouth`.
5. Keep the v6 contracts reproducible; add v7 rather than rewriting v6 evidence.
6. Use the 399-415 focused gate until the mouth passes, then run the hand matrix and full promotion render.

