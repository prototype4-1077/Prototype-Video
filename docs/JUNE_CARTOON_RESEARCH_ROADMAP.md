# June Oxley Cartoon Production Research Roadmap

## Goal

Build a repeatable, zero-cash production system that can turn an authored June
Oxley scene into a coherent cartoon with stable identity, readable acting,
art-directed rendering, synchronized sound, exact delivery timing, and evidence
for every promotion decision.

This roadmap distinguishes a competitive working prototype from the later work
required for studio-grade recurring production. It does not use "AI" as a
substitute for art direction; AI is allowed only where it preserves authored
identity, timing, and review authority.

## What professional cartoon production actually contains

OpenToonz documents the traditional production path as layout, animation,
paint, Xsheet timing, compositing, effects, and final render. Its Xsheet is a
useful mental model because every drawing, prop, audio level, and effect remains
an independently timed layer rather than becoming an opaque generated clip.

- Production workflow: https://opentoonz.readthedocs.io/en/latest/production_workflow.html
- Xsheet/timeline: https://opentoonz.readthedocs.io/en/latest/working_in_xsheet.html
- Onion-skin animation: https://opentoonz.readthedocs.io/en/latest/drawing_animation_levels.html

The June pipeline now implements the equivalent stages as data contracts:

1. Character bible and canonical identity references.
2. Versioned mesh, materials, body rig, facial controls, props, and scene.
3. Authored shot/performance timing on an exact 30 fps frame clock.
4. Audio-derived visemes plus expression, eye, blink, and gesture animation.
5. Storybook NPR light, toon values, neutral ink, depth, and compositing.
6. Parallel image-sequence rendering and exact-frame assembly.
7. AI-assisted 2x finishing only after a temporal gate.
8. Audio, captions, full decode, and immutable delivery evidence.

## Graphic-design findings that matter on screen

### Shape language before surface detail

June must read from silhouette and proportion before texture or lighting is
added. The current large eyes, swept white hair, beard mass, lean torso, plaid
workwear, mug, and ledger are identity anchors. More geometry is useful only
when it improves a pose, facial plane, deformation, or prop contact.

### Value grouping before realism

Cartoon shade is semantic notation, not merely simulated light. The render
therefore uses two toon thresholds, explicit warm/cool light roles, and a small
number of readable value groups. The research basis is the NPAR paper
"Tweakable Light and Shade for Cartoon Animation," which argues for directly
art-directed shade shapes rather than treating them as purely physical output:
https://research.google/pubs/tweakable-light-and-shade-for-cartoon-animation/

### Line hierarchy, not one edge detector

The neutral Sobel pass is a clean prototype, but a mature cartoon needs separate
control of silhouette, crease, material boundary, facial detail, and shadow
lines. Blender's Line Art modifier exposes exactly these edge classes, supports
occlusion, face-mark filters, thickness, material assignment, smoothing, and
baking over a frame range:
https://docs.blender.org/manual/en/4.2/grease_pencil/modifiers/generate/line_art.html

The next line system should use at least three authored layers:

- heavy silhouette and contact ink;
- medium facial, prop, and clothing construction lines;
- light texture/shadow accents that disappear in motion or wide shots.

### Temporal coherence is part of the style

A texture or line that is attractive in one frame can look broken when it
crawls. "Fluidymation" demonstrates why animated style exemplars and natural
medium dynamics are stronger than applying a static style independently to each
frame:
https://research.google/pubs/fluidymation-stylizing-animations-using-natural-dynamics-of-artistic-media/

Pixar's work on stylized ribbons likewise identifies line work and temporal
consistency as core problems:
https://graphics.pixar.com/library/Ribbons/paper.pdf

Accordingly, every June look promotion requires a temporal window, not only a
hero still. Surface texture should be attached to object coordinates, and line
variation should be temporally band-limited rather than randomized per frame.

### Timing and spacing carry the performance

Blender F-Curves interpolate sparse authored keys, but interpolation is only the
starting point. Animation quality comes from choosing anticipation, breakdown,
overshoot, settle, holds, and asymmetry deliberately:
https://docs.blender.org/manual/en/4.2/editors/graph_editor/fcurves/introduction.html

June's next acting pass should measure arcs and pose holds instead of adding
more undirected motion. Stillness at the ledger realization is as important as
the earlier gestures.

## Zero-cash AI and reinforcement learning

### Production agents with separated authority

Agents are most useful at contract boundaries, not as a crowd generating
unreviewable frames. A future production run can use these roles in parallel:

- **Director agent:** converts the approved script and voice into beats, shots,
  performance intent, and immutable timing. It cannot alter character identity.
