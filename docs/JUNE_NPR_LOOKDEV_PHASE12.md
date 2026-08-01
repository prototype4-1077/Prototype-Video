# June Oxley Semantic-Ink Promotion - Phase 12

Phase 12 advances the approved June Oxley performance from the Phase 11
storybook render to a more deliberately drawn cartoon image. It adds semantic
line hierarchy, a quieter final hold, an original authored foley bed, a
streaming delivery audit, and a full-scene open-source restoration finish while
preserving the exact 453-frame acting clock.

The repository is public at
https://github.com/prototype4-1077/Prototype-Video so GitHub's free public
Actions capacity can execute the reproducible render. `main` remains untouched;
the work is isolated on `agent/june-hero-unified-sculpt-phase-5` in draft PR 8.

## Full semantic-ink promotion

- Promotion revision: `c7932efcf2f3fd50699d5727dbc3f188e13aca31`
- GitHub Actions run: `30454667937` (run 66)
- Regression, six deterministic Blender chunks, and exact assembly: passed
- Artifact ID: `8729079236`
- Artifact name: `june-golden-performance-storybook-semantic-npr-v1`
- Artifact ZIP SHA-256:
  `b04c362f8443fc07d276f79a32e13fcbea45b36fa3c95dac27f3cfbc52fa0978`
- Assembled source SHA-256:
  `bea96dabf0dc2c6d591eb80639c9e951a996360506c6b65f076f1bc657263728`
- Assembly-report SHA-256:
  `8afd3c5a13442847342dab8649986b77db1f61ad3fd023c417c1c31019c0e980`
- Immutable look-profile SHA-256:
  `5809cb19c668b1ddea2ad2c73061e47cd10ff0a32af3fea1834cf1da8a32c26d`
- Source contract: 960x540 H.264/yuv420p, 30 fps, exactly 453 frames,
  15.1 seconds, full decode passed
- Assembly contract: six gap-free ranges: 1-76, 77-152, 153-228, 229-304,
  305-380, and 381-453

The assembly job initially could not start because GitHub treated the private
repository as billable capacity. Making the repository public removed that
constraint; rerunning only the failed job completed assembly without repeating
the six Blender renders.

## Visual disposition

The full source audit reviewed frames 1, 93, 171, 172, 260, 339, 340, 398,
and 453 across the authored wide, medium, and close compositions. It passed for
stable June identity, readable performance, coherent shot changes, selective
line hierarchy, prop continuity, and a visibly stable final held pose.

The final hold spans frames 430-453:

- upper-face first/last SSIM: `0.969631`
- upper-face mean adjacent luma difference: `0.168835`
- upper-face maximum adjacent luma difference: `0.306906`
- left-wall mean adjacent luma difference: `0.000272`
- left-wall maximum adjacent luma difference: `0.003210`

Against the Phase 11 audit smoke, Phase 12 reduced mean upper-face drift by
about 83.7 percent and mean left-wall drift by about 98.5 percent. The source
nine-pose matrix SHA-256 is
`f4144650776d6555f0be94af1410cd0bd8de3f301bc985efd645f9947c3d6f06`;
the final-hold strip SHA-256 is
`e009ae8d4a6111ba8b1da561769c9c5a13db38de7664f7dc56186e6ad5140e0e`.

## Semantic-ink experiment

The broad v1.4.0 compositor was rejected because it drew too much internal form
and background structure. The immutable v1.4.1 profile passed the GS050
temporal gate by applying ink semantically and suppressing non-story detail.

- Identity similarity against Phase 11: luminance SSIM `0.951780`
- Full-frame adjacent luma difference: `1.222086`, 18.8 percent below Phase 11
- Face/torso adjacent luma difference: `2.017817`, 18.5 percent below Phase 11
- Right-wall adjacent luma difference: `0.017234`, 32.8 percent below Phase 11
- Upper-left-wall adjacent luma difference: `0.007384`, 54.1 percent below
  Phase 11
- Human review: no silhouette halos, identity drift, or visible temporal crawl

The result demonstrates an important production rule: more detected edges do
not create a better cartoon. Lines should describe silhouette, expression,
contact, and story emphasis; shade masses and color design should carry the
rest.

## Original sound design

`pipeline/cartoon_sound_design.py` synthesizes all non-dialogue audio locally
and deterministically from the versioned sound profile. No external samples,
paid services, or APIs are used. The restrained stem contains room tone, chair
weight shift, boot settle, ledger pickup, pencil contact, and a compassion
breath.

- Foley stem: 48 kHz stereo, exactly 724,800 samples / 15.1 seconds
- Foley peak: `-29.494 dBFS`
- Foley SHA-256:
  `ee73375726065246e78c6124d94e63b2658c9c2f43964474b18f29172be0988d`
