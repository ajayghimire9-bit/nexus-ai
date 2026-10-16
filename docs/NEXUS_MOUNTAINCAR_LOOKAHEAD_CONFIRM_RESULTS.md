# MountainCar lookahead versus frozen H=16 transfer — complete confirmation screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) confirmation grid completed. Label: `mountaincar_lookahead_transfer_established`.

Lookahead minus frozen H=16 dense valley-height return: **50.366 [36.493, 64.239]**. The mean is at least 25 and the lower bound is above 0, so the registered transfer rule **passes**.

This is not the Gymnasium MountainCar-v0 −1/step benchmark. Dense valley height `sin(3 * position)`, 200-step TimeLimit, no goal termination. Development physics `2a5cc4979642cc2a` were not reused. H=16, candidates, and the dense height were not retuned. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. Lookahead used 771 imagined states per step versus 256 for H=16; there is no compute-matched control.

Do not retune from this confirmation sample.

## What was tested

Holdout `bf4b4412f4f683dd`: (0.0031, 0.0007, 0.09), (0.0022, 0.0014, 0.085), (0.0037, 0.0014, 0.07). Ten residual 2×64 MLPs trained with the frozen residual recipe on `mountaincar_default` with new collect seeds. Shared 16×16 candidates, 3 actions, `mountaincar_step_reward`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

H=16 mean **−113.113 [−122.427, −103.798]**. Lookahead mean **−62.747 [−79.405, −46.088]**. Every episode ran 200 steps.

Per-task return_gain:

- task0: **28.998 [11.250, 46.745]**
- task1: **62.325 [39.733, 84.917]**
- task2: **59.775 [26.927, 92.624]**

Seed means: 54.6, 47.6, 49.2, 62.6, 32.7, 59.8, 51.5, 32.0, 22.3, 91.4. All ten seeds are positive.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `retune_from_development` false. `pendulum_weights` false. `cartpole_h3` false. `acrobot_copy` false. Training epochs 200. 24,800 real steps (exact cap). 6,162,000 imagined (exact cap). Retries: 0.

## Provenance

Branch `cursor/mountaincar-lookahead-h16-confirm`. Preparation SHA **b8249bf25b84c9313af034655c45691561f4956c**. One-run SHA **1380e0aad55142bf4909955c122b1c2ab576f0f4**.

- Config SHA256 `80675aadd0b5d31b539ba027263df258a72f94bbad5a4a54ed03f28490a80229`
- Protocol SHA256 `8f2b4f698198177785476a2b839e8dc2cb68cc4c134b0461d15196af22acc7dd`
- Raw artifact SHA256 `bbf22c1717cc82a7140d3728c9a0fa1101d0d5946ebedb447d96012080b81678`

Execute **27.013 s**, process **27.82 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or the dense height from this confirmation sample. A later distinct question is a **compute-matched** control of the same frozen MountainCar package, because lookahead still uses 771 imagined states per step versus 256 for H=16. That proposal is not implemented and is not authorized here. This is not learning-to-learn or AGI.
