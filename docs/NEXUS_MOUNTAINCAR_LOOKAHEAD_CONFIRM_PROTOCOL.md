# MountainCar lookahead versus frozen H=16 transfer — locked protocol v1

Base `998e1d634f942d36a763c6d0229f67393a4fef1f`. Branch `cursor/mountaincar-lookahead-h16-confirm`. The development screen stays closed. Do **not** retune H=16, candidates, or dense height from that sample. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused.

This is a **transfer** test of the frozen development lookahead package on a new unused MountainCar holdout.

## 1. Why a new holdout

Development labeled `mountaincar_lookahead_established` on split `2a5cc4979642cc2a`. Those physics are closed. Confirmation uses a disjoint hash-rule draw and does not drop tasks after seeing development outcomes.

## 2. Holdout

Rule `mountaincar_lookahead_confirm_v1`, split hash `bf4b4412f4f683dd`. Keys `(gravity, force, max_speed)`:

- `mountaincar_look_cf0`: (0.0031, 0.0007, 0.09)
- `mountaincar_look_cf1`: (0.0022, 0.0014, 0.085)
- `mountaincar_look_cf2`: (0.0037, 0.0014, 0.07)

Source (0.0025, 0.001, 0.07) and development physics are rejected.

## 3. Frozen controllers

Unchanged from development: residual 2×64, 1024+256, 20 epochs, H=16 × 16, dense valley height, no goal termination, 200-step TimeLimit, 3 first-action lookahead of frozen open-loop H=16 height with survival weight `(1-p)`. Ten models trained on `mountaincar_default` with new collect seeds. Development checkpoints are not reused.

Lookahead uses 771 imagined states per step versus 256 for H=16. No compute-matched control.

## 4. Primary

Training-seed mean of (lookahead return − H=16 return), three tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `mountaincar_lookahead_transfer_established`
- `mountaincar_lookahead_transfer_harm_established`
- `mountaincar_lookahead_transfer_not_established`
- `incomplete`

## 5. Budget

**300 s**, **24,800** real steps max, **6,162,000** imagined max, **200** frozen-recipe epochs. Resets `26000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
