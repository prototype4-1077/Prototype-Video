# Build the two current June review cuts

For the separate 39.7/40.7-second story review with the visible loan,
return, and coffee handoff, see [Build both story cuts](JUNE_STORY_REVIEW.md).
This page and the older launcher still build the two 38-second edits.

Double-click **Build June Review.cmd** in this checkout. It creates a fresh
folder under `outputs/edit/`, builds the shared shots once, and exports
both 38-second versions of *The Twelve-Dollar Mug*. Open the MP4 in the
`face/` or `visitor/` subfolder. Each has a corresponding MOV with exact
PCM audio. The root also contains the shared mix, English caption sidecar
and a verification report. It never replaces previous outputs.

From the repository folder, you can also check the tools, build both
versions, or select just one of them:

    python -m pipeline.cartoon_current_review --check
    python -m pipeline.cartoon_current_review --output outputs/edit/june-both
    python -m pipeline.cartoon_current_review --variant face --output outputs/edit/june-face
    python -m pipeline.cartoon_current_review --variant visitor --output outputs/edit/june-visitor

`face` stays on June during his reaction. `visitor` adds the short view
of the visitor's hand. Both include the fixed pencil handling and
the right-hand coffee lift and return. The old **Run June Full Short.cmd**
and reviewed outputs remain unchanged.

## What is rebuilt and verified

No older full-length movie, external render cache, network connection,
GitHub action, AI key or paid service is required. The approved scene
regenerates from tracked art once. The two timelines each contain 1,140
frames at 1080p30, original 48 kHz stereo audio and all 18 caption cues.
On the configured Windows runtime, the build checks the native RGB
inventory for all 837 other frames per version, verifies the 303
protected decoded frames against their locked review, and requires the
same PCM stream and caption sidecar. In a dual build it also verifies
the picture packets outside the reaction and all audio/caption packets
match across both variants.

Use the local prerequisites in `JUNE_WORKING_MODEL.md`. Exact checks
can reject runtime/library drift. Start with `--check` to verify local
dependencies and the tracked source locks. If a build fails after
starting, keep its failure report and use a new folder on retry.

Optional `--compare-face PATH` and `--compare-visitor PATH` compare the
results with the exact earlier local review movies **after** rendering.
Those references are never read as picture or sound sources, and the
launcher doesn't require them. Original intro footage was encoded on a
different boundary, so comparisons use same-index visual error there,
and exact picture matching for the corrected action and protected frames.

These are review cuts. Neither a passing build nor the availability of
two variants is artistic approval, a release, or a promotion to main.
The tracked-only build and post-render comparisons are recorded in
`collab/june_current_review_clean_v1/`.
