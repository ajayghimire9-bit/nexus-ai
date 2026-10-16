# Acrobot lookahead versus frozen H=16 transfer — complete confirmation screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) confirmation grid completed. Label: `acrobot_lookahead_transfer_established`.

Lookahead minus frozen H=16 dense-height return: **37.961 [21.106, 54.816]**. The mean is at least 25 and the lower bound is above 0, so the registered transfer rule **passes**.

This is not the Gymnasium Acrobot-v1 −1/step benchmark. Dense upright height, 200-step TimeLimit, no goal termination. Development physics `911ea726b6ed2111` were not reused. H=16, candidates, and the dense height were not retuned. CartPole H=3 unused. Pendulum FiLM unused. Lookahead used 771 imagined states per step versus 256 for H=16; there is no compute-matched control.

Do not retune from this confirmation sample.

## What was tested

Holdout `b309bd481fd8abcb`: (0.75, 0.6, 0.95), (1.3, 1.4, 1.4), (1.15, 0.85, 0.6). Ten residual 2×64 MLPs trained with the frozen residual recipe on `acrobot_default` with new collect seeds. Shared 16×16 candidates, 3 actions, `acrobot_step_reward`, time budget off. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

H=16 mean **−263.435 [−286.657, −240.213]**. Lookahead mean **−225.474 [−252.025, −198.923]**. Every episode ran 200 steps.

Per-task return_gain:

- task0: **39.493 [2.150, 76.837]**
- task1: **38.311 [22.385, 54.236]**
- task2: **36.079 [10.696, 61.462]**

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `retune_from_development` false. `pendulum_weights` false. `cartpole_h3` false. Training epochs 200. 24,800 real steps (exact cap). 6,162,000 imagined (exact cap). Retries: 0.

## Provenance

Branch `cursor/acrobot-lookahead-h16-confirm`. Preparation SHA **1145c00c82405c200a695bbde90cfdeb276be276**. One-run SHA **ca1765d4745aee193f22520123ab209e9d93bd93**.

- Config SHA256 `a87959767f30ca75f0acfc753476ce06fc12c86a324315cc0f910f4149586ab1`
- Protocol SHA256 `dcf9913397acad3e9229ff60aa4b169250892f38f87bc2f9366a3564bf1a6b67`
- Raw artifact SHA256 `435fdcf70c64cc79a47f4b36cd947051a24b4d4263afd0e38efb79b93ebcde5b`

Execute **28.083 s**, process **29.191 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or the dense height from this confirmation sample. A later distinct question is a **compute-matched** control of the same frozen Acrobot package, because lookahead still uses 771 imagined states per step versus 256 for H=16. That proposal is not implemented and is not authorized here. This is not learning-to-learn or AGI.
