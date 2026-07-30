# June Oxley Phase 24 — GS070 Resolution Checkpoint

## Outcome

Phase 24 turns the GS070 visual targets into an exact 7.6-second production shot. The renderer uses a high-detail held-mug macro for the offer, cuts on frame 46 to a new landscape close-hero plate, applies affine-registered feature-level eye and mouth animation, completes one compact nod, and holds June's body still for the final 27 frames while the porch remains alive.

The result is production-pixel 2.5D character animation. The two accepted paintings are the actual frame sources; Pillow, OpenCV, NumPy, Rhubarb, Piper, and FFmpeg control registration, facial timing, bounded deformation, secondary life, encoding, and verification.

## Production package

- Plate contract: `concept/style_frames/june_golden_scene_gs070_resolution_v1.json`
- New close-hero plate: `concept/style_frames/june-golden-scene-gs070-resolution-plate-v1.png`
- Existing offer insert: `concept/style_frames/june_oxley_mug_held_insert_v1.png`
- Lip cues: `concept/style_frames/june_golden_scene_gs070_rhubarb_v1.json`
- Expression cues: `concept/style_frames/june_golden_scene_gs070_expression_v1.json`
- Body motion: `concept/style_frames/june_golden_scene_gs070_body_motion_v1.json`
- Renderer: `pipeline/cartoon_resolution_scene.py`
- Focused regression: `pipeline/tests/test_cartoon_resolution_scene.py`
- CI artifact: `june-gs070-resolution-v1`

## Exact performance clock

- Frames 1–45: held-mug offer insert with a bounded cinematic push
- Frame 46: hard cut to direct-address plate; no optical flow, source dissolve, or generated in-between
- Frame 143: dialogue animation ends
- Frame 145: mouth returns to the authored restrained grin
- Frames 157–188: compact nod
- Frames 202–228: exact 27-frame final hold

During the final hold, head, mouth, shoulders, and breathing channels are locked. Deterministic lantern variation, steam, dust, and wind-chime movement continue so the image feels held rather than frozen.

## Registration correction

The canonical facial atlas was transferred from the registered front hero plate to the new three-quarter close plate with the following affine transform:

```text
[[ 1.52384528, -0.279078367, 379.914944 ],
 [ 0.279078367, 1.52384528, -22.3970917 ]]
```

The first render used the older whole-face atlas masks. Visual review rejected it because the patches replaced cheeks and ears and produced an identity seam. The accepted renderer instead limits the atlas to a 352×249 mouth region and a 367×230 two-eye region on the production plate. The authored beard silhouette, cheeks, ears, and final grin remain untouched.

Rejected render evidence stays outside Git under `outputs/edit/phase24-gs070-resolution/full-render-v1/`. The accepted local render is `outputs/edit/phase24-gs070-resolution/full-render-v3/`.

## Local verification

| Check | Result |
| --- | ---: |
| Video SHA-256 | `eeee3dba56b14c48373ff136f7014a303f9e8ad3200d9f829b902f9f2363e970` |
| Report SHA-256 | `2a494e00a421341f7d865c32976889e1b80076124a7d96fa4c8e8032760da551` |
| Contract SHA-256 | `ff5ae15bf49e4ab19c654948d4217b3202d3ddcffb3d1b9d617694c46d78b194` |
| Codec / pixel format | H.264 / yuv420p |
| Dimensions / rate | 1920×1080 / 30 fps |
| Encoded frames / duration | 228 / 7.600 seconds |
| Minimum / mean review PSNR | 41.059 / 41.244 dB |
| Minimum encoded Laplacian variance | 137.505 |
| Focused tests | 7 passed |
| Full local suite | 381 passed, 1 skipped; 2 legacy tests blocked only when sandboxed Python launched bare FFmpeg |

The full video decodes without errors. Twelve source review frames and seven independently decoded H.264 frames were inspected, including both sides of the cut, dense lip shapes, the question ending, the nod extremes, and the final hold.

The local scratch audio is a zero-cash Piper/Ryan performance used to author and review the Rhubarb timing. It is intentionally outside Git. Public CI renders the same 228-frame animation silently and validates the cue clock, leaving final voice casting and mastering for picture lock.

## Built-in image generation provenance

Mode: built-in image generation, identity-preserving production-plate edit. The generator's original output was saved at `C:\Users\jwats\.codex\generated_images\019fa976-0fb5-7fd3-aaca-6f8276218dd8\exec-87611149-a8fc-4684-82cc-746a24685825.png` and copied without modification to `concept/style_frames/june-golden-scene-gs070-resolution-plate-v1.png` with SHA-256 `c54f82ef387121267829ec0a85c8fbf56830af2fd18c400ef777cfbb9044d029`.

