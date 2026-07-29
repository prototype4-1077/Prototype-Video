# June Phase 12 Resume Checkpoint

Checkpoint date: 2026-07-29 (America/Chicago)

## Outcome

Phase 12 is complete as a working 15.1-second semantic-ink cartoon prototype.
The public GitHub pipeline rendered and assembled the exact scene, the local
free/open-source finish produced a verified 1080p master, original foley was
mixed beneath the approved dialogue, and both automated and human delivery
gates passed.

This is a safe stopping point. Continue with deformation and multi-shot
continuity work; do not rerun the Phase 12 full promotion unless its immutable
look profile, character performance, or scene source changes.

## Repository state

- Public repository: https://github.com/prototype4-1077/Prototype-Video
- Worktree: `C:\Users\jwats\Documents\Codex\2026-07-28\d\work\Prototype-Video`
- Branch: `agent/june-hero-unified-sculpt-phase-5`
- Draft pull request: https://github.com/prototype4-1077/Prototype-Video/pull/8
- Base: `agent/june-hero-asset-v2-phase-4`
- `main` remains untouched.
- Last pushed checkpoint before this document: `6fabfc9`

Use the safe-directory option for local Git commands:

```powershell
git -c safe.directory=C:/Users/jwats/Documents/Codex/2026-07-28/d/work/Prototype-Video ...
```

## Public render evidence

- Full-promotion revision: `c7932efcf2f3fd50699d5727dbc3f188e13aca31`
- Successful full Actions run: `30454667937` (run 66)
- Artifact ID: `8729079236`
- Artifact: `june-golden-performance-storybook-semantic-npr-v1`
- Artifact ZIP SHA-256:
  `b04c362f8443fc07d276f79a32e13fcbea45b36fa3c95dac27f3cfbc52fa0978`
- Source SHA-256:
  `bea96dabf0dc2c6d591eb80639c9e951a996360506c6b65f076f1bc657263728`
- Source contract: H.264/yuv420p, 960x540, 30 fps, exactly 453 frames,
  15.1 seconds, full decode passed
- Assembly: six exact gap-free ranges covering frames 1-453
- Economical CI restore revision: `c847e4957f91c73b48d0dfe06bbe90c8d4ab38b7`
- Restored public CI run: `30468874323`, regression and 30-frame temporal
  render gate passed

The repository had been private, which prevented the final assembly job from
starting under the account's billing state. It was intentionally made public on
2026-07-29. Rerunning only the failed assembly job completed the promotion; the
six successful Blender chunks were not repeated.

## Final local delivery

- Master:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-golden-scene-semantic-npr-v1.mp4`
- Master SHA-256:
  `3050dec00d8c0b40cde8516dcf28e0d3d7aa82c8b13862b18576c5170e5d3165`
- Contract: H.264/yuv420p, 1920x1080, 30 fps, exactly 453 frames,
  15.1 seconds, AAC stereo at 48 kHz
- Full decode: passed, 453 decoded frames
- Dialogue/foley mix SHA-256:
  `f0ecc51233af5e3fcc0b02b89f9c2368195f66df67b09a3b1b28a7e2e2d90487`
- Approved caption SHA-256:
  `e90529d7e302e740e256a2e39295cb4def0e34a25fa1ab15009bf29cc83206be`
- Finish report:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-golden-scene-semantic-npr-delivery-report-v1.json`
- Finish-report SHA-256:
  `9c4a4c32119ff50026688b6f58b2756fa2775b075cf07e902b1273ea4d4da82d`

## Independent audit

- Audit directory:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\phase12-final-audit`
- Audit-report SHA-256:
  `84cb244e892c6acaf4ea93b8fd13b6b713bf452e8da7de9a576d4e91256501e5`
- Nine-pose matrix:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-golden-scene-semantic-npr-final-matrix-v1.png`
- Matrix SHA-256:
  `7c82727ac435deaf9799e3b28c8beab340f75e91dbbf62bff4c13980b7c8cd74`
- Final-hold strip:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-golden-scene-semantic-npr-final-hold-v1.png`
- Hold-strip SHA-256:
  `991b06d66605d129c2147c4432e1d1bac65b1d485644388852ca2d81fb722178`
- Human review: passed; no visible identity change, shape hallucination, or
  temporal redraw crawl

Final hold, frames 430-453:

- upper-face first/last SSIM: `0.937358`
- upper-face adjacent luma mean/max: `0.233295` / `0.422375`
- left-wall adjacent luma mean/max: `0.017598` / `0.390055`

The finish is slightly less static than the source but remains sub-luma on
average and visibly stable. The sharpening and grain cleanup were judged worth
that documented tradeoff.

## Versioned production records

- Full Phase 12 rationale and evidence:
  `docs/JUNE_NPR_LOOKDEV_PHASE12.md`
- Pinned AI-finish contract:
  `concept/style_frames/june_oxley_npr_finish_v2.json`
- Semantic look profile:
  `concept/style_frames/june_oxley_npr_look_v5.json`
- Sound profile:
  `concept/style_frames/june_golden_scene_sound_design_v1.json`
- Delivery auditor: `pipeline/cartoon_delivery_audit.py`
- Sound synthesizer: `pipeline/cartoon_sound_design.py`
- AI finish: `pipeline/cartoon_ai_finish.py`

Generated media remains outside Git. Commit source, profiles, tests, documents,
and hashes; do not add the MP4, WAV, audit PNGs, downloaded artifacts, Blender,
or Real-ESRGAN binaries.

## Exact next step

Start Phase 13 as a 30-60 second deformation-and-continuity pilot. First fix the
close-up bottlenecks—eyelids, cheeks, mouth corners, beard, wrists, fingers, and
cloth topology—then author hand shapes, breathing, eye darts, overlap,
anticipation, overshoot, and settle. Prove the improved June asset across more
locations, camera angles, and prop interactions before another full promotion.

Use the existing linear-UCB learner only to rank bounded visual experiments.
Feed it identity, temporal, render-cost, and blinded pairwise-review evidence;
never let it edit immutable profiles or waive human art-direction gates.
