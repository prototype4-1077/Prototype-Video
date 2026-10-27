# GPT notes — 2026-10-27 — repair-to-acting integration, no full render

Branch: `agent/phase42-human-rejected-gates-repair-v1`.
Previous checkpoint: `2f6743ff2765a0ecfa51d73637da5508d42a0879`.
Read protocol and the current James verdict before work. No new James or
Claude review was present; no acceptance was invented.

## Why this was the next useful step

The preceding goal turn made real progress (continuous eyelid coverage and a
true-speed proof). But that repair was still isolated in a diagnostic path.
Phase40 already supplied body/hand/face/head/atmosphere/camera integration;
building a competing renderer would duplicate working code. The narrow useful
action was to connect the repair to that existing stack and verify their
coexistence while human motion/audio review remains pending.

## Implemented

`pipeline/cartoon_repaired_acting.py` reuses Phase40, Phase35, and Phase42.
It validates their predecessor reports and implementation/source bindings,
temporarily installs the registered repaired-lid texture and continuous
control, then restores texture/cache/shared functions. Its callable
`compose_repaired_frame` is reusable by a future accepted integrated build.

The CLI is intentionally only a fixed six-frame still proof. It cannot create
a movie or full scene. It does not retry retired builders, consume rejected
claims, or change main. Source F001-F228 map to output F076-F303, with exact
1,600-sample windows against the existing balanced-air WAV.

## Evidence

Folder: `collab/phase42_repaired_acting_integration_v1/`.

Report SHA-256:
`45e7caabc0824c548d5c03795e9636cce9effd7618f4aecc2f51d9ce2d4047fb`

Comparison sheet SHA-256:
`9ca60ec4e9daa380842a2a35415b82a8de6db46f82c72bc7684ad6b17d1bdeb6`

Sampled source frames: 70, 79, 81, 82, 148, 173. Output frames: 145, 154,
156, 157, 223, 248. The six existing Phase40 candidate frame hashes match
their historical report before the repair is installed.

- F081 exercises the first full blink while hand/torso acting is nonzero.
  Both survive; eye changes outside prospective eye support = 0.
- F070/F148 are open-eye exact bypasses.
- F173 after the compassion camera matches the exact v2 reviewed blink frame:
  `155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40`.
- All six samples have zero body writes in protected face/mug regions, zero
  body writes outside declared body support, and zero eye changes outside
  prospectively projected eye support.

Inspected the actual comparison image, not just the report. It shows the new
eyes within the same June/porch/body composition. The stills do not settle
motion or acting quality, and no such acceptance is claimed.

## Verification and usability

Eleven new tests pass, including live renders and negative experiments that
remove the repair or invalidate the support projection. Context cleanup and
invalid editorial clocks are covered. The combined six-suite run passes
**43 tests in 78.402 seconds**: repaired acting, continuous blink, eyelid source
successor, full-mix audio successor, audio-noise proxy, and predecessor eyelid
edge diagnostic. These are focused local tests, not a whole-repository or
remote-CI pass.

The root README previously described only the older paid-API TikTok render
farm. Added a clearly separated cartoon notice and
`docs/JUNE_CARTOON_CURRENT_STATE.md` with current capabilities, limitations,
review paths, and actual zero-cash commands. Preserved the legacy text.

## Resume without losing the objective

The end goal remains a competitive, working full-cartoon production prototype,
not six stills or a passing component suite. These changes remove an actual
integration gap; they do not prove production quality.

Read any newer human review first. Existing v2 blink/audio decisions are still
the immediate gate; do not ask James to adjudicate infrastructure details.
After the applicable reviews pass, reuse this adapter in a newly versioned
integrated scene rather than creating another competing pipeline. A complete
performance at normal speed with its audio is the next meaningful end-to-end
deliverable. Until then, do not encode/promote a full scene, retry rejected
artifacts, or re-render unchanged evidence on a timer.
