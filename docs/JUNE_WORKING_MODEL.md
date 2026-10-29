# Run the June Oxley working prototype

This is the zero-cash local cartoon entry point, not the legacy paid-service
render farm or the September Blender studio. It assembles the existing
10.1-second, three-shot June scene at 1920×1080 / 30 fps from tracked source
art and the current body/face/camera stack. No old external render cache,
GitHub connection, runtime AI service, API key or paid account is needed.

James passed the mouth and late hand **for now**, with polish deferred until
the working model exists: `collab/JAMES_VERDICT_2026-10-29b.md`. Those exact
adapters, accepted blink v3, accepted recorded audio v3 and cuts are frozen.
This does not declare final artistic quality, a production release or a
main-branch merge. No additional mouth/hand approval loop is required now.

## On this configured Windows computer

Double-click **Run June Prototype.cmd** in the repository folder. It checks
the local tools/primary assets, builds into a new timestamped folder under
`outputs/edit/`, and prints the absolute movie path. It preserves old output
folders instead of overwriting them. The terminal stays open to show errors.

Equivalent command from the repository folder:

```powershell
python -m pipeline.cartoon_working_model
```

For checks without a render:

```powershell
python -m pipeline.cartoon_working_model --check
```

For a chosen **new** output directory:

```powershell
python -m pipeline.cartoon_working_model --output outputs/edit/my-june-prototype
```

The check does not render or test artistic quality. It validates installed
tools, the accepted component bindings and primary opening dependencies;
the full build also validates the deeper locked facial/body asset graph,
source pixels, final frame/audio clocks, color and encoded-media readback.

## Local prerequisites

- Python **3.11**, with the as-tested free packages in
  `requirements-cartoon-prototype.txt`.
- Local **FFmpeg and FFprobe** on PATH, with libx264/AAC/PCM support.
- This entire branch checkout, including its tracked source art and
  provenance/review assets. No external `outputs/` cache needs copying.

If the packages are missing, install them in a Python environment you own:

```powershell
python -m pip install -r requirements-cartoon-prototype.txt
```

The launcher does not silently install software, download artwork, switch
to a paid service, configure credentials or change account permissions.
The original sample-exact raster toolchain is pinned because source-pixel
equivalence is checked. Broader platform/version support is not claimed.

## Outputs

- `june-working-prototype-v1.mp4`: convenient H.264/AAC playback.
- `june-working-prototype-v1.mov`: identical compressed picture with the
  exact approved PCM24 full mix. Not a lossless-picture production master.
- `working-model-report-v1.json`: actual build scope, source/approval hashes,
  limits and links to the detailed media audit.
- `phase42-integrated-scene-review-report-v1.json`: reused builder's actual
  decoded-video/audio, timestamp, color and compression checks.
- `source-frame-inventory-v1.json`, sample stills, cut filmstrips, source
  manifests and attribution. Keep credits with shared derivatives.
- A local lossless RGB cache is generated for later work, but it is an
  **output**, never an input to this source-built prototype.

The complete accepted audio is muxed once; it is not extracted/rejoined at
the picture cuts. Each silent picture shot is encoded once and concatenated
by stream copy. The native opening's 75 frames are regenerated with the
existing pour renderer and checked against the prior published RGB hashes.
No historical top-level gate or protected source artifact is weakened.

## What this is not yet

This is one runnable authored scene, not arbitrary script-to-cartoon
generation, a free-turning 3-D character, a multi-cast episode engine or
industry-competitive final acting. Art/character expansion, general scene
authoring and later visual polish remain development work. Avoid claiming
that a successful build or provisional component pass completes that goal.

## Verification checkpoint

The actual full303-frame run succeeded from an isolated tracked-file
snapshot of commit `1ec1ce40f84f7fdec2bf21104013cc1dab114184`. No old external
render cache was copied. The launcher also passed `--check` from that copy.
See `collab/phase42_working_model_v1/clean-source-build-receipt-v1.json` and
the adjacent completed movies/reports. All75 original opening hashes and
all138 full-frame hashes from James's passed comparison match. The accepted
full-close frame is unchanged; MOV audio is exact; all303 timestamps pass.
18 source/entry tests and five no-render published-artifact regressions pass.

The publication package intentionally omits intermediate shots, per-frame
reference PNGs and the generated RGB cache. They remain in the complete
local output directory recorded by the receipt. Root inspected the decoded
contact sheet, including both cuts and full-close endpoint. These technical
checks and still inspection do not claim sustained acting/audio acceptance
or complete the full competitive-cartoon goal.
