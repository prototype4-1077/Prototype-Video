# June Phase 40 synchronized acting checkpoint

Date: 2026-08-13

Branch: `agent/phase40-synchronized-acting-integration-v1`

Parent checkpoint: Phase39 commit `1e12c05a9eaf77fc5a7d8a4da2584a9eeac1d979`

## Outcome

Phase40 integrates the Phase39 torso, viewer-left arm, and table-hand performance with the exact accepted Phase35 face, head, secondary-atmosphere, and camera clock. The candidate is measured against all 228 exact baseline frames. It remains an unencoded local A/B: it does not mutate the accepted archive, rebuild a master, promote output, or claim human acting acceptance.

The integration removes the old rectangular shoulder warp only while Phase39 has a nonzero additive state. A fused inverse map derives body motion from the locked GS070 plate and the existing camera geometry without first resampling the moving body into an intermediate image. The candidate then restores the accepted final head, face-feature, mug, atmosphere, and camera pixels by construction. When Phase39 returns to zero at F148, the compositor returns byte-for-byte to the exact baseline and stays there through F228.

## Synchronized performance

- F018-F034: small notice/inhalation and settle while the face enters the first line;
- F045-F082: hand opening and body counter-motion during the account/debt thought;
- F091-F126: compact palm compression with one overshoot during the contrast/question turn;
- F127-F147: physical return before the late facial compassion and question finish;
- F148-F228: exact accepted baseline, including the original head-reaction tail and final hold.

Visual review of the 228-frame evidence shows no collar tear, head seam, mug drift, atmosphere discontinuity, or hand/table separation. Native hand evidence keeps all nail beds, finger silhouettes, cuff contact, and table contact readable. The F147/F148/F149 neighbor triplet returns cleanly to the original compositor.

## Machine result

- focused tests: 8/8 passed;
- full synchronized gates: 15/15 passed;
- exact baseline/candidate frames measured: 228/228;
- intentionally changed frames: 129;
- changed pixels outside prospective replacement/body support: 0;
- changed pixels in transformed head support: 0;
- changed pixels in transformed face-feature support: 0;
- changed pixels in transformed mug support: 0;
- maximum adjacent delivery landmark step: 1.627 px at F021 (`torso.left_chest`);
- maximum whole-frame mean RGB delta: 2.090 at F024;
- F148 baseline/candidate mean RGB delta: 0;
- exact baseline tail frames F148-F228: 81/81;
- Phase39 moving source resamples: 1;
- encoder processes: 0;
- network calls: 0;
- paid-service calls: 0.

Detached reproduction:

- synthetic commit: `21bc76d60851e538251561aea56c89bd8b004d50`;
- source tree: `aa639e675266d0112edc5dbc0d7dc2fb0b8f780f`;
- focused tests: 8/8 passed;
- full synchronized gates: 15/15 passed;
- reproduced inventory: 6/6 files;
- all six reproduced filenames, byte counts, and SHA-256 hashes match the primary package exactly.

## Source bindings

- contract SHA-256: `28751a51b0f4f77b80338f9cb207ad6fdca2bdd49a9c994bb52841b5da4f194d`;
- implementation SHA-256: `1ed3ad4f47e09c7b67835506c60352a05433e1dfd36ac98dae3455c9444208cf`;
- tests SHA-256: `89756c3cb2549e222023a9102d7526e6ebbe8ee7d412307f9d010a8b8d923a25`;
- Phase39 report SHA-256: `22e5875b5e11c72de5b1f5ca1fb3a706e13158d0f7af1f7498b62010f380fe3d`;
- locked Phase35 implementation SHA-256: `72aaff4bc71331821e1aa0938f570a39da9bc0b4c3aaa58232b44452e4b8f249`.

## Final evidence

- machine report: `360427112da5fc79fb173c18d1e6cf9fcaea38173614fcfb511d55a660921256`;
- synchronized keyframes: `4f922c4529c29c52c492fc0b6290807a1386b44215d2d2629db77aa89a00377b`;
- native hand sheet: `f38b130569b090c669393be6aebcea8b7eb3d96489a457f9a8aa02d91aa6c991`;
- temporal neighbors: `3870a3bd2af8cb12e10d4e78503ea83299517a1187517dc8c2129a438510367f`;
- transformed supports: `5aa9bd01db4cabc20fa5bec64a88ca045b6a94d7fedaaad75a15e54a1b3d5953`;
- motion timeline: `682b7e4506c29686df55ac48398a8c2005d8bad7073bb270175ba40d6825a906`.

## Remaining gate

The detached staged-tree reproduction is exact, so Phase40 is ready to freeze locally and hand to Claude for independent evidence review. Human temporal acting acceptance, Candidate03 audio acceptance, and Phase37 V4 eyelid acceptance still gate any corrected master rebuild or encode.
