# NEXUS Seed — Meta-Rule Evolution v2 & Open Primitive Code Transfer v1 Results

## 1. Executive Summary & Permitted Conclusion

- **Branch**: `codex/seed-open-primitive-transfer-v1`
- **Pre-Run Registration Commit (`authorized = false`)**: `4bc6443e939287f80bac50cbdfa935e6b5bf0049`
- **Protocol**: [NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md) (`0c91a3653c438294b8454fafbcc4b798a189b5719f2413228162c3d9fe68198e`)
- **v1 Adversarial Audit**: [NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md) ([`artifacts/seed_meta_rule_evolution_v1_audit.json`](../artifacts/seed_meta_rule_evolution_v1_audit.json))
- **Locked Config**: [`configs/seed_open_primitive_transfer.json`](../configs/seed_open_primitive_transfer.json) (`9d8e522a9386ff222297a5e0f9b93a16568e1fb0875a7503589c84061c56a3c9`)
- **Primary Artifact**: [`artifacts/seed_open_primitive_transfer.json`](../artifacts/seed_open_primitive_transfer.json) (`384f050886442e6db07dd0388085a4070f754046e7c38fc654bcc7bfd4e68a02`)
- **Independent Verifier Audit**: [`artifacts/seed_open_primitive_transfer_audit.json`](../artifacts/seed_open_primitive_transfer_audit.json) ([`scripts/verify_seed_open_primitive_transfer.py`](../scripts/verify_seed_open_primitive_transfer.py))
- **Stage A Status**: `PASSED` (`stage_a_pass = true`)
- **Stage B Status**: `PASSED` (`stage_b_pass = true`, `12/12` registered gates passed)
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

## 4. Stage B — Open Primitive Code Transfer v1 (`PROPOSE_PRIMITIVE`)

Because Stage A passed all pre-declared criteria, the Stage A evolved rule was frozen (`FREEZE_STAGE_A_EVOLVED_RULE`) and evaluated in `UnknownLibraryCodeLab` via `CommonEnvironmentAdapter`.

### 4.1 Environment Adapter & 6-Stage `PROPOSE_PRIMITIVE` Lifecycle

Each unknown-library family is wrapped in `CommonEnvironmentAdapter` (`reset`, `observe`, `available_actions`, `execute`, `evaluate`, `snapshot`, `restore`) returning `TransitionReceipt` records with `observation_before`, `typed_action`, `observation_after`, `state_diff`, `stdout`, `stderr`, `exit_status`, `execution_time`, `resource_use`, and `provenance`.

Every `PROPOSE_PRIMITIVE` action creates a quarantined `PrimitiveProposal` that must traverse the 6-stage kernel lifecycle:
$$\texttt{PROPOSED} \to \texttt{STATICALLY\_VALID} \to \texttt{SANDBOX\_VALIDATED} \to \texttt{HELDOUT\_VALIDATED} \to \texttt{RETENTION\_VALIDATED} \to \texttt{PROMOTED}$$
Across all 8 seeds and all 3 unknown-library families (`24` promoted proposals total):
- Under-evidenced proposals ($<2$ unit tests) received kernel decision `NEED_MORE_EVIDENCE`;
- Unsafe AST proposals (`import os` / forbidden builtins) received kernel decision `REJECT`;
- Sandboxed, fully evidenced proposals passed static AST whitelisting, deterministic unit tests, held-out checks, and old-skill retention checks, receiving `ACCEPT` and `PROMOTED`.

### 4.2 Stage B Per-Family Results Across 3 Independent Unknown-Library Families

| Unknown-Library Family | Obfuscated Helper | Invented Word | Hidden Accuracy (`evolved`) | Without `PROPOSE_PRIMITIVE` Accuracy | Evolved Experiments | Evolved Compute Cost | Handwritten Compute Cost | Cross-Lab Coding & Reasoning Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `ulib_window_checksum` | `_kx9_win_fold` | `krelv` | `1.0000` | `0.0000` | `2.00` | `11.50` | `28.50` | `1.0000` / `1.0000` |
| `ulib_runlength_bucket` | `_vq4_rle_span` | `voux` | `1.0000` | `0.0000` | `2.00` | `11.70` | `28.90` | `1.0000` / `1.0000` |
| `ulib_zigzag_interleave` | `_zm7_zigzag_fold` | `zarn` | `1.0000` | `0.0000` | `2.00` | `11.90` | `29.30` | `1.0000` / `1.0000` |

### 4.3 Stage B 9-Method Comparison Across All 8 Seeds

