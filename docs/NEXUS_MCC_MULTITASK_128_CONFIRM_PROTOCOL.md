# Within-family MCC multitask at 128 — confirmation protocol

Branch `cursor/mcc-multitask-128-confirm` from `5f8cda3`. H10 on
`mcc_multitask_128_v1` **(0.0032, 0.0022, 0.06)** is closed
`mcc_multitask_128_beats_scratch`. This lock tests whether that
weight-pretrain advantage **replicates** on a new unused holdout.
It does not retune H10, reopen source-RMS, residual-scale, or xenv,
or interpret those negative studies.

## Falsifiable question (H11)

On unused MountainCarContinuous physics disjoint from H10, does the
**frozen H10 recipe** — residual world model pretrained on the same
three MCC physics and fine-tuned on **128** target transitions — beat
the identical residual model trained on the same 128 transitions from
scratch?

Both arms use the same target RMS. Primary is budget 128 only. No
cross-family weights. Same residual MLP `(64, 64)`, same H=16 × 16.

## Frozen H10 design (unchanged)

- Sources: `mcc_default` **(0.0025, 0.0015, 0.07)** plus lookahead
  development **(0.0038, 0.0019, 0.085)** and **(0.0024, 0.0019, 0.09)**.
  512 transitions / physics / seed. Concatenated 1504/32 split.
  Pretrain 15 epochs under source-pooled RMS, then switch to target RMS
  and fine-tune 20 epochs.
- Scratch: same create seed, target RMS, 20 epochs only.
- Architecture: residual 2×64, Adam lr 0.001, batch 128, term weight
  0.25, H=16 × 16, 200-step episodes, practical margin 0.0.
- H10 implementation SHA256
  `79a26fed3d0b4a852cd8194492ae67977af41965a56effc01d7441b006dfc701`
  is frozen. Closed H10 raw SHA256
  `caca746457eb72e89c95b6f8b9cd82c7cf06cff68713ff1d9ad8a98519e4d274`
  must not change.

## New confirmation holdout and seeds

- Target `mcc_multitask_128_confirm_v1` — **(0.0022, 0.0016, 0.07)** —
  rejecting default, lookahead, xenv MCC v1–v7, native-RMS,
  residual-scale, and H10 **(0.0032, 0.0022, 0.06)**.
- Seeds: 73,000,000+ / 73,100,000+ / 73,200,000+ / 73,300,000+,
  disjoint from H10 `72,000,000+`.
- Arms: `multitask`, `scratch`. Same target prefix and target RMS.
- Ten seeds; 20 eval traces.

## Predeclared primary and labels

Primary: per-seed H=16 return, paired `multitask − scratch`,
student-t 95% CI over ten seeds. Same rule as H10.

- `mcc_multitask_128_confirm_beats_scratch`: mean > 0 and CI lower bound > 0.
- `mcc_multitask_128_confirm_harm_established`: mean < 0 and CI upper bound < 0.
- `mcc_multitask_128_confirm_not_established`: otherwise.
- `incomplete`: any missing cell, cap failure or nonfinite value; no retune.

Secondary: held-out MAE difference, arm returns. Never label-deciding.

## Bounds

**600-second hard cap**, **20,960 real environment steps** (15,360
source + 1,600 target + 4,000 evaluation), **1,024,000 imagined
transitions**, local CPU. Session ledger at lock: 3316.143 s of 3600 s
remain.

Collection is not authorized by this protocol text alone.

## Tests and reproduction

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_mcc_multitask_128_confirm.py -p no:cacheprovider
PYTHONPATH=src:.deps python3 scripts/run_mcc_multitask_128_confirm.py
```

`--execute` must refuse until a later one-run allocation is committed.
