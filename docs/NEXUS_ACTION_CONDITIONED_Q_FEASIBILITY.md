# Action-conditioned first-action Q — offline feasibility

This is a design diagnostic. It used **zero** new real or imagined transitions and **no** closed development returns. It is not the registered experiment and not authorization to collect.

Branch `cursor/action-conditioned-first-action-q` from `6ecb09c37e00168b911f8d2ae62612147e3654e8`. The 81-coefficient additive protocol was not modified. Artifact `artifacts/action_conditioned_q_feasibility.json`.

## Why additive capacity matching is not an adequate Q

Synthetic data where the best first action flips with the sign of angular position: the 7-coefficient additive model kept a constant preferred action `[1, 1]`. The 16-coefficient action×observation model switched `[0, 1]`. Parameter count matching without action-conditioned features cannot represent state-dependent first-action value.

## Unique labels versus repeated contexts

Historical source cells provide **24 unique (task, action) labels per decoder**, not 144 independent rows. Repeated scoring contexts copy the same continuation return. Proposed collection: **two resets per source task → 48 unique labels per decoder**. Action×context is not identified: targets do not vary with scoring z.

On decoder-0 historical unique rows, `action_obs` has feature rank **12** of 15, 16 weights, ridge-0.1 Gram condition **25.46**.

## Source-only leave-one-task-out (10 decoders, 8 held-out source tasks)

| Family | λ | Action ID | RMSE | Weights | Eligible selector? |
|---|---:|---:|---:|---:|---|
| additive | 0.1 | 0.312 | 77.94 | 7 | no (state-independent) |
| additive | 1.0 | 0.312 | 95.42 | 7 | no |
| additive | 10.0 | 0.312 | 140.16 | 7 | no |
| **action_obs** | **0.1** | **0.463** | **83.35** | **16** | **yes, selected** |
| action_obs | 1.0 | 0.412 | 81.17 | 16 | yes |
| action_obs | 10.0 | 0.362 | 131.87 | 16 | yes |
| action_obs_z | 0.1 | 0.463 | 63.86 | 24 | yes, same ID, extra z |
| action_obs_z | 1.0 | 0.412 | 87.96 | 24 | yes |
| action_obs_action_z | 0.1 | 0.425 | 66.45 | 48 | yes, worse ID |

Chance identification among three actions is 1/3. Additive is at chance. Action×observation at λ=0.1 reaches 0.463. Adding z main effects does not raise identification; the RMSE drop is not treated as justification for unidentified action×context terms. Compactness therefore locks **`action_obs`, λ=0.1**.

Eight unique source observations remain a weak sample. That is why the registered experiment collects two new states per source task rather than restacking contexts.

## Authorization

Committed allocation: `authorized: false`, `runs: 0`. Remaining standing-session allowance is **47.766 s**, below the 240 s protocol cap. Collection is blocked.
