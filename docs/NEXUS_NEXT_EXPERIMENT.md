# Next NEXUS experiment (minimal, falsifiable)

## Incomplete — action-conditioned first-action Q, one-run consumed

The authorized 240 s run timed out with **59/60** evaluation cells (missing decoder 9, task 2, zero visitor). Label `incomplete`. No registered decoder-level interval. Source fit completed. The runner refuses overwrite; the one-run allocation remaining is 0. Completing the screen needs a **new** explicit approval with a higher cap (propose 360 s) and overwrite or new artifact paths. Do not treat the 59 cells as a decision. Report `NEXUS_ACTION_CONDITIONED_Q_RESULTS.md`.

## Locked — action-conditioned first-action Q, collection unauthorized

Protocol `docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md` on `cursor/action-conditioned-first-action-q` from `6ecb09c`. The 81-coefficient additive protocol is preserved and was not edited. Source-only CV selected compact `action_obs` (16 weights, λ=0.1): leave-one-task action identification 0.463 versus additive 0.312 (chance). Additive ranking is state-independent on synthetic data; action×observation ranking is not. Proposed collection uses **two distinct source states per task** (48 unique labels/decoder), not repeated contexts. Primary screen: conditioned minus H=16 first-action 64-return, mean ≥ 1 and lower bound > 0. Budget **240 s**, **45,240** real steps, **11,612,160** imagined transitions. Standing-session remainder is 47.766 s, so collection is **not** authorized. Feasibility: `docs/NEXUS_ACTION_CONDITIONED_Q_FEASIBILITY.md`. Do not treat this heading as a result.

## Locked — capacity-matched first-action Q, collection unauthorized

Protocol `docs/NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md` and config `configs/capacity_matched_q.yaml` are committed on `cursor/capacity-matched-first-action-value` from `a833a2c`. Offline feasibility (`docs/NEXUS_CAPACITY_MATCHED_Q_FEASIBILITY.md`) found 24 unique source labels versus 81 coefficients, design rank 50, and state-independent additive action ranking. Ridge λ=1 is prespecified. **No source labels, fits or development returns have been collected for this estimator.**

The primary screen remains aligned-Q minus H=16 first-action 64-return, mean ≥ 1 with decoder-level lower bound > 0. If the complete run does not pass, this score-correction branch closes. Proposed cap 150 s, 29,880 real steps, 7,741,440 imagined transitions. Remaining standing-session allowance is 47.766 s, so collection is **not** authorized. Do not treat this heading as a result.

## Current proposal — capacity-matched first-action Q, then stop if it fails

The linear 15-coefficient aligned Q did not beat H=16 on first-action 64-return: **−3.535 [−9.840, +2.769]**. Source-fit RMSE stayed around 70 and development Q RMSE was 107.5. This is not a strong test of aligned labels at sequence-V capacity, and it is not an architecture warrant. See `NEXUS_FIRST_ACTION_VALUE_RESULTS.md`. The executable protocol and unauthorized allocation now exist; they have not been executed.

## Current proposal — source-only replanning-aligned value labels

The offline alignment screen passed: the best recorded64-return sequence's first action incurs **20.254 [11.382,29.127]** regret under immediate zero-context replanning. All60 states cover all three actions, but this does not rule out limited suffix search or establish a cause of the old full-episode loss. No new controller improvement was demonstrated. See `NEXUS_ACTION_VALUE_ALIGNMENT_RESULTS.md`.

**One next experiment:** fit a separate small source-only value readout to forced-first-action/common-zero return labels, freeze it before fresh visited-state evaluation, and compare selected first-action64 return against the existing H16 and sequence-value scores. Keep original networks/readouts intact. Specify whether features use actual source endpoints versus imagined evaluation endpoints; preserve independent source/target episodes and equal visitor/task aggregation inside ten decoders. Prediction loss alone cannot pass the screen. Finalize the exact feature/architecture/compute and inference-baseline comparisons before fitting.

Preliminary cost29,880 new real steps (15,360 source labels,3,000 visitor collection,11,520 action branches), around7.7million imagined transitions, estimated110–130CPU seconds, proposed hard cap150seconds. The current conservative ledger has174.408seconds left; the final enforced cap must fit the allowance at execution time. This is a proposal, not a locked implementation or authorization to bypass preconditions. No extra training or collection has run. Previous entries below are chronological history.

## Current proposal — offline action-value alignment, no more scalar tuning

