# GPT NOTES 2026-08-09d - Phase 34 candidate-04 ready for eyes

Answer to the articulation question: deterministic 2.5D piecewise-affine source-texture
deformation driven by A-H/X parameter vectors. It is not per-frame regeneration and it
does not swap full mouths or faces. GS070 remains the only identity texture. A registered,
identity-free oral-interior atlas supplies cavity/teeth/tongue material underneath June's
source-derived upper/lower lip ribbons, moustache, and beard.

The review package is complete and no video encoder exists yet.

- Public repo evidence: `collab/phase34_candidate_04/`
- Local package: `../../outputs/edit/phase34-source-textured-visemes-preview-v1-candidate-04`
- Key sheet: `june-phase34-source-textured-visemes-key-poses-v1.png`
- All transitions: `june-phase34-source-textured-visemes-transitions-v1.png`
- Mouth poses: `june-phase34-source-textured-visemes-mouth-poses-v1.png`
- Upper-face differences: `june-phase34-source-textured-visemes-upper-face-differences-v1.png`
- Delivery scale: `june-phase34-source-textured-visemes-delivery-scale-v1.png`
- F/H/H-to-X: `june-phase34-source-textured-visemes-articulation-specials-v1.png`
- Public LF-normalized manifest SHA-256: `24b544226fd7ebcb21183204a9e6134bd49534f19d4ddc2517dda6bc16d8fd4b`
- Local rendered manifest SHA-256: `674a116201d4c5a74896750eb36ad7d00e272d8335948057268befa72804d4c7`

Machine result: every pre-encode gate passes across 96 native-24-fps frames. Viseme-driven
changes above the alar lock are zero in native pixels and zero in final output after the
declared four-pixel Lanczos guard. Worst temporal local delta is 148.344 under the 150
ceiling and occurs during the blink, not speech. The formerly worst B-to-C oral swap is
139.724 after the sharpened registered blend.

Please judge the four agreed items and cite cells/frames: identity stability, 24fps mouth
legibility, upper-face stillness, and jaw/beard seam. Also inspect B>C F032-F035, F-contact,
H-tongue, and H>X. A review must bind the exact public manifest/evidence directory before one silent
encode can be implemented. James remains the final taste gate.
