# Pickup: full left-hand mug exchange assembled

The previous goal turn was **progress**, not completion: 9920722 produced
a pre-gripped left-hand lift. The current turn adds an open-hand reach,
planted grip acquisition, reuse of the lift, planted hold after touchdown
and opening, all in a single uninterrupted 4.9-second shot. Do not return to
the user-rejected v1 backwards hand or stage a redundant isolated lift.

Latest James verdict remains `JAMES_VERDICT_2026-11-18.md`; the old accepted
resting hand, cuts, mouth, audio and blink are untouched. The latest
applicable Claude file remains the October 29 mouth/hand still comparison;
no new Claude review was run. Five-hour automation stays paused.

Review package: `june_left_handle_exchange_v3/`. Builder:
`python -m pipeline.cartoon_mug_exchange --output <new-dir>`. Open cel and
prompt bind through `concept/scenes/june-gs070-left-handle-v3.json`.
147 decoded frames, 800×450, 30fps, BT.709, no audio. Movie SHA256
4cb42ea479a05e63aa677d69314988cdf912a347dc6a53544ed911f59c7edf86.

Three visual passes (all concluded):

- Bare premultiplied blending passed PSNR/continuity but failed close visual
  inspection: semitransparent double fingers at the changing grip.
- Single interpolated contour removed that ghost, but tight crops isolated
  stray glazed rim/handle pixels in the moving hand matte.
- Removing those prop pixels gave the delivered version. Inspected the
  decoded sequence sheet and full-size hand crops, not a human verdict at
  normal speed. The left silhouette is readable and no obvious second
  handle survives in those samples; finger paint still softens in acquisition
  and release. Local rejected/draft versions live under
  `outputs/edit/june-left-handle-exchange-v3*`; don't show them as approved.

Actual full-frame decode and timestamp verification passed. Raw v2 F4–70 =
v3 F35–101 byte-for-byte. Raw joins F34–35 and F101–102 are identical.
Decoded exact chip position while planted; excursion 78 px; minimum sampled
tracking correlation .9715; held hand vs prop max discrepancy 1 px.
Decoded static opening, closed occupation and reopening checked separately.
Twenty focused checks passed including earlier published proofs.

**Next:** advance from isolated mechanics to a story beat. Recommended
first assembly: the existing “set the bucket down” dialogue as the voice
and reaction spine; a purposefully timed handle/set-down cutaway only where
the physical action reinforces the line. Keep speech natural and sample
aligned, use recorded mug-on-wood Foley with the touchdown (not synth
effects), return to June on a held breath or blink. Confirm time and
composition across decoded cuts first; at present the short dialogue uses
a scratch Piper voice and the mug insert has no final human verdict. The
review assembly should be a derivative; never overwrite the accepted
10.1-second proof. Do not claim production-quality or close the goal until
there is a coherent, reproducibly built, human-reviewed cartoon with
consistent acting, editing and sound. Main untouched; no paid runs.
