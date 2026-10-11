# NEXUS V0.6.2 — Valid continual learning and transfer experiments

Branch `cursor/v06-continual-transfer`. Not merged to `main`. Measured 2026-10-11, CPU, Python 3.13.

`pytest` **83 passed**. Artifacts `artifacts/v06_continual.json` and `artifacts/v061_continual.json` were not overwritten.

Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v062_benchmarks.py`

This is **not** AGI, meta-RL, or a trading system.

## What was wrong in V0.6 / V0.6.1

1. **EWC.** Fisher was `(∇ mean log π)²` plus a value term, then summed across tasks while **replacing** the single parameter snapshot. That is not diagonal empirical Fisher and not multi-task EWC.
2. **Forward transfer.** `R_{i−1,i} − specialist_i` compared an untrained-on-i policy to a fully trained specialist.
3. **Transfer ablations** mixed encoder copy with random observation normalization and did not copy a full policy.

## Corrections

- Diagonal empirical Fisher: `F_i = (1/N) Σ_n (∂ log π(a_n|s_n) / ∂θ_i)²` with **per-sample** gradients. Critic not included.
- After each task k, store a separate `(θ*_k, F_k)`. Penalty `(λ/2) Σ_k Σ_i F_{k,i}(θ_i−θ*_k,i)²`. Snapshots are not overwritten.
- Metrics: average return, forgetting `R_{i,i}−R_{T,i}`, BWT `R_{T,i}−R_{i,i}`, **zero-shot FWT** `R_{i−1,i} − untrained_i`, **forward adaptation** `R_{i,i} − independent_i`.
- Transfer A–F copy overlapping parameters that participate in the forward pass, and copy `obs_rms`.
- Source CartPole is trained with a stronger recipe (shared 64–64, 4 envs, 128 steps, 4 epochs) **before** scaling sequential CL. Sequential CL stays at 2048 steps/task.

Eval seeds: train feedback ≠ val **71000** ≠ independent **72000** ≠ holdout **73000**. Curriculum never sees 72000.

## Source learning (`cartpole_default`, independent seed 72000, n=3)

| Steps | mean return [95% CI] |
| --- | --- |
| 8 192 | 144.7 [68.9, 220.4] |
| 32 768 | 250.8 [4.5, 497.0] |

Per seed at 32 768: **98.9, 500.0, 153.4**. Solve threshold 475. One seed solved; one **collapsed** from 220 at 8k to 99 at 32k. A stable specialist is **not** established. Sequential CL was therefore **not** scaled to 32k.

Params: **4 739** (64–64 shared). Wall clock for the full V0.6.2 suite: **37.3 s**.

## Held-out transfer to `cartpole_lowg` (matched 8 192 target steps, eval 73000)

Source checkpoint: 32 768-step `cartpole_default`. Paired seeds `{0,1,2}`.

| Mode | return at 0 steps | return after 8 192 |
| --- | --- | --- |
| A scratch | 20.0 [−1.2, 41.2] | **138.3 [66.0, 210.7]** |
| B full policy zero-shot | 289.6 [77.7, 501.5] | (no target updates) |
| C encoder + new heads, zero-shot | 11.2 [8.4, 14.1] | (no target updates) |
| D full policy fine-tune | 289.6 | 298.6 [101.1, 496.1] |
| E encoder + new heads, fine-tune | 11.2 | **438.5 [372.8, 504.2]** |
| F frozen encoder + new heads | 11.2 | 159.0 [144.5, 173.4] |

Paired **E − A** after 8 192 steps: **+310.8, +299.1, +290.6**. Mean **+300.2**, 95% CI about **[288.7, 311.6]** (n=3). CI **excludes 0**.

Interpretation:

- Random new heads on a copied encoder (**C**) are not a policy. Copying weights is not transfer.
- Fine-tuning those heads **and** the encoder (**E**) learns `cartpole_lowg` faster than scratch with the same architecture and target-task budget. That is the supported transfer claim.
- Frozen encoder (**F**) vs scratch: paired deltas +24, +83, −46; CI would include 0.
- Full-policy zero-shot (**B**) is high when the source seed solved (seed 1: 500 on low-g with no target training). Fine-tuning that solved policy (**D** seed 1) **fell to 204** — target updates can destroy a transferred policy.
- Positive transfer here is **physics-variant CartPole**, not cross-family (not Acrobot).

## Sequential CL (2 048 steps/task, 6 144 matched, 32–32 recipe, n=3)

Independent specialists average return **95.5 [93.0, 98.1]** (1 315 params; multi-head 1 513).

| Method | average return | zero-shot FWT vs untrained | forward adaptation vs independent | BWT |
| --- | --- | --- | --- | --- |
| independent | 95.5 [93.0, 98.1] | n/a | n/a | n/a |
| naive | 98.3 [80.6, 116.0] | **+36.3 [17.1, 55.4]** | +3.8 [−3.9, +11.4] | −1.5 [−15.1, +12.2] |
| replay | 155.8 [84.9, 226.8] | **+66.1 [43.5, 88.7]** | +33.8 [−11.4, +79.0] | **+39.8 [1.8, 77.8]** |
| EWC (per-task Fisher) | 108.5 [85.7, 131.2] | **+37.3 [17.7, 56.9]** | +7.5 [−0.2, +15.2] | +8.2 [−12.5, +28.9] |
| multi-head | 137.6 [64.0, 211.2] | −14.1 [−38.0, +9.9] | +50.7 [−19.5, +120.9] | **−12.9 [−14.1, −11.6]** |

Zero-shot FWT vs **untrained** is positive for naive/replay/EWC (CI excludes 0). That only says a policy trained on earlier CartPole variants scores above a random net on the next variant. It is **not** a win vs specialists.

Replay BWT CI excludes 0, but average-return CIs overlap independent specialists and policies remain unsolved (~100–150 vs 475). Do not treat this as solved continual learning.

Multi-head **forgets** (BWT CI entirely negative). That mechanism failed under this budget.

Curriculum (val 71000 only): fixed 106.6 [104.3, 108.9]; random 105.7; adaptive **102.1 [98.4, 105.8]**. Adaptive does not beat fixed.

## Success criterion

**Partially met, on one transfer test only.** Encoder + new-head fine-tuning on held-out `cartpole_lowg` beats matched-compute scratch with a paired CI excluding 0.

**Not met** for sequential continual learning: no method’s average return CI sits above independent specialists without overlap, source policies are not reliably solved at 32k, and multi-head BWT is credibly negative.

Failed / next mechanisms:

1. PPO source training is unstable (seed 0 collapse). Transfer claims should be conditioned on a **solved** source, or the collapse itself should be treated as a first-class failure.
2. Fine-tuning a fully copied solved policy can **hurt** (seed 1, 500 → 204). Need smaller LR / frozen backbone options when the source already solves.
3. Sequential CL at 2k steps/task is still below the scale where specialists learn. Do not enlarge every method until the source curve is stable.

## Files

- `src/nexus/cl/regularizers.py` — per-sample Fisher, per-task snapshots
- `src/nexus/cl/metrics.py` — `cl_evaluation_metrics`
- `src/nexus/cl/v062.py`, `scripts/run_v062_benchmarks.py`, `configs/v062_continual.yaml`
- `artifacts/v062_continual.json`
- `tests/test_v062.py`
