# NEXUS V0.8.3 — Decision-aware autonomous learning

Status: **measured**. Not AGI. Not V0.9. V0.8.2 MAE-gating still did not protect control; this increment tests **online** detect/adapt cycles and **decision-aware** commit rules under a hard target cap.

Branch: `cursor/v083-decision-aware-learning`. Parent: `5ff59a1`. Artifact: `artifacts/v083_learning.json` (n=**10**, wall **306 s**). Prior JSON preserved.

## Accounting (Task 1)

`InteractionLedger` now charges every target env step to **exactly one** of `detect` | `adapt_collect` | `online_val`. Pretrain and eval-only are separate. `bucket_sum == target_used`. Cap overruns raise. Zero-budget collect creates **no** env. Confirmation rows: `no_double_count` **true** throughout. Mean pretrain **1328**/seed (train+val+detector calib on source). Detector calib is pretrain, not the target cap.

V0.8.2 bugs fixed: unused 1-step empty collect; detect bucket assigned on the same steps as adapt (double-label); uncharged sequence probe collect.

## Online loop (Task 2)

Each step: observe → estimate with **previous executed action** → plan H=3 → act → residual error → window detector → optional adapt/verify. Multiple detect/adapt cycles per task. Episode reset clears estimator and planner RNG.

## GRU (Task 4)

GRU is **estimation-only**. It is **not** used inside MPC (imagination would not unroll hidden state consistently). Protocol flag `gru_in_mpc: false`.

## Decision gates (Task 3)

A never · B always-commit · C val-MAE (−3%) · D action-consistency (MPC greedy disagreement ≥15% and MAE not worse) · E control-validation (candidate val return ≥ recent deployed return). Val steps for C–E are charged to `online_val`. Confirmation returns are **not** used to decide.

## Noisy confirmation (obs_noise=0.09, new physics, eval seed 111000)

H=3 mean over two noisy tasks:

| Policy | Return @128 [t 95%] | vs never | Harmful-commit rate |
| --- | --- | --- | --- |
| Never | **225 [184, 265]** | — | — |
| Always | 232 [187, 276] | **+6.8 [−25, +39]** | **0.50** |
| MAE | 237 [194, 279] | **+11.9 [−12, +36]** | **0.35** |
| Action | 225 [185, 265] | **+0.3 [−0.4, +1.1]** | **0.00** |
| Control | 225 [184, 265] | **0** | **0.00** |

All paired CIs **include 0**. Mean commits @128: always 3.0, MAE 1.25, action 0.05, control **0**. Action/control **cut harmful updates to 0** by almost never committing. They do **not** beat never-adapt on return.

@256 MAE **266 [208, 324]** vs never **225** (still overlapping). Always **217** (worse point estimate). Clean unused physics: all policies **500** (ceiling; not an estimation test).

## A→B→C→A (Task 6)

Return to A: never / control-gated / snapshot / retrieve **286 [232, 339]** vs naive shared always-FT **116 [93, 139]**. Control-gating **prevented the forgetting** of naive sequential fine-tunes by refusing commits (same controller as snapshot). That is **not** in-network retention.

## Criteria

1. **Decision-aware verification vs MAE-only:** action/control gates have **lower harmful-commit rates** (0 vs MAE 0.35 vs always 0.50).
2. **Improve control vs never-adapt:** **not demonstrated** (paired CIs include 0).
3. Online accounting and prev-action estimators: yes.
4. GRU as valid belief-MPC: **no** (excluded).

Not AGI. A return-based gate that actually spends val budget and still commits when the candidate is better remains open — the current control gate never committed on noisy confirm.
