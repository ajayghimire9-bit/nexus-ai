# Evolution-2.29 — prospective return-scoring contract

Engineering protocol, 2026-10-19. Base verified against GitHub:
`541ddd85f0fa76208bbbcfe2f8d5a865c46208d9`. Branch
`codex/evolution2.29-return-scoring-contract`. Source-only scope; no scientific
execution, neural training/inference, environments, holdout registration or
allocation. Preserve unrelated untracked E1 adapter files and all old results.

## What changes, and what does not

Extend `persist_reset_scoring`, reusing `TrustedEvaluator`, its immutable
`FrozenTrainingFeedbackScale`, `prospective_hidden_evaluator`, existing v2
ten-bundle statistics and E1 `ReservationLedger`. Do not replace
`AdaptiveProposer`, `ContextualStrategyMemory`, the method registry or any meter.
Historical runners, consumed grants and analysis functions remain unchanged.

`freeze_shared_reference` requires the four comparison methods to have exactly
the same predeclared two-anchor exposure before adaptive proposals. Collect
anchor receipts once, expose equally through the existing cache, freeze the
same scale for every method, and never refit on query outcomes. The source-only
fixture authors these anchors; a future study must establish their actual
training-only provenance and include their cost in its resource plan.

`analyze_return_grid` requires expected IDs from a future committed protocol,
not the results: exactly ten unique bundle IDs, both families, two unique slots,
and persist/reset/random/evolution. Missing entire scopes, duplicate cells,
boolean IDs, string/nonfinite metrics, mixed feedback snapshots and incomplete
resource reports fail closed. Paired methods share an episode ID; two slots
cannot be relabeled copies of the same episode. Recorded physical origins,
cache hits, raw rewards and completed environment work must reconcile.

## Measurement and statistics

Primary measurement inputs are raw environment returns, not
`max(decision.scores)`. A schema label alone cannot authenticate this distinction:
the future trusted worker must measure actual rewards. The current capture
uses **authored numbers**, explicitly not real-return research evidence.

Average slots within each family/bundle. Compute persist-minus-control raw
differences separately for each family. Divide by fixed positive family spans
provided externally by a future protocol, then average families equally inside
each bundle. Do not pool incomparable raw family reward scales. Intervals use
ten independent bundles, df=9, through the existing v2 Student-t helper. Retain
the existing conservative five-comparison Bonferroni critical value for the
three reported contrasts; no significance/promotion decision is implemented.
Practical threshold is deliberately unset. Fixed spans, metrics, multiplicity,
threshold and distribution must be scientifically registered before real use.
The illustrative fixture uses span100 for both families; it does not register
a scientifically justified reward range.

Clipped source-scale unit scores remain diagnostics. Validate them against the
same immutable scale, preserve raw returns, and count clipping per logical
method opportunity, including cached receipts. Equal clipped scores cannot
erase a raw-return difference in this analysis. Neither cached results nor slots
are new independent model-training replications.

## Interrupted work and authority boundary

Use existing `Operation`, `Work`, `Clock`, `Limits` and `ReservationLedger`;
there is no additional meter. Reserve each environment step/model call before
dispatch, settle completed work, and retain unknown upper reservations when
interrupted. Synthetic tests demonstrate that a completed step followed by a
pending step preserves both completed and unknown work. Non-complete ledger
reports cannot enter complete-grid inference. Physical completed step totals
must equal unique physical episode receipts; cache receipts do not spend
physical environment steps again.

This is a sequential trusted-host metadata contract, **not** an OS resource
enforcer, authorization or secure sandbox. It does not authenticate arbitrary
fabricated reports or independently verify a worker's timing/episode lineage.
Full runtime integration still needs pre-call reservation, trusted clocks,
parent/child accounting and real reward receipts. No scientific dispatcher is
enabled. Twenty matched fit hashes, timing evidence, fresh exclusion-checked
roles, seeds, prospective study registration and allocation remain absent.
E2.17 remains inconclusive/consumed; H17 remains blocked.

## Deterministic capture and tests, declared before capture

Commit implementation/tests and this protocol first. Run the authored integration
with a ten-second cap: ten fixture bundles, two families, two slots, four methods.
The existing manifest factory supplies scores from authored callbacks, never
from a world/model. Persist/random share one selected variant; reset/evolution
share the other. Source endpoints are0/10; query values are0 and10+bundle index.
Thus there are160 logical query receipts,80 physical synthetic callbacks,
40 source callbacks and no model/proposer updates. Source/query IDs and clocks
are synthetic data, not new scientific seed registrations. The ledger's80
one-step reservations are **simulated metadata**, not executed interactions.
These forced choices are not baseline winners or learned proposal behavior.

Test exact paired interval arithmetic; whole missing bundle/family/slot/method
rejection; invalid types/nonfinite values; snapshot equality; pairing; cache
origins; clipping versus raw differences; fixed family weighting; interruption
settlement; and complete-work reconciliation. Historical E2.28 provenance tests
must verify the recorded execution revision rather than demand that current
source never evolve; historical bytes/results remain unchanged.

Capture source hashes, code revision, raw receipts, manifests, costs and previous
JSON hashes separately in `artifacts/evolution2_29_return_contract.json`.
Do not overwrite a prior capture. Run focused and relevant source-only regression
tests; avoid historical artifact writers and model/planner suites. Scientific
ledger remains **327.869 used /3272.131 remaining**.

## Next scientific prerequisite

One next milestone is a source-only trusted-worker integration review: map each
selected variant to a real-reward receipt and every planner/environment operation
to pre-call reservation, while leaving dispatch disabled. This must verify the
boundaries and identify whether existing runtime code can meet them; it must
not open another evaluator stack or collect new outcomes. This branch establishes
receipt-contract correctness only, not improved learning/control or AGI.
