# Gemma 4 E2B Text-Only Runtime

Updated: 2026-07-10

## Decision

Use the official instruction-tuned Gemma 4 E2B LiteRT-LM artifact as the local answer generator challenger:

```text
litert-community/gemma-4-E2B-it-litert-lm
```

Pinned revision: `6664aee5fc114b486e2fec56a9f73c0146e79e74`
Pinned file: `gemma-4-E2B-it.litertlm`
File size: `2,588,147,712` bytes
SHA-256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`

Do not manually delete multimodal tensors from the standard checkpoint. The mobile/QAT artifact already loads vision and audio on demand and provides the intended low-memory text path.

## Why LiteRT-LM

- supports Linux `x86_64` and CPU inference;
- uses the official `.litertlm` deployment format;
- supports Python and an OpenAI-compatible server mode;
- uses mixed 2/4/8-bit mobile quantization and memory mapping;
- keeps the final model local, so Fireworks token cost is zero.

## Resource Reality

The official model card reports a `2,583 MB` file and `1,628 MB` CPU memory on Linux ARM for the standard artifact. The AMD pod download independently measured `2,588,147,712` bytes. These are promising reference values, not substitutes for the required constrained Linux `amd64` measurement.

AMD pod `x86_64` one-shot smoke evidence with LiteRT-LM `0.14.0`, explicitly selected CPU backend, two pinned cores, 1024 KV tokens, deterministic decoding and disk cache:

| Run | Output | Wall time | Peak RSS | Exit |
|---|---:|---:|---:|---:|
| cold | `4` | `6.44 s` | `1,600,984 KB` | `0` |
| warm | `4` | `1.10 s` | `1,444,104 KB` | `0` |

The pod has 503 GiB RAM, so these measurements validate the artifact/runtime pair but not the grader OOM boundary. The final container must still pass `--memory=4g --cpus=2`.

The stock `litert-lm serve` command selects the artifact's default GPU backend and does not expose a backend flag. Do not use it for grader CPU claims. The project-owned `scripts/litert_cpu_server.py` forces CPU and records the thread/context configuration before serving requests.

Budget target:

| Component | Initial budget |
|---|---:|
| E2B runtime working set | 2.0 GB |
| FunctionGemma 270M runtime | 0.7 GB |
| Python/orchestrator/results | 0.4 GB |
| Safety margin and file-backed pressure | 0.9 GB |
| Total | 4.0 GB |

These are engineering budgets to test, not guaranteed measurements.

The promoted 93-task run, combined-memory run and 2,000-task regression experiment use a 2048-token context. The earlier 1024-context smoke remains cold/warm evidence only.

## Promoted Runtime Limits

- context: `2048` tokens;
- maximum local output: `96` tokens;
- CPU threads: `2`;
- one E2B process per container;
- no vision or audio assets;
- no model download at evaluator startup;
- no speculative draft model until baseline memory and latency pass.
- system packages: `libvulkan1`, `mesa-vulkan-drivers` and GNU `time` for the benchmark image.

## OpenAI Adapter Compatibility

LiteRT-LM `0.14.0` enforces `max_completion_tokens` on `/v1/chat/completions`; it silently ignores the legacy `max_tokens` field. The E2B client therefore sends both aliases, with the same value, so LiteRT-LM receives a hard cap while the request remains compatible with older OpenAI-style adapters.

This was verified on the AMD pod with an adversarial prompt requesting the integers from 1 through 1000. With `max_completion_tokens=8`, generation stopped at exactly eight characters: `1, 2, 3,`. A prior run using only `max_tokens` produced an unbounded answer and is quarantined from the outcome matrix. Do not remove the current field or promote a runtime without repeating this cap test.

## Promotion Matrix

The adaptive `96 -> 192 -> 384` experiment and its conservative teacher-consensus policy are specified in [`E2B_TOKEN_LADDER.md`](E2B_TOKEN_LADDER.md).

| Task family | Initial state |
|---|---|
| Sentiment | Candidate |
| NER | Candidate |
| Short stable factual QA | Candidate with strict calibration |
| Short summarization | Candidate |
| Simple code debugging | Experimental |
| Math reasoning | Fireworks unless deterministic |
| Logic puzzles | Fireworks unless deterministic |
| Code generation | Fireworks by default |

Promote per family, never globally.

## Combined Memory Evidence

FunctionGemma Q8 and the standard E2B artifact were loaded together on the AMD `x86_64` pod and both completed inference. The conservative sum of each process's historical high-water RSS was:

| Runtime | VmHWM |
|---|---:|
| FunctionGemma Q8, llama.cpp, context 2048 | 1,241.594 MiB |
| Gemma E2B mixed 2/4/8-bit, LiteRT-LM CPU, context 2048 | 1,471.332 MiB |
| Combined | 2,712.926 MiB / 2.649 GiB |
| Remaining to 4 GiB | 1,383.074 MiB |

The pod exposes cgroup v2 read-only, so the final 4 GiB limit could not be imposed there. This passes the measured-memory gate with useful margin but does not replace the final Docker `--memory=4g --cpus=2` test. Raw process, cgroup and smoke evidence is hashed in `reports/generated/amd-pod-scale789/memory/combined-memory-report.json`.

## Required Benchmark

Run the E2B route under:

```bash
docker run --rm --memory=4g --cpus=2 YOUR_IMAGE:TAG
```

Measure cold start, warm start, p50/p95 latency, prompt prefill, decode rate, peak RSS, exact output validity and category accuracy. Test both isolated E2B and E2B loaded beside FunctionGemma.

## Rejection Conditions

Reject E2B from the final image if:

- combined peak RSS approaches the 4 GB limit without safety margin;
- the batch cannot finish within 10 minutes;
- quantization causes a material accuracy drop;
- startup requires network access;
- Linux `amd64` packaging is unstable;
- remote token savings do not compensate for accuracy or latency loss.

## References

- [Gemma 4 overview](https://ai.google.dev/gemma/docs/core)
- [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Gemma 4 E2B LiteRT-LM artifact](https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm)
- [LiteRT-LM](https://github.com/google-ai-edge/LiteRT-LM)
