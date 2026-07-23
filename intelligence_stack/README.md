# Intelligence + Render Reliability Stack

This stack connects four open-source capabilities without replacing the existing
Concept Engine, render governor, or James's final judgment.

## Governing flow

```text
Agent Reach capability health + public collectors
                    ↓
      provenance-first signal ledger
                    ↓
       Concept Engine editorial review
                    ↓
 Promptfoo lower-model competency gate
                    ↓
  visual-risk routing + ComfyUI templates
                    ↓
       render + James scene survey
                    ↓
   FiftyOne-compatible visual memory
```

## 1. Agent Reach — external sensing

`reach/collect.py` treats Agent Reach as the capability layer it is. It records
`agent-reach doctor` output when installed, then uses the healthy upstream tools
available in the environment. Public, zero-cookie routes are enabled by default:

- GitHub release/activity signals through `gh`
- YouTube search metadata through `yt-dlp`
- RSS/Atom feeds through the Python standard library
- pre-collected JSONL from authenticated local collectors

Cookie-backed channels are never enabled in GitHub-hosted runners. Run those on a
trusted local or self-hosted machine with dedicated secondary accounts, then pass
the minimized JSONL records to `--ingest`.

Outputs are signals, not editorial commands:

- `concept/external_signals/LATEST.json`
- `concept/external_signals/DAILY_SIGNAL_BRIEF.md`

## 2. Promptfoo — lower-model competency gate

`promptfoo/` contains a model-neutral evaluation suite for script planning and
visual planning. The default provider is an offline fixture provider, so CI can
validate the evaluation contract without API keys. Live providers can be supplied
through environment variables or a local provider wrapper.

The suite checks:

- valid structured JSON
- 18–26 scenes and 300–400 words
- one ruling metaphor
- science fidelity and evidence boundary
- grounding near the end
- final open invitation
- human-heavy imagery under half
- anatomy/contact-risk rules
- supplied narration remains verbatim during revisions

A weaker model is not promoted to production merely because it completes the task;
it must pass the same competency suite repeatedly.

## 3. ComfyUI — constrained hero execution

`comfy/` contains API-format workflow templates and a renderer adapter. Agents do
not invent arbitrary node graphs. They select a versioned workflow and fill a
small scene contract:

- one subject
- one action
- one impossible element
- explicit anatomy/object count
- explicit negative constraints
- deterministic seed

`pipeline/visual_risk.py` scores script scenes before generation. High-risk scenes
must route to stock, a non-human geometric metaphor, or a constrained ComfyUI
workflow. It does not silently rewrite narration.

## 4. FiftyOne — visual memory

`fiftyone/export_visual_memory.py` converts scene scripts, generated assets,
James's scene feedback, and render metadata into a FiftyOne-compatible JSONL
manifest. FiftyOne itself is optional in CI; the manifest remains useful without
installing the UI.

The visual record preserves:

- slug and scene index
- narration and visual prompt
- provider/model/workflow/seed when known
- asset path and hash
- approved/revise decision
- James's comment
- deformation/risk tags
- retention fields when available

The purpose is not to train blindly on approvals. It is to make visual evidence
queryable: which models deform hands, which compositions fail, which metaphors are
clear, and which workflows repeatedly earn approval.

## Activation

- `intelligence-stack-ci.yml` validates the whole stack on pull requests.
- `signal-radar.yml` can refresh public external signals on a schedule or manually.
- `visual-memory.yml` rebuilds the visual manifest after scene feedback changes.
- Live Promptfoo evaluations and ComfyUI generation are manual/secret-gated.

No component may merge, publish, or create a render request on its own.