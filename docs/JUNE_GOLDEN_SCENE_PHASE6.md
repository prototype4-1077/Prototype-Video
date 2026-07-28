# June Golden Scene — Phase 6

Phase 6 changes the unit of quality from a turntable or three generic dialogue shots to a complete 38.8-second, seven-shot story benchmark: **The Twelve-Dollar Mug**.

## What is now executable

- `examples/june-golden-scene-twelve-dollar-mug.json` is the locked story, performance, framing, prop, art, sound, and acceptance contract for 1,164 frames at 30 fps.
- `concept/style_frames/june_golden_scene_style_targets_v1.json` registers byte-exact art-direction targets for every landscape shot and a separately composed portrait resolution frame.
- `pipeline/cartoon_story_reel.py` turns those targets into a 1920×1080 timed reel with authored camera motion, six-word caption phrases, local scratch voice, procedural ambience/pour sound, a 48 kHz mix, and machine-readable delivery QA.
- `pipeline/cartoon_shape_lab.py` creates immutable zero-cost June shape candidates and Pareto-frontier inputs without pretending that random search is reinforcement learning.
- The Blender performance renderer now consumes every authored shot, gesture, performance direction, and camera move instead of indexing only three hard-coded beats.

## Build the story reel

The production build uses local FFmpeg and Piper 1.2.0 with the MIT-licensed `en_US-ryan-medium` voice. Downloaded executables and model weights stay outside Git; generated videos stay outside Git.

```text
python -m pipeline.cartoon_story_reel \
  examples/june-golden-scene-twelve-dollar-mug.json \
  concept/style_frames/june_golden_scene_style_targets_v1.json \
  --output-dir build/june-golden-scene \
  --piper /path/to/piper \
  --voice-model /path/to/en_US-ryan-medium.onnx
```

The report labels this a `style-frame story reel; not final deformation animation`. It rejects wrong dimensions, duration, frame count, missing audio, or a non-48-kHz delivery. It also records the voice-model SHA-256, per-shot cadence fitting, integrated loudness, true peak, loudness range, and any known limits.

## Quality contract

The scene deliberately exposes the weaknesses hidden by a talking-head proof:

- GS020 requires designed fingers and stable mug-chip continuity.
- GS030 requires planted boots, pelvis-led seated-to-standing weight transfer, chair contact, and clothing settle.
- GS040 requires simultaneous face, ledger, pencil, mug, and two-hand readability.
- GS050 requires a muted emotional turn that reads without dialogue.
- GS060 requires a constrained pencil set-down and a whole-body coffee pour.
- GS070 requires mug release, gaze return, restrained direct address, and a live 27-frame hold.

Landscape and portrait are separate layouts. Passing a landscape crop does not approve portrait.

## Honest boundary and next build

The story reel proves story, identity targets, composition, pacing, captions, and sound delivery. Its character motion is editorial camera motion across style frames. It does **not** prove final mesh deformation, coarticulated facial acting, hand constraints, foot locks, cloth, coffee simulation, or temporally persistent ink.

The next asset milestone is therefore one 12–15 second GS030→GS050 performance section on an authored deforming June rig. It must match these targets before the pipeline scales to all seven shots. That rig needs weighted topology, IK/FK, foot roll, clavicle/spine/twist controls, fingers, jaw/lips/cheeks/gaze, corrective shapes, and explicit chair/mug/ledger contacts.

## Zero-cash provenance

- Piper executable: `rhasspy/piper` release `2023.11.14-2`, version 1.2.0 — https://github.com/rhasspy/piper/releases/tag/2023.11.14-2
- Piper voice collection and `en_US-ryan-medium`: MIT-licensed — https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ryan/medium
- FFmpeg: local installed executable — https://ffmpeg.org/
- Blender: workflow-pinned 4.2.0 binary — https://www.blender.org/

The Piper performance is non-canonical scratch audio. A final release requires a consensual local human recording or an explicitly approved canonical June voice asset.
