# Phase 42 — human-rejected gate successors v1

Status: **bounded human-review package; not accepted; no full render or promotion authorized.**

James rejected Candidate03 audio for audible static and Phase37 V4 for unnatural
eyes with gray material above the eyelid.  Those predecessors remain immutable.
This folder contains new A/B evidence only.

## Recommended review order

1. `phase42-eyelid-ai-direct-f240-f256-loop-v1.webp`
   - Review motion first.  It is the direct AI-assisted lid extraction on the
     locked GS070 plate, with an upper-lid-led 70/30 blink.
   - The full-close frame has no gray upper-lid source and no sclera corner
     leaks.  Both eyes reach measured 1.0 iris occlusion.
2. `phase42-eyelid-source-phase36-3x-v1.png`
   - Left: rejected V4.
   - Middle: recommended direct extraction.
   - Right: brighter local-tone-match alternative.
   - Recommendation: **middle/direct**, because it retains more natural socket
     depth while removing the rejected gray source.
3. Listen to `june-phase42-fullmix-balanced_air-v1.wav` first.
4. If any hiss/static remains objectionable, compare
   `june-phase42-fullmix-clean_warm-v1.wav`.
   - Recommendation: **balanced_air**, because it is the least-filtered mix
     that clears the static proxy and keeps more porch air.

## Measured audio change

| Measurement | Rejected Candidate03 | balanced_air | clean_warm |
| --- | ---: | ---: | ---: |
| Static-like window ratio | 28.39% | 0% | 0% |
| Longest static-like run | 0.736 s | 0 s | 0 s |
| Quiet impulsive events | 25 | 0 | 0 |
| Pour/bridge immediate edit delta | 0.00106 FS | 0 FS | 0 FS |
| Bridge/dialogue immediate edit delta | 0.03368 FS | 0.00354 FS | 0.00179 FS |
| Maximum adjacent sample delta | 0.24005 FS | 0.17237 FS | 0.17038 FS |

The remaining fixed-threshold transients in both successors occur only during
dialogue-active samples; none occur in quiet or transition material.  That
supports, but does not replace, human listening.

## Measured eye-motion change

- Full-close iris occlusion: 1.0 left, 1.0 right.
- Maximum adjacent eye-crop 8x8 mean delta: 115.08, below the inherited 130
  blink-pop ceiling.
- The generated frame is never used wholesale.  Only a small bilateral eye
  socket region is extracted; the locked GS070 plate remains the background.
- The predecessor's equal upper/lower travel was replaced because it made the
  lower lid read as a rising shutter.  The successor drives most travel from
  the upper lid and uses the generated closed-eye anatomy only as the target.

## Decision needed after review

- `EYES ACCEPT DIRECT`, `EYES REJECT`, or a precise note about the remaining
  eye behavior.
- `AUDIO ACCEPT BALANCED`, `AUDIO ACCEPT WARM`, or the timestamp and character
  of any remaining defect.

No positive decision here authorizes an automatic retry of a rejected render.
It authorizes a new picture/audio build with new provenance and a new human
review gate.
