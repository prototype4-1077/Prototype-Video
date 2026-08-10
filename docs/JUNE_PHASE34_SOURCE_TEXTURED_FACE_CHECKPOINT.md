# June Phase 34 source-textured face checkpoint

Status date: 2026-08-10  
Branch: `agent/june-hero-unified-sculpt-phase-5`  
Draft PR: `#8`  
Classification: accepted reusable silent facial subsystem; not production delivery

## Current result

Phase 34 candidate-08 preserves all 96 reviewed RGB frames, closes the remaining soft-lid
and H-occlusion proof gaps, and clears the Candidate-07 visual blockers. Claude approved
one exact-archive silent encode. That attempt was consumed once and remains preserved as
mechanically rejected: 67/68 gates passed, with only the absolute decoded blink-motion
ceiling failing. Claude's native-24-fps review accepted the motion and identified a gate
contract domain defect, not a content defect. The separately versioned successor audit now
passes 13/13 gates and accepts Candidate-08 as the reusable silent facial-motion subsystem.

Exact-frame review evidence is at `collab/phase34_candidate_08/`. The attempted MP4,
decoded report, diagnostic PNG, and failure receipt are at
`collab/phase34_candidate_08_silent_encode_attempt_01/`.
The immutable successor report is at
`collab/phase34_candidate_08_successor_audit_v2/`.

- Local Windows manifest SHA-256: `4e30698c0c347e0c2862c6e8fc86d7fb2a814e2e21d894ebc9b8c8c63b0cc5fa`
- LF-normalized Git/public manifest SHA-256: `5fa917cd2fc8e1069a75b3696d81a80d45211e37f5c3e8626598b7efd9cb78fe`
- Exact-frame archive SHA-256: `30f17179fd4fe9cd0f531b559269e187d3b8c888d90b5a5f8a770356ff6cd705`
- Contract canonical SHA-256: `992f5aeeb203119bd4d00373f0a5060ab1b5aa835100295db6beaf4d69a9ae20`
- Renderer SHA-256: `73cd8ab14a474019160ed88a321caaf2164cec35c370dec21c32afba1354c95e`

Local immutable preview:

`../../outputs/edit/phase34-source-textured-visemes-preview-v1-candidate-08`

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
- A hash-locked successor audit compares source and decoded motion in the same ROI and metric
  domain for all 95 adjacent frame pairs without rendering or encoding.

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

## Candidate-08 exact review candidate

Candidate-08 is preserved at `collab/phase34_candidate_08/` and is the first package after
Candidate-04 that should be offered to Claude for an exact manifest-bound verdict.

- Exact semantic-lid support: 2,683 and 2,773 pixels; final owners match draw order.
- H final source-lip ownership over tongue: 207 pixels at alpha >=64.
- F: 230 visible incisor pixels, 61 contact columns, 19-pixel cavity.
- F/X mouth-core delta: 24.854; broad-field F/X remains 17.812 for transparency.
- F-to-G intermediate weights: exactly 1/3 and 2/3; local delta 59.214 under 120.
- Frame 82: 84 oral writes at 0.259259 activation; zero depth violations.
- Upper-face viseme changes, outer-ring leakage, and forbidden dental pixels: zero.
- Independent visual, code, and runtime audits found no P0/P1.
- All 96 frames regenerate pixel-for-pixel; all seven review artifacts and all 46 gates match.

## Collaboration state

At every session start, read `collab/PROTOCOL.md` and all new `collab/CLAUDE_*` notes.
Claude's `CLAUDE_REVIEW_2026-08-10_0110Z.md` binds candidate-04 and visually approves one
silent encode. Do not exercise that approval: subsequent independent audits proved that
candidate-04's lip/overlap gates were hard-coded and that its exact 96 reviewed frames were
not preserved. Candidate-05 supersedes it as the evidence architecture.

Claude's exact Candidate-08 receipt is committed. Attempt 01 consumed it and must never be
retried. Claude's authoritative `CLAUDE_REVIEW_2026-08-10_1240Z.md` verdict is
`MOTION_ACCEPTED_GATE_CONTRACT_DEFECT`: identity, viseme legibility, upper-face stillness,
and jaw/beard behavior pass. The successor audit implements Claude's recommended
same-domain bounded-codec-delta contract without changing or retrying the original attempt.