- Dialogue-plus-foley master: 24-bit PCM, 48 kHz stereo, 15.1 seconds
- Mix SHA-256:
  `f0ecc51233af5e3fcc0b02b89f9c2368195f66df67b09a3b1b28a7e2e2d90487`
- Mix loudness: `-16.4 LUFS` integrated, `6.6 LU` LRA, `-2.9 dBTP`

The foley is intentionally perceptual rather than demonstrative: it supports
body weight, object contact, and room presence without competing with June's
line delivery.

## Free/local AI finishing policy

Real-ESRGAN AnimeVideo-v3 is used only as a restoration and 2x upscale stage.
It cannot invent acting, retime a frame, alter the scene, or approve its own
output. A 30-frame audition passed at 1920x1080 with luminance SSIM `0.993323`
against a conventional Lanczos 2x reference and no observed shape
hallucination. The complete output must still pass an exact frame/audio/decode
contract, a nine-pose review, and a final-hold temporal review.

This is the appropriate role for generative-adjacent tools in this pipeline:
bounded craft assistance under deterministic contracts, not uncontrolled video
generation.

## Finished delivery

The full 453-frame Real-ESRGAN pass completed locally on the available Intel UHD
GPU, then passed independent streaming audit and human review.

- Delivery: 1920x1080 H.264/yuv420p, 30 fps, exactly 453 frames / 15.1 seconds
- Audio: AAC stereo at 48 kHz from the approved dialogue-plus-foley mix
- Captions: approved SRT burned into the picture
- Delivery SHA-256:
  `3050dec00d8c0b40cde8516dcf28e0d3d7aa82c8b13862b18576c5170e5d3165`
- Finish-report SHA-256:
  `9c4a4c32119ff50026688b6f58b2756fa2775b075cf07e902b1273ea4d4da82d`
- Independent-audit SHA-256:
  `84cb244e892c6acaf4ea93b8fd13b6b713bf452e8da7de9a576d4e91256501e5`
- Full FFmpeg decode: passed, 453 decoded frames
- Final nine-pose matrix SHA-256:
  `7c82727ac435deaf9799e3b28c8beab340f75e91dbbf62bff4c13980b7c8cd74`
- Final-hold strip SHA-256:
  `991b06d66605d129c2147c4432e1d1bac65b1d485644388852ca2d81fb722178`
- Human disposition: passed for identity, expression, shot continuity,
  semantic ink, caption legibility, and absence of visible AI redraw crawl

The finish is not numerically as static as its 960x540 source. In the final
hold, upper-face mean adjacent drift rose from `0.168835` to `0.233295`, while
left-wall drift rose from `0.000272` to `0.017598`. Both remain below one luma
level and no crawl was visible in the seven-sample strip. This tradeoff is
accepted because the full result visibly cleans grain and sharpens eyes, beard
planes, silhouettes, and semantic ink without changing June's construction.

## Reinforcement-learning loop

The existing deterministic linear-UCB contextual bandit can rank future look
experiments by shot scale, motion, emotion, and background complexity. Phase 12
adds better reward evidence: identity SSIM, face and wall temporal drift,
full-scene hold stability, render cost, and human pairwise choice. Hard quality
floors remain outside the learner, and promoted profiles stay immutable.

This creates a useful zero-cash feedback cycle: propose a bounded look variant,
render the smallest discriminating slice, measure it, collect a human choice,
update the learner, and promote only after a full-scene audit.

## CI policy

Full-scene promotion remains explicit because it is expensive. Commit
`c847e4957f91c73b48d0dfe06bbe90c8d4ab38b7` restored routine pull-request CI
to the economical 30-frame semantic-NPR temporal gate. Full 453-frame renders
run only when a performance or immutable look profile is deliberately promoted.
Public Actions run `30468874323` passed both regression and that restored
temporal gate on commit `6fabfc9333d21023e4a7b02852cf87749393d1ff`.

## Next production phase

The highest-value next phase is not another resolution increase. It is a
deformation-and-continuity pilot built around one longer scene:

1. rebuild eyelid, cheek, mouth-corner, beard, wrist, finger, and cloth topology
   for close-up acting and clean silhouettes;
2. add hand-shape libraries, eye darts, breathing, overlap, anticipation,
   overshoot, settle, and shot-specific line accents;
3. prove June, props, lighting, and semantic ink across more locations and
   camera angles in a 30-60 second multi-shot pilot;
4. collect blinded pairwise reviewer choices and feed them into the bounded
   look learner;
5. keep AI tools at reversible stages: concept variants, texture cleanup,
   restoration, diagnostics, and reviewer assistance.

That phase attacks the remaining studio-quality gap—expressive deformation and
continuity—while preserving the production system now proven here.
