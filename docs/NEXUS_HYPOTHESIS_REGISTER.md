# NEXUS hypothesis register (V0.5–V0.8.9)

## Latest — H-lookahead-beats-h3-on-unsaturated-cartpole was not established

The complete six-task screen failed the 25-point rule: lookahead minus H=3 **14.000 [−4.621, 32.621]**. Label `cartpole_sat_lookahead_not_established`. Ceilinged tasks were kept. Do not retune H=3 from this sample. CartPole lookahead versus H=3 is now not established on three development draws. Report `NEXUS_CARTPOLE_LOOKAHEAD_SAT_RESULTS.md`.

## Latest — H-lookahead-beats-h3-on-unsaturated-cartpole is implemented, not yet tested

The H=3-only diagnostic passed. This protocol tests one-step backup of frozen H=3 versus receding H=3 on the same six-task split `a69833ab38a34ab4`, margin 25. Ceilinged tasks are kept. Collection unauthorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_SAT_PROTOCOL.md`.

## Latest — H-frozen-h3-unsaturated-on-stricter-cartpole passed; lookahead still untested

The complete H=3-only diagnostic passed the 25-point gap-from-ceiling rule: **33.183 [2.481, 63.886]**. Label `cartpole_h3_unsaturated`. Lookahead was not run. 50/60 episodes still hit 500; do not drop those tasks. A later lookahead-versus-H=3 screen on this same holdout is unimplemented. Report `NEXUS_CARTPOLE_H3_SATURATION_RESULTS.md`.

## Latest — H-frozen-h3-unsaturated-on-stricter-cartpole is implemented, not yet tested

Two CartPole lookahead screens could not measure lookahead because H=3 was at the TimeLimit. This diagnostic keeps frozen H=3, withholds lookahead, and tests six unused stricter-corner physics, margin 25 below 500. Collection unauthorized. Report `NEXUS_CARTPOLE_H3_SATURATION_PROTOCOL.md`.

## Latest — H-lookahead-beats-h3-on-hard-cartpole was not established (still near ceiling)

The complete harder-physics screen failed the 25-point rule: lookahead minus H=3 **4.600 [−7.481, 16.681]**. Label `cartpole_hard_lookahead_not_established`. Frozen H=3 was already at the 500-step cap on 8/10 seed means and 28/30 episodes. Do not retune H=3 from this sample. Report `NEXUS_CARTPOLE_LOOKAHEAD_HARD_RESULTS.md`.

## Latest — H-lookahead-beats-h3-on-hard-cartpole is implemented, not yet tested

The ceilinged CartPole draw could not measure lookahead. This protocol keeps frozen H=3 and tests unused hard physics in the published V0.7.3 off-ceiling region, margin 25. Collection unauthorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_HARD_PROTOCOL.md`.

## Latest — H-lookahead-beats-frozen-h3-on-cartpole was not established (ceiling)

The complete development screen failed the 25-point rule: lookahead minus H=3 **4.000 [−5.048, 13.048]**. Label `cartpole_lookahead_not_established`. Frozen H=3 was already at the 500-step cap on 9/10 seeds. Do not retune H=3 from this sample. Report `NEXUS_CARTPOLE_LOOKAHEAD_RESULTS.md`.

## Latest — H-lookahead-beats-frozen-h3-on-cartpole is implemented, not yet tested

