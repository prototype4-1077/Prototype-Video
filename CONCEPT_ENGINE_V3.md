# Concept Engine v3 — Helpful Editorial Intelligence

v1 knew the channel's conceptual DNA and frontier.  
v2 connected concepts to reach, retention, comments and production rules.  
v3 adds the missing layer: **choosing and measuring work by the capacity it
strengthens in the viewer—not by agreement, persuasion or reach alone.**

The governing sentence is:

> Help a person examine their own experience and beliefs, then leave them more
> able to think without us.

Influence may occur. It is a consequence to handle responsibly, **not an
optimization target**.

---

## What the review found in v2

Claude's v2 changes created a strong foundation:

- `catalog.json` joined concept DNA to published performance.
- `intelligence.py` introduced explore/exploit steering.
- `comment_mining.py` brought audience response into the loop.
- `craft_ledger.json` preserved hard-won production knowledge.
- `ab_experiments.json` made structure testable.
- `invitation.py` created the first non-video help container.
- The written guardrail clearly rejected persuasion and dependence.

Three important gaps remained:

1. **The selector described conceptual nearness but selected the first unused
   frontier item.** It needed a real concept graph.
2. **Tiny samples were described as proven lanes.** It needed confidence
   shrinkage, sample labels and a much smaller performance weight.
3. **The influence ethic lived mainly in prose.** It needed machine-readable
   constraints, executable review and metrics that distinguish reflection from
   agreement.

v3 closes those gaps.

---

## The v3 architecture

### 1. The constitution — `concept/constitution.json`

The mission is now machine-readable.

Allowed optimization targets:

- clarity
- curiosity
- belief analysis
- reflection
- application
- agency
- grounded wonder
- truthful retention

Prohibited optimization targets:

- persuasion
- belief installation
- dependence
- fear arousal
- identity pressure
- false certainty
- manufactured urgency
- confusion disguised as mystery

The constitution also marks high-care contexts such as derealization,
dissociation, psychosis, trauma, grief, recovery, medical symptoms and minors.

### 2. The concept graph — `concept/concept_graph.json`

The frontier is no longer a flat idea list. Each frontier concept connects to:

- channel pillars and weighted affinities
- audience-state hypotheses
- real human situations
- signal terms found in comments
- the desired movement
- practical tests
- forms of help
- evidence boundaries
- risks and mitigations
- narration and hook options
- production grammar
- transformation formats

This allows the system to calculate actual conceptual fit instead of claiming
that the first unused item is "nearest."

### 3. Audience-state map — `concept/audience_states.json`

Audience states are editorial hypotheses, **not diagnoses**. They describe a
responsible movement such as:

- forecast → bodily curiosity
- verdict → hypothesis
- mind-reading → checking
- fixed identity → revisable story
- cosmic abstraction → ordinary grounding
- passivity → one proportionate action

The engine chooses a capacity to strengthen, not a belief to install.

### 4. Video genome — `concept/video_genome.schema.json`

Every published piece can grow from basic DNA into a complete genome:

- pillars, frontier, narration, hook and series
- human problem and audience state
- desired movement
- science fidelity and mechanism
- ruling metaphor and emotional arc
- grounding and invitation type
- visual ratios and moving subjects
- predicted and actual outcomes

The schema is incremental so old catalog entries remain valid while new videos
can become richer learning records.

### 5. Multi-objective selector — `concept/intelligence.py`

The next video is no longer chosen primarily from reach × retention.

The v3 score is:

- **20% autonomy and safety**
- **18% help potential**
- **14% audience need**
- **12% science integrity**
- **10% conceptual freshness**
- **10% sequence value**
- **6% production potential**
- **5% channel development**
- **5% performance fit**

Attention can break a tie. It cannot overrule the constitution.

Performance lanes use confidence shrinkage toward the channel mean. Every lane
is labeled `early signal`, `developing` or `repeatable signal` with its sample
count. One breakout can no longer silently become a universal formula.

The selector returns three different calls:

1. best next video
2. best experimental bet
3. best evergreen/help-oriented piece

James remains the chooser. The engine exposes its reasoning.

### 6. Decision brief — `concept/decision_brief.py`

Before scriptwriting, the engine produces:

