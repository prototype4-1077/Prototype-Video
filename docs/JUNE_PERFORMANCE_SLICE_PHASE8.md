# June Oxley performance slice — phase 8

Phase 8 turns the approved Golden Scene artwork into a timed GS030–GS050
performance proof. It is the first June deliverable in this program whose acting
poses change across the soundtrack rather than relying on a single style frame
per shot.

## Honest classification

The selected delivery is an **AI-assisted key-pose limited-animation performance
slice; not final topology deformation**. It proves authored acting, timing,
editorial continuity, captions, sound, and a viable zero-cash motion treatment.
It does not claim that generated images are a continuously rigged character.

## Locked contract

- Source scene: `examples/june-golden-scene-twelve-dollar-mug.json`
- Source range: GS030, GS040, GS050 beginning at 7.5 seconds
- Duration: 15.1 seconds
- Shared clock: 30 fps
- Exact frame count: 453 (171 + 168 + 114)
- Delivery: 1920×1080 H.264, 48 kHz AAC stereo, burned readable captions
- Source artwork: nine SHA-256-pinned start/mid/end drawings plus the canonical
  June turnaround
- Runtime policy: local FFmpeg and built-in image generation only; no paid API

The executable contract is
`concept/style_frames/june_golden_scene_performance_slice_v1.json`. The renderer
rejects missing, reordered, dimension-changed, or byte-changed key poses before
encoding.

## Candidate decision

Three local treatments were rendered at full delivery resolution and inspected
at both key poses and transition interiors.

1. **Designed dissolve — rejected.** Technically valid, but 0.6-second blends
   doubled June's face, mug, body, and ledger across the first four transitions.
2. **Full-duration motion compensation — rejected.** It removed double exposure
   but left faces and limbs blurred or warped for seconds between distant poses.
3. **Accelerated pose animation — selected.** Clean start/mid/end drawings hold
   for readability. Motion-compensated in-betweens are sampled only into 5–10
   frame action bursts, followed by explicit settled holds. Blur therefore reads
   as speed instead of a persistent anatomy defect.

The selected mode is reproducible with `--mode pose`. `--resume` reuses only
intermediates whose exact shot frame counts pass `ffprobe`; corrupt, empty, or
off-by-one segments are rebuilt.

## Selected-delivery evidence

- Video SHA-256:
  `f84dcdae98fb44d80c451eaae5ba3ba8d9335e7a074edfc0e4b8a4be34aadd32`
- Key-pose contact sheet SHA-256:
  `bacd034c1dd8c1ce42a7d77fb2c97fbb8f5a83f078e3cc4b13d85a7eb5268ace`
- Action-interior QA sheet SHA-256:
  `7f01e660a0cd4b62ded90ebd25f9fa463f99d21365a8feb3d20faeefd63f65a7`
- Report SHA-256:
  `26eab9ad0e701510852737b9e1fbc576817ae6689017fdbbf07332bf8ffdecde`
- Full decode: pass
- Video geometry: 1920×1080
- Frame rate: 30/1
- Frames: 453
- Duration: 15.1 seconds
- Audio sample rate: 48 kHz
- Integrated loudness: −16.76 LUFS
- True peak: −2.89 dBTP
- Loudness range: 6.5 LU

## What this proves—and what it does not

This phase proves a watchable zero-cash limited-animation path for authored June
performances and establishes machine gates that catch silent FFmpeg failures,
including a real variable-resolution zero-frame segment and a one-frame duration
loss found during development.

It does not solve persistent character topology, lip articulation, hand/prop
contact, cloth deformation, or shot-to-shot model identity. Those require the
next phase: transfer this exact 15.1-second performance timing into the weighted
June hero rig, add production controls (IK/FK, foot locks, fingers, jaw/lips,
cheeks, gaze, and prop constraints), and compare the deforming result against
the selected phase-8 delivery frame for frame.
