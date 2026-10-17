# Cross-environment CartPole-target transfer — locked protocol (rung 7)

Branch `cursor/xenv-cartpole-target` from `fd50808`. Rungs 1–6 were MCC
targets and are closed. This rung asks whether the same closed rung-1
`XEnvNet` helps when the **target family changes**. It is not a retune.

## Falsifiable question (H7)

Does rung-1 `XEnvNet` pretrained on Acrobot + discrete MountainCar +
MountainCarContinuous beat matched scratch on unused **CartPole** physics?

Primary is the per-seed mean control return over {128, 1024}, paired
`xenv − scratch`. No FiLM. No architecture change. No MCC holdout reuse.

## Fixed design

- Architecture: closed rung-1 shared 64→64 tanh layer, per-family heads.
- Priors: Acrobot, MountainCar-v0, MountainCarContinuous defaults
  (512+128 transitions each). CartPole is **not** a prior family.
- Holdout rule `cartpole_xenv_v1` — **(6.5, 0.57, 0.28)** — rejecting
  every registered CartPole physics key (89 occupied).
- Seeds: 69,000,000+ / 69,100,000+ / 69,200,000+ / 69,300,000+.
- Ten seeds; target pool 1024+256; H=16 × 16; `n_actions=2`;
  `cartpole_unit_reward`. Episode cap 200 (CartPole-v1 may terminate
  earlier; evaluation steps are a **cap**, not an exact count).

## Predeclared primary and labels

Primary: per-seed mean of {128, 1024} control return, paired
`xenv − scratch`, student-t 95% CI over ten seeds.

- `xenv_cartpole_target_beats_scratch`: mean > 0 and CI lower bound > 0.
- `xenv_cartpole_target_harm_established`: mean < 0 and CI upper bound < 0.
- `xenv_cartpole_target_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

Secondary (never label-deciding): per-budget return gain, prediction MAE,
reference returns.

## Bounds

**600-second hard cap**, **44,000 real environment steps maximum**
(19,200 prior + 12,800 target + ≤12,000 evaluation), **3,072,000 imagined
transitions maximum**, local CPU, one execution after a bound one-run
allocation. Session ledger at lock: 3341.882 s of 3600 s remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_xenv_cartpole_target.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_xenv_cartpole_target.py
PYTHONPATH=src:.deps python3 scripts/run_xenv_cartpole_target.py --execute
```
