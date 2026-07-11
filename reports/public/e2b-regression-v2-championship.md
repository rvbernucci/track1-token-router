# E2B Regression V2 Championship

## Decision

Gemma E2B V2 remains disabled. The frozen candidate preserved baseline accuracy and released three verified local answers, but the sample was too small to satisfy the confidence and token-savings gates. The release runtime remains proof-carrying deterministic solvers followed by Fireworks.

## Final Aggregate Results

| Variant | Accuracy | Local coverage | Local precision | Wilson lower 95% | Fireworks tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fireworks only | 65.00% | 0.00% | n/a | n/a | 249,646 |
| Deterministic + Fireworks | 65.00% | 0.00% | n/a | n/a | 249,646 |
| E2B proof-gated probe | 65.00% | 0.75% | 100.00% | 43.85% | 248,951 |
| Full V2 | 65.00% | 0.75% | 100.00% | 43.85% | 248,951 |

The paired lineage bootstrap placed the lower 95% bound for token savings at zero. The policy therefore failed both the required 90% Wilson lower precision bound and the positive token-savings lower bound. Thresholds and coefficients were not changed after opening the final holdout.

## Runtime Evidence

- Image platform: `linux/amd64`.
- Public image: `ghcr.io/rvbernucci/track1-token-router:v2.0.1-e2b-v2`.
- Public digest: `sha256:c9b66097e6a9aa2aa061a35d328ba529fbf732d71dea01751e53be9dfab27553`.
- Compressed image size: `50,481,245` bytes.
- Uncompressed image size: `124,593,854` bytes.
- Runtime limits: 4 GiB, 2 vCPU and network disabled.
- Observed runtime: 1 second.
- Process peak RSS: 28.758 MiB.
- Official output contract: 2/2 ordered rows, exit code zero.
- Image scan: no sealed evaluation directory, final task identifier or credential pattern.
- Test suite: 594 tests passed after adding explicit 429/503/malformed-response chaos coverage; one environment-dependent test was skipped.
- Release run `29143012652` and anonymous public-image audit run `29143144891` both passed.

## Safety Contract

Invalid FunctionGemma output routes directly to Fireworks and is never imputed. Probability and game-theory utility cannot bypass Answer Contract or a failed registered verifier. Only models present in runtime `ALLOWED_MODELS` may be called, and all remote inference uses `FIREWORKS_BASE_URL`.

No final-holdout prompt, response, reference answer or judge rationale is included in this report.
