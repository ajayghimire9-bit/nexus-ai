# CartPole frozen H=3 saturation diagnostic — complete development screen

## Registered decision

The locked 60-episode (10 training seeds × 6 tasks × 1 H=3 arm) diagnostic completed. Label: `cartpole_h3_unsaturated`.

Ceiling gap (500 − H=3 return): **33.183 [2.481, 63.886]**. The mean is at least 25 and the lower bound is above 0, so the registered unsaturation rule **passes**.

This is not a lookahead result. Lookahead was withheld. H=3 was not retuned. Pendulum weights were unused. V0.7.3 confirmation tuples were unused.

The pass does not mean every cell is off-ceiling. Frozen H=3 still returned **500** on 50 of 60 episodes and on 4 of 10 seed means. Task 0 was 500 on every seed. The pooled gap is carried by a subset of seeds, especially seed 3 (**124.2**) and seed 9 (**87.0**). Do not drop ceilinged tasks after seeing these numbers.

## What was tested

Holdout `a69833ab38a34ab4` in the stricter unused corner: (13.2, 0.27, 0.23), (15.6, 0.25, 0.28), (15.4, 0.27, 0.20), (15.5, 0.30, 0.28), (16.0, 0.34, 0.20), (13.8, 0.31, 0.27). Ten residual 2×64 MLPs trained with the frozen V0.7.2 recipe on `cartpole_default`. Shared 16×3 candidates, objective `both`, time budget off, H=3 receding only. Replication unit: source-training seed. Student-t 95%, df 9. Margin 25 below the 500-step cap.

## Secondary (cannot upgrade)

H=3 mean **466.817 [436.114, 497.519]** (upper bound below 500).

Per-task H=3 return:

- task0: **500.000 [500.000, 500.000]** (still ceilinged)
- task1: **424.400 [345.394, 503.406]** (includes 500)
- task2: **487.000 [457.594, 516.406]** (includes 500)
- task3: **476.300 [422.691, 529.909]** (includes 500)
- task4: **454.100 [384.823, 523.377]** (includes 500)
- task5: **459.100 [390.583, 527.617]** (includes 500)

## Integrity

`--results-audit` passed. Reward sums and ceiling_gap identity reconstructed. `lookahead_run` false. `retuned_h3` false. Pendulum weights flag false. Training epochs 200. 40,809 real steps (under 42,800 cap because some episodes ended before 500). 1,344,432 imagined (under 1,440,000 cap). Retries: 0.

## Provenance

Branch `cursor/cartpole-h3-saturation-diagnostic`. Preparation SHA **37cc0884730c75284f1ba6975913b01eb3c4712f**. One-run SHA **a49f4ef06e7aa3d412c9eecd11315dd0a057143d**.

- Config SHA256 `55be38a5d77e76bb38a56c50d92e9522037855e8b500577de55c665af9291421`
- Protocol SHA256 `657cf38d25c9d013b733e8ba6ef373845b487f980d19f6b815e3cf4ad96cd157`
- Raw artifact SHA256 `fbdbbddc792a5a27d821d9119de6b8af251f53c28421c5a5152628a1bdc3015d`

Execute **7.095 s**, process **8.198 s**. One-run remaining is 0.

## One next experiment

Do not retune H=3 and do not drop task 0 after seeing it ceilinged. A later distinct question is lookahead versus frozen H=3 on **this same locked six-task holdout** `a69833ab38a34ab4`, where the pooled H=3 gap from the TimeLimit is established. That proposal is not implemented and is not authorized here.
