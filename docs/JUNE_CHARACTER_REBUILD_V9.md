# June character rebuild v9 — development review

This is an opt-in, turnable 3D asset on top of the 24-second world movement
audition. It is **not the approved June likeness, a finished episode, or a
production-ready speaking character**. The accepted GS070 painting and canonical
turnaround remain the art targets. This branch does not change either image,
the default v8 render path, June's voice, or any approval decision.

## Implemented

- Connected anatomical head, ears, lips and neck, fitted to June's proportions.
  Enlarged eye regions and a measured socket fit replace the exposed proxy eyes.
- Surface-sampled scalp, beard and moustache grooms. Follicles live on the actual
  head geometry; this is not a painted face attached to a moving card.
- Connected anatomical hands fitted to the named finger controls. The inherited
  lateral wrist/digit offset is corrected in this v9 rig only.
- A single connected coat surface with the existing arm weights transferred into
  it. Independent geometry inspection found one component, with 161,610 faces.
- Transported cross-section frames for limbs, avoiding the old reference-axis
  discontinuity at elbows/knees; more joint rings, fitted cuffs, full-size soles,
  laces, collars, pockets and seam geometry.
- Camera-directed gaze during the address portion of the world audition.
- An offline, pinned anatomical source and corruption detection before loading.
  The source assets are CC0; no external generation service or paid dependency is
  used by the builder.

The anatomical foundation is derived from MakeHuman/MPFB's base mesh and old-male
target at commit `437dd513888a92399d1d3200d2e80859fae55abc`. Only the needed mesh
subsets and hand landmarks are retained. Source URLs, source hashes, derivation,
and the derived archive hash are in
`concept/characters/assets/june_anatomy_cc0_provenance.json`.
[The source project's asset license](https://static.makehumancommunity.org/mpfb/faq/build_other_chargen.html)
permits reuse of its core mesh and targets under CC0.

## Validation and its limits

35 focused tests pass: 14 movement/evidence tests, three source/evidence integrity
tests, and 18 tests covering the repaired historical Phase35 fixture boundary.
Both hands fit their rest landmarks within 0.000000011 scene units. This tests
the fit, not the artistic quality of the hands or the grip.

The 720-frame Blender control audition passes all seven existing checks: foot
targets, wrist targets, planted-ankle displacement, sole penetration, planted-sole
height, boot/table clearance, and mug attachment continuity. Detailed skin, hair
and cloth display meshes are suspended only during these control measurements;
all display states are restored before saving and rendering the full asset.
The audit now emits progress every 60 frames. The measured run reached frame 720
in approximately 39 seconds, including asset construction.

The report does **not** certify finger/handle contact, chair/hand contact, cloth
collisions, a natural gait, facial likeness, or normal-speed acting. These remain
human review items. Passing numerical controls must never promote this asset.

## Visual review disposition

The new foundation improves connectivity and removes several primitive-construction
defects. It is still below the requested top-tier cartoon standard. Remaining
visible issues include a generic neutral face, insufficiently characteristic
smile/brow shapes, a beard and hairline that need an authored silhouette, broad
clothing forms that still feel like a prototype, and incomplete hand/prop contact.
The movement audition also retains the old proxy porch, whose floating wall and
chair parts are unsuitable for a finished film.

The candidate contains neutral mouth plumbing only. `ce_dialogue_ready` is false.
Fitted speech shapes, jaw/cheek motion, blinking and grooming deformation must be
implemented and reviewed together before attaching June's approved Spuds voice.
The source mesh's anatomy is a foundation for sculpting June, not proof that the
canonical character has already been reproduced.

Next: finish the likeness and garment sculpt against the two approved images,
review the sculpt unlit and under neutral light from every side, then complete
the facial rig and real hand/prop contact. Rebuild the porch after the character
passes that art review. Contemporary-issues scripts should retain the dated-source
brief and existing character boundary described in `JUNE_WORLD_MOVEMENT_PROOF.md`.

## Reproduce

```bash
python3 -m unittest pipeline.tests.test_june_anatomy_asset \
  pipeline.tests.test_june_world_motion \
  pipeline.tests.test_cartoon_source_textured_vui_probe_v2 -v

blender -b -t 4 --python-exit-code 1 \
  --python pipeline/blender/render_june_hero_review.py -- \
  --output-dir /tmp/june-v9-new-review --width 960 --samples 48 \
  --views front,three_quarter,profile,back,full,hand

blender -b -t 4 --python-exit-code 1 \
  --python pipeline/blender/render_june_world.py -- \
  --asset v9 --output-dir /tmp/june-v9-new-movement \
  --width 768 --samples 24 --frames 1,173,510,555
```

Blender 4.2.0 was used for the measured evidence. Review directories must be fresh.
The existing `--asset v8` behavior remains the default. No finished episode,
new narration, alternate score, or automatic approval is generated by this path.

## Historical CI repair

The preceding branch's run `34222418099` failed in the Phase35 VUI fixture loader.
Six text artifacts had LF line endings while their existing locks describe CRLF
bytes. Restoring CRLF reproduced every already-recorded SHA-256 exactly. The JSON
values and log text are unchanged, and the expected hashes and authorization
contracts are unchanged. Narrow `.gitattributes` entries preserve these bytes.
No historical render or probe was retried or promoted.

The complete local suite could not pass in this runtime: OpenCV is absent and an
unrelated observability test also failed. The focused tests and actual Blender
evidence above are the completed local verification; they are not a claim that
every repository-wide CI job has passed.
