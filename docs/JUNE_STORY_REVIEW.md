# Build both Twelve-Dollar Mug story cuts

On the configured Windows setup, double-click **Build June Story Review.cmd**.
It creates a new folder under `outputs/edit/` with the complete 39.7-second
handoff and 40.7-second reaction cuts. Each subfolder contains a playback
MP4, a MOV with the exact PCM mix, captions, and the mix WAV. The two cuts
are alternatives for review. This does not make either the default or
change the older **Build June Review.cmd**.

From the branch checkout:

```powershell
python -m pipeline.cartoon_story_review --check
python -m pipeline.cartoon_story_review --output outputs/edit/june-story-screen
python -m pipeline.cartoon_story_review --variant handoff --output outputs/edit/june-handoff
python -m pipeline.cartoon_story_review --variant reaction --output outputs/edit/june-reaction
```

Use the free local prerequisites in [JUNE_WORKING_MODEL.md](JUNE_WORKING_MODEL.md).
The build never installs tools, downloads files, or uses an AI key.
It uses a full checkout of this branch and the pinned raster tool versions;
do not transfer a predecessor MP4, an external audio mix, or another `outputs/`
folder. Different tool versions are not yet supported by the exact native
frame checks. On failure use a new output folder and retain the report.

## What the command verifies

- The porch, original loan, return and ledger frames, visitor's POV,
  coffee action, and handoff build once from their tracked sources.
  The original protected pour and closer are regenerated once and
  compared by decoded frame against the tracked approval reference.
- Shared source clips are assembled without re-encoding their picture.
  The longer cut adds a 30-frame look after the coffee handoff and
  shifts the unchanged closer by one second. The MOV keeps exact PCM,
  and all 18 captions match the selected story clock.
- Playback verifies frame order, decoded frames, audio level, caption
  text/times, and scope. Different shot encode boundaries can change
  MP4 bytes without changing story content. This command does not
  promise portability to other renderer/library versions or byte-for-byte
  equivalence with historical hand-assembled MP4s.

Start with a complete normal-speed viewing of either version before
comparing the other. Check whether the original loan and eventual
return read clearly, whether the ledger decision feels acted, and
whether the visitor's look earns its extra second. A technical pass
does not replace that review.
