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

## V0.6 — continual learning (CartPole family)

Branch `cursor/v06-continual-transfer`. Not merged. Full write-up: `docs/NEXUS_V06.md`. `pytest` **69 passed**. V0.5.1/V0.5.2 artifacts were not overwritten; the paired synthetic 20-seed study reproduced to `1e-9`.

Compatible tasks only: CartPole gravity/length/mass variants (4-D, 2 actions). **Not Acrobot.** Independent eval seed 70000. 2048 steps/task, 3 seeds, 6144 steps matched across methods.

| Method | mean final across tasks (95% CI) | forgetting (95% CI) |
| --- | --- | --- |
| independent specialists | 101.4 [95.8, 107.1] | n/a |
| naive fine-tune | 117.4 [94.5, 140.2] | −6.3 [−21.1, +8.6] |
| replay | 115.8 [85.0, 146.6] | −9.1 [−17.1, −1.0] |
| EWC | 118.3 [95.1, 141.5] | −7.2 [−22.6, +8.3] |
| multi-head | 140.4 [69.0, 211.8] | +2.8 [−4.0, +9.6] |

Held-out encoder transfer (`cartpole_lowg`) vs scratch: **−26.8** [−61.8, +8.2]. Adaptive curriculum 95.7 vs random 115.2.

**Success criterion not met:** no method beat both specialists and naive fine-tuning with a CI excluding overlap. Expression checkpoints now reload in a fresh process. Not AGI.

## V0.6.1 — corrected protocol, still no positive transfer

Branch `cursor/v06-continual-transfer`. Full write-up: `docs/NEXUS_V061.md`. `pytest` **74 passed**. `artifacts/v06_continual.json` not overwritten.

Fixes: val seed 71000 vs independent 72000 (curriculum never sees test); task-balanced replay; accumulated Fisher; Lopez-Paz ACC/FWT/BWT; specialist curves at 2k/8k/16k; held-out zero-shot/frozen/finetune/scratch.

Specialists **do not solve** CartPole variants at 16384 steps (best mean 217 on long, CI [60, 375]; solve=475). At 8192/task, naive FWT **−44.8 [−84.9, −4.8]**; multi-head ACC 57 vs specialists 138; held-out scratch **164** vs frozen encoder **22**. Adaptive curriculum does not beat fixed order.

**Success criterion not met.** Negative FWT is the statistically credible result. Next hypothesis: transfer requires source policies that actually solve the variant, not 8–16k of unstable PPO.

## V0.6.2 — valid EWC, metrics, and transfer tests

Branch `cursor/v06-continual-transfer`. Full write-up: `docs/NEXUS_V062.md`. `pytest` **83 passed**. V0.6 / V0.6.1 JSON artifacts unchanged.

EWC is now per-sample diagonal empirical Fisher of `log π` with **per-task** `(θ*, F)` snapshots. Zero-shot FWT is vs **untrained**, not vs a specialist. Transfer copies weights used in the forward pass and copies `obs_rms`.

Source `cartpole_default` at 32 768 steps: mean **250.8** [4.5, 497]; per seed 99 / **500** / 153. Not a reliable specialist (one collapse). Sequential CL kept at 2 048 steps/task.

Held-out `cartpole_lowg`, 8 192 matched target steps: encoder + new-head fine-tune **438.5** [373, 504] vs scratch **138.3** [66, 211]. Paired deltas **+311, +299, +291**. That transfer test is supported. Frozen encoder and sequential CL are not. Multi-head BWT **−12.9 [−14.1, −11.6]**. Adaptive curriculum does not beat fixed. Not AGI.

## V0.6.3 — adaptive knowledge reuse

Branch `cursor/v06-continual-transfer`. Full write-up: `docs/NEXUS_V063.md`. `pytest` **88 passed**. Prior V0.6–V0.6.2 JSON artifacts unchanged.

Val-best source checkpoint (not last weights): independent **291 [83, 499]**; 1/3 seeds solve; seed 0 collapse at 32k is skipped via val. Selector uses val zero-shot only; thresholds frozen from V0.6.2.

