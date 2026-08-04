# Blender 3D Motion Graphics

The `blender_3d` backend turns literal storyboard scenes into real temporal 3D
clips while retaining the pipeline's existing narration, caption, review,
quality, and assembly stages.

## Selection

Set the submission profile and backend:

```json
{
  "visual_style": "literal_motion_graphics",
  "graphic_backend": "blender_3d"
}
```

Each storyboard scene must use one of the nine `graphic_kind` values:

- `labels`: extruded cards arriving as physical labels.
- `path`: a drawn 3D route, raised nodes, and destination markers.
- `counters`: animated towers, caps, and measurable categories.
- `clock`: a dimensional clock plus a linked event timeline.
- `perception`: layered cards, a moving focus rig, and a lens.
- `evidence`: a physical evidence board, pinned notes, and magnifier.
- `filter`: incoming layers and an animated toggle console.
- `scale`: a moving beam, suspended pans, and competing labels.
- `generic`: a linked spatial mechanism for concepts without a narrower family.

`semantic_anchor`, `visual_function`, `symbol_family`, `keywords`, scene index,
and `visual_revision` determine a stable seed. The seed selects one of six
camera/depth variants and one of three balanced palettes. The same scene is
reproducible, while different scenes do not automatically receive the same
staging.

## Runtime

The main render workflow detects `blender_3d` before the build. It restores a
cached Blender 4.2 runtime, installs headless libraries, and sets `BLENDER_BIN`.
The renderer uses Blender Workbench for fast CPU-safe 1080x608 source bands at
30 fps. Those clips then flow through the existing portrait and native 1080p
YouTube compositions.

The 3D backend is preferred, with a deterministic `pil_2d` fallback. A fallback
is recorded as `graphic_backend_fallback_reason`; it is never presented as a 3D
success. Final verification should require:

- `graphic_backend == "blender_3d"`
- `graphic_dimension == "3d"`
- `motion_source == "blender_3d_storyboard"`
- no `graphic_backend_fallback_reason`

## Proof

Run the manual `Blender 3D Graphics Proof` workflow with a slug and zero-based
scene index. It renders the scene's production stage at its midpoint and uploads
the PNG as `blender-3d-graphics-proof`.

Locally, with Blender installed or `BLENDER_BIN` set:

```bash
python pipeline/blender_graphics.py build/<slug> \
  --scene 1 --preview --output-dir proof-out
```
