# Phase42 — subtle blink refinement v3

James's direction: slightly too quick/frequent, plus a small shape adjustment.
The near-pass source artwork is preserved, not regenerated.

Open `phase42-blink-comparison-real-cadence-v3.webp`:

- Left: previous two-blink cadence on the 7.6-second scene clock.
- Right: one slower late blink with a gently curved intermediate lid margin.
- The refined blink occurs near **six seconds**. The long open-eye hold is
  intentional; this is not the old rapidly repeating half-second loop.

`phase42-blink-refined-real-cadence-v3.webp` shows only the new candidate.
`phase42-blink-refined-neighbors-v3.png` shows all 13 control samples.

## Specific change

- Control span: about 267 ms to 400 ms, using smooth closure/reopening curves.
- Two full-close frames rather than one.
- One blink rather than two in 7.6 seconds.
- Intermediate upper/lower margins acquire at most one native pixel of subtle
  curvature. Exact open and full-close masks/artwork are unchanged.

This is an **eye-only study at a locked head/camera pose**, not the full scene.
It uses the real scene-duration clock to distinguish blink spacing from a
looping preview artifact. Sustained acting/body motion has not been rendered
or accepted in this package.

The first shape experiment remapped already quantized masks and failed a
monotone-coverage test. It was not published. The final version curves analytic
margin coverage instead and keeps the socket feather fixed. The test is
unchanged and now passes across 101 closure values. Both exact endpoints match
the near-pass predecessor; the full-close delivered RGB hash remains
`155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40`.

Forty focused local eye/audio tests pass in the combined run. The blink and
new mix still require James's verdict; no full render or promotion is implied.
