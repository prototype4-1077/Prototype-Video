# June Oxley cartoon — current state and entry point

Updated 2026-10-27. Branch: `agent/phase42-human-rejected-gates-repair-v1`.

## What the program can do now

The local renderer can animate June's registered source artwork with timed
mouth shapes, eyelid closure, head motion, restrained torso/arm/hand acting,
porch atmosphere, and a camera push. Existing scene components include a pour
action and a 303-frame / 10.1-second three-shot edit. The full-mix audio
successors are local 48-kHz stereo PCM24 files; no runtime AI service is needed.

The latest adapter, `pipeline/cartoon_repaired_acting.py`, connects the repaired
eyelids to the existing body/face/head/atmosphere/camera stack. It reuses those
renderers rather than introducing another animation engine. It also maps each
direct-address source frame to its exact output-frame and audio-sample window.

This is still a constrained, source-art-based 2.5D prototype, not a free-turning
3D character or a general episode-production system. Passing component tests
does not make its acting natural or its overall quality competitive.

## Review the current evidence

1. Eye motion at true playback speed:
   `collab/phase42_continuous_blink_review_v2/phase42-eyelid-ai-direct-30fps-v2.webp`.
   The adjacent slow loop is intentionally slower and is labeled as such.
2. Audio: start with
   `collab/phase42_human_rejected_gates_successors_v1/june-phase42-fullmix-balanced_air-v1.wav`.
   Compare the `clean_warm` WAV in the same folder if needed.
3. Combined body/eye stills:
   `collab/phase42_repaired_acting_integration_v1/phase42-acting-eye-integration-comparison-v1.png`.
   Columns are original / body acting only / body acting plus repaired eyes.
   Six sampled frames prove compatibility, not whole-scene temporal acceptance.

Current human decisions: eyes pending, audio pending, body acting pending.
Candidate03 audio and Phase37 V4 eyes remain rejected and immutable.

## Safe local commands

Run from this branch's repository root with the existing Python environment.

Focused live integration checks (re-render selected frames in memory):

```powershell
python -m unittest pipeline.tests.test_cartoon_repaired_acting -v
```

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

The cheapest next decision is James's review of the actual eye and audio
proofs. After acceptance, use the reusable integration adapter in a newly
versioned full review build, then judge the entire performance—not merely its
component scores. Keep main and all rejected artifacts untouched until the
applicable review gates are closed.
