# Pickup — 2026-10-29 — reusable dialogue scene implementation

Previous goal turn classification: **progress**. The full303-frame first
scene was built from clean tracked source and published atf7bb2c4. That is
not competitive whole-cartoon completion. James's provisional mouth/hand
pass remains frozen; do not revisit its unchanged comparison.

Inspection found existing `cartoon_vertical_slice` / story-reel / shot-sequence
tools, but the high-detail current rig's wrappers are locked to particular
228/303/453-frame proofs. The new `cartoon_dialogue_scene.py` reuses the
existing source-asset loaders, mouth adapter, blink shape, motion compiler,
pixel compositor and encoder. It supplies clearly labelled new runtime
performance views; no historical proof loader, contract or passed film is
edited. It intentionally supports resting source hands/head/camera timing,
not new full-body acting or arbitrary camera angles.

New recipe: `concept/scenes/june-rest-your-hands-v1.json`.
New cached line: "Some days, the bravest thing you do is set the bucket down.
Ain't no shame in resting your hands." 207frames /6.9s. Audio clock is derived
from its own48kHz PCM24 source, not forced to228frames. Runtime supports1..60s
with strict bounds, end silence, cue/audio/text binding and inherited camera/
head bounds. The original passed audio is unchanged; this new voice is local
Piper Norman scratch, explicitly non-canonical and not human-accepted.

Local generation uses the already installed Piper/Rhubarb, not a paid API.
`cartoon_dialogue_media.py` prepares a cached sample-aligned WAV and phonemes.
The first run's duration guard caught padding/trimming before resampling.
Preserved the failed output under `d/outputs/edit/june-second-scene-media-v1`.
Fixed by resampling to48kHz before exact sample trim; a real FFmpeg regression
test reproduces the22.05kHz input and proves final sample count / quiet tail.
Second media run succeeded at`june-second-scene-media-v2`; vendored WAV,
phonemes, report, original model card and provenance under
`concept/audio/june_rest_your_hands_v1/`. No time stretching or synthetic Foley.

11 scene tests +2 media tests +5 old published-first-film checks passed18/18
in23.679s. A first test run had the wrong expected exception class after the
real frame300 had already rendered; corrected only that expectation. The
passing test actually renders frame300 through the inherited rig and checks
that frame301 is rejected, while original228-frame source objects and bank
approval remain unchanged. The new-recipe --check also passes.

Launcher: `Run June Dialogue Scene.cmd`; guide: `docs/JUNE_DIALOGUE_SCENES.md`.
The completed full207-frame new scene is still pending at this implementation
checkpoint. Next run it once into a NEW directory, capture actual process
handle, verify every timestamp/decoded frame, unity-gain PCM mono-to-stereo
mapping, sampled picture quality and AAC. Inspect actual decoded output;
then publish only a technically complete new performance review candidate.
Do not call a first-film human verdict approval of the new voice/performance.
Main, rejected artifacts and automation remain untouched/paused.
