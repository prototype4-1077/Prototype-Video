# June Oxley cartoon — current state and entry point

Updated 2026-10-28. Branch: `agent/phase42-human-rejected-gates-repair-v1`.

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

1. Eye motion at true cadence:
   `collab/phase42_blink_refinement_v3/phase42-blink-comparison-real-cadence-v3.webp`.
   The right side has one slower blink near six seconds, not a short repeated
   crop loop. This is an eye-only, fixed-head study, not full-scene motion.
2. Audio: James still hears static throughout `balanced_air`, and removing the
   continuous porch bed made no real change. He corrected the voice-only
   verdict to **no static**. Preserve that voice. He also heard no static in
   sparse Foley v2, but rejected its game/phone-like effects. The replacement
   audition is `collab/phase42_recorded_foley_v3/june-phase42-recorded-foley-v3.wav`:
   two restrained recorded cues (pour and cup contact), no chimes or constant
   bed, and bit-exact voice contribution. This new mix has no human verdict.
   Its `ATTRIBUTION.md` and `sources.json` must travel with derived audio/video;
   the cup source is CC BY 4.0 and the pour page states public-domain dedication.
3. Combined body/eye stills:
   `collab/phase42_repaired_acting_integration_v1/phase42-acting-eye-integration-comparison-v1.png`.
   Columns are original / body acting only / body acting plus repaired eyes.
   Six sampled frames prove compatibility, not whole-scene temporal acceptance.

Current human decisions: eyes are near-pass but still need work; balanced-air
audio is rejected for static throughout; sparse v2 passes the static check
but fails effect character; recorded v3 and body acting are pending. Candidate03,
Phase37 V4, and all reviewed Phase42 files remain immutable. See James's exact
verdicts in `collab/JAMES_VERDICT_2026-10-27.md` and
`collab/JAMES_VERDICT_2026-10-28.md`.

The latest blink feedback asks for slightly slower, less frequent closure and
a small shape adjustment. `collab/phase42_blink_refinement_v3/` contains a
fixed-head eye-only audition at the 7.6-second scene clock: one slower blink,
not a rapidly repeating half-second loop. The closed-eye source artwork is
unchanged. This is not a full-scene motion render or an accepted timing change.

## Safe local commands

Run from this branch's repository root with the existing Python environment.

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

The cheapest next decision is James's review of the actual eye and audio
proofs. After acceptance, use the reusable integration adapter in a newly
versioned full review build, then judge the entire performance—not merely its
component scores. Keep main and all rejected artifacts untouched until the
applicable review gates are closed.
