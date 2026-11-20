# The Twelve-Dollar Mug — arrival and return

Watch `visitor-return-review.mp4` at 1× with sound: original on the
left, new staging on the right. The 10.3-second comparison starts on
“Returned neither” and ends during the cut to June's ledger scene.
The short clip uses shared original narration. The 39.7s alternate
does not add, remove, or re-encode any audio or captions.

This replaces only GS030 (F225–395, 7.500–13.200 seconds). The visitor
lowers the mug with his right hand, sets the pie down with his left,
then looks toward June. June is narrating off-screen; the visitor's
mouth stays closed. The props have independent rigid layers and
contact shadows; neither animation mirrors an existing hand.

`decoded-visitor-return.jpg` shows F224, 225, 270, 291, 309, 329, 344,
352, 360, 367, 379, 395 and 396, left to right, top to bottom. The
photos show distinct table contacts. There is a soft edge at the
left fingers near pie contact (F344), and the pie is out of sight
when we cut to June (F396). These are open viewing questions, not
continuity approval. The opening is narration over an already-present
mug; the arrival insert reads as a recollection, not a literal
forward-in-time sequence. Screen it with adjacent cuts.

## Evidence and rebuild

- `visitor-return.mp4` is the standalone, silent 171-frame shot.
  `visitor-return-proof.json` holds the source and native RGB hashes,
  pose events, dimensions and movie digest.
- `visitor-return-integration.json` records the separate 39.7s
  alternate. 1,020 decoded frames and encoded packets outside
  the shot are byte-exact; all 171 source shot packets occupy their
  intended clock positions. 1,905,600 stereo pairs are identical
  after decoding (plus the same 64 silent AAC padding pairs).
  The complete encoded soundtrack and captions are unchanged.
- The full alternate is local at
  `outputs/edit/june-full-visitor-return-v1/twelve-dollar-mug.mp4` in
  the parent workspace. The two 38s cuts, the 39.7s baseline, review
  launcher, artwork gates and protected delivery paths were not modified.

```text
python -m pipeline.cartoon_visitor_return --output NEW_SHOT_DIR
python -m pipeline.cartoon_visitor_return_review --before EXACT_PAYOFF_MP4 --pcm EXACT_PAYOFF_WAV --shot-dir NEW_SHOT_DIR --output NEW_REVIEW_DIR
```

No production release or human acceptance. Next: screen the hand-off
to the ledger, then use a motivated reaction insert or tighter reverse
only if the pie's disappearance pulls attention. Keep this alternate
intact as the comparison.

## Key provenance

Two original RGB bitmap keys for this shot. Generation used the
in-app image tool with no cash purchase. No new service or account.
For carry, image inputs were the GS040 performance end key (porch
and lighting), GS050 visitor knee key (jacket), and GS070 coffee
approach key (mug). For returned, the exact new carry image was the
edit reference. These are not claims that the images match pixel for
pixel; one fixed background, independent prop and arm mattes, and
a localized eye patch are used in the renderer.

- `concept/style_frames/june-gs030-visitor-carry-v1.png`:
  `054367eb22d00489a973a2a18ca02c1fd3c9a04f61ffa06f0f610e2f570f674d`
- `concept/style_frames/june-gs030-visitor-returned-v1.png`:
  `3b96e5fedf088598a74df946b0e62e9eaeb54bf578c07376d193c9b222cbacda`

Carry generation prompt:

> Use case: illustration-story. A polished 16:9 theatrical-cartoon keyframe for a new shot: the adult male visitor has arrived on June Oxley's porch to quietly return the borrowed mug and bring a homemade pie. Input 1 is STYLE/LOCATION reference only: match the warm evening weathered rural wood, amber light, lantern and painted cinematic rendering, but June is OFF CAMERA to viewer-left. Input 2 is the VISITOR'S right-hand and clothing reference only: same faded russet heavy canvas jacket and olive work trousers, no blue denim. Input 3 is MUG DESIGN reference only: one worn straight-sided cream enamel mug with cobalt rim, a clearly readable familiar front chip, shaped handle, empty. Visitor is NOT June: a middle-aged roughly 45-year-old farm-supply worker with short dark-brown hair with modest gray at the temples, very short stubble, stronger nose and sober tired eyes, tender rather than threatening; no white beard or hats. Medium three-quarter shot including the adult visitor's head and both elbows and the tabletop across the lower quarter. He is center-right, oriented toward June offscreen left, eyes looking shyly down at what he brought. A natural slight forward lean. His anatomical RIGHT hand, attached to the viewer-left shoulder, holds the mug handle in front of him at viewer-left, thumb above the loop, ordinary natural fingers, mug upright; mug base is a clearly visible small distance ABOVE the table as he begins lowering it. His separate anatomical LEFT hand supports a small round golden lattice-crust pie in a dark simple tin from UNDER its right half, at viewer-right, above table and NOT hiding the first hand or mug. Pie upright and level, no slice removed. The objects and both hands are visibly distinct, no duplicate limbs or objects. Hands, prop bottoms, and their exact table landing areas fit within frame. Same environmental light and high-end stylized painterly textures as the cartoon, not a live-action photo. No ledger, coffeepot, additional furniture action, crowds, labels, rope, food outside pie, titles, text, or watermark. One still, no split panels.

Returned edit prompt:

> Use case: precise-object-edit. Image 1 is a locked widescreen theatrical animation frame with the visitor returning a mug and pie. Make the exact final key of the same shot: both objects now rest on the same wooden table, visitor has just let go. Only edit the wrists/forearms, prop height and the direction of his eyes. KEEP the fixed camera, tabletop front/back edge, room, porch background, window, lantern and light. KEEP the identical visitor head shape, hair, age, canvas jacket and proportions, no changing where his torso is. Mug and pie have the same width, texture, orientation and X position. The empty chipped cream mug at viewer-left has been lowered roughly 48 px on an image 941 px high, to sit firmly at y~92% with its original handle on the viewer-left and front chip visible, not tipped. The golden lattice pie in the same dark tin has lowered roughly 104 px to rest beside it on the viewer-right at the same y~92%, serving tin grounded with a natural thin contact shadow. The visitor's anatomical RIGHT hand at viewer-left is clearly not gripping: opens a little off to the left of the mug, a small gap between fingertips and handle. The anatomical LEFT hand at viewer-right is no longer underneath the pie, fingers open and visibly clear at the right side, on or just above the table, not cut out. Both cuffs and elbows stay attached to the same arms; no extra digits or limbs. A modest gaze upward-left to June off camera, restrained and slightly apologetic, mouth closed, no big smile or face movement. No new objects, no steam, no change in crop, no re-style, no text.
