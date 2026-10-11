# NEXUS V0.8.1 — Prediction-to-control transfer

Status: **measured**. Not AGI. V0.8 remains closed as a prediction-adaptation result. This increment asks whether that prediction gain becomes a **control** gain when frozen H=3 is below the CartPole ceiling.

Branch: `cursor/v081-predictive-adaptation`. Parent: `3ca8435`. Artifact: `artifacts/v081_adaptation.json` (n=**10** source-model seeds, wall **431 s**). Prior V0.6–V0.8 JSON files were not overwritten.

## Audit (Phase 1)

V0.8 `split_train_val` shuffles **transitions**, so train and val can share an episode. New work uses `split_by_episodes` (episode-disjoint). Clones and memory snapshots stay parameter-independent (regression tests). Detection and probing env steps are counted inside the target budget.

## Non-saturated tasks (Phase 2)

Weak `force_mag` and one-step action delay still yielded frozen H=3 returns of **500** after the V0.7 recipe. The predefined non-saturation rule that passed screening (frozen planner only, development eval, cap 400) is:

**`obs_noise_std=0.08` on CartPole-v1**, same 4-D observation and 2 actions, plus unused `(g, L, m)` inside safety bounds.

Confirmation offsets were frozen before method ranking (eval seed **101000**). Selection used **development return**, never confirmation.

Source (clean default): H=3 mean **485.5**. Confirmation frozen H=3 mean **289.5 [236, 343]**, fail rate **0.80**. The ceiling problem of V0.8 is removed.

## Detection (Phase 3)

Calibrated on independent **clean source** residuals. Decisions use transition MAE only.

| Stream | Window alarm frac | Notes |
| --- | --- | --- |
| Clean source holdout | **0.00** | empirical FPR |
| Heuristic policy, same physics | **0.00** | policy shift did not trip the window test |
| Source + obs noise 0.08 | **0.758** | delay **31** (first full window) |
| Sequence B (noise + new physics) | **0.758** | miss rate **0** |

Page–Hinkley on the same streams still has source alarm frac **0.230 [0.061, 0.398]** (unusable FPR). The **windowed threshold** is the reliable detector here; the jump in MAE (≈0.005 → ≈0.10) is large.

## Adaptation vs control (Phases 4–5)

Matched target budgets collected with the **frozen MPC** (counted as learning). Episode-disjoint val. Confirmation means over three tasks:

| Budget | Frozen return | Fine-tune | Replay | Adapter | Scratch |
| --- | --- | --- | --- | --- | --- |
| 0 / 64 MAE | 0.101 | 0.096 | 0.094 | 0.100 | 0.153 |
| 64 return | **289.5** | 284 | 286 | 254 | 71 |
| 128 MAE | 0.101 | 0.094 | 0.093 | 0.098 | 0.150 |
| 128 return | **289.5 [236, 343]** | 263 [224, 303] | 246 [229, 262] | 294 [256, 333] | 108 [26, 189] |
| 256 return | 289.5 | 252 | 235 | 296 | 93 |
| 512 MAE | 0.101 | 0.091 | 0.091 | 0.094 | 0.127 |
| 512 return | **289.5** | 213 | 276 | 274 | 36 |

Paired 128 (Student-t, n=10): fine-tune−frozen **−26 [−69, +16]**; adapter−frozen **+4.7 [−49, +59]**; scratch−frozen **−182 [−275, −89]**. All adaptation CIs except scratch **include 0**. Scratch is a clear control failure.

On-policy MAE of planner-visited states at 128: frozen **0.101** vs fine-tune **0.095**. Slightly better fitted residuals did **not** raise return; fail rate rose (0.80 → 0.92 for fine-tune).

Per-task 128: only confirm_1 (hardest) shows a small fine-tune return lift (221 vs frozen 195) with overlapping uncertainty; confirm_0 and confirm_2 frozen remains higher. Heuristic on the logged confirm_0 eval was **500** — the planner, not the env, is the bottleneck.

**MAE improvement is not evidence of better planning on this suite.**

Dev selection often chose **frozen** at 128 (5/10 seeds), consistent with confirmation.

## Memory and A→B→C→A (Phase 6)

After returning to A (128 steps/stage): snapshot source return **298 [262, 334]** vs shared fine-tune **184 [135, 233]** vs retrieve-then-fine-tune **247 [145, 349]**. Shared-model continual learning **forgets control** relative to the stored source snapshot. MAE on A is similar (≈0.093). Memory **≈125 kB**/seed; retrieval **240** inferences/seed. This is snapshot retrieval, not in-network retention.

## Costs

Source collect **1280**/seed; detector calibration **128**/seed; target budget N includes all MPC collect used for adaptation. Not AGI.

## Criteria

1. **Detect mismatch online:** yes for the windowed residual test (FPR 0 on clean/heuristic; delay 31 on noise/B). Page–Hinkley remains unreliable.
2. **Limited adaptation improves prediction:** small MAE drops (0.101 → 0.091 at 512). Modest.
3. **That yields a control advantage:** **not demonstrated**. Paired CIs include 0 or are negative. Scratch destroys control.
4. **Retrieve prior knowledge:** the frozen snapshot beats a shared sequential fine-tune on return-to-A.
5. **Adapt without forgetting:** shared fine-tune forgets A control; memory bytes stay bounded.

Observation noise makes the Markov residual model a poor planner even after extra target data. Next work should not treat CartPole + iid observation noise as solved control transfer.