The source-only scalar test is complete and failed its selection screen: beta0.823947 improved centered prediction error, but calibrated−base return **−9.228 [−22.358,+3.901]** and calibrated−original **+1.194 [−0.102,+2.489]** remain inconclusive. Stop this scalar branch; do not select a new weight from these closed outcomes. See `NEXUS_SOURCE_SCALAR_RESULTS.md`.

**One next experiment:** preregister an exploratory recorded-data comparison of the first action chosen by the actual best64-step full sequence against the best of the three already measured first-action-plus-common-zero continuations. Include original/calibrated scoring choices as references, equal visitor/task weights inside ten decoder units, typed complete-grid checks and explicit oracle/research-only labels. This tests whether the full-sequence objective itself aligns with the executed first-action intervention before fitting a more complex model. No simulation, neural inference, refitting, architecture change or parameter search. Estimated<30CPU seconds, proposed cap60seconds, zero real/imagined transitions. Lock the exact contrasts and tie rule before calculating results. It is a proposal, not an executed extra experiment. Earlier sections below are chronological history.

## Current proposal — source-only scalar calibration, then fresh visited audit

The offline visited ranking audit is complete: centered MSE benefit **−1,194.516 [−2,025.559,−363.473]** while pair ordering accuracy is55.597% [50.432%,60.763%]. The intersection screen failed. Some ordering survives, but its numerical values are unreliable relative to a constant; this does not prove a scaling-only cause. The earlier visited control effect remains inconclusive. See `NEXUS_VISITED_VALUE_RANKING_RESULTS.md`.

**One next experiment:** fit or select a single external scalar correction weight using source-only calibration data, freeze it before inspecting fresh visited-state outcomes, then compare unchanged correction, scaled correction and no correction on the same candidates/states. Preserve all original decoder/encoder/readout checkpoints; do not fit the scalar on these closed visited results. Use the same ten independent decoders, equal visitor/task weights and paired intervals, with fair source calibration interaction accounting. Register exact scalar procedure, fresh seeds, scientific thresholds and a bounded runtime/interaction budget before execution. This tests whether weak usable ordering can become useful selection after numerical calibration, not whether a larger architecture can fit more data. No new experiment or scalar fitting has run. Earlier pending proposals below are history, superseded by the completed offline analysis.

## Current decision — audit visited-state value ranking offline

The visited-state replication is complete and inconclusive: **−5.999 [−22.293,+10.295]** commitment interaction, gain16 **−7.784 [−22.369,+6.800]**. Neither visitor group establishes a positive interaction. The earlier +39.366 initial-state result remains closed. Do not infer that block commitment improves deployed control and do not build a practical commitment policy yet. See `NEXUS_VISITED_COMMITMENT_RESULTS.md`.

**One next experiment:** register an exploratory offline within-state terminal-value ranking/calibration audit of the saved16 candidates at each visited state. Compare frozen predicted48-step tails with actual recorded48-step common-zero tails, decompose bias/centered candidate error, and measure ranking/selection regret against a constant-tail comparator. Average students, equal visitor groups and tasks inside ten decoder units; label all reanalysis exploratory and preserve the primary inconclusive result. No fitting, MPC replay, new data or architecture changes. Estimated<30CPU seconds, proposed cap120seconds, **zero new real or imagined transitions**. Lock a separate protocol and implementation before calculating those outcomes. It has not run. This can test whether the existing readout's useful discrimination fails at the encountered state distribution before investing in controller changes. Earlier entries below are chronological history, superseded by this completed replication and proposed analysis.

## Current decision — test late-state persistence, not a controller change

The initial-state commitment interaction is now complete: **+39.366 [26.247,52.484]**, with positive full-sequence correction gain and inconclusive first-action gain. See `NEXUS_COMMITMENT_VALUE_RESULTS.md`. The registered screen passed, but corrected sequence commitment still returned less on average than original one-action control. Do not deploy a commitment change from these results.

The single next experiment should replicate the same frozen correction×commitment interaction at **late visited states**, weighting student-visitor and zero-visitor states equally within each of ten decoders. Keep the five scoring student seeds, all weights/readouts, H16/16 candidates and zero-context continuation unchanged. This directly tests state-distribution sensitivity rather than adding capacity or fitting on closed outcomes.

