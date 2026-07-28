# June canonical deformation — Phase 7

Phase 7 turns the CI evidence into an explicit engineering correction. The v3 artifact proved that the runtime library, render tiers, face matrix, and dual-profile pipeline work, but its rigid segmented limbs and off-model face are not promotion quality.

## Implemented v4 changes

- `concept/characters/june_oxley_asset_v4.json` pins the canonical turnaround by path and SHA-256. Loading the manifest fails if the reference is absent or changed.
- The shirt palette is blue/navy for v4. Red plaid, small eyes, a gaunt face, and a sparse beard are explicit regressions.
- Each jacket sleeve is one armature-weighted surface spanning shoulder, elbow, and wrist. Each trouser leg is one weighted surface spanning hip, knee, and ankle.
- The armature modifier uses preserve volume. A corrective-smooth modifier and post-deformation subdivision round the elbow and knee zones.
- Authored direction now drives hips and knees as well as torso, head, arms, and hands. Seated-to-stand and weight-transfer phrases map to deterministic leg poses.
- The complete eye stack is enlarged around stable eye centers, expression displacement is amplified, the beard is rounded and extended, the mouth performance is enlarged, and soft swept side-hair masses reinforce the canonical silhouette.
- A four-pose deformation gate renders grounded neutral, elbow fold, seated-to-stand, and asymmetric weight transfer. This is uploaded next to the facial matrix and dual-profile geometry sheets.

## Continuous gate

The manual GitHub workflow builds `june_oxley_hero_rig-4.0.0.blend`, reopens the generated artifact, and renders:

1. three authored key poses in landscape;
2. the same three poses in portrait;
3. all nine visemes and all seven facial expressions;
4. four dedicated elbow/knee/weight-transfer poses.

Workbench remains the fast geometry gate, Eevee remains look-development review, and Cycles remains promotion-only. Early video artifact upload prevents a later quality-render failure from erasing valid proof products.

## Honest boundary

v4 is the first continuously deforming code-native June asset. It is not yet the final theatrical rig. The next promotion slice must add IK/FK controls, foot roll and locks, clavicles/spine/twist chains, finger controls, jaw/cheek/gaze correctives, explicit mug/chair/ledger constraints, persistent ink, and hand-authored timing for GS030→GS050. The style-frame story reel remains the editorial target; only a rendered deforming performance can replace it.
