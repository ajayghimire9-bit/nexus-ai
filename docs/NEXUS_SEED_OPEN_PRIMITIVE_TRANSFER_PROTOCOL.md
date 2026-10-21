# NEXUS Seed — Meta-Rule Evolution v2 (Stage A) & Open Primitive Code Transfer v1 (Stage B) Preregistered Protocol

- **Schema**: `seed_open_primitive_transfer_v1`
- **Branch**: `codex/seed-open-primitive-transfer-v1`
- **Starting Revision**: `f231a03afacbf07d65e765409c1988c4d0457753`
- **Implementation**: [src/nexus/seed/open_primitive_transfer.py](../src/nexus/seed/open_primitive_transfer.py)
- **V1 Adversarial Audit**: [NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md) ([`artifacts/seed_meta_rule_evolution_v1_audit.json`](../artifacts/seed_meta_rule_evolution_v1_audit.json))
- **Locked Configuration**: [`configs/seed_open_primitive_transfer.json`](../configs/seed_open_primitive_transfer.json)

---

## 1. Scientific Objective & Two-Stage Gate

Following the adversarial audit of `seed_meta_rule_evolution_v1` ([NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md)), which confirmed 15 evaluator-leakage, guided-injection, and isomorphic-grammar confounds, this protocol preregisters a strictly gated two-stage experiment:

1. **Stage A — Meta-Rule Evolution v2 (Repair and Replication Without Evaluator Leakage)**:
   - Separates `LearnerTaskView` from `EvaluatorTaskPrivate` with recursive zero-leakage verification (`assert_zero_evaluator_leakage`).
   - Executes real candidate compositions on observed and queried inputs via a counted kernel API and computes held-out accuracy by executing the accepted candidate on private protected inputs.
   - Removes all guided rule injection (`build_initial_population` contains only published handwritten baselines plus uniformly generated valid mutations; zero per-generation child overwrite; strictly uniform `1/13` non-stop opcode sampling; untouched `random_evolutionary_selection` control).
   - Evaluates three genuinely non-isomorphic symbolic families (`list_transformations`, `boolean_circuit_induction`, and `fst_string_rewrite`) with in-loop Dream curriculum generation, real pre/post retention execution, and real Sleep test re-execution with non-overlapping greedy MDL macro compression.
2. **Stage B — Open Primitive Code Transfer v1 (`PROPOSE_PRIMITIVE` & `UnknownLibraryCodeLab`)**:
   - **Executes ONLY if Stage A passes.**
   - Freezes the Stage A evolved learning rule before generating 3 independent unknown pure-Python library families (`ulib_window_checksum`, `ulib_runlength_bucket`, `ulib_zigzag_interleave`) inside temporary content-addressed sandboxes (`CommonEnvironmentAdapter` returning `TransitionReceipt`).
   - Tests whether the learner can inspect obfuscated functions (`_kx9_win_fold`, `_vq4_rle_span`, `_zm7_zigzag_fold`), infer partial effect models from bounded calls, quarantine and promote a `PrimitiveProposal` via `PROPOSE_PRIMITIVE` through the 6-state kernel lifecycle (`PROPOSED -> STATICALLY_VALID -> SANDBOX_VALIDATED -> HELDOUT_VALIDATED -> RETENTION_VALIDATED -> PROMOTED`), compose the promoted primitive into an AST patch (`APPLY_AST_PATCH`), pass private kernel-owned hidden tests, and bind secondary invented words (`krelv`, `voux`, `zarn`) across Coding and Reasoning Labs without a human-supplied mapping.

---

## 2. Stage A Design: Learner/Evaluator Separation, Non-Isomorphic Families & Fair Baselines

