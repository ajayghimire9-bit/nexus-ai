# Evolution-2.11 — persist-versus-reset authorization request

Branch `cursor/evolution2.11-persist-reset-request` from
`ea1b7421817fc9c33eed11b9142ca2e05cd04031`.
Status: **REQUEST ONLY — SCIENCE UNAUTHORIZED**.
Does **not** rewrite v2, v2-pilot, or n=3. Does **not** collect.
Does **not** name a holdout. `continue` is not approval.

This lock exists so a later human approval can bind one config hash,
one named unused holdout, and one step budget. It is not a scientific
result.

No collection. No new fits. H17 blocked. H16 ledger
**305.842 / 3294.158**.

## 1. What would be tested later

Primary contrast: **persist minus reset** on n=3 independent bundles
(df=2). Equal-budget controls: random and evolution. Reuse
`evolution2.methods` (`persistent_adaptive`, `reset_adaptive`,
`random`, `evolutionary`). Bonferroni t crit is the n=3 df=2 value
9.924843200918293. Do not inherit the v2 df=9 gate.

The six-fit clock (1.215 s, n_fits=6) is a **cost prior only**.
Twenty-fit / n=10 cost remains unmeasured. Occupied family defaults
`(10,1,1)` and `(1,1,1)` are not a new holdout. Disposable E2.9
weights are not confirmation residuals. Development and confirmation
must stay distinct.

## 2. What this lock authorizes

**0 s and 0 steps.** `authorized: false`, `env_cap: 0`,
`hold_named: false`. The standing grant does not start this screen.
A later approval must cite this configuration hash, name a holdout
that matches the locked four-role digests, and set `env_cap`.

## 3. What this lock does not do

- No Gymnasium, `collect_transitions`, or holdout evaluation.
- No persist of a physics tuple.
- No rewrite of v2, v2-pilot, n=3, persist, or fit-clock hashes.
- No H17 unlock and no Evolution-3.
