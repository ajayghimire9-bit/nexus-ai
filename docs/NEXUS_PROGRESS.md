# NEXUS progress log

Status is architecture plus measured local experiments. Completing a version tag is not AGI, not a profitable trading system, and not learned meta-RL unless that claim is supported below.

## V0.4 (retained)

Measured 2026-10-11, CPU. Prior CartPole / Acrobot PPO and evolution numbers are **not overwritten**.

| Run | Setup | Timesteps | Eval |
| --- | --- | --- | --- |
| PPO CartPole seed 1 | separate trunks, 10 epochs | 249 856 | **500.0** vs random 22.4 |
| PPO CartPole seed 2 | same | 249 856 | **409.5** vs random 26.2 (**not solved**) |
| PPO CartPole seed 2 (retrain) | same recipe | **399 872** | **500.0** vs random 26.3 |
| PPO CartPole seed 3 | same | 249 856 | **500.0** vs random 21.5 |
| Multi-seed @ 250k | seeds 1,2,3 | 249 856 | mean **469.8**, std 42.7 |
| PPO Acrobot | separate agent | 249 856 | **−83.25** vs random −500 |
| CartPole evolution | 49 152 / candidate | 49 152 | all gen-1 candidates **500** (ceiling) |
| Acrobot evolution | 81 920 / candidate | 81 920 | best **−75.2** (tanh 64-64, gen 1) |

## V0.5 corrections (budget, resume, champions, pairing)

Fixes on `cursor/v05-budget-aware-meta-controller`, not merged to `main` by this work.

- Env-step accounting **sums every training seed**; remaining budget subtracts **actual** PPO timesteps, not the last seed or the estimate alone.
- Resume restores elites, scores, baselines, LinUCB/`ε` state, Python RNG state, champion history, and remaining caps. Interrupted+resume matched an uninterrupted 2-experiment fingerprint sequence in tests.
- Champion file is the evaluated seed **closest to the multi-seed mean**, not the last seed in the loop.
- Controller comparison is **paired**: the same predefined controller seeds (and therefore the same train-seed formula, holdout, and assessment split) for random, ε-greedy, and LinUCB.
- `extra_evaluation` writes an independent assessment on `assessment_eval_seed` and **does not** call `controller.update`. Training feedback uses `holdout_eval_seed` only. Equal holdout/assessment seeds raise.

### Tests

`pytest` **46 passed** in **1.78s** (Python 3.13.5, pytest 9.1.1). No tests skipped.

### PPO / GAE (Stage 1)

Dummy next-step autoreset transitions are masked out of policy, value, and entropy losses (regression: poisoning dummy returns no longer explodes value loss). Same-step autoreset no longer treats the following step as a dummy. Discrete eval is deterministic-argmax and repeatable; continuous greedy action is the distribution mean.

**Not measured:** a 250k CartPole retrain after these loss-masking changes. Do not claim PPO sample-efficiency improved vs V0.4.

### Meta-controller (Stages 2–5)

Seven validated actions (mutate, crossover, expr-mutate, LR search, width search, extra eval, architecture transfer). No `exec` of generated Python.

Controllers: random, ε-greedy (heuristic, **not** meta-RL), disjoint **LinUCB** (contextual bandit, **not** meta-RL). LinUCB updates `A`, `b` from the controller reward.

Controller reward is task-normalized vs a random-policy baseline on the **same** env, plus sample-efficiency / complexity / time / failure terms. Holdout eval seed feeds the controller; `assessment_eval_seed` is reserved for extra evaluation so the selector cannot freely reuse one test set as its only score.

Loop: OBSERVE → PROPOSE → VALIDATE → TRAIN → EVALUATE → STORE → UPDATE → stop on frozen `max_experiments` / `max_timesteps`. Duplicate fingerprints are skipped. Controller state JSON is persisted. Champion checkpoints are copied, not deleted.

The controller cannot change resource caps, eval seeds, or permissions.

### Equal-budget paired comparison (measured)

