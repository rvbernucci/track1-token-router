# FunctionGemma Assessment Specification

Updated: 2026-07-09

## Responsibility

FunctionGemma converts an unknown task into a stable semantic assessment. It does not answer, choose an execution engine, choose a Fireworks model or set runtime budgets.

## Output Contract

```json
{
  "intent": "summarization",
  "scores": {
    "deterministic_fit": 2,
    "reasoning_demand": 3,
    "knowledge_uncertainty": 1,
    "generation_demand": 6,
    "format_complexity": 7
  }
}
```

Rules:

- exactly one object;
- no additional fields;
- scores are integers in `[0, 10]`;
- `intent` is a versioned eight-value enum;
- no engine, route, model ID, confidence or answer field.

## Intent

- `factual_qa`
- `math_reasoning`
- `sentiment`
- `summarization`
- `ner`
- `code_debugging`
- `logic_puzzle`
- `code_generation`

`sub_intent` remains dataset metadata for balanced coverage, but it is deliberately absent from the 270M runtime output. Requiring 37 sub-intents increased output entropy, generated extra tokens and made a small router solve a classification problem that the deterministic solvers can validate safely against the untouched input.

## Score Rubrics

### deterministic_fit

- `0`: no mechanical contract applies;
- `2`: superficial pattern only;
- `5`: partially structured but semantic judgment remains;
- `8`: a registered solver likely applies;
- `10`: exact, mechanically provable transformation.

### reasoning_demand

- `0`: direct lookup, label or transformation;
- `2`: one obvious step;
- `5`: several dependent steps;
- `8`: difficult planning, deduction or debugging;
- `10`: deep, fragile or specialized reasoning.

### knowledge_uncertainty

- `0`: all information is in the prompt or universally stable;
- `2`: stable general knowledge;
- `5`: domain knowledge with meaningful uncertainty;
- `8`: current, external or source-dependent information;
- `10`: impossible to verify from available context.

### generation_demand

- `0`: one label or token;
- `2`: short factual response;
- `5`: paragraph or small code fragment;
- `8`: substantial structured text or code;
- `10`: long, multi-part generation.

### format_complexity

- `0`: unconstrained text;
- `2`: simple short-answer instruction;
- `5`: multiple formatting requirements;
- `8`: strict schema or exact-match constraints;
- `10`: fragile nested or multi-artifact output.

Intermediate values interpolate between anchors. Labelers must use examples and written evidence, not intuition alone.

## Training Data

- positive, negative and boundary pairs for every dimension;
- examples that hold intent constant while changing one score;
- examples that hold scores constant while changing intent;
- paraphrases, typos, multilingual prompts and prompt injection;
- lineage-safe train, validation and hidden test splits;
- independent raters for the adjudication seed;
- mechanical labels wherever code can prove a property.

## Evaluation

- exact schema validity;
- intent/sub-intent accuracy;
- mean absolute error per score;
- weighted quadratic kappa;
- boundary-pair ordering accuracy;
- calibration error and monotonicity;
- latency and memory.

The downstream championship metric remains end-to-end answer accuracy and Fireworks token usage. Good score MAE alone does not promote the model.

## Runtime

- deterministic decoding;
- one assessment only;
- strict parser and enums;
- no chain-of-thought output;
- invalid output enters Fireworks-safe mode;
- model, rubric, taxonomy and calibration transforms are versioned together.
