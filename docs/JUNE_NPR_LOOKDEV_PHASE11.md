# June Oxley Storybook NPR Promotion - Phase 11

Phase 11 promotes the approved June performance from a deformation proof into
a deterministic, art-directed storybook cartoon prototype. It keeps the exact
453-frame acting clock and adds a versioned NPR look, parallel full-scene
rendering, exact assembly, a temporally gated open-source finish, synchronized
audio, and burned captions.

This is a working production prototype, not a claim that procedural rendering
alone equals the best hand-authored studio animation. The visual gate is kept
separate from the technical gate, and the remaining artistic gaps are recorded
explicitly below.

## Promoted render

- Source revision: `be588dc` (`Promote the full NPR scene in parallel`)
- Full promotion workflow: run `30437955999` (run 59)
- Regression, six deterministic render chunks, and exact assembly: passed
- Artifact ID: `8719742588`
- Artifact name: `june-golden-performance-storybook-npr-v1`
- Artifact ZIP SHA-256:
  `5197e2ce8d1c8b218870119d2f17fadf4f31bef907a41c52b81106fce3337a54`
- Assembled 960x540 source SHA-256:
  `1ec22c983064e77a2e43054f8500ea6ec3c0dbb5d2d20547b620a5f18f220161`
- Look-profile SHA-256:
  `82c1bdd50be1984254e195f1f5fe846b5c98eae542e6cbc189a7e391b612ef9f`
- Clock: 960x540, H.264, 30 fps, 453 frames, 15.1 seconds
- Assembly: six gap-free ranges covering frames 1-453

The nine-pose review spans the three authored shot scales at frames 1, 93, 171,
172, 260, 339, 340, 398, and 453. It passed visual review for coherent identity,
readable pose changes, stable props, and clean wide-to-medium and
medium-to-close cuts.

## AI finish and delivery

The delivery uses the official open-source Real-ESRGAN NCNN/Vulkan release and
its AnimeVideo-v3 model as a restoration/upscale stage. It does not generate
new acting or replace source frames. The pinned tool, model, settings, and
temporal-gate evidence are in
`concept/style_frames/june_oxley_npr_finish_v1.json`.

- Temporal audition: 30 consecutive frames, passed human review
- Identity or shape hallucination: none observed
- Static-background adjacent luma difference: reduced 10.34 percent
- Delivery: 1920x1080, H.264/AAC stereo, 48 kHz, 30 fps, 453 frames,
  15.1 seconds
- Delivery SHA-256:
  `203a1b48abe219c2c3a89215baa03725279f5c160d59c68c42be83ecf1e56b25`
- Approved audio-source SHA-256:
  `f84dcdae98fb44d80c451eaae5ba3ba8d9335e7a074edfc0e4b8a4be34aadd32`
- Approved caption-source SHA-256:
  `e90529d7e302e740e256a2e39295cb4def0e34a25fa1ab15009bf29cc83206be`
- Full decode: passed independently with FFmpeg; FFprobe confirmed both streams
- Final nine-pose matrix SHA-256:
  `995c5542f4953fb605e5b57f9f1a32a17561e3092b20c7abc57b9a772d574900`
- Final nine-pose visual disposition: passed for identity, posing, prop
  continuity, shot-scale changes, caption visibility, and absence of AI shape
  hallucination

`pipeline/cartoon_ai_finish.py` enforces the exact input clock, extracts and
validates every numbered frame, requires exact 2x output dimensions, restores
audio and captions, fully decodes the result, reprobes the contract, and emits
SHA-256 evidence for the source, result, executable, audio source, and captions.

## Learning without a cash budget

`pipeline/cartoon_look_learner.py` implements a deterministic linear-UCB
contextual bandit using only the Python standard library. It treats shot scale,
motion, emotion, and background complexity as context; immutable NPR profiles
as actions; and identity, expression, temporal stability, silhouette, palette,
human preference, and render cost as reward objectives.

Hard floors zero out unsafe observations. The learner may recommend the next
look experiment, but it cannot edit a promoted profile, relax a gate, or approve
its own work. Human art direction remains the promotion authority. This is a
practical reinforcement-learning loop for expensive visual experiments without
paid inference, opaque policy optimization, or uncontrolled frame generation.

## CI policy after promotion

Full-scene promotion is explicit because it is expensive. Commit `2c57970`
restored pull-request CI to the economical 30-frame temporal gate after the full
render passed. Pipeline run `30442073803` (run 60) passed that restored gate.
The complete six-chunk 453-frame workflow remains reproducible when a look or
performance is intentionally promoted.

## Honest remaining art gaps

The prototype now has a complete production path, stable identity, authored
acting, exact sound and timing, and a coherent finished look. The highest-value
remaining work is artistic, not more resolution:

1. Replace the single neutral edge treatment with baked Grease Pencil semantic
   ink layers for silhouette, facial marks, construction, contact, and accents.
2. Add an acting-polish pass for arcs, anticipation, breath, overlap, hand
   shapes, eye darts, overshoot, settle, asymmetry, and deliberate stillness.
3. Improve mouth, cheek, eyelid, hand, beard, and cloth topology for expressive
   closeups.
4. Author shot-specific shade shapes and line behavior from story beats.
5. Add original room tone, foley, prop sounds, and restrained music around the
   dialogue.
6. Prove asset continuity in a longer multi-shot pilot and collect real pairwise
   reviewer choices for the look learner.

The recommended next phase is semantic ink plus acting polish on this exact
scene. That produces the largest visible quality increase while preserving the
validated character, clock, sound, and distributed render system.
