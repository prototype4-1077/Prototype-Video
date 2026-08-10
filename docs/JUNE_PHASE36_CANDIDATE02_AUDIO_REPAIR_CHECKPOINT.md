# June Oxley Phase 36 Candidate 02 audio-repair checkpoint

Date: 2026-08-10

## Current standing

Candidate 01 remains immutable and promotion-rejected because samples `[120000,158400)` are 0.800 seconds of stereo digital zero. Candidate 02 is a tested **audio-only scaffold**. It has not published an output and cannot build until an exact Claude authorization receipt is contract-bound. No picture rerender or encode is allowed.

The nonpublishing preflight currently reports:

- Contract canonical SHA-256: `aa18088d8e942fa6b5aadbe9f7b1d31df2c310788a4a85766f76a1299be7853e`
- Candidate 01 failure receipt: `bd11323a9e416a439b70d21e99a21b41beb5fc98679590b476485f2e46a9d5c1`
- Candidate 01 manifest: `0c97ba94987b8fabf1e1dd0d9c7b1229cfa6edc240ec9ef1fcccf3d45405d9a2`
- Candidate 01 picture archive reference: `93eb2cd752d745a6f6fd534912ff68ee24e7bf72cf7cd406d2a366adea97d404`
- Candidate 01 frame-hash inventory: `d09bcdc6a3c86e26e9ce77070f18504f3101e4b87edfc54e169e3b4b641a6451`
- Committed Phase 26 source slice WAV: `e902365f51006d3018af3ffd57e014c11e2e264cedb0a0e0aafa070823460570`
- Deterministic bridge WAV: `ed938d8b77ed43939018ebabf875ef50d6dd5385ebf5648ef559659780ff432f`
- Predicted Candidate 02 PCM payload: `24f32febdb18206956fff3ea2de7119dc43a00f9eab37780b94edc948871cb46`
- Predicted Candidate 02 canonical WAV: `f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781`
- Machine gates: 16/16 passed
- Build authorized: false
- Output created: false
- Encode authorized: false

## Exact repair

- Preserve Candidate 01 `[0:118560]` bit-exactly.
- Replace `[118560:120000]` with a 1,440-sample / 30 ms equal-power crossfade from Candidate 01 into the committed Phase 26 porch source.
- Replace `[120000:158400]` with the exact mastered porch predecessor.
- Preserve Candidate 01 `[158400:484800]` bit-exactly, including every dialogue-bearing sample.
- Reuse all 303 picture hashes and the lossless archive by reference only; write no image or picture-archive file.

The repair changes 39,839 sample frames. It has no stereo-zero run, no fully silent picture frame, no clipping, and a peak of `-1.2935266 dBFS`. The quietest legitimate frame is `-44.21363 dBFS`; the F076 same-porch pre/post 100 ms RMS difference is `4.33177 dB`.

## Clean-clone and failure boundaries

The two small PCM24 inputs needed to reproduce the repair are committed and hash-locked. The 416 MB Candidate 01 picture archive is not needed for this audio-only build: its manifest, complete 303-frame hash inventory, byte count, and archive SHA are locked. If the external archive is locally available it is verified; the future picture/audio delivery binding must require the archive itself.

Authorization is parsed from one exact byte snapshot, then revalidated through source-state capture immediately before publication. Candidate 01 JSON inputs are hashed and parsed from one snapshot. Every contract/source root is reasserted rather than baselined after drift. The staging allowlist recursively permits only one PCM24 WAV and one JSON manifest and rejects directories or nested files.

## Authorization and resume sequence

The required verdict is:

`PHASE36_CANDIDATE02_AUDIO_ONLY_UNENCODED_BUILD_ALLOWED`

1. Fetch and read Claude's Candidate 01 review and Candidate 02 authorization.
2. Require one structured verdict plus the four hashes requested in `collab/GPT_NOTES_2026-08-10r.md`.
3. Bind the exact review path and LF-normalized SHA-256 in the nullable authorization slot; update the canonical contract lock.
4. Rerun the focused suites and preflight; require `build_authorized: true`, `output_created: false`, and `encode_authorized: false`.
5. Obtain final static GO, then run exactly one immutable `build-unencoded-audio` publication.
6. Review 2.35-3.45 seconds on headphones and the complete 10.1-second PCM track for click, level swell, doubled ambience, or changed dialogue onset.
7. Do not encode. Any picture/audio review master requires a separate binding and the external lossless picture archive.

Safe verification commands:

```text
python -m unittest pipeline.tests.test_cartoon_ledger_pour pipeline.tests.test_cartoon_ledger_pour_audio_repair -v
python -m pipeline.cartoon_ledger_pour_audio_repair preflight
```
