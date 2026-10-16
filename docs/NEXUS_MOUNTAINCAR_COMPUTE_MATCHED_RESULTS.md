# MountainCar lookahead versus compute-matched H=16 — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 3 tasks × 2 arms) compute-matched grid completed. Label: `mountaincar_compute_matched_lookahead_established`.

Lookahead minus 48-candidate H=16 dense valley-height return: **54.649 [26.611, 82.686]**. The mean is at least 25 and the lower bound is above 0, so the registered improvement rule **passes**.

Extra H=16 search (768 imagined states per step versus the original 256) did not remove the 25-point remainder on these development physics. The unmatched development gap was **44.092** on different episode seeds, so this is not a paired reduction. Confirmation unused. Frozen development checkpoints were read-only.

This does not reverse the closed Acrobot compute-matched miss (**12.834 [3.815, 21.853]**). Do not retune H=16, the 16-candidate lookahead successor, or the dense height from this sample. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused.

## What was tested

Development split `2a5cc4979642cc2a` with fresh resets `27000000+`. Ten residual 2×64 MLPs loaded from `checkpoints/mountaincar_lookahead_h16`. Arm A scored 48 prefix-stable H=16 candidates (768/step). Arm B kept the frozen 16-candidate one-step backup (771/step). Dense valley height, 200-step TimeLimit, no goal termination. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25.

## Secondary (cannot upgrade)

Matched H=16 mean **−101.528 [−127.403, −75.653]**. Lookahead mean **−46.879 [−67.886, −25.872]**. Every episode ran 200 steps.

Per-task return_gain:

- task0: **25.725 [21.613, 29.838]**
- task1: **53.071 [6.066, 100.077]**
- task2: **85.149 [38.513, 131.786]**

Seed means: 39.9, 126.4, 18.3, 34.4, 35.4, 60.6, 30.6, 66.0, 118.9, 16.0. All ten seeds are positive.

## Integrity

`--results-audit` passed. Reward sums and return_gain identity reconstructed. `retune_from_confirmation` false. `pendulum_weights` false. `cartpole_h3` false. Training updates 0. 12,000 real steps (exact cap). 9,234,000 imagined (exact cap). Retries: 0. Ten frozen checkpoint hashes matched.

## Provenance

Branch `cursor/mountaincar-compute-matched-h16`. Preparation SHA **ea3c9a8d294af572595f9bcd03ba7fba1fd0d516**. One-run SHA **dbefbdc233735428b2b38ed39aedcfbb39cdf46b**.

- Config SHA256 `e33b01b6d50aff45f7c7a99990b978fa7e8bc58503da472903c79651d0eda033`
- Protocol SHA256 `6f5be2802e132bc944e8c97437b0e60a22ebb304b6fdb2a54445fdc3fe75b076`
- Raw artifact SHA256 `8a829874a5ba07d0e37e60b82efbce87afea83f04009c5f857be6e3523ca6c8f`

Execute **29.071 s**, process **29.85 s**. One-run remaining is 0.

## One next experiment

Do not retune H=16, candidates, or the dense height from this sample. Compute-matched remainder is established on MountainCar development and was not established on Acrobot. A later distinct question is the unmatched frozen lookahead package on a **new environment family**, not another MountainCar confirmation split. That proposal is not implemented and is not authorized here. This is not learning-to-learn or AGI.
