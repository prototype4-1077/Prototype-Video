# Full source rebuild verification

The complete 38-second review rebuilt from a fresh Git source archive in the
configured local runtime. No historical Phase25 rendered master or local
render cache was used. This run used `--rebuild-repaired`: all 1,140 frames
were rendered in that run. The protected 303-frame intermediate MOV matched
the checked-in proof byte-for-byte. The tracked comparison movies were used
for verification, not as sources of picture pixels.

`native-early-frames.json` records RGB24 SHA-256 before the single final
encode for all 837 early and pot-return frames. `source-build-report.json`
records the actual decode and PCM audits. Against the existing full review,
those 837 frames match their original positions, with minimum/median
35.74/38.44 dB RGB PSNR. They are not byte-identical because the new route
does not encode and decode old intermediate masters. Every repaired decoded
frame matches exactly. The full mix and caption sidecar are byte-identical
to the first full-cut review. No cut, script, or audio edit changed.

In `lowest-match-frames.png`, old review is left, source rebuild right.
Rows are zero-based F310 (stand) and F911 (pot return). The decoded
comparison was visually checked for continuity and obvious geometry drift;
normal-speed human acting and sound judgment remain open.

See `docs/JUNE_FULL_SHORT_SOURCE.md` for the launcher and optional full
regeneration. The MP4/MOV, mixture and snapshot are retained locally under
`outputs/edit/june-full-source-proof-v1/`; they are not duplicated in Git.
`clean-build-receipt.json` identifies the actual run and its inputs.