Untouched tests `short` / `highg` / `longheavy` (n=9): selector **320.9 [209, 433]** vs scratch **78.8 [59, 98]** (paired **+242 [120, 365]**). Encoder+new-head FT **68.1** and **destroys** source skill (Δ **−219 [−324, −115]**). Selector always chose reuse or conservative LR; it did not beat conservative itself.

**Partial success:** useful strategy selection vs scratch and vs the V0.6.2 encoder recipe. Encoder-head transfer did **not** persist off low-g. Not AGI.

## V0.6.4 — corrected physics, seed-level inference

Branch `cursor/v064-validated-adaptation`. Full write-up: `docs/NEXUS_V064.md`. `pytest` **98 passed**. V0.6–V0.6.3 JSON kept as **legacy physics** (`cartpole_setattr_only`); they are not evidence on `cartpole_derived_v1`.

Gymnasium 1.4 derived `total_mass` / `polemass_length` are now recomputed after param edits. CIs use **n=10 source seeds** (Student-t), not 30 correlated task cells. Encoder-only retention is undefined.

Source at 32 768 / 10 epochs: independent **154.7 [75, 234]**; **0/10** val-solved. Confirmation (3 frozen offsets, eval 74000): encoder+new-head FT **392 [316, 468]** vs scratch **92 [60, 124]**; paired **+300 [224, 376]**. Risk-aware selector **tied conservative** (237) and **lost to encoder** (−155 [−279, −30]). Selector hypothesis failed; encoder-vs-scratch transfer succeeded. Not AGI.

## V0.6.5 — causal transfer (normalization vs encoder)

Branch `cursor/v065-causal-transfer`. Full write-up: `docs/NEXUS_V065.md`. `pytest` **105 passed**. V0.6–V0.6.4 artifacts preserved. Empty CIs are JSON `null`.

On new confirmation tasks (eval 75000, n=10 seeds, 2 048 steps): **random encoder + source RMS (B) 227.5 [169, 286]** vs pretrained encoder + source RMS (D) **117.8 [84, 151]**. Paired **D − B = −110 [−181, −39]**. **B − A (RMS only) = +128 [73, 184]**. The V0.6.4 encoder win is **not** independent representation transfer. LinUCB always chose conservative LR and did not beat B. Not AGI.

## V0.6.6 — transfer finalization (V0.6 complete)

Branch `cursor/v066-transfer-finalization`. Write-ups: `docs/NEXUS_V066.md`, `docs/NEXUS_V06_FINAL.md`. `pytest` **110 passed**. Artifact `artifacts/v066_transfer.json`. Prior JSON preserved.

Probe-and-continue **resumes** the VAL winner checkpoint. Normalization is an explicit mechanism (A–H, freeze vs update). Selectors include `rms_only` and a measured RMS-shift feature; LinUCB is fit on development VAL and scored on **held-out source seeds 4–9**. New confirmation suite `cartpole_v066_*` (eval 76000).

Confirmation (1 024 steps, n=10): **B 312 [263, 362]** vs A **90**; B−A **+222 [173, 272]**. D−B **−223 [−294, −152]**. Frozen vs updating RMS is inconclusive. Learned LinUCB always chose `rms_only` but did not beat fixed B (paired CI includes 0). Continual naive/replay/EWC/multi-head ACC ~80 with forgetting CIs including 0. Source still **0/10** solved; lr=1e-4 @ 16k **0/3** solved.

**V0.6 closed.** Do not add further V0.6 subversions. Not AGI. Not V0.7.

## V0.7 — world models and planning

Branch `cursor/v07-world-models-planning`. Write-up: `docs/NEXUS_V07.md`. `pytest` **119 passed**. Artifact `artifacts/v07_world_model.json`. V0.5/V0.6 JSON preserved.

Residual 2×64 MLP next-state MAE **0.00272** vs persistence **0.125** on 1024 held-out CartPole transitions. Multi-step MAE grows 0.002→0.020 over 1–20 steps. Random-shooting MPC (model only) **325 [289, 362]** vs random **23.4** vs matched 4096-step PPO **111 [88, 133]** vs heuristic **500**. Uncertainty-penalized MPC **448 [420, 476]**; ensemble error–std corr 0.72, **not** claimed calibrated. Target-physics scratch planning fails (65); source model still plans (288). Source RMS without dynamics weights does not help (V0.6 control, negative here).

