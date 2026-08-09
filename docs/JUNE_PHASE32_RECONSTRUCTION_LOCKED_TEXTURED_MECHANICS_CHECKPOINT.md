# June Oxley Phase 32 - Reconstruction-Locked Textured Mechanics Checkpoint

Date: 2026-08-09

Branch: `agent/june-hero-unified-sculpt-phase-5`

Starting commit: `cdfb058fa855368dea07f0d6ce6f3f2d98d2b0ed`

## Honest outcome

Phase 32 delivery attempt v3 is complete as a bounded 1080p textured-mechanics machine proof. It passes all 76 strengthened gates after one H.264 encode and an independent 49-frame full decode. Human full-size review remains required, so facial-performance promotion is not yet approved.

Creative status: `machine_delivery_passed_human_review_pending`.

This proves that June's accepted pose-100 face, denim, hands, boots, mug, lighting, and porch detail can survive the exact accepted Phase 31 micro-settle. It does not yet prove expressive acting, lip sync, dialogue timing, changing occlusion, a complete scene, or audience preference.

## Version history

- v1 is an immutable rejected CRF-10 delivery. It passed preflight but failed decoded endpoint repeatability; it was never retried in place.
- v2 is an immutable 74/74 machine pass under audit revision 1. Final review found four evidence weaknesses: mixed alpha thresholds, sparse deformation sampling, vacuous seam evidence, and missing Phase 32 provenance hashes. Its receipt records `machine_delivery_passed_human_review_pending_superseded_by_audit_revision_2`.
- v3 is the only audit-revision-2 candidate. It repairs visible alpha coverage using nearby existing locked patch pixels, measures every lower-garment Jacobian, tracks a dense material evidence set, gates non-vacuous cross-owner seam coordinates, binds the report to exact contract/code hashes, and selects decoded seam crops from every required pair's worst diagnostic frame.

Never overwrite or re-encode v1, v2, or v3. Any later media change requires a new delivery-attempt version.

## Repository implementation

- `concept/characters/june_oxley_phase31_acceptance_v1.json`
- `concept/characters/june_oxley_phase32_rejected_delivery_v1.json`
- `concept/characters/june_oxley_phase32_superseded_delivery_v2.json`
- `concept/characters/june_oxley_phase32_acceptance_v3.json`
- `concept/characters/june_oxley_reconstruction_locked_textured_mechanics_v1.json`
- `pipeline/cartoon_reconstruction_locked_textured_mechanics.py`
- `pipeline/tests/test_cartoon_reconstruction_locked_textured_mechanics.py`

The renderer uses only nine byte-locked Phase 30 patch-local RGBA arrays and the locked clean porch. It rejects replacement patches, masks, coordinates, source reconstruction, or environment; operates in linear-sRGB premultiplied alpha; resolves one owner per visible pixel; preserves byte-exact endpoints; and publishes only through a staged one-encode/full-decode transaction.

Audit revision 2 additionally provides:

- one semantic occupancy rule: quantized alpha strictly greater than 16;
- zero visible geometry holes and zero character pixels outside expected visible geometry;
- per-region component inventory matching the locked source rather than falsely assuming every painted region has one component;
- a minimum of 138 evaluated pixels for every required seam pair on every moving frame;
- maximum cross-owner source-coordinate divergence p95 of `13.309522642991462` source pixels against a `14.0` gate;
- all 92,851 lower-garment support Jacobians evaluated per moving frame;
- 19,508 persistent tracked material points over the full sequence;
- report provenance containing raw/canonical contract hashes, implementation hash, and source commit;
- decoded seam evidence for all eight declared pairs at rest and at each pair's candidate-disagreement argmax frame.

## v3 delivery evidence

