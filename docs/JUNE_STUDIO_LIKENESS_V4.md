# June Oxley: v4 facial fit and walking study

V3's front blink hid a defect: the turned view exposed part of the iris through
the eyelid. Its cheek planes, narrow nose and raised shoulders also remained
visibly different from the approved artwork. V4 continues the same reusable
Blender character, correcting these specific forms before more episode work.
This remains an unapproved development model, not a finished production episode.

## Model changes

The refiner requires the unchanged v3 asset and matching checksum receipt. It
writes a separate v4 asset and never reapplies itself to an already-refined file.

- Nine masked relaxation passes soften the under-eye/cheek planes. A shared
  spatial field rounds the nose and carries facial followers with the sculpt.
  The original mesh topology, UV seams and speech controls remain editable.
- The neutral lids open slightly. The full-close shapes gain anterior volume,
  and the complete eye assemblies are fitted deeper into their sockets. The
  eyes remain real, visible geometry throughout the blink; no visibility switch
  substitutes for contact between the lid and eye.
- Beard tips taper more softly and the skin tint loses some orange. This uses
  the same pinned, packed v3 sources; no new generative or paid service is needed.
- The shoulder hump is lowered, outer collar leaves are fitted to the evaluated
  coat, and the shirt neckline narrows toward the neck. The plaid has broader
  bands. These are authored garment forms, not a cloth simulation.
- The v3 upper/lower tooth rows, tongue and jaw driver stay intact. Their rigid
  motion is checked again at the D speech extreme.

From the repository root, with Blender 4.2.0:

```bash
blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/refine_june_studio_v4.py -- \
  --source build/june-likeness-v3/june-studio.blend \
  --output build/june-likeness-v4/june-studio.blend \
  --views close,front,wide,blink,smile,speech-d --width 1280 --samples 16
```

The JSON receipt records the source asset, refiner and resulting asset hashes,
the geometric changes and oral checks. `June_Character_Studio_v4` is the reusable
collection. Existing packed textures and the established body rig are retained.

## Test eyelid coverage, including gaze

```bash
blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/audit_june_eyelids.py -- \
  --asset build/june-likeness-v4/june-studio.blend \
  --voice-dir build/june-studio-voice \
  --output build/june-v4-review/eyelid-audit.json
```

The audit uses the head at its render subdivision level. It casts rays from the
camera to front-facing polygon centers on each eye, iris, iris rim and pupil.
It tests nine declared gaze targets from each of three camera positions, then
three blinks in the actual animated benchmark. All closed samples must be
covered. Separate open-eye checks require visible iris samples on both sides,
so burying the eyes cannot pass the audit.

The output describes exactly what was sampled. It does not prove closure for
every pixel, expression blend or possible viewing angle. Inspect the rendered
blinks and intermediate poses too. `--allow-failure` can record a comparison
against an older model without calling that model successful.

## Show the full entrance and the complete original voice

The previous six-second close study omitted most of the walk. The new
`--walk-study LAST` option starts at frame 1, shows the Wide camera through
frame 120, then shows Close from frame 121 through LAST. A LAST value of 300
makes a ten-second study. The same acting camera drives head/gaze in every
worker, preventing a pose reset at the camera cut. Camera markers preserve the
cut in the editable Blender scene.

```bash
python3 -m pipeline.june_studio_render \
  --asset build/june-likeness-v4/june-studio.blend \
  --voice-dir build/june-studio-voice --output-dir build/june-v4-study \
  --blender blender --width 640 --samples 8 --threads 6 \
  --walk-study 300 --chunk-frames 40 --max-new-chunks 1
```

Repeat the identical command until completion. Each worker finishes and verifies
one bounded chunk; assembly only uses complete, checksum-matching frames.
The eight chunks cover all 300 frames once, without changing the original
30 fps clock. The untouched 4.32-second Spuds take begins at exactly four
seconds. The study has no score and does not replace the native 1920×1080
production episode workflow. Existing single-camera and full-scene modes remain
available.

Package the completed render:

```bash
python3 -m pipeline.june_studio_package \
  --render-dir build/june-v4-study --asset build/june-likeness-v4/june-studio.blend \
  --voice-dir build/june-studio-voice --destination build/june-v4-review \
  --blender blender
```

The required numbered survey separates the entrance and spoken address. Its
identity includes the exact model, encoded video and voice hashes. Browser-saved
choices from v2, v3 or another v4 render therefore cannot silently carry over.
All decisions remain unreviewed. The packaged scene includes the packed Spuds
recording and the original full 450-frame editable timeline.

## Review limits and production direction

Look for the same face throughout the camera cut, visible walking and foot
contact, closed lids during the actual head turn, stable teeth during the open
vowel, and covered teeth in the closed-lip pose. Review silhouette and expression
against the canonical turnaround, not merely against the previous model.

A successful rig or eyelid audit does not establish premium acting or artwork
quality. The groom roots, orbital anatomy, wardrobe construction, hands, boots,
porch exterior and purposeful acting still need art direction. Raising render
resolution cannot supply those missing details. Current-event episodes also
need a dated source brief; this benchmark is not reporting a named news event.

## Research used

- [Blender shape keys](https://docs.blender.org/manual/en/latest/animation/shape_keys/introduction.html)
  support blended facial expressions and corrective poses. V4 uses stored
  geometry on the existing topology; it adds no live dependency or frame handler.
- [Blender Studio's facial rigging proposal](https://studio.blender.org/blog/proposal-facial-rigging-with-shape-keys/)
  describes combining shapes and corrective shapes. The eyelid fitting and
  coverage criteria here are authored specifically for June.
- [Blender Studio's eyes chapter](https://studio.blender.org/training/facial-rigging/chapter/eyes/)
  treats eye rigging as a dedicated facial system. That motivates testing actual
  lid/globe fit separately from June's general body-rig audit. No course assets
  or paid training materials were imported.

The exact implementation is verified on Blender 4.2.0 even though current online
manual pages may describe later releases. See the v3 source manifest and guide
for the pinned CC0 skin, anatomy and mouth resources.
