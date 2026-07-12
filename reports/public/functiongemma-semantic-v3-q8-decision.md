# FunctionGemma Semantic-v3 Q8 Decision

## Decision

The semantic-v3 full-SFT Q8 challenger is **not promoted**. The production champion remains the hash-pinned scale-789 Q8 artifact.

## Evidence

| Set | BF16 schema | Q8 schema | BF16 intent | Q8 intent | Q8 p95 |
|---|---:|---:|---:|---:|---:|
| Calibration (1,124) | 100.00% | 100.00% | 97.51% | 96.98% | 881 ms |
| Historical (201) | 99.50% | 99.50% | 96.52% | 96.52% | 870 ms |

Q8 lost six calibration intent decisions relative to BF16, a `0.534` percentage-point regression. The frozen non-inferiority margin was `0.5` points. Historical schema validity was `99.50%`, below the frozen `99.9%` gate. No threshold was changed after observing these results.

The Q8 artifact is `291,557,568` bytes with SHA-256 `73754f537c3ea79bb3e1226a03845476c795aaa26339a8cb2a24ddb14d579275`, converted with pinned llama.cpp commit `074944998d3f25e7001ede30d152b59dff741c8c`.

The complete immutable evidence and lineage are recorded in `configs/functiongemma-semantic-v3-q8-manifest.json`.
