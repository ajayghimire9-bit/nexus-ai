# Within-family MCC multitask at 128 — locked protocol

Branch `cursor/mcc-multitask-128` from `954beb1`. Source-MCC RMS and
residual-scale transplants are closed. This rung tests the cited
within-family lever that those reports kept invoking: **pretrained
weights** from other MCC physics, not an imported source statistic.
It is not a shared-trunk xenv variant and not a retune of
`mcc_native_rms_v1` or `mcc_residual_scale_v1`.

## Falsifiable question (H10)

On unused MountainCarContinuous physics, does a residual world model
**pretrained on three other MCC physics** (512 transitions each) and
fine-tuned on **128** target transitions beat the identical residual
model trained on the same 128 transitions from scratch?

Both arms use the same target RMS. Primary is budget 128 only. No
cross-family weights. Same residual MLP `(64, 64)`, same H=16 × 16.

## Fixed design

- Sources: `mcc_default` **(0.0025, 0.0015, 0.07)** plus lookahead
  development **(0.0038, 0.0019, 0.085)** and **(0.0024, 0.0019, 0.09)**.
  512 transitions / physics / seed. Concatenated 1504/32 split.
  Pretrain 15 epochs under source-pooled RMS, then switch to target RMS
  and fine-tune 20 epochs.
- Scratch: same create seed, target RMS, 20 epochs only.
- Target holdout `mcc_multitask_128_v1` — **(0.0032, 0.0022, 0.06)** —
  rejecting default, lookahead, xenv MCC v1–v7, native-RMS, and
  residual-scale.
- Seeds: 72,000,000+ / 72,100,000+ / 72,200,000+ / 72,300,000+.
- Arms: `multitask`, `scratch`. Same target prefix and target RMS.
- Ten seeds; 20 eval traces.

## Predeclared primary and labels

Primary: per-seed H=16 return, paired `multitask − scratch`,
student-t 95% CI over ten seeds.

- `mcc_multitask_128_beats_scratch`: mean > 0 and CI lower bound > 0.
- `mcc_multitask_128_harm_established`: mean < 0 and CI upper bound < 0.
- `mcc_multitask_128_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

Secondary: held-out MAE gain, arm returns.

## Bounds

**600-second hard cap**, **20,960 real environment steps** (15,360
source + 1,600 target + 4,000 evaluation), **1,024,000 imagined
transitions**, local CPU, one execution after a bound one-run
allocation. Session ledger at lock: 3321.755 s of 3600 s remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_mcc_multitask_128.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_mcc_multitask_128.py
PYTHONPATH=src:.deps python3 scripts/run_mcc_multitask_128.py --execute
```
