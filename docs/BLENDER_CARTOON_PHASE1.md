# Blender Cartoon Studio — Phase 1

Phase 1 introduces a fully local, no-subscription cartoon render path. It does not replace the existing renderer. A script or scene must explicitly opt into `blender_2_5d`.

## Included

- A versioned scene-level motion-plan contract.
- Conservative defaults for recurring characters and object-led scenes.
- A 1080×1920, 24 fps vertical Blender stage.
- Reusable camera, three-point lighting and simple atmosphere controls.
- A local CLI that invokes Blender in background mode and returns MP4 scene clips.
- Pure-Python validation tests that do not require Blender in CI.

## Requirements

- Blender 4.2 or newer installed locally or on the render worker.
- The `blender` executable available on `PATH`, or `BLENDER_BIN` set to the executable path.
- No paid API or subscription is required.

## Opt in

At the top of `script.json`:

```json
{
  "cartoon_motion_backend": "blender_2_5d",
  "scenes": [
    {
      "text": "The room was normal until the wallpaper started remembering.",
      "duration": 5.0,
      "motion_plan": {
        "strategy": "layered_parallax",
        "primary_action": "wallpaper pattern slowly travels toward the viewer",
        "camera": {
          "move": "push_in",
          "intensity": 0.35
        },
        "atmosphere": {
          "dust": true,
          "fog": false,
          "steam": false,
          "wind": 0.1
        },
        "secondary_motion": [
          "curtain sway",
          "light flicker"
        ],
        "locked_elements": [
          "room geometry",
          "wallpaper design"
        ]
      }
    }
  ]
}
```

A single scene can opt in with:

```json
"motion_backend": "blender_2_5d"
```

Existing scripts without either field remain untouched.

## Render

Normalize plans and render all opted-in scenes:

```bash
python -m pipeline.blender_cartoon build/<slug>/script.json --write-normalized
```

Render one preview frame:

```bash
python -m pipeline.blender_cartoon build/<slug>/script.json --scene 0 --preview
```

Use an explicit Blender executable:

```bash
python -m pipeline.blender_cartoon build/<slug>/script.json \
  --blender /path/to/blender
```

Use an authored `.blend` stage instead of the generated proxy stage:

```bash
python -m pipeline.blender_cartoon build/<slug>/script.json \
  --template assets/cartoon/stages/vertical-stage.blend
```

Outputs are written to `build/<slug>/cartoon-renders/` by default.

## Motion strategies

- `rigged_character` — recurring-character acting and reusable gestures.
- `portrait_performance` — close-up facial acting.
- `procedural_object` — machines, clocks, screens, doors and props.
- `layered_parallax` — environments and 2.5D camera movement.
- `keyframe_inbetween` — authored start/middle/end keyframes.
- `full_generated_video` — intentionally unstable surreal motion; not the normal cartoon default.

Phase 1 only establishes the contract, stage and render bridge. Character rigs, mouth shapes, gesture libraries and production environments belong to Phase 2.

## Safety and compatibility

- No existing video is routed to Blender automatically.
- Blender is discovered only when the new CLI is invoked.
- Validation can run without Blender installed.
- The default generated stage uses proxy geometry to prove real temporal rendering; it is not intended as final art.
- Authored `.blend` templates can replace the proxy stage without changing `script.json`.
