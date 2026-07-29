# June Oxley Phase 19 hero-scene checkpoint

Date: 2026-07-29

Status: the identity-locked face performance now runs inside a production-quality 1920x1080 porch composition with June's upper body, anatomical hands, mug, ledger, pencil, wardrobe, environment, secondary motion, and synchronized prototype audio. Local render and decode gates pass; public reproduction is next.

## What changed

Phase 19 converts the facial "map" into a real screen performance. The renderer no longer presents an isolated square portrait. It projects the same deterministic mouth and expression atlases into a cinematic 16:9 hero plate and then applies bounded 2.5D motion on the exact dialogue clock.

| Asset | Role |
| --- | --- |
| `concept/style_frames/june_oxley_porch_hero_plate_v1.png` | 1672x941 RGB source plate with June, porch, hands, mug, ledger, pencil, lantern, wind chime, road, and depth-of-field environment |
| `concept/style_frames/june_oxley_porch_hero_plate_v1.json` | Source hash, paired-atlas hashes, measured registration, rig regions, motion bounds, zero-cash provenance, invariants, and visual gates |
| `concept/style_frames/june_golden_scene_body_motion_v1.json` | Fourteen authored body/camera keys on the exact 453-frame clock plus deterministic secondary-motion parameters |
| `pipeline/cartoon_hero_scene.py` | Color-managed atlas projection, local deformation rig, atmosphere, camera, raw-frame encoder, audio mux, and report generator |

## Source-art method

The built-in image generator created the plate from three references: the exact neutral atlas portrait, the canonical June turnaround, and the approved porch/ledger style target. The prompt locked June's frontal face, silhouette, large blue-gray eyes, crooked bulbous nose, white hair and beard, wardrobe, prop continuity, hand anatomy, lighting, and unobstructed rigging silhouette. It also required a neutral registration pose rather than an action pose.

- Tool mode: built-in image generation with local reference images; no paid API or key.
- Generated source: `exec-807d51bd-9fcd-42e6-acb8-09dfe9753f48.png`.
- Committed source SHA-256: `a6ed59b3ed26d4ac242828fb173386cd19796dd03ed21ed8dd871676b1ada908`.
- Output plate: 1672x941 RGB, true 16:9 composition.

The source plate registered against the 418x418 facial cells at 1.30x with offset `(447, 47)`. Multiscale edge matching found a best score of `0.2230528593`; eye and nose landmarks were then inspected at full resolution. The contract maps the expression crop to `(532, 106, 906, 346)` and the mouth crop to `(561, 242, 876, 450)` in plate coordinates.

## Production pipeline

Per frame, the renderer:

1. Interpolates Rhubarb mouth cues, authored expression cues, and body/camera keys on one exact clock.
2. Resizes and locally color-matches each source patch to the plate lighting before any transition blend.
3. Applies shoulder counter-motion and breathing with edge-pinned deformation fields.
4. Composites eyes/brows first and lips/jaw/moustache/beard second.
5. Moves the complete head region with a bounded, feather-free deformation whose boundary remains fixed, preventing exposed gaps and double silhouettes.
6. Adds deterministic wind-chime sway, lantern variation, mug steam, and dust motes.
7. Executes an authored face-anchored camera push and scales to 1920x1080.
8. Streams RGB frames directly to FFmpeg instead of writing a multi-gigabyte PNG sequence.

The motion is deliberately compact: head movement stays within 3.5 pixels and 0.9 degrees at source resolution, shoulders counter at lower amplitude, gaze leads the compassion nod, breathing stops for the final hold, and the camera push never exceeds 1.9 percent.

## Local evidence

Output directory: `outputs/edit/phase19-hero-performance`

| Property | Verified value |
| --- | --- |
| Video | `june-hero-expression-performance.mp4` |
| Video SHA-256 | `b55112663101c5ba9f02cb4161185563a9e971c81e7344987512fad6edded398` |
| Video | H.264/yuv420p, 1920x1080, 30 fps, 453 frames |
| Audio | AAC, 48 kHz, stereo |
| Video/audio duration | 15.100 seconds / 15.100 seconds |
| Encoded size/bit rate | 8,051,970 bytes / 4,265,944 bits per second |
| Motion keyframes | 14 |
| First frame SHA-256 | `0d2065b90f70d03b1cd94d38dfe46ff96bdf30ad62783eef0685833ba7f0f159` |
| Final frame SHA-256 | `819b124a7b1bc1cb645f21258c75302839d5ce4f9ed137ed0207e5dab3bf7707` |

Verification:

- Five focused hero-scene tests pass.
- The complete pipeline regression passes: 325 tests run, 1 optional-dependency skip, 0 failures.
- FFmpeg decodes every encoded video and audio packet without an error.
- FFprobe confirms the exact codec, pixel format, dimensions, clock, frame count, channel count, sample rate, and duration above.
- Nine full-resolution review frames cover the first frame, both blinks, brow changes, speech extremes, gaze lead, compassion transition, and final closed-mouth hold.
- A fifteen-frame whole-runtime timeline confirms identity, exposure, prop geography, composition, and camera continuity.

## Honest visual gate

Passed:

- The image now reads as a finished cartoon shot rather than a technical facial test.
- June's face, hair, beard, denim, hands, mug, ledger, pencil, wood, sky, and vegetation hold high-frequency detail at 1080p.
- Eye/brow and mouth layers remain coherent under the plate's warm/cool lighting split.
- No rectangular facial-patch seam is visible in the inspected full-resolution states.
- The widest mouth shapes preserve a natural dental arc, tongue, moustache flow, jaw volume, and beard continuity.
- The final compassion frame closes the mouth, lowers the gaze, settles the head, stops the breath, and preserves clear eye direction.
- Secondary porch motion is subordinate to the performance.

Not passed yet:

- Hands and props are high-quality but remain on one source pose; the mug is not lifted and the pencil is not set down.
- Head and shoulder motion is a bounded 2.5D deformation, not a fully separated occlusion-capable rig.
- The prototype is one continuous hero shot, not the complete seven-shot golden scene with inserts and pose changes.
- Only a frontal atlas is production-ready; three-quarter and profile facial atlases remain missing.
- Scratch Piper speech is a timing prototype and not June's canonical voice.
- The body plate came from reference-locked generated art; a long production still needs reviewable source provenance and consistent regeneration policy for every shot.

## Recommended next gate

Publish and independently reproduce this exact 1920x1080 render in GitHub Actions. Then build the first true gesture layer: a registered two-pose right-hand/pencil atlas and two-pose left-hand/mug atlas with occlusion mattes. The shot should lift the mug on the returned-mug beat, settle it without sliding, set the pencil across the ledger on the moral-choice beat, and end in the existing compassion hold. This adds story action without sacrificing the visual quality already achieved.

After that, extend the same contract to the seven golden-scene shots and train a zero-cost preference optimizer over bounded timing candidates. Its reward should combine human A/B rankings with hard penalties for landmark drift, patch-edge energy, pose discontinuity, eye-mouth desynchronization, prop teleportation, excessive motion, broken holds, and visual disagreement with the approved style targets.
