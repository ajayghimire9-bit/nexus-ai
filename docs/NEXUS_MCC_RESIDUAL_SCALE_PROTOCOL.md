# Within-family MCC residual-scale adaptation — locked protocol

Branch `cursor/mcc-residual-scale` from `d8e6402`. Source-MCC observation
RMS is closed `not_established`. This rung tests the remaining
family-native object: a 2-d residual scale from support `s′−s`. It is
not a shared-trunk xenv variant and not a retune of `mcc_native_rms_v1`.

## Falsifiable question (H9)

On unused MountainCarContinuous physics, does a residual world model
trained on **128** target transitions with a frozen **2-d source residual
scale** (mean `|s′−s|` from `mcc_default`, in target-RMS coordinates)
beat the identical model with **unit scale**?

Both arms use the same target RMS. Primary is budget 128 only. No
cross-family weights. Same residual MLP `(64, 64)`, same H=16 × 16.

## Fixed design

- Source: `mcc_default`, 512 transitions / seed, used only to infer
  scale. No source-model training.
- Target holdout `mcc_residual_scale_v1` — **(0.0021, 0.0018, 0.055)** —
  rejecting default, lookahead, xenv MCC v1–v7, and native-RMS.
- Seeds: 71,000,000+ / 71,100,000+ / 71,200,000+ / 71,300,000+.
- Arms: `source_scale`, `unit_scale`. Same train prefix, RMS, and seed.
- The net predicts residual / scale; `step` decodes `obs + pred * scale`.
- Ten seeds; 20 eval traces.

## Predeclared primary and labels

Primary: per-seed H=16 return, paired `source_scale − unit_scale`,
student-t 95% CI over ten seeds.

- `mcc_residual_scale_beats_unit`: mean > 0 and CI lower bound > 0.
- `mcc_residual_scale_harm_established`: mean < 0 and CI upper bound < 0.
- `mcc_residual_scale_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

Secondary: held-out MAE gain, arm returns, saved 2-d scales.

## Bounds

**600-second hard cap**, **10,720 real environment steps**, **1,024,000
imagined transitions**, local CPU, one execution after a bound one-run
allocation. Session ledger at lock: 3326.720 s of 3600 s remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_mcc_residual_scale.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_mcc_residual_scale.py
PYTHONPATH=src:.deps python3 scripts/run_mcc_residual_scale.py --execute
```