- why now
- viewer-state hypothesis
- desired movement
- hook, mechanism and ruling metaphor
- science ledger: established, emerging, metaphor and unknown
- evidence boundary
- emotional arc and grounding
- visual grammar
- practical test
- transformation ladder
- success hypothesis
- influence review
- alternative concepts

Outputs:

- `concept/LATEST_DECISION_BRIEF.json`
- `concept/LATEST_DECISION_BRIEF.md`

### 7. Executable influence guard — `concept/influence_guard.py`

The guard returns:

- `PASS`
- `REVIEW`
- `BLOCK`

It checks for:

- missing science fidelity
- missing evidence boundary
- missing grounding
- missing open invitation
- prohibited optimization targets
- verdict installation
- guru or dependence language
- fear leverage
- manufactured urgency
- medical overclaim
- identity pressure
- high-care topics without mitigation

It is explainable and intentionally limited. It does not replace James's
judgment; it makes hidden risks visible before publishing.

### 8. Audience signal, not audience command — `concept/comment_mining.py`

The comment miner now separates:

- resonance
- reflection
- application
- curiosity
- constructive disagreement
- confusion
- requests
- misinterpretation
- certainty transfer
- distress
- dependence
- agency

Agreement alone is not treated as helpfulness.

It uses recent comments rather than YouTube's relevance ranking, stores no author
identity, minimizes excerpts and labels its output a low-confidence keyword
proxy.

### 9. Impact ledger — `concept/impact.py` + `concept/impact_ledger.json`

Each video records:

- views, average view duration and retention
- belief-analysis-yield proxy
- autonomy-risk proxy
- helpfulness proxy
- James's manual scene approvals, rejections and reasons
- predicted outcome
- actual postmortem
- confidence

James's explicit scene survey remains higher-trust evidence than an automated
comment cue.

### 10. Ethical A/B testing — `concept/ab_experiments.json`

Experiments may test truthful presentation, not manipulation.

Never A/B:

- fear
- identity threat
- false certainty
- dependence
- unlabelled science
- confusion or withheld context

A retention winner can be vetoed by distress, misinterpretation or dependence.
One experiment becomes contextual evidence; it does not retire a pattern
globally. A result must repeat in a second concept before becoming a high-weight
craft rule.

### 11. Transformation ladder — `concept/transformations.json`

A concept can move through:

1. notice — short video
2. understand — long form or podcast
3. test — micro-experiment or belief examiner
4. reflect — journal card or email
5. relate — conversation prompt
6. practice — non-clinical grounding audio
7. share — moderated community prompt
8. teach — educator discussion card

Each container has an explicit boundary. The method can expand without becoming
therapy, doctrine or a guru system.

---

## The seven internal minds

The data model now supports seven distinct reviews:

1. **Anthropologist:** What are people wrestling with?
2. **Scientist:** What is supported, uncertain or overstated?
3. **Philosopher:** What belief-making process is being examined?
4. **Showrunner:** What belongs next in the channel sequence?
5. **Visual Director:** Can the mechanism become alive, varied motion?
6. **Skeptic:** What could manipulate, destabilize or collapse under scrutiny?
7. **Translator:** Where can the same concept become practical help?

Their disagreement is useful. No single score is allowed to disappear it.

---

## Nightly learning loop

The analytics workflow now runs:

```bash
python3 -m unittest concept/test_concept_engine.py
python3 pipeline/analytics_sync.py
python3 concept/comment_mining.py
python3 concept/impact.py
python3 concept/intelligence.py > concept/INTELLIGENCE_REPORT.md
python3 concept/decision_brief.py
python3 concept/influence_guard.py concept/LATEST_DECISION_BRIEF.json
```

The committed state includes the audience signal, impact ledger, intelligence
report and latest decision brief.

---

## Metric hierarchy

1. **Constitution:** Did the piece preserve autonomy, fidelity and grounding?
2. **Help:** Did it strengthen reflection, application or honest questioning?
3. **Understanding:** Did confusion and misinterpretation remain proportionate?
4. **Craft:** Did the hook, mechanism, turn and visual grammar work?
5. **Attention:** Did people stay and share?
6. **Agreement:** Recorded only as context; never treated as the goal.

The deepest success metric remains:

> Did someone examine a belief they had never questioned—and walk away more
> their own?
