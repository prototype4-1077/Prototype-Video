# GPT notes: Candidate-07 measured-articulation milestone

Candidate-07 is preserved for exact-frame comparison, not offered for encode approval.

Evidence: `collab/phase34_candidate_07/`

- Local manifest SHA-256: `2127d59f0cbd1247fb858f8a0edf43b8ccf357602695502185974120fe389ff9`
- LF-normalized Git/public manifest SHA-256: `3d23700d47ecbf2d3384f0f41eaffe3b69f196cbbbdf9ac9a6a9cf32f0bc0cce`
- Lossless RGB archive SHA-256: `0fd9137f3756efecc94e89a5a97d5603c08290ff8843415190c0036d302f94de`
- Contract canonical SHA-256: `3ace2fa14cf4ce32fff803a711dbb6b747989cda27cbbf2924a4853d94db60c6`
- Renderer SHA-256: `2faf32a261c4588370cc0f4df8d142cb70b44c74ea724ee36187f79f095c9429`

What improved versus candidate-06:

- Every lower-face layer records actual alpha writes at the declared 1/255 threshold and
  assigns final ownership on the same support. Frame 82 now proves 84 oral writes.
- F has a dedicated source-textured lower-lip/canonical-incisor contact layer and measured
  incisor visibility, contact length, cavity height, and F/X separation.
- H has a shaped textured tongue tip, center groove, and measured lower-lip overlap.
- The F-to-G overlap retains F contact while beginning the G cavity.
- H-to-X closes cleanly; C/E separation and fixed dental identity remain strong.

All 96 archived frame hashes and all seven review-artifact hashes round-trip. Eighteen
focused tests and all preflight gates pass.

Why this is not the review candidate:

- F remains too close to neutral at delivery scale despite its measured anatomy.
- Frame 65 stays near-closed and frame 66 opens too abruptly.
- Flat burgundy cavity corners still read as a composited cutout in C/D/G/H.
- Independent code review found two remaining proof gaps: Phase33 lid soft-alpha/crease
  writes are not represented by the Phase34 coverage/final-owner evidence, and the H
  lower-lip occlusion gate accepts effectively transparent pre-final writes.

Candidate-08 will preserve this architecture, prove exact eyelid alpha ownership, require
meaningful final H occlusion, redistribute F-to-G interpolation, strengthen delivery-scale F,
and derive cavity-edge color/texture from the local source plate.
