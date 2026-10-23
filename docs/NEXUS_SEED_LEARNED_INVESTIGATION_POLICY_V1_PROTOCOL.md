# NEXUS Seed — Combined Dual-Engine & Learned Investigation Policy Protocol (`seed-learned-investigation-policy-v1`)

## 1. Purpose & Hypothesis

This protocol pre-registers the evaluation of NEXUS's combined dual-engine architecture (`src/nexus/seed/combined_investigation_engine.py`):
1. **Skill Reuse Engine (`CapsuleExecutor` + `Consolidator`)**: Retrieves, binds, checks, monitors, and executes acquired procedures across a three-tier reuse pipeline (exact match, structural/schema rebinding, and E-graph equivalence canonicalization).
2. **Learned Investigation Engine (`LearnedInvestigationPolicy` + `MechanismBActiveEnvironment` + `CurriculumGenerator`)**: Improves how NEXUS acquires the next skill by learning task-conditioned grammar priors and a bounded executable investigation policy controlling `RETRIEVE`, `ENUMERATE`, `CONSTRUCT_PROBE`, `REQUEST_ANSWER`, `TEST`, and `STOP`.

Rather than asserting invented numbers ("70% less search", "95% coverage", "under 80 ms", "1.5B acts like 30B"), every mechanism is measured against explicit baselines and ablations under the cost-aware objective:
$$J(\phi) = \mathbb{E}_{\tau}\!\left[\operatorname{Loss}_{\mathrm{assessment}}\!\left(\operatorname{Learn}_{\phi}(D_{\mathrm{support}})\right) + \lambda_q N_{\mathrm{questions}} + \lambda_e N_{\mathrm{executions}} + \lambda_t T\right]$$
with $\lambda_q = 0.08$, $\lambda_e = 0.02$, and $\lambda_t = 0.10$, and outer training costs (`outer_training_wall_s`, `outer_training_executions`, `outer_training_questions`) reported explicitly.

---

## 2. Three Separately Resettable Knowledge Stores

To ensure improvements are causally attributable, NEXUS maintains three orthogonal, separately resettable stores (`SeparatelyResettableKnowledgeState`):
- **`skills` (`CapsuleSkillStore`)**: Programs/capsules NEXUS has acquired (`reset_skills()`).
- **`learning_strategy` (`InvestigationStrategyStore`)**: Priors and investigation rules $\phi$ that determine how NEXUS investigates (`reset_learning_strategy()`).
- **`language_knowledge` (`LanguageKnowledgeStore`)**: Neural proposer weights and conformal calibration quantiles (`reset_language_knowledge()`).

---

## 3. Experimental Design (4 Benchmarks Run Separately)

### Experiment 1: Outer Training & Curriculum Generation vs Ordinary Random Sampling (Mechanism C)
- Train $\phi$ under a fixed budget of `8` training tasks drawn from the 32-task source pool (`build_training_and_excluded_tasks()`) using:
  1. `curriculum` (`CurriculumGenerator`: selects tasks by version-space ambiguity and novel operator coverage, charging for generator probe executions and overhead).
  2. `random_sampling` (ordinary random task sampling with zero generator probe overhead).
- Record and report all outer training costs (`outer_training_wall_s`, `outer_training_executions`, `outer_training_questions`, `outer_training_objective_debit`).

### Experiment 2: The Decisive Memory-Reset Learning-to-Learn Milestone (24 Excluded Unfamiliar Tasks, Capsules Cleared)
- Clear all acquired capsules (`skills.clear()`, verified by `active_capsules == 0`) and freeze the learner before evaluating on **24 excluded unfamiliar tasks** (16 unseen 3-step sequence/record compositions + 8 practical repository maintenance tasks where multiple candidate patches satisfy initial public symptom tests).
- Compare 7 configurations on the exact same 24 excluded tasks:
  1. `original_untrained_policy` ($\phi_0$: default catalogue order, no learned strategy).
  2. `simple_frequency_prior` (marginal operator frequency prior).
  3. `strong_fixed_infogain` (handwritten entropy-maximizing active questioning over unlearned lexical priors).
  4. `learned_grammar_prior_only` (Mechanism A1: task-conditioned grammar prior without active oracle questioning).
  5. `learned_investigation_policy_random_curr` (Mechanism A1+A2 trained via ordinary random sampling, capsules cleared).
  6. `learned_investigation_policy_curriculum` (Mechanism A1+A2 trained via `CurriculumGenerator`, capsules cleared).
  7. `strategy_reset_ablation` (capsules cleared AND learned strategy reset $\phi \to \phi_0$: verifies that resetting the learned policy eliminates the advantage).

### Experiment 3: Three-Tier Skill Reuse vs Learned Strategy vs Combined Dual-Engine
- Evaluate across the 24 tasks when `CapsuleSkillStore` is seeded with 8 verified source capsules (supporting Tier 1 exact, Tier 2 rebound, and Tier 3 E-graph canonical matches):
  1. `skills_only_untrained_policy` (capsules retained, untrained investigation strategy $\phi_0$).
  2. `strategy_only_capsules_cleared` (capsules cleared, learned investigation strategy $\phi^*$).
  3. `combined_dual_engine_skills_plus_strategy` (both capsules and learned investigation strategy $\phi^*$ retained).

### Experiment 4: Five Explicit Engineering Replacements
1. `ConformalCandidateCalibrator`: Measure empirical top-5 coverage vs split-conformal calibrated coverage at $1 - \alpha = 0.95$.
2. `BoundedEGraphOrganizer`: Organize equivalence classes under sound rewrite rules and detect unsound rules via behavioral probes.
3. `BoundedContractCounterexampleSearcher`: Search for postcondition counterexamples within explicit evaluation and timeout bounds.
4. `AttributedClaimStore`: Store extracted triples with source attribution, scope, validity dates, and contradiction detection.
5. `VersionedCompiledArtifactMonitor`: Compile, version, monitor, and invalidate procedures when schema/environment assumptions change.
