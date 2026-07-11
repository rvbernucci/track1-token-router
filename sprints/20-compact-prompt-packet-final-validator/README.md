# Sprint 20 - Compact Prompt Packet & Final Validator

## Type

Does not depend on credit.

## Objective

Standardize the minimum packet sent to the remote auditor and add a final format validator before returning the response.

## Why It Matters

The remote should be used as insurance, not as a long conversation. And a correct answer in the wrong format can count as an error.

## Deliverables

- Module `router/orchestration/prompt_packet.py`.
- Module `router/orchestration/final_validator.py`.
- `RemoteAuditPacket` contract.
- `FinalValidationResult` contract.
- Packet size meter.
- Common format validators.
- JSON, pure number, literal echo, and free text tests.

## Checklist

- [x] Define minimum remote packet: task, candidate, concern, expected format.
- [x] Remove redundant information from the packet.
- [x] Measure characters and estimated tokens of the packet.
- [x] Validate JSON response when the task requests JSON.
- [x] Validate pure number when the task requests a number.
- [x] Validate literal echo when the task requests exact text.
- [x] Validate improper empty response.
- [x] Validate excess markdown in strict format.
- [x] Add simple local repair when format validation fails.
- [x] Integrate format failure into the trace.
- [x] Integrate packet size into the scoreboard.
- [x] Add regression tests.

## Acceptance Criteria

- The remote packet is smaller than the equivalent raw prompt.
- The final validator blocks obviously incorrect formats.
- Format failures become a signal for policy/budget.
- The final response remains free when the task does not require a strict format.

## Expected Output

Fewer remote tokens and fewer silly losses due to formatting.

## Local Evidence

```bash
python3 -m unittest tests.test_prompt_packet_and_validator
python3 scripts/offline_score_simulator.py
ENABLE_ORCHESTRATOR=1 python3 -m router ask "Return exactly SAFE_OUTPUT and nothing else." --json
scripts/offline_release_check.sh
```

## Decision

The remote packet is stored in `RemoteAuditPacket` with only the compacted task, candidate, concern, and expected format. The final validator runs inside `OrchestratedRunner` when the orchestrator is enabled, without changing the default path.
