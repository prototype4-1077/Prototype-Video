# June notices, then sets his pencil hand at ease

`reaction-side-by-side.mp4`: left = original, right = staged.
Both show GS050 (18.8–22.6 seconds in the film) with one shared audio
excerpt. That small comparison has 30 ms audio-edge fades. The full
review version does not change the audio or subtitle packets at all.

The scene starts on its original plate. Paired facial landmarks move
the gaze, brow, and tilt together. When June has finished looking
down, the hand eases, and one rigid painted pencil rotates behind the
fingers and cuff. Motion is restricted to two local patches before the
original camera/light animation; the mug, ledger and porch are not
blended with the alternate painting. No new artwork or paid service.

Rebuild a complete candidate in a fresh local output directory:

    python -m pipeline.cartoon_compassion_review --output NEW_REVIEW_DIRECTORY

The same 38-second baseline supplies the unchanged scenes, AAC and
captions. Only the 114 frames in GS050 are encoded. All 1,026 remaining
video packets, every AAC/caption packet, all 303 repaired decoded
frames, and exact PCM master are independently verified. See
`reaction-proof.json`; the heavy full candidate is kept locally, not
published again as a large binary. Nothing is promoted. In real-time
playback the question is whether June's decision reads more naturally,
not whether the face/hand happen to move.
