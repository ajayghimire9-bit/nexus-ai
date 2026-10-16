# Next NEXUS experiment (minimal, falsifiable)

## Current decision — lock an H=3-only CartPole saturation diagnostic; do not collect yet

The harder lookahead screen **4.600 [−7.481, 16.681]** stays closed. Do not retune H=3 and do not run lookahead. The locked next test is an H=3-only saturation diagnostic on unused stricter-corner physics `a69833ab38a34ab4`. Collection is **not** authorized. Report `NEXUS_CARTPOLE_H3_SATURATION_PREP.md`.

## Locked — CartPole H=3 saturation diagnostic, collection unauthorized

Protocol `docs/NEXUS_CARTPOLE_H3_SATURATION_PROTOCOL.md` on `cursor/cartpole-h3-saturation-diagnostic` from `894f5ca`. Config SHA256 `55be38a5d77e76bb38a56c50d92e9522037855e8b500577de55c665af9291421`. Protocol SHA256 `657cf38d25c9d013b733e8ba6ef373845b487f980d19f6b815e3cf4ad96cd157`. Primary: seed-mean of (500 − H=3 return) across six tasks, mean ≥ 25 and lower bound > 0. Budget **300 s**, **42,800** real steps, **1,440,000** imagined. Lookahead withheld. Collection is **not** authorized. Do not treat this heading as a result.

## Current decision — harder CartPole lookahead not established; still near ceiling; do not retune H=3

The authorized harder-physics screen completed: lookahead minus H=3 **4.600 [−7.481, 16.681]**. Label `cartpole_hard_lookahead_not_established`. H=3 was already at 500 on 8/10 seed means. Do not retune H=3 and do not resample the same published box. A later distinct question is an **H=3-only saturation diagnostic** on unused stricter-corner CartPole physics, with lookahead withheld until H=3 is unsaturated. That proposal is not implemented and is not authorized here. Report `NEXUS_CARTPOLE_LOOKAHEAD_HARD_RESULTS.md`.

## Consumed — harder CartPole lookahead versus frozen H=3, one-run remaining 0

Protocol `docs/NEXUS_CARTPOLE_LOOKAHEAD_HARD_PROTOCOL.md` on `cursor/cartpole-lookahead-hard-h3` from `82d8551`. Config SHA256 `0515452c75a45d94d610a21ddea91727c499b00a4aeae3d72f56f322a65f954c`. Protocol SHA256 `c2bb743a003544ee1ef6a310ea4c77633fa6f9b42db428a5cfe4a0b40cb26f6e`. Primary completed: lookahead minus H=3 **4.600 [−7.481, 16.681]**, label `cartpole_hard_lookahead_not_established`. Holdout hash `9a60e48299b738ef`. One-run remaining is 0. Further collection is **not** authorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_HARD_RESULTS.md`.

## Current decision — lock harder unused CartPole lookahead versus H=3; do not collect yet

The ceilinged screen **4.000 [−5.048, 13.048]** stays closed. Do not retune H=3. The locked next test uses the same frozen planner on unused hard physics `9a60e48299b738ef` in the published V0.7.3 off-ceiling region. Collection is **not** authorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_HARD_PREP.md`.

## Locked — harder CartPole lookahead versus frozen H=3, collection unauthorized

Protocol `docs/NEXUS_CARTPOLE_LOOKAHEAD_HARD_PROTOCOL.md` on `cursor/cartpole-lookahead-hard-h3` from `82d8551`. Config SHA256 `0515452c75a45d94d610a21ddea91727c499b00a4aeae3d72f56f322a65f954c`. Protocol SHA256 `c2bb743a003544ee1ef6a310ea4c77633fa6f9b42db428a5cfe4a0b40cb26f6e`. Primary: lookahead minus H=3 return, ten training seeds, mean ≥ 25 and lower bound > 0. Budget **300 s**, **42,800** real steps, **2,190,000** imagined. Collection is **not** authorized. Do not treat this heading as a result.

## Current decision — CartPole lookahead not established on a ceilinged draw; do not retune H=3

The authorized development screen completed: lookahead minus H=3 **4.000 [−5.048, 13.048]**. Label `cartpole_lookahead_not_established`. H=3 was already at 500 on 9/10 seeds. Do not copy Pendulum H=16 and do not retune CartPole H=3 from this sample. A later distinct question is lookahead versus H=3 on **harder unused** CartPole physics where H=3 is not saturated. That proposal is not implemented and is not authorized here. Report `NEXUS_CARTPOLE_LOOKAHEAD_RESULTS.md`.

## Consumed — CartPole lookahead versus frozen H=3, one-run remaining 0

