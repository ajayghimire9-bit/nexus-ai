# NEXUS V0.7.1 — Trustworthy world models and planning

Branch `cursor/v071-planning-validation`. Not merged. Measured 2026-10-11, CPU.

Parent `5c14294`. `pytest` **125 passed**. `artifacts/v07_world_model.json` and V0.6 JSON were not overwritten.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v071_benchmarks.py`

Not AGI. Not V0.6. Simulator is an eval oracle. Architecture selection uses **validation MAE only**; the planner kind is frozen from **model seed 0**. Test MAE is computed after freezing.

## Protocol

- 10 independent collection+init seeds. Train 2048 / val 512 / test 512, seed-disjoint.
- Predictors: persistence, ridge residual, direct MLP, residual MLP. Ensemble of 3 residual nets (val early-stop).
- Planner: random shooting, 16 candidates, horizon 6, **absorbing** survival (`alive *= 1-p_term` after crediting the current predicted reward). Time budget enforced by scoring candidate chunks until `max_plan_ms`.
- Paired control eval seeds `{83000, 83017, 83034}`, 2 episodes each.
- Residual greedy/MPC are **diagnostics**, not used to pick the kind.

Seed 0 val MAE chose **ridge**. That kind is frozen for all 10 planner copies of `greedy` / `mpc` / `mpc_matched`.

## 1. Do dynamics generalize?

Test MAE, Student-t n=10 model seeds:

| Model | MAE [t 95%] |
| --- | --- |
| Persistence | 0.1246 [0.1243, 0.1248] |
| Direct MLP | 0.0138 [0.0102, 0.0173] |
| Residual MLP | 0.00369 [0.00306, 0.00431] |
| **Ridge residual** | **0.000105 [0.000090, 0.000120]** |

Ridge and residual beat persistence on every seed. CartPole’s local Euler map is nearly linear, so ridge one-step error is extremely small. Residual MLP is stable across seeds (~0.003–0.005).

## 2. Does planning beat one-step selection?

Frozen **ridge** planner (val-selected):

| Controller | return [t 95%] |
| --- | --- |
| Random | 21.3 |
| Ridge one-step greedy | **246 [230, 262]** |
| Ridge MPC / cost-matched MPC | **9.33** (degenerate) |
| Neural ensemble, penalty 0 | 259 [142, 377] |
| Neural ensemble + uncertainty | 335 [234, 437] |
| Hand heuristic | 500 |

Paired **ridge MPC − ridge greedy = −237 [−253, −221]** (excludes 0). Multi-step shooting on the best one-step model **hurts**.

Diagnostic **residual MLP** (not used for selection):

| Controller | return [t 95%] |
| --- | --- |
| Residual greedy | 283 [249, 316] |
| Residual MPC | 288 [153, 424] |

Paired residual MPC − greedy **+5.6 [−159, +171]** — includes 0. **No reliable multi-step planning advantage** over one-step greedy.

## 3. Does uncertainty-aware planning win?

Ensemble disagreement vs error corr **0.69 [0.60, 0.77]** across 10 seeds. **Not claimed calibrated.**

ens_pen − ens_zero **+76 [−31, +183]** — includes 0. Do **not** call uncertainty-aware planning superior.

Ridge terminate head: prevalence 0.45%, recall **0**, Brier **0.075** vs always-nonterminal Brier **0.0045**. The linear terminate model is **worse** than predicting never-done. Absorbing MPC then collapses imagined return (~9).

Mean plan time: ridge MPC 0.31 ms; matched 0.90 ms; ensemble ~3.6 ms. Mean inferred states: MPC 5376 vs ensemble-pen 193k (members inside `MeanEnsemble.step`).

## 4. When does better prediction help or hurt control?

On-source: **lowest val/test MAE (ridge) yields the worst MPC**. One-step ridge greedy remains strong (246). The failure is **model exploitation under multi-step search**, not a lack of one-step fit.

Transfer (`cartpole_v07_transfer`), residual MLP, n=3 eval seeds, **not** used to pick hyperparameters:

| Model | random-policy MAE | 20-step MAE | MPC return |
| --- | --- | --- | --- |
| Source | 0.00890 | 0.0150 | 476 [423, 528] |
| Fine-tune (256+128 target steps) | **0.00642** | **0.0491** | **500** |
| Scratch | 0.0506 | — | — |

Fine-tune **improved one-step** MAE and **worsened** 20-step open-loop MAE. With the absorbing predicted-reward objective, MPC returns hit the 500 ceiling for fine-tune and DAgger (n=3). On-policy MAE on source-MPC states: source 0.00817, fine-tune 0.00588. Action-ranking vs a 1-step θ-oracle is **weak** (source 0.19, fine-tune 0.17 on 48 states) — ranking used 96 counted oracle env steps per model.

V0.7.0’s “fine-tune MAE↓ but return↓” is **not replicated** under this scorer (returns 476 vs 500, n=3). The durable lesson is: **one-step MAE is not a sufficient statistic for control**.

## 5. Can new experience improve the model?

DAgger mix: **1956** additional target env steps from source-MPC, then fine-tune. Held-out MPC **500** (n=3). Learning env for world models: **2560**/seed (train+val). Test collect 512 is eval-only.

## Sample efficiency vs PPO

| Learner | Train env steps | Eval return |
| --- | --- | --- |
| WM learning (train+val) | 2560 / model seed | residual greedy 283; ridge greedy 246 |
| PPO matched 2560 | 5×2560 = 12800 | **74.2 [51, 97]** |
| PPO v064 16384 | 3×16384 = 49152 | **238 [−264, 741]** n=3, unsolved |

Model-based one-step greedy beats matched PPO. Stronger PPO is noisy and still unsolved at 16k. Heuristic remains 500. Do not equate 2048 WM transitions with 2048 PPO steps: val 512 is extra learning data; test 512 is not.

Analysis oracle steps (action ranking): **1152**. Transfer collect **896**.

Wall **172 s**.

## Scientific answers

1. **Yes** for one-step MAE (ridge and residual CIs far below persistence).
2. **No** reliable gain of shooting MPC over one-step greedy for residual nets; ridge MPC is actively worse.
3. **No** independent-seed evidence that uncertainty penalties beat a cost-matched ensemble with penalty 0.
4. **Better one-step MAE can worsen planning** (ridge) or leave it unchanged (residual MPC vs greedy). Multi-step error can move opposite to one-step after fine-tune.
5. Extra on-policy data is countable and, here, coincided with ceiling returns on n=3 — **inconclusive** as a learning-to-model claim.

Do not scale to Dreamer-style models until shooting MPC beats one-step greedy with a CI excluding 0.