Output directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase32-reconstruction-locked-textured-mechanics-v3`

Video:

- file: `june-phase32-reconstruction-locked-textured-mechanics-v3.mp4`;
- SHA-256: `cab1e6ec07a5a1948c968e1d04e5adfa32b697924f4693c7d31cdcf318d98f73`;
- bytes: `52,735,619`;
- H.264/yuv420p, 1920x1080, 30 fps, 49 frames, `49/30` seconds, no audio;
- exactly one v3 encoder process;
- all 49 frames fully decode;
- first/last subject PSNR: `99.0 dB`.

Report:

- file: `june-phase32-reconstruction-locked-textured-mechanics-report-v3.json`;
- SHA-256: `a52f0ff0f8d22ce8e6abb093524c9ba8e616084a4f01f6f4e40a7643baaee7b6`;
- `preflight_passed=true`;
- `machine_passed=true`;
- 76/76 gates pass;
- audience status: `machine_delivery_passed_human_review_pending`.

Decoded review artifacts:

- contact sheet SHA-256: `4f15ad9a00eca588cb7076b60435d05841228ca7e7a9ff08be7a405335c28756`;
- identity strip SHA-256: `8ce66dc7cbbd2494bb6171aa1caaf7e48438bd6c8731cc958300602ebe61cedd`;
- eight-pair seam detail sheet SHA-256: `6a7d26b23950d91ad42158a319ce1a38627b6a93a72b6cc0cc9104c30fe5c382`.

Decoded fidelity:

- worst subject PSNR/SSIM: `42.13159485467596 dB` / `0.9862520694732666`;
- worst face PSNR/SSIM: `40.036451873788494 dB` / `0.9872577786445618`;
- exact endpoint loop PSNR: `99.0 dB`.

Motion/deformation evidence:

- maximum deformation anisotropy: `1.2181370362437147`, gate `1.22`;
- maximum tracked velocity: `5.356180755551532`, gate `5.5`;
- maximum tracked acceleration: `2.4720834256391386`, gate `2.5`;
- maximum tracked jerk: `1.4448301316729197`, gate `2.0`.

The old `5.0` velocity ceiling came from a sparse 64-point estimate of `4.863154517832324`. Audit revision 2 found the true dense tracked maximum. Because Phase 32 is locked to accepted Phase 31 motion, the revision records both measurements and uses the small round `5.5` ceiling rather than concealing the changed measurement domain.

## Validation

- Combined Phase 29-32 regression: 90 tests passed in `279.123` seconds.
- Phase 29 remains fail-closed for its two known historical motion failures.
- Module compilation passes.
- `git diff --check` passes.
- Independent final review found no P0 or P1 blocker and confirmed that `machine-complete, human-review-pending` is defensible.

## Program capability at this checkpoint

The zero-cash pipeline can now reconstruct June exactly from accepted production pixels, animate a deterministic connected full-body settle, preserve detailed texture through deformation, composite at 1080p, enforce fail-closed provenance/topology/seam/identity/deformation/delivery gates, and produce one-encode reviewable evidence.

It still cannot produce a competitive finished cartoon by itself. Missing production systems include facial pose assets, blinks, gaze, visemes, lip sync, expressive timing, large articulation, unseen-surface handling, shot-to-shot acting continuity, final dialogue/sound, and human preference evidence.

RL remains deferred. With no blinded preference dataset, a reward model would optimize proxies and can learn to game the machine gates. After human-reviewed A/B examples exist, bounded local search or preference learning may tune timing, blink placement, gaze, anticipation, overshoot, and corrective weights while identity, topology, contact, and provenance remain hard constraints.

## Exact resume sequence

1. Ask the user to review the v3 MP4 at full size. Record explicit accept/reject notes; machine pass is not human approval.
2. If accepted, update the v3 receipt's human-review state in a new receipt revision without altering the media.
3. Build Phase 33: a reconstruction-locked close-face blink/gaze/brow/cheek/viseme atlas.
4. Produce one 6-10 second voiced porch acting shot with setup, thought beat, spoken line, reaction, and settle while preserving the Phase 32 body/porch control.
5. Gate eye/mouth topology, lip closure, face identity, temporal popping, gaze continuity, audio sync, exact endpoints, and decoded face fidelity.
6. Run a blinded A/B against the Phase 27 authored facial control.
7. Begin bounded optimization only after several human A/B choices exist.

## Recommended next step

Review the v3 video at full size. If June's subtle settle and all eight joint areas look acceptable, proceed to Phase 33 facial acting. The largest remaining quality gap is performance—eyes, mouth, voice, thought, timing—not another round of body-proof infrastructure.
