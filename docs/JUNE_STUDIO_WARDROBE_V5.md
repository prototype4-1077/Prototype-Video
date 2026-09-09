# June Oxley v5: clothing, hands and work boots

V4 established a working blink and full entrance, but the body still looked like
a rough stand-in for the approved character artwork. V5 continues the same
editable Blender model with garment forms that read in a full-body shot. This
is an unapproved development asset. It does not establish production art or
dialogue approval.

## Asset changes

- Authored elbow compression, knee folds and cloth accumulation above the boots.
  The cloth uses the existing armature weights and has no simulation cache.
- Chest pockets with separate flaps, fitted buttons, doubled jacket topstitch,
  a flatter bib pocket, trouser side seams and cuff bands. The long seams inherit
  normalized skin weights from their garment, so they deform with the cloth.
- Shaped leather work boots replace the old intersecting spheres and rectangular
  soles. Uppers, welts, cap seams, instep eyelets and crossed laces are separate
  geometry. The original sole support height is retained for the existing walk.
- Enlarged hands and an uneven relaxed finger curl. Both are asset properties;
  legacy models keep their original values. The connected anatomical hand mesh
  and its digit weights remain intact.
- A dedicated `Body` camera shows the whole figure. Existing `Wide`, `Front`
  and `Close` framing remains available for comparison with earlier versions.
- The studio survey now lays out its landscape previews at their native aspect
  ratio, including on a narrow screen.

The v4 head, facial shapes, eyes, groom and rigid oral assemblies are preserved.
The audit compares stored facial geometry with the original v4 checkpoint.
No new image generator, paid asset, narration service or add-on is required.

## Build and inspect

Use the pinned Blender 4.2.0 runtime and a v4 `.blend` with its matching JSON
receipt. The refiner rejects a modified source and writes to a separate directory.

```bash
blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/refine_june_studio_v5.py -- \
  --source build/june-v4/june-studio.blend \
  --output build/june-v5/june-studio.blend \
  --views body,wide,close --width 1280 --samples 16

blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/audit_june_wardrobe.py -- \
  --source build/june-v4/june-studio.blend \
  --asset build/june-v5/june-studio.blend \
  --voice-dir build/june-studio-voice \
  --output build/june-v5-review/wardrobe-audit.json
```

The audit checks a clean collection append, packed images, internal driver and
modifier targets, normalized trim weights, ten evaluated poses, preserved hand
scale/curl, and all 450 frames of rig/sole contact. It does not prove absence of
all cloth intersections or approve the artwork. Inspect the rendered walk,
gesture and close detail views as well.

## Short full-body motion study

The study covers animation frames 109–270: 5.4 seconds at 30 fps. It shows the
end of the entrance and the complete untouched Spuds benchmark, beginning 0.4
seconds into the clip. The editable timeline still contains the full 450-frame
performance. This is a lower-resolution, unscored development check; it does
not replace the native 1920×1080 episode workflow.

```bash
python3 -m pipeline.june_studio_render \
  --asset build/june-v5/june-studio.blend \
  --voice-dir build/june-studio-voice --output-dir build/june-v5-motion \
  --blender blender --width 640 --samples 8 --threads 6 \
  --study Body 109 270 --chunk-frames 30 --max-new-chunks 1

python3 -m pipeline.june_studio_package \
  --render-dir build/june-v5-motion --asset build/june-v5/june-studio.blend \
  --voice-dir build/june-studio-voice --destination build/june-v5-review \
  --blender blender
```

Repeat the identical render command to finish six bounded chunks. The existing
content-addressed cache checks model, code, camera, voice and frame identities
before reuse. Do not edit those inputs during a render. Review decisions remain
unreviewed and are isolated from earlier models by the existing review identity.

## Research and production choices

[Blender Studio's stylized character workflow](https://studio.blender.org/training/stylized-character-workflow/)
separates body/outfit sculpting, wrinkles and folds, and surface polishing. V5
applies that staging: change garment forms before spending more on final samples.
The specific June geometry is authored here; no course assets were imported.

[Blender's Solidify modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/solidify.html)
adds thickness to a surface. V5 uses it for leather and cloth layers, while
keeping the boot sole's contact surface explicitly modeled.

[Corrective Smooth](https://docs.blender.org/manual/en/latest/modeling/modifiers/deform/corrective_smooth.html)
can reduce distorted areas after deformation. It remains a targeted option if a
reviewed pose exposes a joint problem; adding it everywhere would not supply
missing garment construction or acting. Live cloth simulation should similarly
wait for a shot that needs loose fabric motion and a stable collision model.

The practical production path is still one reusable character, a limited set of
reusable locations and gestures, small shot studies, then final lighting and
resolution. The current CPU environment makes full motion rendering expensive;
a supported GPU renderer is the next infrastructure improvement to evaluate on
the same benchmark. Preserve the original Spuds recording during comparisons.

## Remaining art work

The face's appeal and proportions, groom roots, collar/neck construction,
individual finger acting and the unfinished porch exterior remain below the
approved artwork. These require further authored work. Extra render samples
cannot turn this model into a top-tier cartoon character on their own.

Current-event episodes also need a dated factual brief. This voice benchmark is
a character study, not reporting on a named news event.
