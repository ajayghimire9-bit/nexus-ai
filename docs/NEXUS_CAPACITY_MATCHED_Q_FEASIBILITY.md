# Capacity-matched first-action Q — offline feasibility

This is a design diagnostic. It used **zero** new real or imagined transitions. It is **not** the registered experiment, not a controller result, and not authorization to collect.

Branch `cursor/capacity-matched-first-action-value` from `a833a2c8f128a6c5edc76b28f411eba5afff0890`. Artifact `artifacts/capacity_matched_q_feasibility.json`.

## Feature lock

The Q feature map imports `terminal_value.polynomial_features` unchanged. On 11 observation/context coordinates that expansion has **77** columns. Three first-action indicators are concatenated, then an intercept is added: **81** coefficients. Sequence-value V remains the frozen 78-coefficient readout with its own mean/scale. Ridge λ=1.0 is prespecified; it was not chosen from source CV or development outcomes.

## Sample size and rank

Per decoder the stacked source design is 8 tasks × 6 contexts × 3 actions = **144 rows**, but only **24 distinct (task, action) labels**. Repeated context rows are the same continuation return and are not independent targets. Unique observations = 8; unique (observation, context) pairs = 48.

On both a synthetic 8×6×3 draw and decoder-0 historical source observations (closed source cells only; development returns unused):

| Probe | Unique labels | Feature rank | Augmented rank | Ridge Gram condition |
|---|---:|---:|---:|---:|
| Synthetic | 24 | 50 | 50 | 7.62 |
| Historical source, decoder 0 | 24 | 50 | 50 | 42.87 |

Unregularized 81-column maps are rank-deficient (action dummies sum to the intercept; at most ~50 independent columns). Ridge λ=1 makes the Gram matrix well-conditioned enough to solve. Overfitting risk remains high: 81 weights versus 24 unique labels.

## Additive action ranking

Because action enters only as three additive indicators, Q(s,z,a) − Q(s,z,a′) does not depend on (s,z). At a restored state the 16 candidates share (s,z), so this estimator cannot rank first actions differently across states. A fitted synthetic probe chose the same argmax action at three distinct (s,z). That is a locked property of the requested 81-coefficient class, not an extra interaction model.

## Authorization

Committed allocation: `authorized: false`, `runs: 0`. Remaining standing-session allowance is **47.766 s**, below the 150 s protocol cap. Collection is blocked. This audit does not create a new session budget.
