# Acrobot lookahead versus frozen H=16 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) development grid completed. Label: `acrobot_lookahead_established`.

Lookahead minus frozen H=16 dense-height return: **27.914 [13.962, 41.867]**. The mean is at least 25 and the lower bound is above 0, so the registered improvement rule **passes**.

This is not the Gymnasium Acrobot-v1 −1/step benchmark. The registered reward is frozen upright height `-cos θ1 − cos(θ1+θ2)`, 200-step TimeLimit, no goal termination. Hang-down is about −2 per step. CartPole H=3 was not used. Pendulum FiLM weights were not loaded. Successor value remained open-loop H=16 height from `s'`. Lookahead used 771 imagined states per step versus 256 for H=16; there is no compute-matched control.

Do not retune horizon, candidates, or the dense height from this development sample.

## What was tested

Holdout `911ea726b6ed2111`: (0.95, 1.2, 0.8), (1.25, 1.35, 0.95), (0.75, 1.4, 1.4). Ten residual 2×64 MLPs trained with the frozen residual recipe on `acrobot_default`. Shared 16×16 candidates, 3 actions, `acrobot_step_reward`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

H=16 mean **−273.626 [−295.098, −252.154]**. Lookahead mean **−245.712 [−268.828, −222.596]**. Every episode ran all 200 steps.

Per-task return_gain:

- task0: **16.067 [−16.830, 48.964]** (includes 0)
- task1: **30.293 [12.867, 47.719]**
- task2: **37.382 [17.696, 57.068]**

Seeds 1, 6, and 9 had small positive gains (8.82, 3.59, 0.59). The 10-seed pooled rule still passes.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `pendulum_weights` false. `cartpole_h3` false. Training epochs 200. 24,800 real steps (exact cap). 6,162,000 imagined (exact cap). Retries: 0.

## Provenance

Branch `cursor/acrobot-lookahead-h16`. Preparation SHA **1d04be0cc049291da97c628b8b51faf579bef876**. One-run SHA **55b789afabe0c013883e6f8fb7399a627a707243**.

- Config SHA256 `3978b7e309f41339a56a2e6993bc48344f2bbf211baf88d3e86ce994ffa7122a`
- Protocol SHA256 `e2b83a21e89292e0aec5112c5456f56f82eb0d14d2b9548389ef8e79ed432567`
- Raw artifact SHA256 `83b9fbeeb2558cd47d41f44342411c5cf69cb0f6261138ee7f0f5d1e07a04e87`

Execute **27.797 s**, process **28.843 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or the dense height from this development sample. A later distinct question is lookahead versus frozen H=16 on a **new unused Acrobot confirmation holdout**. That proposal is not implemented and is not authorized here. This is not CartPole confirmation, not Pendulum transfer, not learning-to-learn, and not AGI.
