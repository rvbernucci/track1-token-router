# Wilson-Nash Risk Ladder V1

## Frozen Policy

The policy uses a `90%` Wilson confidence level. This is distinct from the observed lower-bound value. The immutable artifact SHA-256 is `66a85965cd271b22a8a91696e6506f7f99dda4186d54b59b3eb2d6ced42aab53`.

- Wilson lower bound `>= 0.90`: release E2B after Answer Contract checks.
- Lower bound `[0.80, 0.90)`: deterministic minimax-regret selection.
- Lower bound `[0.70, 0.80)`: one-call review only after Sprint 74 enables it.
- Lower bound `< 0.70`: direct Fireworks.

Evidence is scoped to the frozen v2 decision surface. A probability below the v2 eligibility threshold never inherits the `44/46` sentiment evidence.

## Ablation

On `1,242` protected or external-audit rows:

| Policy | Local | Correct | False local | Precision | Estimated Fireworks tokens |
|---|---:|---:|---:|---:|---:|
| Current v2 gate | 70 | 63 | 7 | 90.00% | 150,016 |
| Wilson 95 hard gate | 70 | 63 | 7 | 90.00% | 150,016 |
| Wilson 90 + Nash | 70 | 63 | 7 | 90.00% | 150,016 |
| Raw probability >= 0.70 | 79 | 67 | 12 | 84.81% | 148,864 |

The raw aggressive policy saves an estimated `1,152` Fireworks tokens but violates the accuracy-first constraint. It is rejected. Code-heavy and math-heavy distributions remain Fireworks-only. Review remains disabled until paired evidence proves both accuracy and token break-even.
