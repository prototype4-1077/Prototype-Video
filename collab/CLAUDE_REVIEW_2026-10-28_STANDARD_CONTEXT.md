---

## Claude visual review — 2026-10-28

**Files actually inspected (pixel-level):**
- `collab/phase34_candidate_09/june-phase34-source-textured-visemes-mouth-poses-v2.png` — 3×3 grid of close-up mouth crops, rendered at source texture scale.
- `outputs/edit/phase42-hand-refinement-v1/late-hand-native-keyframes-v1.png` — 2-column (existing left / candidate right), 6 paired hand crops at native resolution.
- `collab/phase42_integrated_scene_review_v1/decoded-scene-contact-sheet-v1.png` — 12-panel full-scene contact sheet.
- `concept/characters/june_oxley_phase34_source_textured_visemes_v2.json`, `concept/style_frames/june_phase33_direct_address_rhubarb_v1.json`, `collab/HAND_REFINEMENT_FINDINGS_2026-10-28.md` — read for geometry/mapping evidence.

No video, WebP, or audio was played. Motion continuity and lip-sync cannot be assessed from stills.

---

**Strongest visible concern — mouth:**
The pose sheet shows 9 visually distinct mouth shapes. Critically, the internal letter assignments do not match Rhubarb's published semantics. Confirmed by the JSON: internal **A** is a slightly-open shape (opening: 22 px), while Rhubarb A means bilabial-closed (P/B/M). Internal **G** is strongly rounded-open (round: 0.78, opening: 38 px), while Rhubarb G means labiodental (F/V). The actual labiodental contact is encoded in internal **F** (upper\_teeth: 1.0, lower\_roll: 0.42). The pipeline forwarding raw Rhubarb labels straight to internal poses is therefore mapping every bilabial stop to a slightly-open shape and every labiodental fricative to a rounded-open shape. **The mismatch hypothesis is fully supported by the drawings.** This is a genuine semantic routing error, not an artwork defect; a label-remapping correction in `performance_viseme_plan` is the cheapest useful experiment.

**Hand candidate:**
The paired keyframes show the candidate as a cohesive planted rock versus the existing spread. No visible tearing, hole, or contact pop in the 6 sampled stills. The geometry report's containment numbers (0 changed pixels outside declared support, strain 0.000012%) are tight. The candidate concept directly addresses the plausible geometry cause of "rubbery." **Merits a short integrated A/B at real cadence** before any broader revision.

**Cannot be judged from stills:**
Real-time smoothness of the hand entry blend; whether the 0.65° rock reads as pressure or still feels mechanical at speed; whether the label remap produces perceptibly better sync; audio correlation; beard/moustache continuity across viseme transitions. Scene acceptance cannot be granted from stills.