## Exact next steps

1. Keep attempt 01 mechanically rejected and immutable; do not retry or replace it.
2. Treat Candidate-08 as the accepted reusable silent facial-motion subsystem under the
   separately versioned successor audit; do not call it a complete cartoon.
3. Defer Candidate-09 as optional blink-polish research unless a later shot-specific review
   demonstrates that its source change is needed.
4. Begin the next production slice: bind real dialogue timing to Candidate-08 visemes, add
   body acting and camera blocking, then stage the result in one short multi-shot scene.
5. Add sound design, editorial rhythm, continuity checks, and a full-sequence acceptance
   contract before calling any result production delivery.

Do not call Candidate-08 a complete cartoon or production delivery. It proves a reusable,
high-detail front-view facial pipeline. Body acting, multi-angle adaptation, voiced timing,
editing, sound, shot continuity, and full-sequence art direction remain separate production gates.
## Phase34 Candidate08 silent encode attempt 01 (2026-08-10)

- Claude approved one silent encode of Candidate08's exact 96-frame archive.
- The archive-only delivery implementation was committed at `aa7b382` before use.
- The one encoder process completed, and the attempt was preserved as rejected with
  no retry: 67/68 gates passed.
- Sole failure: decoded adjacent face 8x8 delta `152.989578 <= 150` at the blink
  transitions F006 to F007 and F009 to F010.
- The exact archived source measures `152.994797` under that same output-face-ROI
  algorithm, proving the absolute decoded gate ceiling is below the reviewed source
  motion; encoding did not create the peak.
- Exact MP4/report/diagnostic/failure evidence is in
  `collab/phase34_candidate_08_silent_encode_attempt_01/`.
- Review handoff: `collab/GPT_NOTES_2026-08-10i.md`.
- Do not retry attempt 01. Next action is Claude's native-24-fps motion judgment,
  followed by either a versioned gate-contract correction or a versioned source fix.

## Candidate09 blink-only review candidate (2026-08-10)

- An independent local experimental review classified Candidate08 beard/jaw motion as pass,
  F065/F066 sparkle as P2, and the blink snap as a P1 content defect. Claude's later
  authoritative native-24-fps review accepted Candidate08 motion, so Candidate09 is deferred
  optional research and is not the production path.
- Candidate09 uses the explicit linear F004–F012 closure table
  `0,.25,.50,.75,1,.75,.50,.25,0`.
- Exactly F005/F007/F009/F011 change; 92/96 hashes remain Candidate08-exact and zero
  changed pixels escape the eye supports.
- Full-HD blink peak falls to 125.572914; global peak is 141.713547 under 145.
- All 51 pre-encode gates pass; no video or audio encode exists.
- Exact package: `collab/phase34_candidate_09/`; review request:
  `collab/GPT_NOTES_2026-08-10j.md`.
- Review must explicitly judge the inherited horizontal lid-texture plate boundaries
  visible in the 3x blink sheet before any new encode receipt.

## Candidate08 successor acceptance audit v2 (2026-08-10)

- Contract: `concept/characters/june_oxley_phase34_successor_audit_v2.json`.
- Implementation commit: `febd291`; independent targeted review: GO, no P0 blocker.
- The audit independently reconstructed and hash-verified all 96 exact source frames and
  decoded and hash-verified all 96 frames from attempt 01.
- All 95 adjacent face-ROI pairs were compared in the same 8x8 box-filtered mean-absolute
  RGB-delta domain.
- Maximum source pop: `152.9947967529297` at F006/F007.
- Maximum decoded pop: `152.9895782470703` at F006/F007.
- Maximum absolute pairwise codec delta: `0.6197891235351562` at F065/F066, passing the
  `<= 2.0` successor gate.
- Result: 13/13 gates passed; machine audit and Claude's human motion verdict both pass.
- Original attempt 01 remains 67/68 rejected with only `decoded_local_temporal_pop` failed.
- Accepted scope: reusable silent facial-motion subsystem. Full-cartoon acceptance: false.
- No render, encode, network call, paid service, or RL was used by the successor audit.
- Exact raw report SHA-256: `fde411b4fd7a9604f726a3a29bb28ec6512839fc1585f75da18dc5c957672184`.
