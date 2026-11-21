# The Twelve-Dollar Mug — show the offer

Play `mug-offer-review.mp4` normally: original on the left, visible offer
on the right. Does the small gesture read as June offering the mug,
or simply as an extra hand entering the shot?

The empty mug slides 48 native pixels along the same tabletop. June
lets go; the visitor takes the same handle with his anatomical left
hand while keeping the bills in his right. No hand was mirrored.
June's hand was re-posed from the later coffee exchange using a rigid
rotation and uniform scaling, not borrowing that exchange's full mug.
In the rejected first pass June's thumb covered part of the visitor's
cash-holding hand. The selected angle preserves that region and keeps
June's cropped sleeve edge below frame. June's identity is inferred
from the preceding shot; the comparison is a story test of whether
that inference works at speed.

Only F129–224 changes. The [56,312) comparison has 256 frames at
30 fps, one existing soundtrack, quiet audio edges, and the original
entry and return cuts. The stable full cuts were not rebuilt or
replaced. This is not an accepted movie.

Six regression tests passed; the rim/chip transfer, face and cash,
unmirrored donor geometry, grasp timing, and pixel-exact settled tail
were checked. At 1536×432 the two separately compressed panels
scored at least 41.11 dB before the study and 44.90 dB after it,
with no frame misalignment. The decoded stereo audio was 409,600
samples/channel and correlated 0.9999855 with the source interval;
each 30 ms edge peaked within one signed 32-bit step of zero.
The sampled decoded frames and source/output checksums are included.

```text
python -m pipeline.cartoon_mug_offer --baseline CLEAN_HANDOFF_MP4 --pcm CLEAN_HANDOFF_WAV --output NEW_DIR
python -m unittest pipeline.tests.test_cartoon_mug_offer
```
