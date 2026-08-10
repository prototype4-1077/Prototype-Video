# GPT 2026-08-10 - dormant Phase36 ProRes 4444 review-master transaction

This isolated branch adds the downstream professional review/interchange path only.
It does not render, repair, rebuild, encode, mux, or promote any Phase36 media.

The accepted sources remain immutable:

- Candidate01 RGB24 XOR archive SHA-256 `93eb2cd752d745a6f6fd534912ff68ee24e7bf72cf7cd406d2a366adea97d404`
- 303-frame inventory canonical SHA-256 `d09bcdc6a3c86e26e9ce77070f18504f3101e4b87edfc54e169e3b4b641a6451`
- Candidate02 WAV SHA-256 `f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781`
- Candidate02 PCM payload SHA-256 `24f32febdb18206956fff3ea2de7119dc43a00f9eab37780b94edc948871cb46`

The proposed first delivery transaction is MOV, FFmpeg `prores_ks` profile 4/`ap4h`,
10-bit 4:4:4 encoder input, 12-bit `yuv444p12le` decoded ProRes semantics, no alpha,
limited-range BT.709, and exact PCM24 stereo at 48 kHz. It carries all 303 frames at
30 fps and all 484,800 audio samples for exactly 10.1 seconds. The media is explicitly
described as FFmpeg ProRes-compatible, not Apple-certified encoding.

Synthetic controls proved that direct output flags alone write unspecified MOV
primaries/transfer (`2/2/1`). The frozen command therefore sets frame color properties
explicitly before `prores_ks`; the controlled version produced stream/frame BT.709 and
one `nclc` atom at `1/1/1` in the pinned toolchain.

## Frozen scaffold bindings

- authorization subject canonical SHA-256: `603d66999150540dd7f6b4ffeb532ad7937c95af914f3a0f5a89dbae47aeaa79`
- contract raw SHA-256: `de152841cd3543713c2f26824d994aa472918aacc514300e3dfe42071a488aed`
- implementation SHA-256: `62f0c1667b5a9d2e8eccfd977ba273f543bb4d2630d69d5cba3a4b76164eabad`
- command-template canonical SHA-256: `35db54584421340a8c6486340b188e8575d2a66201bb29dc7534b1850b82d61b`
- tests SHA-256: `68d53a941fcd8040c645e5b25ea2a2649f631bcc16c6755f009382d121c3c634`

Twenty-three focused tests pass. The real no-encode preflight reconstructed and checked
all 303 frames, produced combined RGB24 SHA-256
`8a8fdc2a572ec1037e29a475b00e49454a059a73a751444458de95531bfa6501`,
verified the exact PCM payload and pinned FFmpeg/FFprobe/Pillow versions, started zero
encoders, and resolved no output.

The transaction uses integer PTS gates (512 ticks per frame at time base 1/15360;
duration 155,136 ticks), all-frame color gates, exact decoded PCM, bounded decoded
picture metrics, exclusive final-path claim creation, immutable rejection preservation,
an exact success artifact allowlist, extracted review frames, and a separate human
PASS/REJECT receipt schema. Independent adversarial runtime review is GO after injected
copy and claim-fsync failures were both sealed correctly without launching an encoder.

## Deliberate null gates

`vui_prerequisite.probe_result_receipt` is null and `authorization.receipt` is null.
`run-authorized-master` refuses on the VUI null before tool discovery or output
resolution. The failed VUI V1 result must not be bound as a pass. After the separately
reviewed V2/Attempt02 VUI successor passes, bind that exact report here, recompute/freeze
the master subject, request a new hash-bound master authorization, and only then run one
attempt.

No PR should be opened from this branch; publishing it is for branch-level review and
handoff without spending the main render workflow.
