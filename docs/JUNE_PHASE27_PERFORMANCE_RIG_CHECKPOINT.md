# June Oxley Phase 27 — Reusable Multi-View Performance Rig Checkpoint

## Outcome

Phase 27 converts three accepted production-pixel renderers into one reusable June performance interface. A single pinned rig manifest now drives broad body mechanics, constrained hand/prop/liquid mechanics, and close speaking performance through semantic animation channels instead of treating the three shots as unrelated scripts.

The result is an honest multi-view production rig, not a claim that one flat puppet can synthesize every pose or angle. The approved paintings still define the visual map; the rig makes their pixels controllable, testable, repeatable, and usable in a new edit without cutting up the finished Phase 26 movie.

## Rig architecture

- Rig manifest: `concept/characters/june_oxley_performance_rig_v1.json`
- Shared renderer: `pipeline/cartoon_performance_rig.py`
- Focused regression: `pipeline/tests/test_cartoon_performance_rig.py`
- Canonical identity: SHA-256 pinned
- Nested adapter contracts and dependencies: SHA-256 pinned
- Runtime cash cost: zero

The common interface exposes ten semantic channels:

`body_pose`, `root_contact`, `hand_contact`, `prop_pose`, `liquid`, `viseme`, `expression`, `head`, `camera`, and `atmosphere`.

| Action | View adapter | Frames | Primary proof |
| --- | --- | ---: | --- |
| `STAND_UP` | `WIDE_BODY_3Q` registered pose layers | 171 | planted feet, chair contact, mug continuity |
| `POUR_COFFEE` | `TABLE_MEDIUM_3Q` registered pour layers | 258 | bounded pot/mug contact, spout continuity, zero rendered spill |
| `DIRECT_ADDRESS` | `CLOSE_HERO_FRONT` feature atlases | 228 | identity-safe eyes/mouth, visemes, expression, nod, final hold |

The renderer regenerates all three actions from their pinned production layers, concatenates the H.264 action streams without transition interpolation, rebases the accepted Phase 26 sound regions and captions to the new 657-frame clock, and muxes the final audio/captions without re-encoding the combined picture stream.

## Local accepted evidence

Accepted delivery directory:

`outputs/edit/phase27-performance-rig/full-render-v2/`

| Gate | Result |
| --- | ---: |
| Delivery | H.264/yuv420p, 1920×1080, 30 fps |
| Exact clock | 657 frames / 21.900000 s |
| Sound | AAC, 48 kHz, stereo |
| Captions | 11 frame-rebased cues, soft `mov_text` plus SRT |
| Full encoded decode | 657 / 657 frames |
| Review frames | 27 / 27 |
| Repository regression | 382 pass / 1 optional skip |
| Minimum encoded detail variance | 90.352 (floor 30.0) |
| Encoded AAC loudness | −15.91 LUFS-I |
| Encoded AAC true peak | −1.31 dBTP |
| H.264 stream preserved through final mux | yes |
| Optical flow / cross-dissolve / implicit retime | none |

Pinned local hashes:

- Rig contract: `6ac4c5903dfa6e551391a845600f79ef98f9e91a4c5143e50c5b0555cee97c6f`
- Final MP4: `ec9ec3fa6d558893a7959360def5c40ae99ce50db31026858b0b186c06bd78ee`
- Report: `c14af021a9064700135376a763b4cb6ca08765c2d1da63c81df7d146c50f4023`
- SRT: `1fd359e98ac65ab4c067f93550d8abdcfeceac1eb120bfbf977a08f24c6dac98`
- Rebased PCM24 audio: `fe3761658ffdc956eebf0ecd9bfd986013fd78d4bb4a6fa8bee3a055f20365ba`
- Final picture stream: `09f93d556f2accbced6905129da4a9eb4d4939b1f9b8485c7168a22b3659c4af`

The 17.7 LU loudness-range reading is intentionally informational for this discontinuous action excerpt. The source 38.8-second master retains the delivery LRA gate; the excerpt independently gates the two meaningful delivery constraints, integrated loudness and encoded true peak.

The full local suite contains 383 tests. On the first sandboxed Windows pass, two legacy media tests were denied permission to spawn bare FFmpeg; rerunning those exact tests with local FFmpeg access passed. The only skip is the pre-existing optional OpenTimelineIO dependency.

