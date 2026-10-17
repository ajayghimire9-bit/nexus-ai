# Cross-environment low-budget (128) transfer — locked protocol (rung 6)

Branch `cursor/xenv-low-budget-128` from `2a005e0`. Rung 5's **primary**
(mean of {128, 1024}) was `xenv_prior_scale_not_established`
(−4.761 [−36.121, +26.599]). Its @128 secondary
(+23.887 [+1.150, +46.624]) is **not** a label and that holdout is closed.
This rung asks that 128-only question on a **new unused** physics draw. It
is not a retune.

## Falsifiable question (H6)

Does 2×-prior `XEnvNet` (closed rung-1 architecture, 1024+256 source
transitions per family) beat matched scratch on the **128-transition**
target budget alone, on new unused MountainCarContinuous physics?

Primary is budget 128 only. Budget 1024 is collected and reported as
secondary and cannot decide the label. No FiLM. No architecture change.

## Fixed design

- Same recipe as rung 5 except holdout, seeds, and the primary rule.
- Holdout rule `mcc_xenv_v7` — **(0.0016, 0.0011, 0.08)** — rejecting
  default, development, confirmation, rungs 1–5 and the Cline v3 draft.
- Seeds: 68,000,000+ / 68,100,000+ / 68,200,000+ / 68,300,000+.
- Ten seeds; target pool 1024+256; both budgets still run; H=16 × 16.

## Predeclared primary and labels

Primary: per-seed control return at budget **128**, paired
`xenv − scratch`, student-t 95% CI over ten seeds.

- `xenv_low_budget_beats_scratch`: mean > 0 and CI lower bound > 0.
- `xenv_low_budget_harm_established`: mean < 0 and CI upper bound < 0.
- `xenv_low_budget_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

Secondary (never label-deciding): budget 1024 return gain, mean-over-budgets
gain, prediction MAE, reference returns.

## Bounds

**600-second hard cap**, **63,200 real environment steps**, **3,072,000
imagined transitions**, local CPU, one execution after a bound one-run
allocation. Session ledger at lock: 3359.478 s of 3600 s remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_low_budget.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_low_budget.py
PYTHONPATH=src:.deps python3 scripts/run_xenv_low_budget.py --execute
```
