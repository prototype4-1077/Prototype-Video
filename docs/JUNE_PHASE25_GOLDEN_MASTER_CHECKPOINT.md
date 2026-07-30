# June Oxley Phase 25 — Complete Golden Scene Master Checkpoint

## Outcome

Phase 25 produces the first complete working cut of *The Twelve-Dollar Mug*: seven shots, 1,164 frames, and exactly 38.8 seconds at 1920×1080/30 fps. It preserves the strongest accepted artwork as actual output pixels and consumes the three full-motion shots one-to-one.

This is a complete high-quality picture prototype, not a claim that every drawing is continuously deformable. GS030, GS060, and GS070 contain the proved body, liquid, facial, and performance animation. GS010, GS020, GS040, and GS050 use premium authored plates with bounded camera/light life and declared action cuts.

## Production package

- Master contract: `concept/style_frames/june_golden_scene_master_v1.json`
- Master assembler: `pipeline/cartoon_golden_master.py`
- Focused regression: `pipeline/tests/test_cartoon_golden_master.py`
- Local accepted master: `outputs/edit/phase25-golden-master/full-render-v1/june-golden-scene-master.mp4`
- Local scratch dialogue: `outputs/edit/phase25-golden-master-audio/june-golden-scene-scratch-dialogue.wav`
- CI artifact: `june-golden-scene-master-v1`

## Exact frame map

| Shot | Master frames | Count | Production source |
| --- | ---: | ---: | --- |
| GS010 | 1–129 | 129 | Canonical establishing painting with 3% push |
| GS020 | 130–225 | 96 | Canonical mug-chip/thumb-contact insert |
| GS030 | 226–396 | 171 | Registered layered stand video, frames 1–171 one-to-one |
| GS040 | 397–564 | 168 | Ledger start, tactile ledger insert, and ledger end paintings; hard cuts at 453 and 509 |
| GS050 | 565–678 | 114 | Compassion start/end paintings; hard emotional cut at 621 and at least 24 held frames |
| GS060 | 679–936 | 258 | Registered layered pour video, frames 1–258 one-to-one |
| GS070 | 937–1164 | 228 | Registered resolution video, frames 1–228 one-to-one |

Primary shot cuts are 130, 226, 397, 565, 679, and 937. There is no optical flow, cross-dissolve, implicit speed change, frame duplication inside the rendered shots, or paid runtime dependency.

## Local verification

| Check | Result |
| --- | ---: |
| Master video SHA-256 | `1d4535bf15bf3a3b952986b41460a4542a6b9fc5785636447ef3b7c9801e18c4` |
| Master report SHA-256 | `cf832a3cfd3660709b41527c0f36c3ecef07cf2f96dbe6d0b257d4eb5c1f2dca` |
| Master contract SHA-256 | `7c461a3aa4867ea80c091c4919bc806607ed0acc97c0b4da26f0d8d30da8cf6f` |
| Scratch dialogue SHA-256 | `dd0f5b32dcd71fd96321ef710e7725868a778da16c541ae86aa0580acde60fe3` |
| Video codec / pixel format | H.264 / yuv420p |
| Audio codec / format | AAC / 48 kHz stereo |
| Encoded video frames | 1,164 |
| Video / audio duration | 38.800 / 38.800 seconds |
| Minimum / mean review PSNR | 39.216 / 41.987 dB |
| Minimum encoded Laplacian variance | 126.297 |
| Rendered source frames consumed | GS030 171, GS060 258, GS070 228 |
| Focused Phase 24 + 25 tests | 13 passed |

The complete master decodes without errors. Twenty-six source review frames and the same twenty-six independently decoded H.264 frames cover every shot beginning/middle/end and both sides of all internal action cuts. The full encoded contact sheet passed full-resolution visual inspection.

## Sound status

The local prototype contains the complete dialogue, generated at zero cash with the local Piper Ryan voice. Each line is generated separately, finishes within its exact shot duration, and is padded rather than time-warped to preserve intelligibility and the intended action/emotional holds.

This voice is explicitly scratch, not canonical June casting. There is not yet porch ambience, chair/clothing/boot Foley, mug/ledger/pencil/pot/pour Foley, final EQ, dynamics, -16 LUFS-I normalization, or -1 dBTP limiting. Public CI renders the picture silently so it stays reproducible and does not promote the scratch voice as final sound.

## Honest picture boundaries

- GS010 is a premium establishing hold; June's visible mouth is not independently articulated there.
- GS020 preserves exact thumb contact and the chipped rim, but the thumb does not yet rub independently.
- GS040 and GS050 use authored pose cuts, not continuous hand/head topology deformation.
- Large-action continuity is intentionally limited-animation language: held drawings, motivated cuts, camera motion, secondary life, full-rate fluid, and full-rate facial animation where the rig is proved.

These are the remaining differences between a strong complete prototype and a fully reusable studio character system. They do not hide broken contacts, ghosting, or retiming.

## Recommended next production step

Treat this master as picture lock. The next highest-value pass is sound: create a coherent zero-cash porch ambience bed, author the required prop/body Foley to exact frame contacts, record or approve June's final voice, and master the mix to -16 LUFS-I with a -1 dBTP ceiling. In parallel, begin the reusable high-resolution June rig manifest—segmented head, eyes, mouth, hair, torso, arms, hands, clothing, props, shadows, and occlusion planes—so the next episode can replace held plate shots with continuous deformation without lowering the approved art finish.
