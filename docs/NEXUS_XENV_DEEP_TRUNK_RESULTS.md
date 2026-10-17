# Cross-environment deep shared-trunk transfer — results (rung 2)

## Decision

**`xenv_deep_trunk_not_established`.** The predeclared primary — per-seed mean
control return over the budgets {128, 1024}, paired `xenv − scratch` — was
**+2.575 [−16.248, +21.399]** (student-t 95%, df 9, n = 10); the interval
includes 0, five of ten seeds positive. Per budget: @128
**+1.273 [−19.925, +22.471]** and @1024 **+3.878 [−38.175, +45.931]** — both
include 0. Held-out prediction MAE gain was +1.99e-04 [3.2e-05, 3.65e-04]
@128 (a marginal, decision-irrelevant prediction improvement) and
+1.8e-05 [−1.9e-05, +5.6e-05] @1024.

Deepening the sharing did **not** establish cross-environment transfer, and
the point estimate shrank versus rung 1 (+18.618 → +2.575). The deeper
multi-head architecture also underperformed the established single-family
reference pipeline at the large budget (xenv −101.715, scratch −105.593,
reference −84.026 @1024), unlike rung 1 where the multi-head wrapper matched
it. This closes rung 2's configuration. Two consecutive rungs of naive weight
sharing across these heterogeneous families (CartPole, Acrobot, discrete
MountainCar → MountainCarContinuous) have now failed to establish transfer at
these pretraining scales; the established adaptation lever remains multitask
pretraining across physics variants **within** a family.

This is a valid negative result for this configuration only — not a disproof
of cross-environment adaptation in general, not learning-to-learn, not AGI.
No retune and no rerun on this sample; the target physics
(0.0028, 0.0013, 0.065) and this configuration are closed.

## Cost

**17.864 s wall** (600 s cap), **44,000 fresh real steps** (19,200 prior
collection + 12,800 target pool + 12,000 evaluation), **3,072,000 imagined
transitions** exactly, 10 training-epoch budgets per seed inside the frozen
recipe, local CPU, one valid execution after authorization commit `0ac96a1`
(no invalid attempts this rung). Session ledger: 167.823 + 17.864 = 185.687 s
of the standing 3600 s consumed; 3414.313 s remain.

## Integrity

The independent Git-only results audit passed: saved label, per-trace reward
reconstruction and return identities, the 60-trace grid, execution totals and
the forbidden-claim flags. The allocation binds config SHA256 `170a5e58…` and
protocol SHA256 `720acb2c…`; the rule `mcc_xenv_v2` reproduced the target
physics exactly, disjoint from every occupied MountainCarContinuous physics
including rung 1's target; seeds (63,500,000+ blocks) are disjoint from all
closed registries, rung 1's blocks and the other live branches' blocks.

## Provenance

Branch `cline/xenv-deep-trunk`: lock `b189fde` (protocol + `XEnvDeepNet`
implementation + tests + unauthorized allocation), authorization `0ac96a1`
(citing the standing grant and the user's explicit full-authorization
instructions), executed once after it with a clean tree. Raw artifact
`artifacts/xenv_deep_trunk.json` SHA256
`5bbf342712498872a406171b8536a1155c74c25d4cd42ec297a270c3e8c90d55`.

## One next recommendation

Two consecutive weight-sharing rungs are now closed. The evidence points
away from naive trunk sharing across heterogeneous families at these scales:
the next preregistered decision is either (a) a **pretraining-scale rung**
(e.g., 5× prior data per family, everything else frozen) to test whether the
mechanism is starved rather than wrong, or (b) a **mechanism change** (a
learned cross-family context code, connecting to the established
within-family context line) — not another trunk-depth variant. Each requires
its own locked protocol, cost estimate and one-run allocation; nothing here
pre-authorizes either.
