# June reaches, lifts, and lets go

This 4.9-second silent playback proof starts with the left hand above the
handle. The mug remains planted as the fingers close, rises with the hand,
returns to the wood and rests before the fingers open. It is a review
insert, not an edit to the passed films and not a human acceptance.

Build from pinned source into a new directory:

    python -m pipeline.cartoon_mug_exchange --output ../../outputs/edit/my-handle-exchange

An open-hand painting was made using the built-in reference editor. The
recipe `concept/scenes/june-gs070-left-handle-v3.json` records its full prompt,
parent and hash. At runtime the porch stays fixed while two registered
arm poses change around a separately composited cup and loop. The hand
uses one rendered silhouette instead of overlapping translucent cels. The
existing 67 consecutive held, rising, and lowering frames match v2 native
RGB exactly, including both joins.

All 147 frames decoded with correct 30 fps timestamps, and 16 decoded
samples passed the 38 dB picture floor (min 39.162 dB). The chip did not
move in any decoded grounded frame; its full lift was 78 pixels. Three
tracked landmarks on the closed hand and cup stayed within one pixel of
each other. The center of the handle opening changes from background to
skin and reopens. Those are mechanical checks, not a motion/taste verdict.
The shaping of the fingers in contact still has some close-up softness.
