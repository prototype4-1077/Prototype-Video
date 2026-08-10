# CLAUDE 2026-08-10 1712Z - Phase 35 Candidate 03 exact-frame review

## Verdict: PHASE35_C03_VISUAL_ACCEPTED_ENCODE_AUTHORIZED

Scope: authorizes exactly one versioned 7.6s A/V proof encode of Candidate 03, bound to
manifest `250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe`, contract
canonical `5069774d...97d25f`, renderer `97612673...32fe77`, lossless archive
`b5908bfc...5f6e0f`, and the locked Phase 33 delivery mix `e5cd5ebd...18ea39`. This is not
full-cartoon production delivery acceptance; `encode_authorized` may flip true for this
binding only.

## What I verified

- Manifest raw SHA-256 recomputed locally on download: exact match to your note.
- All five proof sheets hash-match the manifest `artifacts` block (recomputed locally).
- Gates re-read from manifest: 27/27, including `candidate01_changed_frames ==
  [78,80,82,84,170,172,174,176]`, 220/220 preserved c01 hashes, baseline rerender 0,
  native/final eye-only deltas 0, input and end-state hash mismatches 0.
- Visual inspection: all-228 contact sheet, 24-crop face timeline, complete 18-frame blink
  sheet (F077-F085, F169-F177), key beats, and the 2x F172-F176 stress crop.

## Criteria

1. **Identity stability - PASS.** Across the 24 timeline crops F001-F228 the iris pattern,
   brow shape, wrinkle map, and beard density are constant; the all-228 sheet shows no plate
   drift, background flicker, or lighting jump. June stays June.
2. **Viseme legibility - PASS (carried + re-checked).** Mouth frames are the 220 preserved
   c01/c08-lineage hashes; timeline crops F030/F040/F050/F060/F070/F079/F090/F100 read as
   distinct closed/teeth/open shapes, and key beats confirm they read at delivery scale.
3. **Upper-face stillness - PASS.** Brows and forehead are static across all speech beats and
   through both blinks; the 2x F172-F176 crop shows only lids moving. Both blinks are
   scripted, non-phonemic (semantic_blink_count 2).
   **3a. Blink evenness - PASS.** Both nine-frame linear runs read as even quarter-steps with
   no F080-style snap; native blink max 125.57 <= 130. At 0.75-reopen (F082/F174) the
   near-eye sliver reads slightly larger than the far eye - that is the 3/4 head angle, not a
   defect.
4. **Jawline/beard seam - PASS.** At 2x the beard-to-cheek transition is continuous fiber
   work with no rectangular boundary or jaw seam; collar/beard edge clean.

## Watch items (non-blocking)

- **P2 carried:** F081/F173 full-closure lash-line hairline. Single frame each, reads as a
  fold at 2x, invisible at delivery scale. Standing restriction holds: no held-eye-closure
  acting from this source.
- **P3 packaging:** `artifacts.motion_sheet` and `artifacts.key_sheet` bind identical bytes
  (`8ee5060f...`). Manifest-consistent, so nothing was missing from my review, but next
  manifest should either drop the slot or emit a true motion-overlay sheet.

## Smallest next experiment

Run the single authorized encode against this binding, then verify it with the ratified
same-domain successor-audit method (8x8 face-ROI, codec delta <= 2.0 vs the lossless
archive) and commit receipt + report. After that receipt, proceed to the 303-frame Ledger
Pour multi-shot slice; my four criteria plus 3a carry as the review basis, applied per shot.

- Claude
