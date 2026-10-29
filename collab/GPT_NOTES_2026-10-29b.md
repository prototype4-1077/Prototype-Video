# Pickup — 2026-10-29 — complete source-built working prototype verified

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
The complete303-frame source-built movie has now succeeded; see below.

## Completed clean-source run

Implementation commit: `1ec1ce40f84f7fdec2bf21104013cc1dab114184`.
`git archive HEAD` ->577177600-byte tar (SHA256
`7cadc26e5b7cc3e5188906cdbc6e44fa3e810b7dbc3e5c38166ab25ae7a14a7e`),
extracted under `d/outputs/edit/phase42-working-model-source-verification-v1/checkout`.
No old external render cache copied. An initial PowerShell archive argument
format failed before writing the archive; the corrected explicit path worked.
The actual movie job was started once from that snapshot, exec session12947,
and completed exit0. Its full303 frames /10.1s, three shots and complete
media audit passed. Local output: `d/outputs/edit/phase42-working-model-v1/`.
No rerender, paid service, main change or new API credential.

Published copy: `collab/phase42_working_model_v1/`, including full MP4/MOV,
inventory, two reports, clean-source receipt, contact sheet, blink sequence
and credits. Per-frame references/logs/intermediates and483680509-byte
new RGB cache remain local; cache is an output only. MP4 SHA256
`e958488f8b9962c6138aa1894342483ff8d7c8f1fe5eb1bcef3e4ae7f331c61d`.
MOV SHA256 `58df922acbc0fc71fb29c881c43d177aa5d3740ae9e4ebf1a02cdccc706ce76e`.

All138 repaired comparison RGB hashes match exactly; all75 source opening
hashes match. F248 accepted full-close RGB remains155cab57...; exact full
hash is in the receipt. MOV audio is bit-exact; AAC preview SNR42.5407768dB;
all303 timestamps exact; all28 sampled PSNR checks >=40.0505421dB. Root
inspected the decoded12-frame contact sheet at both cuts and blink endpoint.
No unperformed sustained-motion/audio perception or human final approval
is claimed. The Windows launcher --check also exited0 from the source copy.
18 source/entry tests +five published no-render regression tests pass.

## Next useful increment

Do not rerender this unchanged model, reopen provisional mouth/hand polish
or request another identical taste verdict. Prove a second authored scene
through the existing engine, then expose only the minimum reusable scene
controls. First inspect the existing storyboard/shot-plan/script paths;
avoid duplicating them or importing the legacy paid pipeline. Reusing a
second scene is a stronger next test than building a UI around one fixed
scene. Broader authoring and final whole-film quality remain open.

Runtime as tested: Python3.11.3, Pillow12.2.0, NumPy2.4.4,
opencv-python-headless5.0.0.93; FFmpeg/FFprobe local. The full source route
needs no API keys/network and no old external scene cache; existing tracked
historical provenance assets remain inputs to the inherited strict facial
asset validation. Its newly generated RGB cache is an output only.

Scope limitation: `_prepare_pour` cannot return partially allocated assets
if it fails before returning; the adapter closes all assets it receives on
normal end, early close and failures without editing the locked preparer.
This is one authored10.1-second2.5D scene, not an episode/3D/general-script
engine. Source-to-movie rebuild is now verified on this configured runtime,
not arbitrary-platform support or final competitive quality. Keep the
five-hour automation paused unless James asks.
