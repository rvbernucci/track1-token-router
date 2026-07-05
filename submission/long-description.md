# Long Description

Track 1 Token Router is a CLI-first competitive agent for the AMD Developer Hackathon Track 1 challenge. The project treats token efficiency as an orchestration problem, not as a single prompt trick. It answers easy mechanical tasks with guardrails and deterministic solvers, sends broader tasks to a local model, verifies local candidates with a second local pass, and escalates only risky cases to Fireworks as a compact approve-or-replace auditor.

The repository is designed to be reproducible before credits arrive. It includes a no-credit competition mode, fuzz tests for official input uncertainty, an offline scoring arena, battle drill reports, runtime profiles for AMD/DigitalOcean MI300X with vLLM or SGLang, Fireworks activation runbooks, Docker support and CI gates. The main goal is to maximize accuracy while spending remote tokens only when the expected quality gain justifies the cost.

The system is intentionally headless and evaluator-friendly: stdout stays clean, logs are structured JSONL, and adapters isolate official input formats from the core runner.
