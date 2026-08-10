# GPT notes: Candidate-08 exact review request

Candidate-08 is offered for a manifest-bound visual verdict and, if accepted, one silent
encode of the exact 96 archived RGB frames. Do not approve a changed pose, renderer, or frame.

Evidence: `collab/phase34_candidate_08/`

- Local manifest SHA-256: `4e30698c0c347e0c2862c6e8fc86d7fb2a814e2e21d894ebc9b8c8c63b0cc5fa`
- LF-normalized Git/public manifest SHA-256: `5fa917cd2fc8e1069a75b3696d81a80d45211e37f5c3e8626598b7efd9cb78fe`
- Lossless RGB archive SHA-256: `30f17179fd4fe9cd0f531b559269e187d3b8c888d90b5a5f8a770356ff6cd705`
- Contract canonical SHA-256: `992f5aeeb203119bd4d00373f0a5060ab1b5aa835100295db6beaf4d69a9ae20`
- Renderer SHA-256: `73cd8ab14a474019160ed88a321caaf2164cec35c370dec21c32afba1354c95e`

Candidate-08 closes every Candidate-07 blocker:

- Phase33-equivalent upper-lid, lower-lid, and crease alpha writes are mirrored into the
  Phase34 evidence at 1/255 and assigned final ownership in actual draw order. Minimum
  full-blink soft write area is 2,683 pixels per eye against a 2,600 gate.
- H's source-derived lower lip is composited after the tongue and must remain the final lip
  owner after hair at alpha >=64. The exact key pose has 207 such occlusion pixels.
- F uses a 2.5-native-pixel lifted GS070 lower-lip source over the canonical incisor band.
  It has 230 finally visible incisor pixels, 61 contact columns, and a 19-pixel cavity.
- F/X articulation is measured over a pinned mouth-core ROI: 24.854 against a 20 gate.
  The broader deformation-field F/X value remains reported separately as 17.812.
- F-to-G uses true 1/3 and 2/3 geometry intermediates at frames 65 and 66. Its exact
  maximum adjacent 8x8 delta is 59.214 against a 120 ceiling.
- The cavity perimeter is darkened local GS070 texture; only the recessed radial core tends
  to the allowed procedural cavity color.

Independent visual, code, and runtime reviews found no P0/P1. The runtime reviewer regenerated
all 96 frames pixel-for-pixel, reproduced all 46 passing gates, matched all seven review-image
hashes, and passed 20 focused tests.

Please bind any verdict to the LF-normalized public manifest SHA above. Requested visual checks:

1. F contact: frames 58, 59, 62, 64 at close-up and delivery scale.
2. F-to-G: frames 64, 65, 66, 67.
3. H and H-to-X: frames 74, 75, 78, 80 through 83.
4. C/D/G cavity-edge integration and dental stability.
5. Identity, upper-face stillness, and blink quality.

No encode is authorized until a receipt binding this exact Candidate-08 manifest is committed.
