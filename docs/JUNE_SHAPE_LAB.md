# June Shape Lab

The June Shape Lab is the first repository-native optimization seam for the
cartoon renderer. It does not claim that parameter sampling is reinforcement
learning, and it does not need Blender, a network connection, or a paid API.

Its v1 contract defines eighteen bounded, artist-meaningful parameters for
June's unified Hero v3 head, face, eyes, mouth, beard, and lean torso. Candidate
zero preserves the authored defaults; later candidates are sampled on explicit
value grids by Python's seeded standard-library generator.

Generate an append-only batch from the repository root:

```text
python -m pipeline.cartoon_shape_lab concept/characters/june_oxley_shape_search_v1.json --output-dir build/june-shape-lab --seed 20260728 --count 8
```

Each candidate is stored at
`build/june-shape-lab/<candidate-id>/candidate.json`. The identifier hashes the
complete payload, including search-space version and sampling provenance. An
exact replay is accepted; an attempt to replace different content at the same
path fails. No timestamp is stored, so identical commands are byte-reproducible.

The module also provides direction-aware `dominates` and `pareto_frontier`
functions. The v1 objective vector protects identity, silhouette, and expression
readability while minimizing render time. It intentionally does not combine
those measurements into one weighted score.

The next integration slice should apply a candidate's parameters to the Blender
builder, render locked low-resolution review views and masks, and write measured
scores beside—not into—the immutable proposal. Promotion must remain a separate
operation with held-out views and the existing human art gate.
