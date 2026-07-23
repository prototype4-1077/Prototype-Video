# Local cartoon animation backend (limited_2_5d)

Zero-cost-by-default, coherent character-based cartoon animation. No paid API required.

## Render modes
- **limited_2_5d** (default): local layered puppet animation via PIL+FFmpeg. Independently
  moving layers (bg/mid/fg, torso, head, eyes, arms, props, particles, shadows, light) with
  blink/nod/breath/gesture/steam/parallax + motivated camera. `cartoon_renderer.py`.
- **local_i2v** (optional): adapter seam for local ComfyUI/Wan when GPU infra exists.
- **paid_i2v** (optional, OFF by default): `video_gen.py` (Replicate). Gated by
  `cartoon_budget.py` — cannot run without an approved `generation-budget.json`.

## Modules
`cartoon_renderer.py` (compositor+validate) · `cartoon_motion.py` (motion curves) ·
`cartoon_assets.py` (auto chroma-key cutouts, eye-band blink, procedural steam) ·
`cartoon_continuity.py` (master sequences) · `cartoon_budget.py` (paid gate) · `video_gen.py` (paid adapter).

## Compliance floor (enforced in `cartoon_renderer.validate`)
>=3 independently moving layers, >=2 active regions, motion beyond a global pan/zoom,
character scenes need subject motion, object scenes need object/env motion. Stock forbidden.

## Cost
limited_2_5d = $0. paid_i2v only runs after per-build budget approval within `paid_i2v_scene_limit`.
