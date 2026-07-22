# Concept Engine v2 — the Intelligence Layer

The v1 think tank *draws* concepts. v2 makes it *smart*: it learns what to make
from what actually worked, learns how to make it better from how viewers behaved,
and learns how to carry the same method into other formats and forms of help.

Three tiers. Tier 1 is built and running. Tiers 2–3 are the roadmap, with the first
pieces of each already in place.

---

## TIER 1 — Know what to make (the feedback loop) ✅ BUILT
The gap in v1: concepts were drawn blind, disconnected from performance. v2 closes it.

- **`concept/catalog.json`** tags every published video with its concept DNA:
  pillar(s), the frontier concept it used, narration style (guided-2nd / testimony-1st
  / documentary-3rd / teaching), hook type (question / confession / plunge /
  demonstration), series, format.
- **`concept/intelligence.py`** joins that DNA with realized performance
  (`build/<slug>/yt_stats.json` + retention verdicts, refreshed nightly by the
  analytics sync) and computes a blended **reach × retention** score per video, then
  ranks the winning *lanes* — which pillar, voice, and hook actually perform.
- The **daily brief now leads with a data-driven steer**: exploit the proven lane,
  and place the single highest-value NEW bet (the untouched frontier concept nearest
  the winning pillar). Explore + exploit, not random rotation.

What it already sees from 3 data points: the **machine/attention pillar in a
guided-2nd voice with a plunge hook** is the spearhead (the 832-view breakout);
**openers are make-or-break** (every tracked video bleeds viewers in its first
scenes); and the recommended next bet is *"Your Feelings Are Forecasts."*
Run: `python3 concept/intelligence.py`. It gets smarter every night automatically.

---

## TIER 2 — Make them better (craft intelligence) 🔨 STARTED
Turn behavior into production rules the scriptwriter obeys.

- **From retention (done):** the "held vs. bled" scene verdicts become craft rules —
  e.g. *hook in the first 1.5s, protect the closing turn.* These feed the scriptwriter.
- **Comment mining (next):** pull YouTube/TikTok comments per video; extract what
  resonated emotionally, what confused, what viewers *asked to see next.* The audience
  is writing the roadmap in the comments — we should be reading it.
- **Structural A/B (next):** the pipeline can already cut two hooks / two openers of
  the same script. Ship both as Shorts, let retention pick the winner, bank the rule.
- **The craft ledger:** every rule learned this way accumulates in one place the
  scriptwriter reads before writing — a compounding style memory beyond taste.npz.

---

## TIER 3 — Transform into other areas of help & influence 🌱 THE FRAME-BREAK
The real asset was never "videos." It's a **validated method**: warmly showing people
the constructed nature of their own experience, and inviting them to examine their own
beliefs — always landing in the ordinary, never leading. That method is portable.

**Same method, new containers (one concept → many forms):**
- **Long-form** (10–20 min / podcast): a pillar becomes a deep episode; the Shorts
  become the trailers.
- **The daily invitation as a product:** the closing questions, distilled into a
  one-a-day email/SMS micro-practice. This *is* the belief-analysis habit, standalone.
- **A serialized book / Substack:** the 11 pillars are chapters; the corpus is drafted.
- **An interactive "belief examiner":** the crossword-test as a guided self-check web
  tool — the viewer runs the test on their own belief, in their hands, tonight.
- **Guided audio:** the grounding beats are already meditation-shaped.
- **Community:** the daily invitation as a prompt (subreddit / Discord) — belief
  analysis becomes a shared practice, not a broadcast.

**Same method, new audiences (re-voiced, never diluted):** educators (critical
thinking), grief (the memory + love pillars), recovery-adjacent and identity work for
teens — each with careful, non-clinical framing.

**The deepest transform — real help, handled with care:** the invitations already do
gentle metacognition (noticing the mind's constructions, examining beliefs, values
reflection). This is an *on-ramp to self-reflection,* not therapy. Which is exactly
why the ethos becomes a **hard constraint** as we scale influence, not a nicety.

---

## THE GUARDRAIL (load-bearing, not optional)
Influence is power, and James named the line precisely: *not to lead, but to motivate
the love of expression and the importance of belief analysis.* As the think tank gets
more intelligent and more far-reaching, it must obey:

1. **Hand the test, never the verdict.** We teach people to examine their own beliefs;
   we never install ours. Intelligence that optimizes for engagement must never be
   allowed to optimize for *persuasion* — that would betray the whole project.
2. **Ground and protect.** Every piece returns to the ordinary and the body. This keeps
   wonder from tipping into derealization — a safety feature, especially at scale.
3. **Science fidelity, always labeled.** More reach = more responsibility not to
   mislead. Metaphor stays labeled as metaphor.
4. **Wonder over dread; agency over dependence.** Success is a viewer who thinks *more
   freely* — not one who needs us to think for them.

The v2 metric of success is not just views. It is: **did this help someone examine a
belief they'd never questioned — and walk away more their own?**

---

## What's live today vs. next
- **Live:** `concept/catalog.json`, `concept/intelligence.py`, the daily brief's
  data-driven steer, the retention craft rules. Growing nightly.
- **Next, on your word:** comment mining, structural A/B, the craft ledger (Tier 2);
  then pick ONE Tier-3 container to prototype (my pick: the daily-invitation product —
  smallest build, purest expression of the mission).
