# Operational Memory Ledger

This directory is the pipeline's durable repair manual.

- `occurrences/*.json` — immutable per-preflight and per-render evidence. One file per run/incident prevents concurrent renders from fighting over one append-only file.
- `solutions.json` — curated root causes, repair actions, fix commits, verification requirements, and safe-auto-fix boundaries.
- `prevention_rules.json` — machine-readable rules enforced by `pipeline/preflight.py`.
- `incidents.json` — materialized incident clusters generated from occurrences.
- `index.json` — compact solution verification and recurrence scorecard.

## Authority boundary

The system may automatically apply only repairs explicitly marked `safe_to_auto_apply` and implemented as deterministic field normalization. It may not rewrite narration, political meaning, science claims, user-approved concepts, or visual direction. Unsafe or creative repairs block dispatch with a known solution reference.

## Lifecycle

`observed -> diagnosed -> repaired -> verification pending -> verified -> prevention rule`

A solution is curated by a human or reviewed code change. Evidence can increase or decrease its confidence, but the ledger never promotes a creative rule by itself.
