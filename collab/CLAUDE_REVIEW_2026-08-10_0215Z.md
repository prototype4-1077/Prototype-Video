# CLAUDE REVIEW 2026-08-10_0215Z - Phase 34 candidate-05 (exact-frame, visual + evidence)

Reviewed: collab/phase34_candidate_05/ at commit f426a4ad. Convention: F0NN = manifest
frame NN, 1-indexed. This review binds LF-normalized manifest SHA-256
27b7498a89939efc9c9d526be1609427fa2e72f1a39a1a85df67fde437dd3817.

## Evidence chain - INDEPENDENTLY VERIFIED

I did not run your reader. I wrote my own decoder for
phase34_rgb24_xor_previous_gzip_v1 (JSON header line, then XOR-vs-previous RGB24,
all-zero seed) against the fetched blobs:

- LF-normalized manifest SHA-256: MATCH (27b7498a...).
- Archive SHA-256: MATCH (ce53dcae...).
- All 96 reconstructed raw RGB24 frame hashes match the manifest, in order.
- Endpoint gate reproduced: F096 vs F001 = 0 changed pixels, exact.
- Blink is the only upper-face event: eye-band (y 200-340) changed pixels vs F001 are
  zero for all frames except F005-F011 (1389 / 4249 / 7349 / 7421 / 7349 / 4249 / 1389)
  - a symmetric eased envelope, better than candidate-04's hard blink.

The exact-frame archive protocol works and should be the standard for every future
candidate. Candidate-04's unexercised approval is moot; your hard-coded-gate finding
invalidates its machine evidence, and I agree with the rejection.

## The four standing criteria (exact frames, mouth ROI at 2x)

1. IDENTITY STABILITY - PASS in stills. Nothing above the mouth region changes in 96
   frames except the declared blink; scene, wardrobe, hairline, catchlights are
   pixel-locked (verified numerically, not by eye). June stays June in every frame.
   Motion caveat: adjacent-frame diff maps (e.g. F017->F018, F049->F050) show
   strand-level change across the ENTIRE beard/jaw/collar warp support every frame,
   not just near the mouth. Amplitude is low (full-frame mean delta 0.35-0.61), but
   this is exactly the signature that reads as beard shimmer at 24fps. Stills cannot
   settle it; only an encoded clip can.

2. MOUTH LEGIBILITY - FAIL at close-up, passable at delivery scale. Confirming your
   self-audit on all three counts: (a) C/E separation is insufficient - F038 vs F054
   mouth-ROI mean delta is 2.47 by my measure, and visually they are near-duplicates;
   (b) dental identity is unstable across poses - F018/F019 show small, individually
   defined teeth, F038/F054 a larger fused bright band (my bright-pixel dental width
   ranges 123-149 px across poses); (c) F contact (F058/F059/F062/F064) reads as
   "narrow slit with teeth glow", not lower-lip-under-upper-teeth. At delivery scale
   A/B/D/F/G/H still read; C vs E does not.

3. UPPER-FACE STILLNESS - PASS, and improved. Zero phoneme-coupled upper-face motion
   in all 96 frames, machine-verified end to end. The eased 7-frame blink is the
   correct shape of a deliberate event.

4. JAW/BEARD SEAM - FAIL: the seam is now the dark pasted-cavity rim. Every open pose
   carries a hard ~2-4 px near-black closed contour encircling the composited oral
   region: clearest at 2x in F018, F019, F033, F034, F038, F041, F042, F049, F050,
   F054, F066, F074, F080; heaviest in the B, D, G mid-zoom panels of the
   delivery-scale sheet, where the rim reads as a maroon ring and the cavity interior
   goes flat. No tearing or double exposure anywhere (H>X exit F080->F083 is clean;
   F082 native closed with no authored oral material, as declared) - but the rim makes
   the mouth read as a sticker in any shot tighter than delivery scale.

## Correction to my candidate-04 review

I passed criteria 2 and 4 on candidate-04 from sheet-scale stills. Candidate-05's
exact frames at 2x show the rim and the dental instability were present then too,
below the resolution of what I was judging. Your stricter audit caught what my
sheet-scale read under-called; this exact-frame protocol is why. Same-scale review is
now the floor for a pass from me.

## Candidate-06 - ordered fixes

1. Kill the rim first. Feather/alpha-match the oral composite boundary into the
   plate's own lip shadow. Acceptance: no closed contour around the oral region darker
   than the native lip line's own shadow in F017 (native closed reference), measured
   on the same 2x crops.
2. One dentition. A single tooth plate warped per pose, not per-pose tooth art.
   Acceptance: tooth-region similarity vs one reference dentition above a fixed
   threshold for all toothed poses.
3. C/E separation or retirement. Widen E's aperture/corner spread until the C/E
   mouth-ROI delta clears an explicit floor (candidate-05 measures 2.47 by my metric;
   set the floor from a pair you accept visually), or retire E into C.

Smallest next experiment: fix 1 only, on one pose (C / F038), published as a
before/after pair under the same exact-frame protocol. Isolates the compositing
boundary variable before dentition or viseme shape changes.

## For James

Taste call: is delivery scale the only shipping scale? At delivery scale the rim
mostly vanishes and the sequence reads well; every tighter framing exposes it. If
close-ups are ever planned, fix 1 is non-negotiable before any encode.

No encode requested, none approved. Review experiment: successful. - Claude
