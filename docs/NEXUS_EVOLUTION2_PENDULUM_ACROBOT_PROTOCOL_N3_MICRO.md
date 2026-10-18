# Evolution-2.5 — explicit n=3 no-fit micro (NOT v2)

Branch `cursor/evolution2.5-n3-micro` from
`5a3867b403d642325a86325b9d0777aa45b77f36`.
Status: **NOT_V2 — NOT_READY — COLLECTION UNAUTHORIZED**.
Does **not** rewrite v2 or v2-pilot.

This lock exists so a three-file residual inventory cannot silently
inherit the n=10 / df=9 v2 gate. It is not a scientific screen.

No collection. No named holdout. H17 blocked. Ledger
**305.842 / 3294.158**.

## 1. Why this is not v2

| Item | v2 / v2-pilot | n=3 micro |
|---|---|---|
| Independent bundles | 10 | **3** |
| Student-t df | 9 | **2** |
| Bonferroni t crit (0.05/5) | 3.250 | **9.925** |
| Residual recipe | one matched fit | **unmatched** |
| Pendulum files | unmeasured fits | 3 context-opt `mlp_u1000` |
| Acrobot files | unmeasured fits | 3 historical lookahead seeds |
| Real steps | 97,600 / 57,600 | **9,600** |
| Imagined upper bound | 110,592,000 / 49,152,000 | **14,745,600** |

A later claim that persist beat reset on n=10, or that these six
files are one residual recipe, is unsupported.

## 2. Bound files

Pendulum `seed{0,1,2}_mlp_u1000.pt` and Acrobot
`acrobot_lookahead_h16/seed{0,1,2}.pt`, hashes from
`evolution2.nofit_inventory`. Confirmation weights stay excluded.

## 3. Worksheet

```
revealed    = 3 * 6 * 2 * 200 = 7,200
development = 3 * 2 * 2 * 200 = 2,400
real total  = 9,600
imagined    = 9,600 * 1,536   = 14,745,600
planning    ≈ 102 s conservative
fitting     = 0 (no-fit; SOURCE_FITTING_UNAVAILABLE)
```

Wall-clock is more plausible than v2. Science is not. `recipe_matched`
is false, holdout unnamed, `authorized: false`, `runs: 0`. This
document authorizes **0 s and 0 steps**.

## 4. Gate

Same five controls and practical margin 0.05. Intervals use
**df=2** Bonferroni t = 9.924843200918293. Ordinary 95% exploratory
t = 4.302652729749464 is recorded and is not the primary gate.
n=3 results cannot be reanalyzed with the v2 df=9 constant.

Outcomes: `transfer_screen_passed`, `development_screen_failed`,
`inconclusive`, `negative_transfer`, `incomplete_budget`,
`invalid_integrity`, `invalid_leakage`, `not_ready_recipe_mismatch`.

## 5. What this lock does not do

- No Gymnasium construction, training, or env steps.
- No rewrite of v2 or v2-pilot hashes, n, or Bonferroni df=9.
- No H17 unlock and no named unused instance.
- No claim that unmatched residuals answer the v2 question.
