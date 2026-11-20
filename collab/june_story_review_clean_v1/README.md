# Both full story cuts rebuild directly from source

The new **Build June Story Review.cmd** ran in an empty-output
copy of the Git index tree `eb60b9ab1f1ed8ef57612b21d240c90a2a7cb127`.
That snapshot included the new launcher and builder and none
of the later receipt files. Neither an old full cut nor its
cached mix was supplied. A tracked, approved short MOV is read
only as the protected-picture comparison reference; the shot
itself is regenerated once from tracked source.

`story-review-build.json` is the successful runtime receipt.
The two movies share all 963 prefix packets and the same 228-frame
closer; the longer cut shifts that closer by 30 frames. The first has
1,191 frames / 39.7s, and the second 1,221 frames / 40.7s. Both
match all 303 protected decoded pictures, exact respective master
PCM, and all 18 subtitle cues. The 40.7s edit adds only 48,000
silent pairs to the 39.7s PCM. Both AAC previews measured −1.4 dBTP.

A separate post-build comparison against the frozen hand-assembled
cuts decoded every frame. 987/1,191 frames match exactly in the
39.7s version and 1,017/1,221 in the 40.7s version. All differences
are in the preserved porch/ledger source regions with different
encode boundaries, with minimum same-frame PSNR 42.36 dB.
PCM WAV and caption text/time are exact in both historical
comparisons. See `independent-comparison.json`. This is not a claim
that the overall MP4 hashes are identical to the earlier exports.

The local results are in the parent workspace under
`outputs/edit/june-story-review-clean-v1/rendered/`:
`handoff/twelve-dollar-mug.mp4` and `reaction/twelve-dollar-mug.mp4`.
All 36 focused tests and 67 subtests passed, including the receipt
tests against both sets of local films. Use the launcher to build
again only if a fresh output is needed. The existing older launcher
and the two story alternatives were not promoted. Runtime validated
on this configured Windows setup, not on all platforms.
