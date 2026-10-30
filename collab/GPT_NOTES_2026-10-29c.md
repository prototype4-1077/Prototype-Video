# Pickup — 2026-10-29 — second authored dialogue scene verified

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

## Actual completed picture and audio-only delivery repair

Source commit`e92742705688c41c8da992e99fad0491a53f9327` was archived/extracted
under `d/outputs/edit/june-dialogue-scene-source-verification-v1/checkout`.
Archive608604160bytes, SHA256
`e93fd8c6d6afdf1b62f9e9e1b42f52b9e0887439d90c06b3ae3352d1ca9980d9`.
No old scene cache copied; cached new audio/cues are tracked. The launcher
--check exited0 from that clean source copy. Actual render session48553
completed207 picture frames but exited1 at the unchanged40dB AAC SNR gate:
256k preview38.2672495dB. Source/MOV PCM were exact; AAC peak0.99266, not
clipping. The failed output remains`june-rest-your-hands-scene-v1/`.

James said "resume" during this job; resumed the actual handle, not a new
render. Correct next action was audio-only delivery repair, not redoing207
unchanged pictures. `cartoon_dialogue_delivery.py` verifies the exact prior
picture hash, identical pixel-renderer AST, recipe/motion plan, specific
AAC-only failure and strict inherited source loaders. Other failures cannot
be relabelled as audio retry. It copies the exact picture/MOV to a NEW folder,
encodes only AAC at512k, and reruns every current media gate.

Actual recovery session43393 exited0 into
`d/outputs/edit/june-rest-your-hands-delivery-v2/`. SNR40.4699088dB,
all207 decoded frames / exact timestamps, MOV dialogue PCM exact after
explicit unity-gain mono-to-stereo duplication, identical MOV/MP4 picture
packets, six PSNR samples>=38.4503725dB (inherited38dB floor). No picture
rerender/re-encode or paid service. Current new-scene default AAC is512k.
Pixel functions themselves are unchanged frome927427.

The initial renderer saved native inventory after the audio audit and lost
its in-memory raw hashes at failure. Do not fabricate them. The publication
honestly includes all207 **decoded** RGB hashes plus all six actual raw
reference PNGs; report says whole native inventory unavailable. The current
builder now writes native inventory BEFORE mux/audit. A simulated later
export-failure regression proves it remains available without rerendering.

Publication: `collab/june_rest_your_hands_v1/`, MP4 SHA256
`fbe7bae4c4843effac9dd22a1053b79e115c5c04fbf124074979d1a09dfdd3a3`;
MOV SHA256`a1253e7cf0e3af6b4ba0eb4720f55297668a688db240999f295787006fe7e5ba`.
Two movies, reports/receipt, decoded contact sheet/inventory, compiled motion,
six raw reference PNGs and credits. Root inspected the six decoded stills,
including full-close blink and final rest. No unperformed normal-speed or
audible review is claimed. The new scratch voice/performance is unaccepted;
the first film's verdict does not transfer. All first-film gates stay frozen.

Focused seven-suite run43/43 passed in29.918s, then the newly added native-
inventory failure regression1/1 passed in0.166s:44 distinct focused checks.
This includes all prior23 source-built-model checks, new dynamic scene/media,
real frame300, audio-only-recovery guards and published-artifact checks. Not
a claim the entire repository suite or artistic production gates have passed.

## Next meaningful capability

Do not render a third talk-only scene or return to mouth/hand polish. Inspect
the existing `cartoon_contact_performance_proof.py` and `cartoon_pose_layers.py`
mechanics for one contact-aware hand/prop action in the current porch rig.
Those older modules use standing/shared-UV or GS030 sources, not the current
GS070 close-view artwork; they are not automatically a compatible drop-in.
Reuse their geometry/contact ideas before building another renderer. Target a
visible reach/grasp/lift/settle with hand/mug contact, occlusion and normal-speed
proof. That is the missing move toward a cartoon rather than a talking image.
The full competitive-cartoon goal is still active/unproven. Main, rejected
artifacts and five-hour automation remain untouched/paused.
