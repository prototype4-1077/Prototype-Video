# Phase42 — sparse-effects audio audition v2

James corrected the voice-only verdict to **no static**. That exact voice PCM
is retained here. The earlier balanced-air mix and porch-bed-removed experiment
remain unaccepted; removing the bed alone made no real change.

Listen to `june-phase42-sparse-foley-v2.wav`. It replaces the noise-based pour,
mug scraping, cloth, breath, and continuous leaves/cicadas with a restrained
selection of damped water/contact tones and chimes. There is no continuous
noise bed. The quieter soundstage is an artistic audition, not a final claim
of realistic Foley or a complete scene mix.

`june-phase42-sparse-effects-only-v2.wav` contains only the added effects for
further diagnosis if required; it is not a replacement for the complete mix.

## Verified

- Mixed PCM minus effects PCM equals the reviewed clean voice PCM exactly.
- Voice source, word timing, amplitude contribution, 48-kHz stereo PCM24 format,
  and 484,800-sample / 10.1-second clock are unchanged.
- No whole-mix denoising, voice regeneration, per-file normalization, paid
  service, download, or video encode occurred.
- Peak is -1.371 dBFS; source readback is exact and edit-boundary steps are
  tested. All files and implementation are hash-bound in the report.

This mix still needs James's listening verdict. Passing waveform tests does
not establish that the new effects sound natural or that static is absent.
The full-render and production-promotion gates remain closed.
