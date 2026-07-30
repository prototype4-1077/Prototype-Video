# June Oxley Phase 28 — Deformable 2.5D Rig Checkpoint

## Stopping point

Phase 28 stops at a locally validated 12-second, 1080p, continuously deforming body-rig proof. The proof uses premium painterly June pixels on the approved porch, not the rejected off-model Blender v8 character.

The canonical identity is explicit and machine-gated: June is an elderly rural **man**, lean and wiry, with short thinning white hair and a trimmed white beard and mustache. An earlier female generation was rejected, archived outside the repository, and never promoted.

## Authoritative files

- Rig contract: `concept/characters/june_oxley_deformable_rig_v1.json`
- Male chroma source: `concept/characters/puppet_sources/june_oxley_puppet_source_v1_chroma.png`
- Male alpha source: `concept/characters/puppet_sources/june_oxley_puppet_source_v1.png`
- Renderer: `pipeline/cartoon_deformable_rig.py`
- Regression: `pipeline/tests/test_cartoon_deformable_rig.py`

The source art is a zero-cash, build-time ImageGen production drawing derived from the canonical turnaround and approved GS030 standing art. Chroma removal is complete; generation is not required at runtime.

## What the rig proves

- Two depth-ordered premultiplied-RGBA layers: body base and independently deforming foreground right arm.
- A continuous Gaussian skeletal inverse-warp field rather than cross-dissolved body drawings.
- Five action windows: `TURN`, `REACH`, `HAND_OFF`, `SIT_DOWN`, and `STAND_UP`.
- Two planted-foot pins and three localized elbow/knee volume correctives.
- A shared body-plus-arm shoulder field, which prevents both hip-pixel borrowing during the reach and shoulder seams during the crouch.
- Male identity invariants that reject female, wife, hair-bun, and clean-shaven interpretations.

## Accepted local master

Location:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase28-deformable-rig\master\june-deformable-rig-proof.mp4`

Delivery and gates:

- 1920×1080, 30 fps, 360 frames, 12.0 seconds, H.264/yuv420p
- MP4 SHA-256: `39fe12fe448ced0f38e8bff48488d019db2ed80b9412b87173f20cc7009a4691`
- Exact full decode: 360/360 frames
- Foot drift: 0.0 px left and right
- Right-hand excursion: 170.438815 px
- Root vertical excursion: 78.125 px
- Maximum landmark step: 7.722593 px (8 px gate)
- Alpha-area range: 0.991920–1.005602
- Distinct landmark poses: 338
- Minimum encoded review-frame Laplacian variance: 270.819998
- Seven focused unit tests pass
- Cash cost: $0; paid runtime services: none

Rejected experiments are retained only under `outputs/edit/phase28-deformable-rig/rejected-wrong-identity` and `rejected-deformation`. They are evidence, not canon.

## Honest limitations

- This is one high-quality three-quarter standing view, not unrestricted angle synthesis.
- `SIT_DOWN` is a bounded planted crouch test; a full chair sit still needs a seated corrective drawing and chair-contact constraint.
- Only the foreground right arm has been isolated as a separate topology-safe layer. The left arm and legs still use the body field.
- The hand-off has no receiver or prop constraint.
- The proof is silent and does not yet integrate the existing close-view viseme/expression atlases.
- The renderer is deterministic and reusable, but the 12-second proof is a rig demonstration, not a finished story scene.

## Recommended next step

Start Phase 29 with one production dialogue shot, not another broad research cycle. Bind the existing male June viseme/expression atlases to this body rig, add blinks and gaze, constrain the reaching hand to the enamel mug, and cut a 12–15 second voiced porch performance. Require face identity, lip-sync, shoulder seam, mug contact, foot contact, temporal stability, audio, and exact-decode gates. Only after that comparison set exists should a local optimizer or reinforcement-learning loop tune bounded timing, gaze, blink, reach, and corrective weights.

## Resume command

```powershell
python -m unittest pipeline.tests.test_cartoon_deformable_rig -v
python -m pipeline.cartoon_deformable_rig concept\characters\june_oxley_deformable_rig_v1.json --output-dir outputs\edit\phase28-deformable-rig\master
```
