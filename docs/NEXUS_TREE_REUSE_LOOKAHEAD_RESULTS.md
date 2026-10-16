# Tree-reuse lookahead versus frozen H=16 — complete development screen

## Registered decision

The locked 90-episode (10 training seeds × 3 tasks × 3 arms) grid completed. Label: `tree_reuse_lookahead_not_established`.

Tree-reuse minus 16-candidate H=16 dense valley-height return: **−14.751 [−37.142, 7.641]**. The mean is below 25 and the interval includes 0, so the registered improvement rule **does not pass**. This is a valid, complete, inconclusive-to-negative decision result. It is not a timeout and not an equivalence claim.

Nearest remaining open-loop height from the current-step H=16 tree did not keep the MountainCar 25-point remainder at 259 imagined states per step. Closed unmatched, confirmation, and compute-matched MountainCar labels stay closed. Frozen development checkpoints were read-only. Confirmation unused.

Do not retune H=16, the 16-candidate successor, or the dense height from this sample. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. MountainCarContinuous unused. No fitted critic.

This is not learning-to-learn or AGI.

## What was tested

Development split `2a5cc4979642cc2a` with fresh resets `29000000+`. Ten residual 2×64 MLPs loaded from `checkpoints/mountaincar_lookahead_h16`. Arm A scored 16-candidate H=16 from `s` (256/step). Arm B cached remaining open-loop height along that tree and backed up nearest Euclidean neighbor at `s'` (259/step). Arm C kept the frozen 16-candidate one-step backup from `s'` (771/step) as a diagnostic. Dense valley height, 200-step TimeLimit, no goal termination. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

H=16 mean **−124.311 [−136.320, −112.301]**. Tree-reuse mean **−139.061 [−162.293, −115.829]**. Lookahead mean **−50.373 [−69.424, −31.322]**. Every episode ran 200 steps.

Lookahead minus tree-reuse: **88.688 [61.818, 115.558]**. Lookahead minus H=16 on this fresh-seed draw: **73.938 [50.255, 97.620]**. Those diagnostics cannot revive the primary screen and cannot retune the closed 16-candidate MountainCar labels.

Mean nearest-neighbor distance: **0.000002 [0.000001, 0.000003]**. Successor states landed on the cached tree. The miss is therefore not an off-manifold interpolator; nearest remaining is not max successor H=16 height.

Per-task tree-reuse minus H=16:

- task0: **−13.412 [−17.782, −9.042]**
- task1: **−13.917 [−58.722, 30.888]**
- task2: **−16.923 [−49.190, 15.345]**

Seed means: 2.6, −17.6, 2.0, −57.1, −39.4, 33.8, −51.6, 15.2, −42.3, 6.8. Five of ten seeds are positive.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `retune_from_confirmation` false. `fitted_critic` false. `pendulum_weights` false. `cartpole_h3` false. Training updates 0. 18,000 real steps (exact cap). 7,716,000 imagined (exact cap). Retries: 0. Ten frozen checkpoint hashes matched.

## Provenance

Branch `cursor/lookahead-generalization-synthesis`. Preparation SHA **cabf4eab4cee31d8aeaaa83f76aa021aa0fa6fdb**. One-run SHA **3eb3275371740e72e10f727b51376463e8672797**.

- Config SHA256 `5d85db5bbab131f1bcb7f9a51b96aef4254753e14325713be34e5af5afc40451`
- Protocol SHA256 `fdaf615cef38209afcaf3a199c8094a41df2ad798a8920ffd957142d5c0b5500`
- Allocation SHA256 `d1983a92f69085ac82b7a4b7ccc9d8ef1c2a8fd29f27a6c9b790d866bf5359a6`
- Raw artifact SHA256 `dbc22d0365e7e747e7c3e3e9477c1be635d48814d6b887a5e3382cfc43d2b6d5`

Execute **34.065 s**, process **35.30 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, fit another Q, or reopen confirmation. The 771-step backup still beats H=16 on this draw, while nearest remaining does not. A later distinct question is **prefix-max tree reuse**: `V(s'|a)` = max remaining at cached t=1 nodes whose first action was `a` (still 259 imagined/step), versus 16-candidate H=16 on these frozen checkpoints with new seeds. That proposal is not implemented and is not authorized here. This is not learning-to-learn or AGI.
