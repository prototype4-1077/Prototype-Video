# Collaboration Protocol: Claude <-> GPT

Two collaborators, one repository. At session start, read the newest James
verdict, GPT pickup notes and Claude review in `collab/`. Current pickup:
`GPT_NOTES_2026-10-29a.md`; access setup is in `CLAUDE_HANDOFF_2026-10-28.md`.
James resumed interactive work on October 29; the five-hour automation is
still paused. The new mouth/hand A/B awaits human motion review. Later human feedback takes precedence over
older recommendations and reviews.

## Current roles and access

- GPT builds reversible experiments on
  `agent/phase42-human-rejected-gates-repair-v1`, not `main`.
- Claude initially reviews actual rendered pixels and proposes narrow VFX /
  animation experiments. Local Claude Code access is now verified by an
  actual review: `CLAUDE_REVIEW_2026-10-28_STANDARD_CONTEXT.md`, with receipt
  metadata in `CLAUDE_ACCESS_2026-10-28.json`. After James's sign-in, an
  extended-context request stopped on HTTP 429 (usage credits required).
  A supported per-launch `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` setting allowed
  the review through the existing Pro subscription at 200K context using
  Claude Sonnet 4.6. Earlier failures remain recorded, not overwritten.
  James confirmed extra usage / usage credits are off. Keep them off;
  do not use API billing. Never treat the CLI token-cost estimate as a
  billing receipt. No global account/model/billing settings were changed.
- The repository remains the durable meeting room. Actual Claude-authored
  reviews use `CLAUDE_REVIEW_*.md`; GPT replies use `GPT_NOTES_*.md`. Label
  authorship accurately. An OpenAI helper is not Claude.
- Start Claude with read-only file tools and no external connectors, shell,
  edits or rendering. Any later implementation gets an isolated file scope;
  do not run concurrent writers over the same renderer or working tree.
- Stop at subscription limits. Do not buy credits, add API keys, alter account
  access, install an integration, or enable a legacy paid workflow.
- Use standard context for these bounded reviews, and invoke Claude only
  for a new reviewable proof or James's request, not unchanged wakeups.
  Local review access does not verify a separate Claude scheduled task's
  GitHub attachment or give Claude shell/write/push access in this mode.

## Evidence and decision rules

Reviews cite exact files, frame numbers and concrete observations. Separate
pixels actually inspected from code/report inference and from motion/audio
that could not be played. A contact sheet cannot establish sustained acting
or lip-sync quality. Historical working CI is not proof CI works today.

Disagreements get a bounded experiment, not an argument. James arbitrates
taste. Preserve rejected and accepted artifacts; never overwrite them to
make a test pass. Passing tests or a Claude recommendation does not grant
human acceptance, a production promotion, an encode or a main-branch merge.

Current transitions, blink v3 and recorded-Foley v3 are accepted. The mouth
and hand near the end remain open. Do not reopen passed gates without new
human feedback. Notify James for meaningful findings or reviewable proofs,
not unchanged polling or unattended rerenders.

Latest actual review: `CLAUDE_REVIEW_2026-10-29_MOUTH_HAND_AB_V1.md`. Its
claim that F067 has no closed mouth is contradicted by the actual pixels
and cue record (A -> X, blend 1, X weight 1, cavity area 0). Read the builder
correction in the current pickup before proposing another closure study.
Closure timing, lip/beard-edge continuity and hand naturalness still require
James's normal-speed judgment; neither the corrected fact nor tests approve
the complete performance.
