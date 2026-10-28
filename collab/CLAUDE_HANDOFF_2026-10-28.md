# Claude visual-effects handoff — 2026-10-28

## Request and authority

James asked: "Lets give Claude access to help with visual effects. We had
something set up earlier in the program." Reuse this repository protocol
and his already signed-in Claude Code, not a new API integration. James
confirmed extra usage / usage credits are off. First task is read-only.

Repository: `prototype4-1077/Prototype-Video` (already public).
Branch: `agent/phase42-human-rejected-gates-repair-v1`.
Starting committed checkpoint: `cccdcb5eadd50153b9173a32f1065a8c9a1fe60c`.
New verdict and hand study may be local additions during the first review.

Connection result: Claude Code 2.1.126 reports a saved subscription login,
but the single bounded review attempt failed with HTTP 401, "OAuth access
token is invalid." It returned zero input/output tokens and $0 cost. No
review or visual inspection was completed by Claude. Stop retries until
James signs in again. Do not extract/refresh credentials through private
endpoints or change authentication to a paid API key.

Do not change account permissions, invite a guessed GitHub identity, create
API keys or run `.github/workflows/idea.yml` (legacy paid API path). Existing
subscription access is sufficient for a local review; stop at its limits.

## Current human decision — not older review state

Read `JAMES_VERDICT_2026-10-28b.md` and `JAMES_VERDICT_2026-10-28c.md`.
James accepted eye v3 and recorded-Foley v3, then said of the full scene:

> "mouth needs a little work. Movements are a little stiff and rubbery. Transitions are ok."

He clarified the rubbery motion is **"hand end of scene."** Preserve cuts,
voice timing, eye artwork and audio. Do not implement the older proposal to
add recovery footage or broadly change head/shoulder acting. Whole-scene
human acceptance and production promotion are still false.

## Actual visual evidence available in the checkout

All following paths are repository-relative:

- `collab/phase42_integrated_scene_review_v1/june-phase42-integrated-scene-review-v1.mp4`
  — current reviewed 10.1-s, 303-frame, 1920x1080, 30-fps scene.
  SHA-256 `fe68c2852ee36d04c49382c0b8dc558dae1a6ccfa44be6526586b286c667437c`.
- Same directory: `decoded-scene-contact-sheet-v1.png`, `reference-f145.png`,
  `reference-f244.png`, `reference-f248.png`, and
  `decoded-blink-in-scene-30fps-v1.webp`. PNGs are readable visual evidence;
  do not claim a movie or animated WebP was played if your tools cannot do so.
- `collab/phase34_candidate_09/june-phase34-source-textured-visemes-mouth-poses-v2.png`
  — actual internal X/A/B/C/D/E/F/G/H artwork. Inspect this image before
  assuming those letters use Rhubarb's semantics.
- `HAND_REFINEMENT_FINDINGS_2026-10-28.md` describes one unapproved hand study
  (currently a local draft; not part of this documentation-only publication).

Optional local-only hand outputs are outside the checkout at
`../../outputs/edit/phase42-hand-refinement-v1/`:
`late-hand-native-keyframes-v1.png`, `late-hand-native-ab-30fps-v1.webp`,
`late-hand-study-report-v1.json`. A remote checkout will not have these until
published. These are studies, not approved replacements.

Frame conventions: output is one-based. Cuts are output F076 and F238.
Dialogue source F001-F228 maps to output F076-F303 (add 75). Speech begins
at output 3.3 s. Late-hand study source F091-F148 maps to output F166-F223,
5.500-7.433 s half-open. The final close-up largely hides this hand.

## Two specific hypotheses to challenge

1. **Mouth translation mismatch (GPT finding, not yet implemented).**
   `pipeline/cartoon_viseme_atlas.py::performance_viseme_plan` forwards raw
   Rhubarb labels, but internal artwork has different meanings. Rhubarb A
   is closed P/B/M and G is labiodental F/V; our A opens and G is rounded.
   Our internal F is labiodental, C clenched teeth, B largest-open, X rest.
   Read `concept/style_frames/june_phase33_direct_address_rhubarb_v1.json`
   and `concept/characters/june_oxley_phase34_source_textured_visemes_v2.json`.
   Official semantics: https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes
   Challenge the mapping against the actual pose sheet. Recommend a small
   mouth-only correction; keep cue times/audio fixed. Do not mistake a
   labeling fix for proof of expressive lip-sync or jaw/beard continuity.
2. **Late hand deforms independently.** New
   local draft `pipeline/cartoon_hand_motion_refinement.py` proposes one restrained,
   coherent 0.65-degree rock about a planted index-tip instead of independent
   finger spreading/compression. Tests report containment, sustained motion,
   rigid-map geometry and unchanged accepted eye frame. These establish
   invariants, not naturalness. Look for a frozen/pasted hand, wrong pressure,
   wrist hinge, edge sliding or an entry/release hitch. Consider whether a
   geometry fix addresses the real perceptual complaint.

## Deliverable for the first review

Return a concise Markdown review: files/images actually inspected, strongest
visual observation, up to three ranked issues, cheapest useful experiment,
and what cannot be judged with your available tools. State whether the hand
candidate should advance to a short normal-speed integrated A/B, be revised,
or be rejected. Do not approve the entire scene from stills.

No edits, shell execution, new agents, rendering, paid calls, CI dispatch,
uploads, merges or production promotion during this read-only task. GPT
will persist the real Claude response as `CLAUDE_REVIEW_*.md`, reply with
builder notes and prepare only the next bounded experiment if warranted.
