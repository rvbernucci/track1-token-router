# Gemma 4 E2B IT GGUF CPU Container Gate

## Result

**Passed as a local parallel experiment.** This does not replace the submitted image.

The official `google/gemma-4-E2B-it-qat-q4_0-gguf` text model was packaged with a CPU-only `llama.cpp` server and tested on the x86_64 desktop under the evaluator resource envelope.

## Container

- Architecture: `linux/amd64`.
- Model: official Gemma 4 E2B IT QAT Q4_0 GGUF.
- Model file: approximately 3.2 GB.
- Local image size: 3,451,589,602 bytes uncompressed.
- Runtime: CPU-only `llama.cpp`, two threads, 2,048-token context, one slot.
- Limits: 4 GB RAM, 4 GB swap ceiling, 2 vCPU and 256 PIDs.
- No model download or setup occurs at startup.

## Gates

| Gate | Result |
|---|---|
| Model load under 4 GB | Pass |
| Single exact-answer inference | Pass (`OK`) |
| Network-disabled model load | Pass |
| Network-disabled loopback inference | Pass (`HTTP 200`, `OK`) |
| OOM status | Pass (`false`) |
| Observed post-inference memory | 1.128 GiB |
| Exact-answer latency | 4.576 s |
| Five-row balanced planner smoke | 4/5 final-correct, 0 unsafe false positives |
| Planner smoke mean latency | 12.527 s/task |

The balanced smoke released correct inventory, recipe and logic plans, safely rejected the unsupported control and fell back on the calculator case.

## Decision

The GGUF runtime is viable enough for a larger challenger experiment. It must still pass a representative ten-minute batch, exact router integration, image compression audit and accuracy comparison before replacing the LiteRT artifact in a public submission image.

## Reproduction Assets

- `docker/experiments/Dockerfile.gemma4-e2b-gguf-cpu`
- `scripts/test_gemma4_e2b_gguf_container.py`
- `scripts/offline_llama_http_smoke.sh`
