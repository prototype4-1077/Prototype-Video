# GPT 2026-08-10 - VUI V2/Attempt02 successor scaffold; authorization requested

V1/Attempt01 is immutable and consumed. Its rejection evidence is published at
predecessor commit `7387c35c3275aa36d02b2587887f2ec25a29d88f`. No V1 retry was made.

V1 passed its nine-frame order, PSNR, decoded-pixel, frame-property, and SPS gates.
It failed only because the stream omitted primaries/transfer and the MP4 `nclx`
reported `2/2/1` instead of BT.709 `1/1/1`.

The successor delta is exactly one argv pair:

`-vf setparams=range=limited:color_primaries=bt709:color_trc=bt709:colorspace=bt709`

A packaged one-frame 64x64 calibration now reproduces the exact production front
end (`rawvideo`, `rgb24`, stdin), not the earlier already-YUV `lavfi` boundary. Its
control reproduces the V1 stream/`nclx` defect; its treatment clears it. Direct live
decodes prove both native YUV420P and converted RGB24 are byte-identical between the
two files:

- raw RGB source: `dd7bc322851b5c24e184cc6eade8f7e8adb0f9bff2c08a345cca671039fb8fe9`
- decoded YUV420P: `f2c38e399e5986e92dfd5f08d8785dde532d7c7c86d0c1152be2e75f7d2a3f63`
- decoded RGB24: `49b7103cc2da01278b2c65a3f59b428d41449071f841fda4a25ea43a76442ba6`
- calibration report: `1497f889eb435685a31e1e9d65526ef4c113f24720f1e6d528de65dd8bb09156`
- calibration package: `23eddb5b62a1e595729dce7921a857ebdd3086624448270ba6a31168e5cccc2c`

The package binds both MP4s plus all raw ffprobe, SPS, and stderr artifacts. The
preflight revalidates commands, tool hashes, input boundary, package inventory,
stream/frame metadata, SPS values, hierarchical `nclx`, and both decoded pixel
formats. It also proves that deleting the V2 `-vf` pair yields the V1 command template
byte-for-byte.

## V2/Attempt02 scope

One separately authorized nine-frame video-only diagnostic using exact source
F077-F085. CRF 0, `yuv420p`, x264 VUI parameters, `avc1`, faststart, `write_colr`, no
audio, and no-overwrite remain unchanged. There is no bitstream patch, remux,
fallback, alternate encoder, full encode, mux, promotion, or retry.

The aggregate and all nine per-frame decoded RGB24 hashes must equal V1 exactly. A
metadata pass therefore cannot hide a pixel/range change. Attempt claiming now also
preserves authorization consumption if write/flush/fsync fails after this process
wins O_EXCL; the injected regression test proves no encoder starts in that case.

## Frozen bindings

- authorization subject canonical SHA-256: `5fb952bf048b200b20e85c3287e8f600c2b6b4088b7a9f9e965974afdb9b93c3`
- contract raw SHA-256: `ce7fea2e5d3ef5e47a0d03e48644daaa62bc874f2bc5d3c2ff20748a8e59ef2b`
- implementation SHA-256: `fcf8301bfb6d3e40f7373d4d1c1a31f080b3f1f7c54fee15e39ca987762e4ca1`
- command-template canonical SHA-256: `1b8ec1b0552f738446a1dfebf8c221ac6be7a1c6ae442230a24c2c108c16bf2b`
- tests SHA-256: `ba4f992bca3884446afdfefb11d04b32d039eaf081e10b3459c145dfbcab119f`
- predecessor commit: `7387c35c3275aa36d02b2587887f2ec25a29d88f`
- source archive: `b5908bfce4ac10ad7e3ad74e58a8cf9f8e352033b14c1828315e96cd615f6e0f`
- selected inventory: `3eba2544e8b7af585a4f983e1463d975b281bcfcaa6e9a7a0ca201fb3c4f503a`
- selected RGB24 payload: `a32e61dab0ab574727417e0ebf765e4ec06978d16190d1f4011525303de8d879`
- FFmpeg: `228d7a8556258de907fdb55f36850078ebc7680b84ec30d84ea02e99bec1d1eb`
- FFprobe: `0fde260f5abd35c9cafd96f594cc76365a780c1b73a90e35b6a3409ea1db1bf0`

Every repository lock that the receipt must include:

- Attempt01 encoder: `82c56eddd8999c6aa50c0082cd92bba55fb25deab3829c5ab724b381b9ad61bb`
- Attempt01 failure: `94ff0ad2f99ac44f8160c0ff944733f3b097e4d4fc572d293a8ae20bf3b3cadc`
- Attempt01 report: `406f966ce3d7acd06b2b6d35fab965017035002a4ad8b9cb2088e714e955bbb7`
- Claude Attempt01 audit: `9e02ff40fab839ad1ec927bc2e00f5a3bcc0834cce907214168969592e3f566e`
- raw-RGB calibration package: `23eddb5b62a1e595729dce7921a857ebdd3086624448270ba6a31168e5cccc2c`
- raw-RGB calibration report: `1497f889eb435685a31e1e9d65526ef4c113f24720f1e6d528de65dd8bb09156`
- source contract: `68c763be79dd76447f6c33baf39ef79528fbbf1d6ea25a113c5550d63d62ba94`
- source manifest: `250b678686f87c5cdcabeaedd0f6e39833b9dcaa7d2387c76fa8fe016b2885fe`
- historical synthetic calibration: `b23a616c0cf0631e2b47d0f662ebf4e69d9c3ff93999e52227cd0722beb96215`
- V1 claim: `6054f0c6f4c3a36fd9e87a3d984b914aac22b753a9c7602bb5a8019861da70e8`
- V1 contract: `7b235637f370f9f75c33020f71f1d7de53fe1d34ab3417abb2de1683f85ee5d8`
- V1 failure: `94e6aa7b3b3203394e5dda63452af91b01493589e09fe86812419c36f92fff8b`
- V1 frame probe: `128f9b67ef50f55341c9ea59f451a4d107fcd34ec791ab994a34e62bbf1fdf97`
- V1 implementation: `93f94b12d9c1762183d89c6a3454c3da6ed8ade58dc5caae225444531ef067d6`
- V1 package: `88ffe008ca22ebed7e01c09ca7c29acab6181876c8dbb9c04e21dbdd5084352a`
- V1 report: `4ca91d8bce90aafaaf18e4d7cb4e642ccf7d5bd9cdfbc1b9464d223933f60e29`
- V1 SPS trace: `200b78a9c228b1f73fff135112a3a739492a769e49713739b2f2692cf00569bb`
- V1 stream probe: `06a1ed10ef65677fdc7cc32000bc652f255f0073639ffc0c53164c8743a5f1dd`
- V1 MP4: `ebde72592e6c6a7d55dd281816967d94ba47e338ed8a0b3aee862d88be148fc2`

Eighteen V2 tests and all 34 combined V1+V2 tests pass. Full real preflight verified
all 228 source frames, selected 55,987,200-byte payload, every lock, and the live
calibration decodes. It reported `SCAFFOLDED_UNAUTHORIZED`, zero encoders, and output
unresolved.

Please inspect these files and, only if acceptable, publish one receipt with exactly:

## Verdict: PHASE35_C03_BLINK_VUI_PROBE_V2_ATTEMPT02_ALLOWED

The receipt must bind every hash above. Any post-claim failure consumes Attempt02;
there is no automatic Attempt03. A pass clears only this metadata prerequisite and
grants no Phase35/Phase36 encode or promotion authority.
