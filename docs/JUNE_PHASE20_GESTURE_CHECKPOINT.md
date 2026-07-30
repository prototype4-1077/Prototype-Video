# June Oxley Phase 20 gesture checkpoint

Date: 2026-07-29

Status: June now performs two story actions inside the full-HD hero shot: he lifts and replaces the returned enamel mug, then reaches for, lifts, and replaces the pencil before the compassion hold. The final local A/V render and full decode pass; public reproduction is the next gate.

## Source drawings

The built-in image generator produced five registration-locked full-frame pose drawings from the Phase 19 plate. Only localized hand, forearm, sleeve, prop, revealed background, and contact-shadow pixels enter the final composite.

| Pose drawing | Purpose | SHA-256 |
| --- | --- | --- |
| `june_oxley_porch_mug_lift_low_v1.png` | Mug gripped and one inch above table | `85ca03e9b6a704fb5089790469171f4cdd1ca777c02822bb09a546ce6ed006dd` |
| `june_oxley_porch_mug_lift_mid_v1.png` | Mug at upper-abdomen in-between | `a060e229df1fbaf2500d8b5a38e2bafeaa2ba780f4196bfe763abeb667926295` |
| `june_oxley_porch_mug_lift_v1.png` | Mug at mid-chest hero pose | `d4d921596259944fabbd91e137108ff718b470ee9d711b3336326e7f8ac6e2e6` |
| `june_oxley_porch_pencil_contact_v1.png` | Fingers pinch pencil while it still touches ledger | `847b7440c2c126d9052e24ab8bf5b6503d1014e49991faf1006dd2b761da0018` |
| `june_oxley_porch_pencil_hold_v1.png` | Pencil paused a few inches above ledger | `94147f429f65e5d9488908327357e971e404e63885240a869113caabbdcc8757` |

All five are 1672x941 RGB. Prompts locked the exact camera, crop, June identity, face, opposite hand, untouched props, porch, lighting, and textures while requiring five-finger anatomy and prohibiting duplicate hands or props.

Image-generation provenance:

- Mug hero: `exec-4f20c6c4-242a-4131-8948-f15e39cbb549.png`.
- Pencil hero: `exec-2f707cb6-0c42-42bc-95eb-d20d4d438ac1.png`.
- Mug low in-between: `exec-3764eb04-afe3-4af1-a0b5-c3de1ec85da9.png`.
- Mug middle in-between: `exec-962fc9ba-3bc9-4286-a6a3-3ee6c89d1ecc.png`.
- Pencil-contact in-between: `exec-404b773e-f4f2-4807-943d-7b7b6421945c.png`.
- Tool mode: built-in reference editing with local reference images; no key, paid API, or paid runtime dependency.

## Contracts and renderer

| Asset | Role |
| --- | --- |
| `concept/style_frames/june_oxley_porch_gesture_atlas_v1.json` | Pose sources, amounts, local patch boxes, feathering, steam origins, interpolation policy, hashes, invariants, and visual gates |
| `concept/style_frames/june_golden_scene_gesture_cues_v1.json` | Five contiguous gesture cues on the exact 453-frame clock |
| `pipeline/cartoon_gesture_atlas.py` | Contract/cue validation, local color transfer, registered pose preparation, limited-animation selection, patch compositing, and steam-origin output |
| `pipeline/cartoon_hero_scene.py` | Optional gesture integration, exact-clock validation, moving steam, and gesture evidence in the final render report |

The mug patch is restricted to plate coordinates `(230, 335, 800, 920)` with a 34-pixel feather. The pencil patch is `(675, 535, 1195, 925)` with a 30-pixel feather. June's head and facial acting always come from the Phase 16/18 atlases after the hand layers, so pose-source facial differences never enter the shot.

## Failed interpolation and final choice

The first implementation used OpenCV DIS optical flow across the neutral and hero gesture poses. Still gates looked plausible, but a 10 fps playback contact sheet exposed translucent duplicate arms and mugs on intermediate frames. Adding registered in-between drawings reduced the error but did not eliminate it on every optical-flow sample. Both renders were rejected and preserved only in local review directories.

