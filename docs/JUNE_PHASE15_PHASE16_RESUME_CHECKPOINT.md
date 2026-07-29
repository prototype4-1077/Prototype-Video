# June Oxley Phase 15/16 resume checkpoint

Date: 2026-07-29
Status: Phase 15 procedural mouth is checkpointed at its representation ceiling; Phase 16 has a locally and publicly verified high-fidelity 2.5D facial-animation prototype.

## Repository state

- Public repository: `https://github.com/prototype4-1077/Prototype-Video`
- Branch: `agent/june-hero-unified-sculpt-phase-5`
- Draft pull request: `https://github.com/prototype4-1077/Prototype-Video/pull/8`
- PR base: `agent/june-hero-asset-v2-phase-4`
- Phase 15 stopping head: `717b1cb704b54fd2f181ada35b72c2b0d2c1afd0`
- `main` remains untouched.

## Phase 15 result: a measured representation ceiling

Phase 15 v8.2 replaced detached lip strips with a cheek-integrated oral mask, fitted beard/muzzle deformation, thinner layered moustache strands, stronger dental volume, and a dedicated nine-viseme matrix.

Authoritative public render:

- Run: `https://github.com/prototype4-1077/Prototype-Video/actions/runs/30495553412`
- Artifact: `june-facial-oral-mask-visemes-v8`
- Test and Blender 4.2 build/reopen/render jobs passed.
- Matrix: 1440x1440, nine 480x480 cells in `A B C / D E F / G H X` order.

Passed:

- Nine poses are distinct and readable at the review scale.
- Beard/muzzle depth and B/G separation improved.
- The rigid white moustache slabs were replaced with thinner layered strands.
- The versioned v8 asset remains deterministic and reproducible.

Did not pass final art:

- The mouth still reads as stacked primitive surfaces.
- The tooth bank remains a rectangular white bar.
- X still looks visually open even though its control value is closed.
- The lower lip reads as a separate red plate.

After three bounded still-gate iterations, another parameter-only pass would optimize the wrong representation. Do not promote the v8 procedural face to a temporal or full-master gate.

## Phase 16 pivot: illustrated source pixels become render pixels

Phase 16 uses an identity-locked, fixed-camera 3x3 facial atlas as the actual facial render source rather than as an unreachable style reference. A neutral X portrait supplies the stable head and shoulders. Only a feathered mouth/moustache/local-beard region is replaced and crossfaded for A-H/X.

Versioned source assets:

| Asset | Contract |
| --- | --- |
| `concept/style_frames/june_oxley_viseme_atlas_v1.png` | 1254x1254 RGB, exact 3x3 cells, SHA-256 `73df92931fd6f0e5d276ab85524232479a23d7e3049feb47b0cff7058a24f201` |
| `concept/style_frames/june_oxley_viseme_atlas_v1.json` | Grid, order, neutral pose, mouth crop, feathering, identity hash, visual gates, and zero-cash provenance |
| `concept/style_frames/june-oxley-canonical-turnaround-v1.png` | Canonical identity reference, SHA-256 `c5c32fb5a5c3739e7e87fab8a8d228ddec0b31044fcd6a029851bb9b67b30aa9` |
| `pipeline/cartoon_viseme_atlas.py` | Validator and deterministic 2.5D preview compiler |

The atlas was generated with the built-in image generator while locking the existing canonical turnaround as the identity reference. It required no paid API or cash runtime. This provenance is explicit: the new graphic quality comes from authored/generated source art preserved by the renderer, not from a claim that the procedural Blender mesh produced the illustration.

## Local Phase 16 evidence

Output directory: `outputs/edit/phase16-2p5d-preview`

| Property | Verified value |
| --- | --- |
| Video | `june-2p5d-viseme-preview.mp4` |
| Video SHA-256 | `92234d4af45b5ff43e5c2bdf89f211bcbe41812ba728437d8649296140c05054` |
| Codec/pixel format | H.264 / yuv420p |
| Dimensions | 836x836 |
| Frame rate | 30 fps |
| Frame count | 135 |
| Duration | 4.500 seconds |
| First frame SHA-256 | `d53cd575a5977e168c731f7d720830b89d21a3f3da44c575f08fbdaebf9b106b` |
| Last frame SHA-256 | `d06541d8fe4c3ff978c3ddc2d35465dd1c28fb89096592366b179b1ffaa2d8f5` |

Verification performed:

