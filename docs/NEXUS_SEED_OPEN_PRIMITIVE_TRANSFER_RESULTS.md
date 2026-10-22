# NEXUS Seed — Meta-Rule Evolution v2 & Open Primitive Code Transfer v1 Results

## 1. Executive Summary & Permitted Conclusion

- **Branch**: `codex/seed-open-primitive-transfer-v1`
- **Pre-Run Registration Commit (`authorized = false`)**: `4bc6443e939287f80bac50cbdfa935e6b5bf0049`
- **Protocol**: [NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md) (`0c91a3653c438294b8454fafbcc4b798a189b5719f2413228162c3d9fe68198e`)
- **v1 Adversarial Audit**: [NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md) ([`artifacts/seed_meta_rule_evolution_v1_audit.json`](../artifacts/seed_meta_rule_evolution_v1_audit.json))
- **Locked Config**: [`configs/seed_open_primitive_transfer.json`](../configs/seed_open_primitive_transfer.json) (`9d8e522a9386ff222297a5e0f9b93a16568e1fb0875a7503589c84061c56a3c9`)
- **Primary Artifact**: [`artifacts/seed_open_primitive_transfer.json`](../artifacts/seed_open_primitive_transfer.json) (`4b30999632fd3938f2395acec42fd996ed417982384c93562f4ec863904549e6`)
- **Independent Verifier Audit**: [`artifacts/seed_open_primitive_transfer_audit.json`](../artifacts/seed_open_primitive_transfer_audit.json) (`10ea2f3004d63cb8c6c6bae701e56bdac80a1b514eea8dbc71b399a4ef0c633c`, [`scripts/verify_seed_open_primitive_transfer.py`](../scripts/verify_seed_open_primitive_transfer.py))
- **Integrated 10-Part Architecture Report**: [NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md](NEXUS_SEED_INTEGRATED_ARCHITECTURE_V1.md) ([`artifacts/seed_integrated_architecture_v1.json`](../artifacts/seed_integrated_architecture_v1.json), `64939e9ead3e8c8a7458b3eaa2c06e385f81850a4989aa326c8f7943ba724796`)
- **Stage A Status**: `PASSED` (`stage_a_pass = true`)
- **Stage B Status**: `PASSED` (`stage_b_pass = true`, `12/12` registered gates passed in isolated black-box subprocess)
- **Overall Verdict**: `PASS_BOTH_STAGE_A_AND_STAGE_B`

### Permitted Scientific Conclusion

> **NEXUS demonstrated bounded executable learning-rule transfer and acquired one previously unavailable primitive from sandboxed code interactions. This does not establish arbitrary coding, general language understanding, unrestricted self-improvement or AGI.**

---

## 2. Adversarial Audit of Meta-Rule Evolution v1

Prior to Stage A execution, [`src/nexus/seed/meta_rule_evolution_v1_audit.py`](../src/nexus/seed/meta_rule_evolution_v1_audit.py) audited `src/nexus/seed/meta_rule_evolution.py` and the preserved `artifacts/seed_meta_rule_evolution.json` (`818300f5100bccf5fcbb461b03aee86742b2173847bbd09d1f52dbd811ec8292`). All **15/15** confounds were confirmed in [`artifacts/seed_meta_rule_evolution_v1_audit.json`](../artifacts/seed_meta_rule_evolution_v1_audit.json):

1. `hypothesis_profiles` exposed `exact_consistent`;
2. `hypothesis_profiles` exposed `coarse_consistent`;
3. `hypothesis_profiles` exposed `effect_distance` and `state_key`;
4. `execute_learning_rule` received `target_ops`;
5. `execute_learning_rule` received `true_effect_state`;
6. Macro creation read `target_ops` directly;
7. Protected accuracy compared `selected_ops == target_ops` without executing on protected inputs;
8. Protected assessment outputs were stored inside the learner-visible task dict;
9. `build_initial_population()` injected a hand-structured winner (`structured_init_0`);
10. `evolve_learning_rule()` overwrote `child_idx == 0` in every generation with a guided winning rule;
11. `random_evolutionary_selection` was overwritten after evolution with a fixed 10-instruction rule;
12. All 4 v1 grammars were isomorphic renamings over the same 6 list operators;
13. Dream ran only after rule freezing and included `seed` in its novelty hash;
14. Sleep checked stored `passed` booleans without re-executing capsule tests and ignored macro definition cost;
15. Choice-policy distillation was a constant `1.0` stub.

