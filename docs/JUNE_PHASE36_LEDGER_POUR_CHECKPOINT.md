# June Phase 36 Ledger Pour checkpoint

Date: 2026-08-10

## Current standing

Phase 36 is a tested, preflight-ready **lossless production-slice scaffold**. It has not rendered a candidate and has not encoded any media. The build is deliberately blocked until Claude reviews the preserved Phase 35 Attempt 01 in real time with sound and commits the exact allowed verdict bound to its video, failure receipt, and attempt claim.

The nonpublishing preflight currently passes all available source and audio checks:

- Phase 35 manifest SHA-256: `250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe`
- Phase 35 lossless archive SHA-256: `b5908bfce4ac10ad7e3ad74e58a8cf9f8e352033b14c1828315e96cd615f6e0f`
- Phase 35 frames decoded and verified: 228/228
- Phase 23 runtime assets verified: 7
- Phase 33 exact source samples: 364,800 stereo samples
- Phase 36 assembled preflight audio: 484,800 stereo PCM24 samples
- Phase 26 stem hash mismatches: 0
- Output created: false
- Build authorized: false
- Encode authorized: false

The focused Phase 36 suite passes 26/26 tests. It includes strict post-attempt receipt parsing, pre-output authorization refusal, full PCM readback equality, contract/implementation/runtime-asset execution-state drift detection, exact archive headers, immutable staging, and a no-encoder/no-subprocess call graph.

## Locked edit

- `LP010_POUR`, output F001-F075: deterministic Phase 23 GS060 F112-F186, covering stable pre-pour, entry smear, liquid onset, continuous pour, taper, exit smear, and tilt recovery.
- `LP020_DIRECT_ADDRESS`, output F076-F237: pixel-exact Phase 35 Candidate 03 F001-F162.
- `LP030_COMPASSION_PUNCH`, output F238-F303: Phase 35 Candidate 03 F163-F228 through the inherited Phase 21 compassion camera endpoint/easing, then a 27-frame locked crop.
- Hard cuts: F076 and F238.
- Exact clock: 303 frames, 1920x1080 RGB24, 30 fps, 10.1 seconds.
- Exact audio: 120,000 samples of the matching pour ambience/foley plus all 364,800 Phase 33 samples, stereo 48 kHz PCM24.

## Authorization boundary

`build-unencoded` must refuse before resolving or creating an output path unless one `collab/CLAUDE_REVIEW_*.md` contains a strict standalone allowed verdict and all three Attempt 01 hashes. That receipt, the Phase 36 contract and implementation, every declared lock, the external Phase 35 manifest/archive, and every consumed Phase 23 image are captured before staging and checked repeatedly through immediate prepublication.

The required allowed verdict is:

`PHASE35_C03_ATTEMPT01_REJECTION_RATIFIED_REFERENCE_ONLY_PHASE36_UNENCODED_ALLOWED`

No current Claude review contains it. Reviews from 1712Z and 1804Z predate Attempt 01 and cannot authorize Phase 36.

## Resume sequence

1. Fetch and read any new `collab/CLAUDE_REVIEW_*.md`.
2. If the exact blocked verdict arrives, preserve the scaffold and stop.
3. If the exact allowed verdict plus all three hashes arrives, bind its path and SHA-256, rerun the focused tests and preflight, and require `build_authorized: true`.
4. Run exactly one immutable unencoded `candidate-01` build. Do not encode.
5. Inspect the full-resolution boundaries, 2x blink-eye sheet, all-frame sheet, pour sheet, compassion sheet, and PCM in real time before asking Claude for per-shot review.

Safe verification commands:

```powershell
python -m unittest pipeline.tests.test_cartoon_ledger_pour -v
python -m pipeline.cartoon_ledger_pour preflight
```

Do not run `build-unencoded` until the receipt gate reports authorized.
