# NEXUS V0.8.7 — From Candidate Quality to Online Learning

Branch `cursor/v087-online-learning-bridge`. Parent `9ee7003` (V0.8.6). Artifact `artifacts/v087_online.json`. Prior artifacts preserved.

Not AGI. MAE ratio **0.97** not retuned.

## Question

Why did the V0.8.6 candidate bank accept low-LR updates while online MAE accepted none? Can bank-matched collection deploy updates online?

## Diagnosis (development, n=10, paired eval seed 136000)

| Condition | Train / val | MAE accept rate | Paired Δ vs never |
| --- | --- | --- | --- |
| Candidate bank | 128 / 64 | **0.10** | −3.2 [−49, +42] |
| V0.8.6 online split | 64 / 32 (≤2 cycles, cap 256) | **0.00** | 0 |
| Online, bank-matched sizes | 128 / 64 (1 cycle) | **0.10** | −0.45 [−1.5, +0.6] |

**Measured:** the split (64 train / 32 val) explains the bank–online mismatch. Matching bank sizes recovers the bank’s (low) accept rate. The gate was not “broken”; the online budget leftover after reserving MAE+val was too small to produce MAE-passing candidates.

Dev froze **matched_sizes** (128/64, 1 cycle, cap 256) before confirmation.

## Confirmation (new physics, eval seed 137000, n=10, paired)

Noisy tasks, same eval seed for every policy:

| Policy | Return | Δ vs never | Mean accepts / proposals |
| --- | --- | --- | --- |
| never / snapshot | 228.3 [199.8, 256.7] | 0 | 0 |
| always + low_lr | 214.3 [195.7, 232.8] | **−14.0 [−43, +15]** | 1.0 / 1.0 |
| **MAE + low_lr** | 235.8 [207.7, 263.8] | **+7.5 [−3.5, +18.5]** | **0.25 / 1.0** (5/20 run-tasks) |
| MAE + finetune | 246.1 [205.1, 287.2] | +17.9 [−9.3, +45.1] | 0.75 / 1.0 |

CIs for gated return **include 0**. Online MAE **did accept** with bank-matched collection (unlike V0.8.6’s 0). Always-adapt did not beat never.

A→B→C→A: MAE-gated **292.9** vs never/snapshot **288.4** (overlap). Mean MAE accepts/seed **0.1**; always **4**. Retrieval matched snapshot.

## Costs

Cap **256** for all methods. Cycle: 128 adapt_collect + 64 val + 32 MAE `online_val` + leftover detect. Wall **182.8 s**. Protocol hash `16f70ff021f6221c`.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v087_benchmarks.py
```

Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0.

## Success criterion

Conservative adaptation **can produce and occasionally deploy** MAE-accepted updates online once collection matches the bank. It did **not** yield a significant control gain. Harmful always-adapt remains a risk (point estimate −14). Do not call 0.25 accept rate a solved online learner.

## Next

Keep 128/64 collection. Raise **cycle count** only with a larger pre-registered cap, or improve candidates so MAE+low_lr accepts more than 0.25 without always-adapt’s harm. Do not retune 0.97 from this confirm. No new env family, no finance.
