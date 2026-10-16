# MountainCarContinuous lookahead versus frozen H=16 transfer — locked protocol v1

Base `57cbf25b8a1f93210bce383846d05910248a6517`. Branch `cursor/mountaincar-continuous-lookahead-h16-confirm`. The development screen stays closed. Do **not** retune H=16, candidates, or dense height from that sample. Discrete MountainCar unused. CartPole H=3 unused. Pendulum FiLM unused. Acrobot unused.

This is a **transfer** test of the frozen development lookahead package on a new unused MountainCarContinuous holdout.

## 1. Why a new holdout

Development labeled `mountaincar_continuous_lookahead_established` on split `d247d7921d6afff7`. Those physics are closed. Confirmation uses a disjoint hash-rule draw and does not drop tasks after seeing development outcomes.

## 2. Holdout

Rule `mcc_lookahead_confirm_v1`, split hash `bc7c74c781c9e24f`. Keys `(gravity, power, max_speed)`:

- `mcc_look_cf0`: (0.0016, 0.0012, 0.09)
- `mcc_look_cf1`: (0.0038, 0.0019, 0.05)
- `mcc_look_cf2`: (0.0029, 0.0015, 0.08)

Source (0.0025, 0.0015, 0.07) and development physics are rejected.

## 3. Frozen controllers

Unchanged from development: residual 2×64, 1024+256, 20 epochs, H=16 × 16, discretized force, dense valley height, no goal termination, 200-step TimeLimit, 3 first-action lookahead of frozen open-loop H=16 height with survival weight `(1-p)`. Ten models trained on `mcc_default` with new collect seeds. Development checkpoints are not reused.

Lookahead uses 771 imagined states per step versus 256 for H=16. No compute-matched control.

## 4. Primary

Training-seed mean of (lookahead return − H=16 return), three tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `mountaincar_continuous_lookahead_transfer_established`
- `mountaincar_continuous_lookahead_transfer_harm_established`
- `mountaincar_continuous_lookahead_transfer_not_established`
- `incomplete`

## 5. Budget

**300 s**, **24,800** real steps max, **6,162,000** imagined max, **200** frozen-recipe epochs. Resets `32000000+`. Local CPU.

**Collection is unauthorized** until a bound one-run allocation sets `authorized: true` and `runs: 1` for this configuration hash, protocol hash, and these caps.

Not a result, not learning-to-learn, not AGI.
