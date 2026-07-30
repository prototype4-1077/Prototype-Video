# June Oxley Phase 26 — Sound-Finished Golden Scene Checkpoint

## Outcome

Phase 26 turns the accepted 38.8-second picture lock into a sound-finished short without changing a single encoded picture packet. The delivery now contains frame-locked June dialogue, porch ambience, body and prop Foley, a mastered stereo mix, an intentionally empty music stem, soft English captions, and an SRT sidecar.

The still references remain the art-direction map. Phase 25 proved that production pixels can approach that map. Phase 26 adds the temporal half of the cartoon—the performance, physical contacts, atmosphere, and editorial sound cues that make those pixels feel inhabited.

## Production contract

- Sound contract: `concept/style_frames/june_golden_scene_master_sound_v1.json`
- Deterministic renderer: `pipeline/cartoon_golden_sound.py`
- Focused regression: `pipeline/tests/test_cartoon_golden_sound.py`
- Pinned dialogue source: `concept/audio/june_golden_scene_dialogue_norman_v1.wav`
- Source clock: 48,000 Hz mono, 1,862,400 samples, exactly 38.8 seconds
- Picture clock: 30 fps, 1,164 frames, exactly 38.8 seconds
- Captions: 18 frame-derived cues, soft `mov_text` plus UTF-8 SRT

The dialogue is generated locally with Piper `en_US-norman-medium`. Its pinned model card identifies LibriVox as the public-domain dataset and says the model was trained from scratch. The runtime model, config, model card, and generated dialogue are all SHA-256 pinned. A human casting decision is still required before claiming that this is June's final voice.

## Sound design

The renderer synthesizes and exports these exact-clock PCM24 stems:

| Stem | Purpose |
| --- | --- |
| `DX_JUNE_MONO` | Frame-fitted June performance |
| `FOLEY_PROP_MONO` | Mug, ledger, pencil, coffee pot, and pour contacts |
| `FOLEY_BODY_STEREO` | Chair, cloth, boots, and breaths |
| `AMB_PORCH_STEREO` | Wind, leaves, insects, and four staged chime events |
| `MUSIC_EMPTY` | Explicitly silent; the scene is intentionally unscored |
| `MIX_PREMASTER_STEREO` | Performance-weighted dialogue and ducked scene stems |
| `MIX_MASTER_STEREO` | Two-pass EBU-style loudness-normalized master |

Twenty-six events cover all nine required Foley categories in the Golden Scene story contract. Dialogue activity ducks ambience and body sound, while phrase-level gains create a four-stage dramatic arc: setup, comic expansion, compassionate hush, and direct-address resolution.

## Local accepted evidence

Local delivery directory:

`outputs/edit/phase26-sound/full-render-v2/`

| Gate | Result |
| --- | ---: |
| H.264 / yuv420p | pass |
| Resolution | 1920 × 1080 |
| Frame rate / frames | 30 fps / 1,164 |
| Duration | 38.800000 s |
| Audio | AAC, 48 kHz, stereo, 256 kb/s target |
| Captions | `mov_text`, English, plus SRT sidecar |
| Integrated loudness | −16.06 LUFS-I master / −16.07 LUFS-I AAC |
| Loudness range | 4.5 LU |
| True peak | −1.29 dBTP master / −1.28 dBTP AAC |
| Picture stream SHA-256 | `353441e6995b76494853b55910174573777f35dee319b8613466bd67ffa28851` |
| Picture re-encoded | no |
| Full video/audio decode | pass |

Pinned local hashes:

- Dialogue WAV: `2cb1fc40d7c03d726e6f7310dda957014ce2bc6c692df41b8ef5c26f0c6171ce`
- Final MP4: `03d9104456ea89285d29f9d8a49ccac15cdc4ae3b7d3bd93d84ebbcee1060131`
- Report: `b2478250670437da548eb9ac362673a9092a7a293aa5587693593f1d2563c8dc`
- SRT: `0100c2c967673cc4ded334f00050c37a0a3f231362590401aa9bb05b6081239e`

The waveform review shows clean phrase separation, intentional quiet beats, visible contact transients, and a tapered final porch hold. The spectrum shows continuous low-level porch air, intelligible speech-band energy, sparse chime harmonics, and no hard clipping shelf.

## Reproduction

The public workflow must first build the exact Phase 25 picture master. It then runs:

```bash
python3 -m pipeline.cartoon_golden_sound mix \
  concept/style_frames/june_golden_scene_master_sound_v1.json \
  --picture-video build/edit/june-golden-scene-master/june-golden-scene-master.mp4 \
  --picture-report build/edit/june-golden-scene-master/june-golden-scene-master-report.json \
  --output-dir build/edit/june-golden-scene-sound-master
```

The delivery gate fails on a missing or changed dialogue asset, incomplete Foley map, off-clock source, non-H.264/yuv420p picture, video re-encode, missing AAC/caption streams, frame or duration drift, loudness outside −16 ± 1 LUFS-I, LRA outside 4–8 LU, final AAC true peak above −1 dBTP, or any decode error. The PCM master reserves 0.3 dB of encoding headroom and the renderer meters the encoded AAC again before acceptance.

## Remaining limitation and next move

Sound completion makes the current short usable as a scored-free narrated micro-cartoon, tone proof, episode pitch, style benchmark, and regression fixture. It does not turn a limited 2.5D performance into feature-animation character motion. The largest remaining visual gap is reuse: June's body, costume, hair, hands, face, and props still depend on shot-specific production plates.

The recommended next phase is a reusable high-resolution June performance rig: layered vector/raster parts backed by a Blender 2.5D deformation skeleton, angle-specific face/hand atlases, deterministic prop constraints, and the current picture/sound gates as its acceptance oracle. That converts the beautiful reference map into an animation system that can produce new scenes rather than one carefully authored scene.
