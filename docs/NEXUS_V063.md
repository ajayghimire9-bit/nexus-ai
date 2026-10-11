# NEXUS V0.6.3 — Adaptive knowledge reuse

Branch `cursor/v06-continual-transfer`. Not merged to `main`. Measured 2026-10-11, CPU.

`pytest` **88 passed**. Artifacts `v06_continual.json`, `v061_continual.json`, `v062_continual.json` were not overwritten.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v063_benchmarks.py`

Not AGI. CartPole physics variants only.

## Protocol

- **Source:** `cartpole_default`. Checkpoint chosen by **val seed 71000**, never by independent 72000.
- **Dev (not the success set):** `cartpole_lowg` (already used in V0.6.2).
- **Untouched final test:** `cartpole_short`, `cartpole_highg`, `cartpole_longheavy`.
- Selector sees **val zero-shot** on the target and **val source quality**. Thresholds frozen from V0.6.2 (`reuse ≥ 350`, `conservative ≥ 80`, else encoder-head FT; scratch if source val `< 50`). It cannot change eval seeds or step caps.
- Fixed strategies (matched 4 096 target steps except reuse=0): scratch, reuse, full fine-tune, encoder+new-head FT, frozen encoder, conservative LR `3e-5`.
- Final returns: holdout seed **73000**. Source retention: independent seed 72000 before vs after adaptation.

## Source-policy quality (n=3)

Val-best independent return **291.3 [83.3, 499.3]**. Last checkpoint (no val select) would keep seed 0 at **98.9** after a collapse from 220.5 at 8 192.

| Seed | Selected steps | Val | Independent | Last independent | Collapsed |
| --- | --- | --- | --- | --- | --- |
| 0 | 8 192 | 181.6 | 220.5 | 98.9 | yes |
| 1 | 32 768 | 500.0 | **500.0** | 500.0 | no |
| 2 | 32 768 | 149.1 | 153.4 | 153.4 | no |

**1/3 seeds solve.** Val-best checkpoint is the only thing that saved seed 0. Source quality is still not reliable.

## Final-test transfer (3 tasks × 3 seeds = 9, 4 096 steps)

| Strategy | target return [95% CI] | source Δ (retention) |
| --- | --- | --- |
| scratch | 78.8 [59.2, 98.3] | n/a |
| reuse (zero-shot full policy) | 268.5 [154.3, 382.8] | 0 |
| full fine-tune | 257.2 [132.1, 382.3] | −19.7 [−194.9, +155.5] |
| encoder + new heads FT | 68.1 [31.3, 104.8] | **−219.5 [−323.7, −115.2]** |
| frozen encoder + new heads | 49.9 [22.1, 77.8] | **−238.3 [−362.0, −114.6]** |
| conservative low LR | **320.9 [209.3, 432.5]** | +45.4 [−22.6, +113.5] |
| **selector (val only)** | **320.9 [209.3, 432.5]** | +45.4 [−22.6, +113.5] |

Paired selector − scratch: **+242.1 [119.6, 364.7]** (CI excludes 0).  
Selector − encoder FT: **+252.8 [152.6, 353.0]** (excludes 0).  
Selector − reuse: +52.4 [−22.2, +127.0] (includes 0).  
Selector − conservative: **0** (on this test set the rule always matched conservative, or reuse that tied conservative at 500).

Decisions: seed 1 (solved source) → **reuse** on every task (val zero-shot 500). Seeds 0 and 2 → **conservative_low_lr** (val zero-shot 119–250, below reuse threshold). Never encoder or scratch on these tasks.

## Failures

1. **V0.6.2 encoder+new-head win does not persist** on short / high-g / long-heavy. It is worse than scratch on the test pool and **destroys** source skill (retention CI entirely negative).
2. Full-policy fine-tune at the default LR can crush a solved policy on the **dev** task (seed 1 conservative on low-g: 500 → 250.5, source Δ −330). The selector avoided that on low-g by choosing reuse.
3. Source PPO remains unstable; only seed 1 is solved.

## Success criterion

**Partially met.** On unseen compatible tasks, the val-only selector avoided the failing encoder recipe and beat scratch with a CI excluding 0. It did **not** beat the strongest fixed strategy (conservative low LR), because that is what it selected whenever zero-shot was middling.

Positive transfer **does** persist as **full-policy reuse / low-LR adaptation** when the source is decent — not as encoder-head reinitialization. That is the mechanism that failed to generalize from V0.6.2.

Next test: stop training sources that fail val; condition transfer claims on solved sources only; try a smaller default LR as the global fine-tune baseline.