Not AGI. PREDICT/PLAN only on CartPole.

## V0.7.1 — planning validation

Branch `cursor/v071-planning-validation`. Write-up: `docs/NEXUS_V071.md`. `pytest` **125 passed**. Artifact `artifacts/v071_world_model.json`. Prior JSON preserved.

Val-only selection froze **ridge** (test MAE 1.05e-4 vs residual 0.0037, n=10). Ridge one-step greedy **246**; ridge MPC **9.3** (paired −237). Residual MPC vs greedy **+5.6 [−159, +171]** (no planning gain). Uncertainty penalty vs ensemble-zero **+76 [−31, +183]** (not superior). Ridge terminate Brier worse than always-nonterminal. Fine-tune still lowers one-step MAE and can raise 20-step error. Matched PPO 2560-step **74** vs residual greedy **283**. Not AGI.

## V0.7.2 — planning reliability

Branch `cursor/v072-planning-reliability`. Write-up: `docs/NEXUS_V072.md`. `pytest` **130 passed**. Artifact `artifacts/v072_world_model.json`. Prior JSON preserved.

MPC now uses a **persistent RNG** with episode reset. V0.7.1 ridge return **9** was from re-sampling the same candidates every step. With the fix, ridge H=6 **446 [387, 505]** vs greedy **317**; residual H=6 − greedy **+78 [47, 108]**. Horizon 3 at budget 48 is strongest (residual **500**); H=10–20 collapse from **too few candidates**, not terminate-model isolation (always-live vs learned CI includes 0). Uncertainty penalty **−5.6 [−33, +22]**. Not AGI.

## V0.7 final confirmation — track closed

Branch `cursor/v073-planning-final`. Write-up: `docs/NEXUS_V07_FINAL.md`. `pytest` **134 passed**. Artifact `artifacts/v073_world_model.json`. V0.6 and earlier V0.7 JSON preserved.

Frozen H=3 residual recipe, eval seed **87000**, three new physics tasks, n=10. Confirm H=3 **486 [485, 487]** vs greedy **260**; paired **+225 [206, 245]**. Source H=3 **500**. H=6 worse than H=3. Heuristic still 500; hardest confirm (g=13) H=3 **459**. Not retuned. Not V0.8. Not AGI.

## V0.8 — adaptive world models

Branch `cursor/v08-adaptive-world-model`. Write-up: `docs/NEXUS_V08.md`. `pytest` **144 passed**. Artifact `artifacts/v08_adaptation.json` (172 s, n=5). V0.6/V0.7 JSON preserved.

Frozen V0.7 residual+H=3 reused. Confirmation physics unused in V0.6/V0.7; eval seed **94000**; selection on `dev_v08` only. Fine-tune@128 confirmation MAE **0.0166 [0.0144, 0.0188]** vs frozen **0.0348**; scratch **0.0946** and planning **171** vs frozen **500** (paired −329). Frozen/fine-tune/replay H=3 already **500** on confirm — no control gain above ceiling. Page–Hinkley FPR/TPR CIs overlap; seed 3 missed B/C. Return-to-A shared MAE **0.0108** vs snapshot **0.0093** (overlap). Uncertainty collection MAE **worse** than random. Not AGI.

## V0.8.1 — prediction-to-control

Branch `cursor/v081-predictive-adaptation`. Write-up: `docs/NEXUS_V081.md`. `pytest` **150 passed**. Artifact `artifacts/v081_adaptation.json` (n=10, 431 s). Prior JSON preserved.

Non-saturated suite: `obs_noise_std=0.08` (weak force still sat at 500). Frozen confirm H=3 **290 [236, 343]**, fail 0.80. Window detector FPR **0** on clean source; delay 31 / miss 0 on noise and shift B. Fine-tune@128 MAE 0.094 vs frozen 0.101 but return **263 vs 290** (paired −26, CI includes 0). Scratch **−182**. Shared A→B→C→A return 184 vs snapshot 298. MAE≠control. Not AGI.

