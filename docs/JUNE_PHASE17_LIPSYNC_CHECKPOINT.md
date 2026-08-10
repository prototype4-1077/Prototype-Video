# June Oxley Phase 17 lip-sync checkpoint

Date: 2026-07-29

Status: the high-fidelity atlas performs a real 15.1-second, audio-matched dialogue clock locally, and the 453-frame cue mode is independently reproduced in public CI.

## What changed

`pipeline/cartoon_viseme_atlas.py` now has two render modes:

- The Phase 16 A-H/X audition cycles all nine art states for direct review.
- Phase 17 samples validated Rhubarb cues at each frame center, applies two-frame cubic coarticulation, and optionally muxes the exact source audio used to generate those cues.

The performance renderer:

- normalizes and validates Rhubarb JSON with the existing cartoon lip-sync bridge;
- keeps the exact cue duration and `round(duration * fps)` frame clock;
- writes a 2.5D patch blend per frame while retaining X as the stable identity base;
- clears stale numbered frames;
- limits FFmpeg to the exact planned frame count;
- writes H.264/yuv420p plus AAC 48 kHz stereo when audio is supplied;
- atomically promotes the completed video;
- records atlas, cue, audio, first-frame, last-frame, and video hashes.

## Local scratch-performance provenance

The dialogue is the existing Golden Scene GS030-GS050 text:

> Three years later, he brought the mug back, plus a pie his wife made, apologizing like he'd misplaced the courthouse. I reached for my little ledger... then watched his hand shake.

This pass uses the already documented free local toolchain:

- Piper 1.2.0 with the MIT-licensed `en_US-ryan-medium` model.
- Rhubarb Lip Sync 1.14.0 with its dialogue hint.
- FFmpeg 8.1.1 locally.

The raw Piper take was 9.523537 seconds. It was pitch-preserving time-fitted to the unchanged 15.1-second performance clock with `atempo=0.630697815`, padded/trimmed exactly, converted to 48 kHz stereo PCM, and then sent to Rhubarb. This is a non-canonical scratch voice, not a release voice.

## Local output evidence

Output directory: `outputs/edit/phase17-cue-performance`

| Property | Verified value |
| --- | --- |
| Video | `june-2p5d-lipsync-performance.mp4` |
| Video SHA-256 | `abcc5c35fe7869682d965713a189f32c57177c2bb60c036f0a145ce622aa4da2` |
| Audio SHA-256 | `247908b9908203fbc3ab727247345d05831bc4a1292672bf0a514457668a8620` |
| Rhubarb cue SHA-256 | `8d6a19d6b94a37ec97a0d70b823ee020cf84c93fa328ea55a4225071887387a7` |
| Source/normalized cues | 83 / 83 |
| Mouth shapes exercised | A, B, C, D, E, F, G, H, X |
| Video | H.264/yuv420p, 836x836, 30 fps, 453 frames |
| Audio | AAC, 48 kHz, stereo |
| Video/audio duration | 15.100 seconds / 15.100 seconds |
| First/last frame SHA-256 | `d06541d8fe4c3ff978c3ddc2d35465dd1c28fb89096592366b179b1ffaa2d8f5` |

Verification:

- Seven focused atlas/performance tests pass; the full local pipeline regression passes 315 tests with 3 expected skips.
- The complete encoded file decodes without an FFmpeg error.
- FFprobe confirms the exact clock and both stream contracts above.
- Four rendered-output timelines inspect 0.0-2.2, 5.0-7.2, 10.5-12.7, and 13.0-15.05 seconds with their audio waveforms.
- The mouth is closed during leading/final silence and changes densely with voiced regions.
- Two-frame cubic blends prevent hard sprite pops at sampled cue boundaries.

## Honest visual gate

Passed:

- The atlas-quality skin, hair, beard, moustache, lips, teeth, tongue, and mouth cavity survive an actual speech clock.
- Audio and animation share the same Rhubarb source, eliminating the earlier risk of demonstrating unrelated mouth motion over a voice track.
- Identity, camera, gaze, and wardrobe remain stable across all 453 frames.
- The final X hold is fully closed and byte-identical to the first neutral frame.

Not passed:

- Eyes and eyebrows remain frozen; no blink, gaze, lower-lid, or compassion-release layer exists yet.
- The head and shoulders are one card, so there is no independent head turn, breathing, or parallax.
- The square close-up is not yet composited into the 1920x1080 porch/body/prop performance.
- The time-fitted Piper voice is useful proof audio but is not June's canonical release performance.
- Patch crossfades preserve quality but do not yet use a deformation mesh to carry lip corners and cheek mass between source states.

## Public Phase 17 evidence

- Run: `https://github.com/prototype4-1077/Prototype-Video/actions/runs/30498462761`
- Head: `f7dee57a6cc649bd1aef7095e626ef703e9f11e5`
- Full `test` job passed in 2m17s, including regression, both atlas renders, full decode, exact ffprobe gates, and both artifact uploads.
- The inherited Blender v8 regression also passed in 6m23s.
- Artifact: `june-2p5d-lipsync-performance-v1`.
- Public video: H.264/yuv420p, 836x836, 30 fps, 453 frames, 15.100 seconds.
- Public video SHA-256: `30f932577d4e7f3fee468be3e81e2e08fcdd38bdd1c811f7abfbd87ecae82954`.
- Public cue SHA-256: `4e59733c26f519fd9f7b596a163a6c58e4fcb90c4525063a5fb0a71732eccc5c` with all 77 canonical cues and all nine shapes.
- Public first and last frame SHA-256: `1f6c51238f87455c1a4495ff98ae9cfa58a7ee2c1cd75e76c57c155f4db8fddd`.
- The downloaded public artifact decoded cleanly and its 24-frame full-runtime timeline passed visual inspection.

The public artifact is intentionally silent because downloaded voice models and generated scratch audio stay outside Git. The local A/V gate proves exact audio coupling; the public artifact proves the complete cue-driven picture path independently.

## Recommended next gate

Create an identity-locked expression/eye atlas for neutral, blink, squint, smile, concern, lower-lid engagement, brow raise, and brow knit. Split the portrait into head, near shoulder, far shoulder, and torso planes, then render the same 453-frame audio performance with designed blink/gaze/emotional beats and subtle depth-safe head/shoulder motion. Only after that close-up passes should the face be composited over the Blender porch/body/hand/prop render at 1920x1080.

The first useful learning loop should optimize bounded timing and blend controls—not generate art blindly. Candidate parameters are cue anticipation, coarticulation length, blink timing, gaze lead, emotional-layer weights, patch warp, and parallax. Reward combines pairwise human preference with hard penalties for lip-sync error, seam energy, identity drift, temporal flicker, and missed final hold.
