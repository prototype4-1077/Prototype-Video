# GS060 — grounded right-hand lift and return

Play `grounded-lift-study.mp4`. This is a silent, three-second action
study at 1080p30: settle, lift, hold and return. No version of the full
cut, recorded pour, caption track or protected picture has changed.

The old tabletop pose put the left hand on the pot and the right
around the mug, then switched both jobs at lift-off. The new grounded
pose puts June's anatomical **right** shoulder, sleeve, wrist and
knuckles on the left of the picture, following the same handle he
holds in the existing lift drawing. His left hand still braces the
enamel mug. The pot is now parked just to the mug's left, not at the
legacy far-right spot. The spout is on screen right in both poses.
The marked pot base rises by about 199 native pixels and moves only
13 sideways; the old registered drawings would require a roughly
500-pixel sideways jump.

The first draft warped both entire painted poses and produced doubled
denim and a second ledger edge mid-swing. It was rejected. The study
uses one articulated arm + pot silhouette registered to corresponding
landmarks, a stationary painting underneath it, and the mug in front
where needed. The figure and environment do not dissolve with the
pot. Frame 34 uses the exact existing raised pose at native size.
Matched matte regions disengage from the table shadow as the pot
rises and settle back to the same parked position. Small changes in
jacket texture are still possible; registration tests don't approve
normal-speed acting or prove a physically rigid 3D prop.

The decoded contact sheet samples F8, 18, 22, 30, 34, 64, 75 and 77.
All source SHA-256s, encoded proof hash and 90 native RGB hashes
are in `lift-study-proof.json`. Local reproduction:

    python -m pipeline.cartoon_grounded_coffee --output NEW_DIRECTORY

## What remains for the full cut

The legacy pencil-up and pencil-down plates still park the pot on the
opposite side of the mug. Do not drop this study directly into those
plates. Next, make a parked pot cel with an unobstructed handle and
restage those positions. Animate the reach from the ledger into the
grounded grip, and release back to neutral after the pot settles.
Keep mug and ledger positions, cut clock, continuous sound and all
original protected frames (F789–863 and F912–1139). Verify the
full joins [678,789) and [864,912) before use; the rest can be copied
unchanged. No human or production approval is claimed.

## Artwork provenance

New asset: `concept/style_frames/june-gs060-right-grip-grounded-v1.png`.
This is the unmodified 1671×941 RGB output of the built-in image tool
with the existing `june-golden-scene-gs060-performance-pot-lift-v1.png`
as the edit target. No paid API or key was used. The renderer normalizes
the one-pixel width difference during loading, then masks only the
moving arm and pot. Exact prompt:

> Use case: precise-object-edit. Edit Image 1, the existing finished 16:9 June Oxley porch animation still at the start of the right-handed pot lift. It is the exact production style, facing direction, character and camera. Make its preceding key drawing, the instant just BEFORE the lift, with the coffee pot standing firmly on the wood. Move only the right forearm, its hand and the pot down to the tabletop; naturally articulate the elbow and cuff, don't simply bend the wrist. Pot base center approximately (51%, 89%) of frame, immediately screen-left of but separated from the enamel mug. At the table the pot is upright, SAME tall dark worn metal pot, lid knob, loop handle on SCREEN LEFT, and spout on SCREEN RIGHT pointing toward the mug. Keep the real anatomy: the upper sleeve on the viewer's LEFT (June's right shoulder) leads uninterrupted into the wrist of the hand gripping the pot's left-side loop handle; same overhead thumb and plausible curled fingers as Image 1, not on the spout or body. June's other, LEFT hand and denim cuff stay exactly where they were in Image 1 on the viewer's RIGHT, bracing the mug, which does not move or change size. Both bases clearly meet wood with short plausible contact shadows, and are not intersecting. Nothing else changes: same downward gaze, head, denim, lighting, porch, framing, perspective, chipped mug, ledger and single pencil resting on it. No text, extra props, fingers, duplicate pot, mirror image, vertical camera shift, or new composition. This is a single registered theatrical cartoon keyframe, not a redesign.