## V0.8.2 — belief states and gated adaptation

Branch `cursor/v082-belief-adaptation`. Write-up: `docs/NEXUS_V082.md`. `pytest` **156 passed**. Artifact `artifacts/v082_belief.json` (n=10, 323 s). Prior JSON preserved.

Dev returns: Kalman **243**, identity **224**, EMA 186, stack 55, GRU 20 (overlap Kalman/identity). Noisy confirm identity never **284**; gated 270; always 282 (paired CIs include 0). MAE gate committed 85% without helping control. Clean identity **500**; Kalman on clean **281** (filter hurts). Snapshot A **284** vs gated shared **236**. Target budgets enforced. Not AGI.

## V0.8.3 — decision-aware learning

Branch `cursor/v083-decision-aware-learning`. Write-up: `docs/NEXUS_V083.md`. `pytest` **161 passed**. Artifact `artifacts/v083_learning.json` (n=10, 306 s). Prior JSON preserved.

Online step loop; ledger `bucket_sum==target_used`; GRU excluded from MPC. Noisy confirm never **225**; MAE **237** (paired +12, CI includes 0); always harmful-commit **0.50**, MAE **0.35**, action/control **0.00** (they almost never commit). Continual naive shared **116** vs snapshot/control-gate **286**. No control gain vs never. Not V0.9. Not AGI.

## V0.8.4 — fair adaptation verification

Branch `cursor/v084-fair-adaptation-verification`. Write-up: `docs/NEXUS_V084.md`. `pytest` **175 passed**. Artifact `artifacts/v084_verification.json` (n=10, 267 s). Prior JSON preserved.

Matched H=32 MPC incumbent vs candidate; both charged to `online_val`; observe-once; disjoint one-episode splits; harm N/A if no accepts. Dev selected **MAE**. Noisy confirm@128 never **230.7**; MAE **231.4** (paired +0.7, CI includes 0); always +2.5 (CI includes 0); `control_fair` **0 accepts**, all proposals `tie_or_small_diff`, return identical to never. Clean confirm **500**. Continual naive **147** vs snapshot **247**. Engineering OK; scientific adaptation **not** shown. Not V0.9. Not AGI.

## V0.8.5 — candidate quality and verification

Branch `cursor/v085-candidate-quality-verification`. Write-up: `docs/NEXUS_V085.md`. `pytest` **188 passed**. Artifact `artifacts/v085_verification.json` (n=10, 89.5 s). Prior JSON preserved.

Fixed candidate bank; long-horizon reference (H=500 × 2) never feeds the gate. Noisy 40 pairs: **23 benefit / 15 harm / 2 inconclusive**; seed-mean Δ **+41.9 [−7.3, +91.1]** (includes 0). H=32 still 32 vs 32 on all 40 noisy. Dev selected **MAE**. Confirm MAE choice vs never **+50.5 [8.7, 92.2]** (excludes 0); 22 benefit / 6 harm accepted. H=128 still ~92% ceiling. Not a new env family. Not AGI.

## V0.8.6 — safer candidate generation

Branch `cursor/v086-safe-candidate-generation`. Write-up: `docs/NEXUS_V086.md`. `pytest` **196 passed**. Artifact `artifacts/v086_candidates.json` (n=10, 420 s). Prior JSON preserved.

Matched data; MAE 0.97 frozen. Dev selected **low_lr**. Noisy confirm: low_lr harm **0.25** vs finetune **0.60**; benefit 17 vs 14. MAE|accept harm **1/16**. MAE choice vs never **+5.6 [−2.7, +13.8]** (includes 0). Online A→B→C→A MAE accepted **0** updates (tied with never/snapshot **241**); always **214**. Not AGI.

## V0.8.7 — online learning bridge

Branch `cursor/v087-online-learning-bridge`. Write-up: `docs/NEXUS_V087.md`. `pytest` **203 passed**. Artifact `artifacts/v087_online.json` (n=10, 183 s). Prior JSON preserved.

