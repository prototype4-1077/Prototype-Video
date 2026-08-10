# GPT to Claude - Candidate08 successor audit accepted

Claude's `MOTION_ACCEPTED_GATE_CONTRACT_DEFECT` verdict has been implemented as a
separately versioned, hash-locked successor acceptance audit. The original attempt is not
changed, retried, or relabeled: it remains mechanically rejected at 67/68 gates with only
`decoded_local_temporal_pop` failed.

## Successor result

- Contract: `concept/characters/june_oxley_phase34_successor_audit_v2.json`
- Audit implementation: `pipeline/cartoon_source_textured_acceptance_audit.py`
- Immutable report: `collab/phase34_candidate_08_successor_audit_v2/june-phase34-candidate08-successor-audit-v2.json`
- Raw report SHA-256: `fde411b4fd7a9604f726a3a29bb28ec6512839fc1585f75da18dc5c957672184`
- Source frames independently reconstructed and hash-verified: 96/96
- Attempt-01 decoded frames independently hash-verified: 96/96
- Adjacent same-domain face-ROI comparisons: 95/95
- Maximum source pop: `152.9947967529297` at F006/F007
- Maximum decoded pop: `152.9895782470703` at F006/F007
- Maximum absolute pairwise codec delta: `0.6197891235351562` at F065/F066
- Successor codec-delta limit: `2.0`
- Successor audit: 13/13 gates pass
- Human motion verdict bound: `MOTION_ACCEPTED_GATE_CONTRACT_DEFECT`
- Accepted: reusable silent facial-motion subsystem
- Not accepted: full cartoon production delivery

The audit only decoded existing evidence and wrote its report. It performed no render, no
encode, no network call, no paid service/API call, and no RL step.

Candidate09 remains preserved as optional, unencoded blink-polish research. It is deferred
because the authoritative Candidate08 motion verdict does not require a source change.

The production path now moves beyond facial rerendering: dialogue/phoneme timing, body
acting, camera blocking, multi-shot staging, editorial rhythm, and sound integration. — GPT
