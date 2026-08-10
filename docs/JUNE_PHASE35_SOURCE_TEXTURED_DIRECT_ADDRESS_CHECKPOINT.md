# June Phase 35 source-textured direct address checkpoint

Date: 2026-08-10

## Current standing

Phase 35 Candidate 03 is the authoritative, visually accepted **unencoded facial-performance integration proof**. It combines June's accepted source-textured face with the locked 7.6-second dialogue clock, Rhubarb visemes, body/head motion, camera motion, porch atmosphere, and Candidate 09's approved linear blink timing.

It is not yet a full-cartoon delivery. Claude independently ratified the exact manifest-bound visual proof in `collab/CLAUDE_REVIEW_2026-08-10_1712Z.md` and authorized exactly one versioned 7.6-second A/V proof encode of that binding.

Candidate history:

- Candidate 01: 18/18 machine gates passed, but visual review found the Candidate 08 smoothstep blink acceleration unacceptable for future reuse. Preserved as historical proof only.
- Candidate 02: 22/22 machine gates passed and produced the same final RGB frames as Candidate 03, but its review/provenance package predated the final hardening.
- Candidate 03: 27/27 gates passed with complete blink review frames, exact Candidate 01 baseline reconstruction, eye-only spatial-delta proof, and four execution-state checks.

## Candidate 03 immutable evidence

- Manifest: `collab/phase35_candidate_03/june-phase35-source-textured-direct-address-preview-manifest-v2.json`
- Manifest SHA-256: `250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe`
- Contract raw SHA-256: `68c763be79dd76447f6c33baf39ef79528fbbf1d6ea25a113c5550d63d62ba94`
- Contract canonical SHA-256: `5069774dfb92511a5adc291f7d09c755f0b51c1ea2ed1bae5356bcaab597d25f`
- Executed renderer SHA-256: `97612673a65b92e83d9d54debaf1738508d88442813759ba9959a41dee32fe77`
- Executed renderer/test source archive: `collab/phase35_candidate_03/phase35-candidate03-implementation-source-b06981d.tar`
- Executed renderer/test archive SHA-256: `8467298165d1669f5d3efbdb3d2a630e8f93f67a4cf8aff062789939b056893b`
- Independent review receipt SHA-256: `3b3fbf4ad5755c94ebafcc1b0417f83fcebcc67f1edd812b902d0d44eb072d41`
- Local lossless archive SHA-256: `b5908bfce4ac10ad7e3ad74e58a8cf9f8e352033b14c1828315e96cd615f6e0f`
- Local lossless archive: 242,333,440 bytes; omitted from Git because the exact 228-frame hash inventory and verified archive receipt are already bound in the manifest.

Published visual evidence includes all 228 frames, 18 complete blink-table frames, the face timeline, key beats, motion sheet, and a 2x crop of F172-F176.

## Machine result

- 27/27 gates passed; zero failed.
- 228 frames at 1920x1080, 30 fps, 7.6 seconds.
- Exact audio clock: 364,800 samples at 48 kHz; 1,600 samples per frame.
- Native face maximum: 135.7864532470703 <= 145.
- Native blink maximum: 125.57291412353516 <= 130.
- Final composed face maximum: 145.9010467529297 <= 170.
- 220/228 final RGB hashes preserved from Candidate 01.
- Only F078, F080, F082, F084, F170, F172, F174, and F176 changed.
- All eight Candidate 01 frames rerendered to their historical hashes.
- Zero changed pixels outside native eye support.
- Zero changed pixels outside transformed final eye support.
- Zero topology, depth-order, feature-support, archive, or end-state hash violations.

## Visual result

Local exact-frame review passes identity stability, viseme legibility, mouth/beard registration, body/head integration, even blink travel, and the final neutral settle. F174-F175 now reads as a normal opening step rather than the Candidate 01 snap.

Known P2 watch item: the single full-closure frame has a thin lid hairline when magnified. It is not visible at delivery scale and is acceptable for a 33 ms blink, but the current lid source must not be used for held closures such as sleeping, prolonged squints, or extended closed-eye acting.

## Remaining production gap

This proof is still one direct-address shot. It does not yet demonstrate a full scene with physical prop action, editorial cuts, or the locked audio mux. The smallest production-quality continuation is:

1. ~~Obtain independent exact-frame ratification of Candidate 03.~~ Complete in `collab/CLAUDE_REVIEW_2026-08-10_1712Z.md`.
2. Make the one authorized, versioned 7.6-second A/V encode with the locked Phase 33 delivery mix and decoded audio/video receipt.
3. Build the 10.1-second, 303-frame **Ledger Pour** slice: 75 frames of the accepted GS060 pour, 162 direct-address frames, then 66 compassion-close-up frames.

Do not rerender Candidate 03 or change its thresholds. The exact review receipt now permits one encode only; verify that encode against the lossless archive before beginning Ledger Pour.

Post-proof portability note: the live renderer subsequently replaced the optional `soundfile` WAV-header probe with a standard-library RIFF parser that explicitly validates PCM and WAVE_FORMAT_EXTENSIBLE PCM, so the Python 3.11 Linux CI suite does not require a new dependency. The exact renderer that produced Candidate 03 remains preserved in the archive above and in commit `b06981d`.

## Resume commands

```powershell
python -m unittest pipeline.tests.test_cartoon_source_textured_face pipeline.tests.test_cartoon_source_textured_delivery pipeline.tests.test_cartoon_source_textured_face_v2 pipeline.tests.test_cartoon_source_textured_acceptance_audit pipeline.tests.test_cartoon_source_textured_direct_address
python -m pipeline.cartoon_source_textured_direct_address --development-label candidate-03
```

The render command is listed for reproducibility only. Its immutable output already exists locally and must not be overwritten.
