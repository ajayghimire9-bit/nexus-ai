# NEXUS V0.8.6 — Safer Candidate Generation

Branch `cursor/v086-safe-candidate-generation`. Parent `cf6780e` (V0.8.5). Artifact `artifacts/v086_candidates.json`. Prior JSON files were not overwritten.

Not AGI. Not a trading system. MAE threshold was **not** retuned (still 0.97 / 32 steps).

## Question

Can a safer generator cut genuinely harmful updates while keeping useful ones, with the V0.8.5 MAE gate frozen?

## Frozen protocol

- Architecture/MPC unchanged (residual 64-64, H=3).
- Matched collect: `c128`/`c256` + 64 independent val (same data for all methods).
- Methods (pre-registered, not from V0.8.5 confirm): finetune lr=5e-4; **low_lr** 1e-4; early-stop patience 2; replay mix; interpolate α=0.5.
- Reference: H=500 × 2, margin 10, `eval_only`. Never in `GateInput`.
- Dev (`dev_v086`) selected the generator by min harm fraction, then max benefit, then MAE-gated choice. Frozen **low_lr** before confirmation.
- Confirm physics/seeds unused in V0.8–V0.8.5 (`V086_CONFIRM_REF_SEED=129000`). n=10.
- Online A→B→C→A after freeze, using **low_lr** + MAE vs always vs never vs snapshot/retrieve.

## Commands

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v086_benchmarks.py
```

Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0. Wall **420.2 s**. Protocol hash `c93a65cd8fde0ad6`. Artifact recorded dirty tree on parent `cf6780e`.

## Candidate quality (noisy confirm, 40 pairs / method)

| Method | Benefit | Harm | Inconcl. | Harm frac | Benefit frac | MAE accept | MAE harm \| accept |
| --- | --- | --- | --- | --- | --- | --- | --- |
| finetune (V0.8.5 recipe) | 14 | 24 | 2 | 0.60 | 0.35 | 30 | 0.53 |
| **low_lr (selected)** | 17 | 10 | 13 | **0.25** | 0.425 | 16 | **0.0625** |
| early_stop | 23 | 14 | 3 | 0.35 | 0.575 | 29 | 0.34 |
| replay | 8 | 28 | 4 | 0.70 | 0.20 | 31 | 0.68 |
| interpolate | 24 | 10 | 6 | 0.25 | 0.60 | 22 | 0.23 |

Seed-mean raw Δ for **low_lr**: **+4.9 [−14.1, +23.9]** (includes 0). MAE-gated choice vs never: **+5.6 [−2.7, +13.8]** (includes 0). Always-accept equals raw Δ.

**Measured:** low_lr cut noisy harm vs matched finetune (0.25 vs 0.60) and kept at least as many benefits (17 vs 14). MAE + low_lr accepted 1 harmful / 16. That is a **harm reduction**, not a significant mean-return gain.

Interpolate looked strong on confirmation (24 benefit) but had the **worst** development harm (0.60) and was not selected. Do not promote it after seeing confirm.

On-policy MAE(candidate) − MAE(incumbent) ≈ **−0.003**; action disagreement **0.018**; “shift to poorly covered states” flag **5%**. low_lr barely moves the planner.

Costs (typical pair): pretrain 1280; collect train 128 or 256; collect val 64; verifier 32; on-policy eval_only 32; reference eval_only ~1500.

## Online A→B→C→A (low_lr generator)

Return to A: never / MAE-gated / snapshot / retrieved all **240.8 [195, 286]**; always-adapt **214.4 [168, 261]**. Mean MAE accepts per seed **0**; always **4**. Gated online did not change deployed weights relative to never. Always-adapt was worse on return-to-A (CI overlap). This is continual **behavior**, not an offline-bank claim.

## Limits

- Safer ≠ higher average return (CIs include 0).
- MAE online accepted nothing with low_lr; bank MAE still accepted 16/40 — collection schedules differ.
- Replay hurt. Early-stop helped benefit but not harm as much as low_lr on the frozen rule.
- One CartPole family, n=10, small residual net.

## Next

Keep low_lr + frozen MAE. Probe **why online MAE rejects** (too little collect vs bank, or candidates too similar). Do not retune 0.97 from these numbers. Do not start finance or a new env family.
