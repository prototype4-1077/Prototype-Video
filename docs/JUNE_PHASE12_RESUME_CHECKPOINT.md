# June Phase 12 Resume Checkpoint

Checkpoint date: 2026-07-28 (America/Chicago)

## Objective

Finish the 15.1-second June Oxley storybook scene as a zero-cash production
prototype with selective semantic ink, polished acting, exact synchronized
dialogue/captions, original authored foley, a verified 1080p finish, and a
reproducible GitHub promotion record.

## Repository state

- Worktree: `C:\Users\jwats\Documents\Codex\2026-07-28\d\work\Prototype-Video`
- Branch: `agent/june-hero-unified-sculpt-phase-5`
- Pull request: https://github.com/prototype4-1077/Prototype-Video/pull/8
- Base: `agent/june-hero-asset-v2-phase-4`
- `main` remains untouched.
- Remote promotion commit: `c7932efcf2f3fd50699d5727dbc3f188e13aca31`
  (`Promote the semantic ink cartoon in parallel`)
- The local checkpoint immediately after that commit contains the streaming
  visual-metrics fix plus the deterministic sound-design implementation. It is
  intentionally not pushed while the expensive promotion run is active.

Always use this safe-directory option for local Git commands:

```powershell
git -c safe.directory=C:/Users/jwats/Documents/Codex/2026-07-28/d/work/Prototype-Video ...
```

The local OAuth token cannot push workflow-file changes. Modify
`.github/workflows/pipeline-tests.yml` with the GitHub connector, then fetch and
rebase locally.

## Active external render

- GitHub Actions run: `30454667937` (run 66)
- Workflow revision: `c7932efcf2f3fd50699d5727dbc3f188e13aca31`
- Regression job: passed.
- Six deterministic Blender ranges are rendering in parallel:
  `1-76`, `77-152`, `153-228`, `229-304`, `305-380`, `381-453`.
- Assembly job name: `assemble-v5-npr`
- Expected assembled artifact name:
  `june-golden-performance-storybook-semantic-npr-v1`
- Expected source files:
  `june-golden-performance-semantic-npr-v1.mp4` and its JSON report.

Do not start another full promotion. First inspect run 66. If all jobs pass,
download the assembled artifact, verify its GitHub digest, SHA-256, 960x540
dimensions, 30 fps, exactly 453 frames, 15.1-second clock, and full decode.

## Approved Phase 12 audition

The v1.4.0 semantic compositor was rejected for excessive form/background ink.
The tuned immutable v1.4.1 profile passed the one-second GS050 gate.

- Profile: `concept/style_frames/june_oxley_npr_look_v5.json`
- Style version: `1.4.1`
- Temporal artifact ZIP SHA-256:
  `d71bcbe2a8d7bfc24cda0a54b84494b6a3e810c550294b1649a137b32e9eb5ee`
- Temporal source SHA-256:
  `f2d445e766f02117c5aa4f3d8b6dc605b9a09a922bb38caf5776ea3ad14ada12`
- Identity similarity against Phase 11: luminance SSIM `0.951780`.
- Full-frame adjacent luma difference: `1.222086`, down 18.8 percent from
  Phase 11 and down 20.7 percent from rejected v1.4.0.
- Face/torso adjacent luma difference: `2.017817`, down 18.5 percent from
  Phase 11 and down 20.7 percent from v1.4.0.
- Right-wall adjacent luma difference: `0.017234`, down 32.8 percent from
  Phase 11 and down 21.4 percent from v1.4.0.
- Upper-left-wall adjacent luma difference: `0.007384`, down 54.1 percent from
  Phase 11 and down 17.1 percent from v1.4.0.
- No silhouette halos, identity drift, or visible temporal crawl were observed.

Evidence outside the repository:

- `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-semantic-ink-v4-v141-comparison.mp4`
  SHA-256 `41f7378ac99a28890ecf78dd5cce6889e587bd800c39be52e0d73d8c31a4dedf`
- Matching PNG SHA-256
  `78750763b2128c5243ca1e943a303947ec6b051ea3e6248132d01888da527350`
