# Rest Your Hands — 7.43-second story review

The mug functions as a visual echo of the line about setting a burden down.
Start on June, cut to the held mug during the first phrase gap, let the
contact interrupt the pause, and return to June before the second line.
This derivative does not replace any passed source film.

- `story.mp4`: watch at normal speed with sound.
- `story.mov`: same encoded picture, exact stereo PCM24 mix.
- `decoded-cuts.jpg`: decoded visual evidence, not a real-time review.
- `verification.json`: source, frame, delivery and sound measurements.

Rebuild from the repository with free local FFmpeg, Python, Pillow,
OpenCV and NumPy into a fresh output folder:

    python -m pipeline.cartoon_story_beat --output ../../outputs/edit/my-rest-your-hands-story

The frame-based decision list is
`concept/scenes/june-rest-your-hands-story-v1.json`. Source face timing
is preserved at both appearances. The hand cut starts already gripped;
the approach is in the standalone exchange proof, not this cut. There
are 16 extra frames of digital silence at the existing phrase pause,
without altering the words or their speed. The voice only receives a
fixed −2 dB trim for true-peak headroom. One recorded contact peaks on
frame 101 (zero-based, 3.3667 seconds), without a synthetic bed.

Picture is encoded once per trim, then packet-copied through concat and
delivery. This verified 720p preview scales the 800×450 insert; it is not
a claim that new detail was generated. The initial MP4's default 1000 Hz
movie clock shortened its declared audio by 16 samples, while the PCM
master and all 223 frames were intact. Final delivery corrected only
the AAC mux/movie clock, with identical video packets and exact 48-kHz
track duration. PCM integrity passed, both true peaks were −2.0 dBTP,
and AAC SNR was 42.64 dB. This remains a scratch-voice story review, not
human-approved or a final mix.
