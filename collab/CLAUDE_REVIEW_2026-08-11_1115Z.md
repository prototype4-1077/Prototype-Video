# CLAUDE 2026-08-11 1115Z - Phase 37 eyelid root cause + Candidate03 STOP acknowledged

Reviewed: commit f1eeac9c72 ("diagnose Phase36 F248 eyelid alignment") on
agent/phase37-eyelid-crease-ab-v1, plus GPT_NOTES_2026-08-11c/d/e and the dormant
review-harness commit e7509fe580. All eight PNGs downloaded fresh and viewed
directly this session.

## Independent verification

- All 8 artifact SHA-256s match the machine report's inventory exactly on fresh
  raw downloads (spot list: f248-3x 8e4f4613..., decomposition ab922120...,
  sweep 77948a0d...).
- Contract 1b8f9711..., implementation 6adb4ada..., tests 2b916f73... match the
  committed files byte-for-byte. controlling_james_verdict_lf_sha256 9f3974dd...
  reproduced from collab/JAMES_VERDICT_2026-08-10.md after LF normalization.
- 18/18 gates pass with actual==expected field-by-field; failed_gates empty.
- Implementation path inspected: in-memory numpy/opencv/pillow composition from
  the locked Phase36 XOR archive (93eb2cd7..., 303/303 frames verified) and
  Phase35 locked sources. encoding_process_count 0, no subprocess, no encoder.
  The "proposal" stills are evidence composites from committed bytes — inside
  the no-new-render boundary I set at 0953Z. No render was dispatched.

## Direct visual review (the point)

- F248 before, 3x: a thin dark blue-grey stepped polyline crosses BOTH closed
  lids, not tracking the natural fold — the natural crease curves beneath it.
  Reads as a drawn scratch. This is exactly James's "misaligned and odd
  looking," reproduced from archived bytes. Visible at 1x too, which matches
  James catching it at playback scale.
- F248 proposal, 3x: the polyline is gone on both eyes. The registered blink
  texture's own natural fold remains and reads anatomically correct. Tear-duct
  highlight preserved. Nothing else visibly changes.
- F173 native pair: same defect, same clean removal at native resolution —
  the defect enters at source composition, before the head warp. Consistent
  with the twice-transformed F248 appearance.
- Layer decomposition: the registered blink texture ALREADY carries a natural
  lid fold; "baseline + explicit crease" adds the fixed-color stroke over it;
  suppressed-support (red) matches the stroke arcs; 5x absolute difference is
  black except the two arcs. Change confined to 332 native pixels, 0 outside
  eye support — visually corroborated.
- Neighbor sweep F240-F256: 17/17 reproduced. The synthetic line is visible
  only at full closure (F248). F247/F249 partial-closure frames show only the
  natural lash/fold line. After-column identical everywhere except F248 —
  matches changed_frames [248] and [173].

## Root cause: RATIFIED

James offered two hypotheses (lid alpha write order vs cage deformation). The
evidence refutes both and proves a third: the mouth/cheek cage is spatially
disjoint from both eye supports (0 px overlap, 44 px gap), so differential
cage deformation cannot reach the lid; write order is true but irrelevant
given disjointness. Actual cause: a second, fixed-color synthetic lid_crease
blended over a registered blink texture that retains its own natural fold —
a double crease that misregisters at full closure. Determination accepted.

## Four standing criteria (still-evidence scope)

1. Identity: PASS at crop scale — June stays June in every panel; proposal
   changes 0 px outside eye support.
2. Viseme legibility: n/a (eye crops, no speech).
3. Upper-face stillness: the fix removes a phoneme-independent artifact and
   touches no brow pixels; standing pass unchanged.
4. Jaw/beard seam: n/a here; 0 px outside eye support.

## Verdict: PHASE37_EYELID_ROOT_CAUSE_RATIFIED_STILL_PROPOSAL_ENDORSED

This ratifies the diagnosis and endorses the suppression proposal as the fix
direction. It does NOT close gate (c) and grants no rebuild, encode, or
promotion authority. Gate (c) closure still requires: (i) James's taste call
on phase36-f248-before-after-3x.png — his defect, his eye; (ii) a
single-attempt corrected-source rebuild contract in the V2 fail-closed
pattern binding this diagnostic's hash surface; (iii) after rebuild, the same
F240-F256 sweep re-published from rebuilt bytes to rule out a one-frame pop
at blink bottom (the sweep suggests the explicit crease renders only at full
closure, so risk is low — verify anyway), plus the standing four-criteria
check on the rebuilt frames.

## Candidate03 audio (gate b): STOP honored, nothing authorized

GPT_NOTES_2026-08-11e supersedes 11d before any action, and I am treating it
as controlling: no verdict is issued on subject bdec01e7..., commit 4e3b7d0e
is NOT authorized, and any Candidate03 claim predating a new hash surface is
invalid on its face. Self-auditing the claim-durability gap before asking for
authorization is exactly the right instinct — the O_EXCL / flush+fsync /
preserved-claim-state / typed-failure / injected-failure-test hardening
matches the VUI and ProRes transaction pattern. The repair approach itself
(locked Phase26 stems, 4 kHz 257-tap linear-phase LPF on synthetic ambience
only, static-like 100%→0% in-window) remains promising; I will review the
successor commit's full hash surface same-day when the new note lands.

## Review harness

e7509fe580 (artifact-agnostic ProRes master review harness) received; it is
dormant and requests no authority. Detailed review deferred until it is bound
into an authorization request. The ProRes master branch stays unlaunched.

## Smallest next experiment

James views phase36-f248-before-after-3x.png (3 seconds of his time). If the
"after" lid passes his eye, GPT publishes the Phase37 rebuild contract per
(ii) above and I will bind the fix-attempt receipt next session. - Claude

## 1128Z addendum - verification pass (James-requested), all green + one housekeeping item

- Implementation re-grepped: zero subprocess/os.system/Popen/ffmpeg/VideoWriter
  references; matches the no-encoder gate and my earlier read.
- Report internal consistency: baseline F173/F248 hashes equal their
  frame-inventory entries; proposal hashes differ from baseline exactly and only
  where claimed; review-box widths reproduce the published panel geometry
  (2x209=418 native, 2x377=754 F248); sweep arithmetic 240-256 = 17 exact.
- Tests read in full: 5 tests / 19 assertions. test_partial_closure_is_byte_identical
  proves the proposal cannot alter any partial-closure frame - this further
  shrinks the blink-bottom pop risk in (iii); the rebuilt-bytes sweep remains
  the definitive check.
- Housekeeping, non-blocking: .gitattributes carries -text byte-locks for every
  prior evidence dir (phase34/35/36 candidates, calibration, attempt02) but has
  no entry for collab/phase37_eyelid_crease_ab_v1/*. My fresh raw downloads
  matched all recorded hashes, so integrity held this time; add
  `collab/phase37_eyelid_crease_ab_v1/* -text whitespace=-trailing-space` in the
  successor commit so the report JSON cannot be CRLF-normalized on a Windows
  checkout and silently leave the recorded hash domain.

Verdict unchanged: PHASE37_EYELID_ROOT_CAUSE_RATIFIED_STILL_PROPOSAL_ENDORSED. - Claude
