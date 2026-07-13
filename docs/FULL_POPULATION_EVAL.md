# Full Population Evaluation

## Scope

Sprint 81 replayed two distinct populations on the AMD GPU environment:

- 4,400 general Track 1 prompts answered by the embedded text-only Gemma 4 E2B model and processed by the Answer Contract Engine.
- 2,000 FunctionGemma tool-planner examples: 1,750 training examples and 250 validation examples.

These strata measure different capabilities and must not be collapsed into one accuracy number. The E2B population measures answer correctness. The planner population measures whether a local deterministic tool can be selected and executed with independently reproducible evidence.

The additional planner calibration and sealed-holdout splits were intentionally excluded from this 6,400-case replay and remain reserved for final confirmation.

## E2B Results

All 4,400 answers were validated after the Answer Contract Engine. Mechanical validators made 2,504 hard decisions. Antigravity, pinned to the expected account and Gemini 3.5 Flash Medium, judged the remaining 1,896 cases against their reference answers and rubrics. Failed judge batches were discarded and replayed until all candidate IDs had exactly one verdict. A reference-shape audit moved 31 cases with inconsistent reference metadata out of mechanical rejection and into semantic adjudication; 17 were accepted.

| Category | Correct | Incorrect | Accuracy |
|---|---:|---:|---:|
| Code debugging | 323 | 227 | 58.73% |
| Code generation | 186 | 364 | 33.82% |
| Factual Q&A | 373 | 177 | 67.82% |
| Logic puzzles | 229 | 321 | 41.64% |
| Math reasoning | 253 | 297 | 46.00% |
| NER | 224 | 326 | 40.73% |
| Sentiment | 498 | 52 | 90.55% |
| Summarization | 310 | 240 | 56.36% |
| **Total** | **2,396** | **2,004** | **54.45%** |

The unrestricted E2B result is not a routing target. It demonstrates why the local model must remain behind a calibrated selective gate. Sentiment is the strongest broad category, while the other categories require sub-cohort selection rather than category-wide release.

### Dataset roles

| Role | Correct | Incorrect | Accuracy |
|---|---:|---:|---:|
| Fit | 1,448 | 1,192 | 54.85% |
| Calibration | 483 | 397 | 54.89% |
| Protected holdout | 465 | 415 | 52.84% |

The small fit-to-holdout decline indicates limited distribution shift, but it also confirms that broad E2B release would be unsafe.

## Selective 192-token retry

The 411 answers rejected by the 96-token Answer Contract Engine were replayed once with a 192-token ceiling. The retry restored a valid contract for 105 cases, but semantic adjudication accepted only 26 additional answers. Correctness increased from 2,396/4,400 (54.45%) to 2,422/4,400 (55.05%). Recoveries were limited to code debugging (11), NER (10), code generation (4), and summarization (1).

This supports one retry only after a concrete contract failure. It does not support a global 192-token default. The AMD replay remained well below 30 seconds per request, but the exact `linux/amd64`, 4 GB, 2 vCPU image must repeat the latency gate before promotion.

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

## Proof-First Deterministic Replay

After the planner replay, the proof engine was extended with closed grammars for the four eligible families. The runtime recognizes only complete expressions, ordered inventory operations, dimensionally consistent recipe-cost statements, and ordering graphs with a unique endpoint. It executes arithmetic with exact rational values and rejects division by zero, incompatible units, negative inventory, incomplete operations, and ambiguous graphs.

The updated proof engine was replayed against the same 2,000 prompts without access to expected answers at inference time:

| Family | Proven answers | Exact matches | Precision |
|---|---:|---:|---:|
| Calculator | 400 | 400 | 100.00% |
| Inventory | 400 | 400 | 100.00% |
| Logic | 400 | 400 | 100.00% |
| Recipe | 400 | 400 | 100.00% |
| Unsupported/none | 0 | 0 | Safe decline |
| **Total** | **1,600/2,000** | **1,600/1,600** | **100.00% selective** |

Proof-carrying solvers now run before FunctionGemma assessment. This removes local-model latency and failure risk for accepted tasks while preserving the planner and Fireworks fallback for every non-matching prompt. The change does not cache task answers: each result is recomputed from literals and operations parsed from the current prompt.

Fireworks calls also share an absolute 28-second per-task deadline. Initial calls, option fallbacks, alternate-model attempts, and truncation retries receive only the remaining budget, preventing a late retry from violating the 30-second evaluator limit.

## Implications

- Keep deterministic tool execution behind provenance validation and independent proof recomputation.
- Prefer direct proof execution before model assessment whenever the full closed grammar accepts the task.
- Use the 4,400 labeled E2B outcomes to retrain the selective gate, not to enable whole categories.
- Optimize first for precision on released E2B answers; Fireworks remains the fallback for rejected or invalid local decisions.
- Preserve planner calibration and sealed-holdout splits for the final no-tuning confirmation.

Raw generations, judge outputs, and task-level labels are retained under the ignored local path `reports/generated/s81-full-population/`. Protected prompt text is not committed.