Protocol: **2 controller seeds** `{0, 1}` shared by all methods; **2 experiments**; **512 env-step cap**; **256 train steps**; **1 train seed**; **2 eval episodes**. Within seed 0 every method used train seed **1000**; within seed 1, **1001**. Actual env steps consumed: **512 per replicate**, **1024 total per controller**. Failures: **0**.

| Controller | mean controller reward | std (n=2) | total env steps | mean fail |
| --- | --- | --- | --- | --- |
| random | 0.108 | 0.019 | 1024 | 0 |
| ε-greedy | −0.035 | 0.014 | 1024 | 0 |
| LinUCB | 0.261 | 0.057 | 1024 | 0 |

Per-pair controller rewards: seed 0 — random 0.095, ε-greedy −0.045, LinUCB 0.221; seed 1 — random 0.122, ε-greedy −0.026, LinUCB 0.301.

LinUCB’s mean was higher **on this 256-step, n=2 smoke**. That is **not** evidence of meta-learning or a reliable ranking: two replicates, PPO far from CartPole-solved (best normalized CartPole score 0.45 ≈ not 475/500), controller reward is not an independent assessment set, and no larger held-out condition suite was run. Do not treat LinUCB as superior.

### Activation expressions (Stage 6)

Restricted trees (approved torch ops only), population + mutate/crossover, node cap 12, SHA canonical dedup, learnable affine `(scale, shift)`, numerical validation. Training eval of expr search at V0.3/V0.4 activation-screen scale was **not re-run** in this increment beyond unit tests.

## V0.5 independent validation (this increment)

Branch `cursor/v05-budget-aware-meta-controller`. Not merged to `main`.

`pytest` **50 passed** in **1.96s**. Mid-experiment PPO resume and in-flight loop resume tests included: interrupted runs do not decrement the budget, and resume does not double-count env steps.

### CartPole 250k with dummy-reset loss masking vs V0.4

Matched recipe: separate trunks, 10 epochs, 249 856 steps, eval 20 episodes seed 10 000. Wall ~21.5 s/seed, 66.3 s total.

| Seed | V0.4 eval | V0.5 eval (masked PPO) | Random |
| --- | --- | --- | --- |
| 1 | 500.0 | **500.0** | 22.2 |
| 2 | 409.5 (not solved) | **457.5 ± 127.5** (not solved) | 22.6 |
| 3 | 500.0 | **500.0** | 24.2 |
| Mean | 469.8 | **485.8** (std 24.5) | — |

`solved_cartpole` remains **false** (seed 2 < 475). Seed 2 still collapsed to 0 rollout return during training. The +48 on seed 2 vs V0.4 is **not** treated as a confirmed algorithm win: one noisy seed, still unsolved, training still unstable.

### Paired controller study (enough decisions for LinUCB updates)

Protocol: controller seeds `{0, 1}`; **8** experiment slots; cap **2048** env steps; **256** train steps; 1 train seed; 4 eval episodes. Feedback holdout seed **80000**; extra-eval assessment **81000**; **independent champion eval seed 92000** (unused in selection, updates, or champion ranking). Methods: random, ε-greedy, LinUCB, **frozen LinUCB** (no `A,b` updates). Wall-clock for the whole comparison: **2.89 s**.

| Controller | mean bandit reward ± std | independent return ± std | total env steps | mean fails / skips |
| --- | --- | --- | --- | --- |
| random | 0.016 ± 0.002 | **336 ± 203** | 2816 | 2.0 / 2.0 |
| ε-greedy | 0.002 ± 0.000 | 127 ± 92 | 3072 | 2.0 / 2.0 |
| LinUCB (updating) | 0.079 ± 0.065 | 224 ± 45 | 3072 | 1.5 / 1.5 |
| LinUCB frozen | 0.015 ± 0.068 | 145 ± 68 | 2560 | 3.0 / 3.0 |

Independent per-pair champion returns (seed 92000): random 192.5 / **480.3**; ε-greedy 192.5 / 61.8; LinUCB 192.5 / 256.3; frozen 192.5 / 97.0.

