# CLAUDE 2026-08-10 2116Z - Phase 36 Candidate 01 per-shot review; Candidate 02 audio-only authorization

Reviewed at branch head f1d5148aac (new commits 824b90ecd8, f1d5148aac since my 2007Z
addendum; GPT notes p/q/r read). Every hash below was recomputed this session on fresh
raw downloads from the branch; none is copied from GPT's notes.

## Candidate 01 visuals - per shot, four criteria plus 3a

Evidence viewed: key-beats, cuts, blink-eyes-2x, compassion, and liquid sheets, plus
full-resolution F075/F076/F237/F238/F248 (all hash-bound at foot of this review).

Shot 1, pour, F001-F075 (wide):
1. Identity PASS - plate locked (window, lantern, porch shadow constant); June consistent
   across all pour keys under the lean-and-pour deformation.
2. Visemes N/A - no speech before F100; mouth holds a soft downward-focus smile, no
   phoneme activity to leak.
3. Upper-face stillness PASS - brows steady through all shot-1 keys.
4. Jaw/beard seam PASS - F075 full-res clean under the deepest head-down pose.
Liquid (shot-specific): stream onset F017-F024 with correct spout contact, opaque arc,
monotonic mug fill F024-F066, clean tilt-back termination F073-F075. No floating-droplet
or detached-stream artifacts at sheet scale.

Shot 2, direct address, F076-F237 (medium):
1. Identity PASS - F076 vs F237 full-res: chimes, road, farmhouse, lantern all locked;
   June unchanged after 161 frames of speech.
2. Visemes PASS - F237 mid-speech full-res: teeth and lip line crisp, mustache fibers
   distinct, no smear; speech keys F100-F207 show clearly differentiated mouth shapes.
3. Upper-face stillness PASS - brows neutral across the full speech run.
4. Jaw/beard seam PASS - fiber field continuous at full res.

Shot 3, compassion punch-in, F238-F303 (close):
1. Identity PASS - the punch-in magnifies everything and June still holds exactly.
2. Visemes PASS at key scale - F267/F276/F277 mouth shapes distinct.
3. Upper-face stillness PASS with carried watch item - quarter-step blink F244-F252 is
   natural and brows stay static through it; F248 full closure carries a faint dark
   hairline across both lids, plainly visible in the 2x sheet, faint at 1x full-res, one
   frame (33 ms). Same character as the phase35 F081/F173 carried P2 fold, not worse.
4. Jaw/beard seam PASS - clean even at F248 closure.

Cut 1 (F075 to F076) and Cut 2 (F237 to F238): continuity-clean - mug fill state, steam
wisp, wardrobe, and lighting all carry across both edits.

Visual ruling: Candidate 01 picture is accepted for bit-exact reuse, consistent with the
failure receipt's picture_may_be_reused_bit_exact=true.

## Candidate 01 audio - rejection independently confirmed and RATIFIED

On a fresh download of june-phase36-ledger-pour-mix-v1.wav (sha256 d9450edd...338207,
matching the manifest): samples [120000:158400) are exactly stereo digital zero - every
byte 0x00. The preceding 100 ms measures RMS -43.169 dBFS, matching GPT's figure at the
reported precision. Root cause, found independently: the committed phase33 delivery mix's
own head [0:38400) is itself digital silence, and c01 [158400:484800) is bit-identical to
phase33 [38400:364800). The hole is inherited source silence, not a mixer regression -
and zero-to-zero transitions are exactly what an adjacent-sample step gate cannot see.
The preregistered rejection PHASE36_CANDIDATE01_REJECTED_AUDIO_CONTINUITY_NEW_BINDING_REQUIRED
stands; the historical 30/30 machine pass is preserved as reference; promotion remains
blocked.

## Candidate 02 repair - independent verification

- Lock hashes recomputed and all match the contract: failure receipt bd11323a...,
  manifest 0c97ba94..., c01 PCM d9450edd..., bridge ed938d8b..., phase26 slice
  e902365f..., phase33 mix e5cd5ebd.... The contract canonical hash reproduces as
  sorted-key compact JSON: aa18088d....
- Bridge structure: frames [1440:39840) are bit-identical to the committed phase26
  slice; head [0:1440) reproduces the declared curve (equal-power cos/sin, t=i/1439,
  round-half-to-even, integer domain) bit-exactly - 0/2880 channel-sample mismatches;
  bridge[0]==c01[118560], giving exactly the declared 39,839 changed sample frames.
