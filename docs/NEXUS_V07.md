# NEXUS V0.7 — World models and planning

Branch `cursor/v07-world-models-planning`. Not merged. Measured 2026-10-11, CPU.

Parent `c38b54e` (V0.6.6 closed). V0.6 artifacts were not overwritten. `pytest` **119 passed**.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v07_benchmarks.py`

Not AGI. CartPole-v1 with corrected physics (`cartpole_derived_v1`). The simulator is an **evaluation oracle** only. Imagined MPC rollouts use the learned model.

## Setup

| Item | Value |
| --- | --- |
| Train / val / test transitions | 4096 / 1024 / 1024 (seed-disjoint) |
| Collect env steps | **6144** |
| Policies | random + exploratory mix |
| Model | 2×64 tanh MLP, CPU |
| Heads | residual Δs vs direct next-s + terminate logit |
| Planning | random shooting, 32 candidates, horizon 8 |
| Control eval | 5 seeds, 8 episodes, seed 83000+ |
| PPO | 4096 env steps/seed × 5 seeds (matched to `n_train`) |

## 1. One-step prediction (held-out test)

| Predictor | MAE | RMSE | term acc |
| --- | --- | --- | --- |
| Persistence (s′=s) | 0.125 | 0.175 | n/a |
| Direct next-state MLP | 0.00632 | 0.0132 | 0.996 |
| **Residual MLP** | **0.00272** | **0.00509** | **0.996** |

Residual MAE per dim: x 0.00292, ẋ 0.00294, θ 0.000375, θ̇ 0.00466.

Residual beats persistence by ~46× on MAE. Winner = residual. Reload MAE matches (0.00272). Different actions from the same start produce distinct predictions (L2 gap 0.70).

## 2. Multi-step open-loop error (action-conditioned on test episodes)

| Horizon | learned mean MAE | horizon-end MAE | persistence MAE |
| --- | --- | --- | --- |
| 1 | 0.00209 | 0.00209 | 0.122 |
| 5 | 0.00528 | 0.00860 | 0.126 |
| 10 | 0.00975 | 0.0175 | 0.203 |
| 20 | 0.0198 | 0.0426 | 0.147 |

Error accumulates with horizon. It stays well below persistence on this testbed through 20 steps.

Oracle check: 10-step imagination vs the **recorded** test trajectory MAE 0.00980 (no extra privileged simulator inputs at inference).

## 3. Control (source CartPole)

Student-t 95%, n=5 eval seeds.

| Controller | mean return | interval | eval env steps |
| --- | --- | --- | --- |
| Random | 23.4 | [17.4, 29.4] | 936 |
| PPO (4096 steps/seed) | 110.7 | [88.5, 133.0] | train 5×4096 |
| One-step greedy (model, no MPC) | 307.5 | [267, 348] | 12 298 |
| Random-shooting MPC | 325.4 | [289, 362] | 13 017 |
| Uncertainty-penalized MPC | **447.9** | [420, 476] | 17 914 |
| Hand heuristic (sanity) | **500** | [500, 500] | 20 000 |

Planner `used_simulator=False`. Mean plan time **0.54 ms**/decision.

Matched-budget PPO (4096 train steps/seed) is far from solved. Learned-model controllers beat that PPO and random. They do **not** beat the known CartPole heuristic. One-step greedy already captures most of vanilla MPC; extra shooting adds a modest mean gain whose CIs overlap one-step.

## 4. Ensemble uncertainty

Three residual members. Test MAE 0.00262. Mean disagreement 0.00254. Error vs std **Pearson 0.72**. **Not claimed calibrated.** Penalizing disagreement during shooting raised source return (448 vs 325) on this run; that is one CPU experiment, not a general calibration theorem.

## 5. Transfer to `cartpole_v07_transfer` (g=11, L=0.45, m=0.15)

Target prediction MAE on 1024 held-out target transitions:

| World model | MAE |
| --- | --- |
| Source residual, no adapt | 0.00904 |
| **Fine-tune source weights** (256+128 target steps) | **0.00380** |
| Scratch on target data | 0.0283 |
| Source RMS + random weights trained on target | 0.0301 |

V0.6 finding (RMS helps **policy** transfer) does **not** repeat for dynamics: source RMS without source weights is no better than scratch. Source weights **do** transfer for one-step prediction here (related Euler physics).

Planning on the target (n=3 seeds):

| Planner model | return [t 95%] |
| --- | --- |
| Source MPC (no adapt) | 288 [258, 318] |
| Fine-tuned | 221 [190, 252] |
| Source-RMS random | 169 [157, 181] |
| Scratch | 65.4 [63.5, 67.3] |

Better one-step MAE after fine-tune **did not** improve MPC (221 < 288). Possible causes: overfitting to short random-policy traces, horizon compounding, n=3. Reported as measured, not as a win.

## 6. When prediction helps vs when planning fails

- Helps: accurate residual model + even one-step greedy ≫ random and ≫ 4096-step PPO on default CartPole.
- Fails / weak: scratch target model (MAE 0.028) → return ~65; vanilla MPC CI overlaps one-step greedy; fine-tune improved MAE not returns; heuristic still ceiling.
- Cost: model collect 6144 steps + milliseconds of planning vs PPO 20480 train steps across 5 seeds. Sample-efficiency claims must include collection.

Wall **55.9 s**.

## Success criteria

1. **Met.** Residual MAE 0.00272 vs persistence 0.125.
2. **Met.** Horizon MAE 0.002 → 0.020 (1→20).
3. **Met.** MPC imagines with the learned model only.
4. **Met as a comparison, not a solved agent.** Model-based > matched PPO; heuristic still dominates.
5. **Met diagnostically.** Planning quality tracks model error; copied RMS is not a substitute for dynamics weights; fine-tune≠better control.

V0.7 is PREDICT + PLAN on a known linear-ish simulator. It is not a world model of an unknown domain and not AGI.
