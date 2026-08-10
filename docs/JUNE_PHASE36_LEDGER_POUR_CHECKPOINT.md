# June Phase 36 Ledger Pour checkpoint

Date: 2026-08-10

## Current standing

Phase 36 Candidate 01 is an immutable, unencoded 303-frame lossless production slice. It passed all 30 declared machine gates, and its exact-frame visual review passes the pour action, both editorial cuts, June's identity, the compassion punch-in, and the known single-frame blink watch item. It is **rejected for promotion** because post-build PCM/spectrogram review found an objective 0.800-second stereo digital-silence hole at the first cut. No media was encoded.

Candidate 01 immutable evidence:

- Phase 35 manifest SHA-256: `250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe`
- Phase 35 lossless archive SHA-256: `b5908bfce4ac10ad7e3ad74e58a8cf9f8e352033b14c1828315e96cd615f6e0f`
- Phase 35 frames decoded and verified: 228/228
- Phase 23 runtime assets verified: 7
- Phase 33 exact source samples: 364,800 stereo samples
- Phase 36 assembled preflight audio: 484,800 stereo PCM24 samples
- Phase 26 stem hash mismatches: 0
- Manifest SHA-256: `0c97ba94987b8fabf1e1dd0d9c7b1229cfa6edc240ec9ef1fcccf3d45405d9a2`
- Lossless 303-frame archive SHA-256: `93eb2cd752d745a6f6fd534912ff68ee24e7bf72cf7cd406d2a366adea97d404`
- PCM24 WAV SHA-256: `d9450edd9a9fe7037b6565dbca31cae67ad0b7c574038c2c9fca0c399e338207`
- PCM payload SHA-256: `5f6cd536af0691509bc53982970cdef5ccdd2a27ce5966415356dd01fa2cb689`
- Preserved executed source archive SHA-256: `e398e7f6b5458384f39a8af00aded6d16317eaa5d5912d561c3ce3f410c3331f`
- Post-review failure receipt SHA-256: `bd11323a9e416a439b70d21e99a21b41beb5fc98679590b476485f2e46a9d5c1`
- Machine result: 30/30 passed; zero execution-state mismatches
- Promotion allowed: false
- Encode authorized: false

The focused Phase 36 suite passes 26/26 tests. It includes strict post-attempt receipt parsing, pre-output authorization refusal, full PCM readback equality, contract/implementation/runtime-asset execution-state drift detection, exact archive headers, immutable staging, and a no-encoder/no-subprocess call graph.

## Candidate 01 review failure

The declared `audio_boundary_step <= 0.01` gate passed at `0.0045226818`, but it measured only the amplitude difference between two adjacent samples. It did not measure continued acoustic energy. Exact PCM review found:

- Active porch/pour audio through sample 119,999; the final 100 ms has RMS `0.00694302` (`-43.169 dBFS`).
- Stereo digital zero for samples `[120000, 158400)`, exactly 38,400 samples / 0.800 seconds / output F076-F099.
- Direct-address audio starts on schedule at sample 158,400 / output F100.
- The second cut at F238 retains valid room tone.

This violates the contract's continuous-porch-perspective intent. Candidate 01 remains historically machine-passed, but it cannot be promoted or encoded. The source pictures are accepted for exact reuse; only the audio binding needs replacement.

The live Candidate 01 builder is now retired fail-closed: the contract binds the exact failure receipt above, `preflight` reports `phase36_candidate01_rejected: true` and `build_authorized: false`, and `build-unencoded` refuses before resolving any output path. The exact source that executed the one historical build remains preserved in `phase36-candidate01-implementation-source.tar`.

## Locked edit

- `LP010_POUR`, output F001-F075: deterministic Phase 23 GS060 F112-F186, covering stable pre-pour, entry smear, liquid onset, continuous pour, taper, exit smear, and tilt recovery.
- `LP020_DIRECT_ADDRESS`, output F076-F237: pixel-exact Phase 35 Candidate 03 F001-F162.
- `LP030_COMPASSION_PUNCH`, output F238-F303: Phase 35 Candidate 03 F163-F228 through the inherited Phase 21 compassion camera endpoint/easing, then a 27-frame locked crop.
- Hard cuts: F076 and F238.
- Exact clock: 303 frames, 1920x1080 RGB24, 30 fps, 10.1 seconds.
- Exact audio: 120,000 samples of the matching pour ambience/foley plus all 364,800 Phase 33 samples, stereo 48 kHz PCM24.

## Authorization boundary

`build-unencoded` must refuse before resolving or creating an output path unless the exact 1910Z Claude receipt matches its LF-normalized contract lock, contains one structured allowed verdict plus Claude's integrity attestations, and all three local Attempt 01 artifacts independently match their complete contract hashes. That receipt, the Phase 36 contract and implementation, every declared lock, the external Phase 35 manifest/archive, all three Attempt 01 roots, and every consumed Phase 23 image are captured before staging and checked repeatedly through immediate prepublication.

The required allowed verdict is:

`PHASE35_C03_ATTEMPT01_REJECTION_RATIFIED_REFERENCE_ONLY_PHASE36_UNENCODED_ALLOWED`

`collab/CLAUDE_REVIEW_2026-08-10_1910Z.md` contains the allowed verdict, accepts the real-time picture/audio, and attests that Claude independently recomputed all five declared hashes with exact matches. Its exact review-file hash is contract-locked; the full local video, failure-receipt, and claim hashes are independently verified by the gate. The earlier addendum request is therefore redundant provenance formatting, not an authorization dependency. Reviews from 1712Z and 1804Z predate Attempt 01 and cannot authorize Phase 36.

## Resume sequence

1. Fetch and read any new `collab/CLAUDE_REVIEW_*.md`.
2. Obtain Claude's review of `collab/phase36_candidate_01/` and authorization for a new audio-only Candidate 02 binding. Do not rerender picture.
3. Bind Candidate 01's 303 RGB hashes/archive unchanged. Replace only the defective audio interval using the verified Phase 26 mastered porch predecessor and a deterministic 30 ms equal-power splice.
4. Add exact-zero-run, fully-zero-frame, per-frame RMS, cut-window RMS/activity, and same-porch energy-continuity gates before producing Candidate 02.
5. Review Candidate 02 around 2.35-3.45 seconds on headphones and over the complete 10.1 seconds. Any encode still requires a separate binding.

Safe verification commands:

```powershell
python -m unittest pipeline.tests.test_cartoon_ledger_pour -v
python -m pipeline.cartoon_ledger_pour preflight
```

Do not rerun Candidate 01, alter its manifest, or encode any Phase 36 media.