LinUCB **did not** beat random on independent evaluation. Random’s mean is dominated by one 480 run. Updating LinUCB beat frozen LinUCB on this sample (224 vs 145 independent; 0.079 vs 0.015 bandit reward) but **n=2** and intervals overlap — not evidence that learning, rather than action-sequence luck, caused the gap.

Actual env steps differ across methods because extra-eval and duplicate skips are 0-step; the cap was 2048/replicate. Failures listed are duplicate fingerprints counted as skips.

**Arm traces (LinUCB vs frozen):** frozen stayed on `mutate_architecture` for all 5 completed actions both seeds. Updating LinUCB diversified: seed 0 `mutate → crossover ×2 → expr → lr → size → extra_eval`; seed 1 `mutate → crossover ×2 → expr ×3`. Preference change is real; it did not produce a better independent champion than random.

**Hypothesis not supported:** a learned (updating) research controller does **not** show repeatable independent-eval gains over random under this CPU budget. Frozen vs updating is suggestive but underpowered.

### Incomplete

- Controller study is still n=2 seeds and 256-step PPO inner loops; CartPole ceiling not relevant here.
- Extra-evaluation of a missing champion is a failed experiment.
- NEXUS Alpha / live trading: not implemented.
- The agent cannot alter its own safety, eval, or financial-risk rules.

## V0.5.1 — prove or reject learned research improvement

Branch `cursor/v05-budget-aware-meta-controller`. Not merged to `main`. Measured 2026-10-11. `pytest` **56 passed** in **3.07s**. Artifacts: `artifacts/v051_synthetic_bandit.json`, `artifacts/v051_ppo_meta.json`. Reproduce with `PYTHONPATH=src:.deps python3 scripts/run_v051_benchmarks.py`.

### PPO checkpoint restoration

`save()` now stores Python / NumPy / PyTorch (and CUDA if present) RNG plus a vector-env snapshot. CartPole-v1 restore fidelity is `classic_control_state` (unwrapped `.state`, TimeLimit `_elapsed_steps`, env `np_random` when present). Envs without those fields restore as **`approximate`**: weights, optimizer, timestep cursor, and library RNG match; the Gymnasium trajectory is not claimed bit-identical. Tests encode both classes (`test_cartpole_resume_restores_classic_control_state`, `test_unsupported_env_resume_is_approximate`).

### Proposal filter (no slot for unrun actions)

Invalid / duplicate / unaffordable / `extra_evaluation` without a champion are rejected before execution (`src/nexus/meta/schedule.py`). Rejected proposals increment `n_rejected_proposals` and do **not** decrement the experiment budget. After `MAX_PROPOSE_ATTEMPTS=32` consecutive failures the loop stops (`stopped: no_valid_proposal`).

### Synthetic contextual bandit (known optimal policy) — **hypothesis supported**

Separate from PPO. Linear rewards `r = x·θ_a + noise`, 4 arms, dim 8, horizon 200, **20 seeds**. Last-50 optimal-action rate (95% CI) and cumulative regret:

| Method | last-50 opt rate (95% CI) | final regret (95% CI) | mean action freq |
| --- | --- | --- | --- |
| random | 0.257 [0.235, 0.279] | 362.4 [339.1, 385.7] | ~uniform 0.24–0.26 |
| ε-greedy (updates) | 0.894 [0.879, 0.909] | 66.3 [59.0, 73.7] | 0.32 / 0.24 / 0.23 / 0.21 |
| **LinUCB (updating)** | **0.957 [0.946, 0.968]** | **30.9 [27.5, 34.2]** | 0.35 / 0.23 / 0.21 / 0.22 |
| LinUCB frozen | 0.369 [0.336, 0.402] | 354.0 [340.6, 367.4] | **1.00 / 0 / 0 / 0** (always arm 0) |

