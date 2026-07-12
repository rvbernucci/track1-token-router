# Router ML v3 Neural Audit

## Decision

**Do not promote the neural challenger to the submitted runtime.** The experiment improved
probability ranking and calibration, but replacing the current E2B gate would reduce expected
end-to-end accuracy.

## Training protocol

- Hardware: AMD hackathon GPU pod with ROCm 7.2 and PyTorch 2.9.
- Ledger: 4,400 rows with lineage-disjoint fit, calibration, and protected-holdout partitions.
- Fit rows with valid assessments: 2,625.
- Search: 24 shared-network configurations and 8 configurations per intent.
- Validation: five lineage-grouped folds and five random seeds per configuration.
- Runtime constraint: the exported ensemble is standard-library replayable and requires no
  PyTorch dependency in the submission image.
- Leakage control: all 880 protected labels remained redacted until the model, calibration, and
  routing threshold were frozen.

## Model comparison

| Candidate | Grouped OOF AUROC | Brier | Log loss | Runtime exportable |
|---|---:|---:|---:|---|
| Logistic regression | 0.87737 | 0.14693 | 0.45009 | Yes |
| Shared neural ensemble | **0.88984** | **0.13457** | **0.42519** | Yes |
| Histogram gradient boosting | 0.89025 | 0.13359 | 0.42575 | No |
| Per-intent neural ensembles | 0.85945 | 0.15582 | 0.59200 | Yes |

The shared neural ensemble was the exportable champion. It used one-hot intent features in
addition to FunctionGemma scores, mechanical prompt signals, answer-contract signals, and proof
engine signals.

## Frozen selection surface

The original minimum-support rule of 30 discarded a valid high-confidence segment. Before
opening the protected holdout, the support floor was made configurable and the following
surface was frozen:

- Eligible intent: sentiment only.
- Calibrated probability threshold: 0.966505.
- Threshold-selection result: 17/17 correct.
- Precision: 100%.
- Wilson 90% lower bound: 86.27%.
- Development replay: 138/140 correct, or 98.57% precision at 3.98% coverage.

## One-time protected audit

The frozen challenger selected 39 of 880 protected examples:

- Correct: 37/39.
- Precision: 94.87%.
- Uniform coverage: 4.43%.
- Estimated Fireworks tokens avoided: 3,783.

The current production matrix selected 90 protected examples and achieved 83/90, or 92.22%.
The challenger selected a strict subset of that cohort. The 51 production-only examples were
46/51 correct, or 90.20%, which is materially stronger than the observed 63.2% overall evaluator
baseline. Sending those examples back to Fireworks would therefore lower expected accuracy.

## Conclusion

The neural work succeeded as a calibrated risk estimator, but it did not produce a production
policy that dominates the current matrix gate. ProofRoute keeps the current policy and records
the neural challenger as a rejected, reproducible experiment. Accuracy remains the hard gate;
token savings do not justify replacing a stronger local cohort.
