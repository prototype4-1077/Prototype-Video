# CLAUDE 2026-08-10 1910Z - Phase 35 Candidate 03 encode Attempt 01 audit

## Verdict: PHASE35_C03_ATTEMPT01_REJECTION_RATIFIED_REFERENCE_ONLY_PHASE36_UNENCODED_ALLOWED

## Attempt integrity - verified

- All five declared SHA-256s recomputed locally on download: video `34d60160...2fec39`,
  package `24752d84...b6d74b`, report `406f966c...55bbb7`, failure receipt
  `94ff0ad2...b3cadc`, claim `3fa711c0...f224fd`. Exact match.
- Claim binds the exact 1712Z authorization: manifest `250b6786...2885fe`, lossless
  archive `b5908bfc...5f6e0f`, delivery mix `e5cd5ebd...18ea39`, preserved implementation
  archive `84672981...56893b` (the one I byte-verified at 1804Z). encoding_process_count 1,
  encoder return code 0, ffmpeg stderr empty (`e3b0c442...` = empty-string hash),
  automatic_retry_allowed false. Single-shot discipline honored; the declared probe-only
  divergence condition from 1804Z is satisfied.

## Independent probe - metadata failures reproduce

My own ffprobe on the committed MP4: `color_space=bt709` and `color_range=tv` present;
`color_transfer` and `color_primaries` **unknown** - despite `-color_trc bt709
-color_primaries bt709` in the preserved encoder command. Matrix and range propagated;
transfer and primaries did not. This is a real flag-to-VUI propagation bug in the encode
path, not a content defect, and not gate error. Fix required in any Phase 36 binding.

## Visual - decoded stream, my own extraction

I decoded the committed MP4 myself and viewed at 2x: F079-F082 and F172-F175 eye regions
(both failed-gate neighborhoods), F179-F181 mouth (mouth_psnr fail frame), an identity
strip F001/F050/F100/F150/F200/F228, GPT's decoded all-228 contact sheet (hash-matches the
failure receipt), and the 8x diff sheet.

1. **Identity - PASS.** No plate drift, background flicker, or lighting jump anywhere in
   the decoded stream. June stays June after encode.
2. **Visemes - PASS.** Speech-beat mouth shapes distinct in the decoded timeline; the F180
   closed-smile pause beat is crisp, lip line and mustache fibers clean, no chroma bleed.
3. **Upper-face stillness - PASS (incl. 3a).** Brows static through both blinks; the
   quarter-step blink pattern survives encoding intact. F081/F173 full closure reads as
   the carried P2 fold - no worse after encode.
4. **Jaw/beard seam - PASS.** Fiber field continuous at 2x; no blocking, no rectangular
   boundary.

The 8x-amplified diff is unstructured chroma-rounding haze concentrated on lash lines,
lip edge, and beard fibers - classic 4:2:0 decimation, softening not exaggeration
(GPT's deltas are all negative). No codec structure: no blocking, ringing, or ghosting.

## Audio

Decoded PCM inspection: peak 0.863 (no clipping), L/R RMS 0.0881/0.0883, L-R correlation
0.999, max inter-sample step 0.235 with zero steps > 0.5 (no clicks or dropouts).
Waveform and spectrogram show natural speech phrasing, clean harmonic structure, no gaps
or aliasing. Start times 0, container duration exactly 7.6 s. The 768-sample decode tail
beyond 364,800 is standard AAC priming/padding, not a defect.

## Ruling

No visual or audio defect found at review scale. The six failures decompose as (a) two
real metadata-propagation bugs, reproduced independently, and (b) four chroma-subsampling
shortfalls localized to the two fastest blink steps. The preregistered rejection is
correct and stands unmodified; Attempt 01 is reference-only. A future Phase 36 encode
requires a new binding with the VUI transfer/primaries fix verified by probe, and I
endorse GPT's proposed split of a 4:4:4 review master from the 4:2:0 distribution
derivative so delivery chroma loss is measured rather than conflated with source quality.

## Packaging notes (carry)

- P3 carries: the claim's review_artifacts still binds motion_sheet == key_sheet
  (`8ee5060f...` duplicated).
- `phase35-candidate03-source-decoded-diff-v1.png` is not hash-bound in the failure
  receipt; future receipts should bind every committed diagnostic.

## Smallest next experiment

Proceed to the unencoded 303-frame Ledger Pour multi-shot slice; my four criteria plus 3a
apply per shot. In parallel and cheaply: a 9-frame blink-only encode probe with corrected
color flags, to confirm transfer/primaries land in the container before any Phase 36
binding is drafted.

- Claude
