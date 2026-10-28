# Collaboration Protocol: Claude <-> GPT

Two collaborators, one repository. At session start, read the newest James
verdict, GPT pickup notes and Claude review in `collab/`. Current pickup:
`CLAUDE_HANDOFF_2026-10-28.md`. Later human feedback takes precedence over
older recommendations and reviews.

## Current roles and access

- GPT builds reversible experiments on
  `agent/phase42-human-rejected-gates-repair-v1`, not `main`.
- Claude initially reviews actual rendered pixels and proposes narrow VFX /
  animation experiments. Local Claude Code is installed and reports a saved
  Claude subscription login, but the first review request on 2026-10-28 was
  rejected with HTTP 401, "OAuth access token is invalid." James must sign
  in again before reviews can run. No Claude review has been produced by
  this reconnection attempt. James confirmed extra usage / usage credits
  are off. Do not enable them or use API billing.
- The repository remains the durable meeting room. Actual Claude-authored
  reviews use `CLAUDE_REVIEW_*.md`; GPT replies use `GPT_NOTES_*.md`. Label
  authorship accurately. An OpenAI helper is not Claude.
- Start Claude with read-only file tools and no external connectors, shell,
  edits or rendering. Any later implementation gets an isolated file scope;
  do not run concurrent writers over the same renderer or working tree.
- Stop at subscription limits. Do not buy credits, add API keys, alter account
  access, install an integration, or enable a legacy paid workflow.

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
