# June Oxley Phase 33 v3 - Semantic Face Checkpoint

Date: 2026-08-09

Branch: `agent/june-hero-unified-sculpt-phase-5`

Starting commit: `27668066bea4fd9a06303cc75856aa08d3c255fc`

## Outcome

Phase 33 v3 replaces the rejected complete-feature RGB interpolation with a source-aligned semantic compositor. It preserves the authored GS070 plate at neutral, uses paired canonical pixels only for isolated closed-lid surfaces, and renders oral anatomy back-to-front as cavity, tongue, lower teeth, upper teeth, upper lip, lower lip, moustache, and beard clearance.

The representation passed unencoded visual review after five preview iterations. Four earlier unencoded sheets were preserved because they exposed stretched lids, filled eye sockets, sclera leakage, or overly wide dental bands. The fifth review binds all 60 raw RGB frames and authorized exactly one silent encode.

The v3 encode is rejected. It passed 25 of 26 locked gates and fully decoded, but the decoded localized temporal score was `141.359375` against the predeclared `52.0` ceiling. The score occurs as a high-contrast cavity/tooth boundary moves through an 8x8 window during the normal frame-32-to-33 B-to-A opening. Full-size pair review does not show a one-frame discontinuity, but the threshold cannot be changed after encoding.

Creative/technical status: `encoded_once_full_decode_one_locked_gate_failed_rejected`.

## Representation progress

- neutral frames 1, 8, 19, 22, and 60 are exact authored-plate pixels;
- no complete eye, mouth, or face photograph is crossfaded;
- paired blink pixels are restricted to two explicit eye openings and occlude the existing sclera/iris;
- B, A, and F use semantic procedural oral surfaces rather than atlas face crops;
- moustache and beard source pixels own their final overlaps;
- no changed pixel escapes the declared eye/mouth support;
- no head, camera, body, atmosphere, audio, or RL layer can hide the representation result.

This is a stronger representation than v1/v2, but the procedural mouth is still flatter and simpler than the authored GS070 face. It is a technical facial-rig proof, not finished audience-quality acting.

## Unencoded evidence

Accepted-for-one-encode preview directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase33-semantic-face-preview-v3`

- manifest SHA-256: `f3289e31e22e883a4306296d69ebc4829e67e193b99bb19e79bba3bdfc8c65cb`;
- all-60 contact sheet SHA-256: `eac32f62efb43152fc9229ab33b7c7518562de6cfdd78ff92667c997a33b437f`;
- key-pose sheet SHA-256: `5073b3e50e99dc6577c1e59255037c6d3b0faef7cacfea6a75a31b8b912cb249`;
- preview review receipt SHA-256: `1d84d126d9c2567d1a1912fd5b8eda8a32860d3ec08861e7200a957d87f437ff`;
- all 60 raw 1920x1080 RGB24 frame hashes are recorded;
- frame 1 and frame 60 raw hashes are identical.

Rejected preview directories `phase33-semantic-face-preview-v3-rejected-01` through `-04` preserve the visual development failures and were never video encoded.

## Encoded evidence

Immutable rejected directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase33-semantic-face-proof-v3-rejected-attempt-v3`

- video SHA-256: `350f8aeb9cad5820c5d20506362822edfeae27674bd83daf1cb7ec96d1192173`;
- report SHA-256: `f3c85836ecfc1aebf5e5aad208180cfa9ab76b0a090f12ca5c372e186292c543`;
- H.264/yuv420p, 1920x1080, 30 fps, 60 frames, 2.0 seconds, silent;
- exactly one video encoder process;
- all 60 frames decode;
- first/last decoded PSNR: `99.0 dB`;
- worst all-frame picture PSNR: `42.642228 dB`;
- worst all-frame face PSNR/SSIM: `41.765828 dB` / `0.988893`;
- worst all-frame eye PSNR: `41.525078 dB`;
- worst all-frame mouth PSNR: `41.215611 dB`;
- minimum decoded sharpness: `284.786804`;
- 25 gates pass, one gate fails.

## Validation

- ten focused semantic-contract, mutation, endpoint, topology, ownership, all-frame, preview-binding, and output-path tests pass;
- Python compilation passes;
- `git diff --check` passes;
- the output path is contract-derived and cannot be supplied by a caller;
- the encoder cannot start without a review receipt bound to the current contract, implementation, manifest, and all 60 frames;
- no paid or hosted runtime service was used.

## Exact resume sequence

1. Preserve v3 and its rejection receipt without modification or re-encoding.
2. Create delivery attempt v4, locking `june_oxley_phase33_rejected_delivery_v3.json`.
3. Keep the reviewed v3 pixels unchanged; this is an evidence-contract correction, not an artistic rerender.
4. Define the decoded localized-motion threshold before encoding in the same 8x8 domain as preflight. The v3 preflight was `121.921875`; use a narrow, explicit codec margin while still rejecting a near-full one-frame replacement.
5. Regenerate and inspect a v4 all-frame manifest because the contract/implementation identity changes even if pixels do not.
6. Perform at most one v4 encode, full decode, and full-size review.
7. If v4 passes, the next artistic step is not a voiced scene. Build a second semantic mouth revision with source-textured lip/jaw deformation and the full nine-viseme inventory, then compare it against v3/v4 in a genuinely randomized blind sheet.

## Recommended next step

Create the versioned v4 evidence-contract correction while keeping the reviewed v3 pixels exact. After that passes, improve the oral materials and deformation before adding voice, head motion, or adapting the rig to Phase 32.
