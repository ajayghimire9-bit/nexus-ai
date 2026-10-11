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
- Mid-experiment resume restores weights/optimizer/timestep cursor; Gymnasium internal env RNG is not fully serialized.
- NEXUS Alpha / live trading: not implemented.
- The agent cannot alter its own safety, eval, or financial-risk rules.
