# The Twelve-Dollar Mug — the original loan

Watch the 8.53-second `opening-loan-review.mp4` at normal speed.
Original on the left; visible borrowing on the right. It starts
on “borrowed twelve dollars” and continues into “Three years later”
and the mug's return, so the repeated prop carries both scenes.
June's establishing wide is unchanged. The insert does not show a
transfer of money; the visitor already holds the folded cash.

The earlier mug close-up (F129–224, 4.300–7.500 seconds) is replaced by
the same visitor collecting it from the porch table. His anatomical
left hand reaches for the handle, secures it at F156, and begins to lift
after F158. By F173 the cup is clear of the table; he draws it slightly
back through F211. Cash stays in his anatomical right hand throughout.
He later returns the mug with his other hand. Neither grip is mirrored
or reversed. The cup and its chip travel rigidly; the sleeve is anchored
toward the shoulder. Cooler daylight, a different framing, the visible
cash, and no pie distinguish the loan from the later return.

The first render exposed a blurred patch on the table as the mug
rose. The review render restores grain from the same plank with a
local feathered match. The expression remains held during this
3.2-second insert. Keep this as a reversible story test: stills and
exact-frame checks are not a normal-speed acting verdict.

## Rebuild and evidence

```text
python -m pipeline.cartoon_opening_loan --output NEW_SHOT_DIR
python -m pipeline.cartoon_opening_loan_review --before EXACT_LEDGER_REVERSE_MP4 --pcm EXACT_PAYOFF_WAV --shot-dir NEW_SHOT_DIR --output NEW_REVIEW_DIR
```

- Build receipt: `opening-loan-proof.json`, with native RGB hashes for
  all 96 frames and the hashes of both original bitmap keys.
- Integration receipt: `opening-loan-integration.json`. The 39.7s
  alternate is local under `outputs/edit/june-full-opening-loan-v2/`
  in the parent workspace. All 1,095 outside picture packets and
  decoded frames are unchanged. Narration and captions are
  packet-identical; all 1,905,600 decoded stereo pairs match.
  The comparison uses shared narration with silent 30ms fades.
- `decoded-opening-loan.jpg` samples F128, 129, 142, 151, 156, 162,
  173, 186, 211, 224, 225, and 291, left to right, top to bottom.

The earlier cuts, approved audio/eyes, rejected evidence, review
launcher, and main branch are not changed. No human verdict.

## Keyframe provenance

Both new sources used the in-app image tool, with no cash payment.
The lift key referenced the existing visitor carry shot for identity
and clothing, the coffee exchange approach for the mug, and the
GS020 style target for the porch. The reach key is a local art edit
of the lift key. The render holds just one set/world plate.

- `concept/style_frames/june-gs020-loan-lift-v1.png` —
  `e2d93068f61d2538ebe54e10e8c601446fb71b889986ad451c73119e12f0998c`
- `concept/style_frames/june-gs020-loan-reach-v1.png` —
  `40450dfe54cba2652a897442eb153f9dcfe3b7d793a936915c4e55822ae0a944`

Lift generation prompt (had a hand-side request; the actual image
was verified as left hand on mug and right on cash, not anatomically
backwards; the open key and motion follow that verified pose):

> Use case: illustration-story. New 16:9 production keyframe from the polished painterly cartoon, a recollection of the moment June lent the feed-store man his enamel mug and a few dollars. Input 1: exact visitor identity and dark rust-brown canvas jacket; use his same mid-40s face, dark swept hair and stubble, but this is a different camera angle on a different morning. Input 2: prop/design reference for the single empty cream enamel mug with dark cobalt rim and subtle front chip (no coffee, no steam). Input 3: June's porch wood, jacket texture and lighting style only. Tight medium shot from June's side of his porch table looking toward the visitor, table in the lower quarter; the visitor is turned three-quarters toward screen left with face and right forearm shown full. Very soft clear morning side light, cooler than the other porch scene but the same woods/porch and illustration style. June is not on camera; no part of him is necessary. Visitor is gently collecting the mug, not returning it. Visible anatomical RIGHT hand, arm anchored to his own rust-brown cuff entering from screen-right, with the thumb up, fingers actually curled through the clearly readable right-facing mug handle. Wrist and forearm run continuously from his body into the grip. Grip on HANDLE only, hand must not wrap around body. The mug is upright in his right hand, its entire empty rim and base clearly visible lifting a few inches up above an unobstructed visible tabletop. Mug at screen x 46%, y 74%; hand attaches to its right only; keep the handle, hand, base freely visible and keep them well inside frame. His other hand, low detail and at least one mug width away, lightly holds a small folded set of muted green banknotes against his jacket; not offering money back, no readable print or labels. Mouth shut, looking toward June off frame to viewer left, a little bashful, not grinning. Keep attention on empty mug, hand and gap to table; no pie, no ledger, no other props, no graphics, no text, no border. One finished 16:9 cartoon keyframe, vivid expressive caricature shapes and detailed painterly textures, not a live-action photograph.

Reach edit prompt:

> Use case: precise-object-edit. Make the earlier frame of exactly this same shot. This man is just about to take the loaned empty mug from the tabletop. KEEP identical 16:9 crop and exact camera, character identity and pose except one forearm, porch background, window, table and lighting. KEEP his folded paper money in the screen-left hand absolutely unchanged. KEEP left-side cuff and fingers around money exactly. ONLY edit the mug & his other arm (the anatomical LEFT arm on the screen-right of frame). Lower the same upright mug down by about 80 image px and move it slightly LEFT about 38 pixels so its bottom truly rests ON the horizontal tabletop with a narrow natural shadow. Preserve identical dimensions, empty cream interior, deep cobalt rim with the front chip, and one free, entirely visible empty handle on the RIGHT side of the mug. The man's hand on screen-right is lifted just clear of that handle (gap of 30–50 pixels), relaxed but visibly reaching toward it, natural thumb on top and fingers not yet closed. Keep intact connection to same rust-colored right-side cuff, same general forearm pose and sleeve profile, shift only necessary forearm/hand pixels. One mug only, tabletop and the full mug bottom visible, no new props, labels or letters; same finish. Face, cash hand, room, and all lighting that does not have to change: unchanged.