### 2.1 Non-Overlapping Data Structures
- **`LearnerTaskView`**: `task_id`, `family`, `public_type_signatures`, `public_primitive_handles`, `currently_observed_examples`, `candidate_query_inputs`, `query_action_budget`, `allowed_typed_actions`, `public_resource_costs`, `invented_word`.
- **`EvaluatorTaskPrivate`**: `task_id`, `family`, `target_implementation`, `target_composition`, `hidden_semantic_equivalence_class`, `unqueried_outputs`, `protected_assessment_inputs_and_outputs`, `oracle_information`, `acceptance_labels`.
- **Forbidden Keys in Any Learner-Visible Object**: `target_ops`, `target_implementation`, `target_composition`, `true_effect_state`, `exact_consistent`, `coarse_consistent`, `evaluator_labels`, `acceptance_labels`, `hidden_outputs`, `unqueried_outputs`, `protected_outcomes`, `protected_assessment`, `protected_assessment_inputs_and_outputs`, `semantic_class_ids`, `hidden_semantic_equivalence_class`, `oracle_information`, `effect_distance`, `state_key`.

### 2.2 Non-Isomorphic Families
1. **Source Family A (`list_transformations`, `list[int] -> list[int]`)**: `reverse_list`, `sort_asc`, `dedup_order`, `add_two`, `sub_one`, `keep_even`.
2. **Source Family B (`boolean_circuit_induction`, `list[bits4] -> list[bits4]`)**: 4-bit logic gate circuits (`gate_not_b0`, `gate_xor_01`, `gate_and_12`, `gate_or_23`, `gate_maj_012`, `gate_rotl4`).
3. **Development Family (`fst_string_rewrite`, `list[str] -> list[str]`)**: finite-state transducer rewrites over `{"a","b","c"}` (`fst_collapse_runs`, `fst_swap_ab`, `fst_double_c`, `fst_strip_b`, `fst_prefix_a`, `fst_rotate_left`).
4. **Sealed Family (`unknown_library_code_lab`, Stage B)**: 3 pure-Python sandbox library families with obfuscated helper functions and non-isomorphic effects (`_kx9_win_fold` modular window checksum, `_vq4_rle_span` run-length product bucket, `_zm7_zigzag_fold` outer-to-inner mirror fold).

### 2.3 Stage A Fair Baselines
All baselines receive the same public primitive handles, learned primitive models, query interface, execution API, and semantic-equivalence treatment:
1. `current_handwritten_learner`
2. `exact_information_gain_learner`
3. `exact_information_gain_plus_effect_composition`
4. `mdl_best_first_search`
5. `exhaustive_typed_enumeration`
6. `random_valid_learning_rules`
7. `random_evolutionary_selection`
8. `shortest_valid_rule`
9. `no_evolution_ablation`
10. `evolved_rule_single_instruction_ablations` (each discovered instruction removed individually)

---

## 3. Stage B Design: `CommonEnvironmentAdapter`, `PROPOSE_PRIMITIVE` & `UnknownLibraryCodeLab`

### 3.1 `CommonEnvironmentAdapter` & `TransitionReceipt`
Implements `reset(seed)`, `observe()`, `available_actions()`, `execute(typed_action)`, `evaluate(goal_predicate)`, `snapshot()`, and `restore()`, returning a `TransitionReceipt` (`observation_before`, `typed_action`, `observation_after`, `state_diff`, `stdout`, `stderr`, `exit_status`, `execution_time`, `resource_use`, `provenance`).

### 3.2 `PROPOSE_PRIMITIVE` & Kernel-Controlled Lifecycle
- Creates a quarantined `PrimitiveProposal` (`proposal_id`, `proposed_name`, `type_signature`, `implementation_kind`, `implementation_reference_hash`, `source_code`, `preconditions`, `predicted_effects`, `evidence_ids`, `counterexamples`, `dependency_versions`, `expected_mdl_benefit`).
- Lifecycle enforced exclusively by `ImmutableTrustedKernel.evaluate_primitive_proposal`:
  $$\texttt{PROPOSED} \to \texttt{STATICALLY\_VALID} \to \texttt{SANDBOX\_VALIDATED} \to \texttt{HELDOUT\_VALIDATED} \to \texttt{RETENTION\_VALIDATED} \to \texttt{PROMOTED}$$
