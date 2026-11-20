# The Twelve-Dollar Mug — first ledger reverse

Watch `ledger-reverse-review.mp4` at normal speed, with sound.
Left: first reverse as it was. Right: a tighter view of June listening.
The 7.53s comparison starts during the pie placement; after the
changed shot, it plays the existing tight pencil detail *and* the
return to the wider view. The question is whether the pie feels
off-camera, and whether we stay with June's reaction rather than
looking at the table. The later wide still doesn't show the pie.

This is a framing-only alternative. At F396 (13.200s), existing
GS040 footage crops to 1280×720 at source offset (120,4) and
scales back to 1920×1080. At F452 (15.067s) it cuts to the exact
original pencil angle. No extra cut, face/hand repaint, reversal,
retiming, or sound change. F508 (16.933s) returns to the original
wide angle. A longer crop would also erase disclosure of the
open ledger and make the next facial close-up a weaker size change.
Neither alternative physically places the pie in the ledger reverse.

`decoded-ledger-reverse.jpg` samples the actual 1080p alternate,
left to right: F379, 394, 395, 396, 414, 451, 452, 477, 507, 508,
531, and 563. The stills verify framing and shot order, not
normal-speed continuity or performance.

`ledger-reverse-proof.json` binds the cropped shot, complete
local alternate, prior cut, PCM reference, builder, and short
comparison. The audit required the same 1,191 frames and
presentation timestamps, all 1,135 picture packets and decoded
YUV frames outside the crop identical, the 56 crop frames decoded
exactly as the isolated shot, and all original audio/caption
packets identical. All 1,905,600 decoded stereo sample pairs
match, along with the identical silent AAC end padding. The
side-by-side retains one shared soundtrack, starts and ends
inside true silence, and applies a 30ms fade in those silent windows.

The 39.7s review is local at
`outputs/edit/june-full-ledger-reverse-v1/twelve-dollar-mug.mp4`
in the parent workspace. Rebuild against the exact visitor-return
review MP4 and coffee-payoff PCM WAV:

```text
python -m pipeline.cartoon_ledger_reverse --before VISITOR_RETURN_MP4 --pcm PAYOFF_MIX_WAV --output NEW_DIR
```

No earlier cut, protected component, default delivery or `main`
changed. No human verdict or production release.
