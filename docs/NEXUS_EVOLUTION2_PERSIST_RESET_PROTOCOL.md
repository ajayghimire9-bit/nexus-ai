# Evolution-2 persist-versus-reset — implementation-ready protocol

Status: **DESIGNED, NOT AUTHORIZED**. `continue` is not approval.
Does not name a holdout. Does not grant 7,680. Does not collect.

Cited request hash
`8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e`.
H17 blocked. H16 ledger **305.842 / 3294.158**.

## 1. Question

On n=3 independent new-physics bundles, does persist beat reset on
hidden development by more than the locked practical margin, against
equal-budget random and evolution?

Primary: persist minus reset. Bonferroni t = **9.924843** (df=2, five
comparisons). Intentionally low-power. Not n=10 confirmation.

## 2. Required approval text

A later human reply must include all three:

1. Config hash `8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e`
2. A named unused four-role holdout matching the locked digests.
   Occupied defaults `(10,1,1)` and `(1,1,1)` are not that holdout.
3. `env_cap=17280`

Any other cap, especially `7680` or `9600`, is refused.

## 3. Locked budget

| Item | Amount |
|---|---:|
| Fresh source | 7,680 |
| Revealed | 7,200 |
| Hidden development | 2,400 |
| Fresh total real steps | **17,280** |
| Imagined upper bound | **14,745,600** |
| Residual fits | 6 |
| Authorized now | 0 |

Development priors, not new-physics clocks: default persist 0.156 s;
six default fits 1.215 s; 24 `decide()` 0.068 s; receding stored-obs
clock recorded separately. Env-rollout wall time remains unknown.

## 4. Execution stages after approval

Reuse only: `collect_transitions`, `train_world_model` residual 64×64,
`planner_adapter.decide`, `TrustedEvaluator.hide_development`,
`ReservationLedger`, `evolution2.methods`, `v2.bundle_family_order`,
`v2.paired_bundle_seeds`.

Until the three approval fields are present, every stage refuses.

## 5. What this protocol does not do

- Name a holdout
- Grant 7,680
- Unlock H17
- Start Evolution-3
- Treat development clocks as scientific results
