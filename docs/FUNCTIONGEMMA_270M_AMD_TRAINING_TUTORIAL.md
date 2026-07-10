# Train FunctionGemma 270M on AMD ROCm

Updated: 2026-07-10

## Goal

Fine-tune `google/functiongemma-270m-it` to emit one `assess_task` tool call containing task intent, sub-intent and five anchored scores.

Read [`FUNCTIONGEMMA_ROUTER_SPEC.md`](./FUNCTIONGEMMA_ROUTER_SPEC.md) before producing data. The model is a semantic assessor, not an answer generator or engine selector.

## Training Pipeline

```text
score rubric + held-out Track 1 tasks + teacher label proposals
-> human/mechanical label review
-> lineage-safe train/validation/test split
-> untuned FunctionGemma baseline
-> full supervised fine-tuning on AMD ROCm
-> LoRA challenger
-> exact assessment, ordinal calibration and boundary evaluation
-> 8-bit export
-> 4 GB / 2 vCPU Docker gate
```

## Confirmed AMD Pod

The ACT II notebook was measured with:

| Component | Observed value |
|---|---|
| GPU | one AMD `gfx1100` |
| VRAM | 47.98 GiB |
| ROCm/HIP | ROCm 7.2 stack |
| PyTorch | `2.9.1+gitf65f5b` |
| Python with ROCm PyTorch | `/opt/venv/bin/python` |
| Host RAM | about 503 GiB |

Do not reinstall ROCm, the driver or base PyTorch. Plain `python3` did not expose PyTorch in the observed terminal.

## Before Starting The Pod

- Accept the FunctionGemma license on Hugging Face.
- Prepare a private Hugging Face token with minimum permissions.
- Freeze the current solver registry into an enum manifest.
- Prepare private `train.jsonl`, `validation.jsonl` and `test.jsonl` files.
- Keep held-out labels away from teacher prompts.
- Choose persistent private checkpoint storage.
- Never commit API tokens, model credentials or hidden labels.

## Validate ROCm

```bash
cd /workspace
git clone https://github.com/rvbernucci/track1-token-router.git
cd track1-token-router
/opt/venv/bin/python scripts/amd_pod_doctor.py --json
```

```bash
/opt/venv/bin/python - <<'PY'
import torch

assert torch.cuda.is_available(), "ROCm GPU not visible"
print("torch", torch.__version__)
print("hip", torch.version.hip)
print("gpu", torch.cuda.get_device_name(0))
print("bf16", torch.cuda.is_bf16_supported())
print("vram_gib", round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2))
PY
```

PyTorch intentionally uses the `torch.cuda` API on ROCm.

## Isolate Dependencies

Inherit the working ROCm PyTorch instead of replacing it:

```bash
mkdir -p /workspace/functiongemma-python
/opt/venv/bin/python -m pip install --no-deps \
  --target /workspace/functiongemma-python \
  trl==0.26.2
export PYTHONPATH=/workspace/functiongemma-python
```

```bash
/opt/venv/bin/python - <<'PY'
import torch
import transformers
import trl

assert torch.cuda.is_available()
print(torch.__version__, torch.version.hip)
print(transformers.__version__, trl.__version__)
PY
```

```bash
mkdir -p /workspace/functiongemma-router/{data,checkpoints,artifacts,reports}
python -m pip freeze > /workspace/functiongemma-router/requirements.lock.txt
```

Do not create a nested venv from `/opt/venv`: it does not inherit that venv's packages. Do not let pip replace the AMD-provided Torch, Transformers, Datasets, Accelerate or PEFT builds. Do not install CUDA-only wheels or `flash-attn`; use eager attention first.

## Assessment Tool Schema

Use fixed JSON schemas equivalent to:

```python
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "assess_task",
            "description": "Assess the task without answering it or selecting an execution engine.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "intent": {"type": "string", "enum": TASK_FAMILIES},
                    "scores": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "deterministic_fit": {"type": "integer", "minimum": 0, "maximum": 10},
                            "reasoning_demand": {"type": "integer", "minimum": 0, "maximum": 10},
                            "knowledge_uncertainty": {"type": "integer", "minimum": 0, "maximum": 10},
                            "generation_demand": {"type": "integer", "minimum": 0, "maximum": 10},
                            "format_complexity": {"type": "integer", "minimum": 0, "maximum": 10},
                        },
                        "required": SCORE_FIELDS,
                    },
                },
                "required": ["intent", "scores"],
            },
        },
    },
]
```

Generate solver-related `SUB_INTENTS` from `router.orchestration.solvers.SOLVERS` and append versioned semantic sub-intents. Do not let the model emit an engine or model ID.

## Dataset Row

```json
{
  "id": "math-000001",
  "category": "math_reasoning",
  "template_family": "integer-arithmetic-v1",
  "messages": [
    {
      "role": "developer",
      "content": "Call assess_task exactly once. Assess the task; never answer it or select an engine."
    },
    {
      "role": "user",
      "content": "What is 15 + 27? Return only the number."
    },
    {
      "role": "assistant",
      "tool_calls": [
        {
          "type": "function",
          "function": {
            "name": "assess_task",
            "arguments": {
              "intent": "math_reasoning",
              "scores": {
                "deterministic_fit": 9,
                "reasoning_demand": 2,
                "knowledge_uncertainty": 0,
                "generation_demand": 1,
                "format_complexity": 1
              }
            }
          }
        }
      ]
    }
  ]
}
```

