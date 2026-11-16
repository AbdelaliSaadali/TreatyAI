# TreatyBench Methodology

## Purpose

TreatyBench is a small deterministic benchmark that demonstrates why independent per-action checks can fail when several agents share customer-level resources.

It is a regression suite for the current encoded rules, not an industry benchmark and not evidence of production effectiveness.

## Dataset generation

The current run generates 30 synthetic cases from a fixed deterministic pattern.

Each case contains:

- One customer with a compensation allowance selected from 80, 100, 120, 150, 180, 220 or 300 MAD.
- Two agents proposing 100 MAD credits.
- A marketing proposal.
- A retention callback proposal.
- A customer consent flag that varies by case.
- An open-critical-case flag that varies by case.
- A customer-wide outbound contact limit of one action in the 24-hour window.

No real customer records or personally identifiable information are used.

## Compared systems

### Baseline: independent per-action approval

Each proposal is evaluated against the same initial customer snapshot. A credit is locally eligible if its amount is within the customer's initial remaining allowance and the agent's delegated amount limit. Marketing is locally eligible if consent is active and no critical case is open. A callback is locally eligible if the customer has an available contact slot.

The baseline does not aggregate accepted proposals before approving them. Therefore, two 100 MAD credits can each pass a 150 MAD snapshot check and then collectively exceed the allowance. Two outbound actions can each see one available contact slot and collectively exceed the shared quota.

### TreatyAI

The same proposals are evaluated together. TreatyAI:

1. Applies delegated scopes and customer-level policy.
2. Constructs the conflict graph.
3. Searches full and permitted partial credit variants.
4. Enforces the shared compensation and outbound-contact limits.
5. Independently verifies the selected plan.
6. Uses the transactional commit boundary in the live concurrency test.

## Metrics

- **Invariant violation:** a case where the combined baseline plan exceeds the shared compensation budget or outbound contact limit, or where TreatyAI's independent verifier fails.
- **Budget violation:** combined selected compensation exceeds the customer's remaining allowance.
- **Contact violation:** combined outbound actions exceed the customer-wide contact capacity.
- **Safe completion:** at least one action is approved or adjusted in the TreatyAI plan. This is intentionally a narrow proxy; it is not a complete business-task success metric.
- **Violation rate:** cases with at least one invariant violation divided by total cases.

## Observed local run

The latest generated 30-case run on this workstation reported:

| Metric | Independent baseline | TreatyAI |
|---|---:|---:|
| Cases with any invariant violation | 23 / 30 (76.7%) | 0 / 30 (0%) |
| Global budget violations | 17 / 30 | 0 / 30 |
| Contact-limit violations | 15 / 30 | 0 / 30 |
| Safe completion | Not measured as a baseline equivalent | 100% |

Budget and contact violation counts overlap; they must not be added to calculate the total number of violating cases.

## Interpretation and limitations

- The baseline is deliberately a per-action architecture with no global aggregation. It is not a comparison against a fully featured Agentforce deployment or a mature commercial policy engine.
- The test generator and policy implementation are authored together. This creates a risk of benchmark overfitting.
- The cases are synthetic and small.
- The safe-completion metric only checks whether at least one action was approved or adjusted.
- The current optimizer uses bounded beam search; no global optimality guarantee is claimed.
- A zero TreatyAI violation count means the implementation satisfied the invariants encoded in these 30 generated cases. It does not prove safety for arbitrary enterprise workloads.

## Next evaluation steps for the PFE

1. Freeze a benchmark specification before changing the engine.
2. Add held-out cases authored independently from the optimizer.
3. Add mutation testing for policies and verifier checks.
4. Add randomized concurrency schedules and retry/failure injection.
5. Compare with a stronger baseline that performs per-action authorization and a separate shared-resource lock.
6. Measure latency, false blocking, safe task completion, escalation rate and optimizer quality.
7. Compare beam search with CP-SAT/SMT formulations.
8. Publish raw case fixtures, expected outcomes and reproducible run metadata.