Pendulum lookahead transfer passed and is not used to copy H=16 onto CartPole. This protocol tests one-step backup of frozen CartPole H=3 open-loop value versus H=3 receding on unused CartPole physics, margin 25. Collection unauthorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_PROTOCOL.md`.

## Latest — H-lookahead-transfers-to-new-physics passed on one Pendulum holdout; not L2L

The complete transfer screen passed the 25-point episode rule: lookahead minus frozen H=16 **98.608 [43.258, 153.957]**. Label `lookahead_transfer_established`. Successor value remained open-loop H=16 from s'. Student-minus-zero includes 0 and is a separate estimand. This is not cross-family transfer, learning-to-learn, or AGI. Do not retune from these outcomes. Report `NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_RESULTS.md`.

## Latest — H-lookahead-transfers-to-new-physics is implemented, not yet tested

Development lookahead versus H=16 passed. Transfer uses a new holdout (`73844661addfa11b`), not historically exposed confirmation physics. Primary: lookahead minus H=16 200-step return, margin 25. Student-versus-zero is secondary and cannot upgrade. Collection unauthorized. Report `NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PROTOCOL.md`.

## Latest — H-lookahead-beats-h16 passed on development; Bellman consistency is not isolated

The complete development screen passed the 25-point episode rule: lookahead minus frozen H=16 **155.647 [109.825, 201.469]**. Label `bellman_backup_improves_episode_return`. Successor value was frozen open-loop H=16 from s', not receding-policy Q. H1 remains the supported mechanism class; this result does not prove Bellman consistency. Confirmation transfer is untested. Report `NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md`.

## Latest — H1 planning-objective mismatch is best supported; H-bellman-backup-beats-h16 is unimplemented

Offline receding-value audit: H1 (open-loop plan value ≠ first-action+replan value) is the strongest supported explanation of long-horizon control failure. H2 (Q coverage/representation) explains closed 64-step Q/V failures, not the deployed rule. H3 (policy-induced distribution shift) is not isolated. Nested H=8, score-correction, and fitted Q/V stay closed. One locked test: parameter-free Bellman backup of frozen H=16 open-loop value versus frozen H=16 receding on 200-step development return, margin 25. Collection unauthorized. Report `NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md`.

## Latest — H-shorter-horizon-improves-episodes was rejected; nested H=8 hurt return

The complete development screen failed the improvement rule and met the hurt rule: H=8 minus H=16 **−174.178 [−265.830, −82.527]**. Label `shorter_horizon_hurts_episode_return`. Executed one-step MAE stayed small. Do not retune H∈{4,8,16,32} on this sample. Report `NEXUS_HORIZON_OBJECTIVE_CONTROL_RESULTS.md`.

## Latest — H-multi-step-error-accumulates-on-live-actions is descriptively large; H-shorter-horizon-improves-episodes is unimplemented

Teacher-forced H=16 angvel MAE on recorded development actions is **1.935 / 2.030** (student / zero own-path). Isolation **−0.095 [−0.515, +0.325]** includes 0. H=1 isolation excludes 0 favoring the student. Exact H=16 sequence-versus-64-step objective mismatch stays demonstrated and closed. Nested H=8 200-step control is locked and unauthorized. Report `NEXUS_MULTISTEP_ROLLOUT_CONTROL_AUDIT.md`.

## Latest — H-student-late-executed-error-grows-faster was not established

The complete development screen failed the 0.05 practical margin: growth_diff **+0.016 [+0.003, +0.029]**. Label `late_error_growth_not_established`. The lower bound is above 0 but the mean is too small. Student executed MAE did not rise late; zero improved more. Episode return includes 0. First mismatch mean 9.6 steps. Do not retune. Report `NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_RESULTS.md`.

## Latest — H-student-late-executed-error-grows-faster is implemented, not yet tested

Archives cannot reconstruct per-step scores or executed one-step errors on 200-step episodes. The locked development experiment logs paired H=16 receding traces with shared candidate seeds. Primary: differential late-minus-early executed angular-velocity error, margin 0.05. Same-state prefix until first mismatch; later steps are different-state. Three-action late-state forks stay closed. Collection unauthorized. Report `NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_PROTOCOL.md`.

## Latest — H-episode-loss-is-a-first-horizon-ranking-miss is not supported by recorded traces

Exploratory decoder-level splits of closed return-phase rewards (not a new primary, `primarily_late` unchanged): steps 16–63 **+0.307 [−4.144, +4.759]** include 0; steps 64–127 and 128–199 exclude 0. Combined with strong source H=16 ranking and PCG ranking-without-control, further initial-state ranking screens are lower information than episode-level diagnosis. Report `NEXUS_NEXT_DIRECTION_ASSESSMENT.md`.

## Latest — H-decision-relevant-score-error was not established on source

Independent recomputation of frozen `planning_value` prefixes and scores found student near-best minus dominated H=16 absolute error **+0.577 [−0.233, +1.387]**, n=10 decoder units, τ=1. Label `source_h1_not_established`. 16-step ranking is already strong (Spearman **0.923 [0.874, 0.973]**). Closed prediction-control-gap fresh ranking gains with episode loss stay closed and already reject “better prediction, worse ranking” on that split. Decision-aware training is not justified. A development diagnostic is locked and unauthorized. Report `NEXUS_DECISION_AWARE_WORLD_MODEL_AUDIT.md`.

## Latest — H-decision-relevant-score-error is implemented, not yet tested

The remaining open measurement is whether development physics with fresh seeds show concentrated H=16 score error on near-best candidates. Primary: student near-best minus dominated absolute score error, mean ≥ 1 and lower bound > 0. Episode return is a separate secondary and cannot pass the screen. Collection unauthorized. Report `NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL.md`.

## Latest — H-remaining-horizon-beats-fixed-H16 was not established on episodes

The complete development screen failed the 25-point full-episode rule: remaining-horizon minus fixed H=16 **+0.523 [−0.077, +1.123]**. Label `boundary_specific_alignment`. The 16-step diagnostic passed its own margin and all episode difference was in the last 15 steps. Close general horizon alignment rather than retuning. Report `NEXUS_HORIZON_ALIGNMENT_RESULTS.md`.

## Latest — H-remaining-horizon-beats-fixed-H16 is implemented, not yet tested

The previous 16-step H=16 loss is an artificial cutoff, not episode termination. The locked experiment compares remaining-horizon `H=min(16, remaining)` with fixed H=16 on complete 200-step development episodes (primary, margin 25) and a 16-step diagnostic (cannot upgrade). Shared per-step seeds must match actions on steps 0–184. Collection unauthorized. Report `NEXUS_HORIZON_ALIGNMENT_PROTOCOL.md`.

## Latest — H-same-set-beats-equal-horizon-fresh was not established

The complete development screen failed its registered pass rule: same-set minus equal-horizon fresh **+0.834 [−0.955, +2.623]**. Label `same_set_advantage_not_established`. Remaining-horizon methods beat production H=16 only as secondaries and cannot upgrade the primary. Do not retune same-set versus equal-horizon fresh. Report `NEXUS_SAME_SET_PLANNING_RESULTS.md`.

## Latest — H-same-set-beats-equal-horizon-fresh is implemented, not yet tested

Retrospective source evidence that same-set suffix receding beat recede-fresh and commit-16 is decoder-consistent but confounded by remaining-horizon mismatch. The locked development experiment equalizes candidate count and scored horizon for same-set versus fresh draws; production H=16 receding is a separate unequal-budget baseline. Collection unauthorized. Reports `NEXUS_SAME_SET_PLANNING_AUDIT.md` and `NEXUS_SAME_SET_PLANNING_PROTOCOL.md`.

## Latest — H-commit-beats-replan was not established

The complete source screen failed both registered pass rules: commit-16 minus recede-fresh **−1.787 [−4.324, +0.751]**. Label `replan_consistency_not_established`. Recede-same-set beat both open-loop commitment and recede-fresh as a secondary only and cannot upgrade the primary. Report `NEXUS_RECEDING_POLICY_CONSISTENCY_RESULTS.md`.

## Latest — H-commit-beats-replan is implemented, not yet tested

After score-correction closed, the remaining control question is whether receding replanning loses 16-step return relative to executing the H=16 selected sequence from the same restored source state. Search noise at that state is measured separately from state-driven re-ranking of the same 16 suffixes. Collection unauthorized. Archived live suffix mismatch is confounded and is not this test. Report `NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL.md`.

## Latest — H-action-conditioned-Q did not establish a first-action gain

The resumed complete 60-cell development screen failed its registered pass rule: conditioned−H=16 **−4.293 [−15.751, +7.165]**. Label `action_conditioned_gain_not_established`. H-additive-enough is not supported as a decision upgrade (conditioned−additive includes 0). Close score-correction rather than enlarging the readout. Report `NEXUS_ACTION_CONDITIONED_Q_RESUME_RESULTS.md`.

## Latest — H-resume-valid is implemented, not yet tested

The incomplete 59/60 action-conditioned grid can be completed only if the missing zero-visitor cell (decoder 9, development task 2) is independently generated from locked seeds and frozen fits, the 59 cells reconstruct, and assembly refuses to replace completed outcomes. If reconstruction fails, the hypothesis is rejected in favor of a fresh full run. Collection unauthorized. Report `NEXUS_ACTION_CONDITIONED_Q_RESUME_PROTOCOL.md`.

## Latest — H-action-conditioned-Q execution incomplete

The registered development screen did not complete: timeout at 240 s, 59/60 evaluation cells. That is not a pass, fail, or equivalence result for first-action return versus H=16. Source labels and both Q fits were frozen before the timeout. A new approval is required to finish or rerun. Report `NEXUS_ACTION_CONDITIONED_Q_RESULTS.md`.

## Latest — H-action-conditioned-Q is implemented, not yet tested

Additive first-action Q, including the unexecuted 81-coefficient polynomial, cannot change preferred action across states. A compact action×observation family (16 weights) can, on synthetic data. Source-only cross-task identification on 24 historical unique labels is 0.463 versus additive 0.312; action×context was not justified. The locked experiment collects two distinct source states per task and compares action-conditioned Q, additive Q, frozen sequence-value and H=16 on new development visited states. Collection unauthorized. If that screen fails, close score-correction rather than enlarging the readout. Reports `NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md` and `NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md`.

## Latest — H-capacity-matched-Q is implemented, not yet tested

The 15-coefficient miss left open whether aligned first-action labels fail because of capacity. The locked 81-coefficient protocol reuses V's 77 polynomial coordinates plus three action dummies, ridge λ=1. Offline diagnostics show only 24 unique source labels versus 81 weights, rank 50, and state-independent action ranking. That does not answer the decision question. Collection is unauthorized until a fresh 150 s / 29,880-step approval. If the complete run fails the registered first-action screen, close this score-correction branch. Report `NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md`.

## Latest — H-aligned-Q not established for the 15-coefficient linear readout

A source-trained linear Q(s,z,a) with 15 coefficients did not raise development first-action 64-return versus frozen H=16: **−3.535 [−9.840, +2.769]**, n=10 decoder units. The registered gain screen failed. Source RMSE remained ~70, so the aligned-label hypothesis was not given a capacity-matched test against sequence-value V. Sequence-value itself also did not beat H=16 on this sample. No architecture change is justified. Unknown: whether the same first-action labels become useful with the 77-coordinate polynomial feature class already used by V. Report `NEXUS_FIRST_ACTION_VALUE_RESULTS.md`.

## Latest — H-objective alignment gap supported on the recorded suite

The best actual64-value sampled sequence's first action loses **20.254 [11.382,29.127]** under forced-first-action+63zero replanning versus the best measured action, across ten decoder units. All60 states cover all3first actions, so the gap is not absent-action coverage. Represented-action and total regret are identical here and are dependent evidence. The exploratory screen passed. However, this is not the globally best sequence, limited future-suffix search is not excluded, and the zero continuation is not a student full-policy value. Learned-baseline versus sequence-reference first-action comparisons remain inconclusive. Further work justified: a source-only readout trained to the actual replanning intervention and evaluated on fresh states, not more scalar tuning. Report `NEXUS_ACTION_VALUE_ALIGNMENT_RESULTS.md`.

## Latest — H-magnitude source-scalar screen failed

The prespecified source-only covariance rule selected common beta0.823947 before fresh visited outcomes. It improved centered prediction error by **+221.281 [73.560,369.002]** but did not establish chosen64 return improvement: calibrated−base **−9.228 [−22.358,+3.901]**, calibrated−original **+1.194 [−0.102,+2.489]**. Both primary return intervals include zero, and no task/visitor subgroup establishes a gain. No claim that all calibration fails or that a scaling-only cause is disproven. Decoder intervals are conditional on the shared source-fitted scalar; uncertainty in fitting beta is not included. Further scalar tuning on this closed data is unjustified. One next question: does even perfect full-sequence value ranking align with executing its first action then replanning? Existing16-sequence and three first-action outcomes can support a separate exploratory offline audit. Report `NEXUS_SOURCE_SCALAR_RESULTS.md`.

## Latest — visited-state value information is mixed

The exploratory intersection screen failed: centered tail benefit **−1,194.516 [−2,025.559,−363.473]** despite tail pair-ordering advantage **+0.05597 [0.00432,0.10763]**, ten decoder units. Label `tail_centered_error_worse_than_constant`. Thus this finite suite supports poor candidate-relative error magnitudes, but contradicts a blanket claim that no ordering information survives. Fixed-source-constant absolute MSE benefit includes zero, so do not claim reliably worse absolute calibration. Prefix/tail combination remains unresolved: research-only actual-prefix substitution is descriptive, not a causal intervention on a learned controller. No new environment data, neural inference or training; parent return effects are duplicate evidence. Further work justified: a source-only scalar calibration test on separately registered visited-state data, not larger encoders or tuning on this sample. Report `NEXUS_VISITED_VALUE_RANKING_RESULTS.md`.

## Latest — H-persistence, complete but not established

The initial-state correction×commitment benefit did not establish a positive replication at phase50 visited states: interaction **−5.999 [−22.293,+10.295]**, n10 independently pretrained decoders, all five scoring students and both visitors averaged inside decoders. Full-sequence gain **−7.784 [−22.369,+6.800]**. Both registered screen conditions failed. This is inconclusive regarding a nonzero effect, not equivalence or a universal negative. Visitor/task intervals also include zero. The posthoc paired decline relative to the old initial-state sample is **−45.365 [−72.104,−18.625]**, but states, candidates and resets differ, so it does not isolate a causal distribution effect. No controller modification is justified. Unknown: whether the fixed readout loses within-state candidate discrimination at visited states. A separately registered offline audit can use already recorded outcomes without training or new data. See `NEXUS_VISITED_COMMITMENT_RESULTS.md`; all earlier claims/results are retained.

## Latest — H-commitment, completed development diagnostic

The same-state experiment supports sensitivity to commitment length: corrected-minus-original return gain16 minus gain1 is **+39.366 [26.247,52.484]** across ten independent decoders. Gain16 **+36.710 [26.599,46.821]**; gain1 **−2.656 [−7.215,+1.904]**. Both registered screen conditions passed. This distinguishes a commitment interaction from the earlier unmatched-state comparison. All three task-level interactions are positive, but only two initial states per known development physics were sampled. Zero-context correction also has a positive interaction, so student context is not established as necessary. Corrected sequence commitment remains descriptively below original first-action return. Full-episode usefulness and late-state persistence remain unknown. No model training, confirmation reuse, or control-generality claim. Raw artifact `artifacts/commitment_value.json`, SHA1844bf2a97316cf8a2c5e4a00ef145c03c88bb693632c5fc3b13181865975623; report `NEXUS_COMMITMENT_VALUE_RESULTS.md`.

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
| H-V089c | Frozen H=3 residual MPC beats random on Pendulum | — | Default-g confirm Δ **+143 [−84, +370] includes 0** | Horizon too short vs dt=0.05 s swing-up | New g/eval later showed H=3 Δ>0; do not overwrite H1 | **H1 failed**; keep the artifact |
| H-V089d | A longer development-selected horizon of the **same** planner beats random on new Pendulum physics | Confirm H=16 Δ **+524 [443, 605]**; CartPole H=3 still 500 | Oracle-on-dev **−128** vs learned **−621**; not swing-up | Search and WM error remain | — | Diagnostic closed |
| H-V089e | MAE-gated low-LR beats frozen H=16 MPC on shifted Pendulum | Always-adapt **+211 [134, 288]**; low-LR **+106 [39, 173]** vs frozen | **Primary MAE-gated +29 [−28, +86] includes 0** | Gate rejects useful updates / accepts mixed harm | Control-based gate as a **new** pre-register, not 0.97 retune | **No** meta-learning on the MAE inner loop |
| H-V089f | A→B→C reduces data needed on Pendulum D | — | ABC vs naive **+22 includes 0**; vs matched **−6 includes 0** | Same as CartPole V0.8.9 | Different inner adapter | **L2L not shown** |
| H-V089g | First-order Reptile init adapts faster than matched-data multitask on new Pendulum physics | Multitask beats source AUC **+163k [70k, 257k]** | Reptile − multitask AUC **−765k** excludes 0 (worse); Reptile ≈ scratch | Reptile interpolation destroyed useful init; inner k/ε not tuned on confirm | MAML / more outer steps would be a **new** pre-register | **No.** Do not scale meta-learning from this. This does not disprove Reptile in general |
| H-V089h | Transition-context FiLM adapts with fewer Pendulum steps than multitask fine-tuning | Encoder L2 Δ **1.52**; returns finite | Dev primary AUC real **−755** vs fine-tune **−454**; real−zero **−103**; real−wrong **−30**. All gate signs negative | Weaker (48, 48) trunk; z poorly separated; real context hurt control | Diagnosis below. Do not open the unused confirmation tuples | **Inconclusive** on the locked confirm test (not run). Development screen **failed** |
| H-length / H-context | Varied support length helps short histories; real context lowers held-out prediction error | Variable−fixed control point estimate **+22**; source real MAE does not beat zero for the fixed trainer | Source fixed real MAE **0.0703** vs zero **0.0700** at budget 128; dev real **0.084** vs zero **0.077**. Control intervals include 0 | Context raises angular-velocity error; ‖z_real−z_wrong‖ ~0.2. Zero-context control still ~146 below the MLP | Optimization diagnostic below. The old artifact key name is unchanged | **H-context not supported** on the fixed trainer. **H-length not established** (interval includes 0) |
| H-optimization | More Adam updates make real context beat zero and wrong context on held-out source prediction | First 300 updates reproduce the diagnosis. Selection angvel falls from **0.150** at 300 updates to **0.136** at 3000 | Audit at 3000: real angvel **0.1264** vs zero **0.1256** vs wrong **0.1234**. Benefits **−0.0008** and **−0.0030**, intervals include 0. Screen failed (1/3 seeds) | Extra updates improved the shared dynamics. Real context stayed worse than zero | Freeze the 3000-update trunk and train only the encoder/FiLM. Do not add updates or open confirmation | **Not supported.** Dynamics improved. Context use did not |
| H-frozen | With the trunk frozen, encoder and FiLM training makes real context beat zero, wrong, and a constant context on a fresh source audit | Checkpoint 0 reproduces the 3000-update selection angvel **0.1363**. Selection real angvel falls to **0.118** at 1000. Frozen hashes unchanged. Encoder L2 **1.60–2.32** | Audit real **0.1484** vs zero **0.1159**, wrong **0.1207**, constant **0.1127**, start **0.1482**. Positive seeds **0**. MAE and horizon 16 exceed the 5% harm limit. Screen failed | Real context is worse than the same model's zero context. The history-free vector is near the MLP; the encoder is not | Directly optimize a latent context with no history encoder. Do not add encoder updates or open confirmation | **Not supported.** History use is absent |
| H-latent | With all network weights fixed, a latent vector optimized from a task's support transitions improves held-out query angular-velocity MAE over zero context, a global task-independent vector, and a vector optimized from wrong-task support | Fresh source audit, rule Adam 0.1 × 256 from the global vector. Task angvel **0.0628** vs zero **0.1151**, global **0.1109**, wrong **0.1762**. Paired control−task intervals exclude 0. Positive seeds **3/3**. Support loss **0.00114 → 0.00030**. Frozen hashes unchanged. Screen passed | Cos and sin point estimates are slightly higher than the global vector; those paired intervals include 0. The frozen encoder on the same rows is **0.1256**, worse than zero. Wrong-support optimization raises query error | Source physics only. Three seeds. Bounded search, not a globally optimal code | Confirmation of the locked rule on hash `87b83c41be34aa1a` | **Supported on this source audit.** Encoder inference is still the weak step. Not control, not L2L |
| H-latent-confirm | The locked support-only latent rule lowers held-out query angular-velocity MAE on the reserved confirmation physics versus zero, the global vector, and a cyclic wrong-support vector | Hash `87b83c41be34aa1a`. Task angvel **0.152** vs zero **0.308**, global **0.314**, wrong **0.398**. Paired intervals exclude 0. Positive seeds **3/3**. All four tasks met the 5% point bar. Frozen hashes unchanged. Screen passed | c2 (m=0.35) remains high at **0.335**, only about 10% below zero. Frozen encoder **0.307**, level with zero. Sine paired difference vs global includes 0 | n=3 exploratory. Four physics tuples, not every pendulum. Support-loss drop is not the claim | Can a history encoder be trained to predict this support-fit latent and keep the query gain? | **Supported on this confirmation set.** Not amortized inference, not control, not L2L |
| H-amortized | The existing history encoder, trained to match support-fit teacher latents, lowers held-out query angular-velocity MAE below zero context and below that frozen encoder | Student is slightly below the frozen encoder: paired difference **+0.0026 [0.0015, 0.0037]** | Best development cell, λ 0 / epoch 120 / 128 rows, angvel **0.1747** vs zero **0.1587**. Paired zero−student **−0.0159 [−0.0170, −0.0149]**. All 48 cells lose to zero. Teacher **0.0781**. Recovery **−0.39**. Training latent distance still **1.27** at epoch 400. Gate failed. Hash `d1fa621351d286cf` not collected | Ten student seeds share three decoders. Epoch 400 was worse on the development metric. One decoder's student beat its own zero context; the pre-registered mean did not | Whether this encoder can be driven onto the eight saved teacher codes without reading development queries | **Not supported.** Not control, not L2L |
| H-represent | The existing 584-parameter mean-pooling encoder can reproduce the eight saved meta-training teacher latents on the support that defined them | Rate **0.01**, step 2000: mean latent distance **0.0074, 0.0021, 0.000024**. Worst tasks **0.0089, 0.0026, 0.000030**. Constant baselines **1.31, 1.75, 1.51**. Output spread matches the teachers. Threshold passed on all three decoders | Rate **0.001** misses the bar (decoder 1 mean **0.252**, worst task **0.534**). A second support of the same task has median distance **1.42, 1.43, 0.87** and is usually not prediction-equivalent | Eight pairs on the support that defined the label. Full batch, not a new task. Decision is the final step, not the best checkpoint | Does a student trained at 0.01 on more source tasks lower development query error below zero and the frozen encoder? | **Supported as a training-set fit.** Not generalization, not control, not L2L |
| H-generalize | The existing 584-parameter encoder, trained at learning rate 0.01 on a broader grid of support-specific teacher codes, lowers held-out development angular-velocity error below zero context and below the frozen encoder | Epoch 200: **0.0913** versus zero **0.1587** and the frozen encoder **0.1773**. Paired gaps exclude 0. The teacher remains lower at **0.0781**. Validation mean **0.0832** versus zero **0.0972** and encoder **0.0951** | Training latent distance **0.648**. Held-out history distance **1.752**. Teacher pairs of the same physics have median distance **1.52**. Validation task va3 is worse than zero, and the teacher is too | Five student seeds share three decoders. Checkpoint chosen on development angular velocity only | A separate confirmation on newly registered physics, retraining these seeds. Do not reopen either reserved split | **Supported on the prediction screen.** The encoder did not reproduce the teacher vectors. Not control and not L2L |
| H-gen-confirm | The same encoder, retrained on the twelve source physics, lowers confirmation angular-velocity error at least 0.01 below zero context, the frozen encoder, and the global vector | Epoch 200: **0.1016** versus zero **0.2729**, frozen encoder **0.2660**, and global **0.2742**. Decoder-level gaps **+0.171, +0.164, +0.173**, each interval above 0.01. Teacher **0.0876**, and that interval includes 0 | Latent distance **1.558**. Sine MAE **0.0098** versus zero **0.0080**. All four tasks cleared the three primary controls | Three frozen decoders. Five student seeds are averaged inside each decoder | Ask whether the saved student context improves H=16 MPC return. Do not retune this split | **Supported on the prediction screen.** Not control and not L2L |
| H-control | The epoch-200 student context raises H=16 MPC return by at least 25 points above zero context and the frozen encoder on the four confirmation physics | Student **−683.0** versus zero **−768.4** and the frozen encoder **−773.2**. Paired gaps **+85.4 [−109.4, +280.3]** and **+90.2 [−5.7, +186.1]**. Both intervals include 0 | Decoder 1 is only **+11.0** above zero. High-gravity and heavy-mass returns stay below **−1000**. The 16-step imagined score does not separate the controllers | Three frozen decoders. Five student seeds are averaged inside each decoder | Keep these episode seeds closed. Do not retune the encoder from this return | **Inconclusive.** The point estimate is positive and the interval includes 0 |
| H-control-replication | Across ten independently trained decoders, the same student raises H=16 return by at least 25 above zero and the frozen encoder, on new episodes of the previous physics and on disjoint physics | Replication return **−636.4** versus zero **−708.6** and encoder **−699.2**. Gaps **+72.2 [+45.6, +98.8]** and **+62.8 [+31.3, +94.3]**, both lower bounds above 25 | Fresh physics **−716.0** versus zero **−696.6** and encoder **−705.7**. Zero gap **−19.4 [−35.4, −3.3]** lies below 0. Visited prediction still improved on both sets | Ten decoders. Seeds 0–2 are the old weights on new episodes. Episode SD exceeds decoder SD because tasks are pooled inside the decoder | Do not retune this sample. The return gain did not transfer | **Negative transfer.** Replication passed. The new physics did not. Not L2L |
| H-prediction-control | On the fresh physics, better one-step prediction comes with worse ranking of shared H=16 candidates | One-step angular velocity improves **0.1148 [0.1030, 0.1266]**; open-loop and recorded error improve too | Regret improves **1.313 [0.507, 2.118]** and H=16 score error falls **6.386 [5.450, 7.322]**. The closed episode gap remains **−19.4 [−35.4, −3.3]** | `rp1` and `rp2` regret intervals include 0. Forecast error stays about **12.8**. Open-loop error stays about **1.16** | How a better one-shot score loses a 200-step episode | **Ranking improved.** The planner audit is H-receding. Not a control claim |
| H-receding | On fresh visited states, the one-shot regret advantage reverses, or the matched next-16 continuation reverses it, or live replay fails | Replay **1920/1920**. Selected-score error falls **4.751 [3.023, 6.480]** and reward-forecast error falls **6.539 [4.548, 8.529]**. Step-0 regret is **4.303 [1.276, 7.330]** | Pooled regret **0.812 [−0.038, 1.662]** and next-16 **−0.528 [−1.139, 0.083]** both include 0. Spearman **−0.013 [−0.067, 0.041]**. `rp2` regret favors zero | Task signs differ. Step-0 continuation **−2.221 [−4.622, 0.181]** includes 0. Next-16 is not a 200-step value | Which mechanism produces the closed **−19.4** episode gap | **Inconclusive.** Do not change the architecture or the planner |
| H-return-phase | On new fresh episodes, the student-minus-zero return difference arises in steps 0–15 or in steps 16–199 | Total **−30.671 [−41.540, −19.801]**. Late **−29.441 [−40.706, −18.175]**. Late share **0.928 [0.836, 1.020]** | Early **−1.230 [−2.583, 0.123]** includes 0. `rp1` total includes 0. `rp2` late is **−98.6** and dominates | New seeds, not the closed **−19.4** sample. Observation distance grows to **2.86** by step 199 | Why the paired trajectories separate after step 15 | **Primarily late on this sample.** Not a general control claim |

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
10. Transition-context FiLM on Pendulum prefixes (development gate failed; confirmation physics not evaluated). The Reptile loss in H-V089g is specific to that configuration.

**Normalization reuse (RMS)** transferred vs scratch. That is a statistics-copy, not an improving learner.

## Unresolved scientific questions

1. Can any CartPole WM update improve H=3 MPC return vs frozen with a CI excluding 0 **and** without retuning 0.97?
2. Does the V0.7 residual+H=3 recipe plan at all off CartPole?
3. Is one-step MAE on incumbent actions the wrong proxy for planner-relevant error (multi-step / near-failure)?

## Current late-control hypotheses (later than the historical register above)

H-late-action: on the registered late states, the student-selected first action loses at least one return point under shared zero-context next-16 continuation. **Not established**: +0.0312 [−0.0827,+0.1452], ten decoder units, complete grid. Full-policy next-16 is also inconclusive. This is not equivalence and not a general control result.

H-long-policy: full-policy continuation from identical late states loses at least five points in local steps 16–63. H-long-first-action: the selected first action alone has delayed adverse consequences under common-zero continuation. **Both are untested proposals**, locked in `docs/NEXUS_LONG_CONTINUATION_PROTOCOL.md`; no new data collected, budget not yet approved. A future negative/inconclusive outcome must not trigger automatic architecture expansion.

## H-policy-switch — predeclared bounded diagnostic

After the measured rp2-concentrated longer-continuation loss, compare SS with SZ tail return after identical student-controlled 16-step prefixes. The same frozen controllers, H=16/16 candidates and ten decoder units are retained. SZ-ZZ inheritance and ZS-ZZ suffix-after-zero are secondary. See `docs/NEXUS_POLICY_SWITCH.md`. The one bounded local run is authorized; no performance improvement is claimed from its design or tests.

## Latest bounded diagnostic: paired policy switching

The rp2 prefix/suffix experiment completed with SS-SZ tail **−18.733 [−27.271, −10.195]**, favoring zero-context continuation after identical student prefixes in all ten decoders. SZ-ZZ inheritance **−4.025 [−23.422, +15.373]** and SS-ZZ overall **−22.758 [−45.939, +0.424]** remain inconclusive. This isolates a continuation-policy disadvantage on the registered states; it does not establish a general switching controller or explain the whole historical episode loss. All checkpoints remain frozen. Details: `docs/NEXUS_POLICY_SWITCH.md`, artifact `artifacts/policy_switch.json`. No general control improvement, learning-to-learn or AGI claim follows.


## Latest source planning-value diagnostic

The frozen-model diagnostic completed all planned data in 238.48 s. An initial support-hash format validation bug was corrected offline without resimulation; the unchanged failed capture and separate complete validation record are both retained. Exact simulator H=16 selection still lost **34.685 [22.677, 46.694]** points to the best64 candidate under a shared zero-policy continuation. The source development screen passed. Student-minus-zero selected64 return **+1.507 [−2.870, +5.885]** is inconclusive. This supports short-objective truncation under a full-block intervention, not a causal explanation of the historical negative transfer or a controller improvement. Source suite: eight known physics, one fresh state each, ten decoder units; all weights fixed and 120 files verified. Costs: 64,512 environment steps, 15,851,520 imagined states. Final tests: 480 passed, plus explicit checkpoint audit. See `docs/NEXUS_PLANNING_VALUE.md`; primary summaries are in `artifacts/planning_value_validation.json`, tied to the unchanged raw capture. Prior pending entries below/above are chronological, not the current run status.


## Terminal-value pilot prepared — no experimental results

The next source-only score-correction experiment is implemented on `codex/terminal-value-pilot`, from base `03ae187`. It adds a 78-coefficient source-fitted terminal readout per decoder while preserving all existing neural weights, H=16 and sixteen candidates. Readout source fitting and development collection are separated by a saved, validated manifest. Primary outcome is corrected-student minus unchanged-student same-state common64 first-action return; ten independent decoders, one-point practical margin and a positive lower95% bound. Strong zero-context and corrected-zero comparisons remain explicit.

Readiness: 35 focused tests and 515 full-suite tests passed; the separate local audit verified120 binary files. The default runner performs preparation only; direct execution without exact budget/config approval fails before collection. **No registered source fitting or evaluation has run.** Proposed cap:600 seconds,28,800 real steps and7,050,240 imagined transitions; estimated2–4 minutes. See `docs/NEXUS_TERMINAL_VALUE_PROTOCOL.md` and `artifacts/terminal_value_preparation.json`. Existing measured findings remain unchanged. This prepared implementation is not evidence of a control gain.


## Completed terminal-value correction pilot

The single approved run completed in109.68 seconds, all28,800 real steps and7,050,240 imagined transitions. The primary corrected-student minus unchanged-student common64 first-action difference is **−0.221 [−5.881,+5.438]**, n10 decoder units. The one-point improvement screen did not pass; label `local_first_action_inconclusive`. Corrected student versus unchanged zero is **−1.655 [−6.798,+3.489]**; corrected zero versus unchanged zero **−1.540 [−6.582,+3.502]**; all secondary intervals include zero.

The correction changed154/300 student first actions. Source-fit RMSE improved versus a training-mean constant, but held-out terminal-value accuracy was not measured by these first-action counterfactuals. All110 six-model groups preserved weights/context/normalization;120 checkpoint files verified before/after and independently afterward. Full suite516 passed; no further training, repeat experiment or confirmation/control sweep. The earlier pending-approval entries are preparation history, superseded by this completed result. See `docs/NEXUS_TERMINAL_VALUE_RESULTS.md`. One next proposal: frozen readout calibration on new states using actual versus imagined endpoints, before changing capacity.


## Frozen terminal-value calibration — registered, not executed

H-readout: fixed source-fitted terminal readouts lack held-out state calibration. H-endpoint: imagined endpoint error changes their calibration. These competing explanations may coexist. The locked primary screen instead tests the positive alternative: student-context imagined-endpoint RMSE beats the fixed source mean by at least10%, with paired95% benefit lower bound>0 across ten decoder units. Actual-versus-imagined errors and source results are secondary exploratory diagnostics. One state per known physics, four candidate labels per state; these are not independent decoder replications. No new outcomes exist and the earlier inconclusive control result is unchanged. Protocol: `NEXUS_TERMINAL_VALUE_CALIBRATION_PROTOCOL.md`. Execution awaits separate exact-budget approval; no controller change, learning-to-learn or control-success claim.


## Completed frozen terminal-value calibration

All registered data completed in83.48 seconds:21,824 real steps and5,448,960 imagined transitions; no support collection, fitting or model updates. Student imagined-endpoint development RMSE85.437 versus source-mean128.324 gives **+42.887 [34.451,51.323]** paired error reduction,33.42%; the registered10% screen passed. Actual endpoints did not improve error reliably: imagined-minus-actual **−2.649 [−7.169,+1.871]**. Source reduction was7.81%, a secondary result. This is value calibration versus a constant, not control improvement or evidence of accurate within-state ranking. Earlier control findings remain closed.

The original full raw capture retained its final exact-sum validation failure (maximum Python/NumPy difference1.7e−13). A separate complete offline validation and independent arithmetic audit recover the grid without any replay. Original capture SHA419a07b95881aaeae1a61c57e194acd75d37a73031e23990a4ca315ca7245d4d; execution40bc1e3; validator204b463. All120 checkpoint files and110 groups preserved. Focused35 passed; full **551 passed,1 deselected** in126.35s; standalone120-file verification passed. See `NEXUS_TERMINAL_VALUE_CALIBRATION_RESULTS.md` and `artifacts/terminal_value_calibration_validation.json`. Earlier pending statuses are retained preparation history. The two-hour session's wall-clock window elapsed during a later pause; no additional simulation was started afterward. Next: a separately registered exploratory within-state analysis using only recorded data.


## Completed recorded-data candidate discrimination

The frozen scoring replay completed in8.01 seconds, **zero new environment steps**,337,920 imagined transitions, all110 cells and all120 checkpoint checks. On the same four labeled candidates, committing the complete16-action sequence plus zero48 continuation improved chosen64 return by **+24.030 [1.279,46.781]** on development, n10 decoder units; source +6.951 [2.576,11.325]. This is explicitly exploratory reanalysis of inspected data, not independent control confirmation or first-action replanning performance. The earlier −0.221 first-action result stays inconclusive and closed.

Development gain is concentrated in dev0 (+71.520); dev1 and dev2 intervals include zero. Centered prediction benefit +106.993 [−42.133,256.119] is inconclusive despite absolute calibration success. Constant correction changed0/660 choices, so its identical contrast and regret reduction are dependent evidence, not corroborating replications. A separately labeled posthoc uniform-in-set reference also favors correction (+16.750 [1.181,32.319]); it is not a preregistered randomized-controller result. All models/readouts/normalizers/contexts remain frozen. Before analysis566 full tests passed; final **567 passed,1 deselected**,132.08s, and51 combined focused tests passed. Independent selected-index arithmetic agrees. See `NEXUS_VALUE_CANDIDATE_DISCRIMINATION_RESULTS.md`; raw analysis SHA4de98e582129067a4d18c9012c5b053fe5d7361fb295370e5b5d6add2da412ed, execution438bacea9fd327c5d56e2ad8128baaa20679d897.

One next experiment is designed, not executed: same-state correction×commitment-length interaction (1 versus16 actions), then common zero continuation to64; ten decoders/five students, unchanged H16/16 candidates, fresh registered states. Proposed59,136 real steps,14,883,840 imagined transitions, estimated4–6 minutes, cap900s. See `NEXUS_COMMITMENT_VALUE_PROPOSAL.md`. No extra simulation was started after the prior two-hour wall-clock window elapsed during an interruption. No general control improvement, learning-to-learn or AGI claim.


## Same-state commitment diagnostic prepared — not executed

The next hypothesis is now a locked executable comparison of correction×commitment length, using identical states,16×16 candidate arrays and action-independent common-zero continuation. Primary gain16-minus-gain1 is averaged inside ten independent decoder units, preserving all previous scores, weights, readouts and normalizers. Complete source reconstruction verified120 files and30 decoder/task context groups, with no new registered environment data. Budget59,136 real steps/14,883,840 imagined transitions, estimated4–6 minutes, hard cap900s. Actual research outcomes remain unknown; readiness/tests are not improvement evidence. See `NEXUS_COMMITMENT_VALUE_PROTOCOL.md` and the preparation record for exact revision, hashes and executed tests. Prior candidate-discrimination/first-action results remain closed and unchanged. Execution awaits new exact-budget approval.
