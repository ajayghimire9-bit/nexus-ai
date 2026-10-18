# NEXUS full research registry

Status: **documentation only**. Not a scientific result.
HEAD: `869a9e56be8405aa62aa3b5f04c66dc4879da1e9`. Ledger **306.954 / 3293.046**.
H17 remains **blocked**.

Missing commits, protocols, or implementations are marked **incomplete**
instead of guessed. Curated rows are partial unless `coverage` is
`source_verified`. Unindexed protocol/results documents are listed so
they are not silently dropped.

Consult this file, `docs/NEXUS_CANONICAL_CURRENT_STATE.md`, and
`docs/NEXUS_CODE_REUSE_MAP.md` before implementing a new algorithm
or component.

## Coverage

- Curated rows: 38
- Unindexed protocol/results docs: 93
- Total rows: 131
- Incomplete or partial: 120
- Source-verified: 11

## Closed primary labels that must not be retuned

| ID | Label | Kind |
|---|---|---|
| H8 | `mcc_native_rms_not_established` | not_established |
| H9 | `mcc_residual_scale_harm_established` | harm |
| H10 | `mcc_multitask_128_beats_scratch` | supported_one_holdout |
| H11 | `mcc_multitask_128_confirm_not_established` | not_established |
| H12 | `mcc_planning_ranking_multitask_better` | supported |
| H13 | `mcc_planning_ranking_confirm_multitask_better` | supported |
| H14 | `h14_fixed_library_helps_multitask_relative` DiD 0.178 | supported |
| H15 | `h15_fixed_library_helps_multitask_relative` DiD 0.23 | supported |
| H16 | `h16_same_state_library_effect_not_established` D_same 0.023 | not_established |

## Experiments

