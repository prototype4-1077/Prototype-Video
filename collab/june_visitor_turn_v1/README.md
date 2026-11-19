# The Twelve-Dollar Mug — why June looks down

Watch the **4.67-second** `visitor-turn-review.mp4` at normal speed.
Current coffee-continuity cut on the left; the same cut with the
visitor on the right. One shared audio excerpt. The question is whether
you immediately understand what changed June's mind, or whether the
cutaway spells out a beat that was already clear.

June starts to look down-right. At 20.267 s we cut to the visitor's
right hand resting on his own knee, then back to June at 20.933 s.
The warm rust canvas cuff visibly differs from June's blue denim.
The table edge sets the eyeline; no borrowed or mirrored June art,
no second hand, no new audible cue. The fingers make two uneven
twitches and then curl a little. The wrist, thumb and tabletop
stay planted. The edit leaves 50 frames (1.667 s) on June's settled
look before returning to the coffee action.

`decoded-turn-poses.jpg` samples F563, 564, 602, 607, 608, 611, 616,
620, 627, 628 and 677. Template tracking over decoded 1080p frames
found 11 px of downward movement at the first middle/index fingertip
peak and 7 px at the smaller second peak (both relative to entry).
No measured displacement at the sample points on the anchored thumb,
cuff and table at those instants. These checks show movement and
anchoring, not human acceptance or emotional readability.

## Provenance and changes

- Picture insert only: F608–627 inclusive. We re-encode the original
  closed section F564–677, with 94 other source RGB frames exactly
  matched to the previous render inventory. The other 1,026 picture
  packets match exactly, including the new coffee action. All 303
  protected decoded frames, all original AAC/caption packets and
  the PCM master are exact. Runtime stays 38 seconds.
- The comparison begins at F538 and stops before F678. Both cuts
  have over 30 ms of PCM silence for the brief comparison fades.
  The full cut doesn't cut or fade the soundtrack at either insert join.
- The optional full local candidate is
  `outputs/edit/june-full-visitor-turn-v1/twelve-dollar-mug-visitor-v1.mp4`
  under the parent workspace. It is not a new default or a production
  export. Rebuild from the pinned coffee candidate:

      python -m pipeline.cartoon_visitor_insert --before COFFEE_CANDIDATE_MP4 --output NEW_DIRECTORY

## New artwork

`concept/style_frames/june-gs050-visitor-knee-v1.png` is the unmodified
1672×941 RGB output of the built-in image tool, using the
`june-golden-scene-gs050-performance-end-v1.png` for style only.
No paid API or key used. Programming the motion is a separate
local pass on the new source art. Exact prompt:

> Use case: illustration-story. One widescreen theatrical animation insert, at 16:9, in the same warm worn rural porch scene as Image 1 (use only as a style, lighting and setting reference, do not reproduce the man, mug or exact composition). This is the view June looks down toward across the small wooden table. Close view of the visiting adult man's one right hand loosely planted palm-down on his OWN bent trouser knee. Natural dorsal anatomy, five distinct digits with the thumb included. The forearm in a warm rust-brown heavy canvas work-jacket cuff enters from the upper RIGHT; back of hand visible at center, fingers angle toward the lower LEFT; the right thumb emerges on the lower RIGHT side of the palm. The thumb and heel are planted on the knee, the other fingers almost flat with fingertips slightly loose, about to make one small nervous involuntary twitch. Strong silhouette and clear visual relationship of cuff to wrist to knee. Not a stiff fist or overly stretched fingers. Muted moss-brown work trousers, jacket distinctly not June's blue denim, younger adult skin with normal calluses and subtle wear. Only a soft out-of-focus edge of the timber porch tabletop at upper LEFT and quiet dark plank tones in the background. Same tactile hand-painted cinematic animated film look as reference, amber porch warmth, shallow but not extreme depth, intimate understated sympathy. No face, second hand, writing, notebook, mug, pencil, additional props, text, labels or watermark.
