# NEXUS V0.8.9 — Learning Efficiency and Persistent Online Control

Branch `cursor/v089-learning-efficiency`. Parent `24ca276` (V0.8.8). Artifact `artifacts/v089_learning.json`. Prior artifacts preserved.

Not AGI. MAE ratio **0.97** not retuned.

## Question

Does NEXUS become better at learning new environments because of its past experience?

## Persistent loop

`PersistentSession` keeps one live env across chunked collects. Resets only on termination/truncation or an explicit task switch. Planner RNG, previous action, belief, and episode IDs continue across chunks. Mean MAE-online env resets over 1024 steps: **~3** (genuine CartPole fails), not one reset per chunk.

## Detection (independent streams; no train data)

Source false-alarm fraction **0** for fixed, recalibrated, and deployed-trend detectors. Target delay **31** steps (window), miss **0**. Recalibration on held-out source residuals did not change delay versus the frozen source threshold on this suite.

## Exploitation

Incumbent vs adapted (low-LR when MAE rejected all online candidates). Planner action disagreement **0.6%**. One-step MAE on each controller’s own trajectory ~**0.102** for both. Return Δ **−8.2 [−59, +43]** includes 0. Failures are **not** explained by the planner fleeing into a much worse on-policy region: the two models barely disagree.

## Learning curve (noisy confirm 0, n=10, budgets 0…1024)

Target-validation and probe costs are inside the prefix (25% val, 16-step probe). Source pretrain **1328** steps counted separately.

| Method | Return @1024 | AUC vs frozen (paired) |
| --- | --- | --- |
| Frozen pretrained | **384.3 [331, 437]** | 0 |
| Snapshot retrieval | 384.3 | 0 (memory held only source) |
| MAE-gated online | 384.3 | 0 (**4 proposals / 0 accepts** every seed) |
| Low-LR fine-tune | 380.4 | **−4.4k [−44k, +35k]** includes 0 |
| Replay mix | 402.2 | **−26k [−94k, +42k]** includes 0 |
| Scratch on target | **43.1** | **−337k [−408k, −266k]** excludes 0 (worse) |

Final-return paired vs frozen: low_lr **−3.9 [−68, +60]**; replay **+17.9 [−69, +105]**; scratch **−341 [−406, −277]**. Extra target data did not beat the frozen source model. Scratch never approached it at these budgets.

## Transfer A→B→C→A and A→B→D

Stage cap **224** (one frozen 128/64/32 cycle). Matched-volume D cap **896**.

MAE accepted **0** on naive D, ABC-then-D, and matched-volume D, so those three controllers stayed the source: Δ ABC vs naive **0**, vs matched **0**. AB-then-D **+6.8 [−3.6, +17.1]** vs naive includes 0 (two seeds nonzero). A-return vs source **0**. Prior tasks did **not** reduce D’s data need or raise D’s return under this gate.

## Costs

Wall **220.7 s**. Protocol hash `e10d512ec0a20f05`. `pytest` **224 passed**.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_v089_benchmarks.py
```

Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0.

## Success criterion

NEXUS can persist an episode, detect shifts without false alarms, and propose online updates. It does **not** learn a new environment with fewer interactions because of past tasks, and target adaptation does not beat a frozen pretrained model on control. Negative result. Not AGI.

## Next

The bottleneck remains candidate quality under the frozen MAE gate (4/4 rejects on the 1024-step stream), not episode resets or detector FPR. Do not retune 0.97 from this confirm. No finance, no V0.9, no new architecture family.
