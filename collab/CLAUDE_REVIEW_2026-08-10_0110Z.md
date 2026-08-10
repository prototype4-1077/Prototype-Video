# CLAUDE REVIEW 2026-08-10_0110Z - Phase 34 candidate-04 (visual, binding)

Reviewed: collab/phase34_candidate_04/ at commit 5878855a. I independently verified the
public LF-normalized manifest SHA-256:
24b544226fd7ebcb21183204a9e6134bd49534f19d4ddc2517dda6bc16d8fd4b - MATCH.
This review BINDS that manifest and evidence directory.

## The four standing criteria

1. IDENTITY STABILITY - PASS. All 96 frames (all-96 sheet) hold head scale, tilt,
   hairline, wardrobe, and scene exactly; key-pose cells are identical above the mouth.
   June stays June in every pose. The atlas-era boil is fully gone. No foreign identity
   enters via cavity/teeth/tongue material.

2. MOUTH LEGIBILITY AT 24FPS - PASS, one watch item. At delivery scale A/B/C/D/G/H all
   read; F reads near-closed, which is correct articulation for F/V. E is the weakest
   read (your C/E mean delta 5.18 and my eyes agree) - motion context should carry it;
   re-judge on the first encoded spoken line. B>C F032-F035: the registered blend works -
   reads as a natural closing bite, no ghosting, no double teeth. The sharpest adjacent
   step in the speech region is F065->F066 (thin F slit -> G oval); it is legal under the
   150 ceiling but it is the single frame pair to watch once encoded.

3. UPPER-FACE STILLNESS - PASS. upper-face-differences sheet: all eight panels
   changed=0, corroborated by gates (0 px changed above the alar base, native and
   output). Catchlights, brows, and forehead wrinkles are pixel-identical across all
   poses. The blink (F006-F007) is the only upper-face event, exactly as declared, and
   it holds the worst temporal delta (148.344), not speech.

4. JAW/BEARD SEAM - PASS, one note. Moustache correctly owns foreground over the upper
   lip (strands cross the lip line in A/B/D close-ups). No tearing, seams, or double
   exposure in any transition row, including the old artifact's favorite spot, H>X
   F080-F083. Note: minimum_beard_front_overlap_pixels = 0 - the beard never draws in
   front of the mouth. The lower-lip/beard ribbon in G F066-F067 and H F074-F080 is
   clean in stills; that boundary is where to look for shimmer in motion.

## Requested specials

- F-contact F058/F059/F062/F064: pass - teeth glint through the contact line reads F/V.
- H-tongue F074-F080: pass - tongue is a distinct material, broad and legible as L.
- H>X F080-F083: pass - F082's small center gap is a plausible closing moment; F083 clean.

## Decision

One silent encode of this exact 96-frame sequence is APPROVED against the bound manifest -
no new poses, no parameter changes. Smallest next experiment if the encode shows a pop at
F065->F066: insert one easing frame (partial cavity pre-opening) at that boundary only.

For James's taste gate: (a) B's upper teeth run bright/large in close-up - fine at
delivery scale, but his call; (b) whether E earns its slot or should lean closer to C.
- Claude
