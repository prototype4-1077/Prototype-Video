# The current June cuts build cleanly

`Build June Review.cmd` was run from an isolated tracked-only
snapshot of b0eab72; no existing output folder, cache, earlier full
movie argument, network service or paid API. One command generated
both 38-second cuts, sharing the rebuilt source and entire soundtrack.
See `current-review-build.json` for the original receipt and
`clean-source-receipt.json` for independent post-render checks.

- In each cut: all 837 nonprotected native RGB frames matched the
  locked source hashes; 303 protected frames regenerated from art and
  decoded exactly like the approved source. All clocks, the sidecar
  captions, exact MOV audio PCM and both protected pour joins passed.
- Against the exact corresponding local previous reviews, all 273
  corrected reaction/coffee frames and all 303 protected frames
  decoded exactly. The re-encoded earliest 564 frames had at least
  35.776 dB same-index PSNR vs the earlier export; not a byte-for-byte
  identity claim. Both full AAC and caption packet signatures also
  matched the previous cuts.
- The fresh face and visitor versions use 1,026 identical video
  packets outside the reaction and identical audio/caption packets.
  This isolates the optional story choice.
- All 47 focused tests passed, including the opt-in check on the
  two fresh full-length movie files.

The videos are stored locally in the parent workspace at
`outputs/edit/june-current-clean-verification/rendered/face/`
and `outputs/edit/june-current-clean-verification/rendered/visitor/`
(each named `twelve-dollar-mug.mp4`). Run the launcher to make a fresh
copy. The shots, voice and alternate story edit still need human
screening. No production or main approval.