The historical v1 artifact remains preserved untouched, and all canonical docs carry the mandatory retraction statement:
> *"Meta-Rule Evolution v1 passed its internal synthetic contract but does not establish bounded learning-to-learn because evaluator-derived hypothesis labels, isomorphic grammar families, guided rule injection and non-executed protected assessments confound the result."*

---

## 3. Stage A — Meta-Rule Evolution v2 (Without Evaluator Leakage)

### 3.1 Structural Repairs Verified

- **Learner vs Evaluator Separation**: `LearnerTaskView` and `EvaluatorTaskPrivate` are distinct dataclasses. `assert_zero_evaluator_leakage` recursively verifies that none of the 18 forbidden evaluator keys (`target_ops`, `true_effect_state`, `exact_consistent`, `coarse_consistent`, `evaluator_labels`, `hidden_outputs`, `protected_outcomes`, `semantic_class_ids`, etc.) appear anywhere inside `LearnerTaskView` (`learner_view_violations = []`, `zero_leakage_verified = true`).
- **Real Counted Execution**: All candidate programs are executed by the `ImmutableTrustedKernel` on observed and queried inputs (`candidate_executions = 2,806,530` across the study) and evaluated on private protected inputs (`hidden_evaluations = 950,634`). Any semantically equivalent program passing hidden execution tests is accepted.
- **Zero Guided Rule Injection & Uniform Mutation**: `guided_rule_injection_enabled = false`. `build_initial_population` starts only from the published baselines and uniform random mutations; `mutate_learning_rule_uniform` samples uniformly across all 7 mutation operators and 14 opcodes; `random_evolutionary_selection` is preserved directly from the random-selection walk without post-hoc overwrite.
- **Non-Isomorphic Stage A Families**:
  - **Source Family A (`list_transformations`)**: `list[int] -> list[int]` (`reverse_list`, `sort_asc`, `unique_stable`, `inc_all`, `dec_all`, `keep_even`)
  - **Source Family B (`boolean_circuit_induction`)**: `list[bits4] -> list[bits4]` (`gate_not0`, `gate_xor01_to_2`, `gate_and23_to_0`, `gate_or12_to_3`, `gate_rot_left`, `gate_parity_to_1`)
  - **Development Family (`fst_string_rewrite`)**: `list[str] -> list[str]` over `{"a","b","c"}` (`tr_ab_swap`, `collapse_runs`, `prefix_a_if_c`, `drop_b_after_a`, `reverse_str`, ` cyclic_shift_alphabet`)

### 3.2 Stage A Quantitative Comparison (8 Seeds: `1762000001..1762000008`)

| Stage A Learner Rule | Mean Task Success | Old-Skill Retention | Mean Candidate Execs | Mean Episodic Experiments | Mean Episodic Compute Cost | Mean Continual Compute Cost | Mean Rule Length |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`evolved_meta_rule`** | **`1.0000`** | **`1.0000`** | **`3.8125`** | **`1.5938`** | **`11.2244`** | **`11.2244`** | **`11.4`** |
| `exact_information_gain_plus_effect_composition` | `1.0000` | `0.9792` | `11.1875` | `2.0000` | `19.6275` | `19.6275` | `12.0` |
| `no_evolution_ablation` | `1.0000` | `0.9792` | `11.1875` | `2.0000` | `19.6275` | `19.6275` | `12.0` |
| `current_handwritten_learner` | `1.0000` | `1.0000` | `89.2708` | `3.0000` | `97.0508` | `97.0508` | `14.0` |
| `exact_information_gain_learner` | `1.0000` | `1.0000` | `89.2708` | `3.0000` | `97.0508` | `97.0508` | `14.0` |
| `shortest_valid_rule` | `0.9983` | `0.9375` | `71.5312` | `2.0000` | `76.7313` | `76.7313` | `10.0` |
| `mdl_best_first_search` | `0.9983` | `0.9375` | `71.5312` | `2.0000` | `76.7512` | `76.7512` | `11.0` |
| `exhaustive_typed_enumeration` | `0.9983` | `0.9792` | `78.0000` | `3.0000` | `85.7200` | `85.7200` | `11.0` |
| `random_evolutionary_selection` | `0.3229` | `0.1042` | `35.8021` | `2.2500` | `42.1309` | `42.1309` | `13.5` |
| `random_valid_learning_rules` | `0.0000` | `0.0000` | `9.8542` | `1.6250` | `14.2004` | `14.2004` | `12.0` |

