# June Oxley Phase 33 v4 - Semantic Face Evidence Checkpoint

Date: 2026-08-09

Branch: `agent/june-hero-unified-sculpt-phase-5`

Starting commit: `d6bb6f83c4ad9225ecb9aed76bcf09355cd117f3`

## Outcome

Phase 33 v4 passes its one permitted encode and every locked machine gate. It is byte-identical to the artistically reviewed v3 RGB sequence; v4 corrects only the invalid evidence contract that compared decoded high-contrast mouth-boundary motion against a threshold declared in a different measurement domain.

The decoded 1920x1080 result was inspected as all 60 frames and as a full-size 15-pose sheet. Identity, background, and body stay locked. The bilateral blink closes without sclera or socket leakage. B, A, and F remain distinct, facial hair returns to the foreground, and the frame-32-to-33 oral transition reads as continuous opening rather than a one-frame replacement flash.

AI-assisted review passes v4 as a silent semantic-face technical proof. Human full-size review remains pending, and this is not accepted as a production cartoon. The procedural mouth still has less material richness and volume than the authored June image.

Creative/technical status: `machine_passed_ai_decoded_review_passed_human_review_pending`.

## What is now proven

- exact authored GS070 pixels at neutral frames 1, 8, 19, 22, and 60;
- a complete bilateral blink using isolated, source-aligned lid surfaces rather than a full eye photograph crossfade;
- depth-ordered cavity, tongue, lower teeth, upper teeth, lips, moustache, and beard ownership;
- distinct B-to-A-to-F articulation with zero changed pixels outside declared feature supports;
- exact first/last return and no body, head, camera, atmosphere, audio, or RL layer hiding the facial result;
- byte identity between all 60 reviewed v3 RGB frames and all 60 v4 pre-encode frames;
- fail-closed, contract-pinned output and exactly one v4 video encode.

## Encoded evidence

Output directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase33-semantic-face-proof-v4`

- video SHA-256: `350f8aeb9cad5820c5d20506362822edfeae27674bd83daf1cb7ec96d1192173`;
- report SHA-256: `9fabc0d5cce538216564f729fed8cae25e506bd4ca551ee7333dc5886c7d254d`;
- decoded contact-sheet SHA-256: `72f23cad8f83e2f3bcda0ab402f2f91190f3a993fd6519af636a58bbd0198e8b`;
- H.264/yuv420p, 1920x1080, 30 fps, 60 frames, 2.0 seconds, silent;
- exactly one encoder process and all 60 frames decoded;
- 15 of 15 locked delivery gates pass;
- worst full-frame PSNR: `42.642228 dB`;
- worst face PSNR/SSIM: `41.765828 dB` / `0.988893`;
- worst eye and mouth PSNR: `41.525078 dB` / `41.215611 dB`;
- minimum decoded sharpness: `284.786804`;
- maximum decoded local 8x8 transition: `141.359375` against a predeclared `150.0` ceiling;
- first/last decoded PSNR: `99.0 dB`.

V4 and the rejected v3 attempt have the same video hash. This is intentional evidence that no pixels were retuned after seeing the v3 decode. The v3 rejection remains valid under its locked but mis-scoped `52.0` threshold; v4 is a separately versioned attempt with the corrected threshold declared before encoding.

## Remaining ceiling

- only B, A, and F exist; the other visemes and coarticulation are not authored;
- the lips use procedural color and shape rather than source-textured, volume-preserving deformation;
- the jaw does not drive chin, cheek, nasolabial, or beard response;
- brows, pupils, gaze, asymmetry, anticipation, drag, and emotional acting are absent;
- there is no approved voice performance or decoded A/V-sync proof;
- the close-front rig is separate from the accepted Phase 32 three-quarter body representation;
- human full-size review is still required before any production claim.

## Validation

- eight focused v4 evidence-contract, byte-identity, mutation, preview-binding, threshold, output-path, and acceptance-scope tests pass;
- ten v3 semantic compositor tests pass;
- 46 tests pass across the v4/v3 semantic proofs, both close-face experiments, and the GS070 resolution scene;
- the source compiles and `git diff --check` passes;
- no paid or hosted service was used;
- no reinforcement learning was used because no preference dataset exists yet.

## Exact resume sequence

1. Keep v3 rejection and v4 technical proof immutable.
2. Create a new unvoiced material/deformation revision rather than re-encoding v4.
3. Extract source-colored upper/lower lip, moustache, chin, and beard-clearance fields from the authored GS070 plate.
4. Replace procedural lip slabs with a compact local deformation cage that preserves texture and oral volume.
5. Author the full nine-viseme set and in-between them through jaw-, lip-, and tongue-aware parameters, not bitmap pose crossfades.
6. Render randomized, label-hidden A/B sheets comparing the accepted v4 proof with the new revision while holding all non-face pixels exact.
7. Collect several human preferences before fitting any bounded optimizer. Identity, topology, ownership, endpoints, provenance, and clock stay hard constraints.
8. Only after the new mouth passes should the pipeline add a voice, coarticulation timing, emotional acting, and the Phase 32 three-quarter adapter.

## Recommended next step

Build the source-textured lip/jaw deformation revision with all nine visemes, still silent and still locked to the GS070 plate. This is the largest visible quality gain available before voice or reinforcement learning: it attacks the current flat-mouth ceiling without adding motion that could conceal defects.