| ID | Status | Protocol / results | Reuse | Coverage |
|---|---|---|---|---|
| `V0.1` | historical_implemented | — / README.md | Not LEVEL 2 transfer. Do not treat architecture search as learning-to-learn. | partial |
| `V0.4` | historical_measured | — / README.md | Historical PPO evidence only. CartPole ceiling confounds evolution ranking. | partial |
| `H-V05` | synthetic_supported_real_not_established | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Keep as a cheap scheduler. Not a path to learning-to-learn. | partial |
| `H-V06` | not_established | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Closed in V0.6.6. Do not retune the unsolved 8k PPO setup. | partial |
| `H-V064` | confounded_then_hurt_after_rms_control | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Do not claim representation learning until RMS is controlled. | partial |
| `H-V066` | supported_as_statistics_copy | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Statistics copy, not an improving learner. | partial |
| `H-V07` | supported_on_cartpole | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | The only reliably positive WM planning result, and only on CartPole. | partial |
| `H-V08` | mae_improved_control_not_established | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Stop treating one-step MAE as the objective. | partial |
| `H-V089` | falsified_under_frozen_protocol | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Closed. Not learning-to-learn. | partial |
| `H-V089g` | reptile_worse_in_that_configuration | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Not a general disproof of Reptile. Not learning-to-learn. | partial |
| `H1` | supported_as_mechanism_class | docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md / docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md | Do not retune nested H=8 or score-correction from this class. | partial |
| `H2` | explains_closed_qv_not_deployed_rule | docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md / docs/NEXUS_RECEDING_LONG_TERM_VALUE_AUDIT.md | Not the deployed H=16 receding rule. | partial |
| `H3` | incomplete_label_collision | — / docs/NEXUS_HYPOTHESIS_REGISTER.md | Cite the specific later ID, not a generic H3. | incomplete |
| `H8` | not_established | — / docs/NEXUS_MCC_NATIVE_RMS_RESULTS.md | Closed unused MCC split. Do not reuse as a train label. | partial |
| `H9` | harm_established | — / docs/NEXUS_MCC_RESIDUAL_SCALE_RESULTS.md | Closed. Do not reuse the same MCC split. | partial |
| `H10` | supported_one_holdout | — / docs/NEXUS_MCC_MULTITASK_128_RESULTS.md | One holdout. Not confirmation. Not learning-to-learn. | partial |
| `H11` | not_established | — / docs/NEXUS_MCC_MULTITASK_128_CONFIRM_RESULTS.md | Closed unused MCC confirmation. Do not retune. | partial |
| `H12` | supported | — / docs/NEXUS_MCC_PLANNING_RANKING_RESULTS.md | LEVEL 1 ranking. Not 200-step control. Closed unused MCC. | partial |
| `H13` | supported | docs/NEXUS_MCC_PLANNING_RANKING_CONFIRM_PROTOCOL.md / docs/NEXUS_MCC_PLANNING_RANKING_CONFIRM_RESULTS.md | Second ranking holdout. Recede is not the primary. Closed. | partial |
| `H14` | supported | docs/NEXUS_H14_CANDIDATE_REUSE_PROTOCOL.md / docs/NEXUS_H14_CANDIDATE_REUSE_RESULTS.md | Closed unused MCC (0.0023, 0.0019, 0.065). Not 200-step control. Not L2L. | partial |
| `H15` | supported | docs/NEXUS_H15_CANDIDATE_REUSE_CONFIRM_PROTOCOL.md / docs/NEXUS_H15_CANDIDATE_REUSE_CONFIRM_RESULTS.md | Closed unused MCC confirmation. Do not retune. | partial |
| `H16` | not_established | docs/NEXUS_H16_SAME_STATE_LIBRARY_PROTOCOL.md / docs/NEXUS_H16_SAME_STATE_LIBRARY_RESULTS.md | Closed unused MCC (0.0015, 0.0014, 0.055). Interval includes 0. Do not retune. | partial |
| `H17` | blocked | — / — | Do not execute. Do not select a target. Exclusion list is a blocklist only. | reviews_only |
| `H-lookahead-pendulum` | supported_development_algorithm_copy | — / docs/NEXUS_BELLMAN_BACKUP_CONTROL_RESULTS.md | Algorithm copy on family-native models. Not cross-family learning. | partial |
| `H-lookahead-transfer` | supported_one_holdout_not_l2l | docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_PROTOCOL.md / docs/NEXUS_LOOKAHEAD_TRANSFER_CONFIRMATION_RESULTS.md | Closed lookahead_transfer_holdout_v1 tuples. Not L2L. | partial |
| `H-lookahead-acrobot` | development_passed_confirmation_passed_compute_matched_not_established | docs/NEXUS_ACROBOT_LOOKAHEAD_PROTOCOL.md / docs/NEXUS_ACROBOT_LOOKAHEAD_RESULTS.md | Closed Acrobot lookahead holdouts. Do not shop a new unnamed confirmation. | partial |
| `E1-feasibility` | designed_not_scientifically_tested | docs/NEXUS_EVOLUTION1_FEASIBILITY.md / — | Feasibility and fixture contracts only. Not a scientific result. | source_verified |
| `E1-toy-loop` | synthetic_only | docs/NEXUS_EVOLUTION1_AUTONOMOUS_LOOP_PROTOTYPE.md / docs/NEXUS_EVOLUTION1_AUTONOMOUS_LOOP_PROTOTYPE.md | Functional intervention, not transferable algorithm improvement. | source_verified |
| `E2-synthetic-screen` | synthetic_contract_only | docs/NEXUS_EVOLUTION2_CROSS_TASK_SCREEN.md / — | Authored hidden scores. Not LEVEL 2 evidence. Do not promote. | partial |
| `E2-pendulum-acrobot-v1` | design_locked_unauthorized_superseded_by_v2 | docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL.md / — | Historical v1 lock. Do not collect. Holdout unnamed. See readiness review. | source_verified |
| `E2-pendulum-acrobot-v2` | design_only_unauthorized | docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2.md / — | Superseding design. Do not collect. Do not name a holdout. | source_verified |
| `E2.1-planner-adapter` | engineering_only_unauthorized | docs/NEXUS_EVOLUTION2_TRUSTED_PLANNER_ADAPTER.md / — | Fake-model adapter. Not a scientific result. Do not collect. | source_verified |
| `E2-pendulum-acrobot-v2-pilot` | prospective_design_unauthorized | docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_PROTOCOL_V2_PILOT.md / — | Reduced worksheet only. Do not collect. Do not rewrite v2. Holdout unnamed. | source_verified |
| `E2-pendulum-acrobot-holdout-review` | naming_blocked | docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_HOLDOUT_REVIEW.md / artifacts/evolution2_pendulum_acrobot_holdout_review.json | Naming blocked. Do not persist a physics tuple. Do not collect. | source_verified |
| `E2-pendulum-acrobot-instance-rules` | four_role_rules_locked_unnamed | docs/NEXUS_EVOLUTION2_PENDULUM_ACROBOT_INSTANCE_RULES.md / artifacts/evolution2_pendulum_acrobot_instance_rules.json | Rules locked. Do not persist tuples. Do not collect. Later naming must match the four digests. | source_verified |
| `E2-residual-timing-probe` | probe_complete_not_a_transfer_result | docs/NEXUS_EVOLUTION2_RESIDUAL_TIMING_PROBE.md / docs/NEXUS_EVOLUTION2_RESIDUAL_TIMING_PROBE_RESULTS.md | Read-only inference. 0 env steps. Not a transfer result. Do not collect. | source_verified |
| `E2.2-adapter-correctness` | engineering_audit_science_blocked | docs/NEXUS_EVOLUTION2_ADAPTER_CORRECTNESS.md / docs/NEXUS_EVOLUTION2_ADAPTER_CORRECTNESS.md | Fixes adapter parity and evolution fairness. Does not enable dispatch or collect. | source_verified |
| `E2.3-source-fitting` | source_fitting_unavailable_cache_pass | docs/NEXUS_EVOLUTION2_SOURCE_FITTING_BENCHMARK.md / docs/NEXUS_EVOLUTION2_SOURCE_FITTING_BENCHMARK.md | Do not collect replacements. Do not invent a fit time. TrustedEvaluator owns scores. | source_verified |
| `NEXUS_ACROBOT_COMPUTE_MATCHED_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_ACROBOT_COMPUTE_MATCHED_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACROBOT_COMPUTE_MATCHED_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_ACROBOT_COMPUTE_MATCHED_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACROBOT_LOOKAHEAD_CONFIRM_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_ACROBOT_LOOKAHEAD_CONFIRM_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_CONDITIONED_Q_FEASIBILITY` | incomplete_unindexed_document | docs/NEXUS_ACTION_CONDITIONED_Q_FEASIBILITY.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_CONDITIONED_Q_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_ACTION_CONDITIONED_Q_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_CONDITIONED_Q_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_ACTION_CONDITIONED_Q_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_CONDITIONED_Q_RESUME_FEASIBILITY` | incomplete_unindexed_document | docs/NEXUS_ACTION_CONDITIONED_Q_RESUME_FEASIBILITY.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_CONDITIONED_Q_RESUME_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_ACTION_CONDITIONED_Q_RESUME_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_CONDITIONED_Q_RESUME_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_ACTION_CONDITIONED_Q_RESUME_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_VALUE_ALIGNMENT_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_ACTION_VALUE_ALIGNMENT_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_ACTION_VALUE_ALIGNMENT_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_ACTION_VALUE_ALIGNMENT_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_BELLMAN_BACKUP_CONTROL_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_BELLMAN_BACKUP_CONTROL_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CAPACITY_MATCHED_Q_FEASIBILITY` | incomplete_unindexed_document | docs/NEXUS_CAPACITY_MATCHED_Q_FEASIBILITY.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CAPACITY_MATCHED_Q_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_CAPACITY_MATCHED_Q_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_H3_SATURATION_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_CARTPOLE_H3_SATURATION_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_H3_SATURATION_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_CARTPOLE_H3_SATURATION_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_LOOKAHEAD_HARD_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_CARTPOLE_LOOKAHEAD_HARD_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_LOOKAHEAD_HARD_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_CARTPOLE_LOOKAHEAD_HARD_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_LOOKAHEAD_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_CARTPOLE_LOOKAHEAD_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_LOOKAHEAD_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_CARTPOLE_LOOKAHEAD_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_LOOKAHEAD_SAT_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_CARTPOLE_LOOKAHEAD_SAT_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CARTPOLE_LOOKAHEAD_SAT_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_CARTPOLE_LOOKAHEAD_SAT_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_COMMITMENT_VALUE_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_COMMITMENT_VALUE_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_COMMITMENT_VALUE_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_COMMITMENT_VALUE_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_CONTEXT_ADAPTATION_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_CONTEXT_ADAPTATION_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_FIRST_ACTION_VALUE_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_FIRST_ACTION_VALUE_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_FIRST_ACTION_VALUE_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_FIRST_ACTION_VALUE_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_H10_H11_CONTROL_DISAGREEMENT_AUDIT_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_H10_H11_CONTROL_DISAGREEMENT_AUDIT_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_H14_CANDIDATE_REUSE_FEASIBILITY` | incomplete_unindexed_document | docs/NEXUS_H14_CANDIDATE_REUSE_FEASIBILITY.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_H16_SAME_STATE_LIBRARY_FEASIBILITY` | incomplete_unindexed_document | docs/NEXUS_H16_SAME_STATE_LIBRARY_FEASIBILITY.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_H17_OCCUPANCY_DEPENDENCE_FEASIBILITY` | incomplete_unindexed_document | docs/NEXUS_H17_OCCUPANCY_DEPENDENCE_FEASIBILITY.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_HORIZON_ALIGNMENT_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_HORIZON_ALIGNMENT_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_HORIZON_ALIGNMENT_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_HORIZON_ALIGNMENT_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_HORIZON_OBJECTIVE_CONTROL_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_HORIZON_OBJECTIVE_CONTROL_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_HORIZON_OBJECTIVE_CONTROL_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_HORIZON_OBJECTIVE_CONTROL_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_LATE_CONTROL_GAP_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_LATE_CONTROL_GAP_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_LATE_EPISODE_DECISION_TRAJECTORY_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_LONG_CONTINUATION_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_LONG_CONTINUATION_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_LONG_CONTINUATION_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_LONG_CONTINUATION_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MCC_MULTITASK_128_CONFIRM_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MCC_MULTITASK_128_CONFIRM_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MCC_MULTITASK_128_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MCC_MULTITASK_128_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MCC_NATIVE_RMS_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MCC_NATIVE_RMS_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MCC_PLANNING_RANKING_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MCC_PLANNING_RANKING_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MCC_RESIDUAL_SCALE_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MCC_RESIDUAL_SCALE_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_COMPUTE_MATCHED_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MOUNTAINCAR_COMPUTE_MATCHED_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_COMPUTE_MATCHED_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_MOUNTAINCAR_COMPUTE_MATCHED_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_CONFIRM_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_CONFIRM_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_CONFIRM_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_CONFIRM_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_MOUNTAINCAR_CONTINUOUS_LOOKAHEAD_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_LOOKAHEAD_CONFIRM_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MOUNTAINCAR_LOOKAHEAD_CONFIRM_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_LOOKAHEAD_CONFIRM_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_MOUNTAINCAR_LOOKAHEAD_CONFIRM_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_LOOKAHEAD_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_MOUNTAINCAR_LOOKAHEAD_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_MOUNTAINCAR_LOOKAHEAD_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_MOUNTAINCAR_LOOKAHEAD_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_PENDULUM_COMPUTE_MATCHED_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_PENDULUM_COMPUTE_MATCHED_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_PENDULUM_COMPUTE_MATCHED_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_PENDULUM_COMPUTE_MATCHED_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_PREFIX_MAX_TREE_REUSE_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_PREFIX_MAX_TREE_REUSE_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_PREFIX_MAX_TREE_REUSE_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_PREFIX_MAX_TREE_REUSE_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_RECEDING_POLICY_CONSISTENCY_FEASIBILITY` | incomplete_unindexed_document | docs/NEXUS_RECEDING_POLICY_CONSISTENCY_FEASIBILITY.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_RECEDING_POLICY_CONSISTENCY_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_RECEDING_POLICY_CONSISTENCY_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_RECEDING_POLICY_CONSISTENCY_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_SAME_SET_PLANNING_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_SAME_SET_PLANNING_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_SAME_SET_PLANNING_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_SAME_SET_PLANNING_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_SOURCE_SCALAR_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_SOURCE_SCALAR_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_SOURCE_SCALAR_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_SOURCE_SCALAR_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_TERMINAL_VALUE_CALIBRATION_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_TERMINAL_VALUE_CALIBRATION_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_TERMINAL_VALUE_CALIBRATION_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_TERMINAL_VALUE_CALIBRATION_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_TERMINAL_VALUE_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_TERMINAL_VALUE_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_TERMINAL_VALUE_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_TERMINAL_VALUE_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_TREE_REUSE_LOOKAHEAD_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_TREE_REUSE_LOOKAHEAD_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_TREE_REUSE_LOOKAHEAD_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_TREE_REUSE_LOOKAHEAD_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_VALUE_CANDIDATE_DISCRIMINATION_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_VALUE_CANDIDATE_DISCRIMINATION_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_VALUE_CANDIDATE_DISCRIMINATION_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_VALUE_CANDIDATE_DISCRIMINATION_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_VISITED_COMMITMENT_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_VISITED_COMMITMENT_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_VISITED_COMMITMENT_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_VISITED_COMMITMENT_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_VISITED_VALUE_RANKING_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_VISITED_VALUE_RANKING_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_VISITED_VALUE_RANKING_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_VISITED_VALUE_RANKING_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_CARTPOLE_TARGET_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_XENV_CARTPOLE_TARGET_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_CARTPOLE_TARGET_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_XENV_CARTPOLE_TARGET_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_CONTEXT_CODE_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_XENV_CONTEXT_CODE_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_CONTEXT_CODE_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_XENV_CONTEXT_CODE_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_DEEP_TRUNK_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_XENV_DEEP_TRUNK_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_DEEP_TRUNK_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_XENV_DEEP_TRUNK_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_LOW_BUDGET_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_XENV_LOW_BUDGET_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_LOW_BUDGET_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_XENV_LOW_BUDGET_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_PRIOR_SCALE_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_XENV_PRIOR_SCALE_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_PRIOR_SCALE_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_XENV_PRIOR_SCALE_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_RESIDUAL_CONTEXT_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_XENV_RESIDUAL_CONTEXT_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_RESIDUAL_CONTEXT_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_XENV_RESIDUAL_CONTEXT_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_TRANSFER_PILOT_PROTOCOL` | incomplete_unindexed_document | docs/NEXUS_XENV_TRANSFER_PILOT_PROTOCOL.md / — | Consult the document before reuse. Do not invent a label. | incomplete |
| `NEXUS_XENV_TRANSFER_PILOT_RESULTS` | incomplete_unindexed_document | — / docs/NEXUS_XENV_TRANSFER_PILOT_RESULTS.md | Consult the document before reuse. Do not invent a label. | incomplete |

## Machine-readable copy

`artifacts/nexus_research_registry.json`