Protocol `docs/NEXUS_CARTPOLE_LOOKAHEAD_PROTOCOL.md` on `cursor/cartpole-lookahead-h3` from `9800181`. Config SHA256 `de1113d814ef506eba7e477fc314c48a9d289a497bab018a02cd1acaa6673ece`. Protocol SHA256 `6bbd5caa29fc4156adfb13f72d00466d0d640812b62b7ca4215ddc8e0335c112`. Primary completed: lookahead minus H=3 **4.000 [−5.048, 13.048]**, label `cartpole_lookahead_not_established`. One-run remaining is 0. Further collection is **not** authorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_RESULTS.md`.

## Current decision — lock CartPole lookahead versus frozen H=3; do not collect yet

Pendulum lookahead minus H=16 **98.608 [43.258, 153.957]** stays closed. Do not copy H=16 onto CartPole. The locked next test uses CartPole’s frozen H=3 × 16 planner and the V0.7.2 residual recipe on unused physics `4bc1f5866ac6c753`. Collection is **not** authorized. Report `NEXUS_CARTPOLE_LOOKAHEAD_PREP.md`.

## Locked — CartPole lookahead versus frozen H=3, collection unauthorized

Protocol `docs/NEXUS_CARTPOLE_LOOKAHEAD_PROTOCOL.md` on `cursor/cartpole-lookahead-h3` from `9800181`. Config SHA256 `de1113d814ef506eba7e477fc314c48a9d289a497bab018a02cd1acaa6673ece`. Protocol SHA256 `6bbd5caa29fc4156adfb13f72d00466d0d640812b62b7ca4215ddc8e0335c112`. Primary: lookahead minus H=3 episode return, ten training seeds, mean ≥ 25 and lower bound > 0. Budget **300 s**, **42,800** real steps, **2,190,000** imagined transitions, frozen-recipe training only. Collection is **not** authorized. Do not treat this heading as a result.

## Current decision — Pendulum lookahead transfer is established; do not retune

The authorized holdout screen completed: lookahead minus frozen H=16 **98.608 [43.258, 153.957]**. Label `lookahead_transfer_established`. Student-versus-zero includes 0. Do not retune the lookahead backup, candidates, horizon, or reward from this confirmation sample. The next distinct question is whether the same frozen package beats H=16 on a **different environment family**. That proposal is not implemented and is not authorized here. Report `NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_RESULTS.md`.

## Consumed — lookahead versus H=16 transfer, one-run remaining 0

Protocol `docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PROTOCOL.md` on `cursor/lookahead-transfer-confirmation-prep` from `961e935`. Config SHA256 `385285edca761d60c1759bf8ef951c2682794e7b3d6066e9223aad5236c9cae8`. Protocol SHA256 `5c2e0d7300e497c65c0564990aa2a86ab4d08e79979c40d8ce7d2ea51735c942`. Primary completed: lookahead minus H=16 **98.608 [43.258, 153.957]**, label `lookahead_transfer_established`. Holdout hash `73844661addfa11b`. One-run remaining is 0. Further collection is **not** authorized. Report `NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_RESULTS.md`.

## Current decision — lock transfer of frozen lookahead versus H=16; do not collect yet

Development lookahead minus H=16 **155.647 [109.825, 201.469]** stays closed. Historically exposed confirmation splits are not reused. Reserved amortized confirmation is not consumed. A new holdout from rule `lookahead_transfer_holdout_v1` is locked. Collection is **not** authorized. Report `NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PREP.md`.

## Locked — lookahead versus H=16 transfer, collection unauthorized

Protocol `docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PROTOCOL.md` on `cursor/lookahead-transfer-confirmation-prep` from `961e935`. Config SHA256 `385285edca761d60c1759bf8ef951c2682794e7b3d6066e9223aad5236c9cae8`. Protocol SHA256 `5c2e0d7300e497c65c0564990aa2a86ab4d08e79979c40d8ce7d2ea51735c942`. Primary: lookahead minus H=16 200-step holdout return, mean ≥ 25 and decoder-level lower bound > 0. Holdout hash `73844661addfa11b`. Budget **180 s**, **27,840** real steps, **12,324,000** imagined transitions, **0** optimizer updates. Collection is **not** authorized. Do not treat this heading as a result.

## Current decision — parameter-free H=16 lookahead beat frozen H=16 on development

The authorized development screen completed: lookahead minus frozen H=16 **155.647 [109.825, 201.469]**. Label `bellman_backup_improves_episode_return`. Successor value remained open-loop H=16 from s'. Do not retune candidates, horizon, or reward weights on this sample. Transfer of that frozen rule is now implemented and remains unauthorized. Report `NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md`.

## Consumed — one-step lookahead versus frozen H=16, one-run remaining 0

Protocol `docs/NEXUS_BELLMAN_BACKUP_CONTROL_PROTOCOL.md` on `cursor/receding-long-term-value-audit` from `580dfb0`. Config SHA256 `1a50c953ceb5a20daf3c4e876adc6a8eb855cb5f4ecd1f7d7dffece4fcad625e`. Protocol SHA256 `6025b926475035677bcb4b7056ef7e0729275be169235f5b94bf956583c4e357`. Primary completed: lookahead minus frozen H=16 **155.647 [109.825, 201.469]**, label `bellman_backup_improves_episode_return`. One-run remaining is 0. Further collection is **not** authorized. Report `NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md`.

## Current decision — nested H=8 hurt complete-episode return

The authorized development screen completed: H=8 minus archived H=16 **−174.178 [−265.830, −82.527]**. Label `shorter_horizon_hurts_episode_return`. Do not shorten the horizon further and do not train a ranking loss from this sample. A later distinct question should address long-term decision value under receding control rather than another MPC-horizon sweep. That proposal is not implemented and is not authorized here. Report `NEXUS_HORIZON_OBJECTIVE_CONTROL_RESULTS.md`.

## Locked — nested H=8 versus archived H=16, collection unauthorized

Protocol `docs/NEXUS_HORIZON_OBJECTIVE_CONTROL_PROTOCOL.md` on `cursor/multistep-rollout-control-audit` from `a9ada15`. Config SHA256 `fc862b46b9ab1163e894acf4a57693282db8d0a20f9f4f35220e0f8f65999b56`. Primary: H=8 receding minus archived H=16 200-step return on the same development resets, mean ≥ 25 and decoder-level lower bound > 0. Shared `candidate_sequences(seed,16,16)[:, :8]`. Budget **90 s**, **12,000** real steps, **1,536,000** imagined transitions. Collection is **not** authorized. Audit: `docs/NEXUS_MULTISTEP_ROLLOUT_CONTROL_AUDIT.md`. Do not treat this heading as a result.

## Current decision — late executed-error growth not established

The authorized development screen completed: student-minus-zero late-versus-early executed one-step angvel growth **+0.016 [+0.003, +0.029]**. Label `late_error_growth_not_established`. Mean below 0.05. 200-step return includes 0. Controllers typically diverged by step 10. Do not train a ranking loss from this sample. A later distinct question would address receding search or compounding state shift after early mismatch. That proposal is not implemented and is not authorized here. Report `NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_RESULTS.md`.

## Locked — late-episode decision trajectory, collection unauthorized

Protocol `docs/NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_PROTOCOL.md` on `cursor/late-episode-decision-trajectory` from `e2da92c`. Primary: (student late−early executed one-step angvel MAE) minus the same quantity for zero context, mean ≥ 0.05 and decoder-level lower bound > 0. No three-action forks. Budget **90 s total process**, **12,000** real steps, **3,084,000** imagined transitions. Collection is **not** authorized. The exhausted 3600 s ledger remaining 47.766 s is below this cap and is not reused. Audit: `docs/NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_AUDIT.md`. Do not treat this heading as a result.

## Current decision — prefer episode-level control diagnosis; do not run the 90 s ranking screen

A source-only comparison of the locked development ranking diagnostic (Direction A) versus 200-step control failure (Direction B) recommends **B**. Recorded return-phase windows put the pooled loss after step 64. Do not execute the 90 s / 19,680 / 3,164,160 ranking collection. That protocol stays locked and unauthorized. No new simulation is authorized by this assessment. Report `NEXUS_NEXT_DIRECTION_ASSESSMENT.md`.

## Current decision — decision-aware training is not justified from the source audit

Source-only recomputation did not establish concentrated student H=16 score error on near-best candidates: **+0.577 [−0.233, +1.387]**. 16-step ranking is already strong. Closed ranking-versus-episode evidence already showed better one-shot ranking without general control. Do not train an action-ranking or value-aware world-model loss from this inventory. Report `NEXUS_DECISION_AWARE_WORLD_MODEL_AUDIT.md`.

## Locked — development near-best score-error diagnostic, collection unauthorized

Protocol `docs/NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL.md` on `cursor/decision-aware-world-model-diagnostic` from `9cf3d19`. Primary: student near-best minus dominated H=16 absolute score error on three development physics, mean ≥ 1 and decoder-level lower bound > 0. 200-step return is a separate secondary. Budget **90 s total process**, **19,680** real steps, **3,164,160** imagined transitions, 30 decoder×task states. Collection is **not** authorized. The exhausted 3600 s ledger remaining 47.766 s is below this cap and is not reused. Audit: `docs/NEXUS_DECISION_AWARE_WORLD_MODEL_AUDIT.md`. Do not treat this heading as a result.

## Current decision — remaining-horizon alignment is boundary-specific

The authorized development screen completed: 200-step remaining-horizon minus H=16 **+0.523 [−0.077, +1.123]**. Label `boundary_specific_alignment`. Close general remaining-horizon alignment as a controller change. A later distinct question would address candidate quality, model bias, or receding search itself—not further shortening of H on these episodes. That proposal is not implemented and is not authorized here. Report `NEXUS_HORIZON_ALIGNMENT_RESULTS.md`.

## Locked — remaining-horizon versus fixed H=16, collection unauthorized

Protocol `docs/NEXUS_HORIZON_ALIGNMENT_PROTOCOL.md` on `cursor/horizon-alignment-diagnostic` from `aa3a5fb`. Primary: remaining-horizon MPC minus fixed H=16 on 200-step development episodes, mean ≥ 25 and decoder-level lower bound > 0. The 16-step window is a diagnostic cutoff. Budget **180 s total process**, **25,920** real steps, **6,405,120** imagined transitions, 10×3×2 cells. Collection is **not** authorized. Audit: `docs/NEXUS_HORIZON_ALIGNMENT_AUDIT.md`. Do not treat this heading as a result.

## Current decision — same-set versus equal-horizon fresh not established

The authorized development screen completed: same-set minus equal-horizon fresh **+0.834 [−0.955, +2.623]**. Label `same_set_advantage_not_established`. Do not retune that contrast. A distinct later question is whether remaining-horizon receding beats production H=16 because the deployed controller plans past the 16-step evaluation window. That proposal is not implemented and is not authorized here. Report `NEXUS_SAME_SET_PLANNING_RESULTS.md`.

## Locked — equal-horizon same-set versus fresh replanning, collection unauthorized

Protocol `docs/NEXUS_SAME_SET_PLANNING_PROTOCOL.md` on `cursor/same-set-planning-audit` from `16d904c`. Primary: same-set suffix receding minus equal remaining-horizon fresh draws on three development physics, mean ≥ 1 and decoder-level lower bound > 0. Production H=16 receding from `s0` is an unequal-budget baseline, not the primary. Budget **60 s total process**, **2,880** real steps, **506,880** imagined transitions. Collection is **not** authorized. Audit: `docs/NEXUS_SAME_SET_PLANNING_AUDIT.md`. Do not treat this heading as a result.

## Current decision — receding policy consistency not established

The authorized source screen completed: commit-16 minus recede-fresh **−1.787 [−4.324, +0.751]**. Label `replan_consistency_not_established`. Same-set suffix receding beat both open-loop commitment and fresh-candidate receding, but only as a locked secondary. A new protocol would need to make remaining-suffix receding versus deployed recede-fresh the primary on a held-out split, with a fresh budget, without reopening confirmation physics or score-correction. That proposal is not implemented and is not authorized here. Report `NEXUS_RECEDING_POLICY_CONSISTENCY_RESULTS.md`.

## Locked — receding policy consistency, collection unauthorized

Protocol `docs/NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL.md` on `cursor/receding-policy-consistency` from `0aed2e3`. Score-correction stays closed. Primary screen: commit-16 minus recede-fresh 16-step return on eight source physics, mean ≥ 1 and decoder-level lower bound > 0. Strong baseline is executing the already selected H=16 sequence. Search-noise first-action disagreement at the same state is not a return result. Budget **120 s**, **8,960** real steps, **1,515,520** imagined transitions. Collection is **not** authorized. Feasibility: `docs/NEXUS_RECEDING_POLICY_CONSISTENCY_FEASIBILITY.md`. Do not treat this heading as a result.

## Current decision — close terminal-value score-correction

The resumed action-conditioned first-action screen is complete and did not pass: conditioned−H=16 **−4.293 [−15.751, +7.165]**. Additive and sequence-value secondaries also include 0. The locked original protocol says to close this score-correction branch rather than add layers, polynomials, or action×context terms. Next work should address receding-horizon policy consistency, action selection and online adaptation under a **new** protocol. That proposal is not implemented and is not authorized here. Report `NEXUS_ACTION_CONDITIONED_Q_RESUME_RESULTS.md`.

## Proposed — fail-closed resume of the missing action-conditioned Q cell, collection unauthorized

The incomplete 59/60 capture is frozen (`artifacts/action_conditioned_q.json` SHA `6f80696ca7cb94d0789ef950c90cf34aa425aab20b4fc9d776c4397201322680`). Offline reconstruction: 160 source cells and ten Q fits rebuild; 59 evaluation cells have complete raw traces and rebuild metrics. The missing cell is decoder 9 / development task 2 / zero visitor, independently seeded from the original lock. Resume writes a **separate** completed artifact and refuses to alter the original files or retune on the 59 outcomes.

Smallest safe completion: **60 s**, **242** real steps, **64,512** imagined transitions, one cell only. If that cell fails fingerprint/replay/metric reconstruction, abort and rerun the full 240 s / 45,240 / 11,612,160 grid. Collection is **not** authorized (`authorized: false`). Protocol `docs/NEXUS_ACTION_CONDITIONED_Q_RESUME_PROTOCOL.md`. Do not treat this heading as a result.

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
