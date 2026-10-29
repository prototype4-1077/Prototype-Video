# Pickup — 2026-10-29 — provisional pass; source-built working model implementation

James answered **"Both mouth and hand pass"** and clarified **"Lets pass them
for now because we have to move on. We will come back to it once we have a
working model."** See `JAMES_VERDICT_2026-10-29b.md`. Freeze those repairs for
the prototype. Stop more mouth/hand polishing, unchanged A/Bs and repeated
taste questions. The full competitive-cartoon goal is not complete.

New entry: `pipeline/cartoon_working_model.py`; Windows launcher:
`Run June Prototype.cmd`; run guide: `docs/JUNE_WORKING_MODEL.md`.
It reuses the existing complete-scene builder/encoder/media audits with a
scoped, exception-restored frame-source/output-name injection. Historical
renderer files and reports remain unchanged. New provisional component
binding is `concept/characters/june_oxley_working_model_component_acceptance_v1.json`.
No output on main, no merge, no new credentials/API billing/cloud service.

The source-opening helper implemented by one scoped OpenAI agent is
`pipeline/cartoon_source_opening.py`. It reuses `_prepare_pour` and the
existing pour compositor, not a new renderer. Pins canonical JSON, LF source
and exact art bytes; strict contact/clock gates remain. All75 actual source
F112-F186 -> outputF001-F075 frames rebuilt and matched the published RGB
inventory exactly. Seven runtime art assets / 16 source/reference PNGs and
21 unique dependency paths are tracked. Audit + three samples are local at
`../../outputs/edit/phase42-source-opening-build-v1/`; audit SHA256
`9273aac16cacb86433bf73f366eb281d15708be773b0b4cf82571115ac074728`.

Opening tests passed 11/11. The first combined orchestration test run found
a mock-fixture mistake (SimpleNamespace passed to dataclasses.replace);
changed only that fixture to a dataclass. The next17 tests passed. One
additional acceptance-file-drift test was then added; all18 tests passed
in8.506s and the local no-render primary-input check passed.
No prototype movie has yet been rendered by this implementation checkpoint.

## Next exact step

1. Current18 source/entry tests and no-render `--check` have passed.
2. Verify the new source/helper code and component binding are committed.
   Create an isolated tracked-file snapshot of that commit with no copied
   external prior-render caches; this is not a new managed worktree/branch.
3. From that clean source snapshot, run the full working-model command once
   into a NEW folder under `d/outputs/edit/`. Capture the actual exec handle;
   never infer a live render from an output directory or lock file.
4. Verify all303 final frames/audio/clocks, the two existing cuts and later
   mouth-to-close-up transition. Publish the completed movie/report only
   after actual success. Do not reopen provisional mouth/hand polish.

Runtime as tested: Python3.11.3, Pillow12.2.0, NumPy2.4.4,
opencv-python-headless5.0.0.93; FFmpeg/FFprobe local. The full source route
needs no API keys/network and no old external scene cache; existing tracked
historical provenance assets remain inputs to the inherited strict facial
asset validation. Its newly generated RGB cache is an output only.

Scope limitation: `_prepare_pour` cannot return partially allocated assets
if it fails before returning; the adapter closes all assets it receives on
normal end, early close and failures without editing the locked preparer.
This is one authored10.1-second2.5D scene, not an episode/3D/general-script
engine. Source packaging/whole-film run still needs the actual clean-snapshot
verification above. Keep the five-hour automation paused unless James asks.
