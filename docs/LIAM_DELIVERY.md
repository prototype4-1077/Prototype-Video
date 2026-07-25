# Liam Intention Delivery Profile

The Liam voice is treated as a warm, sly, brilliant friend speaking with the viewer at midnight. The delivery system directs communicative intention rather than applying broad emotion to every scene.

## Scene fields

- `delivery_role`: `hook`, `setup`, `comic`, `mechanism`, `turn`, `knife`, `grounding`, or `invitation`
- `pause_before`: `short`, `beat`, or `long`
- `reaction`: `chuckle`, `laugh`, or `sigh`
- `is_knife_line`: forces the sparse whisper treatment
- `audio_tags`: remains the exact per-scene override and takes precedence over semantic fields

## Default arc

1. Hook: curious and slightly forward-moving.
2. Setup: thoughtful baseline.
3. Comic beat: mischievous delivery; reactions remain explicit and sparse.
4. Mechanism: matter-of-fact clarity.
5. Turn: slower delivery.
6. Knife line: whisper only when explicitly identified.
7. Grounding: calm return to the room, body, or breath.
8. Invitation: curious normal voice, never an automatic whisper.

## Guardrails

The voiceover manifest records a `delivery_analytics` section. It warns when:

- more than two whisper passages are requested,
- more than four nonverbal reactions are requested,
- more than half the scenes are directed,
- or the final invitation is whispered.

Warnings do not block rendering. They make over-direction visible while preserving intentional exceptions.

## Compatibility

- Existing `scene.audio_tags` remain authoritative.
- `liam_delivery_profile: false` disables automatic semantic direction while preserving explicit tags.
- Performance tags never enter scene text or captions.
- The delivery profile is included in the TTS fingerprint, so stale audio is regenerated when the profile changes.
