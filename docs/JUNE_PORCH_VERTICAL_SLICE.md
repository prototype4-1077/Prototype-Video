# June Porch Dialogue — Production Vertical Slice

This phase proves a complete cartoon production path on one short, authored
performance before the renderer is expanded to full episodes. It is deliberately
more than a moving illustration: June has a reusable armature, separate body
actions, real timed mouth shapes, blinking, three camera setups, a dressed porch,
a visible warm light source, and independent environmental motion.

## What the slice proves

- **Explicit character identity:** the plan must select `june_oxley`; a generic
  host cannot silently replace him.
- **Animatic first:** three authored shots compile onto one continuous 30 fps
  timeline before Blender starts.
- **Reusable performance system:** breathing, head acting, and gestures are
  separate Blender NLA actions; blinking and visemes remain independently timed.
- **Audio-driven mouth timing:** Rhubarb Lip Sync generates `A`–`H`/`X` mouth
  cues from the actual voice track. Silent gaps are closed and malformed or
  overlapping cues fail before render.
- **Production-safe media flow:** Blender writes PNG sequences, FFmpeg assembles
  H.264/AAC deliverables, and GitHub uploads the results as artifacts. Frames,
  audio, and video are not committed.
- **Two canonical canvases:** YouTube is 1920×1080 and portrait is 1080×1920;
  both use the repository's shared 30 fps. Proof mode renders at 25% scale.

The code-native set and character are an integration asset, not the final art
model. That choice makes the production contract reproducible in headless CI and
keeps binary `.blend` files out of source control while the visual language is
still being approved.

## Files

- `examples/june-porch-vertical-slice.json` — authored dialogue, shot, character,
  set, and performance brief.
- `pipeline/cartoon_vertical_slice.py` — validates and compiles the shot plan,
  invokes Blender, assembles videos, and creates contact sheets.
- `pipeline/cartoon_lipsync.py` — Rhubarb runner and frame-clock adapter.
- `pipeline/blender/render_vertical_slice.py` — procedural June rig, porch set,
  actions, cameras, toon look, and PNG-sequence renderer.
- `.github/workflows/blender-cartoon-proof.yml` — pinned, manual CI proof worker.

## Local plan check (Blender not required)

```bash
python -m pipeline.cartoon_vertical_slice \
  examples/june-porch-vertical-slice.json \
  --profiles youtube portrait \
  --quality proof \
  --plan-only \
  --output-dir build/june-porch-plan-check
```

## Local render

Provide Blender 4.2+, FFmpeg, Rhubarb 1.13.0, and a final or temporary WAV:

```bash
python -m pipeline.cartoon_vertical_slice \
  examples/june-porch-vertical-slice.json \
  --audio path/to/june-dialogue.wav \
  --rhubarb path/to/rhubarb \
  --blender path/to/blender \
  --profiles youtube portrait \
  --quality proof \
  --output-dir build/june-porch-proof
```

Use `--quality production` only after the proof contact sheets are approved. It
switches to full canvas sizes and requests Blender's production EEVEE renderer;
the script retains a headless-safe fallback.

## Acceptance gate

The slice is ready to expand only when the rendered artifact confirms all of the
following:

1. June reads as the intended older Southern man without cowboy caricature.
2. Each spoken beat has a deliberate composition and performance change.
3. Mouth cues track consonant/vowel changes and return to closed during silence.
4. June, camera, and at least one environmental element move independently.
5. Landscape and portrait crops both preserve eyes, hands, and the visible light.
6. The run can be reproduced from a clean GitHub worker without committing media.