Proposed minimal allocation: one phase-50 state per visitor/controller, decoder and each of the same three development tasks. A deterministic balanced student-visitor seed assignment must be preregistered, not selected by return; all five students still score every state. Sixty distinct decoder-specific states require15,360 prefix steps,46,080 block-tail steps,11,520 first-action steps, plus3,000 collection steps = **75,960 new real interactions**. Estimate5–7 CPU minutes, hard cap900seconds, no fitting. Finalize fresh seed sets, exact imagined counts, complete-grid tests and protocol before collecting anything. This is a proposal, not an executed or already finalized protocol. No further experiment launched this cycle. Earlier readiness/approval entries are preserved historical records.

## Current readiness — same-state commitment interaction implemented

The commitment-length experiment is now implemented and tested on `codex/commitment-value-diagnostic`, from clean GitHub-matched c458803d820902e4d1eeb3c3208db1ce40fb50f7. Locked executable config and finalized protocol: `configs/commitment_value.yaml` and `docs/NEXUS_COMMITMENT_VALUE_PROTOCOL.md`. There are **no new registered outcomes**. The code enforces zero-context continuation in both arms, identical candidates/future RNG, cached interaction accounting, complete-grid validation and fresh exact-budget approval before environment access. Earlier proposal and results below are preserved history.

The one next run tests the paired gain16-minus-gain1 interaction, one-point practical margin and positive decoder-level95% lower bound, with a separate positive full16 interval required for a benefit label. Proposed4–6 minutes, cap900 seconds,59,136 real steps and14,883,840 imagined transitions. No new support/model/readout training; all120 checkpoint files and30 saved context groups have verified in read-only mode. The former two-hour authorization is expired; this implementation does not self-approve a new simulation.

## Current next experiment — same-state commitment interaction

The calibration screen passed, and a subsequent recorded-data analysis found terminal-corrected complete-sequence selection +24.030 [1.279,46.781] on the four labeled development candidates. This is retrospective and task-concentrated. It does not overturn the earlier inconclusive first-action test on a different sample.

The one next design is `docs/NEXUS_COMMITMENT_VALUE_PROPOSAL.md`: a paired2×2 correction×commitment-length test at identical fresh states/candidates. Measure the interaction between correction gains when committing1 versus16 actions, followed by the same zero-policy future to64. Keep all weights, readouts, H16 and16 candidates fixed. Evaluate all16 candidates' real full-block tails to remove the retrospective subset limitation. Estimated4–6 minutes local CPU, hard cap900s; exact proposed59,136 real steps and14,883,840 imagined transitions. This new simulation has not run and is not authorized by the expired earlier wall-clock allocation. Existing closed splits/results remain unchanged; prepare a separate branch/config/tests and current allocation before collection. Prior recommendations below are preserved history.

## Current next question — candidate discrimination after calibration

The frozen readout passed held-out development calibration versus a source-mean constant:33.42% RMSE reduction, paired +42.887 [34.451,51.323]. Actual endpoints gave no reliable improvement. These results do not establish candidate discrimination; a constant predictor cannot rank actions. The earlier first-action return test remains inconclusive.

Next prepare one exploratory analysis of the saved calibration trajectories: distinguish task/state mean error from within-state candidate error, and compare unchanged versus terminal-corrected in-set64-step sequence selection on the four already labeled candidates. Use only existing data, frozen models and exact original score logic, with zero new environment interactions and a small inference cap. Commit its analysis protocol before calculating these new contrasts. It is a diagnostic on an already inspected sample, not independent confirmation or a new control-success claim. Everything below is preserved history.

## Current preparation — frozen terminal-value calibration

The proposed calibration experiment now has an executable locked configuration, runner, tests and protocol: `docs/NEXUS_TERMINAL_VALUE_CALIBRATION_PROTOCOL.md`, on `codex/terminal-value-calibration`. This is implementation readiness, **not new evidence**. It has collected no registered data and has not fitted or changed any model/readout. Original proposal and historical pending statuses below are preserved; their requirement for a separately locked configuration is now satisfied, while new exact-budget approval remains pending.

The primary test is frozen student imagined-endpoint RMSE versus the existing source-label-mean reference on three development tasks, with at least10% reduction and a positive decoder-level95% lower bound. Actual-endpoint calibration is a paired research-only secondary diagnostic, not an oracle. Same saved contexts, ten decoders, one new state per eight source/three development physics; zero new support steps. Proposed one-run budget21,824 real steps,5,448,960 imagined transitions, estimated2–3 minutes local CPU, hard cap600 seconds. No further experiment is automatically authorized. Config SHA256: `0fea17504d5a5baea32d857947cd516ab14cef84df524d7f835594d71d7d6184`.

