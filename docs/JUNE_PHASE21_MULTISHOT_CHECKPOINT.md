# June Oxley Phase 21 multi-shot checkpoint

Date: 2026-07-29

Status: the 15.1-second June performance is now a real six-shot edit. Two full-resolution tactile paintings enter the encoded sequence as actual mug and ledger shots, while the Phase 20 performance remains the only source of June's visible face, expressions, lip-sync, body motion, and continuous audio clock. The local A/V master, full decode, cut-boundary review, and encoded-detail gate pass; public reproduction is the next gate.

## What changed

The earlier style frames were a visual map. Phase 21 promotes that approach into the renderer:

- High-detail insert art supplies the final pixels for shots where hands and props matter most.
- The registered Phase 20 performance supplies every visible face and spoken mouth, preventing identity changes between paintings.
- A versioned edit contract owns source hashes, exact frame ranges, camera moves, effects, continuity invariants, and visual gates.
- The renderer reads every source-performance frame in order, substitutes only contracted insert ranges, preserves the original audio stream without cutting it, and emits one exact 453-frame master.

This is a hybrid animation pipeline: authored/generative key art carries finish; deterministic local code carries timing, motion, identity, compositing, validation, and delivery.

## Production inserts

Both insert plates are 1672x941 RGB and were generated through the built-in image tool from local registered references. They require no paid runtime or API key.

| Plate | Purpose | SHA-256 |
| --- | --- | --- |
| `june_oxley_mug_held_insert_v1.png` | Midair mug macro matching the completed Phase 20 lift; stable chip, rim, handle, hand, sleeve, lighting, and clear support separation | `857e2e1584170d9264b0806bf74ae64e0a9a3845e0e6a1711c6b3897c2d2389c` |
| `june_oxley_ledger_insert_v1.png` | Face-free pencil/ledger macro for the compassion turn; one short pencil, one closed ledger, one readable elderly hand | `6b11c1c41455b7e44851146c459a3299bef8c0d7082ac6025701fdde097d87d7` |

Image-generation provenance:

- Mug source: `exec-23203714-7d56-48ff-906a-94e648b3ed7e.png`; references were the GS020 v2 mug macro and registered Phase 20 mug-lift drawing.
- Ledger source: `exec-ebdfc803-6481-4196-93dc-85cdb1fff39d.png`; references were the registered pencil-contact drawing plus GS040 and GS020 v2 material/composition targets.
- Prompt mode: `illustration-story`, reference-guided production generation.
- Mug prompt summary: exact lifted cream enamel mug and weathered left hand, macro framing, stable chip/blue rim, five-finger contact, no face/table contact/extra props.
- Ledger prompt summary: exact weathered right hand, short yellow pencil poised above the closed ledger, macro framing, no face/alternate identity/extra anatomy.

## Edit contract

`concept/style_frames/june_golden_scene_multishot_v1.json` content-addresses both inserts and every reference used to derive them. It also requires the input performance and output to remain 1920x1080, 30 fps, 453 frames, and 15.100 seconds.

| Frames | Shot | Source | Editorial function |
| --- | --- | --- | --- |
| 1-50 | `GS010_HERO_SETUP_AND_MUG_LIFT` | Phase 20 performance | Establish canonical June and show the authored mug lift begin. |
| 51-114 | `GS020_MUG_CHIP_INSERT` | Mug macro | Hold on tactile enamel/hand detail with a 3.5% eased push and animated steam. |
| 115-306 | `GS030_HERO_RETURN_AND_LEDGER_REACH` | Phase 20 performance | Match back to the lifted mug, lower it, preserve dialogue acting, and reveal the pencil lift. |
| 307-378 | `GS040_LEDGER_PENCIL_INSERT` | Ledger macro | Let hand, pencil, leather, and wood detail carry the realization with a 4% eased push. |
| 379-392 | `GS045_HERO_PENCIL_RETURN` | Phase 20 performance | Match back to the pencil pose and show the return. |
| 393-453 | `GS050_IDENTITY_LOCKED_COMPASSION_CLOSEUP` | Cropped Phase 20 performance | Cut to the same moving face at 1.5x-1.58x while retaining expression and lip-sync continuity. |

Cut frames are exactly `51, 115, 307, 379, 393`. The underlying audio is never segmented, faded, or re-encoded; it remains one continuous source stream.

