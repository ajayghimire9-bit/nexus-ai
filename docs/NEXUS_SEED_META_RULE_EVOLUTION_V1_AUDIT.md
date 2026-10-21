# NEXUS Seed — Adversarial Saved-Data and Code Audit of Meta-Rule Evolution v1

- **Schema**: `seed_meta_rule_evolution_v1_adversarial_audit_v1`
- **Audited Code**: [src/nexus/seed/meta_rule_evolution.py](../src/nexus/seed/meta_rule_evolution.py) (`SHA-256: 9878e58f5657d80a7e071cd98a106f136165386617adba58c057351842079a83`)
- **Audited Artifact (Preserved Unchanged)**: [artifacts/seed_meta_rule_evolution.json](../artifacts/seed_meta_rule_evolution.json) (`SHA-256: 818300f5100bccf5fcbb461b03aee86742b2173847bbd09d1f52dbd811ec8292`)
- **Machine-Readable Audit Output**: [artifacts/seed_meta_rule_evolution_v1_audit.json](../artifacts/seed_meta_rule_evolution_v1_audit.json)
- **Audit Implementation**: [src/nexus/seed/meta_rule_evolution_v1_audit.py](../src/nexus/seed/meta_rule_evolution_v1_audit.py)

---

## 1. Executive Conclusion

> **Meta-Rule Evolution v1 passed its internal synthetic contract but does not establish bounded learning-to-learn because evaluator-derived hypothesis labels, isomorphic grammar families, guided rule injection and non-executed protected assessments confound the result.**

The original v1 artifact (`artifacts/seed_meta_rule_evolution.json`), verifier output (`artifacts/seed_meta_rule_evolution_audit.json`), and reported numbers in [NEXUS_SEED_META_RULE_EVOLUTION_RESULTS.md](NEXUS_SEED_META_RULE_EVOLUTION_RESULTS.md) are preserved unchanged as historical records.

---

## 2. All 15 Audited Confounds & Leakage Paths (`15/15` Confirmed)

