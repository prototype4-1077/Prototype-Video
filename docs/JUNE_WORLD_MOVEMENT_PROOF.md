# June world movement proof — 2026-09-08

## Purpose and scope

James authorized the recommendation to develop a turnable June who can inhabit a
realistic cartoon environment. This isolated branch adds a continuous 24-second
3D movement audition on top of Phase40. It preserves all accepted paintings,
Phase35–40 sources, audio candidates, approval receipts, and existing render paths.

This audition is **development-only and silent**. It is not an episode, an approved
June redesign, a production-quality claim, or a substitute for his Spuds voice.
The earlier v8.2 procedural mesh is reused to expose movement/asset problems.

## Implemented

- A camera-independent 720-frame / 30 fps performance plan.
- Seated anticipation and standing; four alternating steps with explicit support
  windows; reach, grip closure, mug pickup, head/torso turn, gesture, chuckle, settle.
- World-space IK targets independent of the moving pelvis; arm and leg stretching
  disabled; feet retain orientation as the knee chains solve.
- A single mug for the complete shot; attachment preserves its world transform.
- Continuous finger closure rather than switching poses on one frame.
- A dimensional porch receiver and table; sole height calibrated from evaluated
  mesh geometry rather than assumed from the ankle target.
- Evaluated bone/sole evidence for every frame, separate mechanical gates, an
  editable Blender scene, and selected-frame or continuous rendering.
- Fail-closed measurement validation and an explicit `production_approved: false`.

## Mechanical evidence

13 focused tests pass, including injected slide, penetration, missing evidence,
nonfinite measurements, furniture collision and pickup teleport failures.


Blender 4.2.0, CPU, 720 evaluated frames. Values are inherited scene units:

| Measurement | Observed | Maximum allowed |
| --- | ---: | ---: |
| Foot target error | 0.000000492 | 0.005 |
| Wrist target error | 0.000000695 | 0.005 |
| Adjacent planted ankle displacement | 0.000000554 | 0.002 |
| Sole penetration | 0.000000201 | 0.002 |
| Planted sole height error | 0.000000537 | 0.005 |
| Mug movement at attachment boundary | 0.000000206 | 0.002 |
| Evaluated boot/table bounding-box intersections | 0 | 0 |

These are measurements of evaluated controls/soles, not a certification of
anatomical deformation, grip fidelity, appeal, or acting. Finger-to-handle and
chair-hand contact remain explicit unverified items.

## Visual finding

Selected Cycles renders reveal that the inherited procedural asset is visibly
below the approved GS070 art: narrow segmented-looking legs, weak garment volume,
simplified facial/hair construction, and proxy set dressing. Do not promote this
mesh as the premium June asset. Passing contact math does not fix those defects.

The reusable outcome is the world-space movement/control audition. The next asset
must pass it while matching the approved art in silhouette and close-up likeness.
Do not solve the art gap by painting a new static face over the moving character.

## Reproduction

Run from the repository root with Blender 4.2 available:

```bash
python -m unittest pipeline.tests.test_june_world_motion -v
blender --background --threads 4 --python-exit-code 1 \
  --python pipeline/blender/render_june_world.py -- \
  --output-dir /tmp/june-world-new-proof --engine CYCLES --width 960 --samples 16
```

For a continuous low-resolution motion audition, add `--animate --engine
BLENDER_WORKBENCH --width 640`. This is solid-shaded proof resolution, not delivery
quality. Cycles previews with fewer than eight samples are intentionally undenoised
and useful only for diagnostics. For a full-resolution
frame gate use `--width 1920 --samples 64`. Blender Workbench is an optional
mechanical diagnostic only and requires working OpenGL/EGL dependencies.

Assemble a silent inspection copy after all frames exist:

```bash
ffmpeg -framerate 30 -i /tmp/june-world-new-proof/frame_%04d.png \
  -frames:v 720 -c:v libx264 -crf 18 -pix_fmt yuv420p \
  -movflags +faststart /tmp/june-world-new-proof/june-world-mechanics-preview.mp4
```

## Next production asset gate

1. Use the approved GS070 face and canonical turnaround as art references.
2. Author one coherent 3D June: complete profile/back, weight-bearing boots,
   tailored garment volume, deformable elbows/knees, believable hands, fitted
   mouth/cheeks/eyelids, and stable hair.
3. Match the rig's named control interface or add a versioned retarget adapter.
4. Review untextured silhouette and deformation across seated, rising, walking,
   turning, reaching, gripping and open-hand poses before material polish.
5. Replace the proxy porch with one coherent set including chair/table contacts,
   steps, door and yard. Match light direction and materials to the approved art.
6. Re-run this same audition. Review at normal speed, including side and rear
   views; reject foot slide, knee collapse, volume loss and prop intersections.
7. Add exact June audio, coarticulated mouth shapes, eye targets and expression
   timing; measure audio onset and review the final encoded delivery.

## Episode direction

For contemporary issues, a future episode package should preserve a dated source
brief and separate verified claims from June's commentary. Keep the established
nonpartisan character boundary unless James deliberately changes it. Build one
excellent porch episode before expanding into the diner or a town asset library.
