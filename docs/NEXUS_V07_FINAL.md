# NEXUS V0.7 — Final report (world models and planning)

Status: **V0.7 research track complete.** Branch `cursor/v073-planning-final`. Not merged. Not AGI. **V0.8 is not implemented.**

Parent confirmation commit `6f0e3d3`. Frozen recipe from V0.7.2. Artifact `artifacts/v073_world_model.json`. Prior V0.6 and V0.7 JSON files were not overwritten.

`pytest` **134 passed**. Confirmation wall **114 s**. Reproduce: `PYTHONPATH=src:.deps python3 scripts/run_v073_benchmarks.py`

This document distinguishes **demonstrated prediction**, **demonstrated planning**, and **failed or incomplete transfer**. A positive confirmation was not required to close V0.7; the confirmation happened to be positive on CartPole physics variants.

---

## Frozen planner (not retuned)

Residual 2×64 MLP, 1024 train + 256 val env steps, 20 epochs, CPU. MPC objective = predicted +1 reward plus `-(|θ|+0.25|ω|)`, absorbing survival, persistent episode RNG. Eval budget 48 state-predictions/decision: H=1×48, **H=3×16**, H=6×8. Confirmation eval seed **87000**. Three new physics tasks `cartpole_v073_{0,1,2}` (g,L,m) = (7.5, 0.42, 0.13), (10.5, 0.58, 0.09), (13.0, 0.35, 0.18). Not V0.6.x offsets and not V0.7.0 transfer (11, 0.45, 0.15). **No hyperparameter change after seeing confirmation returns.** Imagined rollouts do not call the simulator and do not read target `gravity/length/masspole`.

n=10 independent collection/init seeds. Student-t 95%, replication unit = model-training seed. Mean learning interactions **1280**/seed. Mean imagined state inferences **8.73×10⁵**/seed (all H=1/3/6 × 4 tasks × eval).

---

## Confirmation results (untouched physics + seed 87000)

| Controller | source CartPole | confirm mean (3 tasks) |
| --- | --- | --- |
| One-step greedy | 270 [252, 289] | 260 [241, 279] |
| H=1 MPC (48 cand) | 269 [246, 292] | 267 [249, 284] |
| **H=3 MPC (16 cand)** | **500** | **486 [485, 487]** |
| H=6 MPC (8 cand) | 414 [386, 442] | 368 [345, 391] |
| Hand heuristic | 500 | 500 |

Paired on confirmation (n=10):

- H=3 − greedy **+225 [206, 245]**
- H=3 − H=1 **+219 [202, 237]**
- H=6 − H=3 **−118 [−140, −95]**
- H=3 − heuristic **−14.1 [−15.0, −13.2]** (still below the analytic controller)

Per confirm task, H=3: v073_0 **500**; v073_1 **498 [496, 500]**; v073_2 **459 [458, 460]** (harder: g=13, short heavy pole). No seed had H=3 mean <450. Greedy on v073_2 is only **162 [151, 174]**.

**Horizon-3 planning gain survives shifted CartPole physics without adapting the world model.** It does not match the hand controller on the hardest variant. H=1 matches greedy (same ranking, more random shooting noise). H=6 is worse than H=3 at this frozen budget (candidate starvation, as in V0.7.2).

In-distribution source with new eval seeds: H=3 is **500** on all 10 seeds; H=3 − greedy **+230 [211, 248]**.

---

## 1. Demonstrated prediction

- Residual MLP one-step MAE ≪ persistence on held-out default CartPole (V0.7.0–V0.7.2).
- Ridge is even more accurate one-step (~1e-4) because local Euler dynamics are nearly linear.
- Multi-step open-loop error grows with horizon (V0.7.0/V0.7.2).
- Source RMS helps **policies** (V0.6), not as a substitute for dynamics weights (V0.7.0).

## 2. Demonstrated planning

- After **persistent episode RNG**, short-horizon shooting (H=3, 16 candidates) beats one-step greedy with CIs excluding 0 on source **and** on frozen confirmation physics (this report).
- Planner never steps the Gymnasium env during imagination.
- Matched H=1 ≈ greedy; extra horizon without extra candidates (H=6, 8 shots) hurts.

## 3. Failed or limited transfer / planning

- **V0.6 encoder weight transfer** does not survive RMS controls.
- **V0.7.1 ridge MPC return ≈ 9** was an RNG bug (identical candidates every step), not proof that accurate models cannot plan.
- **Uncertainty penalties** did not beat cost-matched ensemble-zero (V0.7.1–V0.7.2 CIs include 0).
- **Learned terminate heads** were miscalibrated (ridge Brier worse than always-nonterminal); they were **not** the cause of the RNG collapse.
- **H=10–20 at budget 48** fail from too few sequences.
- **H=3 still loses to the hand heuristic** on g=13 confirm (−14 overall; task 2 mean 459 vs 500).
- **No Dreamer-scale model, no image POMDP, no V0.8 adaptation loop.**
- Sources for V0.6 PPO remain unsolved at short caps; planning here uses a **learned dynamics model + shooting**, not a solved actor.

---

## Costs (confirmation)

| Item | Amount |
| --- | --- |
| Train + val env steps / seed | 1280 |
| Confirm eval seed | 87000 (unused in V0.7.0–V0.7.2 control) |
| Mean model inferences / seed | 8.74e5 |
| Wall | 114 s |

---

## Close V0.7

**Yes.** PREDICT and PLAN are characterized on CartPole: one-step dynamics are learnable; short-horizon MPC with a persistent RNG and a recorded eval budget is a real, transferable (within this family) improvement over greedy; long horizon and uncertainty tricks are not free wins.

**V0.8 question (not this branch):** can an agent **reuse and update** a previously learned world model to adapt to unfamiliar dynamics with fewer interactions than training from scratch—without retuning on the confirmation suite used here?
