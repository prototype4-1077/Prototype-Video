# June Oxley Phase 29 — Competitive Cartoon Reverse-Engineering Checkpoint

Date: 2026-08-01

## Decision

Phase 28 is a valid deformation-engineering proof and a useful component. It is **not** yet evidence of a competitive cartoon performance. Phase 27 remains the audience-facing control because it already combines authored wide action, prop mechanics, close facial acting, finished sound, captions, and editorial cuts.

Phase 29 will not invent a new story or attempt a universal puppet. It will build one production-compatible deformable adapter, then test it by replacing only the existing 171-frame `STAND_UP` action in the Phase 27 reel. The pour, close-up, audio, captions, frame clock, and cuts remain unchanged. The replacement is promoted only if a blind A/B is non-inferior to the accepted control.

This answers the next real question:

> Can continuous deformation enter an already convincing June scene without lowering identity, action readability, prop contact, art quality, sound, or editorial continuity?

## Reverse-engineering team

Three independent roles inspected the accepted Phase 28 master, report, renderer, contracts, character bible, and earlier Phase 24–27 evidence.

- Creative director: defined the finished audience experience and identified acting, face, cinematography, and world response as the largest experiential gaps.
- Technical director: traced the current adapters and found the exact compatibility blockers: Phase 28 is empty-handed, has only body plus right-arm layers, has no chair or mug sockets, has no registered three-quarter facial atlas, and exposes a hard-coded proof timeline rather than Phase 27 semantic inputs.
- Adversarial producer: rejected a competitive-quality claim, audited misleading proxy metrics, and required a controlled A/B rather than another attractive standalone demo.

The team initially disagreed about whether to splice Phase 28 into Phase 27 immediately. The cross-examination resolved this into two ordered gates: first create a compatible adapter fixture; then perform the full controlled replacement comparison. The adapter alone is not an audience-facing success claim.

## Evidence baseline

### Phase 26 — finished sound master

- 38.8 seconds, 1,164 frames, 1920×1080 at 30 fps.
- Dialogue, porch ambience, 26 Foley events, captions, and exact picture-stream preservation.
- PCM master: −16.06 LUFS-I, 4.5 LU LRA, −1.29 dBTP.
- Piper `en_US-norman-medium` remains a prototype casting placeholder.

### Phase 27 — accepted production control

- 21.9 seconds, 657 frames, finished A/V and captions.
- Three honest shot-specific adapters behind one semantic contract:
  - `WIDE_BODY_3Q`: registered body drawings and contacts.
  - `TABLE_MEDIUM_3Q`: mug, pot, hand, liquid, and spill controls.
  - `CLOSE_HERO_FRONT`: visemes, expressions, head motion, camera, and atmosphere.
- This proves a heterogeneous production architecture. It does not prove unrestricted character synthesis.

### Phase 28 — candidate deformable component

- 12 seconds, 360 frames, silent, one three-quarter full-body view.
- Continuous Gaussian inverse warp, two depth layers, foot pins, and elbow/knee correctives.
- Exact decode, zero numerical foot-pin drift, 338 distinct landmark poses, bounded temporal steps, and retained detail.
- It does not prove a real chair sit, grasped prop, facial acting, voice synchronization, weight transfer, or shot-to-shot identity continuity.

## Honest competitive verdict

Status: **GO as a research and production prototype; NO-GO for claiming competitive web-cartoon quality.**

The current render reads as a high-quality painted still being warped. The face, smile, and gaze remain fixed; action intention is unclear without labels; the reach has no target; the sit is a planted crouch; and the camera never changes. Earlier phases contain stronger story, face, prop, and sound systems, but they remain separate shot adapters whose identity and proportions can shift between generated source plates.

The existing `quality_gate_passed` result is true within its engineering scope. It proves deterministic delivery and bounded deformation. It does not prove acting, identity, balance, comedy, story comprehension, or audience preference.

## Metrics that must not be mistaken for cartoon quality

- Identity strings in JSON describe intended identity; they do not inspect pixels.
- Zero foot drift proves pinning; it does not prove believable weight, toe/heel mechanics, or balance.
- Hand excursion proves distance traveled; it does not prove an arc, anatomy, grasp, or contact.
- Distinct landmark states prove parameter variation; they do not prove readable acting.
- Laplacian variance proves high-frequency detail and can reward noisy or torn texture.
- Alpha-area stability cannot detect an implausible silhouette or collapsed joint.
- Decode, codec, and hash gates prove reproducibility, not entertainment value.

Future reports must separate `delivery_integrity`, `mechanical_integrity`, and `audience_quality`. No aggregate pass may silently convert the first two into the third.

## Finished-product north star

A competitive 2–4 minute June cartoon should feel like a few minutes with a sharp old neighbor who makes the audience laugh, recognize something ordinary differently, and then unexpectedly goes quiet.

The target episode shape is:

1. Begin with a specific town incident.
2. Let a rural object or mechanism become the visual metaphor.
3. Use June's joke to open the audience.
4. Let object, town, weather, and neighbor imagery carry most of the explanation.
5. Move closer only when the thought becomes personal.
6. Give the honest or painful line silence and visual space.
7. Return to a physical porch action so the scene does not become a lecture.
8. End on a memorable rural button that hands the question to the viewer.

