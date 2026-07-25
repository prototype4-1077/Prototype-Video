# The Concept Engine — a thinktank for the channel

A living system for generating the channel's best material: it reads the patterns
across everything we've written, checks them against what science actually says,
surfaces concepts we haven't touched, and — every day — hands us one fresh thread
to pull. It exists to help viewers *think*, not to tell them what to think.

Lives in the repo so both Claude and ChatGPT can draw from it. Data-grounded:
built from a mine of 67 scripts / ~25,600 words (2026-07).

---

## The purpose (the ethos — read this first)
James's charge: *"not to lead but to motivate the love of expression and the
importance of belief analysis."* Five principles govern everything below:

1. **The Invitation, not the Instruction.** Every piece ends on a question or a
   test handed to the viewer — never a decree. We open doors; we don't push people
   through them.
2. **Belief analysis is the product.** The goal isn't for viewers to adopt our
   beliefs — it's to give them tools to examine their own (coherence, outside
   evidence, the window vs. the mirror). We teach the test, not the answer.
3. **Science fidelity.** Metaphor is welcome and is labeled as metaphor. We never
   smuggle speculation in as established fact. Each frontier concept carries a
   fidelity tag: `established` / `emerging` / `metaphor`.
4. **Grounding.** Every flight lands back in the room, the body, the ordinary.
   This is the channel's signature (273 corpus mentions, the #1 thread) AND its
   psychological safety rail — it keeps wonder from tipping into derealization.
5. **Wonder over dread.** The turn is always toward agency and love, never
   nihilism. The scary reading gets reframed into an empowering one.

---

## What's inside
- **`concept/patterns.json`** — the data-mined pattern map: the 11 pillars of the
  channel's conceptual DNA (weighted by real corpus frequency) + the recurring
  structural signatures. This is *what we already are*.
- **`concept/frontier.json`** — 12 (and growing) science-grounded concepts we
  haven't made yet, each with hook, ruling metaphor, the turn, and the invitation.
  This is *where we can go*.
- **`concept/daily_brief.py`** — the daily draw. Deterministic by date; each day
  it surfaces ONE angle (an untouched frontier concept, or a cross-pollination of
  two pillars) as a ready-to-develop spark. Logs to `concept/BRIEF_LOG.md`.
- **`concept/mine_corpus.py`** — re-mines the corpus to refresh the pillar weights
  as new scripts are written (run it after each batch).
- **`concept/characters/`** — canonical character bibles for recurring on-channel
  voices. Character scripts must load the named profile before writing or rendering
  so voice, ethics, appearance, world continuity, and visual grammar remain stable.

---

## The 11 pillars (mined, weighted)
1. **The ordinary / grounding** (273) — the return to room, body, breath.
2. **Self & identity as constructed** (141) — you are a role, not a thing.
3. **Belief analysis / how you know** (134) — coherence vs. evidence.
4. **Attention as the instrument** (124) — what you aim at renders.
5. **The lens / never reality raw** (113) — window, mirror, map, veil.
6. **Memory as construction** (102) — recall rewrites; memory is an artist.
7. **Prediction & the constructed 'now'** (73) — perception runs behind.
8. **Emotion, love, and the turn** (72) — toward agency, never nihilism.
9. **Recursion & self-reference** (66) — the eye can't see itself.
10. **Mind as machine** (62) — the reality-machine frame.
11. **Threshold / dissolution** (29) — the DMT lane; newest, highest voltage.

Where science backs each pillar (the integrity map): mediation & prediction ↔
predictive processing / active inference; memory ↔ reconsolidation &
constructive memory; attention & render distance ↔ change/inattentional
blindness, saccadic suppression; self ↔ narrative-self, split-brain interpreter;
threshold ↔ entropic-brain / relaxed-priors. Full science notes live per-concept
in `frontier.json`.

---

## How to use it daily
**To spark a new script:**
```
python3 concept/daily_brief.py            # today's draw
python3 concept/daily_brief.py 2026-08-01 # a specific day
```
Take the hook + ruling metaphor + the turn + the invitation, and develop it into a
script in the house voice. The brief already enforces the ethos (ends on an
invitation, honors a structural signature, lands in the ordinary).

### Script-source precedence
A complete script supplied by James is authoritative. Preserve its narration,
structure, and intended performance unless he explicitly asks for rewriting,
restructuring, or a delivery pass. Never silently force a supplied script into the
fallback template below. Delivery metadata may be added only when it does not alter
the spoken words and the request permits it. An attached or pasted full script also
takes precedence over a concept brief, outline, house template, or automatic role
inference.

### Default Liam script template — only when no complete script is supplied
When James provides an idea, concept, notes, or a request to build without supplying
a complete script, write approximately 24 short scenes and 330–340 spoken words as
one thought unfolding beside the viewer. Use one ruling metaphor throughout and
shape the prose so the performance works even with every audio tag removed.

