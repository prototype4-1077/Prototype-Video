# June Cartoon Asset Library — Phase 3

Phase 3 turns the June Porch integration model into a versioned Blender asset
library. The `.blend` binary is built at runtime and uploaded as a workflow
artifact; source control retains the human-readable contract and deterministic
builder code.

## Design lock

The canonical design comes from the June character bible and animation addendum:

- 78–84 years old, lean and wiry rather than a round toy proxy.
- Lean weathered face, pale blue-gray eyes, thinning white hair, trimmed beard,
  deep smile lines, and a slightly crooked grin.
- Faded plaid shirt, worn denim jacket, clean dark overalls, and work boots.
- Dignified rural specificity without cowboy, preacher, or redneck shorthand.

The non-committed Phase 3 turnaround is an art-direction reference. The committed
`concept/characters/june_oxley_asset_v1.json` is the enforceable source contract.

## Runtime library

`python -m pipeline.cartoon_asset_library` performs four stages:

1. Validate the versioned character, rig, face, hand, material, and quality rules.
2. Launch Blender with hard Python-error propagation.
3. Build a compressed `.blend` containing `CE_June_Oxley` and `CE_June_Porch`.
4. Reopen that library and render three full-resolution quality frames for both
   YouTube and portrait compositions.

The hero rig includes a complete seated biped hierarchy, five readable digits per
hand, independent blinking, A–H/X visemes, three facial-expression controls,
separate breathing/head/gesture NLA actions, layered workwear, boots, facial
weathering marks, and tactile procedural materials.

## Quality gate

```bash
python -m pipeline.cartoon_asset_library \
  examples/june-porch-vertical-slice.json \
  concept/characters/june_oxley_asset_v1.json \
  --blender /path/to/blender \
  --ffmpeg /path/to/ffmpeg \
  --engine CYCLES \
  --samples 12 \
  --output-dir build/june-asset-quality
```

The gate renders shot midpoints 54, 179, and 320 at 1920×1080 and 1080×1920.
It outputs the generated library, profile-specific plans and frames, two contact
sheets, and `asset-quality-report.json`. Animated dialogue proofs remain the
Phase 2 gate; these full-resolution frames judge design, materials, lighting,
hands, and crop safety without spending CPU time on duplicate full-resolution
in-betweens.

## Approval boundary

The library is ready for episode expansion only after a human approves the stable
face, lean silhouette, wardrobe, hands, facial expressions, and both crops. The
pipeline must not infer approval from a successful render.
