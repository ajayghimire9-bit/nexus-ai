# Cross-environment 2× prior-data scale — locked protocol (rung 5)

Branch `cursor/xenv-prior-scale` from `81e0215`. Rungs 1–4 are closed
`not_established`. This rung does **not** add FiLM, trunk depth, or a new
architecture. It tests whether the original one-shared-layer mechanism was
**starved** of source data.

## Falsifiable question (H5)

Does the closed rung-1 `XEnvNet` (one shared 64→64 tanh layer, per-family
projections) — pretrained on **twice** the source transitions per family
(1024+256 instead of 512+128) — improve MountainCarContinuous adaptation
on a NEW unused physics versus the identical architecture trained on the
target only?

Only prior-data volume and the new holdout differ from rung 1. Target
prefixes, fine-tune recipe, H=16 control and the matched scratch arm stay
frozen. Prediction MAE cannot decide the label.

A 5× scale-up would exceed the 100,000 standing interaction cap. This 2×
rung stays at **63,200** real steps.

## Fixed design

- Architecture: `rung1.XEnvNet` exactly. No FiLM, no second shared layer.
- Prior: CartPole, Acrobot, discrete MountainCar; **1024 train + 256 val**
  each, 15 epochs, lr 1e-3.
- Target pool 1024+256; budgets 128/1024; fine-tune 20 epochs lr 5e-4;
  reference residual 64×64, 20 epochs lr 1e-3.
- Holdout rule `mcc_xenv_v6` — **(0.0022, 0.0019, 0.08)** — rejecting
  default, development, confirmation, rungs 1–4 and the Cline v3 draft.
- Seeds: 67,000,000+ / 67,100,000+ / 67,200,000+ / 67,300,000+.
- Ten seeds; frozen H=16 × 16; 200-step episodes.

## Predeclared primary and labels

Primary: per-seed mean control return over {128, 1024}, paired
`xenv − scratch`, student-t 95% CI over ten seeds.

- `xenv_prior_scale_beats_scratch`: mean > 0 and CI lower bound > 0.
- `xenv_prior_scale_harm_established`: mean < 0 and CI upper bound < 0.
- `xenv_prior_scale_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

## Bounds

**600-second hard cap**, **63,200 real environment steps** (38,400 prior +
12,800 target pool + 12,000 evaluation), **3,072,000 imagined
transitions**, local CPU, one execution after a bound one-run allocation.
Session ledger at lock: 3377.327 s of 3600 s remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_prior_scale.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_prior_scale.py
PYTHONPATH=src:.deps python3 scripts/run_xenv_prior_scale.py --execute
```