Learning curve (mean optimal-hit rate): LinUCB 0.45 (t=0) → 0.80 (t=49) → **1.00 (t=199)**; random stays ~0.1–0.35. Frozen never leaves arm 0. Updating LinUCB therefore **learns the known optimal preference**; frozen LinUCB does not.

**Generalization:** train 200 steps on default contexts; greedy accuracy on shifted/scaled contexts (`shift=1.5`, `scale=1.2`, 200 eval steps, 20 seeds): LinUCB **0.991** [0.988, 0.995]; frozen 0.916 [0.901, 0.932]; random 0.248 [0.240, 0.255]. Frozen is high because the shift makes arm 0 frequently optimal while frozen always picks arm 0 — not evidence of learned transfer. LinUCB still beats frozen and random on the shifted set.

This **does not** imply the PPO research controller improved.

### PPO meta-controller (kept separate) — **hypothesis not supported**

Paired seeds `{0,1}`; 4 experiment slots; cap 1024 env steps; 256 inner train steps; 1 train seed; 4 eval episodes. Holdout 80000 / assessment 81000 / independent champion eval **92000**. Wall ~2.2 s for the comparison.

| Controller | mean bandit reward ± std | independent return ± std | total env steps | mean rejected (not slots) |
| --- | --- | --- | --- | --- |
| random | 0.003 ± 0.055 | **336 ± 203** | 2048 | 0.5 |
| ε-greedy | 0.035 ± 0.032 | 127 ± 92 | 2048 | 0.5 |
| LinUCB (updating) | **0.080 ± 0.004** | **336 ± 203** | 1792 | 17.0 |
| LinUCB frozen | −0.050 ± 0.037 | 60 ± 52 | 2048 | 1.5 |

Independent per-pair returns: random 192.5 / 480.3; ε-greedy 192.5 / 61.8; LinUCB 192.5 / 480.3; frozen 23.3 / 97.0. Failures/skips after the filter: **0** (duplicates/unaffordable no longer occupy completed-experiment slots). LinUCB seed 1 stopped after **33** rejected retries (`32` consecutive + earlier) with only 3 completed runs / 768 steps — budget not exceeded, no infinite retry.

Updating LinUCB **tied** random on independent champion return and beat frozen. Bandit reward is higher for LinUCB, but independent eval (the decision that matters) shows **no improvement over random**. n=2, 256-step inner PPO: still underpowered for a research-controller claim.

### Verdict

- **Supported:** LinUCB learns a known-optimal linear bandit and generalizes better than random/frozen on shifted contexts. Scheduling no longer burns slots on unrun proposals. CartPole PPO resume is classified as classic-control exact vs approximate.
- **Rejected:** learned PPO experiment selection does **not** beat random search on independent champion return under this CPU budget.
- Not AGI. Not meta-RL. Not a trading system.

## V0.5.2 — valid decisions and budget efficiency

