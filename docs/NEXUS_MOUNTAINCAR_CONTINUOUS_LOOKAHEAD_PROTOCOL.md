# MountainCarContinuous lookahead versus frozen H=16 — locked protocol v1

Base `ae699174c853d409436ecdd03117a903f2be80c6`. Branch `cursor/mountaincar-continuous-lookahead-h16`. MountainCar discrete, Acrobot, CartPole, and Pendulum stay closed. Do **not** copy discrete MountainCar checkpoints, CartPole H=3, or Pendulum FiLM.

This is a **new family** test of the unmatched one-step lookahead package (backup of open-loop H=16 value, 771 vs 256 imagined states/step) against receding H=16. `MountainCarContinuous-v0` is not `MountainCar-v0`.

## 1. Why this family

Classic-control discrete families are exhausted: Pendulum (FiLM), CartPole (ceiling), Acrobot, and MountainCar-v0. Box2D/MuJoCo are not installed. `MountainCarContinuous-v0` is the remaining Gymnasium classic-control environment that runs locally. Force is continuous; this protocol discretizes it to `{-1, 0, +1}` scaled by `power` (default 0.0015, not discrete `force` 0.001). Gymnasium sparse +100 / action-cost and goal termination are replaced by frozen dense valley height, 200-step TimeLimit, no goal termination.

## 2. Holdout

Rule `mcc_lookahead_dev_v1`, split hash `d247d7921d6afff7`. Keys `(gravity, power, max_speed)`:

- `mcc_look_dev0`: (0.0038, 0.0019, 0.085)
- `mcc_look_dev1`: (0.0024, 0.0019, 0.09)
- `mcc_look_dev2`: (0.0033, 0.0014, 0.05)

Source (0.0025, 0.0015, 0.07) is rejected. Discrete MountainCar physics tuples are not reused.

## 3. Frozen controllers

Residual 2×64, 1024+256, 20 epochs, H=16 × 16, dense valley height `sin(3 * position)`, 3 first-action lookahead of frozen open-loop H=16 height with survival weight `(1-p)`. Ten models trained on `mcc_default`. Discrete MountainCar checkpoints are not loaded.

Lookahead uses 771 imagined states per step versus 256 for H=16. No compute-matched control.

## 4. Primary

Training-seed mean of (lookahead return − H=16 return), three tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `mountaincar_continuous_lookahead_established`
- `mountaincar_continuous_lookahead_harm_established`
- `mountaincar_continuous_lookahead_not_established`
- `incomplete`

## 5. Budget

**300 s**, **24,800** real steps max, **6,162,000** imagined max, **200** frozen-recipe epochs. Resets `28000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
