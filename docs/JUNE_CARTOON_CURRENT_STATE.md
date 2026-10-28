# June Oxley cartoon — current state and entry point

Updated 2026-10-28. Branch: `agent/phase42-human-rejected-gates-repair-v1`.

## What the program can do now

The local renderer can animate June's registered source artwork with timed
mouth shapes, eyelid closure, head motion, restrained torso/arm/hand acting,
porch atmosphere, and a camera push. Existing scene components include a pour
action and a 303-frame / 10.1-second three-shot edit. The full-mix audio
successors are local 48-kHz stereo PCM24 files; no runtime AI service is needed.

The earlier adapter, `pipeline/cartoon_repaired_acting.py`, connects the repaired
eyelids to the existing body/face/head/atmosphere/camera stack. It reuses those
renderers rather than introducing another animation engine. It also maps each
direct-address source frame to its exact output-frame and audio-sample window.

James has now explicitly accepted recorded-Foley v3 and blink-refinement v3:
`collab/JAMES_VERDICT_2026-10-28b.md`. The exact component files and scope are
bound in `concept/characters/june_oxley_phase42_component_acceptance_v1.json`.
The new full-scene path is `pipeline/cartoon_scene_review.py`. It uses those
approved components, the existing body/head/camera stack, and only the first
75 unaffected opening frames from the verified lossless source archive. It
does not reuse the older adapter's rejected audio as an output soundtrack.

This is still a constrained, source-art-based 2.5D prototype, not a free-turning
3D character or a general episode-production system. Passing component tests
does not make its acting natural or its overall quality competitive.

## Review the current evidence

1. Full integrated scene, 1920x1080 / 30 fps / 303 frames / 10.1 seconds:
   `collab/phase42_integrated_scene_review_v1/june-phase42-integrated-scene-review-v1.mp4`.
   This is the normal-speed complete scene, not a short blink loop. The adjacent
   MOV preserves the exact approved PCM24 audio; MP4 uses AAC for convenient
   playback. Both use the same encoded picture without a second video encode.
2. Accepted components, preserved for comparison rather than reopened gates:
   `collab/phase42_blink_refinement_v3/phase42-blink-comparison-real-cadence-v3.webp`
   and `collab/phase42_recorded_foley_v3/june-phase42-recorded-foley-v3.wav`.
   James accepted both in his exact message, "both are good and pass. continue".
   The original pending-review reports remain historical snapshots; the later
   verdict and component binding record acceptance without rewriting them.
3. Earlier combined body/eye stills:
   `collab/phase42_repaired_acting_integration_v1/phase42-acting-eye-integration-comparison-v1.png`.
   Columns are original / body acting only / body acting plus repaired eyes.
   Six sampled frames prove compatibility, not whole-scene temporal acceptance.

Current human decisions: blink v3 and recorded audio v3 pass. The newly
integrated performance, mouth/voice sync, body/hand acting and edit continuity
still need judgment at normal speed. Candidate03, Phase37 V4, balanced-air
audio and sparse tonal v2 remain rejected and immutable. See James's exact
verdicts through `collab/JAMES_VERDICT_2026-10-28b.md`.

The accepted slower blink now occurs near 8.2 seconds in the full edit, at
output F247-F248. Its source clock is unchanged; the full edit has a 2.5-second
opening before the 7.6-second dialogue/camera section. Credits and modification
notices for the recorded Foley must travel with any derivative audio/video.

## Safe local commands

Run from this branch's repository root with the existing Python environment.

New scene source-binding, restored-context, live-frame and published-proof checks:

```powershell
python -m unittest pipeline.tests.test_cartoon_scene_review -v
```

Build a separately named full review, never overwrite a prior candidate:

```powershell
python -m pipeline.cartoon_scene_review --output ../../outputs/edit/my-new-scene-review
```

This uses installed local FFmpeg/FFprobe and the existing preserved opening
archive at `outputs/edit/phase36-ledger-pour-lossless-v1-candidate-01/`.
That 415,959,046-byte lossless source is an external local data dependency,
not fetched automatically or included in a fresh Git checkout. A fresh
checkout needs the preserved cache; it is not yet a self-contained episode
production package. The resulting review files are independently playable.

The builder retains a new lossless full-scene RGB cache outside Git so future
delivery tuning can avoid re-running the animation. Do not re-encode an old
lossy movie or reuse retired one-shot delivery commands as a shortcut.

Focused live integration checks (re-render selected frames in memory):

```powershell
python -m unittest pipeline.tests.test_cartoon_repaired_acting -v
```

Recorded-Foley source, voice-preservation, licensing and sample-clock checks:

```powershell
python -m unittest pipeline.tests.test_cartoon_recorded_foley -v
```

The two small recorded assets are already vendored with credits. The audio
builder uses the installed local FFmpeg decoder; it does not fetch sources,
regenerate speech, invoke an inference service, or run a video encoder.

Continuous blink controls and published playback/source checks:

```powershell
python -m unittest pipeline.tests.test_cartoon_continuous_blink -v
```

Build the six-frame integration evidence in a new, never-used output directory:

```powershell
python -m pipeline.cartoon_repaired_acting --output ../../outputs/edit/my-new-integration-review
```

The builder refuses an existing destination. Do not rebuild an unchanged proof
just to satisfy a scheduled wake. It creates still images and a report, not a
movie, full scene, or production promotion. The report must not be interpreted
as human acceptance.

No new dependencies, paid credentials, external inference, or cloud render job
are required by these paths. The older TikTok workflow below the main README
notice is a separate legacy path; its API-key setup is not the cartoon setup.

## What is still missing

- A human-approved integrated scene at normal playback speed with clean audio.
- Convincing sustained performance across dialogue, pauses, gestures, and cuts;
  sampled stills cannot prove this.
- Broader character/pose coverage, staging, scene variation, and reusable
  episode-scale production. This fixed-view rig does not establish them.
- A validated end-to-end full delivery using the current repaired components.
  The retired/rejected builders must not be retried as a shortcut.
- A self-contained production-source package that does not depend on an
  existing local opening-frame archive.

The cheapest next decision is James's review of the full integrated performance,
especially the pour-to-camera transition, talking motion, hand contact and
close-up settle. Eye/audio component acceptance is already recorded; do not
ask James to repeat it without a new regression. Keep main and all rejected
artifacts untouched. No tests or metadata checks establish competitive acting
or close the overall cartoon objective.
