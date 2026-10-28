# Quiet pickup — 2026-10-28 — recovery assets inventoried, no new render

Starting scene checkpoint: `64240dfba4a7b6624405b32cac946ca683498277`.
No newer James/Claude verdict was present locally or on this repair branch.
The complete scene still awaits review; accepted eye/audio components remain
closed. No movie, artwork, timing contract, approved file or master changed.

## Existing recovery coverage: do not commission duplicate art first

Inspected `concept/style_frames/june_golden_scene_gs060_layered_pour_v1.json`.
Its six existing registered foreground poses already cover pencil poised,
pencil down, pot grasp, lift, pre-pour and full tilt. The timeline uses these
same drawings in reverse after the pour:

- F185: full-tilt to pre-pour smear; F186-F198: pre-pour recovery.
- F199: recovery-to-lift smear; F200-F213: lifted upright pot.
- F214: lift-to-grasp smear; F215-F229: grounded pot grasp.
- F230: release smear; F231-F258: pencil-down / grounded-pot pose.

The reviewed opening takes source F112-F186 only. Therefore F187-F258 already
provides 72 additional frames (2.4 seconds at 30 fps) of authored recovery.
This is an asset-reuse opportunity, not proof that the coarse pose transitions
look natural in motion or that a turn toward the camera exists in these layers.

## Known registration constraint, not a newly discovered defect

The three grounded foreground files still match their recorded SHA-256s.
Their mug-registered pot-base positions are:

| Pose | Registered pot base | Residual from [1301,834] |
| --- | --- | --- |
| Pencil poised | [1301,834] | 0 source pixels |
| Pencil down | [1301,834] | 0 source pixels |
| Pot grasp | [1281,830] | 20.396078 source pixels |

This allowance is already documented in
`docs/JUNE_PHASE23_LAYERED_POUR_CHECKPOINT.md`; do not announce it as a new
regression or a new human rejection. It meets the old 24-pixel pot-anchor
ceiling. A tighter continuous recovery/contact pass has not been established.

Mug registration is separately fixed to [1000,692] with a 0.01-source-pixel
ceiling. Translating the whole foreground to align the pot would move the
already registered mug. Do not blindly "fix" the pot by shifting the complete
character/mug layer or by relaxing either existing gate.

## Cheapest next experiment after whole-scene feedback

Start with the existing return-pose transitions/contact anchors, not new image
generation or another renderer. Check whether the visible pot/hand return can
be made convincing with protected local controls and existing drawings. A
short source/contact study should precede any newly timed full scene.

Do not silently append all 72 recovery frames to the accepted edit: doing so
would lengthen 303 frames / 10.1 seconds to 375 frames / 12.5 seconds and move
the existing dialogue by 2.4 seconds. That is an editorial change requiring a
clear strategy, not a consequence of the earlier component acceptance. Keep
the approved voice samples/eye artwork and the current review immutable.

No paid call, asset regeneration, encode, or cloud job was used for this
inventory. Future wakes without new feedback should not repeat this lookup
or rerender the current full-scene proof.
