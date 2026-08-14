# June Phase 38 acting-motion audit checkpoint

Date: 2026-08-11

Branch: `agent/phase38-acting-motion-audit-v1`

Base commit: `a3d48ad2d1576202cac0adcf7345156570bbd0da`

## Honest outcome

The immutable Phase 36 direct-address shot has strong facial performance, exact timing, and attractive source-textured art, but it does not yet have a close-view body acting rig. Phase 38 verifies this from both the authored control surface and the rendered pixels. It does not alter, rebuild, encode, promote, or claim human acceptance for any picture.

The current close-view body-motion contract exposes only:

- head X/Y translation and tilt;
- one rectangular shoulder translation;
- one rectangular breath translation/scale;
- camera push.

It exposes zero independent hand controls, zero independent arm controls, and zero authored gesture events. Maximum shoulder translation is 0.4 source pixels and maximum breath translation is 1.3 pixels across the full 7.6-second performance. The intentionally locked final hold remains correct and must be preserved.

## Rendered-pixel evidence

The audit streamed and hash-verified all 303 frames from the immutable 415,959,046-byte Phase 36 RGB24-XOR archive. It then applied the exact inverse of the declared uniform LANCZOS camera-push geometry to output F076-F237 and measured 161 adjacent transitions in six regions.

The stationary mug is the camera-resampling control. Median pairwise mean RGB deltas, relative to that control, are:

- table hand: **0.921x**;
- chest/overalls torso: **0.865x**;
- viewer-left arm: **0.643x**;
- face/head: **2.582x**.

The hand, chest, and arm therefore move no more than the stationary prop after the camera transform is normalized. The face clearly carries the performance. These ratios are descriptive evidence, not preregistered artistic pass/fail thresholds.

## Machine result

- 303/303 archived frames verified.
- 161/161 direct-address transitions measured.
- 14/14 diagnostic gates passed; zero failed.
- Archive SHA-256 before/after: `93eb2cd752d745a6f6fd534912ff68ee24e7bf72cf7cd406d2a366adea97d404`.
- Archive bytes and nanosecond mtime unchanged.
- Encoder processes: 0.
- Network calls: 0.
- Paid-service calls: 0.
- Picture rebuild: false.
- Human acting acceptance: false.
- Promotion: false.

Detached exact-camera reproduction:

- synthetic source commit: `8a963f7e86dbbb3680998e1ce86fae109e023df2`;
- source tree: `bf498bbf3a668bb848066a5174f46c911fea3122`;
- focused tests: 9/9 passed;
- diagnostic gates: 14/14 passed;
- reproduced inventory: 4/4 files;
- all reproduced file names, byte counts, and SHA-256 hashes match the primary package exactly.

The source bindings used by both runs are contract `fc6302b59421353266f74baa3d54b545f91302203c41084a2b0f4f93849c8e49`, implementation `2d5fcfa1632f38ad78fc262c602ba046325bc6e1883da9162f74c661988be1ee`, and tests `80f1d24fb1305024c7af9771958f834920a1774c80df0f4112177843e52c264e`.

Final evidence:

- report SHA-256: `0c3c8b0fa4d5773e20be2257e9dab4d67632c83bb2986682e09bf8f19784ade8`;
- contact sheet SHA-256: `78d8f3fe6922fa1bccd30e279ee229dc323ac70a96501689a0ab7a4f3a23ca14`;
- camera-normalized timeline SHA-256: `f43d8d8a4a059a9bcd11588d7ea613e3ad56c4a63ae97e6d4b0587a029174e4a`;
- region map SHA-256: `35b86a1b742178f78679fe942dbc6f6673cef9d65561b3f34c153e57c669e019`.

## Recommended next engineering slice

Build a close-view body source decomposition and one silent 162-frame performance A/B. It needs these independently owned controls:

1. torso translation/rotation;
2. viewer-left clavicle, upper arm, and forearm;
3. table-hand wrist, palm, and grouped fingers;
4. head-to-torso overlap;
5. breath independent of camera push.

The first bounded performance should contain only four authored beats:

- local F018-F034: notice, inhale, and settle into speech;
- F045-F082: one small table-hand opening with torso counter-motion;
- F091-F126: compact palm compression for the account/debt contrast, with one overshoot and settle;
- F127-F162: return the hand before the question finishes and reduce torso/breath into the compassion cut.

This is intentionally not an idle-motion loop. The final stillness and living porch atmosphere remain part of the performance.

## Required safety gates for the acting proof

- Preserve accepted face pixels outside declared transformed body support.
- Preserve mug and table contact.
- Give each body source pixel at most one final resample.
- Keep all five fingers readable at native and delivery scale.
- Prove anticipation, arc, overshoot, settle, and hold from rendered landmarks, not keyframe presence alone.
- Reject cyclic bobbing and continuous motion without story intent.
- Publish native, delivery-scale, difference, contact, and temporal-neighbor evidence before any picture rebuild authorization.

## Current external blockers remain separate

Phase 38 does not supersede the pending Phase 37 V4 eyelid human review or Candidate03 audio listen. The one-shot Candidate03 build remains consumed and must never be retried. The V4 GitHub publication still requires `gh auth login -h github.com`. No corrected full master may be encoded until the human audio and picture gates are explicitly closed.
