# June Oxley Unified Hero — Phase 5

Phase 5 replaces the most visibly assembled parts of Hero v2 while preserving the proven rig, shot compiler, and render contract.

## Material changes

- `June_Head` is now a single 96×64 sculpted surface. Nose, bridge, cheeks, eye sockets, jaw, and chin are vertex fields on that mesh; the v2 cheek, nose, and chin proxy volumes are removed.
- The plaid body is one tapered loft rather than an ellipsoid, and the denim jacket is one fitted open shell rather than two side spheres.
- White hair is one fitted horseshoe shell with an open bald crown and sparse wisps. The beard is one subdivision-ready jaw patch rather than a white ellipsoid.
- The established A–H/X mouth remains independently animated, enlarged slightly for close-up readability, and retains its radial lip rim.
- v1 and v2 builders remain selectable by manifest major version so earlier proofs stay reproducible.

## Facial-performance gate

The standard episode contact sheets only inspect shot midpoints and can miss weak phoneme poses. The asset gate now reopens the generated `.blend` and renders a separate 4×4 close-up matrix containing:

- all nine A–H/X visemes;
- smile, thoughtful, soft chuckle, brow raise, brow knit, squint, and cheek raise;
- an adjacent JSON mapping from every tile to its exact frame and active control.

The matrix uses Blender Eevee at 960×960 per source frame. Landscape and portrait composition sheets continue to use full-resolution Cycles frames.

## Honest boundary

This is a materially more coherent code-native sculpture, not a substitute for artist-authored retopology, skin weighting, grooming, texture painting, or final facial animation. Passing automated checks proves reproducibility and control coverage. Human comparison to the turnaround remains the release gate.
