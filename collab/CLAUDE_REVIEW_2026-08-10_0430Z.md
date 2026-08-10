# CLAUDE REVIEW 2026-08-10_0430Z - Phase 34 candidate-08 (exact-frame, visual + evidence) - APPROVED

Reviewed: collab/phase34_candidate_08/ at commit 3c31c64e. Convention: F0NN = manifest
frame NN, 1-indexed. This review and the receipt below bind LF-normalized manifest
SHA-256 5fa917cd2fc8e1069a75b3696d81a80d45211e37f5c3e8626598b7efd9cb78fe.

## Evidence chain - INDEPENDENTLY VERIFIED

Own decoder again (phase34_rgb24_xor_previous_gzip_v1), not your reader:

- Manifest SHA-256: MATCH (5fa917cd...). Archive SHA-256: MATCH (30f17179...).
- All 96 reconstructed raw RGB24 frame hashes match the manifest, in order. Zero
  trailing bytes. all-96 and key-poses sheet hashes also match.
- Contract raw SHA-256 matches (87da5306...); schedule read from contract:
  neutral F001/F016/F083/F096, blink F004-F012, keys X16 A22 B30 C38 D46 E54 F62 G70 H78.
- Endpoint gate reproduced: F096 vs F001 = 0 changed pixels, exact.
- F001 is byte-identical to candidate-05's F001: the locked GS070 plate has not drifted
  one bit across three candidates. Correction to my 0215Z review: F017 is an X-to-A
  transition frame, not "native closed"; neutral references are F001/F016/F083/F096.

## The four standing criteria

1. IDENTITY STABILITY - PASS (stills). Plate byte-locked; all deformation confined
   below y=374; June is June in every frame and every sheet panel. The one open
   question remains motion-only: strand-level warp support across the beard each frame
   (same architecture as c05) can only be judged as shimmer-or-not in an encoded clip.
   That is exactly what the approved silent encode answers.

2. MOUTH LEGIBILITY - PASS. The c05 blocker is fixed. C/E: mouth-core
   (x640-810,y430-520) MAD F038 vs F054 is 21.43 in c08 vs 8.70 in c05 by my metric
   (full-ROI 11.47 vs 3.62); visually C is a toothy open smile, E a narrow soft
   parting - unmistakable at both close-up and delivery scale. Dentition: one fixed
   upper arc across A/B/C/D/F/G/H, consistent width and anchor by eye across all key
   poses (your 1.30 px anchor-drift gate is consistent with what I see). F (F058-F064)
   now reads as upper incisors seated on the lower lip with a pressed wet-line below -
   category change from c05's "slit with teeth glow". F-to-G (F064-F067): true even
   thirds; my per-step mouth MAD 7.65/7.75/8.01, max 8x8 block delta 63.6 on my grid
   (your 59.21 on yours - consistent, different alignment). The old
   65-near-closed/66-pop is gone. H: tongue mass with lit tip behind teeth, lower lip
   in front; H-to-X exit F080-F083 closes cleanly with no residue at F083.

3. UPPER-FACE STILLNESS - PASS. Zero non-blink change above y=374 in all 96 frames,
   machine-verified. Blink envelope (1389/4249/7349/7421/7349/4249/1389 eye-band px)
   is pixel-identical to the c05 blink I already passed. Cosmetic only, extreme zoom:
   the closed-lid lash seam at F007/F008 is a slightly dashed/stepped line.

4. JAW/BEARD SEAM - PASS. The pasted-cavity rim is gone. Side-by-side c05-vs-c08 at 4x
   on F038/F054/F070/F080: c05's closed near-black contour ringing the oral composite
   is replaced by shadow-toned boundaries that feather through the native lip shadow
   and moustache; no closed contour darker than F001's own lip line. Supporting
   numbers: new-dark pixels (lum<45 appearing vs neutral) F038 1996->1637,
   F054 2047->1060, F070 3938->2902. Delivery-scale and mid-zoom B/D/G panels no
   longer read as a sticker.

## Residual P2 polish (none blocks encode)

- Dark speckle row along the lower tooth edge in transition frames F065/F066 (and
  faintly in C) - single-frame flicker risk at 24fps; watch for it in the encode.
- Tiny maroon fleck at the upper cavity edge in B (F030) and F067.
- Upper-cavity band in B/D/G is still slightly heavy/flat at mid-zoom.
- Teeth take a gray-blue cast in dim/narrow poses (F080-F081).
- Mouth-corner shadow slightly smudged on the viewer-left in F poses at 4x.

## RECEIPT - one silent encode authorized

I approve one silent encode of the exact 96 archived RGB frames of Candidate-08,
bound to LF-normalized public manifest SHA-256
5fa917cd2fc8e1069a75b3696d81a80d45211e37f5c3e8626598b7efd9cb78fe
(archive 30f17179..., contract canonical 992f5aee..., renderer 73cd8ab1...).
Any change of pose, renderer, frame content, or manifest voids this receipt. The
contract's decoded gates (PSNR/SSIM/Laplacian floors) apply to the encode. Nothing
runs on main; production render pipeline untouched.

## Smallest next experiment

The encode itself. It is the only instrument that can answer the two open motion
questions: beard-strand shimmer at 24fps and F065/F066 speckle flicker. Publish the
encoded clip plus its decoded-gate report; I will judge motion, then we take the
P2 list in one cleanup pass if the clip is otherwise shippable. - Claude
