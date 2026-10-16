# Multi-step rollout versus objective mismatch — offline audit

Branch `cursor/multistep-rollout-control-audit` from `a9ada15`. Zero new environment steps. Frozen FiLM checkpoints 120/0/0. Confirmation closed. Late-episode capture SHA256 `743b545d78910f7b0df8c83d15b4eb77190798b1dd803ad4daa51434a6214939` unchanged. This audit is descriptive unless noted. It is not a control pass, learning-to-learn, or AGI.

## 1. Can true 2/4/8/16-step open-loop errors be reconstructed?

**Yes, for teacher-forced executed-action free-running.** The late-episode archive stores 200 pre-step observations, executed discrete actions, rewards, 16 planner scores, selected index, planned second action, one-step angular-velocity error, and per-step seeds. `obs[t+h]` is the actual observation after `h` executed actions from `obs[t]` for `t+h ≤ 199`. Horizons 1, 2, 4, 8, 16 therefore have 184 starts per trace. The observation after step 199 is not stored; that single missing frame does not block H=16 windows.

**No, for planned-candidate versus simulator open-loop.** Selected 16-action sequences are not stored as arrays; they are reconstructable from the seed, but their *actual* 16-step environment trajectories were never collected. Replaying those sequences in the simulator would be new environment interactions and is not done here. A planned 16-action trajectory is **not** the next 16 receding actions. Suffix disagreement is a plan-consistency statistic, not world-model error.

The frozen `WorldModel.step` API already normalizes, accepts discrete actions 0/1/2, and does not query the simulator. FiLM context is installed from saved vectors. Episode TimeLimit is not inside the model; windows that would cross step 200 are dropped.

## 2. Offline teacher-forced errors (descriptive, ten-decoder Student-t 95%)

Estimand: from each live start `t ∈ {0,…,183}`, roll the frozen model for `h` steps under the **recorded** action sequence and compare to `obs[t+h]`. Angular-velocity MAE is `|(pred−actual)_θ̇|`. Angle uses wrapped `atan2` distance on `(cos θ, sin θ)`. Observation MAE is the mean absolute error on the raw three-vector and is **not** an angular metric; it is reported only for comparability with earlier PCG state MAE.

Own-path means each model is evaluated on the occupancy it produced. Isolation is the mean of (student-model − zero-model) error on the student path and on the zero path, so occupancy is matched inside each contrast. Isolation is the H1 isolator. Own-path student-minus-zero remains H3-confounded.

| h | Student on student path | Zero on zero path | Isolation (student−zero model) |
|---|-------------------------|-------------------|--------------------------------|
| 1 | **0.086 [0.078, 0.095]** | **0.110 [0.100, 0.120]** | **−0.026 [−0.036, −0.015]** |
| 2 | 0.152 [0.135, 0.168] | 0.195 [0.175, 0.215] | −0.046 [−0.066, −0.026] |
| 4 | 0.285 [0.249, 0.321] | 0.360 [0.315, 0.406] | −0.079 [−0.122, −0.035] |
| 8 | 0.607 [0.514, 0.700] | 0.712 [0.600, 0.824] | −0.106 [−0.216, +0.003] |
| 16 | **1.935 [1.591, 2.279]** | **2.030 [1.627, 2.432]** | **−0.095 [−0.515, +0.325]** |

H=1 reconstruction matched the archived executed one-step angular-velocity errors to `1e-5`. Denominator: 30 decoder×task cells, 184 starts, two recorded paths, four model×path rollouts. Imagined transitions **353,280**. Environment steps **0**. Wall **1.101 s**. Local CPU.

Angle distance (wrapped radians): student own-path H=1 **0.010 [0.008, 0.012]** versus zero **0.007 [0.006, 0.008]**; H=16 **0.667 [0.565, 0.768]** versus **0.638 [0.516, 0.760]**. The student is better on angular velocity at short horizons and is not better on angle. Do not collapse those coordinates.

Prefix-matched same-state H=16 windows exist in **7/30** cells (8 cells have `n_matched ≥ 16`, one of those has a zero-length 16-step prefix). That is too incomplete for a ten-decoder same-state H=16 interval. Isolation on full recorded paths is the complete H1 contrast.

## 3. Student versus zero rollout behavior

At H=1 and H=4 the student model is more accurate on **both** occupancy distributions (isolation interval above is entirely negative). At H=8 the isolation interval includes 0. At H=16 it includes 0 and the mean (−0.095) is small relative to the 1.9-scale error. The one-step student advantage does not survive as an established 16-step advantage.

H=16 own-path errors are large for both visitors: about twenty times the executed one-step MAE (~0.09 / ~0.11). That matches the closed PCG candidate open-loop magnitudes (fresh student 1.159, zero 1.823) in order, on a different split and a different action source (executed live actions here, scored candidates there).

Phase of the start index, own-path angular velocity:

