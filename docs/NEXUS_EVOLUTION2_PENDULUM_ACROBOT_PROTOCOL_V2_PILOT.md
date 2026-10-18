# Evolution-2 Pendulum↔Acrobot catalogue-proposer protocol v2-pilot

Status: **PROSPECTIVE DESIGN — COLLECTION UNAUTHORIZED**.
Does **not** rewrite v2. v2 remains the scientific target:
`docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2.md`.
Parent: `e0eaa59c8aa7b76a706301a8865f0a43a1751f14`.

This lock exists because historical residual-MLP planning rates
extrapolate to **611.5 s** for the full v2 imagined bound, so a 900 s
standing grant is likely `incomplete_budget` before source fitting.

No collection. No named holdout. H17 blocked. Ledger
**305.842 / 3294.158**.

## 1. What stays identical to v2

- Question: persist versus random, reset, evolution, fixed H=16 flat,
  and fixed H=16 successor on Pendulum/Acrobot.
- n = 10 independent search/model-bundles, paired methods.
- Bonferroni familywise 95% against all five controls; practical
  margin 0.05 of a predeclared analytic range.
- Population-4 / tournament-2 evolution; no crossover.
- Occupied physics exclusion; default `(10,1,1)` and `(1,1,1)` are
  not new sources.
- Holdout unnamed. `authorized: false`, `runs: 0`.

## 2. What is reduced, and why that is weaker

| Item | v2 | v2-pilot |
|---|---|---|
| Catalogue variants evaluated | 12 cached matrix | **6 revealed rows only** |
| Development conditions | 6 | **2** |
| Real steps | 97,600 | **57,600** |
| Imagined upper bound | 110,592,000 | **49,152,000** |
| Historical planning extrapolation | 611.5 s | **271.8 s** |

Unused catalogue variants are never scored. A later claim that
persist beat the full 12-variant library would be unsupported.
Two development conditions are a thinner transfer screen than six.
This is a **pilot**, not a silent v2 pass.

## 3. Worksheet

```
source     = 10 * 2 * (1024 + 256) = 25,600
revealed   = 10 * 6 * 2 * 200      = 24,000
development= 10 * 2 * 2 * 200      =  8,000
real total = 57,600
imagined   = (24,000 + 8,000) * 1,536 = 49,152,000
```

Standing grant: 900 s / 100,000 real. Interactions fit. Wall-clock
is more plausible than full v2 but still unproven: source fitting of
20 models is not measured here. A future run may still be
`incomplete_budget`. This document authorizes **0 s and 0 steps**.

## 4. Outcomes and labels

Same as v2: `transfer_screen_passed`, `development_screen_failed`,
`inconclusive`, `negative_transfer`, `incomplete_budget`,
`invalid_integrity`, `invalid_leakage`.

A complete nonsignificant pilot is `inconclusive`. It does not
authorize retuning v2 or naming a holdout.

## 5. What this lock does not do

- No Gymnasium construction, training, or env steps.
- No rewrite of v2 hashes, n, Bonferroni rule, or practical margin.
- No H17 unlock and no named unused instance.
- No claim that the fake-model adapter or synthetic E2 screen
  answers this question.
