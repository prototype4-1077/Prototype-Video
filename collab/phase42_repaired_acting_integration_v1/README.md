# Phase42 — repaired eyes inside the acting/camera renderer

Status: **six-frame integration proof, not human-accepted or a full scene**.

Open `phase42-acting-eye-integration-comparison-v1.png`. Each row compares:
original source compositor / existing body acting / body acting with repaired
eyes. Full-resolution repaired frames are provided for source F081 and F173.

## What this proves

The repaired eyelids now have a reusable path through the existing body, hand,
face, head, atmosphere, and editorial-camera renderer. No second animation
engine was built. The existing Phase40 candidate hashes are independently
matched before applying the eye repair.

| Source frame | Output frame | Body active | Blink closure | Eye changes outside declared support |
| ---: | ---: | --- | ---: | ---: |
| 70 | 145 | yes | 0 | 0 |
| 79 | 154 | yes | 0.5 | 0 |
| 81 | 156 | yes | 1 | 0 |
| 82 | 157 | yes | 0.75 | 0 |
| 148 | 223 | no | 0 | 0 |
| 173 | 248 | no | 1 | 0 |

At source F081, both the body performance and the repaired full blink survive.
At F070 and F148, the open-eye path is byte-identical to the existing body
render. At F173, the close-up is byte-identical to the previously reviewed
Phase42 eye frame. Across all six samples, body changes never enter protected
face or mug support, and eye repairs never leave prospective eye support.

The allowed eye region is projected from declared native geometry through
the head/camera sampling footprints before inspecting candidate differences;
it is not fitted around the observed changed pixels.

## Exact clock and audio binding

Direct-address source F001 maps to output F076. Every output frame corresponds
to 1,600 stereo sample frames at 48 kHz. Source F025 maps to output F100 and
sample 158,400, where dialogue starts after the repaired bridge. Source F228
ends exactly at sample 484,800.

The unchanged `balanced_air` WAV is hash-bound and format-checked. This is a
sample-window binding, **not** a new encoded audiovisual delivery or listening
verdict. The audio remains pending James's ear.

## Safety and remaining work

- No full scene was rendered; only these six source times were exercised.
- No video encoder, network service, new generation, or cash spend was used.
- Existing Phase40, Phase42, and rejected predecessor artifacts remain intact.
- The mutable source texture, cache, and shared blink functions are restored
  after each use, including injected failure paths.
- Eleven new tests exercise the actual adapter, not just its report. Negative
  tests remove the eye repair and invalidate the support projection; both
  faults are detected.
- The combined focused local regression run passes 43 tests across the new
  integration and predecessor eye/audio paths; this is not a remote-CI claim.

This establishes component compatibility on the sampled frames. It does not
establish natural sustained acting, whole-scene temporal quality, a general
episode-production tool, or permission to rebuild a master. Review the v2
normal-speed blink and the existing audio first. Human acting review and a
newly versioned integrated scene remain ahead.
