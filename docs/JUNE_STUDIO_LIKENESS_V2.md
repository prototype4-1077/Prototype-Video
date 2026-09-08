# June Oxley: likeness and material refinement v2

This is a separate development version of the reusable studio. It improves the
actual animated geometry and surface treatment, using the approved turnaround
and golden-scene artwork as references. It remains below that artwork's finish
and is not a production-approved character or episode.

## What changed

- A continuous rest-space sculpt reduces the orbital masses and lower-face
  length. The same transform is baked into the head, all speech/expression
  shapes, eyes, beard, moustache and teeth, retaining their existing controls.
- A head-control offset reduces the exposed neck while keeping the eyes and
  face together throughout the inherited actions.
- Swept crown strands, lifted scalp strands, fuller brows and fine eye crinkles
  add actual geometry. The new facial curves follow the stored shape keys.
- All added character parts belong to `June_Character_Studio_v2`, so they travel
  together when that collection is appended into a new Blender scene.
- Skin has a more varied complexion, cheek/nose warmth, fine surface detail,
  and restrained subsurface scattering. Rest-coordinate attributes keep the
  texture attached to the deforming mesh.
- Denim has dye variation and a diagonal weave; pockets, stitching and buttons
  are projected back to the exterior of the remeshed coat. Added shoulder and
  collar stitching and small elbow folds make the construction more legible.
- Close cameras have restrained depth of field and a warmer rim light.

No new character-generation service, subscription, voice generation or runtime
network dependency is introduced by this refinement. The existing packed
Poly Haven files and preserved Spuds take are reused.

## Rebuild the refinement

Use Blender 4.2.0 from the repository root. Recover the original studio-v1
`june-studio.blend` and matching JSON receipt from the saved
`June_Oxley_Studio_Review_Package.zip`, or build them with the v1 guide. Keep the
source files in their own directory. The refiner verifies the checksum and
version and refuses to apply itself to an already-refined asset.

```bash
blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/refine_june_studio.py -- \
  --source build/june-studio-v1/june-studio.blend \
  --output build/june-likeness-v2/june-studio.blend \
  --review --width 1280 --samples 32
```

The output includes a new packed asset and checksum receipt, plus neutral close,
front, smile, blink, open-mouth and wide inspection images. These are rendered
from the same turnable asset, not generated image substitutions. The source
studio remains unchanged.

## Short speech studies

The render CLI now accepts `--study CAMERA FIRST LAST`. Frame numbers refer to
the original 30 fps animation. The complete voice take must fit inside the
selected range; camera names and range bounds are checked before rendering.
The full original animation still receives the existing mechanical audit.

```bash
python3 -m pipeline.june_studio_render \
  --asset build/june-likeness-v2/june-studio.blend \
  --voice-dir build/june-studio-voice \
  --output-dir build/june-likeness-study \
  --blender blender --width 640 --samples 8 --threads 6 \
  --study Close 109 288

python3 -m pipeline.june_studio_package \
  --render-dir build/june-likeness-study \
  --asset build/june-likeness-v2/june-studio.blend \
  --voice-dir build/june-studio-voice \
  --destination build/june-likeness-review --blender blender
```

This study has 180 frames rather than the full benchmark's 450: 60% fewer frames
to render. That is a frame-count reduction, not a promise of the same percentage
reduction in wall time. The six-second study includes the unchanged 4.32-second
Spuds recording beginning at 0.4 seconds. It does not truncate, stretch or change
the pitch of the take. Omitting `--study` retains the original three-shot render.

Packaging creates a numbered HTML/JSON survey with unreviewed decisions. The
editable scene includes the packed original audio and opens at the study's
preview range, retaining the full performance timeline. The study is unscored
and does not replace the production 1920×1080 episode pipeline.

## Review boundaries and next art work

Passing the mechanical audit establishes finite transforms, target following,
sole contact and functioning facial deformations. It does not establish likeness,
appeal, cloth collision, phoneme accuracy or acting quality.

The next substantial quality gains require a focused sculpt/paint and animation
pass: more natural orbital and cheek anatomy, finer hair clumping, better jacket
collar construction, a convincing mouth interior, and hand-polished jaw/gaze
timing. Raising render samples alone cannot supply these missing design details.
Finish this reusable character before multiplying it across new sets or episodes.

The current porch remains a development set. The rural exterior, prop wear and
set dressing still need their own art pass. Current-events episodes also need
dated, checked source briefs; this benchmark sentence is a performance test,
not a factual report about a named event.

## Research applied

- Blender's [Principled BSDF documentation](https://docs.blender.org/manual/en/4.0/render/shader_nodes/shader/principled.html)
  describes the layered material and skin-scattering controls. The implemented
  scale, roughness and rest-bound color treatment were checked in Blender 4.2.0;
  they are art settings for June, not universal skin presets.
- The [Blender shape-key workflow](https://docs.blender.org/manual/en/4.2/animation/shape_keys/introduction.html)
  supports reusable deformations on the same topology. This refinement transforms
  every stored facial shape and its followers together instead of altering only
  the neutral face.
- The original [MPFB source and license](https://github.com/makehumancommunity/mpfb2)
  and [Poly Haven CC0 license](https://polyhaven.com/license) remain documented in
  the v1 asset provenance. This pass adds authored geometry and procedural
  materials; it does not introduce untracked third-party artwork.
