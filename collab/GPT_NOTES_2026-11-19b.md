# Pickup: bring up the full short from tracked sources

Prior turn was **progress** at 25fded4 (38-second closed-loop narrative
review, but still needed the exact legacy master). Current work adds
the separate `cartoon_full_short_source` entrypoint and
`Run June Full Short.cmd` at 60e1f93224805aa100dcc034268de68461f0d576.
No frozen renderer, review output, captions, approval or sound source
was changed. See `docs/JUNE_FULL_SHORT_SOURCE.md`.

Actual clean-source proof began in session **95871** from
`C:/Users/jwats/Documents/Codex/2026-07-28/d/outputs/edit/june-full-source-proof-v1/checkout`. The fresh, 707235840-byte Git archive SHA-256 is
`626d024ed5b19a22780c64d94c4a7f422d4f61e694acb433ae3ea307dfb71b80`.
No old render directory was copied into the source checkout or render
output. The invocation is `--rebuild-repaired --compare-review`: the
locked component art/timing rebuilds the protected 303 frames,
the other 837 come from tracked plate/stand/pour art, and the original
review movies are used only to verify strict picture compatibility.

**Complete, exit code 0.** Actual Python run took about 13.4 minutes.
No live render handle remains; do not repeat this proof unchanged.
All 1140 frames built, protected MOV was byte-identical, all 303
protected frames in the final decoded cut were exactly identical.
Full mix WAV and 18-caption sidecar both byte-identical to prior review.
AAC SNR 43.11 dB; both exported true peaks −1.4 dBTP. The separately
rendered 837 shots were compared one-to-one after render, min/median
PSNR 35.742/38.444 dB. The two same-view transitions scored 4.204 and
1.609 mean absolute RGB delta, lower than the master-based version.
Inspected final decoded sheet and the paired worst sampled stand/pour
frames (F310/F911): no observed composition or geometry drift there.
Not byte equivalence for nonprotected frames or a taste verdict.
New MP4 SHA256 35800acc8087fe665368c1d680c358bd2e5ba1f825bbaab19ba50f8f08ccbf1a.
Movie remains at the local sibling `render` output. Tracked evidence
`collab/june_full_short_source_v1/`; no duplicate MP4 or tar pushed.
The default launcher reuses the tracked protected picture for speed;
the clean proof specifically verified the full rebuild flag.
Forty-three focused checks passed, including the new receipt and native
frame clock tests and older source and delivery regressions.

The most important remaining artistic check is not another technical
test: whether June's change of heart around 0:19–0:22 is clear and
acted, instead of a hard pose switch. Inspected actual GS050 start/end
art and preserved a small normal-speed screening guide in
`JUNE_FULL_CUT_REVIEW.md`. This is a recommendation, not James's verdict.
Next, work on the moment June chooses compassion in the full story:
first test gaze arriving before the pencil settles, if the existing
change of heart reads stiffly. Keep shot timing, dialogue and the
approved ending locked. Use the full cut as context, not a new
standalone acting demo. Final voice and continuous artistic screening
are still required. No new Claude invocation, cash spend, automation
change or promotion.