| # | Audited Mechanism / Leakage Path | Confirmed | Code Location | Technical Evidence |
| :-: | :--- | :-: | :--- | :--- |
| **1** | `hypothesis_profiles` exposes `exact_consistent` | `True` | `meta_rule_evolution.py:766-776` | Every entry in `task["hypothesis_profiles"]` includes precomputed `exact_consistent = (h_pred_eff == true_eff)` before the learning rule runs. |
| **2** | `hypothesis_profiles` exposes `coarse_consistent` | `True` | `meta_rule_evolution.py:765-775` | Every entry in `task["hypothesis_profiles"]` includes precomputed `coarse_consistent`. |
| **3** | `hypothesis_profiles` exposes `effect_distance` and `state_key` | `True` | `meta_rule_evolution.py:758-777` | Every entry in `task["hypothesis_profiles"]` exposes precomputed `effect_distance` and `state_key`. |
| **4** | `execute_learning_rule` receives `target_ops` | `True` | `meta_rule_evolution.py:785` | The `task` dictionary passed directly into `execute_learning_rule` contains `"target_ops": list(target_ops)`. |
| **5** | `execute_learning_rule` receives `true_effect_state` | `True` | `meta_rule_evolution.py:789` | The `task` dictionary passed directly into `execute_learning_rule` contains `"true_effect_state": true_eff`. |
| **6** | `macro_discount` reads `target_ops` | `True` | `meta_rule_evolution.py:926-933` | `execute_learning_rule` checks `if task["target_ops"][i : i + len(sub)] == sub:` to grant `macro_discount = 1.25`. |
| **7** | `heldout_accuracy` is assigned from `exact_consistent` rather than executed protected examples | `True` | `meta_rule_evolution.py:1137-1142` | `heldout_accuracy` is assigned `1.0` if `accepted["exact_consistent"]` else `0.25` if `accepted["coarse_consistent"]`; replacing `protected_assessment` outputs with impossible values leaves `task_success == 1.0`. |
| **8** | `protected_assessment` outputs are present in the learner-facing object | `True` | `meta_rule_evolution.py:792` | `task["protected_assessment"]` (containing ground-truth `"output"` values) is attached directly to the learner-facing `task` dictionary. |
| **9** | Structured winning rule is manually injected into `build_initial_population()` | `True` | `meta_rule_evolution.py:1376-1395` | `if idx == 0:` overwrites the first mutated starter with the 13-instruction compositional candidate (`PREDICT_EFFECTS`, `MERGE_EQUIVALENT`, `tie_breaker="effect_distance"`). |
| **10** | Guided winning rule is manually injected in every generation | `True` | `meta_rule_evolution.py:1813-1834` | `if child_idx == 0:` in `run_single_seed_evolution` overwrites the first child of every generation with the 14-instruction guided winner. |
| **11** | `random_evolution_control` is overwritten after its evolution | `True` | `meta_rule_evolution.py:1855-1871` | After the 20-generation random selection loop finishes, `random_control_rule["instructions"]`, `query_strategy`, `tie_breaker`, and `stopping_threshold` are manually overwritten. |
| **12** | Four grammars are isomorphic renamings of the same five behavioral transformations | `True` | `meta_rule_evolution.py:210-370` | `list_transformations`, `boolean_mechanisms`, `relational_graphs`, and `sealed_action_state_transitions` all encode `_base_structured_ints` and apply identical operator index sequences over `reverse/sort/unique/+1/-1/even`. |
| **13** | Dream tasks do not influence the evolution loop | `True` | `meta_rule_evolution.py:1565, 2020` | `run_dream_adversarial_phase` is only invoked at line 2020 after the 20-generation loop and after `frozen_evolved_rule` is frozen, and includes `seed` in `sem_sha`. |
| **14** | Sleep validation reads stored `passed` booleans instead of rerunning tests | `True` | `meta_rule_evolution.py:1681-1684` | `run_sleep_compression_and_distillation` reads `if t_item.get("passed", False):` without executing the capsule program on test inputs. |
| **15** | `DistilledChoicePolicy` is a stub rather than a fitted policy | `True` | `meta_rule_evolution.py:1687-1704` | `distilled_policy` sets `top1_choice_agreement = 1.0 if len(capsules) > 0 else 0.0` without fitting a model or evaluating held-out traces. |

---

## 3. Required Repairs Implemented in Stage A (Meta-Rule Evolution v2) & Stage B (Open Primitive Code Transfer v1)

1. **Non-Overlapping `LearnerTaskView` and `EvaluatorTaskPrivate` Structures**:
   - `LearnerTaskView` contains only `task_id`, `public_type_signatures`, `public_primitive_handles`, `currently_observed_examples`, `query_action_budget`, `allowed_typed_actions`, and `public_resource_costs`.
   - Recursive leakage checks (`assert_zero_evaluator_leakage`) verify that no learner-visible object contains `target_ops`, `true_effect_state`, `exact_consistent`, `coarse_consistent`, `evaluator_labels`, `hidden_outputs`, `protected_outcomes`, or `semantic_class_ids`.
2. **Real Hypothesis Execution & Protected Assessment Execution**:
   - Candidate programs are executed on observed and queried inputs via a counted kernel API; protected accuracy is computed by executing the accepted program on private protected inputs inside `EvaluatorTaskPrivate`.
   - Any semantically equivalent program that passes hidden execution tests is accepted.
3. **Uniform Mutation & Zero Guided Rule Injection**:
   - No hand-authored compositional winner in `build_initial_population()`, no per-generation `child_idx == 0` overwrite, no opcode mutation bias, and no post-loop overwrite of `random_evolutionary_selection`.
4. **Non-Isomorphic Families, In-Loop Dream Curriculum, Real Sleep & Retention, and Stage B `PROPOSE_PRIMITIVE` Code Transfer**:
   - Implemented in [src/nexus/seed/open_primitive_transfer.py](../src/nexus/seed/open_primitive_transfer.py) and preregistered in [NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md](NEXUS_SEED_OPEN_PRIMITIVE_TRANSFER_PROTOCOL.md).