- Corrected metrics JSON SHA-256
  `8dc505056ef760de2c84a1465ad2a84d8dc478a1c00a14293ba739575644759c`

## AI finishing audition

The free/local Real-ESRGAN AnimeVideo-v3 audition completed successfully:

- Output:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-semantic-ink-v141-finished-temporal.mp4`
- Output SHA-256:
  `172725dd0f90d9c6e9b57d7b93bbc5858994756063eba6a2fa495c503d5939a8`
- Contract: 1920x1080, 30 fps, 30 frames, 1.0 second, full decode passed.
- SSIM against a conventional Lanczos 2x reference: `0.993323`.
- It visibly cleans Blender grain and sharpens eyes, beard planes, and ink.
- Static upper-left and left-wall variation fell slightly. Right-wall variation
  rose from `0.015507` to `0.025094`, still far below a visible one-luma change.
- Comparison PNG:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-semantic-ink-v141-finish-comparison.png`
  SHA-256 `b1254ba37387364b6a27ffac507465efd0fb8989c2b49be2f5771de96deaf756`
- Metrics JSON SHA-256:
  `7c228e076e165c4f05cc136d444b9c080b30d3fb65ba01ebaa0d1f9fcfe5d1eb`

The finish remains a candidate, not yet the Phase 12 master. Review a full-scene
nine-pose matrix after promotion, especially the 24-frame final hold at frames
430-453, before spending the roughly 85-minute full upscale.

## New local production improvements

`pipeline/cartoon_visual_metrics.py` now streams decoded frames instead of
holding whole 1080p clips in memory. Regions are tied to the actual GS050
composition: full frame, face/torso, left wall, right wall, and upper-left wall.

`pipeline/cartoon_sound_design.py` plus
`concept/style_frames/june_golden_scene_sound_design_v1.json` synthesize an
original deterministic stereo foley stem with room tone, chair weight shift,
boot settle, ledger rustle, pencil contact, and compassion breath. No external
samples, licenses, services, or APIs are used.

- Focused tests: 7 passed.
- Generated stem: 48 kHz stereo, exactly 724,800 samples / 15.1 seconds.
- Stem path:
  `C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-golden-scene-authored-foley-v1.wav`
- Stem SHA-256:
  `ee73375726065246e78c6124d94e63b2658c9c2f43964474b18f29172be0988d`
- Peak: `-29.494 dBFS`, intentionally subordinate to narration.

## Exact resume order

1. Query run `30454667937`; wait for all six chunks and assembly.
2. Download and validate the assembled artifact. Extract a nine-pose matrix at
   frames 1, 93, 171, 172, 260, 339, 340, 398, and 453, plus a strip covering
   frames 430-453 to prove the final held pose.
3. Restore `.github/workflows/pipeline-tests.yml` to the economical v5
   30-frame temporal gate with the GitHub connector. Pull/rebase locally.
4. Run the complete regression suite, commit/push the local checkpoint, and
   confirm the restored CI gate passes. Avoid retriggering the six-chunk job.
5. Mix the generated foley beneath the approved dialogue with FFmpeg, preserving
   48 kHz stereo and applying a conservative limiter. Audition intelligibility.
6. If the full visual gate passes, run `pipeline.cartoon_ai_finish` on the
   453-frame source with 2x scale, restore the mixed audio, burn the approved
   captions, and emit a delivery report. If the full finish crawls, deliver a
   Lanczos 2x master instead; the visual gate decides, not the label "AI."
7. Verify exact 1920x1080 H.264/AAC, yuv420p, 30 fps, 453 frames, 15.1 seconds,
   48 kHz stereo, full decode, captions, SHA-256, and final matrix.
8. Write `docs/JUNE_NPR_LOOKDEV_PHASE12.md`, update the PR with run/artifact
   evidence, and leave the next recommendation: topology/hand/eyelid deformation
   plus a longer multi-shot continuity pilot.

## Existing Phase 11 fallback

The last fully promoted master remains:

`C:\Users\jwats\Documents\Codex\2026-07-28\d\outputs\june-golden-scene-storybook-npr-v1.mp4`

SHA-256:
`203a1b48abe219c2c3a89215baa03725279f5c160d59c68c42be83ecf1e56b25`
