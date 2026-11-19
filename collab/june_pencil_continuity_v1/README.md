# The Twelve-Dollar Mug — pencil continuity review

Play **pencil-continuity-review.mp4** at normal speed. The old staged
version is on the left; the tighter reaction is on the right. They share
one audio excerpt. The comparison begins at 16.033 seconds in the
38-second film and runs 263 frames at 30 fps (8.767 seconds).

At F563, June's right shoulder and sleeve lead to the hand with the
pencil. At F564–677, the old GS050 art gives it to his left sleeve
without a transfer. At F678, it is back in the right. This version uses
a mid-close reaction to preserve the eye movement, without showing the
contradictory hand. It does not mirror the image, create a hand pass or
redraw a grip. The tradeoff is that the settling hand is now offscreen.
On the right, watch whether the eyes carry this beat on their own.

The rows in `pencil-continuity-poses.jpg` map to full-cut frames
563, 564, 602, 618, 677, 678. This sheet shows the real decoded edit;
it is not a motion or taste verdict. The audio excerpt cuts between
lines with silent 30-ms fade windows. The 38-second candidate retains
all original AAC and optional caption packets, all 303 protected
decoded pictures, and 1,026 untouched video packets. The master MOV
retains exact PCM. No changes to the rejected art, accepted components,
default build, or main branch.

The complete local candidate is
`outputs/edit/june-full-pencil-continuity-v1/twelve-dollar-mug-reaction-v1.mp4`
in the parent workspace. To rebuild it into a fresh directory, use the
prior staged candidate as the exact comparison input:

    python -m pipeline.cartoon_reaction_continuity --before PRIOR_STAGED_MP4 --output NEW_DIRECTORY

That comparator is reproducible with
`python -m pipeline.cartoon_compassion_review --output PRIOR_DIRECTORY`.
See `continuity-reviewed-window.json` for hashes and exact clocks.

## Open: coffee-pot hand and handle

`gs060-lift-return-audit.jpg` samples frames 756, 761, 762, 765,
891, 892, 897, 900. At the table June holds the pot with the left hand
and braces the mug with the right. In the lift/pour the right hand
holds the pot and the left steadies the mug. Both swap at pickup and
again at return. The pot's handle/spout also reverse sides between
these drawings. This is separate from the pencil swap and the old
rejected body-grip art. The short early mug close-up hides the shoulder
and is ambiguous, so it is unchanged.

Next test: a grounded right-hand-on-handle pose with the left hand
keeping the mug still. Check it against the preceding parked pot and
the existing right-hand lift. Use a shared pot orientation and trace
each grip through its wrist and sleeve into the correct shoulder.
Don't lower the entire lift painting; the pot would shift about 500
native pixels sideways while the mug hardly moves. Regenerate only
the unapproved pickup/return lead-ins; preserve protected F789–863
and F912–1139, story clock and audio. A brief reaction cut can keep the
hand out of view if the new pose does not register, but would not prove
on-screen pickup mechanics. No coffee action repair or artistic
approval is claimed in this package.