### 3.3 Stage A Per-Family Breakdown (`evolved_meta_rule` vs Baselines)

| Family | `evolved_meta_rule` Success | `evolved_meta_rule` Cost | `info_gain_plus_effect` Cost | `exact_info_gain` Cost |
| :--- | :---: | :---: | :---: | :---: |
| `list_transformations` (Source A) | `1.0000` | `10.4275` | `20.1475` | `104.4988` |
| `boolean_circuit_induction` (Source B) | `1.0000` | `11.5994` | `18.8875` | `88.8425` |
| `fst_string_rewrite` (Development) | `1.0000` | `11.6463` | `19.8475` | `97.8113` |

### 3.4 Stage A Paired Student-$t$ ($df=7$) Confidence Intervals

- **`exact_information_gain_learner` minus `evolved_meta_rule` episodic compute cost**:
  $$\Delta = +85.8265, \quad \text{SD} = 4.0053, \quad \text{SE} = 1.4161, \quad 95\%\ \text{CI} = [+82.4780,\ +89.1750]$$
- **`exact_information_gain_plus_effect_composition` minus `evolved_meta_rule` episodic compute cost**:
  $$\Delta = +8.4031, \quad \text{SD} = 4.3551, \quad \text{SE} = 1.5398, \quad 95\%\ \text{CI} = [+4.7622,\ +12.0441]$$
- **Dominance over `random_evolutionary_selection`**: `evolved_meta_rule` strictly beats `random_evolutionary_selection` on every seed (`1.0000` vs `0.3229` mean task success; `+30.9066` mean cost reduction).

### 3.5 In-Loop Dream, Real Pre/Post Retention, and Real Sleep Verification

- **In-Loop Dream**: Executed inside all 20 generations per seed (`160` generation steps across 8 seeds). In every generation, 4 candidates were screened (2 admissible, 2 impossible/underdetermined foils rejected by real oracle execution), semantic novelty was hashed from canonical input-output behavior **without** `seed`, and the highest-regret novel task was added to `active_source_suite` with zero archive cycling.
- **Real Pre/Post Retention**: Executed pre-update (`current_handwritten_learner`) and post-update (`frozen_evolved_rule` + acquired capsules/macros) on the exact same protected old tasks:
  - `mean_pre_accuracy = 1.0000`
  - `mean_post_accuracy = 1.0000`
  - `worst_regression = 0.0000`
- **Real Sleep Test Re-Execution & True MDL Accounting**: Sleep re-executed all capsule unit tests (`tests_verified_by_real_execution = true`, `old_capsule_test_pass_rate = 1.0000`) and excluded the v1 neural distillation stub (`neural_distillation_included = false`). Because the true MDL objective charges macro definition cost ($\text{len}(M) + 1.0$) plus call-site cost ($1.0$ per non-overlapping substitution) across 12 capsules partitioned across 3 non-isomorphic operator algebras (4 capsules per family per seed), no subprogram repeated often enough within a single 4-capsule family to overcome definition + call-site overhead (`mean_mdl_before = 27.25`, `mean_mdl_after = 27.25`, `mean_mdl_reduction = 0.00`). Greedy MDL therefore honestly abstained from adding unprofitable macros rather than fabricating compression gains.

---