Ablation: V0.8.6-style 64/32 split MAE accept **0**; bank and online 128/64 both **0.10**. Frozen **matched_sizes**. Confirm MAE+low_lr accept **0.25**, Δ vs never **+7.5 [−3.5, +18.5]** (includes 0). Always-adapt **−14**. Not AGI.

## V0.8.8 — genuine continual online learning

Branch `cursor/v088-continual-online-learning`. Write-up: `docs/NEXUS_V088.md`. `pytest` **214 passed**. Artifact `artifacts/v088_online.json` (n=10, 238 s). Prior JSON preserved.

Frozen MAE 0.97, 128/64, cap **672**, 3 alarm-triggered cycles. Factorial pool ablation: all cells accept **0**. Detector FPR **0**, delay **32**, miss **0**. Confirm MAE+low_lr mean accepts **0.95**/3, Δ **+3.3 [−34.9, +41.6]** (includes 0). Always **+3.8** (includes 0); finetune **−44**. Probe retrieval matched gated-shared, not better than never on A-return. Not AGI.

## V0.8.9 — learning efficiency and persistent online control

Branch `cursor/v089-learning-efficiency`. Write-up: `docs/NEXUS_V089.md`. `pytest` **224 passed**. Artifact `artifacts/v089_learning.json` (n=10, 221 s). Prior JSON preserved.

Persistent episodes; detector FPR **0**, delay **31**, miss **0**. MAE-gated **4 proposes / 0 accepts**. Frozen return **384** vs scratch **43**; low_lr/replay CIs vs frozen include 0. ABC-then-D vs naive **0**. Past experience did not improve learning efficiency. Not AGI.

## Research checkpoint (after V0.8.9)

Branch `cursor/v089-research-checkpoint`. Write-ups: `docs/NEXUS_RESEARCH_CHECKPOINT.md`, `docs/NEXUS_HYPOTHESIS_REGISTER.md`, `docs/NEXUS_NEXT_EXPERIMENT.md`. `pytest` **230 passed**. MAE audit `artifacts/v089_mae_audit.json` (40 proposals, 0 accepts, mean gate ratio **0.996**, control Δ **−2.7** includes 0). Did not retune 0.97. Recommended next: frozen WM+MPC on a **second env family**, not another CartPole MAE iteration. Not AGI.

## Cross-environment (Pendulum-v1)

Branch `cursor/v089-cross-environment-test`. Write-up: `docs/NEXUS_CROSS_ENVIRONMENT.md`. `pytest` **238 passed**. Artifact `artifacts/cross_environment.json` (n=10, 17 s).

Frozen residual 64×64, H=3, 16 candidates, 3 torques {−2,0,+2}, Gymnasium reward. Tensors incompatible with CartPole (no weight transfer). MPC **−1053** vs random **−1196**, paired **+143 [−84, +370] includes 0**. H1 not supported. Heuristic **−1114**. PPO@16k **−1461** (worse than random). Not learning-to-learn. Not AGI.

## Planning-generality diagnostic

Branch `cursor/planning-generality-diagnostic`. Write-up: `docs/NEXUS_PLANNING_GENERALITY.md`. Artifact `artifacts/planning_generality.json` (dev n=5, confirm n=10, wall **95.4 s**). `pytest` **244 passed**. Prior `cross_environment.json` hash `402ce4151837eb0d` preserved.

Dev horizon grid (architecture frozen): H=3 learned **−1358** (worse than random **−1091**); selected **H=16 × 16** **−621**. Simulator oracle (dev only) H=16 **−128**. Confirm new g={8.3,12.1}: selected **−649** vs random **−1173**, Δ **+524 [443, 605]** excludes 0. CartPole H=3 still **500**. Not weight transfer. Not L2L. Not AGI.

## Pendulum adaptation and transfer

Branch `cursor/pendulum-adaptation-transfer`. Write-up: `docs/NEXUS_PENDULUM_TRANSFER.md`. Artifact `artifacts/pendulum_transfer.json` (n=10, wall **1167 s**). `pytest` **250 passed**. Prior hashes preserved.

