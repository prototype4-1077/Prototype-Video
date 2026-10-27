# James verdict — 2026-10-27 — Phase42 blink close, audio still static

Exact feedback:

> "Blink still needs a little work but really good. It almost passes. The audio still has static"

Asked whether the static is before speech, mainly during the voice, or
throughout, James answered: **"Throughout"**. The opening has no dialogue, so
the continuous background must be isolated before changing the voice. This
does not by itself prove the voice is clean.

This follows the shared Phase42 normal-speed blink and balanced-air WAV links.

- Blink: **NEAR_PASS_NOT_ACCEPTED**. Keep the cleaned source and continuous
  control as the current candidate; do not interpret "almost" as approval or
  restart the eye design from scratch.
- Blink file: `collab/phase42_continuous_blink_review_v2/phase42-eyelid-ai-direct-30fps-v2.webp`.
  SHA-256: `b7675748372f24101f268c0ffcabcfb0aa8ff49179291a913b96e54b67edf2d7`.
- Audio: **REJECTED_STATIC_REMAINS**. The full-mix static proxy's zero result
  did not predict James's listening result. A proxy pass cannot establish
  clean audio; do not simply lower the reported score or claim the noise gone.
- Reviewed WAV: `collab/phase42_human_rejected_gates_successors_v1/june-phase42-fullmix-balanced_air-v1.wav`.
  SHA-256: `d25975e13d1b1fc873214b342e8abb5065ef7409a2a98b523eee846523ba4357`.
- No verdict on the separate clean-warm alternative is inferred.

Next: isolate voice, ambience, and effects at the same gain and clock, identify
the remaining source, and repair that source. Preserve all reviewed artifacts.
Keep both eye/audio gates open; no full render, promotion, or acceptance claim.

## Follow-up: targeted blink direction and corrected audio answer

James clarified the blink:

> "a little bit too quick and frequency, and just a tap of the shape. its hard to explain"

Interpretation for the next small audition: slow the blink slightly, reduce
repetition, and gently curve the lid margin without replacing June's near-pass
closed-eye artwork. The old short review loop repeats roughly every half-second;
the next preview must distinguish loop frequency from the actual scene clock.

For `june-phase42-porch-bed-removed-v1.wav` (SHA-256
`8ab4281813b6d42d5dba3eb5a8d863ff47725e98f345c3ebd9c545486cbe0bc7`),
James answered **"No real change"**. Removing the continuous bed was not a
successful fix; do not continue claiming it is the confirmed primary cause.

When asked about the voice-only reference, James initially selected static
even in the silent opening, then explicitly corrected it:

> "correction there is not static."

In context this corrects the **voice-only reference** verdict to
**NO_STATIC_HEARD**. It is not acceptance of the original or bed-removed mix,
and it is not evidence of a playback-device problem. Preserve this exact clean
voice contribution and work on the added effects/background.

Voice-only file: `collab/phase42_audio_source_isolation_v1/june-phase42-voice-only-v1.wav`.
SHA-256: `b9a2f402d9255397bf8cafec9170aca6e76c028b5cbd5ede0733d2ebc699f16a`.
