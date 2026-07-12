# Sprint 74 - Fireworks Verify-or-Repair And OOD Arena

## Timebox

`75 minutes` with a hard Fireworks development budget of `$6` and a `$20` reserve. Test a compact stratified arena and disable review for every stratum without clear token and accuracy evidence.

## Objective

Prove whether reviewing an E2B candidate costs fewer tracked tokens than asking Fireworks to answer directly, while preserving or improving final accuracy on unseen near-boundary prompts.

## One-Call Contract

- [x] Send the raw task and untrusted E2B candidate in a compact data envelope.
- [x] Request exactly one control outcome: `APPROVE` or `REPLACE` followed by the replacement answer.
- [x] Release the E2B candidate when approved.
- [x] Release the replacement answer when rejected.
- [x] Never perform a second Fireworks call after a valid rejection.
- [x] Keep the reviewer prompt injection-resistant and forbid chain-of-thought output.
- [x] Validate the control contract and final answer contract mechanically.
- [x] Fall back to direct Fireworks behavior on malformed reviewer output.

## Token Break-Even Arena

- [x] Compare direct answer versus verify-or-repair on the same task and Kimi model.
- [x] Record prompt, completion and total tokens separately.
- [x] Stratify by eight intents, candidate length and E2B correctness; the sampled set had no strict-format support.
- [x] Calculate approval, repair, false-approval, false-rejection and malformed rates.
- [x] Calculate review tokens including replacement-answer output.
- [x] Disable review for every category without sufficient positive break-even evidence.
- [x] Reject all observed savings strata because support was too small for a positive confidence interval.

## Fresh OOD Set

- [x] Reuse a compact lineage-separated sample of previously unseen E2B candidates instead of spending tokens on new generation.
- [x] Select immutable task IDs with two correct and two incorrect candidates per intent where execution completed.
- [x] Avoid generation calls entirely.
- [x] Blind judges to route, probability, cluster and model identity.
- [x] Apply the Answer Contract Engine mechanically before blind Fireworks judgment.
- [x] Log request IDs, usage and estimated cost without credentials.
- [x] Stop below the reduced `$6` ceiling after the global token gate failed; estimated spend was below `$0.06`.

## Promotion Gates

- [x] No false approval was observed among parseable reviewed candidates.
- [x] Observed review judgments were higher, but malformed outputs prevent an accuracy promotion claim.
- [x] Review failed token break-even globally and no stratum had sufficient positive support.
- [x] Arena models were restricted to the declared Track 1 allowed models.
- [x] A disabled, malformed or unavailable reviewer degrades to direct Fireworks, not synthetic success.

## Definition of Done

- [x] No review stratum passed both measured accuracy reliability and token benefit; the tier remains disabled.
- [x] All tasks bypass review and use direct Fireworks under the release policy.