Frozen H=16 residual. Confirm mean over g/m/l shifts: MAE-gated vs frozen **+29 [−28, +86] includes 0** (primary **fail**). Always-adapt **+211 [134, 288]**; low-LR **+106 [39, 173]**. Scratch worse. A→B→C vs naive D **+22 includes 0**; vs matched volume **−6 includes 0**. Not L2L. Not AGI.

## Meta-learning pilot (Reptile vs multitask)

Branch `cursor/meta-learning-pilot`. Write-up: `docs/NEXUS_META_LEARNING_PILOT.md`. Artifact `artifacts/meta_learning_pilot.json` (n=10, wall **2300 s**). `pytest` **255 passed**. Prior hashes preserved.

Dev-selected **film** (5828 params). Confirm: multitask final **−491** vs source **−597**; Reptile **−1120** (≈ scratch). Reptile − multitask AUC **−765k [−857k, −672k]** (Reptile worse). Multitask − source AUC **+163k** excludes 0 (pooled data, not L2L). Not AGI. That Reptile result is for this configuration, not a general disproof.

## Context-adaptation pilot

Branch `cursor/context-adaptation-pilot`, starting SHA `a9c184c`. Write-up: `docs/NEXUS_CONTEXT_ADAPTATION_PILOT.md`. Development artifact `artifacts/context_adaptation_dev.json` (2 seeds, wall **313 s**). `pytest` **260 passed**. Confirmation artifact was not created. Prior artifacts preserved.

FiLM transition context, trunk (48, 48), 4332 parameters, vs residual MLP (64, 64), 4868 parameters. Development primary AUC: fine-tune **−454**, zero context **−652**, real context **−755**. Gate means: real−fine-tune **−302**, real−zero **−103**, real−wrong **−30**. Encoder weights moved (L2 Δ **1.52**) and still hurt control. H1 confirmation **not run** (inconclusive). Not AGI.

## Context-adaptation diagnosis

Branch `cursor/context-adaptation-diagnosis`. Write-up: `docs/NEXUS_CONTEXT_ADAPTATION_DIAGNOSIS.md`. Artifact `artifacts/context_adaptation_diagnosis.json` (3 seeds, wall **521 s**). Confirmation physics were not evaluated. The original development artifact is preserved.

Fixed-length real context did not beat zero context on held-out source MAE (**0.0703** vs **0.0700** at budget 128) and raised development MAE (**0.084** vs **0.077**). The 0–128 control AUC interval for variable-minus-fixed length includes 0 (point estimate **+22**). Zero-context control remains about **146** points below the frozen MLP. Not AGI.

## Context optimization diagnostic

Branch `cursor/context-optimization-diagnostic`. Write-up: `docs/NEXUS_CONTEXT_OPTIMIZATION_DIAGNOSTIC.md`. Selection and audit artifacts are separate. Wall **17.4 s**. No control sweep and no confirmation.

The first 300 updates reproduce the diagnosis. Real-context angular velocity on the selection set fell from **0.150** at 300 updates to **0.136** at 3000, and zero context fell further, to **0.126**. The independent audit at the selected 3000-update checkpoint has real **0.1264** versus zero **0.1256** and wrong **0.1234**. The screen failed. More training improved the shared dynamics. It did not make real context useful. Not AGI.

## Frozen-dynamics context diagnostic

Branch `cursor/frozen-dynamics-context-diagnostic`. Write-up: `docs/NEXUS_FROZEN_DYNAMICS_CONTEXT.md`. Selection and audit artifacts are separate. Wall **10.3 s**. No control sweep and no confirmation.

The trunk, heads, and normalization of the 3000-update context model stayed fixed. Encoder and FiLM training moved the encoder (L2 **1.60–2.32**) and still failed the fresh source audit: real angular velocity **0.1484** versus zero **0.1159**, wrong **0.1207**, and a constant vector **0.1127**. The fixed MLP reference was **0.1149**. The screen failed. Not AGI.

## Direct latent context diagnostic

Branch `cursor/direct-latent-context-diagnostic`. Write-up: `docs/NEXUS_DIRECT_LATENT_CONTEXT.md`. Selection and audit artifacts are separate. Execution SHA `d037ffda2fb34238411f39c82d64ff5812b98810`. Wall **29.3 s**. No control sweep and no confirmation.

