# CLAUDE REVIEW 2026-09-13 - June studio v1-v6 architecture review

Reviewed from public reads (PRs #11-#18, docs/JUNE_REUSABLE_STUDIO.md, JUNE_STUDIO_ART_V6.md,
pipeline/june_studio*.py, workflow june-studio-voice-benchmark.yml). James has read this.

## Architecture: APPROVED, and it is the right call
Retiring the Phase 34-36 2D cage/atlas approach for a packed Blender studio is correct.
What this buys, explicitly: character-independent body actions (WHO/WHAT split), a solver
for lip-sync instead of hand-built cages (Rhubarb), a frame cache keyed on inputs, and
provenance receipts. This is a library that compounds. Good work.

## Three blockers, none technical

### 1. The studio went blind (highest priority)
There are 218 images in this repo and ZERO committed review renders for studio v2-v6.
Likeness verdicts are prose only ("facial softness, cheek/beard volume... remain below the
approved artwork"). No second party can see what that means. The Phase 34-36 breakthrough
happened BECAUSE proof frames were committed and could be viewed.
RULE RESTORED: an art candidate without committed renders is not reviewable, and not
eligible for approval. Prose is not evidence.

### 2. The likeness loop has no exit condition
v2->v3->v4->v5->v6 are each "an unapproved art candidate" chasing an approved turnaround
that exists only as a felt target. There is no defined pass condition, so there is no v7
that can end it.
EXIT TEST (smallest decisive experiment): render v6 at the EXACT camera/framing of the
approved 2D turnaround and the approved golden-scene art. Commit a side-by-side sheet:
approved reference left, v6 render right, same scale, same crop, front / 3-4 / profile,
plus one expression row. James rules once: approve, or he names three specific deltas.
No v7 without those named deltas.

### 3. Nothing merges and nothing ships
Eight stacked open PRs; pipeline/june_studio.py 404s on main; the studio's only artifact in
a month is a 68 KB voice take. CI runs only the 8-minute voice job - no Blender render runs
in CI, so every frame depends on James's local machine.
RECOMMENDATION: ship a 30-second episode with v6 AS-IS. "The Night Clyde Left the Vehicle"
is already written (build/june-oxley-left-the-vehicle, 24 scenes, Spuds take). Audience
judges Clyde's story, not cheek volume. Shipping also proves the pipeline end to end, which
six likeness passes have not.

## Enhancements worth building next (in leverage order)
1. EMOTION-DRIVEN FACE. ElevenLabs audio_tags already encode feeling ([laughs], [tender],
   [whispers]). Map tags -> the 15 facial assets so the face acts the emotion while Rhubarb
   handles phonemes. Cheap, and it is the line between a talking model and a performance.
2. SHOT GRAMMAR from James's message-mode doctrine (descriptive / abstract / story /
   metaphor). In 3D this becomes camera language: static clean, slow push, handheld medium.
   Nearly free in this architecture; it is a house style that cannot be copied.
3. EARL. The 8 body actions are character-independent by design - a second character proves
   the compiler and unlocks dialogue, where June's humor actually lives.
4. EEVEE FOR DAILIES, Cycles for finals. Review in seconds; the frame cache makes it safe.
5. ONE-COMMAND EPISODE: text -> voice -> Rhubarb -> actions -> render -> contact sheet.
   That is prompt-to-cartoon, and this architecture finally puts it in reach.

I am back on hourly review rotation and can view any frames you commit. - Claude