## Current next question — after the inconclusive terminal-value pilot

Do the **frozen** terminal-value readouts predict held-out continuation returns, and does using imagined rather than actual endpoints explain their error? The completed correction pilot did not demonstrate improved first actions: **−0.221 [−5.881,+5.438]**. It changed154/300 student actions, so the intervention was active; improved source fitting did not establish development decision quality.

The one proposed experiment is in `docs/NEXUS_TERMINAL_VALUE_CALIBRATION_PROPOSAL.md`: retain all fitted weights and recorded contexts; collect fresh states on the eight source/three development physics; compare predicted48-step zero-policy value from actual versus imagined endpoints against a frozen source-mean reference. Proposed cost21,824 real steps,5,448,960 imagined transitions, estimated2–3 minutes, hard cap600 seconds. It needs a separately locked configuration and approval. No additional experiment has started. Do not increase capacity, refit on the just-closed sample or claim control improvement.

Completed report: `docs/NEXUS_TERMINAL_VALUE_RESULTS.md`. Everything below is preserved preparation/history; its pending approval and next-direction wording is superseded by this section.


## Ready for budget approval: terminal-value pilot

The source-only terminal-value comparison is implemented and tested; it has **not** collected registered data or fitted research readouts. Protocol: `docs/NEXUS_TERMINAL_VALUE_PROTOCOL.md`. Clean implementation: `f8a438e`. Preparation record: `artifacts/terminal_value_preparation.json`. All515 regression tests passed, plus the explicit120-file checkpoint audit.

Request one fixed development run: estimated2–4 minutes, hard cap600 seconds,28,800 environment steps and7,050,240 imagined transitions. Exact executable config SHA256: `b426beef6da918c94c300fe8935b97c8b1640dadd03f1f9cedc17f3f8bd5b094`. The underlying entry point rejects absent or stale budget approval before any collector call. Do not self-supply approval.

The single question is whether the source-trained terminal correction improves the student’s same-state first-action choice under common-zero continuation. Primary margin1point with positive decoder-level95% lower bound; no general-control or learning-to-learn claim. Approval of this new training/evaluation scope remains pending. Following recommendations and costs are preserved history.


## Current next scientific question — after source planning-value diagnostic

Can a small source-trained terminal-value correction improve same-state first-action decisions while keeping the encoder, decoder, H=16 and sixteen candidates fixed? The completed diagnostic found exact16 selection regret **34.685 [22.677, 46.694]** over a 64-step intervention, while student-minus-zero chosen64 return remained **+1.507 [−2.870, +5.885]**, inconclusive. Accurate short reward ranking alone is insufficient on this finite source suite.

Propose one bounded comparison: train the terminal-value estimator only on newly collected source episodes; lock it before testing on disjoint development states against unchanged MPC, using paired common continuation and decoder-level uncertainty. Do not fit to the closed diagnostic or reuse its seeds as independent evidence. Suggested ceiling: 600 seconds and 65,000 total real steps, with exact training/evaluation allocations and minimum effect registered before collecting data. No further experiment has run. This is a candidate score correction to test, not an established controller improvement.

The latest completed report is `docs/NEXUS_PLANNING_VALUE.md`. All following recommendations and pending-status wording are preserved historical entries, superseded by this section.


Not AGI. Do not retune MAE 0.97. Do not start finance, NAS, Reptile, MAML, or a meta-controller. The direct-latent confirmation protocol is closed; do not retune its learning rate or update count.

## Current evidence and one next direction

The approved 64-step diagnostic completed (full-policy tail −8.661 [−14.513, −2.809], concentrated in rp2). The subsequent bounded policy-switch experiment isolates continuation choice after identical student prefixes: SS-SZ **−18.733 [−27.271, −10.195]**. Inheritance and overall SS-ZZ remain inconclusive. Both are development diagnostics, not general control confirmation.

The single next direction is a separately preregistered source-only planning-value diagnostic on fresh development physics. Test whether action-sequence scores predict longer-horizon continuation values before changing encoder capacity or training a new controller. No new experiment is launched from this recommendation. Do not deploy a hard-coded rp2 or step-16 switching rule. The sections below are historical registrations and findings; their old pending statuses are not current authorizations.

## Historical 64-step proposal — subsequently completed

