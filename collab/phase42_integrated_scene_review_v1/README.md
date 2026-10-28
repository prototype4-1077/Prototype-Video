# June Oxley — integrated scene review v1

Watch `june-phase42-integrated-scene-review-v1.mp4`: the full 10.1-second,
303-frame scene at 1920x1080 / 30 fps. This is not an eye-only study or a
rapidly repeating blink crop. James has already accepted the exact blink v3
and recorded audio v3 in `collab/JAMES_VERDICT_2026-10-28b.md`.

## What to judge now

- Does the pour-to-camera cut feel intentional and readable?
- Do talking, gaze, hands and shoulders feel like one sustained performance?
- Does the face stay stable through speech, the close-up and the late blink?
- Does the approved sound still fit the visible actions?

The blink closes fully at F247-F248, around 8.2 seconds in this full edit.
The original early blink is removed. Source art, mouth/voice clocks, the
existing opening, body rig and editorial camera are preserved/reused.

## Formats and evidence

- MP4: convenient H.264/AAC preview.
- MOV: the same H.264 picture with bit-exact approved stereo PCM24 audio.
  This is exact-audio, **not** a lossless-picture production master.
- `human-accepted-audio-v3.wav`: unchanged approved source audio.
- `decoded-scene-contact-sheet-v1.png`: samples from decoded video, not hero art.
- `reference-f145.png`, `reference-f244.png`, `reference-f248.png`: lossless
  rendered source samples for independent body/partial-blink/full-blink review.
- `source-frame-inventory-v1.json`: all 303 source RGB hashes and frame metrics.
- `phase42-integrated-scene-review-report-v1.json`: actual clocks, color
  metadata, audio identity, preview compression and artifact hashes.
- `shot01.mp4`–`shot03.mp4`: encoded-once picture segments, combined by stream
  copy. They are assembly evidence, not additional artistic candidates.

The short `decoded-blink-in-scene-30fps-v1.webp` is a 13-frame stress loop.
Its rapid loop repetition is **not** the scene's blink frequency; use the
complete movie to judge cadence. Cut filmstrips include decoded audio waveforms.

## Scope and credits

Eye and audio component acceptance is closed. The new combined performance
is not yet human-accepted or production-promoted, and no main-branch merge is
authorized here. A polished source-art puppet is not evidence of a general
episode-scale or free-turning 3D production system.

Keep `ATTRIBUTION.md` and `sources.json` with shared/derived audio or video.
The cup recording is by Nicole Marie T under CC BY 4.0. The pour source page
states public-domain dedication; both recordings were freely downloaded.
No paid service, cloud render job, new dialogue generation or image generation
was used for this review.

The local build uses the preserved lossless opening cache; that external data
is not in a fresh Git checkout. A new full-scene lossless RGB cache is retained
under `outputs/edit/phase42-integrated-scene-review-v1/` outside Git for future
delivery work. The videos in this review bundle play without that cache.

Recommended next artistic work: connective acting between pouring and direct
address, rather than reopening the accepted eyelids or removing more audio.
