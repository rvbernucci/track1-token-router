# Long Description

Track 1 Token Router is a CLI-first competitive agent for the AMD Developer Hackathon Track 1 challenge. The project treats token efficiency as an orchestration problem, not as a single prompt trick. It handles the eight official general-purpose categories with a Fireworks-compatible router, calibrated model selection, compact answer prompts and mechanical validators that protect schema, format and high-confidence calculations without replacing the AI agent.

The repository is designed to be reproducible before credits arrive. It includes a no-credit competition mode, fuzz tests for official input uncertainty, an offline scoring arena, battle drill reports, Fireworks activation runbooks, Docker support and CI gates. It also includes AMD/Gemma runtime profiles for development and calibration, while the submitted image remains small and compatible with the official CPU/RAM grading envelope. The main goal is to maximize accuracy while spending remote tokens only when the expected quality gain justifies the cost.

The system is intentionally headless and evaluator-friendly: stdout stays clean, logs are structured JSONL, and adapters isolate official input formats from the core runner.
