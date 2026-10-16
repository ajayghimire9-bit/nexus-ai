# Prefix-max tree reuse versus frozen H=16 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) grid completed. Label: `prefix_max_tree_reuse_not_established`.

Prefix-max minus 16-candidate H=16 dense valley-height return: **−9.832 [−31.108, 11.445]**. The mean is below 25 and the interval includes 0, so the registered improvement rule **does not pass**. This is a valid, complete, inconclusive-to-negative decision result. It is not a timeout and not an equivalence claim.

Max remaining open-loop height at cached t=1 nodes whose first action matches `a` did not keep the MountainCar 25-point remainder at 259 imagined states per step. Prefix hit-rate was **0.999 [0.998, 0.999]**; the miss is not the missing-prefix fallback. Closed nearest-neighbor tree-reuse, unmatched, confirmation, and compute-matched MountainCar labels stay closed. Frozen development checkpoints were read-only. Confirmation unused.

Do not retune H=16, the 16-candidate successor, or the dense height from this sample. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused. MountainCarContinuous unused. No fitted critic. No 771 arm.

This is not learning-to-learn or AGI.

## What was tested

Development split `2a5cc4979642cc2a` with fresh resets `30000000+`. Ten residual 2×64 MLPs loaded from `checkpoints/mountaincar_lookahead_h16`. Arm A scored 16-candidate H=16 from `s` (256/step). Arm B cached the same tree and backed up max remaining at t=1 among sequences that started with `a` (259/step). Dense valley height, 200-step TimeLimit, no goal termination. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

Prefix-max remaining after `(s, a)` is a 15-step open-loop tail. Lookahead scores a fresh 16-step tree from `s'`. That horizon mismatch is part of the mechanistic gap; this screen does not isolate it.

## Secondary (cannot upgrade)

H=16 mean **−104.045 [−123.934, −84.157]**. Prefix-max mean **−113.877 [−131.569, −96.185]**. Every episode ran 200 steps.

Per-task prefix-max minus H=16:

- task0: **1.341 [−5.206, 7.889]**
- task1: **−17.041 [−44.462, 10.380]**
- task2: **−13.795 [−66.797, 39.208]**

Seed means: 17.2, −19.7, −9.0, −27.9, 11.0, −57.8, −28.5, 32.3, −39.1, 23.2. Four of ten seeds are positive.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `retune_from_confirmation` false. `fitted_critic` false. `lookahead_arm` false. Training updates 0. 12,000 real steps (exact cap). 3,090,000 imagined (exact cap). Retries: 0. Ten frozen checkpoint hashes matched.

## Provenance

Branch `cursor/prefix-max-tree-reuse-h16`. Preparation SHA **99bc584a668db188d527bb9dd509fbb919be5dc4**. One-run SHA **f9009477f4ec1e6c8b1abbcface177e592069905**.

- Config SHA256 `1d1a39c11076644fcc590fa378e0d19c3bff8ec68f4f92e078de894609daf440`
- Protocol SHA256 `7f7a3ca13b267d9873fa0d2339db6cd82e5c6f313239bc9835b4e057a5b6a634`
- Allocation SHA256 `8f6cef716eecfed4fb9caba7841bb729c22efecce3d36835e25354adb674ec04`
- Raw artifact SHA256 `87078ff2e7242b0bba8a7f43d371e320a3d2129484c7b5bbbd25e825843295cc`

Execute **13.762 s**, process **14.71 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, fit another Q, or try another reuse of the tree grown from `s`. Nearest remaining and prefix-max both failed the 25-point rule. The known MountainCar controller remains the 771-step successor backup. A later distinct question is lookahead versus frozen H=16 on a **new unused MountainCarContinuous confirmation holdout**. That proposal is not implemented and is not authorized here. This is not learning-to-learn or AGI.