Branch `cursor/v05-budget-aware-meta-controller`. Not merged to `main`. Measured 2026-10-11. `pytest` **60 passed**. V0.5.1 unpaired synthetic results remain in `artifacts/v051_synthetic_bandit.json` and are not overwritten.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v052_benchmarks.py`.

### Task 1 — paired synthetic bandit (**hypothesis supported**)

Within each of **20 seeds**, every controller sees the same pre-generated context sequence and the same potential-reward noise. Metrics are paired differences vs random (mean and 95% CI). Horizon 200; held-out 200 in-distribution + 200 shifted contexts (no updates on held-out).

| Method | last-50 opt | train regret | held-out in-dist opt | held-out shifted opt |
| --- | --- | --- | --- | --- |
| random | 0.262 [0.240, 0.284] | 367.6 | 0.243 | 0.258 |
| ε-greedy (updates) | 0.893 [0.881, 0.905] | 66.7 | 0.972 | 0.992 |
| **LinUCB** | **0.961 [0.945, 0.977]** | **31.6** | **0.970** | **0.992** |
| LinUCB frozen | 0.344 [0.310, 0.378] | 370.8 | 0.356 | 0.926 |

Paired deltas **LinUCB − random**: last-50 opt **+0.699** [0.673, 0.725]; regret **−336.0** [−359.1, −312.8]; held-out in-dist **+0.728** [0.718, 0.737]; shifted **+0.735** [0.722, 0.747]. CIs exclude 0. Frozen vs random regret CI **includes 0** (+3.3 [−12.2, +18.7]). Frozen shifted accuracy is high because frozen always picks arm 0 and the shift makes arm 0 often optimal — not learned transfer.

Action frequencies: frozen **1.0 / 0 / 0 / 0**; LinUCB 0.33 / 0.23 / 0.20 / 0.24; random ~uniform. Learning curve: LinUCB opt-hit 0.40 → **1.00**.

### Task 2 — feasible action selection

The loop enumerates unique `ExperimentAction`s, filters duplicate / unaffordable / unsupported / impossible (`extra_evaluation` without a champion), then ranks the remainder. Invalid actions are never proposed. Empty valid set stops with `no_valid_candidates`. Confirmatory vs exploratory tiers (`train_timesteps=8192`, `explore_timesteps=2048`) share an arm but differ in cost.

### Task 3–4 — PPO meta (CartPole + Acrobot), paired seeds `{0,1,2}` (**hypothesis not supported**)

Protocol: 4 experiment slots; cap **24 576** env steps; confirm 8192 / explore 2048; 1 train seed; 8 eval episodes. Holdout 80000 / assessment 81000 / **independent 92000**. Task-normalized vs a random-policy baseline on the same env. Inner PPO is still far below the V0.4 250k CartPole recipe.

**CartPole-v1 independent champion (seed 92000):**

| Controller | indep return ± std | task-norm | total env steps | useful exp | invalid avoided | gain / 1k steps |
| --- | --- | --- | --- | --- | --- | --- |
| random | 85.7 ± 100.5 | 0.119 | 63 488 | 3.33 | 9.0 | 0.006 |
| ε-greedy | 106.6 ± 76.8 | 0.160 | 30 720 | 4.0 | 12.0 | 0.015 |
| LinUCB | 99.8 ± 82.5 | 0.147 | 24 576 | 4.0 | 11.7 | 0.028 |
| LinUCB frozen | **166.7 ± 75.8** | **0.281** | 24 576 | 4.0 | 11.7 | 0.017 |

Paired indep deltas vs random (n=3): LinUCB **+14.1** [−174.5, +202.7]; ε-greedy **+20.9** [−158.7, +200.6]; frozen **+81.0** [−118.1, +280.2]. **All CIs include 0.** Frozen’s point estimate is highest; that is not a learning effect (no `A,b` updates; it only chose `mutate_architecture` / explore). Updating LinUCB preferred explore (`mutate → crossover → expr → lr`) and used **fewer** steps than random (paired step delta −12 971 [−19 661, −6 281]) without a reliable independent-return gain.

**Acrobot-v1:** every controller’s independent return is **−500** (task-norm 0). 8192-step inner PPO does not produce Acrobot progress. LinUCB/frozen again used 24 576 vs random 63 488 steps. No controller beat random; there was no signal to beat.

Remaining timesteps never went negative. Failures occupying slots: **0**. Useful completed experiments: 3–4 per replicate. Cost-aware ranking did choose inexpensive explore runs; that improved compute use, not independent CartPole/Acrobot skill.

### Verdict

- **Supported:** paired LinUCB learns the synthetic optimal policy and beats random/frozen on in-distribution and held-out contexts with CIs excluding 0. Valid-candidate ranking avoids invalid proposals and stays inside the step cap.
- **Rejected:** learned PPO experiment selection does **not** beat random search on independent champion return on CartPole or Acrobot under this budget. Frozen outperforming updating LinUCB on CartPole point estimates is **not** evidence of learned self-improvement.
- Inner-loop compute (8k steps) is still too small for these classic-control tasks relative to the 250k PPO baseline. Not AGI. Not meta-RL. Not a trading system.
