# Fireworks Verify-or-Repair Arena V3

## Decision

The one-call review tier is **not enabled**. Direct Fireworks remains the fallback for every stratum.

## Contract

The reviewer receives only the raw task and the untrusted E2B candidate. It returns `APPROVE` or `REPLACE` followed by the replacement answer. This control header is internal; the user-facing answer remains free-form and the official `{task_id, answer}` JSON is reconstructed only by the Answer Contract Engine.

## Paired Evidence

The frozen arena sampled correct and incorrect E2B candidates across the eight Track 1 intents. Kimi answered directly and reviewed the candidate on the same task. MiniMax judged outputs blind to route, with a recorded Kimi fallback only when the offline judge failed its control contract.

| Metric | Direct | Verify-or-repair |
|---|---:|---:|
| Completed paired tasks | 27 | 27 |
| Judged correct | 14 | 18 |
| Fireworks tokens | 9,948 | 10,796 |
| Mean tokens/task | 368.4 | 399.9 |
| Malformed control outputs | 0 | 2 |

Review used `848` more Fireworks tokens (`8.52%`) overall. Code debugging saved 26 tokens over four tasks and sentiment saved 21 over three, but neither support is large enough for promotion. The 19 short-candidate tasks saved only 76 tokens in total and included one malformed review. No stratum has a positive lineage-aware confidence interval for token savings.

The arena stopped rather than spend further credits after the global token gate had failed. Malformed review output remains fail-closed to direct Fireworks in the implemented runtime component.
