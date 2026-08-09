# June Oxley Phase 33 - Close Facial Acting Checkpoint

Date: 2026-08-09

Branch: `agent/june-hero-unified-sculpt-phase-5`

Starting commit: `0a9e655aca7c9bfd6103e60afb4dcfb675d90d90`

## Honest outcome

Phase 33 now has two complete zero-cash 7.6-second voiced close-view technical experiments, but it does not yet have an artistically viable facial system. Delivery attempt v2 passes 30/30 clock, containment, sampled decode-quality, and stream proxy gates after one H.264/AAC encode. Independent visual review rejects it for artistic promotion because it still crossfades flat eye and mouth photographs rather than animating semantic, depth-ordered facial parts.

This phase does not claim that the existing frontal atlases can be pasted into Phase 32. They cannot. Phase 32 remains the locked `WIDE_BODY_3Q` control, and Phase 33 is a separate `CLOSE_HERO_FRONT` view adapter. A later scene may cut between them; it may not blend or relabel one view as the other.

Creative status: `machine_proxy_gates_passed_ai_visual_review_rejected_representation`.

## The performance

- 1920x1080, 30 fps, 228 frames, 7.6 seconds;
- frames 1-24: visible attention and thought beat;
- frames 25-162: shifted local Piper Norman dialogue performance;
- frames 168-201: compact reaction/nod;
- frames 202-228: locked face/body settle with live porch atmosphere;
- dialogue: “Funny thing: the account got lighter before the debt did. What are you carrying just because the ledger says so?”;
- exact 48 kHz clock: 364,800 samples, 1,600 samples per video frame;
- final mix and dialogue-analysis stem are byte locked to the regenerated Rhubarb cues;
- no hosted or paid service was used.

## Version history

### v1 - immutable visual rejection

V1 passed all 41 machine gates and fully decoded, but AI-assisted visual review rejected it. The registered neutral and X crops replaced the authored face, several phonemes ballooned the oral cavity, and overlapping upper-face/mouth RGB crops depended on painter order. Sharp pixels and accurate clocks did not make that acting acceptable.

V1 remains immutable at:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase33-close-facial-acting-prototype-v1`

The rejection receipt is `concept/characters/june_oxley_phase33_rejected_delivery_v1.json`.

### v2 - immutable technical experiment, visual rejection

V2 treats the authored GS070 plate as the base and applies attenuated atlas replacements before global head motion. Neutral expression and X mouth change zero source pixels. Mouth ownership removes expression influence from all 11,376 overlapping feature pixels, preventing ambiguous double ownership. Independent code review established that these are not registered neutral-state deltas: each state is subtracted from the authored plate, so weighted states remain crossfades toward foreign atlas pixels. It also established that feature pixels can be resampled by overlapping shoulder/head warps and the camera resize, contrary to the contract's one-resample claim.

V2 remains a bitmap corrective system, not semantic facial geometry. Decoded diagnostic strips show doubled/translucent irises and eyelids, mouth states dissolving through the moustache/beard, and weak viseme differentiation. Human review is still useful, but it cannot promote this representation without a semantic rebuild.

## Repository implementation

- `concept/audio/june_phase33_direct_address_dialogue_v1.wav`
- `concept/audio/june_phase33_direct_address_mix_v1.wav`
- `concept/scripts/june_phase33_direct_address_v1.txt`
- `concept/style_frames/june_phase33_direct_address_rhubarb_v1.json`
- `concept/style_frames/june_phase33_direct_address_expression_v1.json`
- `concept/style_frames/june_phase33_direct_address_body_motion_v1.json`
- `concept/characters/june_oxley_phase33_close_facial_acting_v1.json`
- `concept/characters/june_oxley_phase33_rejected_delivery_v1.json`
- `pipeline/cartoon_close_facial_acting.py`
- `pipeline/tests/test_cartoon_close_facial_acting.py`
- `concept/characters/june_oxley_phase33_close_facial_acting_v2.json`
- `concept/characters/june_oxley_phase33_rejected_delivery_v2.json`
- `pipeline/cartoon_close_facial_acting_v2.py`
- `pipeline/tests/test_cartoon_close_facial_acting_v2.py`

## V2 delivery evidence

Output directory:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\edit\phase33-close-facial-acting-prototype-v2`

Video:

- file: `june-phase33-close-facial-acting-prototype-v2.mp4`;
- SHA-256: `bd43dcf1560ccc64ed3cd56bbb1c968e962c5e662fbdf0032960f9167ab37faa`;
- bytes: `7,668,651`;
- H.264/yuv420p, 1920x1080, 30 fps, 228 frames, 7.6 seconds;
- AAC, 48 kHz stereo;
- exactly one v2 video encoder process in this recorded invocation (the implementation does not prevent another output directory from being used);
- all 228 frames fully decoded.

Report:

- file: `june-phase33-close-facial-acting-report-v2.json`;
- SHA-256: `73bc1e4a69e4f7b6829de60d435a6f79e761b7fd55073c2128a950aa82add4d5`;
- 30/30 codec/clock/containment/sampled-fidelity proxy gates pass;
- accepted production delivery: `false`;
- human review required: `true`.

