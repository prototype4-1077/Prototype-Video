# Perpetual Frontier Loop

The Perpetual Frontier Loop is the Concept Engine's constitutional evolution laboratory. It exists to make the studio better at discovering, questioning, diversifying, testing, transferring, and forgetting without giving an automated system authority over the channel's identity or production decisions.

## The two loops

### Production loop

`Sense → Conceive → Challenge → Build → Inspect → Publish → Learn`

This is the existing video-making system: Concept Engine, visual planning, rendering, scene review, surgical revision, analytics, model evaluation, and telemetry.

### Evolution loop

`Map → Find gaps → Dream → Design experiments → Transfer → Revise models → Forget weak rules → Expand the map`

This loop does not make videos. It produces evidence-backed questions and proposals for James to choose from.

## Constitutional boundary

The laboratory may read repository evidence, write reports under `concept/evolution_state/`, construct hypotheses with alternatives and uncertainty, propose controlled experiments, create dream-only cross-pollinations, recommend provisional rule retests and retirements, and measure diversity, lineage, coherence, capability evidence, and unknown unknowns.

It may not edit `concept/frontier.json` automatically, change scripts or approved narration, create `render.request`, publish, merge, promote a model, change the permanent channel principles, or optimize only for views.

The permanent identity remains:

1. The Invitation, not the Instruction.
2. Belief analysis is the product.
3. Science fidelity.
4. Grounding.
5. Wonder over dread.
6. James retains final authority.

## What each cycle produces

### Living world model

`hypotheses.json` stores provisional claims about performance, visual reliability, and efficiency. Every hypothesis includes evidence for, evidence against, alternative explanations, confidence, learning progress, and a proposed clarifying experiment. The system says **may**, not **does**, because observational patterns are not causal proof.

### Experiment designer

`experiment_queue.json` turns high-value uncertainty into controlled tests. It specifies treatment, control, fixed factors, primary and secondary metrics, information value, stop conditions, and required human approval. The purpose is to learn why something works, not merely repeat what happened to work.

### Quality-diversity atlas

`diversity_atlas.json` preserves the best observed example in each creative region. Current dimensions include pillar, fidelity, hook, narration, human-presence band, and generation band. This prevents the recommender from collapsing into one successful format.

### Dream mode

Dream mode cross-pollinates distant pillars with mechanisms borrowed from ecology, immunology, architecture, music, law, information theory, control theory, evolution, theatre, logistics, archaeology, and cybernetics.

Dreams are always marked `dream_only`, fidelity-labeled `metaphor`, paired with an analogy warning, ended with an invitation question, and excluded from automatic production.

### Intrinsic curiosity

The curiosity queue prioritizes productive novelty using uncertainty, learning progress, future reuse, channel relevance, cost, and risk.

### Unknown-unknown detector

The loop looks for performance outliers, videos that fit no current taxonomy, uncategorized revision comments, disagreement between James's approval and audience performance, and sparse regions in the diversity atlas. The output does not invent a new category automatically. It asks whether the map is missing a dimension.

### Disagreement observatory

Candidate experiments and dreams are challenged by long-lived perspectives: scientist, mystic, skeptic, audience anthropologist, visual physicist, editor, ordinary person, archivist, and contrarian. These positions are preserved rather than averaged into a vote.

### Lineage and evolutionary value

`lineage.json` records how concepts, pillars, expedition domains, dreams, and videos are related. It also measures reproductive value: which ideas create the most useful descendants.

### Negative-space archive

`negative_space.json` preserves untouched frontier concepts, rejected scenes and comments, quality failures, dream proposals not selected, sparse creative regions, and rules awaiting retest. A rejected visual is treated as an execution failure until evidence shows the concept itself was bad. This lets future tools revisit ideas that were previously premature.

### Rule confidence, decay, and forgetting

`rule_review.json` separates constitutional rules from provisional production rules. Constitutional rules never decay. Provisional rules lose confidence when they are not reconfirmed, lose more confidence when contradicted, and move through `active`, `retest`, and `retire_candidate`. No rule is retired automatically.

### Coherence lattice

Candidate proposals are inspected across science, concept, emotion, visual legibility, timing, ethics, catalog novelty, audience invitation, operational feasibility, and channel identity. A locally beautiful idea can still be rejected as globally incoherent.

### Capability constitution

`capability_report.json` tracks evidence for abilities such as narration preservation, science boundaries, visual-risk detection, surgical revision, model challenger gates, render tracing, missing-taxonomy detection, experiment design, and cognitive diversity. A capability becomes demonstrated only when the declared repository evidence exists.

### Adjacent-world expeditions

`expedition_library.json` gives Dream Mode mechanisms and visual languages from unrelated fields, plus a warning against smuggling analogy in as science.

### Surprise budget

The portfolio reserves 70% for proven and adjacent work, 20% for uncertainty-reducing experiments, and 10% for wild frontier exploration. The wild lane cannot be removed by short-term optimization.

### Multiple possible selves

Five long-lived cognitive selves score proposals differently: Scientist Engine, Midnight Engine, Visual Engine, Frontier Engine, and Ordinary Engine. `multiple_selves.json` keeps their separate rankings and identifies crossover candidates that remain strong across all perspectives. This is cognitive biodiversity, not a vote.

## Inputs

The loop reads whatever evidence is currently available: patterns, frontier concepts, catalog DNA, scripts, YouTube statistics, scene feedback, quality reports, motion reports, OpenTelemetry summaries, and Agent Reach signal ledgers. Missing evidence is treated as missing, not silently invented.

## Commands

```bash
python3 concept/perpetual_frontier.py --root .
python3 concept/perpetual_frontier.py --root . --date 2026-08-01
python3 concept/perpetual_frontier.py --root . --json
```

## Automation

`perpetual-frontier-cycle.yml` runs weekly, manually, and when relevant evidence changes on `main`. It commits only `concept/evolution_state/**`. It does not create scripts, art, pull requests, or renders.

## The human decision

The brief ends with a question because the laboratory is itself governed by the channel's ethos:

**Which uncertainty is worth spending a real video to examine?**