The accepted renderer uses `registered_stepped_inbetweens`: finished drawings selected at an 8-10 fps hand-animation cadence while eyes, mouth, body deformation, atmosphere, camera, encoding, and audio remain at 30 fps. This is intentional animation "on threes," not a technical frame drop. It produces clean silhouettes and resembles traditional limited character animation instead of a digital dissolve.

Motion design:

- Frames 1-36: neutral hand pose.
- Frames 37-50: mug traverses low, middle, and hero drawings on a cubic timing envelope.
- Frames 51-114: mug hero hold.
- Frames 115-128: mug drawings reverse cleanly to the table.
- Frames 129-294: neutral hands.
- Frames 295-306: pencil contact and hero drawings.
- Frames 307-378: pencil hold.
- Frames 379-392: pencil drawings reverse to the ledger.
- Frames 393-453: no hand action; gaze, head settle, breath stop, and compassion own the ending.

Steam origin follows the mug across the authored drawing positions rather than remaining on the table.

## Local evidence

Output directory: `outputs/edit/phase20-gesture-performance-v2`

| Property | Verified value |
| --- | --- |
| Video | `june-hero-expression-performance.mp4` |
| Video SHA-256 | `2f72490ed262db8e21bdd1e415eeded4374dfb959bad8cb1b2fd70b240806386` |
| Video | H.264/yuv420p, 1920x1080, 30 fps, 453 frames |
| Audio | AAC, 48 kHz, stereo |
| Video/audio duration | 15.100 seconds / 15.100 seconds |
| Encoded size/bit rate | 8,281,195 bytes / 4,387,388 bits per second |
| Gesture cues/states | 5 / neutral, mug_lift, pencil_hold |
| First frame SHA-256 | `0d2065b90f70d03b1cd94d38dfe46ff96bdf30ad62783eef0685833ba7f0f159` |
| Final frame SHA-256 | `819b124a7b1bc1cb645f21258c75302839d5ce4f9ed137ed0207e5dab3bf7707` |

Verification:

- Eleven focused hero/gesture tests pass.
- The complete pipeline regression passes: 331 tests run, 1 optional-dependency skip, 0 failures.
- FFmpeg decodes the complete gesture-enabled A/V file without an error.
- FFprobe confirms the exact video/audio contract above.
- Full-resolution transition frames inspect every registered mug and pencil drawing in both directions.
- Encoded-output 10 fps contact sheets inspect the complete lift phases at playback spacing.
- A fifteen-frame runtime timeline confirms that hand actions land on the intended story beats and leave the ending still.

## Honest visual gate

Passed:

- Mug, handle, chip, hand, thumb, sleeve, and elbow remain a single readable silhouette in every accepted drawing.
- Pencil remains one short yellow prop; thumb, index, middle, ring, and little fingers remain anatomically readable.
- No duplicate hand, arm, mug, or pencil survives in the accepted transition frames.
- Pose-patch borders remain invisible at normal and full-resolution inspection.
- The mug action supports the returned-mug line; the pencil action supports the ledger line.
- Steam follows the lifted mug.
- The hands return to neutral before the final gaze-down/compassion hold.

Not passed yet:

- Hand actions intentionally animate on threes; they are clean but less fluid than a fully drawn theatrical sequence on ones or twos.
- The current pose library has one action path per prop and cannot yet improvise arbitrary gestures.
- The mug never reaches June's lips and there is no sip, liquid surface, or swallowing animation.
- The pencil does not produce a visible mark or page deformation.
- Only one front-facing hero shot is integrated; the other six golden-scene shots and angle-specific atlases remain missing.
- Scratch Piper speech remains a timing prototype, not June's final voice performance.

## Recommended next gate

Publish and independently reproduce the gesture-enabled 1920x1080 artifact. Then stop expanding this single shot and assemble the first multi-shot sequence: use GS010 as the present hero setup, GS020 as a mug-chip insert, GS040 as the ledger/pencil medium, GS050 as the existing emotional close-up, and GS070 as the final question. Each shot should have its own registration contract, action drawings, continuity hashes, and cut-frame handles. Add open-source ambience, mug/wood/pencil Foley, and a temporary music stem only after picture timing is locked.