Preferred arc:
1. **Scenes 1–2 — Hook:** one-breath, concrete, surprising; curious and slightly brisk.
2. **Scenes 3–5 — Recognition/setup:** state the viewer's ordinary assumption fairly.
3. **Scenes 6–7 — Comic pressure release:** humor grows from the ruling metaphor;
   laugh with the viewer, never at them.
4. **Scenes 8–12 — Mechanism:** temporarily reduce poetry; explain one causal step at
   a time and label the science `established`, `emerging`, or `metaphor`.
5. **Scenes 13–16 — Turn:** reinterpret what the mechanism means personally; do not
   merely repeat the claim.
6. **Scenes 17–18 — Knife line:** one or two short, whisperable sentences; no joke or
   technical language immediately after.
7. **Scenes 19–20 — Compassionate release:** restore normal warmth, remove shame, and
   turn toward agency without declaring an answer for the viewer.
8. **Scenes 21–22 — Grounding:** return to the room, body, hands, breath, or an
   ordinary object using simple concrete language.
9. **Scenes 23–24 — Invitation:** end with one genuinely open, ordinary-life test or
   question; do not whisper it by default and do not answer it.

Writing preferences:
- Write in speakable breath groups; avoid stacked abstract nouns.
- Vary sentence length so emphasis exists before tags are added.
- Put important words near phrase endings.
- Use serious setup → absurd extension → clean exit for humor.
- Build pauses at real thought boundaries, not every visual cut.
- Keep reactions sparse: amused delivery is preferred over audible laughter;
  chuckles belong after a payoff.
- The mechanism must become clearer than the poetry.
- Restore warmth after any whisper.
- A script should still sound natural when all delivery metadata is removed.

Scene delivery metadata should describe the intention already present in the prose,
not compensate for weak writing. Use `delivery_role` values `hook`, `setup`,
`comic`, `mechanism`, `turn`, `knife`, `grounding`, and `invitation`; add
`pause_before`, `reaction`, or `is_knife_line` only when the meaning requires it.
Explicit `audio_tags` remain the highest-priority manual override.

**For a recurring character script:**
1. Load the character JSON and companion bible under `concept/characters/`.
2. Preserve the character's exact voice provider/name and do not silently substitute
   the normal Liam voice.
3. Keep the channel ethos and science-fidelity boundary active inside the character's
   own language.
4. Treat the character's appearance, town, ethics, title system, and recurring props
   as continuity—not disposable prompt decoration.

The canonical June Oxley profile is:
- `concept/characters/june_oxley.json`
- `concept/characters/JUNE_OXLEY.md`

**To keep the engine current:**
- After writing new videos, run `python3 concept/mine_corpus.py` and update the
  pillar weights in `patterns.json`.
- When you meet a new idea in the wild (a paper, a comment, a shower thought), add
  it to `frontier.json` with its fidelity tag. The engine gets smarter the more we
  feed it.

**The gaps worth mining next** (under-served but on-brand): the DMT/threshold lane
is smallest (29) yet highest-voltage — `entropic_brain` and `body_ownership` bridge
it to real science. `constructed_emotion` and `placebo_belief` push the
belief-analysis pillar into the body, where it has teeth.

---

## The one-line summary
We already know what we are (the pillars). This engine tells us, every morning,
one true and untouched place we could go next — and reminds us to hand the viewer
the test instead of the answer.

---

## Growing the think tank (how BOTH Claude and ChatGPT contribute)
The think tank is a living, shared brain. **`concept/frontier.json` in this repo is
the single source of truth.** Anyone with repo write access can grow it:

**To add a new concept** — append an object to the `frontier` array in
`concept/frontier.json` with these fields, then commit to `main`:
```json
{"id":"snake_case","title":"Punchy Title","fidelity":"established|emerging|metaphor",
 "science":"one honest sentence of the actual science, named",
 "hook":"the disarming opening line","metaphor":"the one ruling image",
 "turn":"the empowering reframe","invitation":"the question handed to the viewer"}
```
Rules: fidelity must be truthful (never tag speculation as `established`); the
invitation must be a question, not a decree; keep it on-ethos (wonder over dread,
belief-analysis, grounding).

**To refresh the pillar weights** after new videos ship: run
`python3 concept/mine_corpus.py` and update the weights in `concept/patterns.json`.

**Access map:**
- **Claude** — full write (clone + commit). Builds concepts, scripts, and hero art.
- **ChatGPT (Codex Connector)** — read/write to code, so it CAN append a concept to
  `frontier.json` and commit it. It reads the live file for the current bank.
- **The ChatGPT Project's uploaded copy** is a static snapshot — re-upload it after
  the repo file changes to keep the Project's baked-in knowledge current (or rely on
  the connector reading the live repo version, which the Project instructions do).

So: to *update the think tank*, write to `concept/frontier.json` in the repo. That is
the canonical act, and both agents can do it.
