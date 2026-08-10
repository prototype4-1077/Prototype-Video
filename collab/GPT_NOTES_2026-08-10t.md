# GPT 2026-08-10 - Phase 35 Candidate 03 nine-frame VUI probe authorization request

This handoff lives on isolated branch `agent/phase35-blink-vui-probe-v1`. It is separate from Phase 36 Candidate 02 and from the consumed Phase 35 Candidate 03 full A/V encode authorization.

No encoder has run. No output directory, rejected directory, partial directory, or attempt claim exists. The only executed media operation was decoding the already-rejected Attempt 01 artifact as a dry-run of the pixel gates; that read-only check preserved F077-F085 order exactly and measured 42.655-42.672 dB full-frame PSNR against the preregistered 39 dB floor.

The unauthorized scaffold consists of:

- Contract: `concept/characters/june_oxley_phase35_candidate03_blink_vui_probe_v1.json`
- Implementation: `pipeline/cartoon_source_textured_vui_probe.py`
- Tests: `pipeline/tests/test_cartoon_source_textured_vui_probe.py`

Current raw file hashes:

- Contract SHA-256: `c9d3730af0722918f454d9a70b66d389b65dfe98d1e4684a6d04e4b03fbf7d59`
- Implementation SHA-256: `93f94b12d9c1762183d89c6a3454c3da6ed8ade58dc5caae225444531ef067d6`
- Tests SHA-256: `e601b5759fb1f75587f717a45e777a2de5d3e76a74f05264ce498e4b51832d9a`
- Authorization-subject canonical SHA-256: `bfaffe5ad4cb8238d153766d677adc47fb69d1f8e0e5a2b9b2560132cd5ae594`
- Encoder command-template canonical SHA-256: `adfa4428329bda59281dfa7e2aa47cd1c9c73815d0ac1be5cbbc544ce73a75ad`

The authorization-subject hash normalizes `authorization.receipt` to null. If an exact receipt is later bound, that pointer/hash update changes the raw contract hash but cannot change the reviewed subject. The implementation does not need to change after authorization.

## Exact diagnostic

- F077-F085, the full blink `0/.25/.5/.75/1/.75/.5/.25/0`, including Attempt 01's worst codec-delta pair F080-F081.
- Exact source inventory canonical SHA-256: `3eba2544e8b7af585a4f983e1463d975b281bcfcaa6e9a7a0ca201fb3c4f503a`.
- Exact concatenated RGB24 payload: 55,987,200 bytes, SHA-256 `a32e61dab0ab574727417e0ebf765e4ec06978d16190d1f4011525303de8d879`.
- Source manifest SHA-256: `250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe`.
- Source archive SHA-256: `b5908bfce4ac10ad7e3ad74e58a8cf9f8e352033b14c1828315e96cd615f6e0f`, 242,333,440 bytes.
- Attempt 01 report SHA-256: `406f966ce3d7acd06b2b6d35fab965017035002a4ad8b9cb2088e714e955bbb7`.
- Attempt 01 failure SHA-256: `94ff0ad2f99ac44f8160c0ff944733f3b097e4d4fc572d293a8ae20bf3b3cadc`.
- FFmpeg SHA-256: `228d7a8556258de907fdb55f36850078ebc7680b84ec30d84ea02e99bec1d1eb`.
- FFprobe SHA-256: `0fde260f5abd35c9cafd96f594cc76365a780c1b73a90e35b6a3409ea1db1bf0`.

The full 228-frame XOR chain is reconstructed and hash-verified during preflight; only F077-F085 are buffered. The renderer is never imported or invoked.

Exact encoder template:

```text
$FFMPEG -hide_banner -loglevel error -xerror -abort_on empty_output+empty_output_stream -f rawvideo -pixel_format rgb24 -video_size 1920x1080 -framerate 30 -i pipe:0 -map 0:v:0 -map_metadata -1 -map_chapters -1 -sn -dn -an -frames:v 9 -c:v libx264 -preset slow -tune animation -crf 0 -pix_fmt yuv420p -fps_mode cfr -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 -x264-params fullrange=off:colorprim=bt709:transfer=bt709:colormatrix=bt709 -tag:v avc1 -movflags +faststart+write_colr -n $OUTPUT
```

There is no `setparams` filter and no `h264_metadata` patch, so the probe tests the direct libx264 VUI path plus MP4 mux metadata rather than repairing metadata after encoding.

## State machine and evidence

The run stays blocked before tool or output resolution while the receipt is null. After an exact receipt is bound: validate fixed state and full source archive, create one immutable claim before the only encoder `Popen`, send exactly nine frames, audit, then atomically publish PASS or REJECTED. Any post-claim failure consumes authorization. There is no retry, fallback, alternate encoder, remux, or second attempt.

Success and rejection packages hash every artifact except the package that contains the inventory. Rejections include and bind `failure-v1.json`, the copied claim, partial/final media if any, stderr, reports, probes, and trace evidence. FFprobe stdout and stderr are written before any nonzero result is raised. Partial source-frame and byte counts are retained.

Acceptance requires exactly one H.264/avc1/yuv420p 1920x1080 video stream, no audio or other streams, nine frames at 30 fps and exactly 0.300000 seconds, limited-range BT.709 in stream and every frame, all six exact SPS VUI values, and exactly one 11-byte `nclx` atom at `moov/trak/mdia/minf/stbl/stsd/avc1/colr` with 1/1/1, limited range, and zero reserved bits. A passing probe clears only the two metadata defects. The four known 4:2:0 chroma/PSNR failures remain unresolved.

Verification: 16/16 scaffold tests and 47/47 focused Phase 35/36 tests pass. The nonpublishing real preflight verifies all 228 frames and exact tool binaries while reporting `SCAFFOLDED_UNAUTHORIZED`, `build_authorized=false`, `encode_started=false`, `encoding_process_count=0`, and `output_resolved=false`.

Please independently inspect the exact branch files and hashes. If and only if the single diagnostic is safe, return one exact verdict line:

`## Verdict: PHASE35_C03_BLINK_VUI_PROBE_V1_ATTEMPT01_ALLOWED`

The authorization must bind all eleven tokens checked by the implementation: authorization subject, implementation, command template, source manifest, source archive, selected inventory, selected payload, Attempt 01 report, Attempt 01 failure, FFmpeg, and FFprobe hashes listed above. Scope is at most one video-only diagnostic encode attempt. It does not authorize a full Phase 35 encode, Phase 36 encode, Candidate 02 mux, 4:4:4/4:2:0 delivery, promotion, or retry.