Production target: approximately 22–28 motivated shots, four useful shot sizes, and no more than 45% human-heavy imagery. The character bible's stronger target of about 30% human-heavy imagery remains preferred. Sound is the temporal spine: voice, breath, pause, porch ambience, selective board/chair/mug Foley, and deliberately used quiet.

## Backwards dependency map

```text
Audience laughs, believes June, and remembers the quiet line
└── Finished 2–4 minute episode
    ├── Locked story and emotional turn
    │   ├── specific incident
    │   ├── ruling rural-object metaphor
    │   ├── joke → investigation → knife line → button
    │   └── honest boundary where the facts end
    ├── Locked voice performance
    │   ├── final casting
    │   ├── breaths, drawl, chuckles, and pauses
    │   └── exact stress and silence timing
    ├── Animatic and editorial grammar
    │   ├── wide / medium / close / insert palette
    │   ├── motivated cuts and reaction holds
    │   ├── eyeline, screen direction, and prop continuity
    │   └── object- and town-led visual argument
    ├── Shot-family performance adapters
    │   ├── deformable wide body mechanics
    │   ├── constrained hand / prop / liquid actions
    │   ├── registered close facial acting
    │   └── inserts, environment, and atmosphere
    ├── Shared semantic performance score
    │   ├── intent, body pose, root and contact
    │   ├── gaze, blink, expression, and viseme
    │   ├── prop, camera, light, and atmosphere
    │   └── editorial and sound clock
    ├── Deterministic local assembly and render pipeline
    └── Promotion evidence
        ├── delivery and mechanical gates
        ├── blind action / identity / preference gates
        └── second-shot reuse without a new whole-character generation
```

## Production architecture

The strongest zero-cash design is **heterogeneous, shot-based, and contract-driven**. One representation should not be forced to solve every shot.

```text
script → timed voice → shot contracts → semantic performance tracks
                                      ↓
               ┌──────────────────────┼─────────────────────┐
               ↓                      ↓                     ↓
       deformable body       prop/contact adapter    face-performance adapter
               └──────────────────────┼─────────────────────┘
                                      ↓
                     compositor → editorial → sound → gates
```

The stable product is the semantic interface and the shot contract, not a single mesh. A view adapter may use continuous deformation, registered drawings, a feature atlas, procedural liquid, or a direct high-quality insert. Each adapter is promoted independently against an accepted control.

This preserves the best pixels already produced while letting weak adapters be replaced incrementally. It also avoids the most expensive failure mode: lowering every shot to the capabilities of one universal rig.

## Ranked blockers

1. **Acting legibility:** intention, gaze, blink, anticipation, weight, follow-through, and reaction are not yet unified.
2. **Identity continuity:** independently authored plates vary in skull, eyes, proportions, age, angle, and color response.
3. **Body mechanics:** the current warp cannot reveal hidden anatomy and does not yet model support changes, heel/toe behavior, or real chair contact.
4. **Hands and props:** Phase 28 has no grasp state, mug socket, receiver, or finger/occlusion correctives.
5. **Direction and world coverage:** the current proof is one locked porch view, while the intended series depends on objects, town locations, weather, and neighbors.
6. **Voice casting:** the sound pipeline is strong, but the present local Piper voice is a prototype placeholder.
7. **Scalability:** new view/action combinations still demand manual art decomposition and registration.
8. **Public reproducibility:** Phase 28 is committed locally but not yet part of the public CI workflow.

## Phase 29 scope — controlled deformable promotion

### Gate A: private adapter fixture

Create `DEFORMABLE_PERFORMANCE_3Q` / `deformable_performance_3q` behind the Phase 27 action interface.

Required semantic inputs:

- `body_pose`
- `root_contact`
- `hand_contact`
- `prop_pose`
- `camera`
- `atmosphere`

Required production topology:

- head and neck
- torso and pelvis
- left and right upper/lower arm chains
- separate hands and grasp correctives
- left and right upper/lower leg chains
- separate boots and support sockets
- mug layer and mug transform
- chair-hand and chair-seat contacts
- costume overlap/correction patches
- receiving shadow and light-wrap layers

Use the accepted Phase 27 seated and standing drawings as registered endpoint/corrective art. Preserve the exact 171-frame `STAND_UP` clock. Do not pretend the empty-handed Phase 28 source can reconstruct hidden seated anatomy or a credible grasp.

Gate A is engineering evidence only. It must not be presented as a new finished cartoon.

### Gate B: audience-facing hybrid A/B

- Control A: untouched Phase 27 performance-rig proof.
- Candidate B: replace only `STAND_UP` with the Gate A adapter.
- Preserve `POUR_COFFEE`, `DIRECT_ADDRESS`, Phase 26 sound, captions, 657-frame clock, and both hard cuts.
- The cut into `POUR_COFFEE` becomes the identity, scale, color, eyeline, and prop-continuity test.
- Publish B only if it is non-inferior to A on action readability, same-character judgment, visible artifact count, and overall preference.

