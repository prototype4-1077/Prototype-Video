# June Phase 39 close-body acting rig checkpoint

Date: 2026-08-11

Branch: `agent/phase39-close-body-acting-rig-v1`

Parent checkpoint: Phase38 commit `89d900f55f2611267175b79592e90a7dad3112a8`

## Outcome

Phase39 turns the measured close-view body-performance gap into a working, zero-cash source-textured rig. It replaces the single rectangular shoulder drift with independently authored torso, viewer-left arm, and table-hand controls. All moving regions resolve into one source-resolution inverse-remap field, so moving source pixels receive one final Lanczos resample and the proof has no cutout holes or layer-painter seams.

This is a local silent acting prototype. It does not mutate the accepted picture archive, encode video, promote a master, or claim human acting acceptance.

## Performance design

The 162-frame, 5.4-second proof has four intentional beats rather than an idle loop:

1. F018-F034: a small notice/inhalation and settle into speech;
2. F045-F082: table-hand opening with torso and opposite-arm counter-motion;
3. F091-F126: compact account/debt palm compression with one overshoot and settle;
4. F127-F162: return before the question finishes, followed by a true 14-frame hold.

The hand remains grounded on the table. The face/head rectangle and mug rectangle are copied byte-exact after the remap and change by zero pixels across all 162 frames.

## Machine result

- focused tests: 9/9 passed;
- full performance gates: 14/14 passed;
- rendered frames measured: 162/162;
- maximum source displacement: 2.268 px;
- maximum adjacent landmark step: 0.555 px;
- opening thumb-to-pinky span gain: 5.029 px;
- open-to-compressed span recovery: 7.777 px;
- maximum fingertip vertical excursion: 1.994 px;
- maximum changed pixels in protected face/head: 0;
- maximum changed pixels in protected mug: 0;
- maximum changed pixels outside prospective resampling support: 0;
- final byte-identical hold frames: 14/14;
- moving source resamples: 1;
- encoder processes: 0;
- network calls: 0;
- paid-service calls: 0.

Detached reproduction:

- synthetic commit: `43c1bd1bd7550390f5cf94c68bc55eba62a1bb0e`;
- source tree: `c12ce8dea61c262d7d7761f30f05e8d35692dfa9`;
- focused tests: 9/9 passed;
- full performance gates: 14/14 passed;
- reproduced inventory: 5/5 files;
- all five reproduced file names, byte counts, and SHA-256 hashes match the primary package exactly.

## Visual inspection

Native 2x hand review of F001, F072, and F115 shows intact nail beds, finger silhouettes, cuff contact, and tabletop contact. The opening and compression remain restrained rather than rubbery. Full-frame keyframes show no visible collar tear, face drift, mug drift, or region boundary seam. The performance is deliberately subtle; temporal human review is still required before integration.

## Bindings and evidence

Source bindings:

- contract SHA-256: `fbf86552d6e45727441a4341c256c71e5d9bf315dbfa14a66a46153ec42fac04`;
- implementation SHA-256: `e48bf364a927fb79cf872b5a17bcf732caea2e08772bd38cdeed641a13f4f0d8`;
- tests SHA-256: `cf076bd981f678043520e70560bcf0d00fb773969754fa610a04e911cf7bf7c9`;
- locked GS070 plate SHA-256: `c54f82ef387121267829ec0a85c8fbf56830af2fd18c400ef777cfbb9044d029`;
- locked Phase38 report SHA-256: `0c3c8b0fa4d5773e20be2257e9dab4d67632c83bb2986682e09bf8f19784ade8`.

Final evidence:

- report: `22e5875b5e11c72de5b1f5ca1fb3a706e13158d0f7af1f7498b62010f380fe3d`;
- support overlay: `991b2749a7b5b2e0724e5fada3f3629485a360453935c341350d84a2967523aa`;
- keyframe sheet: `056d697412275fe43d24184606ab91b4d60f044a35bc18c02855660bc6938f27`;
- difference sheet: `939dd9c366c300fa4385a411176f8f7be8c52f6b1ae729bb1ce5288c36f30e99`;
- motion arcs: `aa9e278326d3abfb1cdde0ab6885c129eafaa712ad3f5eca814fb88894b1c8d2`.

## Next step

The detached fresh-snapshot reproduction is exact, so this plan-only proof is ready to freeze locally. The next integration step is to apply the accepted body field before the existing head, facial-feature, atmosphere, and camera stages, then render a synchronized body-plus-face A/B. Candidate03 audio and Phase37 V4 eyelid human verdicts still gate any corrected master rebuild.