The latest completed late-state diagnostic remains inconclusive: common-zero +0.0312 [−0.0827,+0.1452], full-policy −0.0234 [−0.2236,+0.1767]. The single next proposal is the 64-step same-state study in `docs/NEXUS_LONG_CONTINUATION_PROTOCOL.md`, preserving all trained controllers and H=16/16 candidates. Its primary contrast is the full-policy student-minus-zero tail over local steps 16–63, averaged inside ten decoder units. Common-zero continuation is secondary.

Proposed cost: 198,832 environment steps, 50,851,840 imagined states; roughly 14 minutes local runtime, hard cap 1800 seconds. **Do not run until the user approves this exact budget and configuration.** No new experiment has been executed. Current preparation supplies an offline audit, configuration, tested rollout primitive and explicit remaining integration checks. The prior recommendations below are chronological history, superseded by this approved direction for design work only.

## Closed on measured runs

Pendulum H=16 planning beat random on its confirmation physics (`docs/NEXUS_PLANNING_GENERALITY.md`). MAE-gated adaptation did not (`docs/NEXUS_PENDULUM_TRANSFER.md`). Reptile lost to matched-data multitask in that configuration (`docs/NEXUS_META_LEARNING_PILOT.md`). That Reptile result is not a general disproof.

The context-adaptation development screen failed (`docs/NEXUS_CONTEXT_ADAPTATION_PILOT.md`). Real-context primary AUC **−755** versus fine-tune **−454**, versus zero context **−652**, versus wrong-task context **−725**. Confirmation physics hash `87b83c41be34aa1a` was not evaluated in that pilot.

## Why earlier runs stayed off confirmation

The (48, 48) context trunk (4332 parameters) was already far behind the (64, 64) MLP (4868 parameters) at budget zero. Real and wrong-task encoder vectors were close (`‖z_real − z_wrong‖` about 0.10–0.72). Using the prefix made control worse than a constant zero context. Those encoder runs did not earn a confirmation. The direct-latent source screen is a different result and is what the next experiment tests.

## Diagnosis that replaced the trunk-widening plan

The development diagnosis (`docs/NEXUS_CONTEXT_ADAPTATION_DIAGNOSIS.md`) kept the (48, 48) trunk. Fixed-length real context did not beat zero context on held-out source MAE (0.0703 vs 0.0700 at budget 128) and raised development MAE from 0.0774 to about 0.084, mostly in angular velocity. Open-loop horizon-16 error moved the same way. Variable-length training had a positive short-budget point estimate and a seed-level AUC interval that includes 0. Zero-context control stayed about 146 points below the frozen MLP. The final-epoch MLP matched the selected checkpoint, so that asymmetry is not the gap.

## Optimization diagnostic

More updates improved the shared dynamics and did not make real context useful (`docs/NEXUS_CONTEXT_OPTIMIZATION_DIAGNOSTIC.md`). At 3000 updates the source audit still had real angular-velocity MAE **0.1264** versus zero **0.1256** and wrong **0.1234**. The 5% screen failed. Do not continue to 10,000 updates.

## Frozen-dynamics diagnostic

Freezing that 3000-update trunk and training the encoder and FiLM did not make real context useful (`docs/NEXUS_FROZEN_DYNAMICS_CONTEXT.md`). On a fresh source audit, selected real-context angular velocity was **0.1484** versus zero **0.1159**, wrong **0.1207**, and a trained constant vector **0.1127**. The screen failed. The paired constant-minus-MLP difference on that same artifact is **−0.00228 [−0.0137, +0.0092]** and includes 0. Overlap of the two separate intervals is not that test. Do not add more encoder updates.

## Direct latent diagnostic

Optimizing `z` alone, with the history decoder frozen, passed the source screen (`docs/NEXUS_DIRECT_LATENT_CONTEXT.md`). The locked rule is Adam learning rate **0.1** for **256** updates from the global vector. Fresh-audit angular velocity was **0.0628** versus zero **0.1151**, global **0.1109**, and wrong-support **0.1762**. Paired intervals exclude 0. The frozen encoder on the same 128 rows stayed worse than zero context (**0.1256**). Cos and sin paired differences versus the global vector include 0.

## Direct latent confirmation

The locked rule passed on the reserved physics (`docs/NEXUS_DIRECT_LATENT_CONFIRMATION.md`). Confirmation angular velocity was **0.152** versus zero **0.308**, global **0.314**, and wrong-support **0.398**. Paired intervals exclude 0. The frozen encoder on the same support rows stayed at **0.307**, level with zero context. Low-mass task c2 remained the high-error case at **0.335**.

