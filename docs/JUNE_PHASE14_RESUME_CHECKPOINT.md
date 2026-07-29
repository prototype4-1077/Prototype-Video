# June Oxley Phase 14 resume checkpoint

Date: 2026-07-29  
Status: safe stopping point; public v7 volumetric-mouth render is reproducible, but final cheek/lip integration remains an art blocker.

## Repository state

- Public repository: `https://github.com/prototype4-1077/Prototype-Video`
- Branch: `agent/june-hero-unified-sculpt-phase-5`
- Pull request: `https://github.com/prototype4-1077/Prototype-Video/pull/8`
- PR base: `agent/june-hero-asset-v2-phase-4`
- Phase 14 render head: `b41b0835af288abfa28e6df0a9e34c9966a83b96`
- `main` remains untouched.
- Phase 12 remains the latest promoted 1920x1080, 15.1-second master.

## What Phase 14 added

- Hero asset contract `concept/characters/june_oxley_asset_v7.json`.
- Look contract `concept/style_frames/june_oxley_npr_look_v7.json`.
- A recessed, upper-anchored volumetric mouth bag instead of the v5/v6 flat radial cavity.
- Independently authored upper and lower lip contour meshes with nine per-viseme shape targets.
- Upper and lower gums, dental banks, tongue, and explicit oral-depth ordering.
- Skull-locked upper anatomy plus soft jaw-coordinated lower anatomy in head space, avoiding the rigid double transform seen in the first v7 audition.
- Continuous rounded dental silhouettes with restrained grooves instead of bead-like individual tooth cubes.
- Bounded beard jaw coupling at 0.30 maximum plus a mouth-clearance corrective.
- A fixed public temporal gate for frames 399-415, the exact Phase 13 failure window.
- Six new Phase 14 contract/geometry tests; the focused file now passes 49 tests.

## Public validation evidence

Stopping-point run:

- Run: `https://github.com/prototype4-1077/Prototype-Video/actions/runs/30490943922`
- Head: `b41b0835af288abfa28e6df0a9e34c9966a83b96`
- `test`: success in 1m09s.
- `blender-v7-volumetric-mouth-temporal`: success in 6m57s.
- Blender 4.2 built, saved, reopened, animated, and rendered the generated v7 `.blend`.
- Output: H.264/yuv420p, 960x540, 30 fps, 17 frames, 0.566667 seconds.
- Source window: frames 399-415 of the unchanged 453-frame performance clock.
- Workflow artifact: `june-golden-performance-volumetric-mouth-v7`.

Artifact hashes:

| Artifact | SHA-256 |
| --- | --- |
| Temporal video | `1a71b374d9467e5f7b2afcfacae84faf9eb31c9a0f4efeafb664933210a5a6d2` |
| Temporal matrix | `ab1b72dbb8751133d2ea80582b221145667faaf53a7d261b66d18ff636c811f8` |
| Generated v7 `.blend` | `88191e5a1fcae353a033f8891803966347db2ed6c5061b51dfbb646dc3624191` |
| Quality report | `56789bfed2829f8b01bf2ceda731f7f8e74b842e066c95bd88d6f6881e473022` |
| Compiled plan | `83e1b8c0be501ab44f55ba6a6903fcee59df70a016d4aa644aeef3b4df5abcec` |

Local evidence outside the repository:

- `outputs/june-phase14-volumetric-mouth-v1-matrix.png` and `-temporal.mp4`: first v7 audition; lower oral cluster detached under rigid jaw parenting.
- `outputs/june-phase14-volumetric-mouth-v2-matrix.png` and `-temporal.mp4`: soft jaw-coupling fix; one coherent mouth, but cavity occluded dental layers.
- `outputs/june-phase14-volumetric-mouth-v3-matrix.png` and `-temporal.mp4`: corrected depth ordering; individual teeth read as beads.
- `outputs/june-phase14-volumetric-mouth-v4-matrix.png` and `-temporal.mp4`: stopping-point continuous dental-bank version.
- `outputs/june-phase14-v4-frame403-x2.png`: full-resolution inspection frame.
- Raw stopping-point artifact: `work/phase14-run30490943922`.

## Visual verdict

Passed:

- The mouth cavity no longer reads as the large flat oval detached below the beard seen in Phase 13.
- The lower lip, teeth, gums, and tongue no longer split into a second mouth on the chin.
- The cavity sits behind lips and teeth; foreground/middle/background ordering is stable throughout frames 399-415.
- Upper and lower dentition read as continuous cartoon banks rather than a row of bead-like cubes.
- Beard movement is restrained and no longer magnifies the opening into a separate oval.
- The v7 library and focused render are deterministic, public, free, and reproducible.

Not passed:

- The upper and lower lips still read as separate horizontal contour strips instead of continuous soft tissue flowing into the cheeks.
- Lip corners are not yet integrated into the head surface, so wide/open poses remain mechanically symmetrical.
- Dental-bank grooves become too line-like at some close-up poses and need an art-directed visibility mask.
- The focused window contains only `C-B-C` visemes; all nine v7 oral poses still need a dedicated square matrix.
- Hands remain contract-tested but visually unverified.
- Phase 14 is therefore a successful representation and layering prototype, not a final-art mouth promotion.

## Recommended next step: Phase 15 cheek-integrated oral sculpt

Do this before another full 453-frame render or reinforcement-learning search:

1. Replace the separate lip tubes with a fitted oral-mask surface that shares the head's facial curvature and blends into cheek/muzzle vertices.
2. Author mouth-corner anchors and asymmetric cheek/nasolabial correctives so open poses deform the surrounding face, not only the aperture.
3. Keep the proven recessed bag and dental/tongue depth stack from v7.
4. Add per-viseme groove visibility and upper/lower dental exposure masks rather than relying only on translation.
5. Render a nine-viseme 3x3 close-up matrix plus the existing frames 399-415 temporal gate.
6. Promote the mouth only when corners, cheek flow, dental exposure, cavity depth, beard clearance, and temporal continuity pass together.
7. Then render the six-pose hand/contact matrix before returning to the full 453-frame promotion master.

Reinforcement learning becomes useful after the oral-mask representation exists. A bounded local preference optimizer can then tune mouth-corner, cheek, dental-exposure, and beard-clearance weights using pairwise human ratings plus continuity penalties. It should not be used to optimize around detached lip topology.

## Resume checklist

1. Confirm the branch is clean at or after `b41b083` and still tracks the public remote.
2. Read this file, `concept/characters/june_oxley_asset_v7.json`, and `concept/style_frames/june_oxley_npr_look_v7.json`.
3. Inspect `outputs/june-phase14-v4-frame403-x2.png`, the v4 matrix, and the v4 temporal video.
4. Start Phase 15 at `_mouth_v7_lip_vertices`, `_make_mouth_v7_lip`, and the head correctives inside `_make_june_v6`/`_make_june_v7`.
5. Preserve v6 and v7 evidence; introduce v8 rather than rewriting the published contracts.
6. Do not run the full master until the nine-viseme mouth matrix and six-pose hand matrix both pass.