- Kernel decision is strictly one of `ACCEPT`, `REJECT`, or `NEED_MORE_EVIDENCE`.

### 3.3 Stage B Baselines
1. `corrected_frozen_evolved_rule`
2. `strongest_handwritten_learner`
3. `exact_information_gain_plus_effect_composition`
4. `exhaustive_sandbox_probing`
5. `examples_only_retrieval`
6. `learner_without_propose_primitive`
7. `proposal_lifecycle_without_sleep_compression`
8. `scratch_learning_in_target_lab`
9. `isolated_labs`

---

## 4. Registered Acceptance Gates (`12` Gates)

1. **`gate_01_zero_evaluator_private_fields_reach_learner`**: Recursive inspection confirms zero forbidden fields in any learner-visible structure.
2. **`gate_02_selected_program_passes_hidden_execution_tests`**: Mean held-out execution accuracy $\ge 0.99$ in Stage A and Stage B.
3. **`gate_03_unknown_effect_learned_without_stored_complete_fingerprint`**: `whole_program_fingerprints_stored == False` and Stage B hidden accuracy $\ge 0.99$.
4. **`gate_04_proposed_primitive_passes_complete_kernel_lifecycle`**: Every promoted primitive transitions through all 6 lifecycle states (`PROPOSED` $\to \dots \to$ `PROMOTED`).
5. **`gate_05_frozen_rule_transfers_to_non_isomorphic_code_family`**: Non-isomorphism proof holds and Stage B accuracy $\ge 0.99$.
6. **`gate_06_beats_or_non_inferior_to_strongest_fair_baseline_on_success`**: Evolved learner is $\ge$ strongest fair baseline on task success in Stage A and Stage B.
7. **`gate_07_improves_experiments_or_compute_with_paired_ci_excluding_zero`**: Paired 95% Student-$t$ confidence intervals ($df=7$) for compute cost reduction vs `exact_information_gain_plus_effect_composition` and `strongest_handwritten_learner` exclude zero (`ci95_low > 0`).
8. **`gate_08_removing_promoted_primitive_removes_transfer_gain`**: Ablating `PROPOSE_PRIMITIVE` (`learner_without_propose_primitive`) reduces Stage B accuracy by $\ge 0.50$.
9. **`gate_09_no_human_written_cross_lab_semantic_mapping`**: `manually_supplied_cross_lab_mapping == False` and secondary invented-word transfer across Coding and Reasoning Labs achieves $\ge 0.99$.
10. **`gate_10_old_task_retention_at_least_98pct_real_pre_post`**: Real pre/post execution accuracy on protected old tasks is $\ge 0.98$ with `worst_regression == 0.0`.
11. **`gate_11_all_discovery_evolution_sandbox_validation_costs_included`**: All kernel counters (`candidate_executions`, `primitive_calibrations`, `queries`, `dsl_instructions`, `hidden_evaluations`, `sandbox_actions`, `proposal_validations`) and `kernel_sha256_before == kernel_sha256_after` are verified.
12. **`gate_12_at_least_two_unknown_library_families_reproduce`**: At least $2$ independently generated unknown-library families reproduce the result (`3` families tested across 8 seeds).

---

## 5. Permitted Conclusions

- **If Stage A fails**:
  *“Meta-rule evolution remains an engineering hypothesis; learning-to-learn is not established.”*
- **If Stage A passes but Stage B fails**:
  *“NEXUS demonstrated bounded meta-rule transfer on synthetic non-isomorphic families, but open primitive acquisition was not established.”*
- **If both pass**:
  *“NEXUS demonstrated bounded executable learning-rule transfer and acquired one previously unavailable primitive from sandboxed code interactions. This does not establish arbitrary coding, general language understanding, unrestricted self-improvement or AGI.”*
