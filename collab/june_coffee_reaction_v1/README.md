# The Twelve-Dollar Mug — a look after the coffee

Play these separately, at 1× with sound. Both begin with the same
narration and retain the same final question. Neither is frozen or
sped up to match the other.

- `ending-handoff-only.mp4` (8.77 s): original 39.7-second cut.
- `ending-with-visitor-reaction.mp4` (9.77 s): 40.7-second cut.

The hands make the same exchange in both. In the longer cut, after
June lets go, we see the visitor look down and then toward June.
The tighter crop keeps the mug, pie, and hands out of frame. It uses
the registered visitor-return eyes and a single porch/character plate,
not a replay of the return shot. Only the eye patch changes; no
new blink, smile, or head/body action was authored. The visitor
already looks up in the earlier arrival, so both performances must
be judged in context.

The longer edit leaves 2.14 seconds between release and June's next
spoken line, versus 1.14 seconds before. The later cut to June's
original direct-to-camera ending has the mug beside him. That angle
can read as the narrator returning to the present instead of a
literal reverse of the handoff; if viewers see the mug jump, record
it as an unresolved transition, not as a passing continuity test.

## Evidence

F963–992 (30 frames) are new. All 1,191 older encoded picture
payloads and decoded YUV frames are identical, and their timing is
unchanged except for the 228-frame closer that moves +1.0 second.
The exact PCM master inserts 48,000 zero stereo pairs at a silent
boundary. All prior PCM remains exact; the small playback MP4
uses a newly encoded AAC stream, not packet-copied audio. All 18
caption texts remain; only the last four cues move +1.0 second.
The old and new short reviews start and end inside silence and use
30ms fades. The playback master measured 42.80 dB AAC SNR against
the PCM version and −1.4 dBTP, with true digital zero at the
insert and both review boundaries. The full-duration film and PCM master are in
`outputs/edit/june-full-coffee-reaction-v2/` in the parent workspace.

The decoded sheet samples F949, 953, 962, 963, 970, 975, 979, 982,
992, 993, 1017 and 1042, left to right then top to bottom.
This proves which shots and poses were used, not how the pace feels.
The final hashes and scope are recorded in `coffee-reaction-proof.json`.

```text
python -m pipeline.cartoon_coffee_reaction --before OPENING_LOAN_V2_MP4 --pcm PAYOFF_MIX_WAV --output NEW_DIR
```

## Screen the whole film before freezing the edit

Show either full cut at normal speed, without explaining the new
shot. Ask what was borrowed, what was brought back, and what changed
between June reaching for the pencil and the end. Then compare the
other version: did the extra look communicate a response, or just
delay the line? A positive vote on pacing is not a pass of every
acting beat. Choose one provisional cut before consolidating the
serial editorial builders into one source-only production command.
Keep the alternate and exact component approvals.
