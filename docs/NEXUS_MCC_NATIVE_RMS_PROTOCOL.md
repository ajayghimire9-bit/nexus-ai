# Within-family MCC source-RMS adaptation — locked protocol

Branch `cursor/mcc-native-rms` from `925cb2c`. This is **not** another
shared-trunk, FiLM, low-budget, or target-family xenv rung. It tests the
synthesis recommendation: a family-native interface statistic.

## Falsifiable question (H8)

On unused MountainCarContinuous physics, does a residual world model
trained on **128** target transitions with frozen **source `mcc_default`
observation RMS** beat the identical model trained on the same 128
transitions with frozen **fresh target RMS**?

Primary is budget 128 only. No cross-family weights. Same residual MLP
`(64, 64)`, same H=16 × 16 planner, same train prefix.

## Fixed design

- Source: `mcc_default` (0.0025, 0.0015, 0.07), 512 transitions / seed,
  used only to fit RMS. No source-model training.
- Target holdout `mcc_native_rms_v1` — **(0.0029, 0.0022, 0.055)** —
  rejecting default, lookahead splits, and xenv MCC v1–v7.
- Seeds: 70,000,000+ / 70,100,000+ / 70,200,000+ / 70,300,000+.
- Arms: `source_rms`, `scratch_rms`. Same `train_world_model` seed.
- Ten seeds; 20 eval traces; H=16 × 16.

## Predeclared primary and labels

Primary: per-seed H=16 return, paired `source_rms − scratch_rms`,
student-t 95% CI over ten seeds.

- `mcc_native_rms_beats_scratch`: mean > 0 and CI lower bound > 0.
- `mcc_native_rms_harm_established`: mean < 0 and CI upper bound < 0.
- `mcc_native_rms_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

Secondary (never label-deciding): held-out prediction MAE gain, arm
returns, RMS mean/var.

## Bounds

**600-second hard cap**, **10,720 real environment steps** (5,120 source
+ 1,600 target + 4,000 evaluation), **1,024,000 imagined transitions**,
local CPU, one execution after a bound one-run allocation. Session
ledger at lock: 3331.649 s of 3600 s remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_mcc_native_rms.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_mcc_native_rms.py
PYTHONPATH=src:.deps python3 scripts/run_mcc_native_rms.py --execute
```