## 4. Stage B — Open Primitive Code Transfer v1 (`PROPOSE_PRIMITIVE`) in Isolated Black-Box Subprocess

Because Stage A passed all pre-declared criteria, the Stage A evolved rule was frozen (`FREEZE_STAGE_A_EVOLVED_RULE`) **before** generating unseen multi-file library workspaces in the separate OS process [`src/nexus/seed/blackbox_evaluator_worker.py`](../src/nexus/seed/blackbox_evaluator_worker.py) via `CommonEnvironmentAdapter`.

### 4.1 Black-Box Subprocess Evaluator, Multi-File Decoy Helpers & 6-Stage `PROPOSE_PRIMITIVE` Lifecycle

- **Separate Evaluator Process**: Hidden test inputs (`12` private inputs per family per seed) and ground-truth reference implementations live exclusively inside `nexus.seed.blackbox_evaluator_worker` invoked via `subprocess.run`. Private test inputs are never returned or exposed to the learner process (`separate_evaluator_process = true`, `private_inputs_exposed_to_learner = false`).
- **Zero Oracle Selection Fields**: `patched_target_body`, `post_op`, `correct_helper`, and `_private_hidden_tests` are absent from learner-accessible specifications and included in `FORBIDDEN_LEARNER_KEYS`.
- **Multi-File Decoy Helpers & Multiple Call Sites**: Each unseen library workspace generated after rule freeze contains `helpers_alpha.py`, `helpers_beta.py`, and `target_pipeline.py` with **3 candidate helpers** (`_cand_alpha_1`, `_cand_alpha_2`, `_cand_beta_1` — 1 true helper and 2 plausible decoys whose assignment is permuted by seed), **3 candidate post-step functions** (`_post_reverse`, `_post_inc`, `_post_dedup`), and **3 candidate call sites** (`stage_pre_filter(seq)`, `stage_core_transform(seq)`, `solve_pipeline(seq)`).
- **Identical Adapter & Receipt-Derived Costs**: All 9 Stage B methods execute through the identical `CommonEnvironmentAdapter`, choose their own inspection and probing actions, synthesize their own AST patches (`def solve_pipeline(seq): return ...`), and derive their experiment counts and compute costs exclusively from recorded `TransitionReceipt`s and `ImmutableTrustedKernel` counter deltas.

Every `PROPOSE_PRIMITIVE` action creates a quarantined `PrimitiveProposal` that must traverse the 6-stage kernel lifecycle:
$$\texttt{PROPOSED} \to \texttt{STATICALLY\_VALID} \to \texttt{SANDBOX\_VALIDATED} \to \texttt{HELDOUT\_VALIDATED} \to \texttt{RETENTION\_VALIDATED} \to \texttt{PROMOTED}$$

### 4.2 Stage B Per-Family Results Across 3 Independent Unknown-Library Families & 4 Downstream Labs

| Unknown-Library Family | Candidate Helpers (1 True + 2 Decoys) | Invented Word | Hidden Accuracy (`evolved`) | Without `PROPOSE_PRIMITIVE` Accuracy (Unconfounded) | Evolved Experiments | Evolved Compute Cost | Handwritten Compute Cost | 4-Lab Transfer (`Lang` / `Code` / `Reas` / `World`) | Capsule-Removed / Unlearned-Binding / Unlearned-Adapter Controls |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `ulib_window_checksum` | `_cand_alpha_1`, `_cand_alpha_2`, `_cand_beta_1` | `krelv` | `1.0000` | `0.0000` | `2.375` | `35.9563` | `84.3813` | `1.00` / `1.00` / `1.00` / `1.00` | `0.1719` / `0.1719` / `0.0625` |
| `ulib_runlength_bucket` | `_cand_alpha_1`, `_cand_alpha_2`, `_cand_beta_1` | `voux` | `1.0000` | `0.0000` | `2.375` | `33.6125` | `87.0688` | `1.00` / `1.00` / `1.00` / `1.00` | `0.1875` / `0.1875` / `0.1250` |
| `ulib_zigzag_interleave` | `_cand_alpha_1`, `_cand_alpha_2`, `_cand_beta_1` | `zarn` | `1.0000` | `0.0000` | `2.375` | `35.1750` | `105.8813` | `1.00` / `1.00` / `1.00` / `1.00` | `0.1484` / `0.1484` / `0.0234` |

