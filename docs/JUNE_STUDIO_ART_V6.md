# June Oxley v6 artwork candidate

V5 kept the complete figure visible and established shaped work boots, but its
large head, raised elbows, floating bib and open neckline pulled away from the
approved turnaround. V6 develops the editable Blender character toward a more
relaxed silhouette and clearer layers of workwear.

This is an **unapproved art candidate**, stacked on draft PR #17 at
`274674019fb30e42f10812ff2b774f08053daeda`. It is not a production or dialogue
approval. The source v5 files and their review decisions remain unchanged.

## What changed

- Scale the complete head hierarchy uniformly to 0.86, with a restrained shared
  cheek/nose refinement. Keep the orbital region and rigid oral assembly fitted.
- Taper and sweep the existing crown strands. The hairline still needs art work.
- Reduce sleeve bulk and fit the continuous jacket opening closer to the neck.
  Rebuild the flannel neckline, collar leaves, fitted quad bib, patch pocket,
  straps, hardware and stitches. Use a broad woven check and deeper indigo.
- Contour the overall waist toward the upper legs and add a fly seam. The
  waist-to-leg transition remains stiffer than the approved reference.
- Lower the hands, bring them closer to the body, curl the fingers and adduct the
  thumbs. Reuse the existing action datablocks and rebake their body controls.
  Assets without the new rig properties retain their existing hand targets.
- Preserve the v5 boot geometry, foot/pelvis action curves and Body camera.

The candidate is better suited to another focused likeness review. Facial
softness, cheek/beard volume, groom roots and finer hand acting remain below the
approved artwork. The porch is still a development set.

## Reproduce

Use Blender **4.2.0** and the recovered, checksum-verified v5 core package. Keep
all outputs in separate directories. No external texture or new voice download
is needed; the assets are packed.

```bash
blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/refine_june_studio_v6.py -- \
  --source /path/to/v5/june-studio.blend \
  --output /path/to/v6/art/june-studio.blend \
  --views body,close,front,smile,blink,speech-d --width 1280 --samples 32

blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/prepare_june_studio_v6_review.py -- \
  --asset /path/to/v6/art/june-studio.blend \
  --source /path/to/v5/june-studio.blend \
  --performance /path/to/v5/june-speaking-scene.blend \
  --output-dir /path/to/v6/study --render

python -m pipeline.june_studio_v6_package \
  --asset /path/to/v6/art/june-studio.blend \
  --render-dir /path/to/v6/study \
  --comparison /path/to/June_Oxley_v6_Comparison.jpg \
  --output-dir /path/to/v6/delivery \
  --license-file /path/to/v5/SOURCE_LICENSE.txt
```

The same Blender scripts can run with CPython 3.11 and the official `bpy==4.2.0`
wheel, using `python script.py -- ...`. The local art runtime used NumPy 1.26.4.
Run general pipeline tests in a separate environment with the repository's
requirements: their historic image-byte fixtures depend on its current
NumPy/OpenCV behavior.

The original v5 ZIP was truncated after the essential assets. Its complete
master and speaking scene were recovered using ZIP-member CRCs and the original
manifest checksums. The cue-source folder was absent. V6 consequently preserves
the original facial/acting actions and packed Spuds sound strip rather than
regenerating missing Rhubarb cues. This also works around the bpy wheel's lack
of Audaspace for creating new sound strips. Full Blender can play the retained
strip normally.

The editable scene keeps frames 1–450, the Body-camera preview at 109–270 and
the original voice at frame 121. The 162-frame movie is 5.4 seconds, 640 × 360 at
30 fps; the complete 4.32-second take starts 0.4 seconds into it. The six art
stills are 1280 × 720. No new narration or voice substitution is involved.

## Validation and review

The evaluated v6 asset passes:

- Clean append: 131 objects, 245 driver targets, no missing dependencies and
  packed character images. Maximum detail weight-sum error is `2.98e-08`.
- All 450 rig frames: maximum hand-target error `0.000368`, maximum leg-target
  error `5.37e-07`, minimum sole height `0.0899999`, no nonfinite transforms.
- Exact stored v5 boot geometry and unchanged foot/pelvis action curves.
- Eleven declared full-character framing poses with at least 2% image margin.
- Twenty-seven static closed-eye/gaze samples, three moving blinks and open-eye
  visibility controls. The ray test samples polygon centers; it is not proof
  for every possible blend or pixel.

The package requires matching model, scene, voice and all 162 frame hashes. It
decodes the finished movie, verifies the ZIP CRCs and creates a new review
identity from the exact delivered artwork. Scene 1 and the overall decision
start **unreviewed**. No old approval is imported. These checks do not certify
cloth collision, likeness, acting or production readiness.

Candidate model SHA-256:
`e27e4b49d947672333ff1b31906a5f2be69c0e7acfcc45fce66736f0c055e61c`

Speaking scene SHA-256:
`1434b6d12afdb04676d8b08b465ad883d80a437c2ce55bddaf8f40003c2366dc`

Preserved Spuds take SHA-256:
`ace859a6f34b3897636135be98d83d92f7ba1318cecfe3702c734850d4fb4903`

Artwork, editable models and the numbered survey are delivered in
`June_Oxley_v6_Artwork_Package.zip`; rendered media and Blender binaries are not
committed to Git. The source refiner, audit, packager and regression guards are
kept in this branch.
