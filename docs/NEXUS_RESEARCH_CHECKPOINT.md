# NEXUS research checkpoint (after V0.8.9)

Branch `cursor/v089-research-checkpoint`. Parent `47d0213`. Not AGI. MAE **0.97** not retuned.

This note separates **repository-reported** numbers (committed artifacts from earlier milestones) from **independently reproduced** checks run on this branch.

## Independently reproduced (this branch)

| Check | Result |
| --- | --- |
| `PYTHONPATH=src:.deps python3 -m pytest tests -q` | **230 passed** |
| `validate_v089_artifact` | protocol hash `e10d512ec0a20f05`, n=10, MAE 0.97, budgets `[0,64,128,256,512,1024]`, stage 224, `is_agi=false` |
| Ledgers | every seed `bucket_sum == target_used`, `no_double_count` |
| Frozen curve | return identical at budget 0 and 1024 (same weights) |
| MAE stream (re-run) | **40/40** proposals `mae_reject`, **0** accepts; mean gate ratio **0.996** (need ≤0.97) |
| Artifact wall (reported) | 220.7 s; audit wall **28.6 s** |

The full V0.8.9 learning-curve and transfer tables were **not** re-trained on this branch. Those remain repository-reported in `artifacts/v089_learning.json` / `docs/NEXUS_V089.md`.

## Protocol audit (artifact, not re-run)

**Pairing:** each of 10 source-training seeds uses the same confirm eval seed **156000** for every method and budget. Dev eval seed **155000** is distinct. Pretrain **1328** (1024+256+48 calib) is reported separately from the 1024 target cap.

**Episode boundaries:** `PersistentSession` resets only on terminate/truncate or `switch_task`. MAE *gate* collection uses a **fresh** env (`make_task_env` + reset), not the live session. Gate trajectories are therefore a new episode of at most 32 incumbent-MPC steps.

**Leakage:** off-policy learning-curve fits split a **single persistent prefix** into train prefix + 25% suffix val (index split, not episode-disjoint). That can leak episode identity into early stopping. **Independent eval** is `paired_control_eval` and is not that suffix. MAE-gate val is a separate 32-step rollout. Detection calibration in V0.8.9 used source residuals, not candidate train batches.

**Counting:** target steps are `detect` + `adapt_collect` + `online_val`. Pretrain and paired eval are outside the cap. Retrieval probes (16) are inside the prefix accounting in the curve, not a hidden extra budget.

## Failed-adaptation audit (independently re-run)

Command: `PYTHONPATH=src:.deps python3 scripts/run_v089_checkpoint.py`

Frozen gate: accept iff `mae_after ≤ 0.97 * mae_before` on 32 incumbent-policy steps charged to `online_val`. Control returns below are **eval-only**, 1 episode, and **did not** enter `GateInput`.

40 proposals (10 seeds × 4), all `mae_reject`:

| Quantity | Value |
| --- | --- |
| Gate MAE before → after (mean) | 0.1039 → 0.1035 (drop **0.0004**) |
| Gate ratio mean [min, max] | **0.996** [0.987, 1.015] |
| Ratios ≤ 0.97 | **0 / 40** |
| Train MAE ratio mean | 0.989 (also **0** ≤ 0.97) |
| Val (incumbent-collected) MAE ratio | 0.994 |
| Weight L2 Δ | **0.100** [0.100, 0.101] (almost constant) |
| Planner disagreement | **2.1%** [1.3, 2.9] |
| 1-ep control Δ vs incumbent | **−2.7 [−29, +24]** includes 0 |
| Seeds with 1-ep Δ ≥ +10 | 13/40 (and 13/40 ≤ −10) — noise, not a gate bug |

**Verdict:** candidates are **ineffective under the frozen MAE test** (≈0.4% error drop vs a required 3%; tiny, stereotyped weight change). The 1-episode control audit is too noisy to claim the gate blocked large true return gains: the seed-paired mean includes 0. Do not retune 0.97 to 0.99 (that would have accepted 7/40 by hacking the threshold).

Closest ratio 0.987 still fails 0.97. Low-LR (1e-4, 8 epochs) is too conservative to move one-step error on this stream.

## What actually works (repository history)

- Residual 2×64 world model + H=3 random-shooting MPC on **CartPole** (V0.7.3 confirm **486** vs greedy **260**, CI excludes 0).
- Observation-normalization transfer vs scratch (V0.6.5–V0.6.6), which is **not** learned dynamics transfer.

## What has not worked (repository history)

Repeated CartPole *adaptation* (V0.8–V0.8.9): online MAE accepts are rare or, when they occur, paired control CIs include 0 (except one V0.8.5 MAE-choice confirm that did not replicate). Sequential CL, retrieval, and ABC→D did not beat frozen/source. See `docs/NEXUS_HYPOTHESIS_REGISTER.md`.

## Decision

See `docs/NEXUS_NEXT_EXPERIMENT.md`. Primary recommendation: **test the frozen world-model+MPC recipe on a second environment family** (direction B), not another CartPole MAE-threshold iteration.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v089_checkpoint.py
```
