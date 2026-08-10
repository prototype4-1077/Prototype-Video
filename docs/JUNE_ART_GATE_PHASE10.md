# June Oxley Human Art Gate — Phase 10

The first full v5 Blender render passed its technical gate at 453/453 frames,
but failed human art review. A green render is evidence of reproducibility, not
evidence of appealing animation.

## Baseline findings

- A–H/X mouth shapes were present in the rig but effectively invisible behind
  the beard and mustache; the facial matrix read as the same closed line.
- GS050 used the dedicated face-test macro camera and cropped the dialogue mouth
  out of frame.
- GS040's tighter crop left isolated chair pieces at the edge of frame, which
  read as floating props.
- The arm, leg, foot-lock, gaze, jaw, finger, and prop systems rendered without
  a Blender error across the complete 15.1-second slice.

## Phase 10 corrections

- v5 replaces the hidden planar mouth with a forward camera-facing cavity,
  visible teeth, lip arcs, and deliberately separated viseme extremes;
- Golden Scene close-ups now use a performance-specific head-and-shoulders
  camera, while the extreme macro camera remains exclusive to the face matrix;
- rocking-chair geometry is visible for GS030 and hidden for GS040–GS050;
- the quality runner now supports a nine-pose `poses` smoke tier and the original
  453-frame `full` promotion tier.

The smoke tier is not allowed to claim full-frame approval. Its report records
`render_mode`, `contract_frames`, and `rendered_frames` explicitly. The manual
promotion workflow continues to render every frame and encode the deformation
video.

## Approval rule

Phase 10 advances only if the next matrix shows visibly distinct open, narrow,
wide, rounded, and closed mouth families; GS050 includes eyes, nose, mouth, and
beard; and no chair fragment reads as a floating object in GS040. After those
conditions pass, the full 453-frame promotion render must be repeated.

## Promotion result

Phase 10c passed the human and technical gates on 2026-07-28.

- Code revision: `2dd6e49` (`Isolate June facial control art gate`)
- Full promotion revision: `5d0c415`
- GitHub Actions run: `30422026729`
- Regression result: 248 passed
- Blender result: 453/453 frames, 960x540, 30 fps, 15.1 seconds
- Workflow artifact: `8712450088`
- Artifact SHA-256: `679e14f6eabfd039fb0c5f587c2da48489d8fd09d98484cddac8dee9a49f4ea4`

The reviewed full render has readable A-H/X mouth families, an isolated facial
matrix without incidental blinks, restrained brow-knit motion, intact
deformation, stable prop visibility, and valid wide/medium/close framing. The
PR workflow was returned to the nine-pose smoke gate after promotion; full
453-frame rendering remains available as the explicit promotion tier.