## Amortized latent inference

The development gate failed (`docs/NEXUS_AMORTIZED_LATENT_INFERENCE.md`). The selected student, distillation only at epoch 120 with 128 support rows, had angular velocity **0.1747** versus zero **0.1587** and the frozen encoder **0.1773**. The teacher on the same decoder was **0.0781**. Every λ, epoch, and budget cell lost to zero context. Epoch 400 was worse than epoch 120. Confirmation physics hash `d1fa621351d286cf` was not collected. Do not add epochs. Do not run MPC.

## Encoder representability

The existing encoder can reproduce the eight saved codes (`docs/NEXUS_ENCODER_REPRESENTABILITY.md`). At Adam learning rate **0.01** for 2000 full-batch steps, mean latent distance was **0.0074, 0.0021, and 0.000024** against constant baselines of **1.31, 1.75, and 1.51**. Rate 0.001 did not pass. A second support of the same task does not reproduce the saved vector (median distance **1.42, 1.43, 0.87**) and usually changes the support loss. That fit is not generalization and not control.

## Latent encoder generalization

The development screen passed (`docs/NEXUS_LATENT_GENERALIZATION.md`). Epoch 200 angular velocity was **0.0913** versus zero **0.1587**, the frozen encoder **0.1773**, the global vector **0.1478**, and the direct teacher **0.0781**. The eight-task baseline at the same epoch was **0.1672**. The validation mean also passed, at **0.0832** versus zero **0.0972**. Training latent distance stayed **0.648**, and a new support of a training physics stayed at **1.752**. Validation task `pendulum_lat_va3` is worse than zero context, and its teacher is too. Neither reserved confirmation hash was collected.

## Latent generalization confirmation

The prediction screen passed (`docs/NEXUS_LATENT_GENERALIZATION_CONFIRMATION.md`). Confirmation angular velocity was **0.1016** versus zero **0.2729**, the frozen encoder **0.2660**, and the global vector **0.2742**. The decoder-level gaps clear the 0.01 margin and exclude 0. The direct teacher was **0.0876**, and that paired interval includes 0. Latent distance stayed **1.558**. All four tasks cleared the three primary controls. No control sweep was run.

## Latent context control

The H=16 comparison is inconclusive (`docs/NEXUS_LATENT_CONTROL.md`). Student return was **−683.0** versus zero **−768.4** and the frozen encoder **−773.2**. The decoder-level intervals are **+85.4 [−109.4, +280.3]** and **+90.2 [−5.7, +186.1]**. Both include 0. The teacher return was **−682.4**. These episode seeds stay closed.

## The one next experiment

**Do not rerun these control episodes and do not change the encoder.**

The ten-decoder replication passed on new episodes of the previous physics and failed on the disjoint physics (`docs/NEXUS_CONTROL_REPLICATION.md`). Fresh student-minus-zero is **−19.4 [−35.4, −3.3]**. Visited prediction still improved there. Do not retune this sample.

The same-state diagnostic (`docs/NEXUS_PREDICTION_CONTROL_GAP.md`) then found that the student also ranks shared H=16 candidates better and forecasts their return more closely than zero context, on both physics sets. Fresh regret improved by **1.313 [0.507, 2.118]** and the H=16 score error fell by **6.386 [5.450, 7.322]**. That does not reverse the closed episode loss.

The receding-horizon audit is closed (`docs/NEXUS_RECEDING_HORIZON_DIAGNOSTIC.md`). On fresh visited states the pooled regret gap is **0.812 [−0.038, 1.662]** and the matched next-16 gap is **−0.528 [−1.139, 0.083]**. Both include 0. Live replay matched **1920/1920** stored decisions. The registered branches were not separated. Do not change the encoder, the decoder, the horizon, or the candidate count on this sample. Do not open a long-horizon policy-value study from this result: the local diagnostics did not all favor the student. The closed fresh episode gap stays an input. That is not learning-to-learn.

The return-phase decomposition is closed (`docs/NEXUS_RETURN_PHASE_DECOMPOSITION.md`). On new fresh episodes the student-minus-zero total is **−30.671 [−41.540, −19.801]**. Steps 0–15 include 0. Steps 16–199 are **−29.441 [−40.706, −18.175]**. Do not change the encoder, the decoder, the horizon, or the candidate count from this split. The late window is where the paired difference accumulates. Trajectory divergence means that window is not a same-state comparison. That is not learning-to-learn.
