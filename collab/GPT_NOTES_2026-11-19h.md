# Pickup: validate the one-command current review build

Progress: added `Build June Review.cmd` and
`pipeline.cartoon_current_review` at b0eab72. The launcher can build
both 38-second review cuts or select the face/visitor reaction.
There is no old full-movie input. Shared source spans [0,564),
[678,789), [864,912) and the regenerated protected scene are
made once. Each variant has 837 pinned native RGB hashes and
303 protected decoded frames to verify. Both get the same source
PCM and 18 caption cues. No previous renderer was edited.

The **clean-snapshot verification is in progress**. Exact snapshot
b0eab72c85ed3f4cf6355ebab9dd93eb1e4eee8d is locally exported into
`outputs/edit/june-current-clean-verification/snapshot` in the
parent workspace. Archive size 728832000 bytes, SHA-256
223831b52e9604992d3adefacafcf19394c064740922e0029b511d68fc57b739.
Snapshot had no pre-existing outputs/edit. Launched its Windows
`Build June Review.cmd` to fresh sibling `rendered`, with no
comparison paths or prior outputs. **Poll actual shell session
29132 first; Python PID 37976 observed live. Do not relaunch for
silence/timeouts.** The early frame encoder was still running.

Mix/caption source files in the new output both match the previously
tracked exact SHA-256s before verification. Dry checks for both and
face work. The new automated suite passed four tests; exactly one
actual-dual-build receipt test was skipped while the movie is running.
Run it with `JUNE_CURRENT_BUILD_PROOF` pointing to the new directory
after terminal success. Then compare both generated outputs to the
exact previous coffee/visitor cuts after render, not as source.
If any later stage fails, preserve that run, diagnose the actual
failure, and use a separate directory only for a justified retry.

This is an infrastructure change, not an artistic approval, default
selection or release. Still open: full-cut screening and addressing
the next sequence based on the result. No automation, main branch,
cash or author/media consent change.
