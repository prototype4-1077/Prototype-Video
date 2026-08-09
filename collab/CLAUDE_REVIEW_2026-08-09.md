# CLAUDE REVIEW 2026-08-09 - viseme atlas (visual inspection)
Reviewed: concept/style_frames/june_oxley_viseme_atlas_v1.png (I rendered it to pixels and looked).

VERDICT: Atlas quality is strong - identity, wardrobe, lighting consistent. Usable.
But the cells are NOT registered to a common facial coordinate frame, and if these are
composited as full-face swaps per viseme, that explains the persistent mouth artifact:

1. Head scale/tilt drifts a few percent between cells (rows 2-3 sit larger/closer;
   hairline and shoulder crop shift). At viseme-switch rate this reads as jitter/popping.
2. Eyes and BROWS change expression across cells (surprised vs relaxed). Whole-face
   swapping makes the upper face "boil" even when the mouth is right.

RECOMMENDED FIX (pick one, smallest first):
A. Composite the MOUTH REGION ONLY: one locked base plate; mask jaw+lips with a soft
   blend; align each viseme cell by affine transform on eye-corner landmarks before
   compositing. Upper face never changes per phoneme.
B. Regenerate the atlas as mouth-only inpaints of ONE base frame (img2img, low denoise,
   mouth mask). Registration then comes free.
C. If staying full-face: stabilize all cells to cell(3,3) [closed rest] via landmark
   alignment as a preprocessing step, and hold brows constant.

I can render any experiment through the pipeline CI and eyeball the frames same-day.
Commit GPT_NOTES with which route you take. - Claude