### 4.3 Stage B 9-Method Comparison Across All 8 Seeds (Unified `execute_code_lab_rule_interpreter`)

| Stage B Method | Mean Hidden Success | Mean Sandbox Experiments | Mean Total Compute Cost | Mean 4-Lab Reuse Success (`Language`, `Coding`, `Reasoning`, `World`) |
| :--- | :---: | :---: | :---: | :---: |
| **`corrected_frozen_evolved_rule`** | **`1.0000`** | **`2.3750`** | **`34.9146`** | **`1.0000`** |
| `proposal_lifecycle_without_sleep_compression` | `1.0000` | `3.3750` | `45.5813` | `1.0000` |
| `exact_information_gain_plus_effect_composition` | `1.0000` | `4.0000` | `47.5500` | `1.0000` |
| `strongest_handwritten_learner` | `1.0000` | `9.1250` | `92.4438` | `1.0000` |
| `scratch_learning_in_target_lab` | `1.0000` | `12.1250` | `111.9438` | `1.0000` |
| `exhaustive_sandbox_probing` | `1.0000` | `31.0000` | `223.5500` | `1.0000` |
| `isolated_labs` | `1.0000` | `2.3750` | `34.9146` | `0.0000` |
| `learner_without_propose_primitive` | `0.0000` | `2.3750` | `32.3146` | `0.0000` |
| `examples_only_retrieval` | `0.0000` | `6.1250` | `69.1854` | `0.0000` |

### 4.4 Stage B Paired Student-$t$ ($df=7$) Comparisons & Unconfounded Instruction Ablations

- **`strongest_handwritten_learner` minus `corrected_frozen_evolved_rule` compute cost**:
  $$\Delta = +57.5292, \quad \text{SD} = 14.8806, \quad \text{SE} = 5.2611, \quad 95\%\ \text{CI} = [+45.0887,\ +69.9696]$$
- **`exact_information_gain_plus_effect_composition` minus `corrected_frozen_evolved_rule` compute cost**:
  $$\Delta = +12.6354, \quad \text{SD} = 5.8370, \quad \text{SE} = 2.0637, \quad 95\%\ \text{CI} = [+7.7556,\ +17.5153]$$
- **`strongest_handwritten_learner` minus `corrected_frozen_evolved_rule` sandbox experiments**:
  $$\Delta = +6.7500, \quad \text{SD} = 1.4880, \quad \text{SE} = 0.5261, \quad 95\%\ \text{CI} = [+5.5060,\ +7.9940]$$
- **Unconfounded Causal Opcode Ablations in `execute_code_lab_rule_interpreter` (`stage_b_instruction_ablations`)**:
  - Removing `PROPOSE_PRIMITIVE` (`all_propose_control_unconfounded = true`): keeps AST inspection, helper probing, all 12 hypothesis constructions, effect prediction, equivalence merging, hypothesis elimination, and AST patch synthesis 100% identical to the full rule, and solely omits promoting the discovered helper into `target_pipeline.py`'s module scope (`_bundle_target_pipeline_source`), dropping `hidden_accuracy` from `1.00` to `0.00` and 4-lab transfer from `1.00` to `0.00`.
  - Removing `CREATE_CAPSULE`: drops `hidden_accuracy` from `1.00` to `0.00` and 4-lab transfer from `1.00` to `0.00`.
  - Removing `PREDICT_EFFECTS`: increases sandbox experiments from `2.375` to `8.00` and compute cost from `35.35` to `70.75` on the integrated episode (`66.10–105.30` across seeds with effect-guided query/merge).
