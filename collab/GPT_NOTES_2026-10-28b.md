# GPT notes — 2026-10-28 — both components pass; full integrated scene rendered

Parent checkpoint: `df152e55297976a83556a1a2c26e55b219620038`.
Branch: `agent/phase42-human-rejected-gates-repair-v1`.

## New controlling human evidence

James: **"both are good and pass. continue"**. This explicitly accepts the
recorded-Foley v3 WAV and the candidate on the right of blink v3. Read
`collab/JAMES_VERDICT_2026-10-28b.md`; the exact artifact hashes and bounded
next-review scope are in
`concept/characters/june_oxley_phase42_component_acceptance_v1.json`
(SHA-256 `52c1f98020ff143ecb2d00f670284eb3cd79697e77aeee92107a100c7fc67e66`).

Do not ask him to re-accept the components or treat the original reports'
pending-review fields as a later rejection. Those old bytes remain unchanged.
This is not acceptance of an unseen full performance, production release,
main merge, or the entire competitive-cartoon objective.

## Implemented full review

`pipeline/cartoon_scene_review.py` uses the existing body/face/head/camera
stack under a restored-context v3 eyelid override. The old first blink is
removed; the accepted late slower curve closes at output F247-F248 (~8.2 s).
Source F173 full-close RGB remains exactly
`155cab57828f6b0e46a8a36ed4ab0b8cb8950918d02cca3803b473fd2786db40`.
Body acting is active in 129 dialogue-section frames; protected face and mug
regions are checked on every composed frame.

The earlier `cartoon_repaired_acting.py` remains a historical sampled-still
adapter and still binds old balanced-air audio. The new renderer never uses
that file as the output soundtrack. Its source is the exact approved WAV.

Opening F001-F075 comes from the immutable verified lossless archive, never
an old encoded movie. The archive reader verifies all 303 old RGB hashes and
retains only the unaffected opening. The 228 dialogue/camera frames are newly
composed with accepted eyes and existing body motion. The three shots encode
once apiece, then stream-copy concatenate; the second output container does
not re-encode the picture. No new voice/image generation or paid service runs.

Review package: `collab/phase42_integrated_scene_review_v1/`.

- MP4, portable H.264/AAC:
  `fe68c2852ee36d04c49382c0b8dc558dae1a6ccfa44be6526586b286c667437c`
- MOV, same picture + exact approved PCM24:
  `e5c3d2dd371bffe53b77c0015469d110d574e544c79f8ee2deb4c28f1f95e08e`
- Scene report:
  `b03ea10a48a82fc4a0c39c77b5b2f1d5fff39e89c06514d9ebf37b30d4a13a99`
- Implementation:
  `6637e6ddd953175ba7c7bac054ccfe74513666b1d85db4f874d1cf7de12104d3`

## Verification, failures and scope

69 focused local tests passed in 93.056 s: scene review, recorded Foley,
source isolation, sparse Foley, blink refinement, older repaired integration,
continuous blink, eyelid source, old full-mix successors and noise proxy.
This is not a whole-repository/cloud-CI pass or an aesthetic verdict.

Every output frame decoded at exact 30-fps timestamps, with 303 frames /
10.1 seconds, no gap/duplication/offset. Actual stream metadata is BT.709
primaries/transfer/matrix, TV range, 1:1 pixels. All 75 opening frames remain
original RGB; accepted audio in MOV is bit-exact at all 484,800 stereo sample
frames. MOV/MP4 video packet hashes match. AAC preview SNR is 42.540777 dB,
with 576 decoder padding samples beyond the source duration. Sampled picture
compression checks cover 28 frames, minimum full-frame RGB PSNR 40.050542 dB.
Do not promote those sampled checks into a full reference-pixel audit.

Used the video-review workflow on decoded contact sheets, cut filmstrips and
waveforms (2.5-s and 7.9-s cuts), plus the full-close source frame. Those
inspections support the review package; they do not substitute for watching
the complete performance or listening to the AAC preview.

An initial old-loader attempt stopped before producing frames at a legacy
raw-text lock. It is preserved under
`outputs/edit/phase42-integrated-scene-review-v1-initial-legacy-loader-failure/`.
No legacy gate was relaxed or rejected artifact overwritten. Using the
already verified lossless opening removed that unnecessary loader dependency.

The first complete encode passed picture/audio clocks but failed self-review:
stream flags alone dropped color primaries/transfer and pixel-aspect metadata.
Preserved it, its report and exact implementation snapshot under
`outputs/edit/phase42-integrated-scene-review-v1-missing-color-metadata/`.
Reused the project's proven frame-level setparams/x264 recipe for the fresh
corrected build; no h264_metadata bitstream patch or lossy-input re-encode.
Metadata checks were strengthened, not waived. All 303 source RGB frame
records are identical before and after this delivery fix.

The corrected build retains a 484,174,385-byte lossless RGB cache outside Git:
`outputs/edit/phase42-integrated-scene-review-v1/scene-rgb24-xor-v1.gz`, SHA-256
`dbb1370891f09583b8ad5696084c8d2ef116df301cca849df56726fa9fc65982`.
Independent gzip/XOR readback verified every reconstructed frame against the
inventory. Combined RGB digest:
`0c4ea62e79f065c86a34ed035e1fe15390228909c6f57fe01f2910d345f15c26`.
The public receipt is `lossless-cache-independent-audit-v1.json`.

Candidate03 WAV still hashes to
`a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c`;
Phase37 V4 report still hashes to
`fd08ee030123fc96585994825fc49942a937e9e631722478fa54bcee6bc36a7f`.
Main and all old proofs were untouched. No cloud render/paid API ran.

## Schedule and pickup

Updated the existing five-hour heartbeat's instructions, not its frequency,
target chat or active state. It now preserves the passed components, starts
from this integrated review, avoids unchanged rerenders, and stays quiet when
there is no meaningful new review/work. It must not reopen the old eye/static
loop merely because frozen historical reports say pending.

1. Read new human/Claude feedback before building. New combined performance
   remains pending; accepted eye/audio gates are closed unless a new regression
   is reported. Latest Claude review remains 2026-08-13_0612Z.
2. Present the complete normal-speed MP4. The 13-frame eye WebP is a diagnostic
   stress loop, **not** the scene's blink frequency. Never ask James to judge
   cadence from that rapidly repeated crop.
3. Recommended next artistic target: a more complete pour-recovery / turn-to-
   camera beat and purposeful hand/gaze acting. The existing cut carries the
   transition; this is now a performance/staging question, not a reason for
   another eyelid or blanket-audio repair. Inventory existing recovery poses
   before considering new art or another engine.
4. Reproducibility gap: the local builder needs the preserved 415,959,046-byte
   opening archive, which is not in a fresh Git checkout. A self-contained
   source package/cache-independent opening path is still needed. Published
   review videos themselves play independently. Do not claim episode-scale
   production or universal fresh-clone readiness.
5. Keep the full objective unfinished. The prototype is still source-art-based
   2.5D with limited pose/shot coverage; these checks do not establish a genuinely
   competitive general cartoon-production system or authorize production release.