- **Continuity agent:** checks June, wardrobe, props, eyelines, screen direction,
  and set geography against canonical references. It cannot render or promote.
- **Animator agent:** proposes pose, gaze, face, hand, prop, anticipation, and
  settle keys from the performance intent. Its plan must pass contact and timing
  validators before Blender receives it.
- **Look agent:** proposes bounded NPR profiles and asks the contextual bandit
  which experiment is most informative. It cannot relax reward floors.
- **Render agent:** executes deterministic frame ranges and emits hashes and
  reports. It makes no aesthetic decisions.
- **QA agent:** measures frame continuity, temporal stability, audio sync,
  identity gates, and delivery conformance. It cannot rewrite the artifact it
  judges.

No agent may both create and approve the same evidence. Only a human can promote
an identity, acting, or visual-style change. This division makes parallelism
useful while preserving accountability and reproducibility.

### AI finishing

The approved finishing candidate is the open-source Real-ESRGAN AnimeVideo-v3
model. The official project explicitly supports portable NCNN/Vulkan binaries
and an animation-video model, including 2x output:
https://github.com/xinntao/Real-ESRGAN

It is used as a restoration/upscale stage, not a generator. The temporal
audition must pass before it can touch a delivery, and the original Blender
frames remain authoritative.

### Contextual preference bandit

Full policy-gradient reinforcement learning would waste renders and obscure why
a visual choice won. The useful formulation here is a contextual bandit:

- context: shot scale, motion intensity, emotion intensity, background complexity;
- action: an immutable NPR look profile;
- reward: identity, expression readability, temporal stability, silhouette,
  palette harmony, human preference, and render cost;
- hard constraints: identity, acting, temporal, and render-time floors;
- exploration: linear UCB confidence bonus;
- authority: recommendation only; a human still promotes the look.

The implementation is `pipeline/cartoon_look_learner.py`, backed by
`concept/style_frames/june_oxley_npr_reward_v1.json`. It is standard-library
Python, deterministic, local, and paid-API-free.

Preference-learning research supports treating sparse human comparisons as a
bandit problem rather than pretending an absolute aesthetic reward is known:
https://arxiv.org/abs/2312.00267

## What is still missing

The current prototype is a strong procedural storybook cartoon, but it is not
yet honest to call it equivalent to the best hand-authored studio animation.
The remaining gaps, in priority order, are:

1. Art-directed Grease Pencil line layers with facial face marks and stable
   baked strokes.
2. A dedicated acting pass: gesture arcs, hand shape language, shoulder/torso
   overlap, breath, eye darts, anticipations, overshoots, and meaningful holds.
3. More artist-grade mouth, cheek, eyelid, hand, and cloth topology for extreme
   closeups.
4. Shot-specific shade shapes instead of globally simulated toon lighting.
5. Foley, room tone, prop sounds, and a restrained original score mixed around
   the dialogue.
6. A multi-shot pilot using the same asset continuity, not only one 15.1-second
   performance slice.
7. Accumulated preference observations from real reviewers so the bandit learns
   taste rather than only proving its mechanics.

## Original opportunities

### Semantic ink

Make line behavior part of the storytelling grammar. Stable dark ink marks
present reality; softened broken ink marks memory; line density collapses at a
moment of moral clarity; prop-contact lines strengthen exactly when a gesture
lands. These changes are authored from story beats and baked in object space,
so they remain coherent.

### Performance contracts as reusable acting intelligence

Store a performance as intent-level events (reconsider, conceal, notice,
soften, settle), each expanding into gaze, face, torso, hands, props, timing,
and line/shade emphasis. This creates a reusable acting agent without allowing
it to rewrite dialogue or identity.

### Render-evidence flywheel

Every promoted frame sequence becomes training evidence: profile, shot context,
objective metrics, reviewer comparison, render time, and final disposition.
The contextual bandit then spends future free render time on the most
informative experiment rather than brute-forcing a giant parameter grid.

## Information needed for the next learning cycle

- Pairwise preference choices between two contact sheets or short temporal gates.
- A 1-5 review for identity, acting clarity, line quality, palette, staging, and
  emotional truth.
- A small set of "never lose this" canonical frames for June's face, silhouette,
  workwear, mug, and ledger.
- Target platform/aspect priorities and whether dialogue-first shorts or longer
  multi-shot stories matter most.
- The next approved script and final recorded voice before animation begins.

The system can proceed without paid services. What it cannot manufacture by
itself is taste evidence; reviewer choices are the signal that turns a safe
experiment engine into a personalized cartoon studio.