## Renderer and automated gates

`pipeline/cartoon_shot_sequence.py` provides:

- strict source, hash, dimensions, zero-cash provenance, clock, shot coverage, camera, and effect validation;
- bounded 16:9 cover crops with cubic camera easing and no nonuniform stretch;
- deterministic steam and warm-light micro-motion on the insert paintings;
- sequential base-video decoding so every visible mouth remains on its original audio frame;
- H.264/yuv420p raw-frame streaming to FFmpeg with atomic publication;
- optional byte-preserving AAC passthrough when the base performance contains audio;
- first/middle/last review frames for every shot;
- a second complete encoded-video decode and PSNR/detail measurement before the result can pass.

The contract rejects an encoded master if any of the eighteen review frames falls below 38 dB PSNR or below 30 Laplacian-variance units. These are delivery-retention gates, not aesthetic substitutes; the cut sheets and full-resolution frames still require visual inspection.

## Local evidence

Output directory: `outputs/edit/phase21-multishot-v1`

| Property | Verified value |
| --- | --- |
| Video | `june-golden-scene-multishot.mp4` |
| Video SHA-256 | `3e6674977e41ec548990426f35e703bc92489aca33308948707125fefc68a128` |
| Video | H.264/yuv420p, 1920x1080, 30 fps, 453 frames |
| Audio | AAC, 48 kHz, stereo, 15.100 seconds |
| Video duration | 15.100 seconds |
| Encoded size/bit rate | 10,346,536 bytes / 5,481,608 bits per second |
| Sequence-contract SHA-256 | `fecaa35202524ed6764a66b373adf9a8aff43adb84ce4a2384d402787ca46827` |
| Review-frame samples | 18: first, middle, and last frame of all six shots |
| Minimum/mean encoded PSNR | 40.644 dB / 42.095 dB |
| Minimum encoded detail variance | 43.814 |
| Audio packet SHA-256 | `c3c90fbae0fc42f89efbb9f715372d260b5df5c0bbdd18b32d8d077c1881a71b`, identical before and after the edit |

Verification:

- Seven focused Phase 21 tests pass; the complete pipeline regression passes 338 tests with one optional-dependency skip and zero failures.
- FFmpeg decodes the complete final A/V file without error.
- FFprobe confirms both streams share the exact 15.100-second duration.
- Five cut-centered filmstrips inspect every edit with the continuous waveform beneath it.
- Full-resolution before/after cut frames verify matching mug height, pencil state, environment, palette, and identity.
- The final close-up uses sequential Phase 20 frames, so the facial performance continues rather than freezing or switching models.
- No optical flow, face generation, temporal interpolation, or alternate character painting enters the edit.

## Honest visual gate

Passed:

- The finished render now reaches the high-detail still-art level during the mug and ledger inserts because those paintings are the final shot pixels.
- Mug and ledger cuts land after their corresponding Phase 20 lift motions and return to matching poses.
- The macro inserts retain skin folds, denim weave, enamel wear, leather cracks, wood grain, depth of field, and golden-hour lighting after encoding.
- Steam survives the H.264 encode and moves independently of the camera push.
- June's face remains one registered identity throughout every visible facial shot.
- The emotional close-up retains moving eyes, mouth, brows, head, shoulders, atmosphere, and the original frame clock.

Not passed yet:

- This is a six-shot 15.1-second performance slice, not yet the complete 38.8-second seven-shot Golden Scene.
- The macro inserts use camera/effect motion rather than fully articulated finger animation.
- June still lacks registered three-quarter and profile facial atlases for speaking turns at new angles.
- Seated-to-standing, walking, coffee-pour/liquid, and final offering-hand mechanics remain outside this slice.
- The local Piper dialogue is a timing voice, not the approved final June performance.
- Designed porch ambience, mug/wood/pencil Foley, music, and final loudness mastering remain unintegrated.

## Recommended next gate

Publish and independently reproduce this exact multi-shot artifact. Then expand the picture contract to the full 38.8-second seven-shot Golden Scene rather than polishing this slice indefinitely: build registered GS030 standing mechanics, GS060 coffee-pour/liquid mechanics, and GS070 wide/portrait resolution coverage; add angle-specific face atlases only where a speaking face is visible. After picture lock, produce a zero-cash local voice/ambience/Foley mix and master the completed scene.
