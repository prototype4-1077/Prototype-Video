# The Twelve-Dollar Mug — repaired full-cut review

Watch `twelve-dollar-mug.mp4` at normal speed with sound. This is the
complete 38-second narrative review, not a production release. The
temporary voice and earlier shot performances still need judgment.

The four-part picture map retains the early setup and the coffee
sentence, incorporates all 303 repaired frames, and omits only 24 frames
of the old silent outro hold. The two passing same-view joins are
at 26.30 and 28.80 seconds; the cut to June's face is at 30.40 seconds
after the pot settles. The output stays on the original story clock
through the final line. Turn on English captions in your player or use
`captions.srt`; all 18 authored cues are retained.

`mix.wav` is the exact PCM24 stereo master track. It uses continuous
old dry narration at matched level with a fixed −1 dB trim through the
pour, the recorded pour once underneath it, then the unchanged approved
closing mix. No old synthesized bed, chimes, or rejected effects enter.
Keep the attribution file with this package.

The local builder requires the exact pinned Phase25 review master as
its legacy **picture** input. It does not require the Phase26 mixed
audio, new art generation, API keys or any paid service:

    python -m pipeline.cartoon_full_short --legacy-master PATH_TO_PHASE25_MASTER --output NEW_DIRECTORY

See the scene recipe for exact inputs and spans. The verified local MOV
is intentionally not duplicated in Git; its picture packets equal the
posted MP4 and its decoded PCM equals the posted WAV. A complete
source-only rebuild of the legacy picture prerequisite in the current
runtime remains separate from this reproducible assembly.

Verification passed: 1140 frames at 1080p30 with exact 48-kHz audio clock,
303 identical repaired decoded frames, 364800 exact approved closing
stereo sample pairs, 43.11 dB AAC SNR, −1.4 dBTP. See the decoded cut
sheet and `verification.json`. These are technical results, not proof of
natural acting, perceptually clean playback, or a human full-cut pass.