- Assembling c01[0:118560) + bridge + c01[158400:484800) reproduces BOTH predictions:
  PCM payload 24f32feb... and canonical WAV f498ba44.... The repair changes nothing else.
- Assembled continuity: junction max inter-sample steps 0.017 and 0.051 (ordinary signal
  scale, no click), longest residual all-zero run 0 frames, peak 0.862 unchanged.
- Code and gates: cartoon_ledger_pour_audio_repair.py is fail-closed (null receipt means
  build blocked), stdlib+numpy only, no subprocess, encode_authorized hard-false; the
  contract forbids resampling, loudness processing, and lossy encoding, and locks the
  picture reference untouched (copy/decode/rerender/mutate all false).

Two notes, neither blocking: (a) the phase26 master is repo-external, so the slice's
provenance to master hash bff9ae4d... is declared rather than recomputable here; this
authorization binds the committed slice hash, which is sufficient for an audio-only
build. (b) The filled interval's porch bed runs about 5 dB hotter (-37.4 dBFS) than the
c01 bed immediately pre-bridge (-42.7 dBFS); over the 30 ms equal-power ramp this reads
as a gentle ambience swell into the pour and speech onset - plausibly the original
phase26 perspective, but it goes on James's listen list for eventual encode review.

## Verdict: PHASE36_CANDIDATE02_AUDIO_ONLY_UNENCODED_BUILD_ALLOWED

Binding hashes for this authorization:

- Candidate 01 failure receipt: bd11323a9e416a439b70d21e99a21b41beb5fc98679590b476485f2e46a9d5c1
- Candidate 01 manifest: 0c97ba94987b8fabf1e1dd0d9c7b1229cfa6edc240ec9ef1fcccf3d45405d9a2
- Candidate 02 bridge WAV: ed938d8b77ed43939018ebabf875ef50d6dd5385ebf5648ef559659780ff432f
- Predicted Candidate 02 WAV: f498ba44f9443b2b025da6fe607322df7f47a7b22ce2a82e987419602ff3d781

Scope: at most one immutable unencoded audio-only Candidate 02 build. All 303 RGB frame
hashes and the lossless archive binding stay unchanged (inventory d09bcdc6..., archive
93eb2cd7..., 415,959,046 bytes). No picture rerender, no picture mutation, no video
encode, no promotion. Any Phase 36 encode remains separately blocked pending the VUI
transfer/primaries fix confirmed by the 9-frame blink probe (1910Z terms carry). If the
built WAV's readback hashes diverge from the predictions above, the build is rejected
without retry and a defect receipt is required.

## Smallest next experiment

Run the authorized Candidate 02 build and publish its receipt with full readback hashes.
Cheap and useful in parallel: the 9-frame blink encode probe with corrected color flags,
so the encode path is proven before any Phase 36 encode binding is drafted. Optional and
purely James's taste: a single-frame lid-texture patch experiment for the F248 closure
hairline, judged on a regenerated blink sheet only - no full rerender.

## Diagnostics viewed this session (sha256 of fresh downloads)

- key-beats ec5dbdb9d57bed1495092bb68e97467be45bb3f58e248fbee1ab896bbc02e3c3
- cuts 917a64bc75b25af9c32f0d05cfce35ceadcb1b349fc0605e25339741e3e55a4c
- blink-eyes-2x 5c287dcfd96e455885a4109b9bbe35aa8570613247286b635ae0f401e204c609
- compassion 979b57c14facf92649206c7934537ee3e7045c04d6b71123d88669691bb31d5c
- liquid 16b54b65db54ceaffb468be78dfdbedf8399f33e657cabe8e8f0dce750e6d76c
- all-303 c241a99adf03d5e5fd337f81a1b8e16c52a5b379084ffec6df7b6e09f8489ea6
- frame_0075 1782ed1de555e74c03177dffcee02deb7d99298acd4ab1e40f8838e90555ce3b
- frame_0076 4493748373cf7445f8d9cae046efdb1014f331d2db1bfd922020261372cb707d
- frame_0237 3b8cc4899d658d5133348d399992d77ccf999ca63a3dfae587b579cf2c361777
- frame_0238 bf9799014599de78e6ec22d9fa1076bf0475e77165b22cdf9e0934f2f7f1c6dd
- frame_0248 70c4c66556388d7f345dac081d14706846fd80aefa20a8d23ea20de84927e2dc
- waveform 36f9ad5e3a5d5f7557ea92dd902ed896faf64ce4dc2b8268e3578431fbce08f7
- spectrogram aa7b818ea15366cca3c4cc945c2e12e3620bc81250bcd6f752417ed96862aac4

- Claude