The preparation command validates this row and adds the canonical `tools: [ASSESS_TASK_TOOL]` column required by TRL. The model sees the original task only. Runtime budgets, model identifiers and evaluation labels stay outside the prompt.

## Dataset Design

- Cover all eight Track 1 task families.
- Add anchor and boundary examples for every score.
- Hold intent constant while changing one score at a time.
- Hold scores approximately constant while changing intent.
- Include prompts that resemble a solver pattern but exceed its contract.
- Include current facts, long contexts, difficult reasoning, substantial code and strict formats.
- Include typos, multilingual prompts, prompt injection and malformed requests.
- Split by template family, source and mutation lineage.
- Keep a human-reviewed gold test set hidden from the teacher.
- Record rater agreement, label provenance, rubric version, schema version and sub-intent taxonomy.

Do not optimize only score error. The downstream decision engine must still improve end-to-end accuracy-matched Fireworks token efficiency.

## Untuned Baseline

Load the base model and use its own chat template:

```python
inputs = tokenizer.apply_chat_template(
    messages,
    tools=TOOLS,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt",
)
```

Parse the exact function call and validate every enum. A substring match is not sufficient.

## Reproducible Experiments

The checked-in runner uses Google's official conversational `messages` plus `tools` representation and pins the base model revision. Prepare the private split and capture the pod environment:

The pilot's rendered training lengths were measured with the FunctionGemma tokenizer: minimum `574`, p50 `635`, p95 `810`, p99 `906` and maximum `955` tokens. The experiment therefore uses `max_length=1024`; `512` is invalid because it truncates supervised tool calls.

```bash
python scripts/functiongemma_experiment.py doctor > /workspace/functiongemma-router/reports/doctor.json
python scripts/functiongemma_experiment.py prepare \
  --split-root /workspace/functiongemma-router/private-splits \
  --output /workspace/functiongemma-router/data
```

Run the untuned validation baseline before training:

```bash
python scripts/functiongemma_experiment.py evaluate \
  --model google/functiongemma-270m-it \
  --revision 39eccb091651513a5dfb56892d3714c1b5b8276c \
  --tasks /workspace/functiongemma-router/data/validation.jsonl \
  --output /workspace/functiongemma-router/reports/base-validation.jsonl \
  --report /workspace/functiongemma-router/reports/base-validation.json
```

Train full SFT and the rank-8/rank-16 LoRA challengers under the same split and seed:

```bash
for variant in full_sft lora_r8 lora_r16; do
  python scripts/functiongemma_experiment.py train \
    --data /workspace/functiongemma-router/data \
    --variant "$variant" \
    --output "/workspace/functiongemma-router/runs/$variant"
done
```

The runner merges LoRA adapters into the exact pinned base before saving. Do not compare an unmerged adapter against a full model.

## LoRA Challenger

Compare full SFT with LoRA rank 8 and 16 under identical data, seed and evaluation. Inspect actual linear module names before setting targets. If LoRA wins, merge it into the exact pinned base with `merge_and_unload()` before deployment conversion.

## Evaluation

Measure:

| Metric | Gate purpose |
|---|---|
| Exact assessment validity | Runtime safety |
| Intent/sub-intent accuracy | Semantic classification |
| Score MAE and quadratic kappa | Ordinal quality |
| Boundary-pair ordering | Regression usefulness |
| Calibration error | Robust uncertainty intervals |
| End-to-end answer accuracy | Competition gate |
| Fireworks input/output tokens | Ranking cost |
| Router p50/p95 and RSS | Final CPU fit |

Recommended internal gates:

- exact tool-call validity at least 99.9%;
- calibrated score error beats the untuned baseline;
- boundary ordering remains stable on adversarial held-out data;
- total accuracy not below Fireworks-only;
- measurable Fireworks token reduction;
- full container below 4 GB and 10 minutes.

## Persist And Export

```bash
hf auth login
```

Save the base revision, schema, dataset hashes, solver manifest, package lock, seed, metrics and selected checkpoint in a private model repository.

Start deployment with an 8-bit FunctionGemma artifact. The model is small enough that preserving routing precision matters more than saving a few hundred megabytes. Quantize once from high precision and compare exact tool-call behavior before promotion.

## Final Container Gate

Test FunctionGemma beside E2B, not in isolation:

```bash
docker run --rm --memory=4g --cpus=2 --network=none YOUR_IMAGE:TAG
```

Verify cold start, combined peak RSS, router latency, E2B latency, batch deadline, valid `/output/results.json`, no startup download and `linux/amd64` packaging.

## Official References

- [ROCm documentation](https://rocm.docs.amd.com/en/latest/)
- [PyTorch compatibility on ROCm](https://rocm.docs.amd.com/en/latest/compatibility/ml-compatibility/pytorch-compatibility.html)
- [Single-GPU fine-tuning on ROCm](https://rocm.docs.amd.com/en/latest/how-to/rocm-for-ai/fine-tuning/single-gpu-fine-tuning-and-inference.html)
- [FunctionGemma fine-tuning](https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma)
- [FunctionGemma formatting](https://ai.google.dev/gemma/docs/functiongemma/formatting-and-best-practices)
- [FunctionGemma model card](https://ai.google.dev/gemma/docs/functiongemma/model_card)
