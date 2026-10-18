# Evolution-2.13 — Full resource budget and real execution path

Branch `cursor/evolution2.13-resource-budget` from `bb15c2e`.
Status: **BUDGET LOCKED — 7680 NOT GRANTED — SCIENCE BLOCKED**.

This closes the resource-budget gap without starting persist-versus-reset
science. Occupied-default 7,680 is not authorization. H17 blocked. H16
ledger **305.842 / 3294.158**.

## Verdicts

| Gate | Verdict |
|---|---|
| Fresh real-environment total | **17,280** |
| Premature 7,680 grant | **REFUSED** |
| Imagined screen upper bound | **14,745,600** |
| Real planner execution path | **PASS** at `env_cap=0` |
| New-physics source fitting | **BLOCKED** |
| Holdout integrity | **BLOCKED** |
| Scientific persist-versus-reset | **BLOCKED** |

## 1. Locked real-step budget

| Line | Steps | Notes |
|---|---:|---|
| Fresh source 3×2×(1024+256) | 7,680 | New unused physics only |
| Revealed 3×6×2×200 | 7,200 | Shared across four methods |
| Hidden development 3×2×2×200 | 2,400 | `TrustedEvaluator.hide_development` |
| Confirmation | 0 | Not this request |
| **Fresh total** | **17,280** | Fits standing 100,000 |

Existing E2.8 arrays are occupied defaults. They contribute **0** credit.
`env_cap=7680` remains a reuse error. `9600` omits matched residuals.
`25600` is the v2 n=10 source worksheet.

## 2. Imagined and fit budget

Revealed plus development is 9,600 real screen steps. If the later
scientific runner replans every step at cap 1,536, imagined transitions
are at most **9,600 × 1,536 = 14,745,600**. Source fitting adds 0
imagined. n=3 needs **6** residual fits, not 20. The twenty-fit v2 clock
stays unmeasured and is not invented.

## 3. Measured versus unknown time

Measured on disposable default artifacts, `env_cap=0`, no Gymnasium:

- E2.8 default persist 7,680: 0.156 s wall. Not new physics.
- E2.9 six default fits: 1.215 s wall / 0.974 s CPU. Not new physics.
- This clock: 24 real `decide()` calls in 0.068 s wall (0.00284 s per
  decision, 36,564 imagined). The 9,600-decision planner-only prior is
  **27.3 s**. That is not a 9,600-step new-physics episode clock.

Unknown and not invented: fresh-physics collection wall, fresh-physics
six-fit wall, true 9,600-step new-physics screen wall including env
rollouts, twenty-fit v2 clock. v2 already labels 900 s as
`likely_incomplete_budget_under_900s`. The planner-only prior sits
under that cap; the missing env-rollout cost does not.

## 4. Real execution path — PASS, still not science

The four methods now consume evaluator-owned unit-interval scores from
`planner_adapter.decide` on disposable residuals, reserved through
`ReservationLedger`. Persist keeps weights across Pendulum→Acrobot.
Reset discards them. Hidden development variants cannot enter
`training_feedback`. Twelve-arm scientific dispatch stays BLOCKED.

`TrainingFeedback` remains a 0–1 contract. Raw planner returns are
normalized inside the evaluator after a catalogue warmup. That adapter
is required for a later real run; callers still cannot substitute
scores.

`collect_transitions` and `train_world_model` are still refused. This
path does not fit new physics and does not grant 7,680.

## 5. Next necessary action

A separately authorized persist-versus-reset experiment can test
cross-task benefit only after:

1. Human approval citing `8e90b74a`
2. A named unused four-role holdout
3. `env_cap=17280` for fresh physics, not 7,680

`continue` is not that approval. Do not start Evolution-3.
