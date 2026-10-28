# PAUSED at James's request — 2026-10-28 — usage near 7%

James requested a pause because usage is low and resets in a little over an
hour. The goal and five-hour heartbeat are paused, not complete. Do not
resume or spend model usage until James asks. No automatic one-hour retry
or new reminder was requested. Keep the existing five-hour schedule paused.

## Claude access is now actually working

James completed sign-in and asked to review access. A standard attempt hit
HTTP 429: usage credits required for long context. After verifying the
documented setting exists in this installed Claude, used the per-launch
`CLAUDE_CODE_DISABLE_1M_CONTEXT=1` flag. Actual Claude Sonnet 4.6, 200K
context, completed a read-only pixel review in 79.501 s with zero permission
denials. Real review and sanitized provenance are saved as:

- `CLAUDE_REVIEW_2026-10-28_STANDARD_CONTEXT.md`
- `CLAUDE_ACCESS_2026-10-28.json`

Only Read/Glob/Grep were exposed; hooks and MCP were disabled. No global
model, account, billing, repository permissions or main changes. James
confirmed extra usage off. The CLI's $0.17284185 token-cost estimate is not
a billing receipt; do not call it an observed cash charge or a $0-token
review. Authentication was the existing Pro subscription, not an API key.
Separate Claude scheduled-task repository attachment remains unverified.

Claude confirms the mouth semantic mismatch from actual artwork and
recommends a short integrated hand A/B, not scene acceptance from stills.
Its suggestion to change the old viseme function should be implemented as
an isolated adapter instead, preserving historical renderer hashes.

## Local repair checkpoint — not yet human-reviewed/published

New draft `pipeline/cartoon_mouth_semantics_refinement.py` translates raw
Rhubarb labels to internal art: A:X, B:C, C:D, D:B, E:A, F:G, G:F, H:H, X:X.
Frame/cue times, blend values, artwork and audio source remain fixed.
`mouth_override` restores both cache objects and plan on exception. Two
independent adapters now reuse identical poses over the complete study.

The first uncached study was stopped by its verified Python/FFmpeg PIDs
because it needlessly recomputed repeated poses; its unfinished files remain
at `../../outputs/edit/phase42-mouth-semantics-v1/`. Do not promote them.

The replacement **finished successfully**, exec session 14943 terminal exit
0. No running mouth job remains to poll. Completed 138-frame native A/B is
at `../../outputs/edit/phase42-mouth-semantics-v1-cache-reuse/`. Its printed
result reports 0 outside-perioral changed pixels and 0 folded triangles.
Do not infer visual acceptance: root still must inspect the decoded movie
samples/keyframe PNG, audit audio/PTS/color, and publish the verified packet.
No full-scene successor was encoded.

20 core mouth/hand tests passed in 207.951 s. Two newly added published-proof
tests were added AFTER that process collected its tests and have NOT run;
they currently need the completed output copied into the repository packet.
Do not report all current tests passing or a full-repository test run.

Hand draft, ten associated tests, findings and native evidence remain at
the paths in the previous handoff. Root inspected its keyframe sheet and
code; actual Claude also inspected those stills. Native/all-frame and six
integrated support checks pass, but real-time acting is not human-accepted.

## Exact next step after James resumes

1. Read this note, latest James verdict and actual new Claude review.
2. Inspect the completed mouth native A/B; verify its final-frame count,
   timestamps, metadata and MOV excerpt audio. Keep the 30-ms preview-only
   fades separate from untouched accepted full-scene PCM.
3. Copy verified mouth/hand evidence into the already created
   `collab/phase42_mouth_semantics_v1/` and `phase42_hand_refinement_v1/`
   folders; include source manifests/credits. Run the new published tests.
   The source files, those packet READMEs and .gitattributes additions are
   local drafts, not staged by this documentation-only checkpoint.
4. Prepare a short normal-speed integrated hand/mouth comparison if the
   native study is visually credible. Preserve accepted cuts/eye/audio and
   all immutable evidence. Do not rerender the unchanged full scene.
5. Re-enable the existing five-hour heartbeat only when James wants it;
   update its stale scope to latest mouth/late-hand feedback at that time.

Goal remains unfinished. Production promotion/main changes remain gated.
