# June Oxley Phase 30 — Reconstruction Lock Checkpoint

Date: 2026-08-01

Branch: `agent/june-hero-unified-sculpt-phase-5`

Parent commit at start: `5eaa50080ab60c6a1e7b4e2eb46338f68dff13a5`

## Stopping decision

Phase 30 is complete and accepted as an engineering foundation. Phase 31 is intentionally stopped before its first encode because usage is low and its in-memory mechanics evaluator still has one known TPS audit bug. No Phase 31 video has been rendered.

Phase 27 remains the audience-facing quality control. Phase 30 proves that its accepted standing June pixels can become an honest animation representation without repeating the exploded-atlas failure.

## Phase 30 completed work

Repository files:

- `concept/characters/june_oxley_reconstruction_locked_patch_v1.json`
- `pipeline/cartoon_reconstruction_locked_patch.py`
- `pipeline/tests/test_cartoon_reconstruction_locked_patch.py`

The reverse-engineering audit rejected arbitrary upper/lower-arm and thigh/shin cuts. The accepted representation has exactly nine visible regions supported by the flattened source painting:

1. `lower_garment` — one waist-to-both-cuffs surface;
2. `torso_shell`;
3. `left_sleeve` — continuous shoulder to cuff;
4. `right_sleeve` — continuous shoulder to cuff;
5. `head_neck`;
6. `left_hand`;
7. `right_hand_mug` — atomic;
8. `left_boot`;
9. `right_boot`.

The extractor uses deterministic inclusive `cv2.fillPoly` region rasters, stable hard ownership, native-pixel overlap support, and deterministic geodesic assignment of the alpha 1–8 fringe. Rest recomposition reads only patch-local RGBA; it cannot silently read the original source during reconstruction.

Fail-closed protections include:

- one pinned RGBA source and pinned Phase 27 registration operation;
- exactly nine connected semantic supports and ownership masks;
- no zero-owner region or hidden split-limb region;
- exact raw RGBA reconstruction;
- exact registered-rest equivalence;
- exact report schema and quality-gate inventory;
- post-load contract mutation rejection;
- patch corruption/source-leakage regression coverage;
- mandatory gate and schema deletion rejection.

Validation: 20/20 Phase 30 tests pass. Combined Phase 30 plus Phase 31 static suites currently pass 33/33. Both modules compile.

## Phase 30 bounded artifact

Output directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase30-reconstruction-locked-patch`

Key facts:

- `machine_passed=true`;
- raw RGBA mismatched pixels: 0;
- registered RGBA mismatched pixels: 0;
- patch count: 9;
- semantic overlap: 82,229 pixels / 0.4042842955;
- maximum semantic cover count: 4;
- lower-garment ownership: 72,560 pixels;
- reconstructed PNG SHA-256 is exactly the accepted source SHA-256: `c8665a358c7f18fb159ce15c9bd381b433871a1f2f47f6b227e31cb08031e07d`.

Diagnostic proof sheet:

- `june-pose100-reconstruction-proof-sheet.png`
- SHA-256 `caaac924cac0a9d11b108bf0ac077ec8ec31ebb3a45434b141acca09982f22f2`

Machine report:

- `june-pose100-reconstruction-report.json`
- SHA-256 `5b8f4cfb88d4cd72e34307afb2e460f85761ef6de4c14724d0618d76f2f2ca7d`

The proof sheet shows the accepted source, patch-local reconstruction, and color-coded ownership map. The first two panels are visually and byte-for-byte identical.

## Phase 31 work in progress — do not encode yet

Repository files:

- `concept/characters/june_oxley_connected_region_mechanics_v1.json`
- `pipeline/cartoon_connected_region_mechanics.py`
- `pipeline/tests/test_cartoon_connected_region_mechanics.py`

The contract defines a zero-cash 49-frame / 30 fps / 960×540 flat-color mechanics proof. It uses nine clamped PCHIP keys, zero endpoint tangents, absolute source-space head/hand/mug transforms, one five-control lower-garment cage with fixed ankle controls, continuous three-control sleeves, identity boots, one stable render order, and one final Phase 27 registration application.

The 13 contract/static tests pass. No video, contact sheet, or Phase 31 report has been encoded.

### Known blocking defect

Do not run the Phase 31 evaluator or encoder before repairing this defect:

- `pipeline/cartoon_connected_region_mechanics.py` near line 442 indexes `inverse_residuals` with `sampled.ravel() > 0`. `inverse_residuals` has one entry per destination query, but `sampled.ravel()` is the flattened remapped image; the dimensions do not match. Any non-rest lower-garment deformation can raise.
- Compute inverse residual on the sampled support queries themselves: evaluate `forward(inverse(destination)) - destination` at destination grid indices whose remapped lower-support mask is nonzero. Report the sampled maximum and require `<=0.25` source pixels.
- Preserve the sampled destination Jacobian determinant gate and require it to stay positive. Do not fall back to the three control-triangle test alone.

### Required audit after that repair

Before encoding, add and pass runtime tests that prove:

- all 49 frames evaluate in memory;
- the contract canonical hash rejects changed tracks, loosened gates, deleted delivery gates, and empty report schemas;
- head, hands, and mug use the absolute source-space tracks currently in the contract;
- actual composite matrices drive translation, rotation, centroid, and cage-step gates;
- final registered region masks at alpha >16 remain connected;
- boot anchor, sole, endpoint-motion, and shadow metrics come from rendered masks and receiver geometry, not constants;
- seam gaps and secondary edges come from the transformed support masks, not initialized zeros;
- balance uses the final registered character alpha centroid;
- loop comparison segments the character from the known opaque diagnostic background rather than treating video alpha as evidence;
- `require_delivery=True` fails before a real encode.

## Exact resume sequence

1. Read this checkpoint and the Phase 30 contract.
2. Repair the TPS inverse-residual indexing defect.
3. Finish Phase 31 runtime adversarial tests; do not render yet.
4. Run the Phase 30 and Phase 31 focused suites.
5. Run the full 49-frame in-memory Phase 31 preflight. Keep the 4.0 preview-pixel cage/centroid gate fixed; change motion keys rather than loosening the threshold if necessary.
6. Independently review the in-memory metrics for hardcoded or target-derived false passes.
7. Only after all non-delivery gates pass, perform exactly one Phase 31 encode.
8. Decode all 49 frames, verify H.264/yuv420p 960×540 at 30 fps for 1.633333 seconds, inspect the nine key frames/contact sheet, and record the creative verdict separately from `machine_passed`.
9. If the flat-color proof passes, the next milestone is a textured proof using the accepted pixels. Do not start RL or a full episode render yet.

## Promotion rule

Phase 31 may promote only if every source, topology, seam, contact, motion, balance, delivery, and decoded-loop gate passes and an independent visual review confirms one trouser mass, no bucket cuffs, no seam or double edge, no boot slide, and no mug flex. Machine pass is not audience approval.
