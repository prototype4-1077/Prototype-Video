# Claude review 2026-08-13 0612Z - Phase37 V3 canthus-preserving diagnostic + Candidate03 audio build

Scope of this pass: everything GPT shipped after `CLAUDE_REVIEW_2026-08-11_1212Z.md`
(phase37) and `CLAUDE_REVIEW_2026-08-11_1959Z.md` (candidate03). Two commits reviewed:

- `c4ca1b9e` "Add canthus-preserving eyelid diagnostic V3" on `agent/phase37-eyelid-crease-ab-v1`
- `acbbc10e` "publish authorized Candidate03 audio evidence" on `agent/phase36-candidate03-audio-repair-v1`

This file grants **no** authorization. No verdict token is issued. No encode, render,
rebuild, promotion, retry, or human-acceptance authority is created or implied here.
Nothing was dispatched. `main` was not touched.

## 1. Candidate03 audio build - honored the authorization exactly; independently re-measured

The build consumed `CLAUDE_REVIEW_2026-08-11_1959Z.md` and produced exactly what was
predicted. Verified by download, not by reading GPT's receipt:

- WAV SHA-256 `a75b39fbae9d0be8b5853a78b1201f0498b188587e0a3366fa5f6338a19c0c0c` - **matches prediction**
- PCM payload SHA-256 `5cc890db17a2f38aac67fe26c6381b0eab43dd6ae1c4200097e3e98f06fd19f3` - **matches prediction**
- 484,800 stereo frames, 48 kHz, 24-bit, 10.1 s - matches the picture-side contract
- one attempt, claim present, `authorization_consumed: true`, `further_build_attempt_allowed: false`

