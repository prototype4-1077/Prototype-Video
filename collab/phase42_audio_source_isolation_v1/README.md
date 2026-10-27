# Phase42 — source-isolation listening comparison

James still hears static **throughout** the previously recommended balanced-air
WAV. That listening verdict supersedes the old proxy's zero score. The blink
is near-pass, not accepted; no eye changes were made in this audio pass.

## Listen in this order

1. `june-phase42-porch-bed-removed-v1.wav`: June plus discrete coffee, body,
   mug, and chime events, with only the continuous procedural porch bed removed.
   Does the steady static disappear, reduce, or stay the same?
2. `june-phase42-voice-only-v1.wav`: exactly the same voice contribution and
   shared gain. **Intentional silence for the first 3.3 seconds**, then June.
   Use this to distinguish noise in the voice from noise in the soundstage.
3. `june-phase42-porch-bed-only-v1.wav`: the removed continuous bed, at its
   original playback gain, not amplified to make it sound worse.

All three have the same 10.1-second clock. These are controlled comparisons,
not accepted masters. Silence in an isolated track is expected and must not be
mistaken for a complete-scene audio hole.

## What changed

The old bed explicitly synthesizes noise-based leaves and cicadas over wind.
The earlier shelving treatment retained this source. It could reduce the
proxy's high-frequency score without resolving James's perceived static.

This experiment does not apply another whole-mix filter, regenerate speech,
retime words, adjust the voice level, or silently normalize each audition.
It reconstructs the exact reviewed balanced-air PCM with **zero sample error**,
then subtracts only the continuous bed. Discrete noisy Foley is intentionally
retained so a remaining defect can be localized rather than hidden.

## Evidence and limits

- The isolated bed is nonzero in all 303 output frames, including before any
  dialogue. Its opening RMS is -45.36 dBFS at original mix gain.
- The old static proxy still scores the bed-only file zero. This is explicit
  evidence that zero on that proxy cannot establish perceptually clean audio.
- Reference PCM equals bed-removed plus bed-only within independent PCM24
  rounding. Voice-only is compared with the actual source contribution.
- Exact source/reference hashes, shared gain, sample clock, readback, unchanged
  reference, and reproducible output hashes are tested. The focused audio run
  passes 16 tests; that is not a listening verdict.
- No network call, paid service, image generation, or video encode occurred.

## James's follow-up decisions

- Bed-removed comparison: **"No real change"**. The bed-only hypothesis did
  not solve the complaint and is not a successful repair.
- Voice-only: James corrected his initial answer to **"correction there is
  not static."** The voice-only reference is therefore the clean component to
  preserve. The corrected answer is not evidence of a playback-device problem
  or acceptance of either full mix.

The next audition is `../phase42_sparse_foley_v2/`, which preserves this voice
exactly and replaces/omits the noisy effects. Its listening verdict remains
pending.

If bed-removed still has static, compare the voice-only file. If voice-only is
clean, isolate the discrete coffee/breath/mug sources next. If voice-only also
has the defect, repair the speech source instead. Do not call this experiment
a clean mix before James listens.
