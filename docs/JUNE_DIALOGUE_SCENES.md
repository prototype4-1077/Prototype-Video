# Author a new June dialogue scene

The first passed three-shot film is frozen. This separate adapter tests
reusing June's existing artwork and lower-level face/head/atmosphere/camera
renderer with **new words, new phoneme timing and a new audio-derived clock**.
It does not create another raster engine or modify the earlier proof loaders.
New performance descriptors are explicitly unapproved runtime views of those
validated assets, not forged approvals of changed historical contracts.

On the configured computer, double-click **Run June Dialogue Scene.cmd**.
It uses the included new recipe and cached audio/phonemes, not live AI.
New output goes into a fresh timestamped folder under `outputs/edit/`.

For a different authored recipe, from the repository root:

```powershell
python -m pipeline.cartoon_dialogue_scene --scene concept/scenes/june-rest-your-hands-v1.json --check
python -m pipeline.cartoon_dialogue_scene --scene concept/scenes/june-rest-your-hands-v1.json --output outputs/edit/my-new-scene
```

The recipe has these controls:

- Dialogue text and exact local audio/phoneme files, with SHA256 hashes.
- Head position/tilt and camera push at normalized phases0..1. Bounds are
  inherited from the existing rig; cubic easing comes from its motion loader.
- Blink start times, reusing the passed13-frame shape/curve at new positions.
- Resting source hands only. Torso/hand action authoring is not implemented
  by this adapter; it rejects those controls instead of reviving old warps.

The audio determines duration. Current bounds are1..60seconds,30fps,1080p,
48kHz mono/stereo PCM24. Its sample count must be divisible by1600. At least
one quiet second and closed-mouth cues must follow the speech. Cue metadata
must bind to the exact WAV and words. No arbitrary unverified audio/clock
changes are silently accepted. These are technical, not artistic, guarantees.

## Make new dialogue without a paid service

The included example uses the already installed Piper Norman voice and
Rhubarb. It is a **non-canonical scratch voice**, not a human-accepted June
voice. The existing passed audio remains untouched. Existing cached audio
and cues can render without either executable or voice-model download.

To prepare your own new line, supply the actual local tool/model paths:

```powershell
python -m pipeline.cartoon_dialogue_media --text "Your new line here." --output outputs/edit/new-dialogue --piper LOCAL_PIPER_EXE --voice LOCAL_MODEL_ONNX --rhubarb LOCAL_RHUBARB_EXE
```

It refuses existing output. No installation, network access, credential,
external API or billing fallback. It resamples **before** sample-clock
padding/trimming, preserves natural speech rate, and adds30ms speech-edge
fades,400ms lead and at least1s quiet tail. Add the produced WAV/cue files
to the project with the hashes and words printed in its provenance report,
then reference them in a copied recipe. Keep model/source attribution.

## Verification and limitations

The builder checks every exported timestamp and decodes every final frame.
MOV audio must equal source PCM, with explicit unity-gain mono-to-stereo
duplication if necessary; MP4 preserves identical encoded picture and uses
AAC. Sampled decoded picture has a38dB PSNR floor; AAC SNR must exceed40dB.
Reports, frame inventory, compiled motion, a decoded contact sheet and failure
logs preserve evidence. Existing outputs are never overwritten.

This adds reusable dialogue/head/camera timing, not a new full-body action,
new camera angle, new set, multi-cast episode engine or final voice quality.
The new line, acting and blink placement still need normal-speed judgment;
the first film's provisional verdict does not transfer to this performance.
An actual full new-scene run is pending at this implementation checkpoint.
