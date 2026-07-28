# June Hero Asset v2 — Phase 4

Phase 4 upgrades the proven Phase 3 puppet without changing the episode renderer's
scene, lip-sync, timing, or output contracts. The version boundary is deliberate:
the Phase 3 `1.0.0` builder remains callable, while current no-library renders and
the production gate use `2.0.0`.

## Visual target

The canonical character bible and the reviewed Phase 3 turnaround remain the art
direction. June must read as a lean, capable man in his late seventies or early
eighties—not a round toy proxy or a cowboy stereotype.

Hero v2 specifically addresses the Phase 3 visual review:

- smooth high-segment head, eye, hair, hand, and boot surfaces;
- tapered torso, arms, legs, and garment panels;
- asymmetrical cheek, nose, brow, eye, and hair landmarks;
- small layered sclera, iris, pupil, and catchlight assemblies;
- independent upper/lower eyelids that blink without scaling the eyeballs;
- compact radial-topology lip rim with A–H/X visemes;
- brow raise, brow knit, squint, and cheek-raise corrective shapes;
- segmented two-piece fingers and thumbs;
- tailored jacket lapels, collar, pocket, straps, buttons, cuffs, and soles;
- procedural woven plaid, skin subsurface response, denim weave, and worn leather.

## Asset contract

`concept/characters/june_oxley_asset_v2.json` declares version `2.0.0` and adds
machine-enforced modeling, eyelid, corrective-shape, segmented-hand, artifact
reopen, and human-art-approval requirements. The `.blend` remains a generated CI
artifact and is never committed.

## Quality gate

The manual Blender workflow must:

1. pass all cartoon and asset-contract tests;
2. render both animated proof formats using Hero v2;
3. build `june_oxley_hero_rig-2.0.0.blend`;
4. reopen that exact library from disk;
5. render shot-midpoint Cycles frames at 1920×1080 and 1080×1920;
6. upload the library, six source frames, two contact sheets, two proof videos,
   plans, mouth cues, and the machine-readable report.

Passing automation proves integrity and repeatability. It does not grant the
human art approval required before episode-scale rendering.
