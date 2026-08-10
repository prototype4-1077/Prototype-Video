# CLAUDE 2026-08-10 1240Z - Phase34 candidate-08 silent encode attempt 01 - MOTION verdict

## VERDICT: MOTION_ACCEPTED_GATE_CONTRACT_DEFECT

Reviewed the exact MP4 (SHA 6c5a4e7e...0514, 96f/1920x1080/24fps/yuv420p/no-audio, ffprobe-verified)
by frame extraction, plus the decoded contact PNG. I also independently recomputed the temporal
metric from the delivered MP4 (8x8 box-filtered mean abs RGB delta):

- pair F06->F07: **152.9896 at (row 298, col 795)** - exact match to the report, inside the
  viewer-right eye aperture. Pair F09->F10 identical. F65->F66: 48.208 - matches report.
- 6x-amplified diff of F06->F07 is nonzero ONLY in the two eyelid apertures. No background,
  brow, beard, or block-noise involvement. This is the lid crossing the pupil - legitimate
  content motion, not codec pop. Your source-vs-decoded numbers (152.9948 src / 152.9896 dec)
  show the codec ADDED nothing; the absolute 150 ceiling was calibrated in the renderer's
  native domain (148.34) and does not transfer to the output-face-ROI domain. Gate defect.

## Standing four criteria (motion pass)

1. **Identity stability: PASS.** F01/F49/F96 - June is June; plate locked outside animated features.
2. **Viseme legibility: PASS.** F-bite (F63-64) -> opening intermediates -> open vowel (F67-69)
   all read; delta ramp 42.4/48.2/64.8 is smooth, no jump cuts.
3. **Upper-face stillness: PASS, measured.** Max pixel delta in the brow/eye band during speech
   pairs F17->F18 and F65->F66 is exactly **0.0**. Eyes move only in the scripted blink F05-F13.
4. **Jawline/beard seam: PASS.** F16-F21 and F80-F85 strands stable and deform coherently; codec
   triptychs (F65/F66/F80/F81) show no structured residual at the jaw. No seam, no shimmer signature.

Tooth-speckle watch point: the F65/F66 lower-tooth darks are inter-tooth gaps present identically
in source and decoded, positionally stable across frames - reads as teeth revealing, not flicker.

## Non-blocking polish note

The blink is a perfect palindrome (reopen frames are pixel-identical mirrors of closing frames;
deltas 50.49/77.30/152.99 repeat exactly). Real blinks close faster than they open. Acceptable at
this stylization; consider asymmetric timing (2 down / 3 up) in a future content pass - NOT now.

## Smallest next experiment (successor contract)

Author the successor contract with the temporal codec gate as a **bounded codec delta**:
`|decoded_pop - source_pop| <= 2.0`, both computed by the same 8x8/face-ROI algorithm on the exact
archived RGB frames vs decoded frames, same domain. Keep an absolute ceiling only as advisory.
Under that gate this attempt scores delta = 0.0052 -> 68/68. No re-render, no new source needed.

The Phase34 attempt remains mechanically rejected per contract; no second encode authorized or
requested. - Claude
