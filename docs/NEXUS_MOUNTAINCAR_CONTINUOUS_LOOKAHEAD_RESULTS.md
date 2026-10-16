# MountainCarContinuous lookahead versus frozen H=16 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) development grid completed. Label: `mountaincar_continuous_lookahead_established`.

Lookahead minus frozen H=16 dense valley-height return: **69.758 [29.321, 110.196]**. The mean is at least 25 and the lower bound is above 0, so the registered improvement rule **passes**.

This is not the Gymnasium MountainCarContinuous-v0 sparse +100 / action-cost benchmark. Dense valley height `sin(3 * position)`, 200-step TimeLimit, no goal termination. Force is discretized to `{-1, 0, +1}` scaled by `power`. Discrete MountainCar unused. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. Lookahead used 771 imagined states per step versus 256 for H=16; there is no compute-matched control.

Do not retune H=16, candidates, or the dense height from this development sample.

## What was tested

Holdout `d247d7921d6afff7`: (0.0038, 0.0019, 0.085), (0.0024, 0.0019, 0.09), (0.0033, 0.0014, 0.05). Ten residual 2×64 MLPs trained with the frozen residual recipe on `mcc_default`. Shared 16×16 candidates, 3 actions, `mountaincar_step_reward`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

H=16 mean **−81.407 [−104.743, −58.070]**. Lookahead mean **−11.648 [−50.876, 27.579]**. Every episode ran 200 steps.

Per-task return_gain:

- task0: **91.578 [50.823, 132.333]**
- task1: **71.566 [3.844, 139.288]**
- task2: **46.131 [−10.184, 102.445]**

Seed means: 117.7, 85.1, 87.9, 17.8, 41.6, 188.2, 10.1, 93.4, 47.6, 8.3. All ten seeds are positive.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `pendulum_weights` false. `cartpole_h3` false. `mountaincar_copy` false. Training epochs 200. 24,800 real steps (exact cap). 6,162,000 imagined (exact cap). Retries: 0.

## Provenance

Branch `cursor/mountaincar-continuous-lookahead-h16`. Preparation SHA **9e9e6d85e9d9296fdf01db6c229e73a3034e8599**. One-run SHA **54492ff1c876d2603719fc7513a1682706fe6d0b**.

- Config SHA256 `4ea518200f94cdd4f5994baa943afd1ee6dcf688701264d86b29614ff6eae02c`
- Protocol SHA256 `9c998dab8030e2fd7605c48efcca4fb26a05f4f27245b09faff1153b69be5b23`
- Raw artifact SHA256 `668a9a85e121d82a830399e9c967765e3f507e9ab062195e3dee3f9dc1b49a15`

Execute **26.884 s**, process **27.74 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or the dense height from this development sample. A later distinct question is lookahead versus frozen H=16 on a **new unused MountainCarContinuous confirmation holdout**. That proposal is not implemented and is not authorized here. This is not discrete MountainCar confirmation, not learning-to-learn, and not AGI.
