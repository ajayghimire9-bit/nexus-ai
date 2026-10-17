# Cross-environment support-inferred context-code transfer — results (rung 3)

## Decision

**`xenv_context_code_not_established`.** The predeclared primary — per-seed
mean control return over the budgets {128, 1024}, paired `xenv − scratch` —
was **−2.300 [−9.921, +5.320]** (student-t 95%, df 9, n = 10); the interval
includes 0, five of ten seeds positive. Per budget: @128
**−2.584 [−12.645, +7.476]** and @1024 **−2.016 [−9.997, +5.965]** — both
include 0. Held-out prediction MAE gain (xenv − scratch) was
−6.52e-05 [−1.31e-04, +9.19e-07] @128 and
+9.03e-06 [−3.38e-05, +5.19e-05] @1024; both intervals include 0.

Occupancy-conditioned FiLM on the closed rung-1 trunk did **not** establish
cross-environment transfer. Mean returns: @128 xenv −187.914 versus scratch
−185.329 and reference −178.263; @1024 xenv −151.563 versus scratch
−149.547 and reference −116.354. The multi-head wrapper again trails the
single-family residual reference at the large budget. Parameter counts were
identical (8,858).

This closes rung 3's occupancy-only `(obs, action)` configuration. Three
consecutive cross-environment rungs are now closed
`not_established` (shared layer +18.618, deep trunk +2.575, context-code
−2.300). The established adaptation lever remains multitask pretraining
across physics variants **within** a family.

The source audit's interpretation limits apply: this result does **not**
test residual / `T(s'|s,a)` inference. Secondary
`nearest_source_ratio` mean 0.612 is reported only; it was computed after
fine-tune and is not the frozen `z` that conditioned control. It is not
label-deciding.

This is a valid negative result for this configuration only — not a
disproof of cross-environment adaptation in general, not learning-to-learn,
not AGI. No retune and no rerun on this sample; the target physics
(0.0027, 0.0009, 0.05) and this configuration are closed.

## Cost

**18.516 s wall** (600 s cap), **44,000 fresh real steps** (19,200 prior
collection + 12,800 target pool + 12,000 evaluation), **3,072,000 imagined
transitions** exactly, 135 locked epoch-loops per seed inside the frozen
recipe, local CPU, one valid execution after authorization commit `c0d5013`
(no invalid attempts). Session ledger: 185.687 + 18.516 = 204.203 s of the
standing 3600 s consumed; 3395.797 s remain.

## Integrity

The independent Git-only results audit passed: saved label, per-trace reward
reconstruction and return identities, the 60-trace grid, execution totals,
context dimension and the forbidden-claim flags. The allocation binds
config SHA256 `8a64693a…` and protocol SHA256 `34e9b869…`; the rule
`mcc_xenv_v4` reproduced the target physics exactly, disjoint from every
occupied MountainCarContinuous physics including rungs 1–2 and the Cline
v3 draft; seeds (65,000,000+ blocks) are disjoint from all closed
registries and the other live branches' blocks.

## Provenance

Branch `cursor/xenv-context-code`: lock `b4db637`, source audit `751b4ec`,
authorization `c0d5013` (citing the standing grant and the user's
2026-10-17 explicit continue authorization), executed once after it with a
clean tree. Raw artifact `artifacts/xenv_context_code.json` SHA256
`e621ba941c084a743df68e7c4e29ccb9c87f4960b863087737c780f2ef087352`.

## One next recommendation

Occupancy-only context-code is closed. Do not retune FiLM width, support
length, or this holdout. The source audit already named the untested
mechanism: a **residual-aware** support encoder that may read `(s, a, s'−s)`
from the same support slice, still with no family-ID table, matched scratch,
and a new unused physics draw. Pretraining-scale still exceeds the 100,000
standing interaction cap. Each requires its own locked protocol, cost
estimate and one-run allocation; nothing here pre-authorizes either.
