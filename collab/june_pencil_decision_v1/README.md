# The Twelve-Dollar Mug — June lets go of the pencil

Watch `pencil-decision-review.mp4` at 1×. The original is on the
left; the right keeps the same angle and sound but gives June
more time before reaching for the pot. The question: does he
look like he chooses to stop keeping score?

The pencil was already set down in the earlier cut. In this
version it stays poised longer, then comes to rest before June
opens his fingers fully. At F735 it has settled flat on the ledger;
by F741 his hand is clear. He reaches at F746, raises the pot
by F781, and the original lead-in and pour remain on their clock.
The hand and pencil use separate motion curves. No new hand,
flip, blink, sound effect, or face art.

The narration describes the choice after we see it. “So I set the
pencil down” starts during the protected pour, not at pencil contact.
Syncing it literally would change protected picture or speech. The
6.6-second review starts in the thought pause and runs through that
line. The earlier visitor hand POV, final pour and closer are unchanged.

## Evidence

The separate 39.7s alternate replaces only F678–788. The other
1,080 encoded picture packets and decoded frames are exact. All
original audio and caption packets and the decoded soundtrack
are identical. The final seven frames of the approach match the
original source RGB before encoding; their decoded pixels have
minor differences from the changed encode history. From F789,
including the entire protected pour, the old pictures are exact.
The comparison starts and ends with digital silence and 30ms fades.

One midrange test showed the eraser on top of the far knuckles
instead of behind them. The selected shot extends the hand holdout
only while they cross, before the pencil is flat. Review that
moment and the inherited wrist movement at normal speed, not as
an accepted grip. `pencil-decision-proof.json` binds the short
video, source, builder and raw frame inventory. The local alternate
is `outputs/edit/june-pencil-decision-v3/twelve-dollar-mug.mp4`
in the parent workspace.

```text
python -m pipeline.cartoon_pencil_decision --before CLEAN_HANDOFF_MP4 --pcm CLEAN_HANDOFF_MIX_WAV --output NEW_DIR
```

No default change, production release or human verdict. If the
timing alone doesn't communicate a decision, a later test could
physically move the ledger aside with fingertip contact. Do not
add more pauses or touches unless they improve what a viewer sees.