- Focused atlas tests: 5 passed; full local pipeline regression: 313 passed, 3 skipped.
- FFmpeg decoded the complete output without an error.
- FFprobe confirmed the exact codec, pixel format, dimensions, rate, count, and duration above.
- An 18-frame rendered-output timeline was inspected at `outputs/edit/phase16-2p5d-preview/verify/timeline.png`.
- Held poses and mid-transition frames were inspected separately at full atlas resolution.

Visual verdict:

- All nine held poses preserve illustrated skin, hair, moustache, beard, lip, cavity, tongue, and natural dental-arc detail.
- The neutral portrait and gaze remain stable because the X cell is the fixed base.
- The feathered patch boundary is not visibly readable in the held or sampled transition frames.
- Five-frame cubic-eased transitions avoid a hard sprite pop.
- This is a successful front-facing facial-animation representation prototype.
- It is not yet a full performance: there is no blink/expression layer, head turn, hand/body motion, porch composite, dialogue soundtrack, or production shot edit.

## Public Phase 16 evidence

- Run: `https://github.com/prototype4-1077/Prototype-Video/actions/runs/30497313917`
- Head: `900ef4d136d21babbb12941bc5cf274e20b12622`
- `test`: passed in 1m42s with the full regression suite, atlas render, complete FFmpeg decode, exact ffprobe checks, and artifact upload.
- Artifact: `june-2p5d-viseme-atlas-v1`.
- Public video: H.264/yuv420p, 836x836, 30 fps, 135 frames, 4.500 seconds.
- Public video SHA-256: `6ea69ea93811c8f0ce546afee8654bda973f444d20a3cad3d305c6858e462fe6`.
- Public first-frame SHA-256: `09f4cf8f9813295ce340b0f9baba36b79e39a4648f1cdd2c560503010dd01d14`.
- Public last-frame SHA-256: `1f6c51238f87455c1a4495ff98ae9cfa58a7ee2c1cd75e76c57c155f4db8fddd`.
- The downloaded public artifact decoded cleanly and its 18-frame rendered-output timeline passed visual inspection.

The public Linux and local Windows encoders produce different binary hashes, so each report pins its own outputs. Their frame count, timing, codec contract, atlas hash, pose order, and reviewed appearance agree.

## Compiler invariants

- Rejects non-June, non-X-neutral, paid, reordered, wrong-sized, wrong-mode, or hash-mismatched atlas contracts.
- Rejects a mouth crop outside one cell or unsafe feather values.
- Clears stale numbered frames so a shorter rerender cannot leak old frames into FFmpeg.
- Writes to a partial video and atomically promotes it only after FFmpeg succeeds.
- Pins first-frame, last-frame, atlas, and video hashes in the report.
- Uses cubic easing rather than linear transitions.

## Recommended next gate

Build a real 15.1-second high-fidelity performance close-up before attempting another whole cartoon:

1. Drive the atlas with `june_golden_scene_rhubarb_lipsync_v1.json` on the unchanged 453-frame clock instead of cycling poses alphabetically.
2. Add identity-locked eyelid, brow, and emotional-state layers for blink, smile release, lower-lid engagement, and the final compassion hold.
3. Segment the portrait into head, near/far shoulders, and torso cards; add small perspective-safe 2.5D turns and designed breathing without perpetual bob.
4. Composite that head performance onto the existing Blender porch/body/prop render, retaining Blender for camera, depth, contact shadows, hands, props, and environment.
5. Add the existing local scratch dialogue or a fresh free local Piper voice, rerun Rhubarb from the exact audio, and verify A/V sync.
6. Render a public 1920x1080 close-up gate, inspect every cue boundary and the final hold, then expand the source art to 3/4 and profile angle atlases.

Reinforcement learning becomes useful after these controls exist. Optimize bounded choices such as patch warp, coarticulation duration, blink timing, gaze lead, and head/shoulder parallax with pairwise human preference plus penalties for identity drift, seam energy, lip-sync error, and temporal flicker. It cannot create missing angle art or rescue the discarded primitive-mouth representation.

## Resume checklist

1. Confirm the branch is at or after the Phase 16 atlas/compiler commit and the public atlas-preview workflow is green.
2. Read this file, the atlas JSON contract, and `pipeline/cartoon_viseme_atlas.py`.
3. Inspect the public preview artifact at normal playback speed, not only the atlas still.
4. Extend the compiler with cue-timeline mode using the existing 77-entry Rhubarb file and exact 453-frame clock.
5. Preserve Phase 15 and the alphabet preview as evidence; add a new performance artifact rather than overwriting them.
6. Keep `main` untouched until the stacked draft PR passes the performance, hand/contact, and delivery gates.
