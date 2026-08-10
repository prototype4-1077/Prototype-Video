# GPT notes: Candidate-06 intermediate architecture milestone

Candidate-06 is preserved for exact-frame comparison, not offered for encode approval.

Evidence: `collab/phase34_candidate_06/`

- Local manifest SHA-256: `fe3d5f4255a269d699d737ca6f22316b449b42249b184165852d6e757c528223`
- LF-normalized Git/public manifest SHA-256: `1051a967411c4f363cea4fe24d5ef4cc61f6fc20d0acbcc2bb5483aa7ea66022`
- Lossless RGB archive SHA-256: `478fd2fc301c70295ea8a7de44163e7980d5e9030ee9fdd7e8588d7029155ced`
- Contract canonical SHA-256: `894f453758ad3b685487140702d90846068b8907803d90fc7e96c5a11d850b1d`
- Renderer SHA-256: `a2a0783f207b9132e4691520690088d2e283dddbecb15f2d4afaf72c64030bff`

What improved versus candidate-05:

- X-to-A and H-to-X use symmetric non-neutral semantic coverage instead of a hard oral cutoff.
- Upper teeth use one fixed E-derived dental arc at a fixed 88x16 skull anchor.
- Non-dental oral anatomy blends linearly, removing the cited transition topology jumps.
- C/E mean separation increased from 4.384 to 14.332.
- The forbidden mask is applied before dental extraction; the metric is zero.
- Final-owner depth precedence replaces the permissive all-pairs overlap allowlist.
- Source-textured cavity feathering reduces the black cutout edge.

All machine gates pass; 17 focused tests pass; all 96 archived hashes round-trip. The
public Candidate-05 GitHub run `31347312542` is fully green, including regressions and Blender.

Why this is not the review candidate:

- F contact is nearly neutral at frames 58/59/62/64.
- H tongue is a generic pink strip.
- F-to-G frame 65-66 still opens too quickly.
- Maroon cavity patches remain.
- Two independent code audits found that low-opacity writes are composited but omitted from
  depth coverage. Candidate-07 will record actual alpha-write support/final writers and add
  dedicated F/H semantic layers.

Please use candidate-06 only as a before/after reference when candidate-07 is published.
