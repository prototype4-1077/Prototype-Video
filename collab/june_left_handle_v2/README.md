# June's left-hand mug lift — review insert

Watch `june-left-handle-v2.mp4` at normal speed. It is silent by design.
The question is narrow: does June's left wrist read naturally as he lifts
and sets the mug back on the wood? His hand is already around the handle;
this is not the reach or release, and it is not part of the accepted movie.

Build from the repair worktree into a **new** directory:

    python -m pipeline.cartoon_mug_action --output ../../outputs/edit/my-left-hand-study

The scene recipe in `concept/scenes/june-gs070-left-handle-v2.json` includes
every new source, prompt and checksum. The output is 800×450 at 30 fps,
framed as a detail insert; it does not enlarge the painting.
`source-frames.json` records native cropped RGB hashes; the still sheet is
decoded from the movie. `verification.json` identifies the actual source code.
No API call, art generation, subscription or web request is part of the build.

The post-encode source cleanup changed only a timing comment and a trailing
blank line. The original encoder source hash is preserved in the receipt.
Original and shipped Python AST SHA256: 6ac8d17be903a95e3a130a2a84b677f728fadf3e1d85a927ad45682a1ee5606f.
All 84 native RGB hashes were regenerated and compared equal without re-encoding.
