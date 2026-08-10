# June Phase 34 source-textured face checkpoint

Status date: 2026-08-10  
Branch: `agent/june-hero-unified-sculpt-phase-5`  
Draft PR: `#8`  
Classification: unencoded technical/artistic preview; not production delivery

## Current result

Phase 34 candidate-07 is the latest immutable exact-frame experiment. It preserves all 96
reviewed RGB frames, proves lower-face soft-alpha writes, and adds dedicated F and H anatomy.
It passes all pre-encode gates and 18 focused tests. It has not been encoded, has no review
receipt, and is not artistically accepted.

Review evidence is staged at `collab/phase34_candidate_07/`.

- Local Windows manifest SHA-256: `2127d59f0cbd1247fb858f8a0edf43b8ccf357602695502185974120fe389ff9`
- LF-normalized Git/public manifest SHA-256: `3d23700d47ecbf2d3384f0f41eaffe3b69f196cbbbdf9ac9a6a9cf32f0bc0cce`
- Exact-frame archive SHA-256: `0fd9137f3756efecc94e89a5a97d5603c08290ff8843415190c0036d302f94de`
- Contract canonical SHA-256: `3ace2fa14cf4ce32fff803a711dbb6b747989cda27cbbf2924a4853d94db60c6`
- Renderer SHA-256: `2faf32a261c4588370cc0f4df8d142cb70b44c74ea724ee36187f79f095c9429`

Local immutable preview:

`../../outputs/edit/phase34-source-textured-visemes-preview-v1-candidate-07`

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

## Candidate-06 intermediate milestone

Candidate-06 is preserved at `collab/phase34_candidate_06/` as the first smooth semantic
anatomy/dental experiment. It is not an encode candidate.

- Local manifest SHA-256: `fe3d5f4255a269d699d737ca6f22316b449b42249b184165852d6e757c528223`
- LF-normalized Git/public manifest SHA-256: `1051a967411c4f363cea4fe24d5ef4cc61f6fc20d0acbcc2bb5483aa7ea66022`
- Exact-frame archive SHA-256: `478fd2fc301c70295ea8a7de44163e7980d5e9030ee9fdd7e8588d7029155ced`
- Contract canonical SHA-256: `894f453758ad3b685487140702d90846068b8907803d90fc7e96c5a11d850b1d`
- Renderer SHA-256: `a2a0783f207b9132e4691520690088d2e283dddbecb15f2d4afaf72c64030bff`

It introduces symmetric semantic activation at X boundaries, one canonical upper dental arc,
linear non-dental anatomy blending, source-textured cavity feathering, strict dental source
filtering, and final-owner depth validation. C/E separation rises from 4.384 to 14.332.
Transitions and dental identity are materially smoother than candidate-05.

Candidate-06 blockers:

- F contact is too close to neutral at frames 58/59/62/64.
- H tongue reads as a generic pink strip.
- F-to-G still opens too quickly at frames 65-66.
- Maroon cavity patches remain in the widest shapes.
- The depth gate records hard/thresholded coverage rather than every significant alpha write,
  omitting 167-594 softly blended lower-face pixels in sampled frames. Candidate-07 must
  record actual alpha support and final writers at the same declared threshold.

## Candidate-07 measured-articulation milestone

Candidate-07 is preserved at `collab/phase34_candidate_07/` as a measured-articulation
experiment. It is not an encode candidate.

- Exact lower-face alpha support and final writers are recorded at 1/255.
- Frame 82 proves 84 oral-interior writes with zero depth-order violations.
- F has 89 visible incisor pixels, 56 contact columns, a 14-pixel cavity, and strong F/X
  numerical separation, but remains too subtle at delivery scale.
- H has a distinct 391-pixel tongue tip, 27-pixel groove, and 27 nominal lip-overlap pixels.
- C/E mean separation is 14.166; identity and the upper face remain locked.
- All 96 archived hashes and all review artifacts round-trip exactly.

Candidate-07 blockers:

- F is still nearly neutral at delivery scale and frame 65 to 66 still opens too abruptly.
- Flat burgundy cavity corners remain in C/D/G/H.
- Semantic eyelid soft-alpha and crease writes are not included in Phase34 coverage/final
  ownership; roughly 700 full-blink fringe pixels can evade depth validation.
- H's nominal lip-over-tongue metric accepts alpha down to 1/255 before later hair layers;
  it does not prove visibly meaningful final occlusion.

## Collaboration state

At every session start, read `collab/PROTOCOL.md` and all new `collab/CLAUDE_*` notes.
Claude's `CLAUDE_REVIEW_2026-08-10_0110Z.md` binds candidate-04 and visually approves one
silent encode. Do not exercise that approval: subsequent independent audits proved that
candidate-04's lip/overlap gates were hard-coded and that its exact 96 reviewed frames were
not preserved. Candidate-05 supersedes it as the evidence architecture.

Candidate-07 is preserved for Claude as an exact-frame before/after experiment, but should
not receive an encode receipt. Candidate-08 must clear the visible and proof blockers first.

## Exact next steps

1. Candidate-08: mirror exact semantic-lid alpha/crease writes into Phase34 coverage and
   final ownership without changing the locked Phase33 dependency.
2. Require meaningful final source-lip ownership over H's tongue, not a transparent pre-write.
3. Increase F's delivery-scale incisor/lip contrast and shift the contact band downward.
4. Use a linear F-to-G geometry interpolation so frames 65 and 66 are true intermediates.
5. Derive the cavity edge from darkened local source texture instead of flat burgundy fill.
6. Render a new immutable 96-frame archive, run independent code/visual audits, and ask Claude
   for a manifest-bound verdict.
7. Only after an accepted receipt, encode the exact reviewed archive once and fully decode-verify it.

Do not call candidate-07 a complete cartoon or production delivery. It proves a reusable,
high-detail front-view facial pipeline. Body acting, multi-angle adaptation, voiced timing,
editing, sound, shot continuity, and full-sequence art direction remain separate production gates.
