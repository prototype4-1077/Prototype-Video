# The Twelve-Dollar Mug — continuous right-hand coffee action

Watch `coffee-continuity-review.mp4` at normal speed, with sound.
Old action is on the left, new on the right, one shared audio excerpt.
The excerpt spans 22.033–31.000 s of the 38-second film. It includes
the end of the reaction before the action and the cut to the closer.

June sets down the pencil, reaches for the pot, lifts with his right
hand while his left steadies the mug, and brings the pot back to its
starting point before releasing. The pot is already parked to the
left of the mug when the scene begins. The handle stays to the left
through lift and return. No grip is mirrored. This integrates the
earlier silent experiment in context; it does not replace the locked
pour. The pencil set-down is still shown before its line of narration
in this retrospective telling, as in the original timing.

## Evidence and rebuild

- `decoded-before-after.jpg` shows decoded full frames 678, 704, 711,
  719, 726, 732, 738, 754, 788, 789, 863, 864, 886, 900, 906, 911, 912.
- `decoded-contacts.jpg` shows the hand and prop junctions from
  decoded frames 711, 716, 727, 730, 734, 736, 751, 905. Tests cover
  exact shared grounded endpoints, stationarity of the pot body/mug
  before the lift, and both splice boundaries. The pencil and finger
  contours receive a close-crop review, not a claim of photoreal motion.
- Only two closed segments were encoded: [678,789) and [864,912).
  **981** other AVC packets and all AAC and optional caption packets
  match the exact pencil-continuity cut. All **303** protected frames
  decode byte-for-byte exactly, and the MOV audio is exact PCM. The
  two same-angle joins have decoded RGB mean absolute differences of
  4.20 and 1.61 (previous 5.45 and 3.59). The silent edges of the
  comparison have 30 ms fades; none is applied to the complete film.
- `verification.json` pins the results, stages, artwork and code.
  `new-native-digests.json` indexes the two replacement segments.
  These checks do not establish human acceptance.

The complete local candidate is
`outputs/edit/june-full-coffee-continuity-v1/twelve-dollar-mug-coffee-continuity-v1.mp4`
under the parent workspace. The replay recipe uses the exact pencil
candidate as input (see `june_pencil_continuity_v1/` to rebuild it):

    python -m pipeline.cartoon_coffee_cut --before PENCIL_CANDIDATE_MP4 --output NEW_DIRECTORY

There is no new default, production export publication, or main
promotion. Next judgment is the **full cut at normal speed**, especially
the junction from the close reaction into the coffee action and into
the closing line. Only after that review choose between a missing
visitor reaction, a pacing change or a voice pass.

## New ink and paint

These are unchanged outputs of the built-in image tool; no paid
API or key was used. The renderer localizes these edits to the right
arm and pencil; only animates the pot during pickup/pour/return. No
rejected art was edited or used.

`concept/style_frames/june-gs060-right-grip-parked-v1.png`, edit
target `june-gs060-right-grip-grounded-v1.png`:

> Use case: precise-object-edit. Image 1 is a 16:9 production cartoon keyframe. Draw the instant AFTER June has released the grounded coffee pot and withdrawn his right hand. Change ONLY the skin and denim on the screen-left forearm from the elbow forward. On the viewer's left, the near anatomical right arm now angles down and left from the SAME shoulder and elbow, to a relaxed palm-down right hand with softly extended fingers hovering just over the ledger, no longer touching the pot. Hand centroid approximately x31%, y83%; fingertips can approach the resting pencil but don't touch it. Thumb is near his body in this palm-down orientation, not an extra digit. Reveal the complete handle where it was behind his hand: one single uninterrupted C-shaped dark curved handle, on the left of the pot, merging seamlessly into the visible original top and bottom ends at the exact same points. Do NOT move, resize, yaw, recolor or redesign the pot; keep the exact lid, spout on the right, vertical orientation, and foot and contact shadow at the same pixels. Keep the single yellow pencil, ledger, coffee mug, his left hand and cuff bracing the mug on the viewer's right, face, eyes, head, lighting, fabric, wood, porch and camera unchanged. No other edits, no text, no new objects, no mirror.

`concept/style_frames/june-gs060-right-grip-pencil-v1.png`, edit
target `june-gs060-right-grip-parked-v1.png`:

> Use case: precise-object-edit. Image 1 is an already registered production cartoon still of June with his anatomical RIGHT hand resting above the ledger on the viewer's left. Change ONLY that hand, adjoining cuff, and the one yellow pencil. Capture the matching pose a moment before he sets the pencil down: right hand directly above the same ledger using a relaxed, clearly three-finger writing grip, thumb and index oppose around the shaft and middle finger supports it. The graphite tip is pointed down and slightly right, hovering just above the ledger. Eraser on the upper left. The pencil is the SAME single yellow pencil as in the input, now in the writing hand; none stays on the ledger. Keep the wrist and cuff near the same spot as the input, with a tiny natural lift, retaining all right-arm anatomy and that shoulder connection. Do not cover or move any part of the coffee pot or its exposed left handle. Keep the pink eraser, yellow shaft, natural pencil length, the unchanged right-facing spout, left hand bracing the mug, grounded contact, ledger, character, head, gaze, background, lighting, camera and crop exactly the same. No new objects, extra hands or digits, text, mirror or camera movement. Only draw this one pose.
