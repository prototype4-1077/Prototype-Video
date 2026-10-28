# GPT notes — 2026-10-28 — real recorded Foley, no tonal substitutes

Parent checkpoint: `3786cd0a6c03b2a981745184a31ebf52acbdf069`.
Branch: `agent/phase42-human-rejected-gates-repair-v1`.

## Controlling new verdict

Read `JAMES_VERDICT_2026-10-28.md`. James heard **no static** in sparse v2 but
described game-like opening noises and a later phone-like sound. Static-check
success is not effect-character acceptance. No new blink verdict was given.
The event identity is inferred, not timestamp-confirmed by James.

Do not return to oscillator/water-drop tuning, the old noisy procedural
effects, or voice filtering. Voice-only remains the human-clean reference.

## Smallest informative replacement

Added `pipeline/cartoon_recorded_foley.py`, reusing the existing local FFmpeg
audio decoder, PCM24 read/write, and exact editorial sample mapping. Only
two real recordings are used: a kettle/mug pour and one cup/table contact.
All chimes and other synthetic cues are omitted. The cut-out pot-set tail is
not invented. This diagnostic is deliberately sparse; it is not complete
scene Foley or an episode-quality sound-design claim.

Raw source files, pinned hashes, authors, source pages, licenses and fixed
excerpt ranges are in `concept/audio/foley_sources_v1/`. The Commons page
states that the pour recording was dedicated to the public domain. The cup
recording by Nicole Marie T is CC BY 4.0. Credits and modification notices are
copied alongside the audition; carry them into any later derivative render.
Both were downloaded freely without an account. No purchase or inference
service was used; builds use only the vendored files and local decoder.

The Ogg download's SHA-1 matches Commons metadata. Its container does not
decode through this installation's libsndfile, but the already-installed
FFmpeg decoder handles it; no new dependency or install was needed.

Package: `collab/phase42_recorded_foley_v3/`.

- Main WAV SHA-256:
  `3c6965f8030d9c7360a418cb19dd6b193396a5c1a37b8084ca247622a259c14f`
- Effects-only SHA-256:
  `e80120adaeb00d0fa156137a504c7805d458f142e7e71f9b00d18a6718ea9212`
- Report SHA-256:
  `d11230d8b32ba7c1934a7ea8c1358351274a720ef19fa329318bbdb42ea94e04`
- Source manifest SHA-256:
  `42eb293da43770457956fb4a336dfaa4b713274d063ecbe9641b17b1788b5d59`

The pour occupies output samples `[25600,120000)` (0.533–2.5 s). The cup
occupies `[209600,235200)` (4.367–4.9 s), with the main transient approximately
32 ms into its window. Excerpts have 1,440-sample / 30-ms fades at both edges.
No looping, stretching, pitch change or generative synthesis occurs.

## Verification versus listening

The voice contribution is bit-exact: `mix - effects == voice` at every PCM
sample, including beneath the cup contact. No whole-mix normalization occurs.
The 48-kHz stereo PCM24 clock remains 484,800 samples / 10.1 s; peak is
-1.382286 dBFS, and both edit-boundary adjacent-sample deltas are zero. Effects
are exact digital silence outside their two windows.

Eight new source/credit, timing, fade, preservation, immutable-output and
fresh-build tests pass. Combined local run: **48 tests in 13.821 s**, covering
recorded Foley, source isolation, sparse v2, blink refinement, continuous
blink, eyelid source, old full-mix successors and noise proxy. This is not a
full-repository or cloud-CI pass. It does not establish that the new recorded
mix sounds natural or static-free. James must actually listen.

Candidate03 audio remains
`a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c`;
the rejected Phase37 V4 report remains
`fd08ee030123fc96585994825fc49942a937e9e631722478fa54bcee6bc36a7f`.
No eye assets, old packages, master or main-branch files were modified.
No full scene was rendered, no video encoder ran, and no cloud render was
dispatched. The two downloads cost zero cash; build-time network calls are
zero. Workflow push filters were inspected before publication.

## Resume / stopping point

1. Check later human replies before doing any more builds. Recorded v3 has
   no human acceptance yet. Ask whether the pour and single cup contact now
   read as physical actions, without beeps or hiss. If they still fail, isolate
   the offending cue or omit it; do not generate another oscillator sweep.
2. Blink v3 remains pending. Its fixed-head 7.6-s comparison is unchanged at
   `collab/phase42_blink_refinement_v3/phase42-blink-comparison-real-cadence-v3.webp`.
   The candidate blinks near six seconds. Do not infer approval from an
   audio-only answer, and do not rerender unchanged media on a scheduled wake.
3. Only after explicit eye and audio acceptance should the v3 variant be
   carried through the existing body/camera adapter for an authorized full
   performance review. No full render or master promotion before then.
4. Read any newer Claude reviews under `collab/`; the latest at this stopping
   point is still `CLAUDE_REVIEW_2026-08-13_0612Z.md`. No new external verdict
   was fabricated. Keep the overall full-cartoon objective unfinished.
