# Acrobot lookahead versus compute-matched H=16 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) compute-matched grid completed. Label: `acrobot_compute_matched_lookahead_not_established`.

Lookahead minus 48-candidate H=16 dense-height return: **12.834 [3.815, 21.853]**. The lower bound is above 0, but the mean is below the registered 25-point practical margin, so the improvement rule **does not pass**.

The leftover positive interval does not isolate a compute-free Bellman backup. Extra H=16 search (768 imagined states per step versus the original 256) closed most of the earlier 16-candidate gap on these physics (development +27.914). Do not retune H=16, the 16-candidate lookahead successor, or the dense height from this sample.

Confirmation physics unused. Frozen development checkpoints were read-only. CartPole H=3 unused. Pendulum FiLM unused.

## What was tested

Development split `911ea726b6ed2111` with fresh resets `24000000+`. Ten residual 2×64 MLPs loaded from `checkpoints/acrobot_lookahead_h16`. Arm A scored 48 prefix-stable H=16 candidates (768/step). Arm B kept the frozen 16-candidate one-step backup (771/step). Dense upright height, 200-step TimeLimit, no goal termination. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

Matched H=16 mean **−262.109 [−286.177, −238.040]**. Lookahead mean **−249.275 [−271.724, −226.825]**. Every episode ran 200 steps.

Per-task return_gain:

- task0: **15.705 [−7.347, 38.758]**
- task1: **4.880 [−8.072, 17.832]**
- task2: **17.916 [9.805, 26.026]**

Seed means: 9.9, 1.2, 28.3, 20.6, 10.0, 5.3, −6.3, 36.2, 10.2, 12.9. Two seeds clear +25; one is negative.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `retune_from_confirmation` false. `pendulum_weights` false. `cartpole_h3` false. Training updates 0. 12,000 real steps (exact cap). 9,234,000 imagined (exact cap). Retries: 0. Ten frozen checkpoint hashes matched.

## Provenance

Branch `cursor/acrobot-compute-matched-h16`. Preparation SHA **5cd0c2734b755633aee2d6883c2d438477bbd733**. One-run SHA **1b0620090e83ab7aa107f2986236dcbe12437c29**.

- Config SHA256 `530fc209dc3b8bef360fac3d112068f110915a99fd0a355ebbd2a2eb68950453`
- Protocol SHA256 `e9804af7d07cefe74348415f88ca81ea1bfcc38269f5f1ab3da3edd46ac1f874`
- Raw artifact SHA256 `ed99327d3a0f8be9501df13619957b416268ae3f3dfaa36676f93c51e256bcc2`

Execute **29.728 s**, process **30.706 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or the dense height from this sample. The unmatched 16-candidate package still transferred on Pendulum and Acrobot; this screen did not establish that the backup beats extra search on Acrobot. A later distinct question is the same compute-matched contrast on **Pendulum development physics**, where the unmatched gap was larger. That proposal is not implemented and is not authorized here. This is not learning-to-learn or AGI.