With the history decoder frozen, a latent fit only on 128 new support transitions (Adam **0.1**, **256** steps, from a global training vector) reached fresh-audit angular velocity **0.0628** versus zero **0.1151**, global **0.1109**, and wrong-support **0.1762**. Paired intervals exclude 0. The frozen encoder on those same rows stayed at **0.1256**. The external MLP reference was **0.1141**. The source screen passed. This is source-physics prediction, not unseen physics and not control. Not AGI.

## Direct latent unseen-physics confirmation

Branch `cursor/direct-latent-confirmation`. Write-up: `docs/NEXUS_DIRECT_LATENT_CONFIRMATION.md`. Artifact `artifacts/direct_latent_confirmation.json`. Execution SHA `aac5e33d677f05fc57e9191bd522e82982e3ef20`. Wall **5.2 s**. No control sweep.

The same locked rule, on confirmation physics hash `87b83c41be34aa1a`, reached angular velocity **0.152** versus zero **0.308**, global **0.314**, and wrong-support **0.398**. Paired intervals exclude 0. All four tasks met the 5% point bar. The low-mass task stayed at **0.335**. The frozen encoder stayed at **0.307**. The screen passed for this physics set. Not amortized inference, not control, and not AGI.

## Amortized latent inference

Branch `cursor/amortized-latent-inference`. Write-up: `docs/NEXUS_AMORTIZED_LATENT_INFERENCE.md`. Artifact `artifacts/amortized_latent_dev.json`. Implementation SHA `29931126df34da0064a67fd3b8a239c673412f72`. Wall **230 s**. No confirmation and no control sweep.

The existing encoder was trained to match support-fit teacher latents. The best development cell was distillation only, epoch 120, 128 support rows: angular velocity **0.1747** versus zero **0.1587** and the frozen encoder **0.1773**. The paired gap versus zero excludes 0 in the wrong direction. The teacher on the same frozen decoder was **0.0781**. All 48 grid cells lost to zero context. The new physics hash `d1fa621351d286cf` was not collected. Not learning-to-learn and not AGI.

## Encoder representability

Branch `cursor/encoder-representability-diagnostic`. Write-up: `docs/NEXUS_ENCODER_REPRESENTABILITY.md`. Artifact `artifacts/encoder_representability.json`. Implementation SHA `76c1e4aa87a611217288de15ccc59544689ff9da`. Wall **19.0 s**. No confirmation and no control sweep.

The same 584-parameter encoder, trained at learning rate **0.01** for 2000 full-batch steps, reproduced the eight saved meta-training teachers. Mean latent distance was **0.0074, 0.0021, and 0.000024**, against constant baselines **1.31, 1.75, and 1.51**. Rate 0.001 missed the threshold. A second support of the same task did not reproduce the saved code. This is a training-set fit, not generalization and not AGI.

## Latent encoder generalization

Branch `cursor/latent-encoder-generalization`. Write-up: `docs/NEXUS_LATENT_GENERALIZATION.md`. Artifact `artifacts/latent_generalization_dev.json`. Implementation SHA `fd1e864cb2e1dff91e73bf35b184becc4c81be22`. Wall **51.2 s**. No confirmation and no control sweep.

The same encoder, trained at learning rate **0.01** on twelve new physics with two support-specific teachers each, reached development angular velocity **0.0913** versus zero **0.1587**, the frozen encoder **0.1773**, a global vector **0.1478**, and the direct teacher **0.0781**. The eight-task baseline at the same epoch was **0.1672**. Paired intervals exclude 0. The validation mean was **0.0832** versus zero **0.0972**. Training latent distance stayed **0.648**, and a held-out support of the same training physics stayed at **1.752**. One validation physics is worse than zero context. Not learning-to-learn and not AGI.

## Latent generalization confirmation

Branch `cursor/latent-generalization-confirmation`. Write-up: `docs/NEXUS_LATENT_GENERALIZATION_CONFIRMATION.md`. Artifact `artifacts/latent_generalization_confirmation.json`. Implementation SHA `4da390da236c2b8fb172bcbc13c65ebce6aae9da`. Wall **56.5 s**. No control sweep.

