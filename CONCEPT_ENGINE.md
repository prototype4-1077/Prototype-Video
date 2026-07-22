# The Concept Engine

A living think tank for the channel. It studies the complete body of work,
separates frequency from truth, checks scientific claims against sources,
surfaces patterns and tensions we did not pre-name, and produces one daily
thread worth developing. Its purpose is to help viewers examine beliefs—not to
deliver beliefs for them.

## Governing ethos

1. **Invitation, not instruction.** End with a question or test, never a decree.
2. **Belief analysis is the product.** Teach ways to examine a belief: evidence,
   coherence, alternatives, uncertainty, and consequences.
3. **Evidence and metaphor stay visibly different.** Science may ground a piece;
   it does not certify every poetic turn that follows.
4. **Ground every flight.** Return to the room, body, relationship, or ordinary
   object. Grounding is both a house signature and a psychological safety rail.
5. **Wonder over dread.** Make room for agency and care without promising control.
6. **Frequency is not truth.** A repeated motif describes our corpus; it does not
   prove the motif is accurate, valuable, or ready to repeat.
7. **The strongest counterview belongs in the room.** A concept is not ready until
   we can state what would weaken it and whose experience is missing.

## The three integrity gates

### 1. Corpus integrity

`concept/mine_corpus.py` selects one canonical production for each normalized
title, preferring published and completed versions. It then:

- counts pillar terms on word boundaries;
- reports how many variant files were deduplicated;
- discovers recurring two- and three-word phrases that were not in the pillar
  dictionary;
- detects recurring conceptual tensions such as fixed/changing,
  evidence/belief, and alone/connected; and
- records concept coverage from scripts carrying `concept_id`.

Run a read-only report:

```text
python3 concept/mine_corpus.py
```

Refresh the checked-in snapshot:

```text
python3 concept/mine_corpus.py --write
```

`concept/patterns.json` records the method, canonical script count, word count,
duplicate-title groups, emergent phrases, tensions, and pillar weights. Counts
are descriptive signals only.

### 2. Evidence integrity

`concept/evidence.json` is the claim ledger. Each frontier concept records:

- a bounded claim the cited source can support;
- evidence status and confidence;
- source type and stable URL;
- limitations;
- the strongest counterview; and
- blind spots that deserve another discipline, culture, population, or lived
  experience.

The five scene roles are:

| Role | Meaning |
|---|---|
| `evidence` | A bounded statement supported by cited sources |
| `interpretation` | A meaning drawn from evidence, not the result itself |
| `metaphor` | An image for thinking, not a literal mechanism |
| `speculation` | A possibility whose uncertainty remains visible |
| `invitation` | A viewer question or practice, not a factual claim |

`concept/frontier.json` contains hooks, metaphors, turns, and invitations, but
defers scientific bounds and citations to the evidence ledger. A concept-level
label never automatically transfers to every sentence in a script.

### 3. Production integrity

Concept-led scripts carry a top-level `concept_id`, pacing target, and a role on
every scene. Evidence scenes cite `source_ids` from the ledger.

Before rendering:

```text
python3 concept/script_gate.py build/<slug>/script.json
```

The gate catches:

- repeated or near-duplicate narration;
- duration estimates that disagree with the stated target;
- scenes longer than 25 words;
- evidence scenes without traceable sources;
- unknown epistemic roles or source IDs;
- more than four hero stills in a concept video; and
- visual keywords that never appear in the spoken beat.

The Render workflow runs this gate automatically. It supplements—not replaces—
human scientific, editorial, accessibility, and visual review.

## Daily selection

`concept/daily_brief.py` is deterministic by date but no longer chooses an item
at random. It scores frontier concepts using:

- whether a concept-tagged script already exists;
- recent brief history and a cooldown window;
- citation readiness and evidence status;
- lower corpus coverage; and
- concept-level audience outcomes when available.

Two days emphasize evidence-ready frontier concepts; the third uses a
lower-coverage cross-pollination. Every brief includes the strongest counterview,
limits, blind spots, and sources.

Preview without changing history:

```text
python3 concept/daily_brief.py
```

Record that a brief was actually issued:

```text
python3 concept/daily_brief.py 2026-08-01 --record
```

Record later decisions separately:

```text
python3 concept/daily_brief.py 2026-08-01 \
  --concept-id body_ownership --mark selected --slug where-you-end
```

Valid marks are `selected`, `produced`, `published`, and `rejected`.
`concept/brief_history.json` distinguishes previewing an idea from choosing it.

## Learning from viewers without chasing them

Visual approvals and retention continue to train footage selection in
`pipeline/memory.json` and `pipeline/taste.npz`. When a script carries
`concept_id`, `pipeline/learn.py` also writes bounded concept-level summaries to
`concept/outcomes.json`:

- explicit human approval count;
- mean audience watch ratio;
- mean completion ratio; and
- held and bled scenes for each sample.

This lets the daily selector learn which concepts connect while keeping concept
performance separate from visual-query performance. Outcomes inform selection;
they do not decide truth. A high-retention idea still needs evidence review, and
a low-retention idea may need a better script rather than abandonment.

## The current conceptual map

The checked-in pillars describe the channel's existing center of gravity:

- the ordinary and grounding;
- self and identity as constructed;
- belief analysis and how we know;
- attention;
- mediation, lenses, and maps;
- memory;
- prediction;
- emotion, love, and the turn;
- recursion;
- mind-as-machine metaphors; and
- threshold or dissolution experiences.

The generated `emergent_phrases` and `recurring_tensions` sections are where we
look for vocabulary and conflicts the original pillar list did not anticipate.
Neither is automatically a script idea; each is an invitation to investigate.

## Review rhythm

- **After new scripts:** run the corpus miner with `--write`.
- **Before drafting from science:** review the claim ledger and open the cited
  source—not only its summary.
- **Before rendering:** run the script gate and inspect every hero frame against
  its mechanism.
- **After approval:** record the video normally; concept approval is captured for
  scripts with `concept_id`.
- **After retention arrives:** the audience learner updates visual and conceptual
  outcomes separately.
- **Quarterly:** review stale sources, contested claims, missing disciplines, and
  populations overrepresented in the source base.

## The one-line standard

Find a pattern, test its claim, name its uncertainty, include the strongest
alternative, and hand the viewer a question they can examine for themselves.
