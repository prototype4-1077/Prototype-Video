# CLAUDE 2026-08-11 1220Z - Phase37 v2 sclera-occlusion diagnostic: two-defect root cause ratified, edge treatment required

Reviewed: commit 52d5a6d74a ("diagnose Phase36 F248 sclera occlusion") on
agent/phase37-eyelid-crease-ab-v1. All 8 PNGs downloaded fresh via raw contents
API and viewed directly this session, including my own crops of the four-state
panels, the F247/F248/F249 sweep triplet, and an 8x zoom of the viewer-right
lower margin in baseline vs combined.

## Independent verification

- 8/8 artifact SHA-256s and byte sizes match the machine report inventory on
  fresh downloads (spot: f248-3x 4ecc2cf3..., decomposition 6861690b...,
  sweep 2cf19386...).
- Contract da1c36fa..., implementation e91063c2..., tests 2b04d909... match
  the committed files byte-for-byte.
- 32/32 gates pass with actual == threshold field-by-field; failed_gates
  empty. encoding_process_count 0, paid/network calls 0, no encoder.
- Housekeeping from my 1128Z addendum CLOSED: .gitattributes now carries
  -text byte-locks for both phase37_eyelid_crease_ab_v1/* and
  phase37_eyelid_occlusion_ab_v2/*, plus LF locks on the v2 contract and the
  diagnostic implementation/tests. Thank you.

## Direct visual review

- Two-defect root cause: RATIFIED. The sweep is the proof: F247/F249 show a
  pale lower band that is legitimately exposed lower sclera mid-blink; at
  F248 full closure that same band persists under the viewer-right eye where
  closure=1.0 says it must be covered. The decomposition's red under-occluded
  region sits exactly on that band, provenance traces it to the registered
  patch (neutral_plate_fallback_pixels 0, delta_mean 56.8 right / 79.7 left),
  and the crease/sclera supports are disjoint (overlap 0) — two separable
  defects, cleanly demonstrated.
- Crease suppression: unchanged from v1 and still clean — polyline gone in
  crease_only and combined at native, F173-final, and F248 scales; natural
  fold preserved; tear-duct highlight intact.
- Occlusion expansion: DIRECTION CORRECT, COMPOSITING NOT YET ACCEPTABLE.
  The write lands on the leak and the combined F248 reads clearly better
  than baseline at sweep scale. But at 8x on the published native combined
  panel (and visibly at 3x in phase36-f248-four-state-3x.png, lower margin
  of the viewer-right eye), the hard alpha-255 ownership boundary renders as
  a stair-stepped edge between the newly written brown lid texture and the
  adjacent pale band — a small blocky notch in the twice-transformed F248
  view. This is the same class of hard-edge artifact James caught at
  playback scale on the crease. Additionally, a residual cream band remains
  immediately outer/inferior to the write, continuous in tone with the
  baseline leak. The classifier assigns it protected/fringe, and
  residual_under_occluded_after=0 is true by that classification — but
  whether that band is authored lower-lid waterline (keep) or
  under-segmented leak (cover) is not decidable from the published stills.

## Four standing criteria (still-evidence scope)

1. Identity: PASS — June stays June in every panel; native diffs 0 px
   outside allowed support at all three transform levels.
2. Viseme legibility: n/a (eye crops, no speech).
3. Upper-face stillness: PASS unchanged — no brow writes; write audit clean.
4. Jaw/beard seam: n/a — 0 px outside eye support.

## Verdict: PHASE37_V2_TWO_DEFECT_ROOT_CAUSE_RATIFIED_OCCLUSION_DIRECTION_ENDORSED_EDGE_TREATMENT_REQUIRED

This ratifies the two-defect determination and endorses crease suppression
as-is. The occlusion expansion is endorsed in direction only: do not carry
the hard-step write into a rebuild contract. Gate (c) stays open. No
rebuild, encode, or promotion authority is granted. Candidate01 archive
remains immutable; phase36_encode_authorized false is correct.

## Smallest next experiment (still-only v3, same fail-closed in-memory pattern)

1. Seed probe: add exactly one HSV seed inside the residual cream band
   (viewer-right eye, immediately outer/inferior to the v2 write in the
   published native panels) and republish the classification delta. If it
   joins the sclera core, extend ownership over it; if it classifies as
   authored waterline, it stays and we say so explicitly.
2. Feathered edge: replace the hard 255 ownership step with a 1-2 px alpha
   ramp at the write boundary (or clip the boundary to the authored lash
   curve), and publish a single F248 baseline|v2-combined|v3-feathered
   comparison panel at 1x and 3x.

Both are zero-render, zero-cost, and stay inside the no-new-render boundary.
After v3, James makes the taste call on the combined F248; only then the
single-attempt corrected-source rebuild contract per my 1115Z (ii)-(iii).

## Candidate03 audio (gate b)

No successor note since the 11e STOP; 95ceefbf51's claim-durability
hardening was already acknowledged at 1115Z. Nothing authorized; awaiting
the new hash surface. ProRes master branch remains correctly unlaunched. - Claude
