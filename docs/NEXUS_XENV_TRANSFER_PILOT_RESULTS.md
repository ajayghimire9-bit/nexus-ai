# Cross-environment shared-trunk transfer pilot — results

## Decision

**`xenv_shared_layer_not_established`.** The predeclared primary — per-seed
mean control return over the budgets {128, 1024}, paired
`xenv − scratch` — was **+18.618 [−20.400, +57.636]** (student-t 95%, df 9,
n = 10); the interval includes 0. Seven of ten seeds were positive. Per
budget: @128 **+24.548 [−20.310, +69.406]** and @1024
**+12.687 [−29.216, +54.591]** — both include 0. Held-out target prediction
MAE was essentially unchanged (+5.3e-05 [−5.2e-05, +1.6e-04] @128;
−1.5e-05 [−5.3e-05, +2.3e-05] @1024).

The minimal-sharing configuration — one shared 64→64 tanh layer pretrained
jointly on CartPole, Acrobot and discrete MountainCar, with per-family
input/output heads — did **not** establish a cross-environment adaptation
advantage over the identical architecture trained on the target only, at
matched target data, on the new unused MountainCarContinuous physics
(0.0025, 0.0015, 0.09). This is a valid inconclusive result for **this
configuration only**: not a disproof of cross-environment adaptation in
general, not learning-to-learn, not AGI. No retune and no rerun on this
sample; the target physics and this configuration are closed.

Anchoring (secondary): the reference established single-family `WorldModel`
pipeline reached −122.906 @128 and −80.254 @1024; the multi-head scratch arm
reached −173.508 @128 and −77.514 @1024, so the multi-head wrapper is roughly
at parity with the established pipeline at the large budget and the shared
layer's pretraining is the open variable, not the wrapper.

## Cost

Valid execution: **16.096 s wall** (600 s cap), **44,000 fresh real steps**
(19,200 prior-family collection + 12,800 target pool + 12,000 evaluation),
**3,072,000 imagined transitions** exactly (12,000 × 256), 10 training-epoch
budgets per seed inside the frozen pilot recipe, local CPU, one execution
after commit `253b8ac`.

**Invalid attempt 1, disclosed honestly:** the first execution after
authorization commit `6053272` stopped at 9/10 seeds when an instrumentation
accounting bug counted evaluation-only model calls as imagined transitions
(3,072,016 of the 3,072,000 cap). Label `incomplete`; no scientific outcome
was observed or used; it consumed 43,967 real steps and 3,072,016 imagined
transitions and is preserved as
`artifacts/xenv_transfer_pilot_incomplete_attempt1.json`. The accounting was
fixed (rollout-scoped instrumentation, regression-tested), committed, and the
identical locked configuration was executed once more. Combined new real
interactions: 43,967 + 44,000 = **87,967 < 100,000** per-experiment standing
cap.

## Integrity

The independent Git-only results audit passed: saved label, per-trace reward
reconstruction and return identities, the 60-trace grid, execution totals and
the forbidden-claim flags. The allocation binds config SHA256 `531bfe1a…` and
protocol SHA256 `4e309b4f…`; the rule `mcc_xenv_v1` reproduced the target
physics exactly and the target is disjoint from every occupied
MountainCarContinuous physics; seeds (63,000,000+ block) are disjoint from all
closed registries and the other live branches' blocks. Session ledger:
167.823 s of the standing 3600 s consumed; 3432.177 s remain.

## Provenance

Branch `cline/xenv-transfer-pilot`: lock `6cdbbaf` (protocol + implementation
+ tests + unauthorized allocation), authorization `6053272`, accounting fix
`253b8ac` (with preserved invalid attempt), executed once after it. Raw
artifact `artifacts/xenv_transfer_pilot.json` SHA256
`f6bf1a96a4fd78792eb9a0b43cf0d3677a415dc0134ebf49a8935223c8800c70`.

## One next recommendation

The established positive lever remains **multitask pretraining across
physics variants within a family**; the minimal cross-family rung (one shared
layer) is not established. The next rung, as a **new preregistered
configuration** (not a retune of this one): deepen the sharing — share the
full two-layer trunk behind per-family input projections, or introduce a
learned cross-family context code — with the same matched-data scratch
control and fairness gates. Each needs its own locked protocol, cost estimate
and one-run allocation. Nothing here pre-authorizes it.
