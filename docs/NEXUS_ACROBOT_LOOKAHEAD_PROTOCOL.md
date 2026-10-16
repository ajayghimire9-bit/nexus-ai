# Acrobot lookahead versus frozen H=16 — locked protocol v1

Base `5d2e616d48990cacbb6da1a8eead0074c9d3bd86`. Branch `cursor/acrobot-lookahead-h16`. CartPole lookahead versus H=3 stays closed on three development draws. Do **not** retune CartPole H=3. Do **not** load Pendulum FiLM weights.

This is a **new family** test of the frozen one-step lookahead *mechanism* (backup of open-loop planner value) against receding H=16. Acrobot is not CartPole and not Pendulum.

## 1. Why Acrobot, and why not Gymnasium -1/step

CartPole's 500-step +1 TimeLimit hid lookahead. Gymnasium Acrobot-v1 also uses -1/step until a goal and a 500-step cap, which would floor both arms at -500 if unsolved. The registered task therefore uses a **frozen dense upright-height reward** `-cos θ1 - cos(θ1+θ2)`, 200-step TimeLimit, and **no goal termination**. Hang-down is about -2 per step. This is not the Gymnasium Acrobot benchmark.

H=16 × 16 is used because this family has 3 discrete actions and dense per-step cost, matching the Pendulum planner *package*, not because Pendulum confirmation was used to retune. CartPole H=3 is not copied. Pendulum checkpoints are not loaded (`obs_dim` 6 vs 3).

## 2. Holdout

Rule `acrobot_lookahead_dev_v1`, split hash `911ea726b6ed2111`. Keys are `(LINK_MASS_1, LINK_MASS_2, LINK_LENGTH_1)`:

- `acrobot_look_dev0`: (0.95, 1.2, 0.8)
- `acrobot_look_dev1`: (1.25, 1.35, 0.95)
- `acrobot_look_dev2`: (0.75, 1.4, 1.4)

The source task (1.0, 1.0, 1.0) is rejected. CartPole and Pendulum splits are unused.

## 3. Frozen controllers

Ten residual 2×64 MLPs, 1024+256, 20 epochs, trained on `acrobot_default`. Shared 16×16 candidates, 3 actions, `step_reward = acrobot_step_reward`, time budget off.

- Arm A: receding H=16 (`h16_first_action`)
- Arm B: one-step backup of frozen open-loop H=16 height from `s'` over 3 first actions, survival-weighted `(1-p)`

Lookahead uses 771 imagined states per step versus 256 for H=16. No compute-matched control.

## 4. Primary

Training-seed mean of (lookahead return − H=16 return), three tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `acrobot_lookahead_established`
- `acrobot_lookahead_harm_established`
- `acrobot_lookahead_not_established`
- `incomplete`

## 5. Budget

**300 s**, **24,800** real steps max, **6,162,000** imagined max, **200** frozen-recipe epochs. Resets `22000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
