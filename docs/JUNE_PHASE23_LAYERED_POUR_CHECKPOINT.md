# June Oxley Phase 23 — GS060 Layered Pour Checkpoint

## Outcome

Phase 23 converts the approved GS060 artwork from a visual target into an actual 8.6-second production shot. The renderer consumes six pinned, full-detail RGBA performance drawings over a reconstructed clean porch. It does not redraw June with low-detail procedural shapes.

This distinction matters:

- The canonical turnaround and GS060 style target remain the design map.
- The six registered source drawings and derived foreground layers are production pixels.
- Pillow, NumPy, and FFmpeg control timing, registration, camera, steam, liquid, encoding, and verification.

The result is deliberately classified as authored-pose 2.5D limited animation. It is not claimed to be continuous topology deformation or a final reusable character rig.

## Production package

- Contract: `concept/style_frames/june_golden_scene_gs060_layered_pour_v1.json`
- Renderer: `pipeline/cartoon_pour_layers.py`
- Focused regression: `pipeline/tests/test_cartoon_pour_layers.py`
- Clean porch plate: `june-golden-scene-gs060-clean-porch-v1.png`
- Six accepted performance drawings: pencil poised, pencil down, grounded pot grasp, lift, pre-pour, and full tilt
- Six pinned RGBA foreground layers derived offline with the free U2Net and U2Net-human models
- CI artifact: `june-gs060-layered-pour-v1`

The active-pour illustration is retained as provenance for coffee color, arc, width, and landing, but its baked liquid is not used at runtime. The stream is generated deterministically from the registered spout to the receiving mug ellipse.

## Mechanics and continuity gates

- Exact clock: 1920×1080, 30 fps, 258 frames, 8.600 seconds
- Mug rim registration: every pose resolves to the same `[1000, 692]` source-canvas target with zero residual
- Grounded pot continuity: the three pre-lift drawings stay within 20.396 source pixels of the fixed tabletop anchor; the contract ceiling is 24 pixels
- Liquid origin: zero-pixel error at the full-tilt spout
- Liquid destination: normalized receiving-ellipse value 0.033058, safely inside the mug
- Rendered liquid spill: zero source pixels
- Liquid timing: onset frames 128–135, continuous pour 136–176, taper 177–184
- Transition method: one-frame directional target-pose smears; no full-frame optical flow and no multi-frame cross-dissolves
- Support-foot audit: intentionally false because this is a medium insert; the final edit must precede it with the already-proved GS030 wide standing shot

## Local verification

The accepted local render is under `outputs/edit/phase23-gs060-layered/full-render-v2/` and is intentionally outside Git.

| Check | Result |
| --- | ---: |
| Video SHA-256 | `8754b7127aad59545882a2d6976306227323b87bc889a4dc0b2c4afbbbea52c7` |
| Contract SHA-256 | `ee15b51a42334b6abe9e01cb2d15a65dcbb9876b69444d6087fbe2241e1b386a` |
| Codec / pixel format | H.264 / yuv420p |
| Encoded frames decoded | 258 / 258 |
| Minimum review-frame PSNR | 40.844 dB |
| Mean review-frame PSNR | 41.358 dB |
| Minimum encoded Laplacian variance | 83.242 |
| Mug registration residual | 0.000 source px |
| Grounded-pot maximum residual | 20.396 source px |
| Spout-start error | 0.000 source px |
| Rendered spill | 0 source px |
| Focused tests | 13 passed |

Twenty encoded transition/liquid frames and a complete contact sheet were visually inspected at full resolution. The final grasp drawing restores the left hand to the mug while the right hand takes the pot handle, keeps the pot grounded before lift, and removes the rejected duplicate/teleport behavior.

## Rejected iterations retained outside Git

Three earlier files are preserved under `outputs/edit/phase23-gs060-layered/rejected-iterations/`:

- The first grasp drawing, whose foreground extraction lost the dark pot
- The second registered grasp attempt, whose pot placement was improved but not final
- The first pose-30 matte derived from the rejected grasp

They are not referenced by the production contract and are not shipped in the branch.

## Honest current ceiling

This shot now carries the high-detail art into the encoded video, but the animation vocabulary is still bounded by six authored drawings. Large movement is communicated through readable poses and one-frame smears rather than independently deformable limbs, fingers, cloth, hair, and facial planes. The public artifact is also silent so CI can remain zero-cash and deterministic.

The larger cartoon is not complete: GS070 final coverage, the exact 38.8-second GS010–GS070 assembly, final voice, ambience, Foley, music, and loudness mastering remain.

## Recommended next production step

Build GS070 as the final identity-locked emotional close-up, then assemble GS030 + GS060 + GS070 with the existing multishot material into the exact 38.8-second master. In parallel with that picture-lock work, begin a reusable high-resolution June rig manifest that separates the approved art into head, eyes, mouth, hair, torso, upper/lower arms, hands, props, shadows, and occlusion planes. That rig—not more global motion effects—is the path from premium limited animation to continuous premium animation.

## Public evidence

Pending the Phase 23 GitHub Actions run and independent artifact download.