## Public reproduction

GitHub Actions run [30546955844](https://github.com/prototype4-1077/Prototype-Video/actions/runs/30546955844) rebuilt the entire dependency chain on a clean Ubuntu runner. The 383-test picture/sound/performance job passed in 10m08s; the separate Blender v8 cheek-integrated nine-viseme gate passed in 6m11s.

Downloaded artifact `june-performance-rig-proof-v1` was independently verified under `outputs/edit/phase27-public-run-30546955844/` with FFmpeg 8.1.2:

| Public gate | Result |
| --- | ---: |
| Final MP4 SHA-256 | `8d044d7090aff602dac962e65f948972b21ab70e8a3745bfd75f8ccd7fa62e2a` |
| Report SHA-256 | `a871afb73d5bb6d1b3b6daa5c81113fed5ee4bcd202f4c24a7193f4bd3cc672d` |
| SRT SHA-256 | `1a54c87c3afd0a9b29c02c1cb5a8896f4568affce16181bc9812b0c7214d733e` |
| Public picture-stream SHA-256 | `d4f961d4559b67f2a31d573ae4c689c4f1aa828af48bf2f8440c4d72899fa306` |
| Dimensions / clock | 1920×1080 / 30 fps / 657 frames / 21.9 s |
| Streams | H.264 yuv420p / AAC 48 kHz stereo / English `mov_text` |
| Review frames | 27 / 27 |
| Minimum encoded detail variance | 90.380 |
| Independent AAC meter | −15.91 LUFS-I / 17.7 LU informational LRA / −1.31 dBTP |
| Full independent video/audio decode | pass |
| Picture preserved through final mux | yes |
| Caption text versus local master | identical |

Different FFmpeg/libx264 versions make the local and hosted container/packet hashes intentionally different. Decoded cross-platform picture comparison measures 58.086 dB average PSNR and 0.999144 SSIM, confirming that the clean runner reproduced the accepted visual sequence with only normal encoder-level variation.

## Reproduction

The rig proof requires the accepted Phase 26 sound master and report, then runs:

```bash
python3 -m pipeline.cartoon_performance_rig \
  concept/characters/june_oxley_performance_rig_v1.json \
  --sound-master build/edit/june-golden-scene-sound-master/june-golden-scene-sound-master.mp4 \
  --sound-report build/edit/june-golden-scene-sound-master/june-golden-scene-sound-master-report.json \
  --output-dir build/edit/june-performance-rig-proof
```

Acceptance fails on a missing or changed identity/adapter asset, incomplete semantic channel set, missing action class, off-clock action, cut through a dialogue cue, prohibited interpolation, child-renderer gate failure, delivery codec/clock drift, decode failure, detail loss, picture-stream change during final mux, loudness outside −16 ± 1 LUFS-I, or encoded true peak above −1 dBTP.

## What this enables now

The program can regenerate a coherent June action reel from high-resolution production layers, preserve one identity across three editorial scales, reuse the same semantic action vocabulary in code, validate physical contacts and liquid behavior, rebase sound/captions to a new edit, and reject quality regressions automatically. It is useful today for micro-cartoon production, episode pitching, action/voice tests, art-direction comparisons, and as a deterministic acceptance oracle for stronger future rigs.

## Known limitation and next move

The v1 rig is still a view-adapter system. Broad movement uses a small set of authored pose drawings; independent feature articulation exists only in the close view; a new camera angle still needs registered production art. That is a large step beyond a slideshow, but it is not yet unrestricted character acting.

Phase 28 should build one continuously deformable production view rather than add another finished scene. Segment June's approved wide-body art into depth-ordered head, torso, upper/lower limbs, hands, boots, costume overlap, and prop layers; bind them to a Blender 2.5D skeleton; add joint-corrective drawings and planted-contact constraints; then make `STAND_UP`, `SIT_DOWN`, `TURN`, `REACH`, and `HAND_OFF` pass identity, silhouette, foot, hand, temporal-stability, and retained-detail gates. A local critic can rank parameter candidates, but reinforcement learning should optimize bounded motion/rig parameters only after the deterministic measurements and a human-approved comparison set exist. It should not be asked to invent the final pixels.
