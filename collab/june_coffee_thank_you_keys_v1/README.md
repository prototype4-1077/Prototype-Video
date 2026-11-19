# GS070A — the visitor accepts the coffee

Story review of the current cuts: we see June pour and then turn to
the camera. We don't see the visitor accept anything. The pot-repair
and reaction cutaway solve physical continuity and reveal the
visitor's unease, but the act of accepting the coffee is still the
missing response. This is an optional production sketch, not an
approved version of the ending.

Three keys in `concept/style_frames/` share the same table-side
view: `june-gs070-coffee-exchange-approach-v1.png`,
`june-gs070-coffee-exchange-accepted-v1.png`, and
`june-gs070-coffee-exchange-clean-v1.png`. “Accepted” in the filename
means that the visitor accepts the cup; it is not a verdict.
June's denim comes from camera-left, and the same visitor rust cuff
from the reaction insert comes from camera-right. The mug, chip,
handle and coffee need to be **one rigid layer** reconstructed from
the filled receiving body and the unobstructed approach loop. The
approach painting is empty: do not use it for the liquid at any time.

See `concept/scenes/june-coffee-thank-you-keys-v1.json` for pinned
source hashes and the first blocking clock. At 30 fps, June slides the
mug at a fixed table level, the visitor reaches for the handle, and
the hesitation stops on contact before June releases. Render each
arm separately over the clean table; put the visitor's thumb in
front of the handle and the wrapped fingers behind the loop, with
a painted contact shadow. Do not dissolve the whole plate, float
the base, teleport the liquid or add a new sound. Preview at 1× and
judge whether the gesture reads without narration.

The existing edit has only 11 frames between pot landing and the
protected close. Don't cram the exchange into that gap or replace
protected F912–1139 to get room. First stage a separate roughly
1.33-second action proof. If it works, compare a deliberately longer
ending with unchanged existing dialogue words and continuity, and
test whether it earns the extra beat. No cut changed this turn.

## Exact generation prompts

All three are unmodified 1672×941 outputs of the built-in image tool.
No paid API or key. The two input reference assets for the first
stage were `june-gs060-right-grip-grounded-v1.png` and
`june-gs050-visitor-knee-v1.png`, respectively.

Approach key:

> Use case: illustration-story. Generate a new widescreen 16:9 theatrical-cartoon close shot as the matching detail view at the end of this porch scene. Use Image 1 ONLY for the worn amber wooden tabletop, lighting, elderly June's blue denim, and exact hero mug design (cream enamel, cobalt rim, characteristic dark chip at front, one small curved handle on the right). Use Image 2 ONLY for the other adult visitor's distinct worn rust canvas cuff and younger right hand. Same handcrafted naturalistic painted animation, subtle daylight warmth, calm quiet empathy. Camera at a table-side shallow three-quarter angle with space horizontally, looking slightly down. One mug centered near 51% of screen, its flat base at y~76% firmly ON the table, and clear 15% screen-width horizontal room to its right for a subsequent slide. One anatomically correct hand from each person: from screen LEFT, June's elderly left hand with blue denim cuff and back/knuckles visible makes light low contact with ONLY the mug's left side, guiding it right without lifting it or hiding the rim chip; from screen RIGHT, the visitor's separate right hand with rust-brown cuff floats above and just right of the handle, bent thumb above the future grasp and curved fingers separated by a small obvious gap from the handle (hasn't grasped yet). Show both wrist-to-cuff paths and both intentional silhouettes. At this instant the people are not holding hands; they are offering and receiving the cup. Keep one prop, natural proportions and five digits on each hand (a naturally occluded digit is fine; no extras), finger lengths vary normally; the visitor is tentative, not reaching urgently. Sparse soft-focus dark porch behind, no other props, no ledger, logos, text, smoke, faces, or other limbs. Fully painted final-style key, not a split panel.

Receiving key (edited from the approach key):

> Use case: precise-object-edit. Image 1 is the locked wide close-up for a cartoon shot. Keep exactly the same camera, composition, tabletop grain, shadows, background, blue rim with central chip, shape and position of the one grounded cup, and the same two cuffs. Change just the hands as the mug is accepted. June's blue-denim LEFT wrist withdraws toward viewer-left about 13% of image width; his elderly hand opens and stays low with a clear small gap from the left side of the mug, fingertips no longer touching. Do not remove his whole arm. The visitor's younger RIGHT hand wearing the rust cuff moves slightly down and left to wrap exactly around the original cream handle at screen right. The thumb presses the top of the loop lightly, fingertips hook inside/behind it with believable overlapping skin and ceramic, remaining little finger rests naturally below. Same correct orientation and shape of each arm and wrist, no duplicates. Put a shallow level of warm dark brown coffee inside the existing mug, clearly visible from this angle LOWER than the rim, smooth surface, no splash, steam or foam. Mug not lifted or tilted; exactly same bottom pixel position, width, handle and rim. The characters do not touch other than through the mug. Everything outside the two hand regions and inside the existing rim unchanged. No new objects, extra fingers, lettering or crop.

Clean plate (edited from the approach key):

> Use case: precise-object-edit. This is the clean background plate for the exact animation still in Image 1. Remove the central mug and ALL hands and sleeve parts entering from left and right, including their cast shadows. Reveal believable continuous horizontal weathered wooden tabletop grain and the softly out-of-focus dark wooden porch behind those occluded parts. Extend the actual existing wood pattern, table plane, depth, color, directional warm dappled light and focus into the revealed regions. Lock camera angle, framing, table height and every already-visible background pixel as much as possible. No props, no people, no cup, no limbs, no new light source, no text or watermark; one empty scene matching the input pixel layout.
