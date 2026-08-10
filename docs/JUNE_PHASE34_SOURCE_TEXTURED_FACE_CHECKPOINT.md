# June Phase 34 source-textured face checkpoint

Status date: 2026-08-09  
Branch: `agent/june-hero-unified-sculpt-phase-5`  
Draft PR: `#8`  
Classification: unencoded technical/artistic preview; not production delivery

## Current result

Phase 34 candidate-05 is the first review package that preserves all 96 exact reviewed
RGB frames and closes the technical proof defects found in candidate-04. It passes all
pre-encode gates and 16 focused tests. It has not been encoded, has no review receipt,
and is not artistically accepted.

Public review evidence is staged at `collab/phase34_candidate_05/`.

- Local Windows manifest SHA-256: `660f90067ef99efa147c0d25321741af96a345cd44eccd40cebd45cf1c67e3f6`
- LF-normalized Git/public manifest SHA-256: `27b7498a89939efc9c9d526be1609427fa2e72f1a39a1a85df67fde437dd3817`
- Exact-frame archive SHA-256: `ce53dcae6ef5195e8200393b91cc50975f59d1350161f92cfdbaf2153958075b`
- Contract canonical SHA-256: `7312f237a0f114402d72e0ddd399eecde4a2e8883ff808715eb6b0f6e6950034`
- Renderer SHA-256: `06be7b8eabb8dbe94cf43546727159d2f7c74970ceff8bd2146ecc39ceb00dc6`

Local immutable preview:

`../../outputs/edit/phase34-source-textured-visemes-preview-v1-candidate-05`

## Architecture now proven

- The GS070 plate is the only identity texture; no full-face or full-mouth identity swap occurs.
- A fixed 10-by-10 cage applies bounded source-texture deformation below the alar lock.
- Generated oral material is classified and excluded at the atlas boundary.
- Upper dentition uses an independent skull-anchored transform.
- June's source-textured lip ribbons, moustache, and beard re-occlude the recessed oral layers.
- Layer coverage, connected seam coverage, and forbidden-material leakage are measured.
- The canonical contract, thresholds, pose geometry, output path, and policies are hash-pinned.
- The Phase 33 dependency is loaded from its declared lock rather than a hard-coded alternate path.
- The atlas builder verifies inputs and exact output hashes and refuses destructive overwrite.
- A deterministic RGB24 XOR+gzip archive reconstructs every reviewed output frame exactly.
- Runtime network access, generation, audio, encoding, and RL are forbidden in this preview stage.

## Candidate-05 evidence highlights

- 96/96 exact archived frame hashes round-trip successfully.
- Exact neutral endpoints; zero changes outside feature support.
- Zero viseme changes above the alar base and protected output margin.
- Zero generated-atlas outer-ring pixels reported by the current gate.
- Zero unexpected layer-overlap pixels reported by the current gate.
- Connected source seam coverage: 1.00 for every key pose.
- Upper-dentition centroid range: 2.200 native pixels; E upper teeth: 656 pixels.
- Frame 82 authored oral material: zero; the former red/orange pinhole is gone.
- Zero folded triangles; area ratio 0.5102 through 1.8579; condition maximum 2.0643.
- H tongue: 347 pixels; eight distinct non-neutral poses.
- Confusable-pair minimum delta: 4.384 for C/E.
- Worst adjacent 8x8 feature delta remains blink frames 6 to 7 at 148.344 under 150.
- Sixteen focused tests pass. A repository-wide discovery run made no observed failure but
  exceeded the 10-minute local command limit; GitHub CI remains the authoritative full run.

## Candidate-05 review verdict

Candidate-05 is a valid pipeline experiment, not a quality-signoff encode source.

Visual P1s:

- Oral onset/exit pops remain at frames 17-18 and 81-83.
- Topology jumps remain at 33-34, 41-42, 49-50, and 65-66.
- The dark maroon cavity perimeter still reads as a pasted cutout in several poses.
- Dental y anchoring is improved, but tooth identity, width, and spacing still morph.
- F contact is weak; C and E are too similar at delivery scale.

Integrity P1s found after the candidate was rendered:

- Independent upper-dentition extraction can bypass the outer-lip exclusion mask.
- The oral overlap allowlist permits every lower-face layer pair and is too broad to catch
  a six-layer depth-stack regression.

These findings do not alter the immutable candidate-05 evidence. They are mandatory
candidate-06 fixes.

## Collaboration state

At every session start, read `collab/PROTOCOL.md` and all new `collab/CLAUDE_*` notes.
Claude's `CLAUDE_REVIEW_2026-08-10_0110Z.md` binds candidate-04 and visually approves one
silent encode. Do not exercise that approval: subsequent independent audits proved that
candidate-04's lip/overlap gates were hard-coded and that its exact 96 reviewed frames were
not preserved. Candidate-05 supersedes it as the evidence architecture.

Candidate-05 will be offered to Claude as an exact-frame review experiment with special
attention to frames 17-18, 33-34, 41-42, 49-50, 65-66, and 80-83. No receipt should be
issued for an encode unless a later candidate clears the visual and integrity blockers.

## Exact next steps

1. Preserve and publish candidate-05 evidence and the collaboration note.
2. Candidate-06: carry the forbidden-material mask through independent dentition extraction.
3. Replace the broad overlap allowlist with exact permitted depth-stack combinations.
4. Replace the hard oral cutoff with a smooth semantic coverage ramp while retaining exact X bypass.
5. Use one persistent canonical dental arc and deform semantic cavity/tongue/lower-mouth layers separately.
6. Feather and locally grade the cavity perimeter with June's source texture.
7. Strengthen F lower-lip contact and separate C/E silhouettes.
8. Render a new immutable 96-frame archive, run independent code/visual audits, and ask Claude
   for a manifest-bound verdict.
9. Only after an accepted receipt, encode the exact reviewed archive once and fully decode-verify it.

Do not call candidate-05 a complete cartoon or production delivery. It proves a reusable,
high-detail front-view facial pipeline. Body acting, multi-angle adaptation, voiced timing,
editing, sound, shot continuity, and full-sequence art direction remain separate production gates.
