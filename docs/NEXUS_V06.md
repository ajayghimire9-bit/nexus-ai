# NEXUS V0.6 — Continual learning and transferable intelligence

Status: first measured CartPole-family continual-learning study. Completing V0.6 is **not AGI**. V0.5.2 research-controller code and artifacts are unchanged.

Branch: `cursor/v06-continual-transfer`. Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v06_continual.py`.

`pytest` **69 passed**. Independent eval seed **70000** (unused in training). All sequential methods used **6144** env steps (3 × 2048). 1315 parameters (1513 for multi-head).

## What is in scope

Compatible tasks share observation/action semantics. The study uses **CartPole-v1 physics variants** (`obs_dim=4`, `n=2` discrete actions):

| task_id | gravity | pole length | pole mass | split |
| --- | --- | --- | --- | --- |
| cartpole_default | 9.8 | 0.5 | 0.1 | source A |
| cartpole_long | 9.8 | 0.8 | 0.1 | source B |
| cartpole_heavy | 9.8 | 0.5 | 0.3 | source C |
| cartpole_lowg | 4.9 | 0.5 | 0.1 | **held-out** |

CartPole and Acrobot are **not** treated as transferable. Acrobot is 6-D / 3-action and is excluded from this protocol.

## Phase 1 — V0.5.2 preserved

- Existing tests still pass.
- Dynamic expression activations store `expr_tree` in checkpoints; `PPOTrainer.from_checkpoint` re-registers them in a **fresh process**.
- `artifacts/v051_*.json` and `artifacts/v052_*.json` were not overwritten. Re-running the paired synthetic 20-seed study reproduced V0.5.2 last-50 opt rates to `1e-9`.
- Matched-compute helper `nexus.meta.matched.apply_matched_compute` raises the experiment-slot cap so the **timestep** cap binds. No large saturated CartPole-250k controller study was repeated.

## Methods (matched steps per phase)

1. **Independent:** one PPO specialist per task (2048 steps each). Final score is specialist-on-own-task. Forgetting is undefined.
2. **Naive:** sequential fine-tuning A→B→C, then eval all.
3. **Replay:** naive + behavior-cloning on a replay buffer filled during PPO collect.
4. **EWC:** naive + diagonal Fisher penalty after each task.
5. **Multi-head:** shared encoder, task-specific policy/value heads.

Then: freeze encoder from naive sequential, train a new head on held-out `cartpole_lowg` vs from-scratch at 2048 steps. Curriculum: fixed order vs random vs competence/uncertainty/forgetting selector (cannot edit eval seeds or step caps).

## Measured results (3 seeds, 8 eval episodes)

Mean final return averaged across the three source tasks, 95% CI:

| Method | mean final (CI) | mean forgetting (CI) |
| --- | --- | --- |
| independent specialists | 101.4 [95.8, 107.1] | n/a (0 by definition) |
| naive fine-tune | 117.4 [94.5, 140.2] | −6.3 [−21.1, +8.6] |
| replay | 115.8 [85.0, 146.6] | **−9.1 [−17.1, −1.0]** |
| EWC | 118.3 [95.1, 141.5] | −7.2 [−22.6, +8.3] |
| multi-head | 140.4 [69.0, 211.8] | +2.8 [−4.0, +9.6] |

Encoder weight transfer vs matched-step scratch on `cartpole_lowg`: **−26.8** [−61.8, +8.2] (point estimate is **negative transfer**; CI includes 0).

Curriculum mean return across tasks: fixed **116.9** [90.0, 143.9]; random **115.2** [111.8, 118.7]; adaptive **95.7** [90.6, 100.9]. Adaptive was worse than random.

### Per-seed notes

- Multi-head seed 0 `cartpole_heavy` eval 476.5 dominates the multi-head mean; the CI is wide and includes the independent baseline.
- Replay seed 0 looked strong (139/156/139) but seed 1–2 did not beat naive. Average return does not beat naive.
- Replay’s forgetting CI is below 0 (later phases did not collapse earlier-task scores on this budget). That is **not** the same as beating naive on final return.

## Verdict vs the V0.6 success criterion

The criterion asked for retention or positive transfer **beyond** from-scratch specialists **and** naive fine-tuning, on independent eval, at matched compute.

**Not met.** EWC ≈ naive. Replay ≈ naive on return. Multi-head’s point estimate is higher but its CI includes independent and naive. Encoder transfer to held-out low-gravity CartPole did not beat scratch. Adaptive curriculum did not beat fixed/random.

This is a small, valid protocol (compatible tasks, matched steps, reserved eval seed). 2048 steps is far below the V0.4 250k CartPole solve budget; returns are mostly 80–160, not solved. Negative results are retained.

Not AGI. Not meta-RL. Not a trading system. Not a claim that CartPole variants imply general transfer.
