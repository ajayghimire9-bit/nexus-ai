# Cross-environment residual-aware context-code transfer — results (rung 4)

## Decision

**`xenv_residual_context_not_established`.** The predeclared primary — per-seed
mean control return over {128, 1024}, paired `xenv − scratch` — was
**−1.819 [−23.729, +20.091]** (student-t 95%, df 9, n = 10); the interval
includes 0, three of ten seeds positive. Per budget: @128
**+9.441 [−14.568, +33.449]** and @1024 **−13.079 [−50.543, +24.386]** —
both include 0. Prediction MAE intervals include 0 at both budgets.

Residual-aware FiLM on the closed rung-1 trunk did **not** establish
cross-environment transfer. Mean returns: @128 xenv −155.994 versus scratch
−165.435 and reference −116.985; @1024 xenv −79.183 versus scratch
−66.105 and reference −88.026. Parameter counts were identical (8,906).

This closes rung 4. Four consecutive cross-environment rungs are now
`not_established` (shared layer +18.618, deep trunk +2.575, occupancy-only
context −2.300, residual-aware context −1.819). The established adaptation
lever remains multitask pretraining across physics variants **within** a
family.

This is a valid negative result for this configuration only — not a
disproof of cross-environment adaptation in general, not learning-to-learn,
not AGI. No retune and no rerun on this sample; the target physics
(0.0019, 0.0013, 0.065) and this configuration are closed.

## Cost

**18.470 s wall** (600 s cap), **44,000 fresh real steps**, **3,072,000
imagined transitions** exactly, local CPU, one valid execution after
authorization commit `1f6acab` (no invalid attempts). Session ledger:
204.203 + 18.470 = 222.673 s of the standing 3600 s consumed; 3377.327 s
remain.

## Integrity

The independent Git-only results audit passed: saved label, 60-trace grid,
execution totals and forbidden-claim flags. Rule `mcc_xenv_v5` reproduced
**(0.0019, 0.0013, 0.065)**; seeds `66,000,000+` are disjoint from closed
blocks including rung 3.

## Provenance

Branch `cursor/xenv-residual-context`: lock `33d320a`, authorization
`1f6acab`, executed once with a clean tree. Raw artifact
`artifacts/xenv_residual_context.json` SHA256
`fe3885b47ab254082755fb76ae70b861ab9de8f998ba20d1e03ceab7dd818c30`.

## One next recommendation

Do **not** add another FiLM-width, pad, or support-length variant on this
shared-trunk recipe. Four matched-data rungs at this pretraining scale have
failed to establish transfer. A pretraining-scale test still exceeds the
100,000 standing interaction cap. The next bounded step is a new locked
protocol, not a retune: either stop this xenv-sharing line at this scale, or
obtain separate authorization for a reduced-grid scale screen. Nothing here
pre-authorizes either.
