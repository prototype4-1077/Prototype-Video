# Host-avatar v2 technique (the ghost fix)

North-star: the two approved June target frames (porch/kindness + diner/roadblocks).

1. INTEGRATED GENERATION (root fix): each host scene is ONE generated image with June
   painted into the corner-host position — correct light, shadows, occlusion. No cutout
   compositing => ghosting impossible. Style+seed-locked prompt keeps him consistent.
2. STACKED EFFECTS on the still (multiple tools at once):
   - Dual-frame talk cycle: same seed, mouth-closed (A) + mouth-open (B) variants,
     blended in the host region at speech rhythm (syllable flutter + word pauses).
     Frame-to-frame generation variance reads as hand-drawn line-boil life.
   - Deep-page camera: slow push + micro drift, background plane counter-drift (parallax).
   - Near-plane dust/pollen drift.
   - (Available to stack next: MiDaS depth-map true multiplane — onnxruntime present;
     blink band; concept props layer from cartoon_renderer.)
3. Reroute: hero endpoint not needed — art generated directly (fixes GPT's blocked hero step).

Spec fields honored: host_avatar_mode(enabled, corner=lower_right, scale=medium,
lip_sync_required, idle_motion_required), host_grounding(full opacity via integration),
deep_parallax_required(push+counter-drift+dust planes), concept_background_required
(open gate + path + town = kindness-with-boundaries porch concept).
