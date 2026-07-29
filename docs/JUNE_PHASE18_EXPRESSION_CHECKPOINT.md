# June Oxley Phase 18 expression checkpoint

Date: 2026-07-29

Status: an identity-locked upper-face atlas now adds authored blinks, brows, gaze, and emotional progression to the exact 453-frame A/V performance locally. Public reproduction remains the next gate.

## Source art

Phase 18 uses a second 3x3 source atlas generated with the built-in image generator from both the canonical turnaround and the exact Phase 16 neutral portrait.

| Asset | Contract |
| --- | --- |
| `concept/style_frames/june_oxley_expression_atlas_v1.png` | 1254x1254 RGB, exact 3x3 cells, SHA-256 `23a1e4fd24ca13ada1c34722905528b052993c0f37477195f13d2a5b6bcf462b` |
| `concept/style_frames/june_oxley_expression_atlas_v1.json` | Identity, paired-viseme hash, order, upper-face crop, feathering, invariants, provenance, and visual gates |
| `concept/style_frames/june_golden_scene_expression_cues_v1.json` | Fourteen authored states on the exact 453-frame, 15.1-second clock, SHA-256 `5ad1e61837c6fad56f13baff5929fc513bb61417a85f065a447c84727e344d5a` |
| `pipeline/cartoon_expression_atlas.py` | Contract validator, cell compiler, feather mask, exact-clock state planner, and cubic transitions |

Atlas order:

```text
neutral       blink        squint
brow_raise    brow_knit    concern
warm_eyes     gaze_down    compassion
```

The atlas is the actual upper-face render source. It is not merely a style target. A feathered eye/brow/forehead/upper-cheek crop is composited over a fixed neutral cell, followed by the independent viseme crop. This ordering lets emotional acting change eyes and brows without corrupting mouth timing, beard flow, or dental art.

## Authored performance

- Neutral attention establishes the line.
- A complete blink lands in the first pause.
- Brow raise and warm eyes support the returned-mug/pie beat.
- Brow knit supports the courthouse exaggeration.
- A second blink resets into the ledger joke.
- Squint, concern, downward gaze, and compassion progressively carry the emotional turn.
- The last 1.45 seconds remain in the quiet compassion state while the mouth returns to X.

The cue contract forbids gaps, overlaps, unknown states, mismatched frame clocks, and unsafe transition lengths. Blinks use two-frame transitions; the final compassion move uses six frames.

## Local evidence

Output directory: `outputs/edit/phase18-expression-performance`

| Property | Verified value |
| --- | --- |
| Video | `june-2p5d-lipsync-performance.mp4` |
| Video SHA-256 | `c369ed374b21c8554297f44087545481fff50a1a011ef666d30f1c395809285a` |
| Video | H.264/yuv420p, 836x836, 30 fps, 453 frames |
| Audio | AAC, 48 kHz, stereo |
| Video/audio duration | 15.100 seconds / 15.100 seconds |
| Expression cues/states | 14 / all 9 |
| First frame SHA-256 | `800bde740386391ed374ac56d5b916deff3913a81e8d45b80b7e4b625519a336` |
| Final compassion frame SHA-256 | `5aa45e703211a47c7b7c21b60db78ca08e32b381b333e9ca0751dac1a2e72bc8` |

Verification:

- Twelve focused expression/viseme tests pass.
- The complete pipeline regression passes: 320 tests run, 3 optional-dependency skips, 0 failures.
- The encoded A/V file decodes completely without an FFmpeg error.
- FFprobe confirms the exact video and audio contracts above.
- Rendered-output timelines inspect the first blink, brow-raise/warm-eye beat, brow-knit/second-blink beat, and the complete concern-to-compassion turn.

## Honest visual gate

Passed:

- Both eyelids close naturally and reopen without changing June's head silhouette.
- Brow raise, knit, concern, and compassion are clearly distinct at playback scale.
- Gaze moves down without a head turn.
- Upper-face and mouth layers remain visually coherent through dense speech.
- The final stillness now communicates an emotional choice instead of reading as a frozen talking head.
- Painted skin, wrinkle, pupil, eyelid, hair, beard, and cloth detail survive the complete performance.

Not passed:

- Head, neck, shoulders, and torso are still one flat card.
- There is no independent breathing, head arc, gaze-lead rotation, or shoulder counter-motion.
- The close-up is still square and not yet composited into the porch/body/hand/prop performance.
- Whole-character angle coverage still needs 3/4 and profile source sets.
- Scratch Piper audio remains non-canonical.

## Recommended next gate

Split the neutral portrait into head, near shoulder, far shoulder, and torso layers with overlap-safe mattes. Add a bounded 2.5D motion contract: gaze leads head by 2-4 frames, head rotates only a few perspective-safe degrees, shoulders counter by a smaller amount, breaths occur at authored silence windows, and the final compassion hold settles completely. Then composite this high-fidelity close-up over a 1920x1080 Blender porch/body/hand/prop pass using Blender depth and contact shadows while preserving the atlas face as a camera-facing textured card.

Reinforcement learning can then compare bounded timing/warp candidates. The reward should combine human pairwise preference with hard penalties for eye-mouth desynchronization, identity drift, patch seams, temporal flicker, excessive bob, broken holds, and disagreement with the authored emotional state.
