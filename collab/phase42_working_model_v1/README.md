# June working prototype v1 — complete source-built scene

Completed 2026-10-29 from clean tracked source commit
`1ec1ce40f84f7fdec2bf21104013cc1dab114184`, not an old movie/cache.
303 frames / 10.1 seconds / 1920x1080 / 30 fps. One existing authored
three-shot scene: pour, direct address, closing close-up.

- Play `june-working-prototype-v1.mp4` for convenient H.264/AAC playback.
- The MOV has the same compressed picture and exact approved PCM24 audio.
- Run **Run June Prototype.cmd** at repository root, or follow
  `docs/JUNE_WORKING_MODEL.md`, to regenerate it locally without API keys.

All75 source-built opening frames match the original pixels; all138 frames
from James's passed mouth/hand comparison match its repaired full-frame RGB.
The accepted full-close endpoint is unchanged. Every final timestamp passes;
MOV audio is exact and preview AAC SNR is42.54dB. All28 sampled picture checks
exceed40.05dB PSNR. These are technical checks, not final artistic approval.

James's mouth/hand pass is provisional: polish is deferred so development
can move forward. No new mouth/hand approval question is needed now.
This milestone proves the configured source-to-movie path, not arbitrary
script generation, free-turning3D characters, episode-scale production or
industry-competitive acting. Main/release promotion remains false.

The detailed audit records files from the complete local run. This Git
review package intentionally omits per-frame reference PNGs, intermediate
shots, logs and the483MB generated RGB cache; those remain locally under
`d/outputs/edit/phase42-working-model-v1/`. The receipt identifies the exact
source archive, process completion and publication boundary. Root inspected
the decoded contact sheet; no unperformed motion/audio review is claimed.

Keep `ATTRIBUTION.md` and `sources.json` with shared derivatives.
Recommended next increment: prove a second authored scene through the same
engine, then expose the minimum reusable shot/dialogue controls. Do not
start another renderer or another polish cycle on this scene.
