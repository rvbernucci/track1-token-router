# Boundary-Trained E2B ML Audit

## Question

The 480-row boundary OOF report found `276/288` correct selectively routed answers (`95.83%`) and strong code-generation, factual-QA and summarization cohorts. Does that justify enabling those intents in the hidden evaluator?

## Evidence Boundary

The OOF result is valid but internal to the boundary corpus: each lineage-grouped fold was predicted by a model trained on the other boundary folds. It proves that the corpus contains learnable easy-task structure. It does not prove transfer to a different task lineage.

We therefore converted all 480 boundary rows from audit data into training data, trained per-intent ridge logistic, histogram gradient boosting and Extra Trees classifiers, selected thresholds only on the existing calibration splits, and opened only legacy and expansion protected holdouts for final audit.

## Independent Result

Extra Trees was the strongest challenger. It selected only sentiment outside the boundary corpus:

| Holdout | Selected | Correct | Precision | Wilson 95% lower |
|---|---:|---:|---:|---:|
| Expansion | 26 | 25 | 96.15% | 81.11% |
| Historical | 3 | 3 | 100.00% | 43.85% |
| Combined | 29 | 28 | 96.55% | 82.82% |

Code generation, factual Q&A, summarization, logic puzzles, NER, code debugging and math reasoning produced no eligible operating point with minimum support on the independent holdouts. Ridge selected 16 sentiment rows at `93.75%`; histogram gradient boosting selected none.

## Decision

The multicategory boundary classifier remains a shadow challenger. Promoting it would assume that the hidden evaluator matches the boundary generator rather than the independent legacy and expansion distributions. The main image therefore remains sentiment-only, while the OOF table is retained as evidence that a future broader, independently generated easy-task corpus could unlock additional zero-token coverage.
