# CLAUDE 2026-08-11 0953Z - Phase 35 c03 blink VUI probe V2 Attempt02: evidence review

Reviewed evidence published at commit d61fd1e5 ("publish passing Phase35 VUI Attempt02
evidence") on agent/phase35-blink-vui-probe-v2-attempt02, per GPT_NOTES_2026-08-11a.md.

## Session note

My sandbox VM was down during the initial 0953Z pass, limiting it to raw-download
inspection of the text artifacts. The VM recovered at 1044Z under James's
supervision and every deferred check was completed before this file was committed -
see the 1044Z addendum at the bottom. Nothing in the initial pass changed; the
addendum only strengthens it.

## Independent verification (raw downloads, this session)

- ffprobe-stream-v1.json: h264/avc1, High 4:4:4 Predictive, yuv420p, 1920x1080,
  30/1 CFR, 9/9 frames, 0.300000 s, stream color tv/bt709/bt709/bt709. Matches the
  report's embedded copy verbatim.
- ffprobe-frames-v1.json: all nine frames tv/bt709/bt709/bt709. Matches verbatim.
- h264-sps-trace-v1.txt: exactly one SPS; video_signal_type_present_flag=1,
  video_full_range_flag=0, colour_description_present_flag=1, colour_primaries=1,
  transfer_characteristics=1, matrix_coefficients=1. Bitstream-level confirmation.
- probe-report-v1.json: 33/33 gates pass with actual==expected on every gate,
  checked field-by-field. The two Attempt01 failed gates (video_color_transfer,
  video_color_primaries) and the two V1 probe failed gates (stream_color_metadata,
  mp4_colr_nclx) all now pass. MP4 colr: one hierarchical nclx at
  moov/trak/mdia/minf/stbl/stsd/avc1/colr, 11-byte payload, 1/1/1, full_range 0,
  reserved 0 - the exact V1 mux-side defect, cleared.
- Authorization binding: the report carries my 0119Z receipt path, lf_normalized_text
  domain, sha 9e9e1f74..., verdict string exact. Command template 1b8ec1b0...,
  implementation fcf8301b..., source archive b5908bfc..., selected payload
  a32e61da..., ffmpeg 228d7a85..., ffprobe 0fde260f..., and all nineteen repository
  locks match my bound tokens value-for-value.
- Pixel invariance: decoded aggregate RGB24 a0f093e0... and all nine per-frame
  hashes equal V1's recorded decoded values - the same values I verified against the
  immutable V1 report during the 0119Z session. A metadata pass could not have
  concealed a pixel or range change.
- Encoder stderr sha e3b0c442...b855 is the SHA-256 of the empty string: silent,
  clean encode. process_count 1, return_code 0, exactly one invocation, no retry.
- Corroborating detail: GPT's note lists Attempt02's frame-probe hash 128f9b67...
  identical to the vui_probe_v1_frame_probe lock. Correct and expected - V1's defect
  was container/colr-level only, so the V1 and V2 frame probes are byte-identical.
  A consistency point in the evidence's favor.
- PSNR floor 42.65527255467107 dB >= 39 required (minimum at probe frame 6 / F082).
  Chroma subsampling loss inherent to yuv420p; disposition honestly retains
  attempt01_chroma_failures_cleared=false - out of probe scope, as bound.
- Disposition denies all further authority: no full Phase 35/36 encode, no c02 mux,
  no delivery, no promotion, retry_allowed=false, authorization_consumed=true.
  Matches the authorized scope exactly.

Not machine-checkable from the repo: the note's "three independent agents returned
GO" preflight claim. Non-blocking; the single-transaction evidence stands on its own.

## Verdict: PHASE35_C03_BLINK_VUI_PROBE_V2_ATTEMPT02_PASS_RATIFIED

Gate (a) of James's 2026-08-10 three-gate state - VUI/color metadata - is cleared.
Status METADATA_PROBE_PASSED_NO_DELIVERY_AUTHORITY accepted as written. This
ratification grants no delivery, mux, encode, promotion, or retry authority.

## Four standing picture criteria

Decoded pixels are hash-identical to the already-reviewed V1 frames, and I
additionally viewed decoded stills directly this session (addendum). (1) identity
stability: PASS - June stays June through the fully-closed-lid extreme at F081.
(2) viseme legibility: n/a for this evidence (blink clip, no speech; mouth static
by design and observed static). (3) upper-face stillness: brows do not move across
F077/F081/F085 - consistent with the standing pass. (4) jaw/beard seam: no visible
seam artifact across the blink; motion here is lids-only, so this is corroboration,
not a full motion retest. The F248/F081 lid fine-geometry defect remains the open
picture item - full-frame 1080p stills show no gross artifact at F081, but the
defect James flagged is crop-scale; adjudication stays with gate (c) before/after
crops.

## Smallest next experiment

Gate (b) (audio repair with the human-audible-noise proxy) is parked on James's ear.
Gate (c) is next for GPT and needs no new render authority to start: publish the
F248/F081 lid root-cause analysis with before/after reproduction crops decoded from
existing committed/verified source bytes only (bind any not-yet-locked source bytes
first; decode-and-crop, no new render), plus a proposed single-attempt fix contract
in the V2 pattern. I will view the crops directly next session and, if the contract
is exact, issue the fix-attempt authorization receipt. The ProRes 4444/PCM24 master
branch stays dormant, unbound, and unlaunched.

## 1044Z addendum - deferred checks completed, all green

VM recovered; James present. Everything below performed on my own sandbox toolchain
(system ffmpeg/ffprobe), not GPT's pinned binaries, from fresh raw downloads at the
immutable evidence commit d61fd1e5.

- Byte-rehash, all eleven package files: every SHA-256 matches GPT's published
  values exactly - video 04140edd... (2,803,370 bytes exactly as reported), report
  047d4bd8..., package c01cdbb9..., claim 41534b41..., SPS trace 85c23341..., stream
  probe 86d23493..., frame probe 128f9b67..., and all four stderr files empty
  (e3b0c442...). Eleven-file inventory exact. .gitattributes now byte-locks
  collab/phase35_candidate_03_blink_vui_probe_attempt_02/* with -text, implementing
  my 0119Z hash-domain recommendation - thank you.
- Independent decode replicated: my ffmpeg produced decoded RGB24 aggregate
  a0f093e08ae1e24b5e2d343877023995142632b5b5f5d5201309649617f06e5b over exactly
  55,987,200 bytes - byte-identical to the report, V1, and the bound acceptance
  value, on a different toolchain. My ffprobe independently reads
  tv/bt709/bt709/bt709.
- Direct visual review: decoded stills at probe frames 1/5/9 (F077/F081/F085)
  viewed at full frame. Coherent full blink, identity stable through closed-lid
  extreme, mouth/brows/hand/background static, no flash, no face-swap jitter, no
  seam artifact. GPT's contact-sheet description is corroborated.
- Auditor note on an expected hash delta: the report's contract raw_sha256
  d6af2de3... differs from my bound token 4 (ce7fea2e...) because binding my receipt
  into authorization.receipt necessarily changes the contract's raw bytes. The
  binding-invariant authorization_subject_sha256 5fb952bf... matches my bound token
  1 exactly, which is precisely what the subject-hash mechanism exists to guarantee.
  Not a defect; recorded so nobody trips on it.

Verdict unchanged and strengthened: PHASE35_C03_BLINK_VUI_PROBE_V2_ATTEMPT02_PASS_
RATIFIED. Gate (a) cleared. Next: gate (c) lid root-cause crops per above; gate (b)
stays parked on James's ear. - Claude
