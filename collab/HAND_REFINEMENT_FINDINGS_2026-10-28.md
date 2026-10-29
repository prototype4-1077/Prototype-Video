# Late table-hand study — 2026-10-28 — review pending

Scope follows James's latest clarification, **"hand end of scene."** Preserves
accepted transitions, 303-frame edit, eye v3, audio v3, and all existing locked
renderers/contracts/proofs. No new art, paid/network call, audio processing,
video encode, commit, push, or main change.

## Finding and one candidate

Studied source F091–F148, output F166–F223: **5.500–7.433 s, half-open**, 58
frames at 30 fps. The final close-up is not the hand shot.

The old late gesture changes pairwise distances among its 11 hand controls by
up to **3.625669 source px**. At source F115, Gaussian-averaged inverse deltas
have up to **0.628242% local length strain** in the 34,377-pixel opaque hand
core. These are measurable stretch mechanisms, not proof that stretch alone
explains James's perceptual objection. The numbers are modest; timing and the
source-art/2.5D limitation may also matter.

One candidate replaces the late independent spread/compression with a small,
coherent **0.65-degree planted-index-tip rock**. It reaches its press at F111,
holds through F116, then releases more slowly to the unchanged F148 endpoint.
F091–F101 uses a quintic entry blend to inherit old F090 without a jump; exact
coherent geometry begins F102. No earlier gesture or later shot is changed.

Measured candidate:

- Maximum control excursion: **2.696599 px**; maximum adjacent step:
  **0.288327 px**. This is an active gesture, not a frozen-hand bypass.
- F102–F147 pairwise distance error: **0.000000139 px**; planted control drift:
  **0 px**. Other fingertip vertical excursions remain below 1.7 px.
- F115 inverse-map core length strain: **0.000012035%**, positive determinant
  minimum **0.999999952**. The rigid inverse field is evaluated analytically,
  not reconstructed by the old Gaussian averaging.
- Entry blend still permits **2.625972 px** maximum distance change. That
  temporary tradeoff preserves the inherited boundary; it is not hidden as
  a rigid-motion result.

## Implementation / verification

New adapter: `pipeline/cartoon_hand_motion_refinement.py`.
Use `with hand.hand_override(prepared.integration.body, source_frame):` around
the existing synchronized/scene composition call. The context overrides only
the exact prepared rig/state; torso/arm fields, original region masks,
protected pixels and camera fusion remain owned by the existing stack. Both
overridden functions restore on exceptions and nested exit.

`pipeline/tests/test_cartoon_hand_motion_refinement.py`: **10 tests passed in
71.844 s**; the strengthened geometry assertion also passed independently.
Tests cover actual render-failure restoration, nested restoration, unchanged
early/end frames, rigid inverse-map lengths/orthogonality, sustained motion,
native support, selected camera integration and exact accepted F173 eye hash.

All **58 native frames** were compared: **0 changed pixels outside declared
hand/wrist support**, **0 face/head changes**, **0 mug changes**. Source
F091–F146 differs from the old native rendering; F147 is below native raster
quantization and F148 is exactly unchanged. Selected integrated delivery
frames F091/F104/F115/F130/F147/F148 also have **0 differences outside the
prospectively declared transformed hand support** and **0 head/face/mug
changes**. Delivery support includes both native and post-camera 5px guards,
matching the existing compositor; it is not fitted to observed RGB changes.

The first test run exposed two faulty diagnostic assumptions: requiring F147
to visibly change despite subpixel motion, and omitting the compositor's
post-camera support guard. Corrected those checks, not the animation candidate
or any historical gate. No parameter sweep or second pose candidate.

## Local proof and limits

Workspace output: `outputs/edit/phase42-hand-refinement-v1/` (outside checkout).

- `late-hand-native-ab-30fps-v1.webp`: native 390×241 crops, existing left /
  candidate right, 58 frames, independently read back at **1,933 ms**.
  SHA-256 `71ba1e0d7b58eba9f59e48e9341bfaa4a6ad7315b8a3d63527cc0b842c0fae00`.
- `late-hand-native-keyframes-v1.png`: six native A/B samples; inspected at
  source scale (one visual self-review pass), no obvious tearing/hole/contact
  pop in those samples.
- `late-hand-study-report-v1.json`: frame range, geometry, all-frame native
  containment, sampled hashes and artifact inventory. Human review pending.

Tradeoff: coherent anatomy with restrained active emphasis, but less separately
articulated finger acting. This is planar motion around an authored contact
control, **not** a 3-D finger/contact simulation. Sampled still inspection and
deterministic tests do not establish normal-speed naturalness, believable
pressure, or that the gesture solves James's complaint. No complete scene was
encoded/reviewed, no audio was included or listened to, and delivery support
was checked at six frames rather than all 58. Recommend reviewing this one
real-cadence hand study with the independent mouth repair before expanding.