- H=1 early/middle/late: student 0.089 / 0.085 / 0.086; zero 0.123 / 0.100 / 0.107. No late blow-up.
- H=16 early/middle/late: student 1.729 / 2.035 / 2.056; zero 1.909 / 1.843 / 2.381. Compounding is present in every window.

Controllers diverge early (first mismatch **9.6 [4.7, 14.5]**). After mismatch, mean observation L2 is **1.91 [1.48, 2.34]**. Aggregate own-path error and return comparisons mix different states (H3). Isolation already holds occupancy fixed by replaying each recorded action sequence through both models.

## 4. World-model error versus planning-objective mismatch

Evidence matrix (closed results unchanged):

| Status | Finding |
|---|---|
| Demonstrated | Exact H=16 sequence selection incurs **+34.685 [+22.677, +46.694]** 64-step regret versus the best candidate in the same set (`short_objective_misses_practical_value`). This is complete-sequence commitment plus 48 zero-policy steps, **not** receding first-action control. |
| Demonstrated | Student H=16 ranking on those source prefixes is strong (Spearman **0.923**, selected16 regret **0.336**). |
| Demonstrated gap | First action of the best64 sequence loses **20.254 [11.382, 29.127]** under first-action+zero-replan. Selecting the best 16-action block is not selecting the best receding first action. |
| Demonstrated | On live development paths, executed one-step angular-velocity error stays small and the student remains better at H=1/H=4 on matched actions. |
| Demonstrated (this audit, descriptive) | Free-running H=16 error on recorded actions is large (~1.9–2.0) for both models. |
| Inconclusive | Student-minus-zero 200-step late-episode return **−5.414 [−92.420, +81.592]**. |
| Inconclusive | Commit-16 versus recede-fresh 16-step return **−1.787 [−4.324, +0.751]**. |
| Inconclusive | Remaining-horizon versus H=16 200-step return **+0.523 [−0.077, +1.123]**. |
| Inconclusive | Linear and action-conditioned first-action Q versus H=16. Score-correction stays closed. |
| Inconclusive | Same-state late first-action quality **+0.0312 [−0.0827, +0.1452]**. |
| Not available without new env | Simulator-executed candidate open-loop on these development episodes; unevaluated-candidate actual returns. |

H1 (multi-step model error) is **large on live executed actions**. H2 (short objective) is **already demonstrated for complete 16-action commitment versus 64-step value**, and first-action readouts have not turned that into receding control. H3 (different occupancy) is real after step ~10 and is why own-path error is not a same-state ranking test. These remain competing contributions to episode return; this audit does not award a unique cause.

## 5. Plan consistency

Receding disagreement `action[t+1] ≠ planned_second[t]`:

- Student early **0.509 [0.490, 0.529]**; late **0.525 [0.497, 0.553]**
- Zero early **0.544 [0.516, 0.573]**; late **0.548 [0.530, 0.565]**

Fraction of the planned 15-step suffix that disagrees with the next 15 receding actions: student **0.628 [0.621, 0.634]**; zero **0.637 [0.633, 0.641]**. That is receding versus the original plan, **not** prediction error.

Causal components: horizon is fixed at 16 (not shortened); context is frozen. Newly observed states and new candidate draws both change every step and **cannot be separated** from this log. The closed receding-consistency screen already measured same-state search-noise first-action switch **0.500 [0.430, 0.570]** versus state-driven suffix switch **0.200 [0.122, 0.278]**. The planner is not modified.

## 6. Next intervention

Decision rule, registered in code before the frozen-model rollouts: if H=16 own-path angular-velocity MAE ≥ 0.5 for both visitors and the student is not established as more accurate at H=16 on matched actions, propose a **shorter scoring horizon** on 200-step return rather than a ranking-loss retrain or a longer imagination.

That rule selected **`shorter_horizon_control`**. H=8 already sits at 0.61 / 0.71, so the locked contrast uses nested H=8 prefixes of the same 16×16 candidates, not independent (16,8) draws.

Protocol: `docs/NEXUS_HORIZON_OBJECTIVE_CONTROL_PROTOCOL.md`. Collection is **not authorized**.

## 7. Resources and authorization

- Environment steps this audit: **0**
- Imagined transitions this audit: **353,280** (model inference on archived actions only)
- Wall: **1.101 s**
- Training: **0**. Paid services: **0**. Confirmation: unused. Three-action forks: **0**
- Checkpoints: **120 verified, 0 missing, 0 mismatched**
- Exhausted 3600 s ledger and consumed one-runs: not transferred
- Future collection requires a fresh human approval bound to config SHA256 `fc862b46b9ab1163e894acf4a57693282db8d0a20f9f4f35220e0f8f65999b56`, protocol SHA256 `76894e91fe872fe600d652691203e2f38e5b611c96d22d8df527dffb24e93317`, **90 s**, **12,000** real steps, **1,536,000** imagined transitions

Not control improvement, not learning-to-learn, not AGI.