If Gate B fails, retain the Phase 27 authored-pose adapter for episode production and restrict continuous deformation to bounded in-betweens, secondary motion, and corrective intervals. Failure is useful: it identifies the representation ceiling without reopening accepted work.

## Phase 29 acceptance gates

### Delivery integrity

- Exact 1920×1080, 30 fps, 171 action frames and 657 assembled frames.
- Full video/audio decode; deterministic report and content hashes.
- Unchanged Phase 27 pour and close picture frames.
- Unchanged rebased Phase 26 audio, captions, cuts, and delivery loudness.

### Mechanical integrity

- Mug/hand and chair/hand contact error no greater than 3 px for 95% of contact frames.
- No mug penetration, disappearance, duplicated fingers, or broken occlusion.
- Intentional support transfer with center-of-mass proxy over the active support region.
- Heel/toe movement is allowed and scored; both feet must not be frozen merely to win a drift metric.
- No deformation foldover, joint collapse, texture tearing, alpha seam, or costume gap at full speed, quarter speed, and representative stills.
- Maximum temporal landmark step no greater than 8 px outside declared smear frames.
- Accepted seated and standing endpoints match their registered controls.

### Audience quality

- At least 80% correct silent-action read in a blinded panel.
- At least 90% same-character judgment across the cut into the medium pour.
- Candidate B is non-inferior to A on identity, action clarity, visual artifacts, and overall preference.
- Setup, change, and result are understandable without action labels or the quality report.
- A second novel shot can be produced from the promoted adapter without generating another whole character.

Independent evaluator agents may provide a cheap first panel, but their correlated judgments are not a substitute for the user's final real-time visual approval.

## AI, agents, and reinforcement learning

### AI art

Use generation as a production drawing department for view-specific source art, occlusion patches, correctives, props, and backgrounds. Accepted pixels must enter the final composite or be reproduced by equivalent geometry. Every generated asset is identity-checked, registered, content-addressed, and rejectable.

### Agent collaboration

The practical limit is three simultaneous subagents plus the lead. A 30-role effort should therefore run as ten bounded waves of three, with each wave writing to shared contracts and evidence rather than holding an unstructured conversation.

Suggested waves:

1. story, character, and audience north star
2. storyboard, layout, and cinematography
3. character identity, model sheet, and costume continuity
4. body rig, facial rig, and hands/props
5. environment, effects, and lighting
6. voice, Foley, and mix
7. renderer, compositor, and editorial
8. automated QA, visual critics, and accessibility
9. adversarial production audit, scalability, and licensing
10. blind evaluation, integration, and release readiness

Each wave gets one concrete artifact, one cross-examination, one synthesis, and one stop checkpoint. This captures the value of thirty specialist viewpoints without paying the coordination and usage cost of thirty concurrent free-form agents.

### Reinforcement learning

Do not use RL yet. The current proxy metrics are easy to game and would optimize sharp texture, frozen contacts, or large parameter motion rather than good acting.

After one human-approved Phase 29 comparison exists, use a bounded local optimizer first—CMA-ES, Bayesian search, or evolutionary search—to tune timing, anticipation, overshoot, blink placement, gaze lead, corrective weights, and contact offsets. The reward must be a vector with hard rejection gates, not one opaque score.

Only consider preference learning or RL after a library of blinded A/B decisions exists. Keep identity, topology, contact, decode, and loudness as hard constraints outside the learned reward. This prevents reward hacking from promoting technically measurable but visibly worse animation.

## Explicit non-goals for Phase 29

- No new story or unrelated showcase.
- No unrestricted 360-degree June.
- No walking system, cloth simulation, crowds, or multiple speaking characters.
- No replacement of the accepted pour or close-face adapters.
- No attempt to paste the straight-on facial atlas onto the Phase 28 three-quarter head.
- No broad renderer rewrite.
- No paid service or paid runtime API.
- No RL before trustworthy human-approved comparisons exist.
- No claim that Phase 29 is a complete episode.

## Promotion ladder after Phase 29

1. **15–30 second story test:** setup, turn, and payoff; blind comprehension and identity pass.
2. **60–90 second pilot:** at least two locations, one object-led metaphor, four shot families, complete sound, and a second reusable action generated without a new whole-character asset.
3. **2–4 minute episode:** 22–28 motivated shots, final voice casting, object/town coverage, editorial and audio finish, accessibility, public reproducibility, and audience retention/recall evaluation.

## Resume here

1. Add the `deformable_performance_3q` contract and semantic adapter interface.
2. Decompose the accepted Phase 27 seated/standing art into the required topology and register Phase 28 controls to it.
3. Implement mug, chair, support, shadow, and occlusion constraints on the exact 171-frame clock.
4. Render and inspect Gate A.
5. If Gate A passes, assemble hybrid B with the unchanged Phase 27 downstream shots and sound.
6. Run blind A/B evaluation and record both machine and audience evidence separately.

This is the stopping point for the reverse-engineering wave. No render or production asset was changed during this analysis.
