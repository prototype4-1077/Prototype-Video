# June Oxley: v3 skin and oral assembly

This development asset continues studio-v2. It preserves the existing body rig,
facial controls, cameras and Spuds benchmark while addressing the smooth skin,
pointed-looking teeth and brush-like crown visible in the v2 review. It is not
an approved character or finished episode.

## What changes

- A shared rest-space sculpt softens cheek transitions, rounds the nose, reduces
  the crown height slightly and adds a small asymmetric smile. It is applied to
  every stored facial shape and existing facial follower together.
- The head and hands receive UVs matched by source vertex and polygon identity.
  The head deliberately omits some original neck polygons, so face-list position
  is not used as an identity. UV seams retain each polygon corner's coordinates.
- A pinned 2048×2048 MakeHuman aged skin texture adds complexion and age detail.
  The shader combines it with restrained pore detail, variable roughness and
  subsurface scattering. The scalp is masked to avoid importing a dark haircut
  beneath June's white groom. This is a full-body source atlas, not a dedicated
  high-resolution facial scan.
- The old individually deforming sphere teeth are replaced with the CC0 system
  teeth and gums, split into upper and lower assemblies, plus a fitted tongue.
  A bounded jaw rotation reads the existing speech controls. Teeth remain rigid
  within each row instead of stretching with nearby lip vertices.
- Crown strands share neighboring guide directions and arcs, with three subtle
  gray/ivory tones. The beard and mustache tips are trimmed while retaining
  their existing speech-following roots.

## Prepare the pinned source assets once

From the repository root:

```bash
python3 -m pipeline.june_studio_v3 \
  --directory build/june-v3-resources --cache build/june-tool-cache
```

The manifest is `concept/characters/june_studio_sources_v3.json`. The first
preparation downloads the official system pack and the pinned base OBJ, checks
their hashes, then extracts only the declared skin, teeth and tongue sources.
Later preparation reuses the verified files. The source images are packed into
the finished Blender asset; ordinary shot rendering needs no network access,
MPFB installation or new subscription.

## Build the separate v3 asset

Use the same Blender 4.2.0 build as the v2 source. Retain the v2 `.blend` and
matching JSON receipt in their own directory.

```bash
blender -b -t 6 --python-exit-code 1 \
  --python pipeline/blender/refine_june_studio_v3.py -- \
  --source build/june-likeness-v2/june-studio.blend \
  --output build/june-likeness-v3/june-studio.blend \
  --resources build/june-v3-resources \
  --views close,front,smile,blink,speech-d,wide --width 1280 --samples 24
```

The builder refuses another source version or a mismatched source checksum. It
does not apply itself twice. The JSON receipt records matched UV counts, source
hashes, oral rigidity measurements, groom counts and packed images. Character
parts belong to `June_Character_Studio_v3` for reuse in other scenes.

## Review the same performance

```bash
python3 -m pipeline.june_studio_render \
  --asset build/june-likeness-v3/june-studio.blend \
  --voice-dir build/june-studio-voice \
  --output-dir build/june-v3-study --blender blender \
  --width 640 --samples 8 --threads 6 --study Close 109 288 \
  --chunk-frames 40 --max-new-chunks 1
```

Repeat the identical command until `status.json` reports `completed`. The
renderer checks every completed chunk before reuse and retains the entire
original 4.32-second Spuds take. Use `pipeline.june_studio_package` as described
in the v2 guide to package the editable scene and numbered, unreviewed survey.

The motion study is a development preview. It does not replace the native
1920×1080 production episode workflow. Keep the full original take, compare
matched expressions against v2 and the approved artwork, and review teeth/lip
clearance at actual speech extremes before increasing render resolution.

## Evidence and limitations

The evaluated jaw check measures motion and rigidity at the D speech extreme.
It does not certify every possible blend, lip contact, acting quality or
character likeness. The broader studio mechanical audit and clean-scene append
check remain necessary. All approval flags stay false until James approves.

The supplied teeth include a connected gum/mouth mesh; its upper/lower division
is an authored fitting decision. The full skin atlas and procedural groom are
starting materials for art direction, not a guarantee of the approved artwork's
finish. Wardrobe construction, a detailed exterior and hand-polished acting
remain separate work.

## Primary sources

- [MakeHuman system assets and per-asset CC0 licenses](https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html)
  provide the aged skin, teeth/gums and tongue data used here.
- [MPFB material overview](https://static.makehumancommunity.org/mpfb/docs/materials/overview.html)
  describes image-based and procedural skin material workflows.
- [Pinned MPFB base mesh](https://github.com/makehumancommunity/mpfb2/blob/437dd513888a92399d1d3200d2e80859fae55abc/src/mpfb/data/3dobjs/base.obj)
  supplies the UV reference. No upstream application code is copied into this
  implementation. Exact source and derived-file hashes are in the manifest.
