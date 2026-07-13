# Full Population Evaluation

## Scope

Sprint 81 replayed two distinct populations on the AMD GPU environment:

- 4,400 general Track 1 prompts answered by the embedded text-only Gemma 4 E2B model and processed by the Answer Contract Engine.
- 2,000 FunctionGemma tool-planner examples: 1,750 training examples and 250 validation examples.

These strata measure different capabilities and must not be collapsed into one accuracy number. The E2B population measures answer correctness. The planner population measures whether a local deterministic tool can be selected and executed with independently reproducible evidence.

The additional planner calibration and sealed-holdout splits were intentionally excluded from this 6,400-case replay and remain reserved for final confirmation.

## E2B Results

All 4,400 answers were validated after the Answer Contract Engine. Mechanical validators made 2,535 hard decisions. Antigravity, pinned to the expected account and Gemini 3.5 Flash Medium, judged the remaining 1,865 cases against their reference answers and rubrics. Failed judge batches were discarded and replayed until all candidate IDs had exactly one verdict.

| Category | Correct | Incorrect | Accuracy |
|---|---:|---:|---:|
| Code debugging | 323 | 227 | 58.73% |
| Code generation | 186 | 364 | 33.82% |
| Factual Q&A | 373 | 177 | 67.82% |
| Logic puzzles | 221 | 329 | 40.18% |
| Math reasoning | 249 | 301 | 45.27% |
| NER | 219 | 331 | 39.82% |
| Sentiment | 498 | 52 | 90.55% |
| Summarization | 310 | 240 | 56.36% |
| **Total** | **2,379** | **2,021** | **54.07%** |

The unrestricted E2B result is not a routing target. It demonstrates why the local model must remain behind a calibrated selective gate. Sentiment is the strongest broad category, while the other categories require sub-cohort selection rather than category-wide release.

### Dataset roles

| Role | Correct | Incorrect | Accuracy |
|---|---:|---:|---:|
| Fit | 1,437 | 1,203 | 54.43% |
| Calibration | 481 | 399 | 54.66% |
| Protected holdout | 461 | 419 | 52.39% |

The small fit-to-holdout decline indicates limited distribution shift, but it also confirms that broad E2B release would be unsafe.

## Planner Results

| Metric | Result |
|---|---:|
| Population | 2,000 |
| Tool-eligible tasks | 1,600 |
| Proven local answers released | 1,591 |
| Correct released answers | 1,591 |
| Selective precision | 100.00% |
| Recall on tool-eligible tasks | 99.44% |
| Safe declines | 400/400 |
| Unsafe false positives | 0 |
| Guarded fallbacks | 9 |

Eight guarded fallbacks introduced a number absent from the prompt. One proposed an inventory operation without explicit ordering provenance. Replaying those cases produced the same guard rejection, confirming systematic fail-closed behavior rather than transient inference failure.

### Planner families

| Family | Correct releases | Eligible | Recall |
|---|---:|---:|---:|
| Calculator | 398 | 400 | 99.50% |
| Inventory | 393 | 400 | 98.25% |
| Logic | 400 | 400 | 100.00% |
| Recipe | 400 | 400 | 100.00% |
| Unsupported/none | 400 safe declines | 400 | 100.00% safe |

## Implications

- Keep deterministic tool execution behind provenance validation and independent proof recomputation.
- Use the 4,400 labeled E2B outcomes to retrain the selective gate, not to enable whole categories.
- Optimize first for precision on released E2B answers; Fireworks remains the fallback for rejected or invalid local decisions.
- Preserve planner calibration and sealed-holdout splits for the final no-tuning confirmation.

Raw generations, judge outputs, and task-level labels are retained under the ignored local path `reports/generated/s81-full-population/`. Protected prompt text is not committed.
