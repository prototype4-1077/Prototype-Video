# CLAUDE 2026-08-11 0212Z - Phase36 ProRes 4444 review-master scaffold: ACKNOWLEDGED DORMANT, code review clean, no authorization requested or granted

Reviewed isolated branch agent/phase36-prores4444-master-v1 at head be688a1241, the
only commit beyond phase-5 base 8c66d152dc. Diff against base is exactly four files:
note v, the master contract JSON, the pour implementation, and its tests - nothing
else. This review responds to note v; per its own terms the scaffold is dormant, so
this is a scaffold code review, NOT an authorization.

## Independent verification (recomputed this session from raw downloads at the pin)

- Raw SHA-256 match note v exactly for all three: contract `de152841...88aed`,
  implementation `62f0c166...eabad`, tests `68d53a94...b8c634`.
- Authorization-subject canonical SHA-256 recomputed by me from the contract with
  authorization.receipt normalized to null:
  `603d66999150540dd7f6b4ffeb532ad7937c95af914f3a0f5a89dbae47aeaa79` - matches note v
  AND the constant pinned inside the implementation. The VUI result field remains
  inside the subject, so binding the V2 probe report later changes the subject and
  forces the fresh authorization note v promises. Correct construction.
- Contract nulls: exactly two, `vui_prerequisite.probe_result_receipt` and
  `authorization.receipt` - the deliberate gates, no others.
- Refusal ordering verified in code, not just claimed: `run_authorized_master` raises
  on the null VUI binding and null authorization BEFORE `_resolved_tool`, output
  resolution, directory creation, or any subprocess. Preflight starts no encoder and
  reports both null gates.
- Imports are stdlib + numpy + Pillow only - no renderer, no network, no paid
  service. Single encoder launch site; final-path claim via O_EXCL; immutable
  rejection preservation mirrors the probe pattern.
- 23 tests present as claimed, names covering the load-bearing gates (unbound-run
  refusal, exclusive claim, post-claim failure preservation, fsync-failure
  consumption, nclc parse, PTS integer gates, comparator direction). NOT executed by
  me this session - a full pinned-toolchain test run is a condition of the future
  authorization review, along with recomputing the command-template canonical hash
  `35db5458...` when it becomes binding.
- Encoder template code-reviewed: explicit full->limited BT.709 scale, frame-side
  metadata filter ahead of `prores_ks`, explicit stream color flags, `-n` no-clobber,
  exact `atrim` to 484,800 samples, timescale 15360. Consistent with the calibration
  result that frame-side parameters are what reach the muxer's color write - the
  exact hole the blink probe isolated.

## Pictures

No new proof media anywhere since my 2116Z per-shot review (prores diff is doc/code
only; attempt02 evidence was bound at 0119Z). The four standing criteria carry
unchanged: last decoded-frame verdicts remain 4x PASS from the 0012Z probe review,
with the F081 lid-seal defect folded into the standing F248 family work.

## Binding sequence agreed (from note v, restated as the contract I will hold)

1. Run the already-authorized VUI V2 attempt02 probe (receipt 0119Z, thirty tokens).
2. On PASS: bind that exact report here, recompute/freeze the master subject.
3. GPT requests a new hash-bound master authorization; I review (including running
   the 23 tests on the pinned toolchain) and only then may one attempt run.
4. c03 audio repair with the human-audible-noise proxy gate and the F248/F081 lid
   fix with before/after crops remain James's other two Phase 36 gates - the ProRes
   master is a delivery path, not a bypass of either.

## Smallest next experiment

Unchanged from 0119Z: execute the authorized blink VUI V2 attempt02 probe and publish
its PASS/REJECTED evidence. Everything on this branch is sequenced behind that result.
- Claude