Independent diff against the rejected Candidate02 WAV (my own decode, not GPT's proxy):

- changed sample frames: 39,838, **contiguous**, spanning exactly 2.4700 s - 3.3000 s
- every sample outside that span is byte-identical to C02
- peak unchanged at -1.294 dBFS, zero clipped values in either mix
- splice discontinuity: entry 0.0105, exit 0.0063 adjacent-sample delta, both **below** the
  0.0367 typical adjacent delta in the 0.1 s of untouched material before the splice.
  No click, no step at either boundary.

My own STFT (2048/hann/512) on the repaired span, versus C02:

| window | spectral flatness (med) | energy >4 kHz (med) | RMS |
|---|---|---|---|
| C02 2.47-3.30 | 0.4548 | 65.1% | -37.4 dBFS |
| C03 2.47-3.30 | 0.0000 | 0.20% | -42.6 dBFS |
| C03 0-2.47 (untouched) | 0.3946 | 50.8% | -40.5 dBFS |
| C03 3.30-10.1 (untouched) | 0.1873 | 27.9% | -23.4 dBFS |

**The static is gone.** Flatness collapses to zero and high-band energy drops by a factor
of ~320. That part is not in dispute.

**New risk introduced, and it needs James's ear.** The 4 kHz linear-phase low-pass took the
air out with the hiss. Inside the repair the mix has effectively zero content above 4 kHz
while the material either side sits at 51% and 28% high-band, and the span is also ~5 dB
quieter than what it replaced. The likely percept is not static but a 0.83-second hole -
the porch going dead and then coming back. That is a taste call, not a metric; GPT's proxy
thresholds are artifact-regression gates and correctly do not claim otherwise.

**Audio verdict: machine-clean, human-listen still required.** Ask James to listen for the
transition *into* 2.47 s and *out of* 3.30 s rather than the middle of the span.

## 2. Phase37 V3 - four standing criteria

Media viewed (downloaded raw, inspected at native 1x, and at 8-10x nearest-neighbour on the
write regions; not read from GPT's summary):

- `phase36-f248-four-state-canthus-preserved-3x.png` / `-1x.png`
- `phase35-f173-four-state-canthus-preserved-2x.png` / `-1x.png`
- `phase36-f248-disputed-canthus-preserved-vs-v2-filled-v3.png`
- `phase36-f240-f256-canthus-preserved-neighbor-sweep-v3.png`
- `phase37-eyelid-occlusion-machine-report-v3.json` (41 gates, 0 failed)

### (1) Identity stability of the locked GS070 plate under deformation - **PASS**

Native changes are confined to declared supports (`native_changed_outside_allowed_support: 0`,
and 0 outside the twice-transformed support after head warp and both camera transforms). The
neighbor sweep F240-F256 shows 16 of 17 frames AFTER-IDENTICAL, F248 alone CHANGED. Candidate03
leaves `picture_reference_hash_unchanged` and the frame-hash inventory intact. June stays June.

### (2) Mouth/viseme legibility at speech rate - **NOT EXERCISED**

Still-only, eye-region crops. No change from the 2026-08-11 position. Nothing to re-judge.

### (3) Upper-face stillness - **SPLIT: crease PASS, sclera write FAIL**

**Crease suppression - PASS, and it is a real improvement.** In F248 BASELINE both upper lids
carry a hard, near-straight, uniform-grey line that ignores lid curvature and overruns onto the
temple on the viewer-right eye. It reads as drawn-on, not anatomical. In CREASE-ONLY it is gone
and the lid resolves to a clean dome with the registered natural fold beneath. Same result at
F173. Ship this half.

**Sclera write - FAIL as rendered.** At 10x native on F248, the write does not cover a bright
sclera sliver with lid texture; it stamps an axis-aligned dark-brown bar (~20x4 native px solid
core, 34x24 px bounding box) into the middle of the pale lid-margin crescent, with squared ends,
leaving pale material on both sides of it. It is a straight slab laid across a curved feature.
The same defect reproduces at F173 at smaller scale (~8x2 px core, same squared ends, same
partial coverage). Edge profile is feathered over 3-5 px, so it is not a binary stamp, but there
is a +17-unit brightness overshoot immediately outside the trailing edge - a faint ridge.

Two aggravating factors:

- **Asymmetry.** Per the write audit, viewer-right eye takes 82 candidate px / 36 new hard-owner
  px; viewer-left takes 2 / 0. I measured 282 changed px on the right half of the F248 crop and
  **zero** on the left. At full closure the two eyes now differ: one intact crescent, one bisected
  by a dark bar.
- **Single-frame.** Only F248 changes in the whole F240-F256 blink. A hard-edged dark bar that
  exists for exactly one frame in an otherwise smooth closed lid is a one-frame pop in the eye
  region - the failure mode criterion (3) exists to catch.

GPT's report flags the *upper* pale band as a human-taste question
(`remaining_upper_pale_band_classification`) but does not flag the lower-margin bar at all. The
classifier is treating part of a curved specular lid-margin highlight as under-occluded sclera.

### (4) Jawline/beard seam under motion - **NOT EXERCISED**

Eye-region crops only, no motion media. Unchanged.

### Disputed medial canthus, V2 filled vs V3 preserved

V3's preservation is the better call and I endorse it: the 3-px viewer-left inner-corner glint
survives and reads as a catchlight. V2's fill flattens it to a notch. This is a small difference
and either would survive review, but preserved is right, and it correctly stays NO-GO for
rebuild without James. Note that **both** variants carry the lower-margin bar from section (3) -
it is not a canthus-policy artifact.

## 3. Smallest next experiment

Do not rebuild the picture on the combined proposal as it stands. Split it:

1. **Re-issue the diagnostic with crease-only as the candidate for rebuild.** It is the half that
   passes, it is independently gated, and it does not depend on the sclera classifier.
2. **For the sclera half, one still-only V4** with two changes: (a) constrain the write to the
   lid-margin's tangent so it follows the crescent instead of crossing it, and require all-or-none
   coverage of a contiguous margin run - partial coverage of a bright curved feature is worse than
   no coverage; (b) render the viewer-left eye under the identical rule and publish both eyes at
   10x native, so left/right consistency at full closure is visible rather than inferred. Same
   frames (F173, F248), same neighbor sweep, still no encoder.
3. **Audio v4 A/B, if James dislikes the hole:** shelve rather than brick-wall - keep the ambience
   above 4 kHz at roughly -12 dB instead of removing it, so the room stays alive across
   2.47-3.30 s. One additional audio-only build, A/B'd against v3 for his ear. Requires a fresh
   authorization; none is granted here.

## 4. For James

- The Candidate03 audio is built and byte-exact to what was authorized. It needs his ears before
  anything else moves - specifically the two transitions at 2.47 s and 3.30 s.
- The eyelid fix is half good. The synthetic crease removal is clean and worth shipping. The
  sclera-fill half introduces a one-frame dark bar in one eye and should not go into a rebuild
  until it follows the lid margin.

-- Claude
