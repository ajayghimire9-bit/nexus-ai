# NEXUS V0.8.8 — Genuine Continual Online Learning

Branch `cursor/v088-continual-online-learning`. Parent `6b62fe4` (V0.8.7). Artifact `artifacts/v088_online.json`. Prior artifacts preserved.

Not AGI. MAE ratio **0.97** not retuned. Protocol not revised from this confirmation.

## Frozen baseline

Residual world model, H=3 MPC, MAE 0.97 / 32 steps, low-LR generator, independent validation. Train/val **128/64** carried from V0.8.7’s development protocol, **not** from V0.8.7 confirmation. Pre-registered cap **672** = 3 × (128+64+32) for three adaptation opportunities. Detector: window 32, k=3, calibrated on independent source residuals.

## Task 2 — collection-size factorial (development pool)

Identical source weights, planned-belief pool, adapt seed, and verifier seed. Varied `train_n` ∈ {64,128}, `val_n` ∈ {32,64}, cycles ∈ {1,2}.

| Condition | MAE accept rate (n=10) |
| --- | --- |
| All eight cells | **0.00** |

On this frozen source-planned pool, none of the three factors produced a MAE accept. Cycle count and the 64→128 train increase did not unlock the gate when data were not collected by the deployed online loop.

## Task 3 — change detection

| Metric | n=10 |
| --- | --- |
| Source false-alarm rate | **0.00** |
| Dev detection delay | **32** steps (detector window) |
| Dev miss rate | **0.00** |

Alarms did not fire on source physics at cap 128. On the shifted development target, every seed alarmed at the window length; no missed changes.

## Confirmation (new physics, eval seed 146000, n=10, paired)

Noisy tasks; change-triggered; max 3 cycles; cap 672. Mean proposes for gated/always methods: **3.0** (miss rate 0).

| Policy | Return | Δ vs never | Mean accepts | Beneficial / harmful (return-signed) |
| --- | --- | --- | --- | --- |
| never / snapshot | 287.7 [260.2, 315.3] | 0 | 0 | 0 / 0 |
| always + low_lr | 291.6 [265.7, 317.4] | **+3.8 [−36.8, +44.4]** | **3.0** | 0.60 / 0.40 |
| **MAE + low_lr** | 291.1 [262.3, 319.8] | **+3.3 [−34.9, +41.6]** | **0.95** | 0.20 / 0.30 |
| MAE + finetune | 243.4 [209.4, 277.3] | **−44.4 [−94.4, +5.7]** | 2.10 | 0.30 / 0.70 |

All paired Δ CIs **include 0**. Do not claim a control improvement. MAE+low_lr deployed ~1 of 3 proposed updates per noisy task. Always-adapt committed every proposal without a significant return gain. Fine-tuning under MAE was the worst point estimate.

## Tasks 4–5 — A→B→C→A with probe retrieval

Per-stage cap 224 (one opportunity). Probe **16** current-env steps; retrieval by probe MAE; no task labels. Mean probe interactions **64** / seed; memory **~100 KB**.

A-return returns (overlap throughout): never/snapshot **348.8**; gated/retrieved **345.9**; naive-shared **344.1**. Retrieved matched the latest gated snapshot, not the source. Probe memory did not beat never-adapt.

## Costs

Cap **672**. Cycle cost **224**. Wall **237.9 s**. Protocol hash `312e4c8783c24b68`.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v088_benchmarks.py
```

Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0. `pytest` **214 passed**.

## Success criterion

NEXUS **can** detect a physics shift (FPR 0, delay = window, miss 0), propose three online updates, and sometimes commit MAE-gated low-LR weights that then collect the next data. It did **not** produce a statistically reliable control gain, useful snapshot retrieval versus never-adapt, or a factorial proof that train_n/val_n/cycles alone explain MAE accepts on a frozen pool. Negative result on genuine continual improvement. Not AGI.

## Next

Keep MAE 0.97 and 128/64. The gap is candidate quality under on-policy residual error, not detector false alarms. Do not retune the gate from this confirm. No new env family, no finance, no V0.9.