Final prompt:

```text
USE CASE: identity-preserving production plate edit and cinematic recomposition.

Create one polished 16:9 horizontal cartoon production plate for GS070, suitable for deterministic cutout/atlas animation at 1920x1080.

INPUT ROLES:
1) june-golden-scene-gs070-portrait-style-target-v2.png is the PRIMARY identity, expression, released-mug, hand, and emotional-performance reference.
2) june-golden-scene-gs070-style-target-v2.png is the porch set, table, lantern, road, depth, color, and lighting-continuity reference.
3) june_oxley_porch_hero_plate_v1.png is the canonical near-frontal face, costume, rendering-quality, and character-proportion reference.

COMPOSITION:
- Recompose as a landscape close-hero shot, not a wide shot and not a portrait crop.
- June occupies the left-center/center, upper torso visible, face near-frontal and large enough for later facial-atlas registration.
- Place June's eye/face anchor near 43% of frame width and 42% of frame height.
- June has just released the mug and has returned his gaze directly to camera.
- One anatomically correct offering hand is now relaxed and clearly resting near the mug; it must read as a completed release, not gripping it.
- The cream enamel mug is prominent in the lower-right/foreground, stable on the tabletop, with the same blue rim and distinctive upper-right rim chip.
- Preserve porch continuity: warm lantern glow, weathered wood, cool road/depth beyond, painterly cinematic atmosphere.
- Keep the lower-left region comparatively uncluttered and dark enough for a future caption lane.
- Restrained, kind, knowing grin; direct connection with viewer; no exaggerated comedy pose.

IDENTITY INVARIANTS:
- Exact June Oxley identity: bald crown, short white side hair, full white beard and mustache, large blue-gray eyes, bulbous rounded nose, weathered kind face.
- Worn denim/plaid/overalls wardrobe and established warm/cool palette.
- Premium hand-painted animated-feature look with clean readable silhouettes, textured brushwork, soft volumetric light, controlled depth of field, and production-quality detail.
- Near-frontal face geometry must stay compatible with the canonical hero plate and existing viseme/expression atlases.

HARD NEGATIVES:
No text, captions, logos, watermark, borders, split panels, extra people, extra hands, extra fingers, missing fingers, duplicated mug, warped mug, floating objects, hand gripping the mug, profile face, closed eyes, grotesque expression, photorealism, anime styling, flat vector art, low-detail background, smeared beard, or cropped head.

Output only the clean final production plate.
```

## Honest current ceiling

GS070 now reaches the approved art level because accepted source pixels survive into the encoded shot. Its facial rig is still view-specific: the affine front-atlas transfer is strong for this bounded three-quarter angle but is not a general head-turn solution. The macro-to-close cut communicates the release without a continuously deforming arm and hand.

The seven-shot cartoon is not yet assembled. Final voice, room tone, porch ambience, mug/wood Foley, music, subtitles, mix, and loudness mastering also remain.

## Recommended next production step

Assemble the exact 1,164-frame, 38.8-second GS010–GS070 picture master from the accepted Phase 21, GS030, GS060, and GS070 material. The assembly contract should map every output frame to one pinned source frame, prohibit implicit retiming, enforce all shot durations, add transition and continuity review frames, preserve audio slots without inventing final sound, and emit one public artifact. Once picture lock passes, build the reusable high-resolution June layer/mesh rig for continuous future episodes rather than reopening this short's accepted poses.

## Public evidence

GitHub Actions run [30534953396](https://github.com/prototype4-1077/Prototype-Video/actions/runs/30534953396) independently passed the full repository regression, every existing full-HD shot gate, the exact GS070 render/decode/quality assertions, artifact upload, and the separate Blender v8 nine-viseme facial gate.

Downloaded artifact `june-gs070-resolution-v1` was independently verified under `outputs/edit/phase24-public-run-30534953396/`:

- Public video SHA-256: `41726dc3e631de5389370e711fff438062daa4426e9e402181c4c437bd20b83f`
- Public report SHA-256: `d733fbfb09f3c6b9866c4ef021c1f60821da78802cf94412f66d7d080b442b42`
- H.264/yuv420p, 1920×1080, 30 fps, 228 frames, 7.600 seconds, intentionally silent
- Full independent FFmpeg decode: pass
- Public minimum/mean review PSNR: 41.063/41.245 dB
- Public minimum encoded Laplacian variance: 137.505
- Body-locked/live-porch final hold: pass
- Twelve exact encoded frames plus the full public contact sheet passed full-resolution visual inspection
