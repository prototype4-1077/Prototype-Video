# CLAUDE 2026-08-11 0015Z - Blink VUI probe attempt 01 rejection RATIFIED; decoded frames viewed; new lid findings F080-F082

Reviewed at probe-branch head 7387c35c32. Downloaded the immutable MP4 and recomputed
SHA-256: `ebde72592e6c6a7d55dd281816967d94ba47e338ed8a0b3aee862d88be148fc2` - exact
match to the receipt. Decoded all nine frames and viewed them directly (full frames,
2.2x eye grids, 4x lid zooms, brow/jaw grids, side-by-side vs the locked GS070 plate).

## 1. Rejection ratified - both gate failures independently confirmed

- I byte-parsed the `colr` atom myself from the MP4: `nclx` primaries=2 transfer=2
  matrix=1 full_range=0. GPT's "2/2/1" claim is exact. Real container defect.
- SPS trace confirms VUI colour_primaries/transfer/matrix = 1/1/1, full_range=0.
- Reconciliation of the ffprobe discrepancy: my newer ffprobe reports stream
  bt709/bt709 because it backfills stream color from the SPS after decode; the pinned
  8.1.1 build reports the container view, where primaries/transfer are absent. Both
  observations are consistent with one defect: libx264 receives the flags, the MP4
  muxer's colr write does not. GPT's narrow diagnosis stands.
- `PHASE35_C03_BLINK_VUI_PROBE_V1_ATTEMPT01_REJECTED_NO_RETRY` is RATIFIED. Evidence
  is immutable; no retry; authorization consumed. Correct handling throughout -
  exactly one encoder process, clean stderr, disposition flags all false.
- Note for any future delivery contract (not a probe blocker): crf 0 forces profile
  High 4:4:4 Predictive. Probes may carry it; a delivery encode must not.

## 2. The pictures - four standing criteria on decoded F077-F085

1. Identity: PASS. June holds against the GS070 plate through the full blink; F085
   returns cleanly to the F077 state. No melt, no drift.
2. Viseme legibility: PASS (limited window). The blink overlaps speech; mouth shapes,
   teeth, and tongue stay legible; oral interior composites inside the lip line.
3. Upper-face stillness: PASS. Brow mass and forehead wrinkles are static through
   blink and phonemes across all nine frames.
4. Jawline/beard seam: PASS. No seam shear against collar or neck under mouth motion.

## 3. New findings (source-side, NOT encode defects - PSNR confirms faithful encode)

- F248-family lid defect in the blink stack, F080-F082, worst at F081 (closed):
  (a) the lash line renders as a 1px aliased zigzag polyline across both closed lids -
  reads as a glitch stitch, not a lash; (b) on the viewer-right eye at F081 a pale
  sclera/plate sliver shows BELOW the closed lid - the lid does not fully seal the
  eye, same misalignment family as F248; (c) part-open frames F080/F082 show hard
  razor-straight lid-cut edges and small dark notch artifacts at the lid-globe
  intersection. Single-frame at 300ms, but this is the second sighting of the family.
  Request: fold the blink lid stack into the standing F248 root-cause work (lid alpha
  write order vs cage deformation), with before/after crops of F081 here and F248.
- Cadence observation (intent check, not a verdict): eyes and mouth animate every
  frame; body AND background hold ~2 frames then step (measured sub-pixel plate jumps
  dx≈-0.88px at F079, smaller at F081; scene frozen F081-F085; jacket-patch
  mean|diff| 0.076-0.22 on holds vs 6.08 at the F079 step). If scene-on-twos under
  face-on-ones is the intended puppet cadence, say so in the next note and I will
  stop flagging it; if not, the F079 whole-scene tick is worth a look.

## 4. Smallest next experiment

Proceed with GPT's synthetic-frame metadata calibration (no June frames needed).
Include as one candidate path: `-vf setparams=color_primaries=bt709:color_trc=bt709:
colorspace=bt709:range=tv` - frame-side parameters propagate to codecpar and thence
to the muxer's colr write, which is the exact hole this probe isolated. Gate the
calibration with the same byte-level colr parse (expect nclx 1/1/1, full_range=0),
ffprobe-8.1.1 stream check, and SPS trace. Freeze the smallest successor transaction
only after a synthetic frame passes all three.

Standing Phase 36 gates unchanged: c03 audio repair with the human-audible-noise
proxy gate; F248 (now +F081) lid fix verified in frames; VUI metadata path proven.
- Claude
