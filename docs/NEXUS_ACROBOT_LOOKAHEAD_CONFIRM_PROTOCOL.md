# Acrobot lookahead versus frozen H=16 transfer — locked protocol v1

Base `a09957f3d8df220f7c8f578c54034cded63f1fe3`. Branch `cursor/acrobot-lookahead-h16-confirm`. The development screen stays closed. Do **not** retune H=16, candidates, or dense height from that sample. CartPole H=3 unused. Pendulum FiLM unused.

This is a **transfer** test of the frozen development lookahead package on a new unused Acrobot holdout.

## 1. Why a new holdout

Development labeled `acrobot_lookahead_established` on split `911ea726b6ed2111`. Those physics are closed. Confirmation uses a disjoint hash-rule draw and does not drop tasks after seeing development outcomes.

## 2. Holdout

Rule `acrobot_lookahead_confirm_v1`, split hash `b309bd481fd8abcb`. Keys `(LINK_MASS_1, LINK_MASS_2, LINK_LENGTH_1)`:

- `acrobot_look_cf0`: (0.75, 0.6, 0.95)
- `acrobot_look_cf1`: (1.3, 1.4, 1.4)
- `acrobot_look_cf2`: (1.15, 0.85, 0.6)

Rejects source (1.0, 1.0, 1.0) and development `911ea726b6ed2111`.

## 3. Frozen controllers

Unchanged from development: residual 2×64, 1024+256, 20 epochs, H=16 × 16, dense upright height, no goal termination, 200-step TimeLimit, 3 first-action lookahead of frozen open-loop H=16 height with survival weight `(1-p)`. Ten models trained on `acrobot_default` with new collect seeds. Development checkpoints are not reused.

## 4. Primary

Training-seed mean of (lookahead return − H=16 return), three tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `acrobot_lookahead_transfer_established`
- `acrobot_lookahead_transfer_harm_established`
- `acrobot_lookahead_transfer_not_established`
- `incomplete`

## 5. Budget

**300 s**, **24,800** real steps max, **6,162,000** imagined max, **200** frozen-recipe epochs. Resets `23000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
