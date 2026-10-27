# GPT notes — 2026-10-27 — clean voice preserved, sparse Foley and blink v3

Parent public checkpoint: `f70b614de50fcbe48b7f2a6c37222e0bec68fabd`.
Working branch: `agent/phase42-human-rejected-gates-repair-v1`.

## Controlling human evidence

Read `collab/JAMES_VERDICT_2026-10-27.md` completely. Key sequence:

1. Blink v2 almost passes; audio static remains throughout.
2. Removing the continuous porch bed made **"No real change"**. The bed-only
   repair hypothesis failed. Do not keep applying stronger filters to it.
3. James explicitly corrected the voice-only answer: **"correction there is
   not static."** Preserve the clean voice contribution. Do not infer hardware
   noise from the retracted silent-opening answer or accept the original mix.
4. Blink clarification: a little too quick and frequent, with just a small
   shape adjustment. This is not a request for a new character/eye design.

## Audio change

Added `pipeline/cartoon_sparse_foley.py`. It preserves the exact voice-only PCM
as an additive component and replaces/omits the old noise-based effects with
subdued damped water/contact tones and chimes. No continuous noise bed, fake
breath hiss, cloth noise, or sustained noise scrape is reintroduced. The mix
minus effects is bit-exact to the clean reference. No speech filter, synthesis,
retiming, or whole-mix normalization occurs.

Package: `collab/phase42_sparse_foley_v2/`.
Report SHA-256:
`24dff185eabfcdc54bb211bf9a27bb0d2a64020e2bc0ddf624314e1d79748ce0`
Main WAV SHA-256:
`a101eb565a828881a42e39ed1b706271eb6a1d4de72c7029f8612fb035e1e776`
Peak -1.370746 dBFS; 484,800 stereo PCM24 frames at 48 kHz.

The mix was displayed inline and James was asked whether it stays free of
static like the voice-only reference. Check any later reply; no answer or
acceptance is assumed here. Tonal effects may sound sparse/stylized and still
need an artistic listening decision.

## Blink change

Added `pipeline/cartoon_blink_refinement.py` with an eye-only fixed-head study.
The old half-second crop loop exaggerated apparent blink frequency. The new
review plays the full 7.6-second cadence: previous two blinks on the left,
candidate one late blink on the right. Closure span grows from 267 to 400 ms,
with two full-close frames, cubic ease, and at most one native pixel of gentle
margin curvature. Exact open and closed artwork remain unchanged.

Package: `collab/phase42_blink_refinement_v3/`.
Report SHA-256:
`bc3c59cd52c68f7d214200aa386df0c7427dbe268908f601868773c0b2fc62f4`
Comparison loop SHA-256:
`768006f6c0333af7cf3f9015e59b6cb69365ab34e6d4e3b9c8c0e66b094813ca`
Candidate loop SHA-256:
`02630d5a6e4a7441edca6c79f4b419deb6794bf46fc4b16cf0610b42fd63edce`

The candidate blink occurs near six seconds. Label the long hold so James
does not mistake a realistic cadence for a frozen preview. This is not full
scene motion: the head/camera pose is locked at source F173.

## Negative experiment and verification

An initial shape attempt remapped quantized alpha and failed monotonicity at
closure .17. Rejected that attempt without weakening the test. The final
analytic-margin formulation passes monotone coverage at 101 closures and tiny
control-step tests; fixed socket support and exact endpoints are preserved.
The failed external diagnostic was recoverably moved to
`outputs/edit/phase42-blink-refinement-v3-rejected-quantized-mask`; verified
output is at `outputs/edit/phase42-blink-refinement-v3` and copied to collab.

Combined focused local run: **40 tests in 14.353 seconds**, covering source
isolation, sparse Foley, blink refinement, continuous blink, eyelid source,
old audio successor, and old noise proxy. Actual PCM subtraction, unchanged
voice, file reproduction, clock, headroom, boundary samples, mask/source
identity, decoded 7,600-ms loop timing, support and context cleanup are covered.
This is not a broad repository/CI pass or perceptual-quality acceptance.

## Resume

1. Check newer human replies before doing more rendering.
2. Review sparse Foley and the v3 comparison at real cadence. Both remain
   unaccepted. Voice-only has only been judged free of static, not cast as a
   final performance/voice approval for the whole series.
3. If static persists, use effects-only to identify an event; do not touch
   the clean voice. If effects are clean but unnatural, improve only those.
4. If the blink passes, carry the explicit v3 timing/shape variant into the
   already working body/camera adapter. Do not mutate the hash-locked v2 base.
5. No full scene/master encode, promotion, paid call, image regeneration, or
   main-branch change occurred. Keep the full-cartoon objective open: these
   remain component auditions, not a finished competitive production system.
