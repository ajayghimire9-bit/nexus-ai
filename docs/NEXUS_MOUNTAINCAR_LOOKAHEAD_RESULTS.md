# MountainCar lookahead versus frozen H=16 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) development grid completed. Label: `mountaincar_lookahead_established`.

Lookahead minus frozen H=16 dense valley-height return: **44.092 [13.945, 74.239]**. The mean is at least 25 and the lower bound is above 0, so the registered improvement rule **passes**.

This is not the Gymnasium MountainCar-v0 −1/step benchmark. Dense valley height `sin(3 * position)`, 200-step TimeLimit, no goal termination. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. Lookahead used 771 imagined states per step versus 256 for H=16; there is no compute-matched control.

Do not retune H=16, candidates, or the dense height from this development sample.

## What was tested

Holdout `2a5cc4979642cc2a`: (0.0035, 0.0006, 0.075), (0.0025, 0.0013, 0.07), (0.0015, 0.0013, 0.085). Ten residual 2×64 MLPs trained with the frozen residual recipe on `mountaincar_default`. Shared 16×16 candidates, 3 actions, `mountaincar_step_reward`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

H=16 mean **−100.470 [−121.728, −79.212]**. Lookahead mean **−56.378 [−79.555, −33.201]**. Every sampled episode in the first cell ran 200 steps.

Per-task return_gain:

- task0: **24.739 [4.522, 44.956]**
- task1: **76.041 [39.624, 112.458]**
- task2: **31.495 [−34.616, 97.606]**

Seed means: 74.8, 31.5, 60.6, 21.1, 13.9, 144.5, −0.4, 23.8, 52.3, 18.9. One seed is slightly negative; the pooled rule still passes.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `pendulum_weights` false. `cartpole_h3` false. `acrobot_copy` false. Training epochs 200. 24,800 real steps (exact cap). 6,162,000 imagined (exact cap). Retries: 0.

## Provenance

Branch `cursor/mountaincar-lookahead-h16`. Preparation SHA **b9fca91c364376b291ae5e985fdf95fbcdfd9756**. One-run SHA **55957b41e9cfea66544c832354e69163b143f6bc**.

- Config SHA256 `9e4f9cf8b92cbb5e54d9a17b20c1518aae9f925e490930cd4b958ec7885e97f4`
- Protocol SHA256 `4f7ebc5f30755e80adecee9c930e9b888a006f1e5edca00d742a8caa3932d4bb`
- Raw artifact SHA256 `28e19af3e986a25bd094d9a271180002f85c03c2cb9bb655cfae52ab25fa78eb`

Execute **27.134 s**, process **28.189 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or the dense height from this development sample. A later distinct question is lookahead versus frozen H=16 on a **new unused MountainCar confirmation holdout**. That proposal is not implemented and is not authorized here. This is not CartPole confirmation, not Pendulum transfer, not learning-to-learn, and not AGI.