Corrective evidence:

- neutral source pixels changed: `0`;
- X-mouth source pixels changed: `0`;
- raw expression/mouth overlap pixels evaluated: `11,376`;
- multiply owned overlap pixels after ownership resolution: `0`;
- stable identity pixels: `222,410`;
- changed pixels outside owned feature support: `0`;
- bilateral blink mean absolute delta: `29.4242`;
- frames with observed non-X mouth motion: `131`.

Decoded fidelity:

- worst full-frame PSNR: `41.5821 dB`;
- worst face PSNR/SSIM: `41.0886 dB` / `0.972670`;
- worst eye PSNR: `40.9494 dB`;
- worst mouth PSNR: `40.6424 dB`;
- minimum encoded Laplacian variance: `219.3065`.

## Validation and independent audit

- Phase 33 v2 corrective, v1 facial/audio, and GS070 regression: 28 tests passed in 62.5 seconds.
- V1 focused suite: 14 adversarial tests pass.
- V2 focused suite: 7 tests pass.
- Module compilation passes.
- `git diff --check` passes.
- The recorded invocation used one encoder process, fully decoded, and atomically published its output directory. Code review found that the renderer does not bind the requested directory to the contract, so this is evidence about the invocation rather than enforcement of a globally unique attempt.

Independent adversarial review found these false-positive areas that block any broader machine-proof claim:

- atlas states are differenced from the authored plate rather than a registered neutral/X state, so the claimed correctives are attenuated replacements;
- callers can bypass attempt uniqueness by supplying another output directory;
- the required preview is a 16-still sheet whose existence, contents, and review verdict are not bound to the 228-frame attempt;
- the claimed single post-composite resample is contradicted by overlapping cubic shoulder/head warps followed by a LANCZOS camera resize;
- decoded regional fidelity samples only 16 review frames rather than all 228;
- stable identity scope is measured before final head/camera transforms rather than source-aligning final pixels;
- blink, gaze, and mouth-motion checks are RGB-delta proxies rather than semantic topology/landmark evidence;
- encoded AAC content and A/V lag are not decoded and compared with the locked mix;
- mean temporal deltas can hide a localized one-frame pop;
- endpoint semantics are incomplete;
- the fixed v2-left/v1-right sheet is not genuinely blinded;
- failure cleanup can leak a staging directory when the single rejected-path name already exists.

These findings do not invalidate the exact clock, full decode, file hashes, per-invocation encoder-process count, or registered-mask containment evidence. They narrow the report's `machine_passed` field to those proxies and prevent artistic, semantic, or transaction-policy promotion.

## What the program can do now

The zero-cash pipeline can render a voiced, cue-driven, 1080p close shot with exact audio/video timing, versioned immutable delivery, head/camera/atmosphere motion, complete video decode, and review evidence. It can also preserve the accepted detailed Phase 32 body/porch pixels in a separate three-quarter view. It cannot yet claim anatomically valid lip sync, blink, gaze, or facial topology.

The pipeline still does not have one continuous high-quality facial representation even in the close camera, much less across both cameras. Complete RGB feature crops are the wrong interpolation unit. Explicit lids, pupils, lips, jaw, cavity, teeth, tongue, moustache, and beard-clearance ownership are now the primary blocker; the Phase 32 angle and unapproved voice casting follow after that.

## Reinforcement learning disposition

RL remains deferred. The pipeline now has a useful A/B unit, but one AI-reviewed pair is not a preference dataset. After humans rank several identity-safe alternatives, bounded optimization may tune state weights, two-frame transition timing, blink placement, gaze lead, nod amplitude, and phrase timing. Identity, feature ownership, audio clock, topology, provenance, and delivery gates must stay hard constraints rather than reward terms.

## Exact resume sequence

1. Show v2 as the clearest evidence of the remaining defect; record any user observations, but keep its rejection receipt immutable.
2. Build Phase 33 v3 as a GS070-matched semantic, occlusion-aware 2.5D face: sclera, iris/pupil, upper/lower lids, brows, cavity, skull-locked upper teeth, jaw-driven lower teeth/tongue, upper/lower lips, moustache, chin, and beard-clearance layers.
3. Drive those layers with a local landmark mesh and piecewise-affine or moving-least-squares deformation. Never crossfade complete eye or mouth photographs.
4. First produce a 60-frame silent proof: exact neutral, one bilateral blink, B-to-A-to-F articulation, and exact neutral return with head motion disabled.
5. Add all-frame source-aligned identity, semantic topology/occlusion, per-region temporal-pop, exact endpoint, and decoded-audio/A-V-sync tests before any voiced re-encode.
6. Only after the GS070 semantic proof passes human review, author the same semantic rig as `POSE100_3Q_FACE` inside Phase 32 coordinates.
7. Collect blinded human A/B choices; only then begin bounded preference optimization.

## Recommended next step

Build the 60-frame GS070 semantic occlusion proof next. The experiment has now shown that neither full-strength RGB atlas replacement nor attenuated RGB-delta blending can deliver competitive facial acting. A small, depth-ordered lid/pupil/lip/jaw/oral rig is the shortest honest path forward; the Phase 32 three-quarter version should follow only after that representation works.