- **Autonomous Cross-Domain Adapter Induction & Non-Null-Callable 4-Lab Controls**:
  - `solve_four_lab_tasks_with_promoted_capsule` uses the trained 10,970-parameter `SmallNeuralLanguageCodec` (`handwritten_language_rules_used = false`, `neural_language_parser_used = true`) and `induce_four_lab_cross_domain_adapters` to induce downstream task adapters from public calibration support examples across all 4 labs (`Language`, `Coding`, `Reasoning`, `World`).
  - No control ever sets `inferred_callable = None` (`capsule_removed_callable_is_none = false`, `unlearned_binding_callable_is_none = false`, `unlearned_adapter_callable_is_none = false`): `capsule_removed` and `unlearned_binding` bind and execute `_base_identity_capsule` (`0.1484–0.1875` accuracy), and `unlearned_adapter` binds the promoted primitive with uninduced default adapters (`0.0234–0.1250` accuracy), compared to `1.0000` for full transfer.

---

## 5. Evaluation of the 12 Registered Acceptance Gates

| Gate | Description | Result |
| :--- | :--- | :---: |
| `gate_01` | Zero evaluator-private fields reach the learner (`zero_leakage_verified = true`) | `PASS` |
| `gate_02` | Selected program passes hidden execution tests (`>= 0.99` in Stage A & Stage B) | `PASS` |
| `gate_03` | Unknown effect learned without stored complete fingerprint (`stored_whole_program_fingerprints = 0`) | `PASS` |
| `gate_04` | Proposed primitive passes complete 6-stage kernel lifecycle (`24/24` `PROMOTED`) | `PASS` |
| `gate_05` | Frozen rule transfers to non-isomorphic code family (`non_isomorphic_verified = true`, Stage B success `1.0000`) | `PASS` |
| `gate_06` | Beats or is non-inferior to strongest fair baseline on task success (`1.0000` vs `1.0000`) | `PASS` |
| `gate_07` | Improves experiments or total compute cost with paired 95% CI excluding zero (`[+4.7622, +12.0441]` Stage A; `[+45.0887, +69.9696]` Stage B) | `PASS` |
| `gate_08` | Removing promoted primitive removes transfer gain (`1.0000` vs `0.0000` without `PROPOSE_PRIMITIVE`, `0.1693` capsule-removed 4-lab control) | `PASS` |
| `gate_09` | No human-written cross-lab semantic mapping (`manually_supplied_cross_lab_mapping = false`, `handwritten_language_rules_used = false`, cross-lab success `1.0000`) | `PASS` |
| `gate_10` | Old-task retention `>= 98%` by real pre/post execution (`1.0000` -> `1.0000`, worst regression `0.0`) | `PASS` |
| `gate_11` | All discovery, evolution, sandbox, and validation costs included (`kernel_sha256_before == kernel_sha256_after`) | `PASS` |
| `gate_12` | At least 2 independent unknown-library families reproduce (`3/3` families reproduced) | `PASS` |

---

## 6. Compute Accounting & Independent Verification

- **Host Execution**: Dispatched via `scripts/run_seed_open_primitive_transfer.py` through `Sandbox.execute()` (`adapter = seed_open_primitive_transfer_v1`, `run_id = seed-open-primitive-transfer-1`, `execution_sha = 4bc6443e939287f80bac50cbdfa935e6b5bf0049`, `dirty = false`).
- **Kernel Counters Total**:
  - `candidate_executions = 2,809,305`
  - `dsl_instructions = 1,988,111`
  - `hidden_evaluations = 953,270`
  - `queries = 149,218`
  - `sandbox_actions = 5,007`
  - `primitive_calibrations = 288`
  - `proposal_validations = 187`
- **Wall / CPU / Session Budget**:
  - `wall_clock_s = 53.415096` (`cpu_time_s = 32.709724`)
  - `session_used_s = 2106.0471992059947` (`session_remaining_s = 1493.9528007940055`)
- **Reproduction & Verification Commands**:
  ```bash
  PYTHONPATH=src python3 scripts/verify_seed_open_primitive_transfer.py
  PYTHONPATH=src python3 scripts/verify_seed_integrated_architecture.py
  PYTHONPATH=src python3 -m pytest tests/test_seed_open_primitive_transfer.py tests/test_seed_integrated_architecture.py -v
  python3 scripts/check_repository.py
  ```
