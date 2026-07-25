# Liam Intention Delivery Profile

The Liam voice is treated as a warm, sly, brilliant friend speaking with the viewer at midnight. The delivery system directs communicative intention rather than applying broad emotion to every scene.

## Script-source precedence

A complete script supplied by James remains authoritative. Do not silently rewrite, restructure, shorten, or force it into the default arc. Delivery metadata may be added only when the spoken words remain unchanged and the request permits a delivery pass. An attached or pasted full script takes precedence over a concept brief, outline, house template, or automatic role inference.

The writing template below is a preference only when no complete script is supplied.

## Default script-and-voice arc

For a new Concept Engine script, target approximately 24 short scenes and 330–340 spoken words. Hold one ruling metaphor throughout and write the prose so it still performs naturally after every tag is removed.

| Scenes | Writing job | Delivery role |
|---|---|---|
| 1–2 | One-breath concrete hook; surprising without explaining | `hook` |
| 3–5 | State the ordinary viewer assumption fairly | `setup` |
| 6–7 | Release pressure with humor from the ruling metaphor | `comic` |
| 8–12 | Explain one causal step at a time; reduce poetry | `mechanism` |
| 13–16 | Reinterpret what the mechanism means personally | `turn` |
| 17–18 | One or two short whisperable knife lines | `knife` |
| 19–20 | Restore warmth, remove shame, return agency | `setup` or `turn` |
| 21–22 | Return to room, body, hands, breath, or an ordinary object | `grounding` |
| 23–24 | Hand over one open, testable question | `invitation` |

Science claims must be labeled `established`, `emerging`, or `metaphor`. The mechanism must become clearer than the poetry. The final invitation is not whispered by default.

## Writing for the voice

- Write in speakable breath groups rather than dense paragraphs.
- Vary sentence lengths; do not ask tags to manufacture emphasis.
- Put important words near phrase endings.
- Build pauses at real thought boundaries, not every visual cut.
- Use serious setup → absurd extension → clean exit for humor.
- Prefer amused delivery over audible laughter.
- Place a chuckle after the payoff, never before it.
- Keep the knife line brief, nontechnical, and free of immediate jokes.
- Restore ordinary warmth after a whisper.
- End with a genuine question the script does not answer.

## Scene fields

- `delivery_role`: `hook`, `setup`, `comic`, `mechanism`, `turn`, `knife`, `grounding`, or `invitation`
- `pause_before`: `short`, `beat`, or `long`
- `reaction`: `chuckle`, `laugh`, or `sigh`
- `is_knife_line`: forces the sparse whisper treatment
- `audio_tags`: remains the exact per-scene override and takes precedence over semantic fields

Scene metadata should describe an intention already present in the prose, not compensate for weak writing.

```json
{
  "text": "You may not be defending reality.",
  "delivery_role": "knife",
  "pause_before": "beat",
  "is_knife_line": true
}
```

## Default delivery arc

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
