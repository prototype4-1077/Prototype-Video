# Integrated mouth/hand A/B — v1 — human review pending

Watch `june-mouth-hand-integrated-ab-v1.mp4` once at normal speed. Existing
performance is on the left; mouth-label translation plus the restrained
planted-hand candidate is on the right. Same speech, 138 frames at 30 fps,
4.6 seconds: original scene time 3.3–7.9 s, source F025–F162 / output
F100–F237. No word timing, speech speed or final-scene cut was changed.

Both columns use the exact same fixed [400,60,1360,1080] delivery-pixel crop
at 1:1 scale, with labels outside the image. This is diagnostic close framing
to make the mouth and late hand readable together, **not** a new final-scene
camera/edit. The original head/body/camera motion remains in both columns.

Judge only the open decisions:

- Does the right mouth follow the words more convincingly, including closed
  P/B/M and F/V contact, without an abrupt tooth/beard seam?
- Does the late right hand feel planted and deliberate rather than rubbery?
- Is either repair less expressive, too quiet, or still mechanical at speed?

The cuts, blink v3 and recorded-Foley v3 are already accepted. This clip
doesn't replay the later cut/blink in motion; their acceptance is not reopened.
The combined adapters also check the exact existing F248 full-close RGB hash
outside this excerpt. Do not treat that endpoint test as sustained acting
approval or call this an entire completed cartoon.

The old side reuses the hash-verified lossless current-scene cache, not a
second render or a recompressed video baseline. The new side reuses the
current body, facial, atmosphere and camera stack with isolated adapters.
Every frame is checked against a prospectively declared mouth/hand support
union; the mug is separately protected. Limits and source hashes are in
`integrated-mouth-hand-review-report-v1.json`.

MOV: same H.264 picture, exact PCM24 review excerpt. MP4: browser-friendly
H.264/AAC. Only the short review excerpt has 30-ms edge fades; the accepted
10.1-second full-mix WAV is untouched. Keep `ATTRIBUTION.md` and `sources.json`
with shared copies. These are compressed-picture review files, not a lossless
production master. Native component studies are in the sibling mouth/hand
packages; no new full-scene render, art generation, paid call or cloud job.

No human acceptance, production promotion or main merge is implied.
