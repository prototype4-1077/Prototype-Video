# The Twelve-Dollar Mug — visitor accepts the coffee

Watch the two small clips separately at normal speed with audio:
`ending-without-handoff.mp4` (4.63 s) and
`ending-with-handoff.mp4` (6.33 s). They start at the same phrase,
and the longer one has a real pause, not a freeze-frame or edited
dialogue. The point of the test is the visitor's response and whether
the extra time earns itself.

The cut from the wide to the detail reveals an **open right hand**
on the ledger side, not the left hand previously bracing the mug.
June reaches for the stationary mug over 11 frames, then slides it
to the visitor. The visitor makes contact and June releases, with
the cup still resting on the visitor's side. Cutting back to June
is a small jump in time, not a claim that the visitor's grip is
still in frame. A quiet close-up rather than a new line of voiceover.

## Technical evidence

- The alternate is **39.7 s**, 1191 frames at 1080p30. Added F912–962
  inclusive (51 frames). The closer's first image is now F963.
  The 40 isolated handoff frames have the exact same native RGB hashes;
  only the new 11-frame approach is different in the insert.
- All 1,140 original picture packets and decoded RGB frames keep
  their content. The 228 closing frames are shifted 51 frames, not
  retimed/re-encoded; the rest keep their clock. All protected frames
  therefore retain their content as well.
- Inserted 81,600 zero stereo sample pairs inside a verified silent
  boundary. PCM before and after is byte-exact. The shorter preview
  and extended preview use their own narration at the same rate.
  The full alternate AAC is newly encoded (42.90 dB SNR against
  the exact extended PCM); audio was not packet-copied. MOV and
  MP4 both measured −1.4 dBTP. All 18 caption texts are retained;
  the last four are shifted exactly 1.7 s.
- `decoded-payoff-staging.jpg` shows F911, 912, 916, 921, 923, 930,
  939, 945, 946, 953, 962, 963, and 987 in order. Both joins checked
  in the decoded full movie. A sheet/metric is not a motion verdict.

The full alternate and its exact-PCM MOV are local under
`outputs/edit/june-full-coffee-payoff-v1/` in the parent workspace.
Build from the exact clean 38-second `visitor/` review movie made
by `Build June Review.cmd`:

    python -m pipeline.cartoon_coffee_payoff --before CLEAN_VISITOR_MP4 --output NEW_DIRECTORY

Neither original 38-second cut or its default launcher changed.
This is a separate experiment for human screening, not an accepted
ending, release or main-branch change.
