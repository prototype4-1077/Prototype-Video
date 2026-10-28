# Pickup — 2026-10-28 — Claude reconnection prepared; human sign-in needed

James requested Claude help with visual effects using the earlier setup.
Reused `collab/PROTOCOL.md`; added root `CLAUDE.md` and current
`collab/CLAUDE_HANDOFF_2026-10-28.md`. No new service, repository visibility
change, GitHub collaborator invitation, API key, CI dispatch or main change.

## Connection evidence and blocker

- Local Claude Code 2.1.126 is installed. Its auth-status command reports
  a saved first-party Claude Pro subscription login, not an API key.
- James explicitly confirmed extra usage / usage credits are off.
- One actual review request used only Read/Glob/Grep, `dontAsk` permission
  mode, hooks disabled, no MCP servers, no session persistence and a
  task-scoped extra directory for the local hand proof. No shell/edit/agent
  tools were exposed to Claude. Existing configured model was not changed.
- Actual result: **HTTP 401, "OAuth access token is invalid."** Zero
  input/output tokens, zero API processing time and reported cost $0.
  This is a failed connection, **not a Claude visual review**.
- Stop here until James signs in again to Claude Code. Do not try private
  token endpoints, inspect credentials, log him out, buy credits or switch
  billing providers. Never publish auth account identifiers.

Local launch settings remain outside the checkout at
`../../outputs/edit/phase42-claude-review-v1/`. They contain no credentials.
The active process already exited; there is no running Claude job to poll.

## Latest artistic decision (supersedes older pickup proposals)

`JAMES_VERDICT_2026-10-28c.md` records that transitions pass and the mouth and
late hand need work. Keep the 303-frame edit, cuts, accepted eye v3 and exact
recorded-Foley v3 fixed. Do not extend the recovery or change head/shoulders.

The hand helper finished one reversible local candidate and ten reported
passing tests; its files/proofs remain local drafts awaiting root/Claude
review, not promoted code. Do not call that OpenAI helper Claude. The mouth
inspection found an unimplemented semantic mismatch between raw Rhubarb
labels and internal mouth artwork; details and primary-source reference are
in the handoff. Neither finding is a human naturalness verdict.

## Next exact step

After James restores Claude Code sign-in, run the bounded read-only review
from the handoff. Inspect actual mouth pose and hand keyframe PNGs plus the
full-scene contact sheet. Explicitly report if normal-speed playback is not
available. Persist only an actual Claude-authored review under
`CLAUDE_REVIEW_*.md`, then respond with builder notes. Do not rerender the
unchanged full scene or reopen passed gates while waiting.

This publication contains documentation and the new human verdict only.
Local hand code/tests/proofs and the deferred historical source archive are
not implicitly approved, staged or published. The full scene remains
unaccepted for production.
