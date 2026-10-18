# Evolution-2.12 — Independent scientific-runner and resource-readiness audit

Audits commit
`9428e18345a44870838f9cefc6c144f549f7af35`
on `cursor/evolution2.12-persist-reset-dry-run`.
Status: **PRE-AUTHORIZATION — SCIENCE BLOCKED**.
Does **not** collect, fit, name a holdout, debit the ledger, or start
Evolution-3. Locked E2.11 hashes are unchanged.

H17 blocked. H16 ledger **305.842 / 3294.158**.

## Pre-authorization report

| Gate | Verdict |
|---|---|
| GitHub provenance | **VERIFIED** |
| Development dry-run | **PASS** |
| Real planner integration | **PASS** |
| Real source-fitting path | **BLOCKED** |
| Exact total environment-step requirement | **17,280 fresh steps** |
| CPU/wall-time estimate | measured and unknown separated below |
| Holdout integrity | **BLOCKED** |
| Scientific execution readiness | **BLOCKED** |
| One next necessary action | Cite `8e90b74a`, name a four-role unused holdout, and set `env_cap=17280` for new physics. `continue` is not approval. |

## 1. GitHub provenance — VERIFIED

Remote
`https://github.com/ajayghimire9-bit/nexus-ai/commit/9428e18345a44870838f9cefc6c144f549f7af35`
matches local HEAD at push time. Branch ancestry:
`8404151` (E2.11 request) → `9428e18` (E2.12 dry-run). Fifteen files
changed; untracked Evolution-1 adapters were not included. Locked
request hashes still match:

- config `8e90b74ad3f406509051025160799c13d9a28bbb7e16c11a77808653bb43827e`
- protocol `2c0d54cfd61215dddcda2e21fc71b36856b1871b5ba4f8817daecceb609174c9`
- allocation `ecb6b8c69932d8fe2bfc4c29870e9cf0ee4474a048338898c258d3689879da8f`

`authorized: false`, `env_cap: 0`, `hold_named: false`.

## 2. Development dry-run — PASS

Independent re-run of `run_development_dry_run(seed=7)`:

- All four methods exercised: persist, reset, random, evolution.
- Persist retained cross-task weights (12 updates; weights changed across
  the three train families; freeze held through development).
- Reset discarded state (`updates=0`, zero weights after each
  `reset_task`).
- Equal budget: 16 proposal slots per method, identical
  `TrainingFeedback`, shared anchors, matched development `eval_clone`.
- Development scores did not enter persistent training weights.
- Holdout family was not consumed. Scientific execution stayed BLOCKED.

## 3. Environment-step reconciliation — 17,280 fresh

| Worksheet | Steps | What it is |
|---|---:|---|
| E2.8 occupied-default persist | 7,680 | 3×2×(1024+256) on family defaults `(10,1,1)` / `(1,1,1)` |
| n=3 revealed + development | 9,600 | 7,200 revealed + 2,400 hidden development |
| **Fresh new-physics total** | **17,280** | 7,680 **new** source + 9,600 screen |

Those operations do not share steps. Fitting residuals needs source
transitions; proposer feedback needs revealed controller episodes;
hidden development needs unused evaluation episodes.

The existing 7,680 arrays **cannot** be credited. They are occupied
defaults, not a named unused holdout, and the E2.8 persist grant does
not authorize this screen. A 7,680 `env_cap` would reuse that grant. A
9,600 `env_cap` would omit matched fresh residuals. A 25,600 cap is the
v2 n=10 source worksheet, not this request.

Confirmation and n=10 are additional and unauthorized.

## 4. Real planner integration — PASS

All 12 catalogue variants bind through `bind_evaluation` on both
Pendulum and Acrobot (24 rows). The existing trusted dry-run scores
locked default-family observations with disposable residual copies:
24 physical decisions, 2 cached replays, interrupt settlement intact.

Action semantics unchanged: Pendulum `continuous_scalar` (−2, 0, +2);
Acrobot `native_discrete_index` (0, 1, 2). Fixture checkpoints match
`reviewed_binding`. Scientific twelve-arm dispatch stays **BLOCKED**.
This is development verification, not a new-physics screen.

## 5. Real source-fitting path — BLOCKED

`train_world_model` residual 64×64 exists. The six-fit clock (1.215 s
wall, 0.974 s CPU, 0 env steps) used occupied-default arrays and
disposable weights. Those weights are not confirmation residuals and
not new-physics sources. A later n=3 screen needs six **fresh-physics**
fits. That path is designed and refused.

## 6. Bonferroni — preserved, low-power

Locked n=3 threshold remains **9.924843200918293** (df=2, five
comparisons). That conservatism is intentional even though only three
controls are listed. A positive interval requires
`mean > 9.924843 × s / √3 ≈ 5.730 s`. A 0.05 practical-margin effect
would need bundle scatter below ≈ 0.0087. Inconclusive is the expected
label unless the effect is enormous. This is **not** n=10 confirmation
and must not inherit the v2 df=9 gate.

## 7. Scientific runner design — refuse-only

Minimum stages exist and all refuse:

- `collect_fresh_source`
- `fit_source_models`
- `reveal_training_feedback`
- `hidden_development_evaluation`
- `run_scientific`

They reuse `PersistentAdaptive` / `ResetAdaptive` / random / evolution,
`TrustedEvaluator.hide_development`, `ReservationLedger`,
`v2.paired_bundle_seeds` for bundles 0–2, and
`v2.bundle_family_order` counterbalance
`(pendulum, acrobot)`, `(acrobot, pendulum)`, `(pendulum, acrobot)`.
`dispatch()` still hits the unnamed-holdout gate first. Flag-flips do
not collect.

## 8. Costs — measured versus unknown

**Measured**

- Default-family persist 7,680 steps: 0.156 s wall (E2.8).
- Six disposable default fits: 1.215 s wall / 0.974 s CPU, 0 env steps
  (E2.9). Same fit count as n=3×2 families, **different physics**.

**Unknown — do not invent**

- Fresh-physics source collection wall time.
- Fresh-physics six-fit wall time.
- Revealed + development screen wall time, including imagined planning.
- Twenty-fit / n=10 v2 clock.

Standing cap 900 s remains. Do not debit H16. Do not write
6 × 20 / 6 as a twenty-fit measurement.

## 9. Remaining blockers

1. Holdout unnamed (`NAMING_BLOCKED`). Occupied defaults are not it.
2. Request unauthorized; `env_cap` is 0, not 17,280.
3. Source-fitting on new physics is refused.
4. The scientific runner remains refuse-only.
5. H17 stays blocked.

Next necessary action: a separate human approval that cites
`8e90b74a`, names a four-role unused holdout, and sets
`env_cap=17280` for fresh physics. `continue` is not approval.
