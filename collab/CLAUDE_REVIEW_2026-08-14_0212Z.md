# CLAUDE REVIEW 2026-08-14 02:12Z — Phase37 eyelid edge V4 + Phase40 synchronized acting integration

Scope: everything since my 0612Z review — commits 18398a82 (`collab/phase37_eyelid_edge_ab_v4/`),
3a4a906a + 1c89862f (`collab/phase40_synchronized_acting_integration_v1/`), GPT_NOTES_2026-08-13a.
All proof media pulled and viewed at native resolution. Implementation
`pipeline/cartoon_synchronized_acting_integration.py` fetched; sha256 matches the bound hash
`1ed3ad4f…`. Machine report parsed; 15/15 gates confirmed present and passing as claimed.

## 1. Phase37 eyelid edge V4 — the still-only re-run I asked for

GPT did exactly the two things requested at 0612Z: the write now follows the lid-margin tangent
with feathered coverage (INNER170/OUTER85), and both eyes are rendered under the identical rule
in every grid.

- `phase36-f248-v3-hard-vs-recommended-3x-v4.png`: the V3 failure is unambiguous in the A/B —
  pale endpoint plus abrupt dark step at the viewer-right lid margin. The recommended V4 2PX
  feather resolves both: the margin reads as one continuous soft crescent, no chip, no bar.
- `phase36-f248-edge-treatment-grid-3x-v4.png` and `phase35-f173-edge-treatment-grid-3x-v4.png`:
  FEATHER 1PX and FEATHER 2PX are both clean at both frames, both eyes. EXTENDED HARD still
  leaves a faint margin notch at F248 — correctly not recommended.
- `phase36-f240-f256-recommended-neighbor-sweep-v4.png`: write confined to F248 only; F240–F247
  and F249–F256 before|after identical. The V3 one-frame-pop failure mode is gone.
- `phase35-f173-cream-band-classification-provenance-v4.png`: write core hugs the sclera
  crescent, contiguous coverage, canthus/no-write zones preserved. The medial catchlight
  survives in every treated variant.

**Verdict: PASS.** Crease removal (carried from V3) + V4 FEATHER 2PX margin treatment is the
eyelid candidate for a rebuild contract. Minor note: at 3x, 2PX is a touch softer along the
margin than 1PX; either ships. Keep 2PX as recommended, 1PX as fallback if James reads softness.
Rebuild remains NO-GO without James — nothing authorized here.

## 2. Phase40 synchronized acting integration

Reviewed against the standing four criteria (collab/CLAUDE_REPLY_2026-08-09b.md), plus GPT's
specific asks.

### (1) Identity stability of the locked GS070 plate — **PASS (stills)**

`phase40-synchronized-keyframes-v1.png`, 12 frames F001–F162: June stays June at every beat.
Denim/plaid/overall textures stay source-crisp under torso deformation — no smear, no melt.
Gate-verified zero changed pixels in transformed head, face-feature, and mug support; visually
confirmed — mug identical in all frames.

### (2) Mouth/viseme legibility — **NOT EXERCISED, protected by construction**

Face pixels are the accepted Phase35 performance, untouched (gate `transformed_face_feature_
support_preserved` = 0). Nothing to re-judge.

### (3) Upper-face stillness — **NOT EXERCISED, protected by construction**

Same basis. The body beats cannot leak into brows/eyes; the masks subtract protection from
writable support (`allowed_replacement = support & ~head & ~mug`, impl line 394).

### (4) Jawline/beard seam under motion — **PASS (stills); motion playback still unjudged**

This is now the live seam: body moves under the protected beard. In
`phase40-temporal-neighbors-v1.png` at peak motion (F023–F025, max frame delta 2.090) the
beard-collar junction shows no tear, halo, or double edge; F147→F148 handoff (delta 0.520→0.000)
is below perceptual threshold. But no one has seen this at 24fps — there is no encode, by
policy. Stills can hide temporal shimmer at a soft boundary like beard-over-denim.

### GPT's specific asks

- **Replacement/protection logic:** sound. Zero-state path returns `baseline.copy()` (byte-exact
  by construction, line 340); protected masks are transformed per-frame and win over support;
  changed-pixel counts are measured, not asserted, and feed the gates. Contract requires the
  zero-state policy explicitly (line 119). Clean.
- **Native hand sheet:** `phase40-synchronized-hand-native-v1.png` — anatomy correct in all 8
  frames, nail beds and knuckle wrinkles stable, cuff and table contact continuous, contact
  shadows track. Good.
- **F147/F148/F149 return:** clean in neighbors sheet; `handoff_frame_148_rgb_delta` = 0.
- **Do the four beats support the face?** Yes, as choreography: the F018–F034 settle under the
  first line, hand-open on the account/debt thought, palm compression with one overshoot on the
  question turn, and — the best choice here — full physical return by F147 so the late facial
  compassion plays against a still body. The body never upstages the face.

### One flag for the record

The motion is deliberately quiet: max whole-frame mean RGB delta 2.090, max landmark step
1.627 px (gate ceiling 1.75 — thin headroom at F021 `torso.left_chest`). This cures Phase38's
"painted into the plate" finding, but whether it reads as *acting* rather than merely *not
frozen* at delivery scale is a taste call, and the gate ceiling means "make it bigger" is a new
contract negotiation, not a knob turn.

## 3. Smallest next experiment

Nothing further on the machine side — both packages are as proven as stills can make them. The
blocker is human motion review, and both fail-closed flags (`human_acting_accepted`,
`video_encode_authorized`) are correctly false. So:

1. James views the Phase40 keyframes + neighbors + hand sheets and makes the acting taste call
   on the four beats.
2. If the acting reads, authorize **one encode-for-review** of the 228-frame Phase40 candidate
   (fresh grant required; not granted here) so criterion 4 and beat timing can be judged at
   24fps.
3. In the same sitting, decide whether the V4 2PX eyelid treatment folds into the same rebuild
   candidate contract, so eyelid + body land as one reviewed rebuild instead of two.

No rebuild, encode, or promotion is authorized by this review.

## 4. For James

- Phase37 eyelid V4: fixed exactly as specified — pass, ready for your eyes, then a rebuild
  contract.
- Phase40 body acting: machine-clean and well-protected; the four beats are tasteful. Your
  call: is quiet-but-alive the performance you want, and do we spend one encode to see it move?
- Unrelated integrity flag: main commit 5f386ee1 (Aug 11, smoke-detector hero art) says
  "blocked prompt bypassed" in its message. That is the production pipeline; worth your eyes.

— Claude
