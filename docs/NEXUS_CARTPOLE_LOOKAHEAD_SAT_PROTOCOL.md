# CartPole lookahead versus frozen H=3 on the unsaturated holdout — locked protocol v1

Base `18ed8e424daf5351f84c8f5763730c644ea54574`. Branch `cursor/cartpole-lookahead-sat-h3`. The H=3-only diagnostic stays closed. Do **not** retune H=3, candidates, or reward. Do **not** drop ceilinged tasks. V0.7.3 confirmation tuples stay closed.

## 1. Why this holdout

The H=3-only diagnostic labeled `cartpole_h3_unsaturated` because the pooled ceiling gap was **33.183 [2.481, 63.886]** on split `a69833ab38a34ab4`. That diagnostic withheld lookahead. This protocol asks whether one-step backup of frozen H=3 open-loop value beats receding H=3 on **that same six-task split**.

Task 0 was at the 500-step cap on every diagnostic seed. It stays in the grid. Post-hoc task dropping is forbidden.

## 2. Holdout

Rule `cartpole_h3_saturation_v1`, split hash `a69833ab38a34ab4`:

- `cartpole_h3_sat0`: (13.2, 0.27, 0.23)
- `cartpole_h3_sat1`: (15.6, 0.25, 0.28)
- `cartpole_h3_sat2`: (15.4, 0.27, 0.20)
- `cartpole_h3_sat3`: (15.5, 0.30, 0.28)
- `cartpole_h3_sat4`: (16.0, 0.34, 0.20)
- `cartpole_h3_sat5`: (13.8, 0.31, 0.27)

Disjoint from the two ceilinged lookahead draws and from V0.7.3 confirmation.

## 3. Frozen controllers

Unchanged: V0.7.2 residual 2×64, 1024+256, 20 epochs, H=3 × 16, objective `both`, time budget off, 2 first-action lookahead of frozen open-loop H=3 score with survival weight `(1-p)`.

Ten residual models are trained with new collect seeds. Saturation checkpoints are not reused. H=3 is not retuned from the diagnostic outcomes.

## 4. Primary

Training-seed mean of (lookahead return − H=3 return), six tasks inside the seed. Student-t 95%, df 9. Margin **25**.

- `cartpole_sat_lookahead_established`
- `cartpole_sat_lookahead_harm_established`
- `cartpole_sat_lookahead_not_established`
- `incomplete`

## 5. Budget

**300 s**, **72,800** real steps max, **4,380,000** imagined max, **200** frozen-recipe epochs. Resets `21000000+`. Local CPU.

**Collection is unauthorized.** `authorized: false`, `runs: 0`.

Not a result, not learning-to-learn, not AGI.