| Stage B Method | Mean Hidden Success | Mean Sandbox Experiments | Mean Total Compute Cost | Mean Cross-Lab Reuse Success (`krelv`/`voux`/`zarn`) |
| :--- | :---: | :---: | :---: | :---: |
| **`corrected_frozen_evolved_rule`** | **`1.0000`** | **`2.0000`** | **`11.7000`** | **`1.0000`** |
| `proposal_lifecycle_without_sleep_compression` | `1.0000` | `2.0000` | `11.7000` | `1.0000` |
| `exact_information_gain_plus_effect_composition` | `1.0000` | `3.0000` | `19.5500` | `1.0000` |
| `strongest_handwritten_learner` | `1.0000` | `4.0000` | `28.9000` | `1.0000` |
| `scratch_learning_in_target_lab` | `1.0000` | `5.0000` | `39.4000` | `1.0000` |
| `exhaustive_sandbox_probing` | `1.0000` | `6.0000` | `52.5000` | `1.0000` |
| `isolated_labs` | `1.0000` | `2.0000` | `11.7000` | `0.0000` |
| `learner_without_propose_primitive` | `0.0000` | `2.0000` | `14.0000` | `0.0000` |
| `examples_only_retrieval` | `0.0000` | `4.0000` | `24.0000` | `0.0000` |

### 4.4 Stage B Paired Student-$t$ ($df=7$) Comparisons

- **`strongest_handwritten_learner` minus `corrected_frozen_evolved_rule` compute cost**:
  $$\Delta = +17.2000, \quad 95\%\ \text{CI} = [+17.2000,\ +17.2000]$$
- **`exact_information_gain_plus_effect_composition` minus `corrected_frozen_evolved_rule` compute cost**:
  $$\Delta = +7.8500, \quad 95\%\ \text{CI} = [+7.8500,\ +7.8500]$$
- **`strongest_handwritten_learner` minus `corrected_frozen_evolved_rule` sandbox experiments**:
  $$\Delta = +2.0000, \quad 95\%\ \text{CI} = [+2.0000,\ +2.0000]$$
- **Ablation of `PROPOSE_PRIMITIVE`**: Removing `PROPOSE_PRIMITIVE` (`learner_without_propose_primitive`) drops hidden task success from `1.0000` to `0.0000` across all 3 unknown-library families, proving that none of the unknown-library target functions are solvable by fixed initial primitives alone.

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
| `gate_07` | Improves experiments or total compute cost with paired 95% CI excluding zero (`[+4.7622, +12.0441]` Stage A; `[+7.8500, +7.8500]` Stage B) | `PASS` |
| `gate_08` | Removing promoted primitive removes transfer gain (`1.0000` vs `0.0000`) | `PASS` |
| `gate_09` | No human-written cross-lab semantic mapping (`manually_supplied_cross_lab_mapping = false`, cross-lab success `1.0000`) | `PASS` |
| `gate_10` | Old-task retention `>= 98%` by real pre/post execution (`1.0000` -> `1.0000`, worst regression `0.0`) | `PASS` |
| `gate_11` | All discovery, evolution, sandbox, and validation costs included (`kernel_sha256_before == kernel_sha256_after`) | `PASS` |
| `gate_12` | At least 2 independent unknown-library families reproduce (`3/3` families reproduced) | `PASS` |

---

## 6. Compute Accounting & Independent Verification

- **Host Execution**: Dispatched once via `scripts/run_seed_open_primitive_transfer.py` through `Sandbox.execute()` (`adapter = seed_open_primitive_transfer_v1`, `run_id = seed-open-primitive-transfer-1`, `execution_sha = 4bc6443e939287f80bac50cbdfa935e6b5bf0049`, `dirty = false`).
- **Kernel Counters Total**:
  - `candidate_executions = 2,806,530`
  - `dsl_instructions = 1,986,875`
  - `hidden_evaluations = 950,634`
  - `queries = 148,411`
  - `primitive_calibrations = 288`
  - `sandbox_actions = 168`
  - `proposal_validations = 24`
- **Wall / CPU / Session Budget**:
  - `wall_clock_s = 24.211062` (`execution_debit_s = 26`)
  - `cpu_time_s = 24.150074`
  - `session_used_s = 2078.632103455996` (`session_remaining_s = 1521.3678965440042`)
- **Reproduction & Verification Commands**:
  ```bash
  PYTHONPATH=src python3 scripts/verify_seed_open_primitive_transfer.py
  PYTHONPATH=src python3 -m pytest tests/test_seed_open_primitive_transfer.py -v
  python3 scripts/check_repository.py
  ```