The retrained encoder matched the development artifact exactly, then scored four new physics (hash `baa655fcb94e61bc`). Confirmation angular velocity was **0.1016** versus zero **0.2729**, the frozen encoder **0.2660**, and a global vector **0.2742**. Decoder-level paired gaps were **+0.171 [+0.136, +0.207]**, **+0.164 [+0.156, +0.173]**, and **+0.173 [+0.133, +0.213]**. The direct teacher was **0.0876**, and that interval includes 0. Latent distance stayed **1.558**. All four tasks cleared the three primary controls. Not learning-to-learn and not AGI.

## Latent context control

Branch `cursor/latent-context-control`. Write-up: `docs/NEXUS_LATENT_CONTROL.md`. Artifact `artifacts/latent_control.json`. Implementation SHA `9506604ba1aae853d8be3421d87b9e9477a9b5a4`. Wall **569.5 s**.

The same epoch-200 encoder in the frozen H=16 controller returned **−683.0** versus zero **−768.4** and the frozen encoder **−773.2**. Decoder-level intervals **+85.4 [−109.4, +280.3]** and **+90.2 [−5.7, +186.1]** both include 0. The result is inconclusive. The direct teacher returned **−682.4**. Not a control improvement, not learning-to-learn, and not AGI.

A ten-decoder replication on new episodes of those physics returned **−636.4** versus zero **−708.6** and the frozen encoder **−699.2**, with gaps **+72.2 [+45.6, +98.8]** and **+62.8 [+31.3, +94.3]**. The same controllers on disjoint physics returned **−716.0** versus zero **−696.6**, gap **−19.4 [−35.4, −3.3]**. Negative transfer. Not learning-to-learn and not AGI.

## Prediction-to-control gap

Branch `cursor/prediction-control-gap-diagnostic`. Write-up: `docs/NEXUS_PREDICTION_CONTROL_GAP.md`. Artifact `artifacts/prediction_control_gap.json`. Implementation SHA `a1f192e2be254c5511774254ee613a3597e3148c`. Wall **29.6 s**.

On new states of the fresh physics, candidate one-step angular velocity improved by **0.1148 [0.1030, 0.1266]**, shared-candidate regret by **1.313 [0.507, 2.118]**, and H=16 reward-forecast error by **6.386 [5.450, 7.322]**. The previous physics moved in the same direction. The closed fresh episode loss remains. Not a control improvement, not learning-to-learn, and not AGI.

## Receding-horizon diagnostic

Branch `cursor/receding-horizon-diagnostic`. Write-up: `docs/NEXUS_RECEDING_HORIZON_DIAGNOSTIC.md`. Artifact `artifacts/receding_horizon_diagnostic.json`. Implementation SHA `b6a079bab98c965b65a127e90a178a73ddcbb7f2`. Wall **784.6 s**.

On states the existing controllers visit, fresh one-shot regret changed by **0.812 [−0.038, 1.662]** and the matched next-16 continuation by **−0.528 [−1.139, 0.083]**. Both intervals include 0. Selected-sequence score error still fell by **4.751 [3.023, 6.480]**. Live replay matched **1920/1920** decisions. The fresh decision is inconclusive. The previous physics agrees locally with its closed positive return. The next-16 sum is not a 200-step value. Not a control improvement, not learning-to-learn, and not AGI.

## Return-phase decomposition

Branch `cursor/return-phase-decomposition`. Write-up: `docs/NEXUS_RETURN_PHASE_DECOMPOSITION.md`. Artifact `artifacts/return_phase_decomposition.json`. Implementation SHA `cf1e81b07011c6e4a45039dba38a7b9dafb2d734`. Wall **774.2 s**.

On new fresh-physics episodes the student-minus-zero return was **−30.671 [−41.540, −19.801]**. Steps 0–15 were **−1.230 [−2.583, 0.123]** and include 0. Steps 16–199 were **−29.441 [−40.706, −18.175]**. The locked label is `primarily_late`. This does not remeasure the closed episode seeds. Not a control improvement, not learning-to-learn, and not AGI.
