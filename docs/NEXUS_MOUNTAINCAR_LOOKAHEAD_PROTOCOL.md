# MountainCar lookahead versus frozen H=16 — locked protocol v1

Base `004d10edd7c39981d79e69d58951fdde1658587e`. Branch `cursor/mountaincar-lookahead-h16`. Pendulum compute-matched **60.182** stays closed. Acrobot unmatched transfer stays closed. Do **not** retune H=16, candidates, or reward from those samples. CartPole H=3 unused. Pendulum FiLM unused.

This is a **new family** test of the unmatched one-step lookahead package (backup of open-loop H=16 value, 771 vs 256 imagined states/step) against receding H=16. MountainCar is not Pendulum, CartPole, or Acrobot.

## 1. Why MountainCar, and why not Gymnasium -1/step

CartPole's 500-step +1 TimeLimit hid lookahead. Gymnasium MountainCar-v0 uses -1/step until the flag and a 200-step cap, which would floor both arms at -200 if unsolved. The registered task therefore uses a **frozen dense valley-height reward** `sin(3 * position)`, 200-step TimeLimit, and **no goal termination**. The valley floor is -1. This is not the Gymnasium MountainCar benchmark.

H=16 × 16 is used because this family has 3 discrete actions and dense per-step height, matching the unmatched Pendulum/Acrobot planner *package*, not because those confirmation outcomes were used to retune. CartPole H=3 is not copied. Pendulum and Acrobot checkpoints are not loaded (`obs_dim` 2 vs 3 vs 6).

## 2. Holdout

Rule `mountaincar_lookahead_dev_v1`, split hash `2a5cc4979642cc2a`. Keys are `(gravity, force, max_speed)`:

- `mountaincar_look_dev0`: (0.0035, 0.0006, 0.075)
- `mountaincar_look_dev1`: (0.0025, 0.0013, 0.07)
- `mountaincar_look_dev2`: (0.0015, 0.0013, 0.085)

The source task (0.0025, 0.001, 0.07) is rejected. Pendulum, CartPole, and Acrobot splits are unused.

## 3. Frozen controllers

Ten residual 2×64 MLPs, 1024+256, 20 epochs, trained on `mountaincar_default`. Shared 16×16 candidates, 3 actions, `step_reward = mountaincar_step_reward`, time budget off.

- Arm A: receding H=16 (`h16_first_action`)
- Arm B: one-step backup of frozen open-loop H=16 height from `s'` over 3 first actions, survival-weighted `(1-p)`

Lookahead uses 771 imagined states per step versus 256 for H=16. No compute-matched control.

## 4. Primary

Training-seed mean of (lookahead return − H=16 return), three tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `mountaincar_lookahead_established`
- `mountaincar_lookahead_harm_established`
- `mountaincar_lookahead_not_established`
- `incomplete`

## 5. Budget

**300 s**, **24,800** real steps max, **6,162,000** imagined max, **200** frozen-recipe epochs. Resets `25000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
