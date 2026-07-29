# June Oxley Performance Control Rig — Phase 9

Phase 9 converts the approved 15.1-second Golden Scene acting contract from
AI-assisted key poses into a true Blender deformation test. It is deliberately
an engineering and animation gate, not a claim that June's final topology or
acting polish is finished.

## What v5 adds

- arm and leg IK targets with elbow and knee pole controls;
- locked foot targets for planted-contact acting;
- clavicle controls for shoulder arcs and silhouette clarity;
- jaw, independent eye bones, and a shared gaze target;
- ten articulated digit controls;
- held mug, table mug, ledger, and pencil props with shot-keyed visibility;
- the reusable `June_Golden_Performance_v1` action;
- an exact compiler from GS030–GS050 to 453 Blender frames at 30 fps.

The rig remains generated from repository-native Python and Blender. It uses no
paid API or service. Generated `.blend`, frame sequences, matrices, and videos
remain workflow artifacts rather than Git binaries.

## Locked timing

| Shot | Start | Mid | End | Frames |
| --- | ---: | ---: | ---: | ---: |
| GS030 | 1 | 93 | 171 | 171 |
| GS040 | 172 | 260 | 339 | 168 |
| GS050 | 340 | 398 | 453 | 114 |

The performance manifest and canonical turnaround are both SHA-256 pinned. A
build fails if either reference changes, if a shot budget changes, if any of the
nine pose frames moves, or if the full render does not cover all 453 frames.

## Continuous gate

The zero-cost GitHub Actions path builds the v5 asset library, reopens the saved
artifact, renders all 453 performance frames in Blender Workbench, encodes a
silent deformation review video, and builds a labeled nine-pose matrix. The
same job still produces face and joint-deformation matrices for regression
review.

## Honest boundary

The generated hero currently proves control structure, exact timing, reusable
actions, contact props, and continuous skeletal deformation. It does not yet
prove final skin weighting, cloth secondary motion, shot-specific hand contact,
or feature-film facial topology. Those must be judged from the rendered CI
artifact and iterated before promotion to Eevee look development and a final
Cycles beauty render.

## Next promotion gate

After the Workbench deformation slice passes visual review, the next step is a
shot-specific contact and polish pass: sculpted elbow/knee correctives, mug and
pencil hand-contact offsets, facial timing driven from the real dialogue audio,
and one Eevee hero-lighting render for GS040. Workbench remains the fast
regression tier; only selected frames advance to Eevee and Cycles.
