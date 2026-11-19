# Build the complete June short locally

Use `Run June Full Short.cmd` on Windows, or from the repository root:

    python -m pipeline.cartoon_full_short_source --check
    python -m pipeline.cartoon_full_short_source --output PATH_TO_FRESH_DIRECTORY

This builds the 38-second repaired *Twelve-Dollar Mug* edit directly from
the tracked legacy plate/pose/liquid art and exact sound sources. The
default reuses the tracked reviewed 303-frame repaired picture so it
can preserve those decoded pixels exactly. No older rendered Phase25
master, outside cache, cloud service, voice-generation or API key is
needed. The existing master-input reproduction command is unchanged.

For the full source-rendered route (including all protected frames):

    python -m pipeline.cartoon_full_short_source --rebuild-repaired --compare-review --output PATH_TO_FRESH_DIRECTORY

`--rebuild-repaired` calls the approved component source build and uses
its new picture; the tracked reviewed MOV stays a comparison target,
not its pixel source. The final builder checks 303 decoded repaired
frames against that tracked proof without accepting a version drift.
`--compare-review` additionally compares the 837 other frames with the
prior 38-second review **after** encoding. It is optional and does not
supply images to the renderer. Outputs are never overwritten.

This configured runtime uses local FFmpeg/FFprobe, Python, NumPy 2.4.4,
Pillow 12.2.0, and OpenCV. Start with `--check`; missing or changed
locked inputs fail closed. See `JUNE_WORKING_MODEL.md` for setup. The
prior cut and credits remain in `collab/june_twelve_dollar_mug_repaired_v1/`.
The output contains a preview MP4, exact-audio MOV, PCM mix, sidecar
captions, native frame hashes and technical checks. Technical equivalence
does not approve the full film, temporary voice, production release or
main-branch promotion.
