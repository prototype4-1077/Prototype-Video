# The Concept Engine — a living think tank for the channel

The Concept Engine reads the channel's conceptual history, checks ideas against
science, senses audience response, chooses responsible new directions, learns
from production and transforms strong concepts into other forms of help.

Its purpose is not to tell viewers what to think.

> It hands them a lens, an evidence boundary and a test—then returns ownership
> of the conclusion to them.

The live architecture is documented in `CONCEPT_ENGINE_V3.md`.

---

## The constitution

1. **Invitation, not instruction.** End with a viewer-owned question or test.
2. **Belief analysis is the product.** Teach the examination process, not our verdict.
3. **Science fidelity.** Label established, emerging and metaphor; say where evidence stops.
4. **Grounding.** Every flight returns to the room, body, breath or ordinary object.
5. **Wonder over dread.** Fear cannot be the lever or destination.
6. **Agency over dependence.** Success is a viewer who can think more freely without us.
7. **Influence is not an optimization target.** Optimize clarity, reflection, application and truthful retention—not persuasion.

Machine-readable source: `concept/constitution.json`.

---

## What the engine knows

### Channel memory

- `concept/patterns.json` — the 11 mined pillars and structural signatures.
- `concept/catalog.json` — published-video concept DNA.
- `concept/video_genome.schema.json` — the richer genome new records can grow into.
- `concept/craft_ledger.json` — James's rules, production evidence and confidence labels.
- `concept/impact_ledger.json` — attention, helpfulness proxies, manual feedback and postmortems.

### Frontier and context

- `concept/frontier.json` — science-grounded concepts with hook, metaphor, turn and invitation.
- `concept/concept_graph.json` — connections to pillars, situations, audience states, help modes, risks and production grammar.
- `concept/audience_states.json` — editorial state hypotheses and safe movements.
- `concept/transformations.json` — the ladder from video to test, reflection, relationship, practice and teaching.

### Intelligence and review

- `concept/intelligence.py` — confidence-aware, multi-objective selection.
- `concept/decision_brief.py` — the pre-script decision brief.
- `concept/influence_guard.py` — PASS / REVIEW / BLOCK autonomy review.
- `concept/comment_mining.py` — reflection, application, confusion and risk signals.
- `concept/impact.py` — refreshes the impact ledger.
- `concept/ab_experiments.json` — ethical experiment protocol.
- `concept/invitation.py` — one safe daily belief-analysis question.

---

## The 11 pillars

1. The ordinary / grounding
2. Self and identity as constructed
3. Belief analysis / how you know
4. Attention as the instrument
5. The lens / never reality raw
6. Memory as construction
7. Prediction and the constructed now
8. Emotion, love and the turn
9. Recursion and self-reference
10. Mind as machine / rendering engine
11. Threshold and dissolution / DMT lane

The pillars describe what the channel has become. They are not quotas and they
are not claims about ultimate reality.

---

## Daily use

### See the editorial portfolio

```bash
python3 concept/intelligence.py recommend
```

Returns:

- best next video
- best experimental bet
- best evergreen/help-oriented piece
- sample size and confidence
- influence status

### Build the decision brief

```bash
python3 concept/decision_brief.py
python3 concept/decision_brief.py --concept constructed_emotion
```

### Run the influence review

```bash
python3 concept/influence_guard.py concept/LATEST_DECISION_BRIEF.json
python3 concept/influence_guard.py --text path/to/script.txt
```

### Generate the daily invitation

```bash
python3 concept/invitation.py
```

### Validate the engine

```bash
python3 -m unittest concept/test_concept_engine.py
```

---

## How a new idea enters

Add the frontier concept to `concept/frontier.json`, then add a matching node to
`concept/concept_graph.json`.

The frontier record says what the idea is:

```json
{
  "id": "snake_case",
  "title": "Punchy title",
  "fidelity": "established|emerging|metaphor",
  "science": "one honest sentence naming the mechanism",
  "hook": "the opening line",
  "metaphor": "one ruling image",
  "turn": "the empowering reframe",
  "invitation": "the viewer-owned question"
}
```

The graph node says where it can help, where it can mislead, how it can move,
and how it can be made visually alive.

A concept is incomplete until both exist.

---

## The decision rule

The engine may recommend. James decides.

Audience requests are signals, not commands. Performance is evidence, not
authority. A viral lane is not automatically the next lane. A beautiful
metaphor is not automatically science. A retention winner is not a winner when
it increases confusion, dependence or false certainty.

The Concept Engine is intelligent only when it can correct itself without
forgetting what it is for.
