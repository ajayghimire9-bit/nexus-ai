# H10/H11 prediction-versus-control disagreement — analysis protocol

Branch `cursor/h10-h11-control-disagreement-audit` from `668463e`.
Source-only. No environment interactions, no training, no reserved
holdout scoring, no fitted Q-functions, no H10/H11 rerun, and no
change to closed recipes or seeds.

## Question

Using only committed H10 and H11 artifacts, what can be established
about the prediction-versus-control disagreement, and what cannot?

## Frozen inputs

- H10 raw `caca746457eb72e89c95b6f8b9cd82c7cf06cff68713ff1d9ad8a98519e4d274`
- H11 raw `e8045423ff257e2f55acbead5a3f2eafc54f5ed5f88dab99933cca5eea286950`
- H10 implementation `79a26fed3d0b4a852cd8194492ae67977af41965a56effc01d7441b006dfc701`

## Allowed operations

Recompute paired returns and Student-t intervals. Split saved rewards
into steps 0–15 and 16–199. Tabulate saved actions. Compare MAE
scalars to return deltas. List missing fields.

## Forbidden operations

New `env.step` / `env.reset`. New `train_world_model`. Scoring any
unused physics. Fitting value heads. Re-executing H10 or H11 runners.

## Decision rule

This audit produces an interpretation and one recommended diagnostic.
It does not assign a control label and does not authorize collection.

Not learning-to-learn, not AGI.
