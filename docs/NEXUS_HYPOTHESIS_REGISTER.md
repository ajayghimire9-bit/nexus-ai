# NEXUS hypothesis register (V0.5–V0.8.9)

Evidence is from committed artifacts unless marked *reproduced this checkpoint*. CIs are seed-clustered Student-t 95% where that protocol existed. Completing a version tag is not AGI.

| ID | Hypothesis | Support | Contradiction | Failure modes | Unresolved | Further work? |
| --- | --- | --- | --- | --- | --- | --- |
| H-V05 | A contextual bandit (LinUCB) can select PPO experiments better than random on independent return | Synthetic bandit: LinUCB beats random/frozen, CI excludes 0 | CartPole/Acrobot independent champion CIs all include 0; frozen point estimate > updating LinUCB | Inner PPO 8k steps too weak; Acrobot all −500 | Would a 250k inner loop change selection? (costly, not learning-to-learn) | **No** as a path to L2L. Keep as a cheap scheduler only |
| H-V06 | Sequential CL (naive/replay/EWC/multi-head) beats specialists on CartPole variants | — | No method beat specialists **and** naive with non-overlap; V0.6.1 FWT **−45 [−85, −5]** | Unsolved source policies; 2–16k steps | Solved specialists + larger replay | **No** on unsolved 8k PPO. Closed in V0.6.6 |
| H-V064 | Encoder transfer (new head) beats scratch | V0.6.4 confirm **+300 [224, 376]** vs scratch | V0.6.5: random encoder + source RMS beats pretrained encoder (**D−B = −110**) | Confounded with RMS; encoder can hurt | When do features transfer after RMS is controlled? | **No** as “representation learning” until RMS is not the whole effect |
| H-V066 | RMS-only reuse is the useful mechanism | B vs A **+222 [173, 272]** | LinUCB choosing `rms_only` did not beat fixed B (CI includes 0) | Normalization ≠ task intelligence | RMS + tiny adapter? | Optional control, not a research engine |
| H-V07 | A residual WM supports planning better than greedy / random | V0.7.3 H=3 **+225 [206, 245]** vs greedy | Ridge one-step can have **worse** MPC if RNG is reset every step (V0.7.1) | Too few candidates at long H; ridge≠residual | Calibrated uncertainty unused | **Keep** as the only reliably positive WM result — on CartPole |
| H-V08 | Fine-tuning the WM on a shifted CartPole lowers error **and** raises return | FT@128 MAE 0.017 vs frozen 0.035 | Planning already 500; no control headroom. V0.8.1: MAE↓ return **263 vs 290** | MAE ≠ control; ceiling tasks | Off-policy error vs planner-state error | **Stop** treating one-step MAE as the objective |
| H-V081 | Residual-error detector finds physics/noise shifts | FPR 0, delay ~31, miss 0 (V0.8.1–V0.8.9, *reproduced delay 31*) | PH/window TPR CIs overlapped in V0.8 | Alarm ≠ useful update | Recalibration vs fixed: no delay difference in V0.8.9 | Detector is adequate; not the bottleneck |
| H-V082 | Belief estimators (Kalman/GRU) improve noisy MPC | — | Identity ≥ Kalman on noisy; Kalman **hurts** clean (281 vs 500); GRU unusable in MPC | Filter mismatch; GRU not in planner | Learned beliefs with training in the loop | **No** until a belief is in the actual planner and wins a paired CI |
| H-V083 | Gated online learning beats never-adapt | — | MAE +12 CI includes 0; always-adapt harmful-commit 0.50 | Wrong control comparison (later fixed) | — | Historical; superseded by V0.8.4+ |
| H-V084 | Fair H=32 control gate selects better models | Engineering: matched seeds, observe-once | **0 accepts** (`tie_or_small_diff`); cartpole saturates at H=32 | Horizon too short | Longer matched H still ceiling in V0.8.5 | **No** as a CartPole gate |
| H-V085 | MAE gate on a shared candidate bank has decision value | Confirm MAE vs never **+50.5 [8.7, 92.2]** excludes 0 | Seed-mean pair Δ vs never includes 0; 6 harmful accepts; later versions do not replicate this gain | Bank ≠ online collection | Was +50.5 luck + ceiling? | **Do not retune**; treat as one unreplicated positive |
| H-V086 | Low-LR candidates are safer than standard FT | Harm 0.25 vs 0.60 on the bank | MAE choice vs never **+5.6** includes 0; online MAE **0** accepts | Too-small updates (see checkpoint audit) | Larger LR + early stop on **independent** val | Only if control CI excludes 0 |
| H-V087 | Online MAE accepts once collection matches the bank (128/64) | Accept rate 0.25 vs 0 for 64/32 split | Δ **+7.5 [−3.5, +18.5]** includes 0 | Size ≠ usefulness | Persistent vs chunked collect | Diagnostic only |
| H-V088 | Change-triggered multi-cycle learning improves control | Detector works; ~0.95 accepts / 3 cycles | Δ **+3.3 [−35, +42]** includes 0; retrieval = gated, not > never | Accepts don’t move MPC | Deployed-data vs frozen pool | **No** further cycles on CartPole without better candidates |
| H-V089 | Past tasks reduce data needed on a new task D | Persistent episodes work | Frozen **384** vs scratch **43**; ABC-then-D Δ **0**; MAE-gated 4/4 rejects | Gate never commits; frozen already strong | If we forced always-adapt on D after ABC | **Falsified** under the frozen protocol |
| H-V089b | Low-LR proposals fail the MAE gate because they are tiny, not because the gate is blind to huge gains | *Reproduced:* ratio 0.996, L2 Δ 0.10, disagreement 2%; 0/40 ≤ 0.97 | 13/40 1-ep Δ≥10 but 13/40 Δ≤−10; seed Δ includes 0 | 1-ep control is a weak audit | Multi-episode matched control on the same 40 pairs | **Do not retune 0.97** |

## Mechanisms that have never shown useful transfer

These produced no paired control/sample-efficiency gain that survived an independent confirm:

1. Sequential naive fine-tune / replay / EWC / multi-head on CartPole variants (V0.6).
2. Learned experiment selection on real PPO (V0.5).
3. Encoder-only reuse after RMS is controlled (V0.6.5).
4. GRU/stack beliefs in the planner (V0.8.2).
5. Uncertainty-directed collection (V0.8).
6. Fair H=32 control gate (V0.8.4).
7. Probe-MAE snapshot retrieval without task labels (V0.8.8–V0.8.9).
8. ABC experience as initialization for D under MAE (V0.8.9).
9. Always-adapt online (often negative point estimates).

**Normalization reuse (RMS)** transferred vs scratch. That is a statistics-copy, not an improving learner.

## Unresolved scientific questions

1. Can any CartPole WM update improve H=3 MPC return vs frozen with a CI excluding 0 **and** without retuning 0.97?
2. Does the V0.7 residual+H=3 recipe plan at all off CartPole?
3. Is one-step MAE on incumbent actions the wrong proxy for planner-relevant error (multi-step / near-failure)?
