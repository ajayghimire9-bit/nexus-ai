# NEXUS V0.6.4 — Validated adaptation (corrected physics)

Branch `cursor/v064-validated-adaptation`. Not merged. Measured 2026-10-11, CPU, Gymnasium 1.4.0.

`pytest` **98 passed**. Historical `artifacts/v06*.json` / `v063_adaptation.json` were **not** overwritten.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v064_benchmarks.py`

Physics version: **`cartpole_derived_v1`**. V0.6–V0.6.3 are **`cartpole_setattr_only` (legacy)**. Do not cite those scores as evidence on these environments.

Not AGI. Confirmation tasks are still CartPole physics variants.

## P0 — physics

Gymnasium CartPole caches `total_mass = masscart + masspole` and `polemass_length = masspole * length` in `__init__`. V0.6–V0.6.3 only `setattr` the knobs, so length/mass edits did not change the Euler step. `apply_params` now recomputes those derived fields. Tests compare corrected vs unsynced dynamics and check deterministic reset/step.

## P0 — statistics

Replication unit = **source-training seed** (n=10), not task×seed (not n=30). Each seed’s score is the mean over the three confirmation tasks. Intervals are Student-t 95% (df=9). Hierarchical bootstrap (resample seeds) is also stored.

## P0 — retention

- **A** source snapshot before adaptation (original heads + RMS).
- **B** adapted weights on the source task.
- **C** preserved snapshot (equals A).
- **D** encoder + **original source heads** (only for new-head methods).
- **E** adapted weights with the source RMS.

Encoder-only transfer sets `retention_defined=False`. Replacing heads is not reported as catastrophic forgetting of the source policy.

## Source policies (all 10 seeds; val-best checkpoint)

Recipe: 64–64 shared, 4 envs, 128 steps, **10** PPO epochs, lr **2.5e-4**, obs RMS. Budgets 8 192 then 32 768. Selection uses **val 71000 only**.

Independent return **154.7 [75.0, 234.3]**. **0/10** met the val solve threshold 475. Best seed: val 449.8, independent 470. Total source steps **327 680**. Failed runs are kept.

Solved-source subgroup: **empty** (predefined val criterion). No second analysis beyond “all seeds.”

## Confirmation tasks (frozen before outcomes)

Generator `base_plus_frozen_offsets` from `(g=9.8, L=0.5, m=0.1)`:

| id | gravity | length | masspole |
| --- | --- | --- | --- |
| cartpole_confirm_0 | 7.5 | 0.65 | 0.18 |
| cartpole_confirm_1 | 13.0 | 0.38 | 0.22 |
| cartpole_confirm_2 | 9.8 | 0.72 | 0.06 |

Selector never sees confirm eval seed **74000**.

## Target return after 8 192 steps (seed-level mean across 3 tasks)

| Strategy | mean [t 95% CI] |
| --- | --- |
| scratch | 92.0 [60.2, 123.7] |
| reuse | 156.6 [74.7, 238.5] |
| full fine-tune | 196.3 [117.6, 275.1] |
| conservative low LR | 237.5 [154.8, 320.1] |
| frozen encoder + new heads | 108.4 [81.3, 135.4] |
| **encoder + new heads FT** | **392.0 [315.8, 468.2]** |
| V0.6.3 selector | 237.5 (always reuse/conservative) |
| risk-aware selector | 237.5 (same) |

Paired **encoder − scratch**: **+300.0 [224.2, 375.9]** (n=10 seeds, CI excludes 0).  
Paired **encoder − conservative**: **+154.5 [30.0, 279.1]** (excludes 0).  
Paired **risk selector − scratch**: **+145.5 [46.9, 244.1]** (excludes 0).  
Paired **risk selector − conservative**: **0**.  
Paired **risk selector − encoder**: **−154.5 [−279.1, −30.0]** (selector loses).

Learning curves (seed-mean of task-means):

| steps | scratch | reuse/cons@0 | conservative | encoder+heads |
| --- | --- | --- | --- | --- |
| 0 | 39.8 | 156.6 | 156.6 | 13.4 |
| 512 | 81.0 | — | 158.8 | 36.8 |
| 2 048 | 88.1 | — | 205.1 | 111.1 |
| 4 096 | 112.3 | — | 230.8 | 230.1 |
| 8 192 | 92.0 | — | 237.5 | **392.0** |

Encoder starts worse (new heads) and overtakes matched scratch by 2 048 steps and conservative by 8 192.

Risk-aware decisions: conservative_low_lr **27**, reuse **3**, encoder **0**. It reproduced conservative LR. That is a **negative selector result**, not an improvement.

## Success criteria

1. **Met:** encoder + new-head fine-tuning vs scratch on new confirmation tasks, seed-level t-interval excludes 0.
2. **Not claimed:** improved retention of the *same* source policy for encoder methods (`retention_defined=False`).
3. **Failed:** neither selector beats the strongest fixed baseline (encoder FT). Thresholds frozen from V0.6.3 legacy-physics development pushed the controller *away* from encoder transfer.
4. **Partial:** at 0–2 048 steps, reuse/conservative are better; at 8 192, encoder is better. “Faster acquisition” depends on the budget.

## Hypotheses that failed

- 32 768 steps × 10 PPO epochs still does **not** produce a solved CartPole source (0/10 on val).
- A val-threshold selector frozen after V0.6.3 does **not** pick the winning strategy once physics is corrected.
- V0.6.3 “encoder transfer does not persist” was measured under **inconsistent** CartPole dynamics and does not hold here.

Wall clock **212 s**. Params **4 739**.
