# NEXUS planning-generality diagnostic

Branch `cursor/planning-generality-diagnostic`. Parent `3aceb76` (`cursor/v089-cross-environment-test`). Artifact `artifacts/planning_generality.json`. Prior `artifacts/cross_environment.json` hash **`402ce4151837eb0d` was not overwritten**.

Not AGI. Not learning-to-learn. Independently trained residual world models; tensors remain incompatible across CartPole and Pendulum (no weight transfer). The simulator oracle is **development-only** and is not a learned or deployable controller.

## Why this experiment

The frozen CartPole recipe (residual 64×64, H=3, 16 candidates) did **not** significantly beat random on default Pendulum (`docs/NEXUS_CROSS_ENVIRONMENT.md`: Δ **+143 [−84, +370] includes 0**). This diagnostic isolates horizon, search budget, learned-model error, and the 3-torque interface **without revising that H=3 confirmation**.

## Audit (Phase 1)

| Check | Result |
| --- | --- |
| Pendulum reward | Gymnasium `-(θ² + 0.1 θ̇² + 0.001 u²)` on the **current** state |
| Obs / action | 3-D `[cos θ, sin θ, θ̇]`; discrete torques `{−2, 0, +2}` in model and planner |
| Independent inits | Dev eval seed **168000**; confirm **169000** (not the prior 163000); CartPole **170000** |
| Train / val | Disjoint env-seed collections (`assert_disjoint_seeds`) |
| Inference cost | `InferenceCounter` model-states + `plan_ms` with `enforce_time_budget=False` |
| Prior confirm | `cross_environment.json` still hash `402ce4151837eb0d` |

Architecture stayed residual **(64, 64)**. Width was not raised from confirmation.

## Phase 2 — Horizon grid (development, default g=10, n=5 WM seeds, 1 eval episode)

Two comparisons, architecture fixed:

1. **Fixed candidates** = 16 sequences.
2. **Fixed imagined-state budget** 48 (`n_cand = max(2, 48 // H)`).

| Config | n_cand | imagined / decision | Learned return | Oracle (simulator) | Learned plan ms |
| --- | --- | --- | --- | --- | --- |
| H=3 both modes | 16 | 48 | **−1358 [−1399, −1316]** | −1270 | 0.63 |
| H=8 fixed 16 | 16 | 128 | −1033 [−1072, −994] | −777 | — |
| H=8 budget | 6 | 48 | −1034 [−1100, −968] | −893 | — |
| **H=16 fixed 16** | 16 | 256 | **−621 [−813, −430]** | **−128** | 3.26 |
| H=16 budget | 3 | 48 | −894 [−992, −796] | −674 | — |
| H=32 fixed 16 | 16 | 512 | −872 [−1084, −661] | −128 | 6.48 |
| H=32 budget | 2 | 64 | −1011 [−1118, −905] | −967 | — |

Dev random **−1091 [−1215, −968]**; heuristic **−743**. Val MAE **0.033 [0.019, 0.048]**; multi-step H=3 MAE **0.051**.

**Selection (dev only, frozen before confirm):** max mean return, then cheaper imagined-state count → **H=16, 16 candidates**. H=3 on this development pool is **worse than random**. H=32 does not beat H=16 for the learned model (compounding rollout error). Oracle H=16 and H=32 match (~−128): extra horizon does not help with 16 random sequences once dynamics are exact.

## Phase 3 — Error sources (development)

| Source | Evidence |
| --- | --- |
| **Horizon** | Oracle H=32 − H=3 = **+1143** return; learned H=32 − H=3 = **+485**. Short H=3 cannot score a swing-up. |
| **World model** | Oracle − learned at H=16/32 is large (H=32 gap **+745**). Learned H=16 **−621** vs oracle **−128**. |
| **Search** | At H=32, 16 candidates beat budget-2 by **+139**. At H=16, 16 candidates beat budget-3 by ~**+273**. |
| **Action interface** | 3 torques. Oracle best still **−128**, not near 0 (upright). Discretization and random shooting remain limiting. |

The oracle uses privileged `(θ, θ̇)` and `env.step`. It was **not** run on confirmation.

## Phase 4 — Confirmation (n=10 WM seeds, g∈{8.3, 12.1}, 2 episodes, eval seed 169000)

Protocol hash `c32ee7c682467cf9`. Replication unit = world-model training seed (Student-t 95%, df=9). Episodes within a seed are **not** independent replications.

| Controller | Return | Δ vs random |
| --- | --- | --- |
| Random | −1173 [−1200, −1146] | 0 |
| Heuristic PD | −1085 | +88 (deterministic) |
| H=3 × 16 (not selected) | −955 [−1124, −785] | **+219 [42, 395]** excludes 0 |
| **Selected H=16 × 16** | **−649 [−719, −580]** | **+524 [443, 605]** excludes 0 |

Selected vs heuristic **+436 [366, 505]**. Confirm val MAE **0.035**. Mean plan **3.33 ms** (H=16) vs **0.63 ms** (H=3). Action mix under H=16 ≈ `(0.32, 0.33, 0.35)`; H=3 is biased toward torque −2 (`0.52, 0.19, 0.29`). `used_simulator` is false on every confirm controller. Per-physics selected means: g=8.3 **−479**; g=12.1 **−819**.

This **does not replace** the prior default-g H=3 result (CI included 0). New physics and a new eval seed.

### CartPole regression (same architecture, frozen H=3 MPC)

n=10, eval seed 170000: MPC **500** vs random **15**, Δ **+485** (CI degenerates: every seed 500 vs 15). Recipe still plans on CartPole.

## Phase 5 — Decision

**Success criterion (this diagnostic):** the same residual world-model + random-shooting MPC **mechanism**, with architecture frozen and horizon chosen only on development, improves paired return vs random on untouched Pendulum confirmation **and** still beats random on CartPole.

- Pendulum selected vs random: CI lo **443 > 0**.
- CartPole: still solved under H=3.
- `proceed_to_meta_learning` in the artifact is **true** in that narrow sense.

**What this is not**

- Not representation transfer (weights not shared).
- Not learning-to-learn (algorithm reuse + a development-selected horizon).
- Not reliable swing-up: selected mean **−649** vs oracle-on-dev **−128**.
- Not a license to raise width or MAE 0.97 from this confirm.
- Not a large meta-learner. A **small** next test is allowed: MAE-gated low-LR adaptation on **shifted Pendulum** with **this frozen H=16 protocol**, n=10, vs never-adapt. If that CI includes 0, meta-learning remains unjustified.

Wall **95.4 s**. Python 3.13.5, PyTorch 2.14.1, NumPy 2.5.4, Gymnasium 1.4.0.

```bash
PYTHONPATH=src:.deps python3 -m pytest tests -q
PYTHONPATH=src:.deps python3 scripts/run_planning_generality.py
```
