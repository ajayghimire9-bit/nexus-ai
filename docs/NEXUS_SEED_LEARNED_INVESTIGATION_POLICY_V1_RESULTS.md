# NEXUS Seed — Combined Dual-Engine & Learned Investigation Policy Results (`seed-learned-investigation-policy-v1`)

## 1. Executive Summary

Executed from clean pre-registered revision `e3a8b8e` on `codex/seed-symbiotic-workbench-v1` ([Protocol](NEXUS_SEED_LEARNED_INVESTIGATION_POLICY_V1_PROTOCOL.md), [Config](../configs/seed_learned_investigation_policy_v1.json)), this study implements and benchmarks the 7-component combined NEXUS architecture (`src/nexus/seed/combined_investigation_engine.py`):
1. **`CapsuleExecutor`**: Three-tier reuse pipeline (Tier 1 exact signature match, Tier 2 schema/parameter rebinding, Tier 3 E-graph canonical equivalence match) with versioned assumption monitoring (`VersionedCompiledArtifactMonitor`).
2. **`LocalNeuralProposer`**: Translates natural-language requests into operator/edit hypotheses with empirical coverage measurement and split-conformal calibration (`ConformalCandidateCalibrator`).
3. **`LearnedInvestigationPolicy` (Mechanism A)**: Task-conditioned grammar priors and bounded executable investigation controller (`RETRIEVE`, `ENUMERATE`, `CONSTRUCT_PROBE`, `REQUEST_ANSWER`, `TEST`, `STOP`) optimized and evaluated under the explicit cost-aware objective:
   $$J(\phi) = \mathbb{E}_{\tau}\!\left[\operatorname{Loss}_{\mathrm{assessment}}\!\left(\operatorname{Learn}_{\phi}(D_{\mathrm{support}})\right) + \lambda_q N_{\mathrm{questions}} + \lambda_e N_{\mathrm{executions}} + \lambda_t T\right]$$
   with $\lambda_q = 0.08$, $\lambda_e = 0.02$, and $\lambda_t = 0.10$.
4. **`EvidenceKernel`**: Executes candidate hypotheses, checks outcomes, records provenance, searches for bounded contract counterexamples (`BoundedContractCounterexampleSearcher`), and stores attributed claims (`AttributedClaimStore`). The learner cannot rewrite its success criteria.
5. **`Consolidator`**: Canonicalizes verified solutions via `BoundedEGraphOrganizer`, registers versioned capsules, and retires invalidated procedures.
6. **`CurriculumGenerator` (Mechanism C)**: Selects high-ambiguity, operator-diverse training tasks within an explicit budget, benchmarked head-to-head against ordinary random task sampling (`random_sampling`).
7. **`IndependentEvaluator`**: Evaluates frozen learners on **24 excluded unfamiliar assessment tasks** (16 unseen 3-step sequence/record compositions + 8 practical repository maintenance tasks) using `MechanismBActiveEnvironment` as the metered answer source.

---

## 2. Three Separately Resettable Knowledge Stores

`SeparatelyResettableKnowledgeState` isolates:
- **`skills` (`CapsuleSkillStore`)**: `reset_skills()` clears acquired procedures without touching $\phi$ or language parameters.
- **`learning_strategy` (`InvestigationStrategyStore`)**: `reset_learning_strategy()` resets $\phi \to \phi_0$ without touching acquired capsules or language parameters.
- **`language_knowledge` (`LanguageKnowledgeStore`)**: `reset_language_knowledge()` resets proposer weights and conformal quantiles to pretrained defaults.

Independent reset verification (`reset_attribution_verification.exact_match_after_independent_resets`) passed (`true`).

---

## 3. Outer Training & Curriculum Comparison (Mechanism C)

| Outer Training Mode | Budget Tasks | Covered Operators | Generator Probe Executions | Total Outer Executions | Outer Oracle Questions | Outer Training Wall (s) | Outer Objective Debit |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `curriculum` (`CurriculumGenerator`) | 8 | 12 / 12 | 256 | 372 | 16 | 0.002007 | 8.720201 |
| `random_sampling` | 8 | 5 / 12 | 0 | 144 | 4 | 0.000358 | 3.200036 |

---

## 4. Experiment 2: The Decisive Memory-Reset Learning-to-Learn Milestone (`skills.clear()`)

All 24 excluded unfamiliar tasks (16 compositional sequence tasks + 8 repository repair tasks) were evaluated with **acquired capsules completely cleared** (`active_capsules == 0`, `skills_hash = 44136fa3...`):

| Policy Configuration (Capsules Cleared) | Solved (`24` Tasks) | Seq Solved (`16`) | Repo Solved (`8`) | Mean Assessment Loss | Total Questions ($N_q$) | Total Executions ($N_e$) | Mean Executions | Mean Objective $J(\phi)$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `original_untrained_policy` ($\phi_0$) | **0 / 24** | 0 / 16 | 0 / 8 | 0.781250 | 0 | 321 | 13.3750 | 1.048752 |
| `simple_frequency_prior` | **2 / 24** | 2 / 16 | 0 / 8 | 0.708333 | 0 | 321 | 13.3750 | 0.975836 |
| `learned_grammar_prior_only` (Mechanism A1) | **9 / 24** | 4 / 16 | 5 / 8 | 0.531250 | 0 | 267 | 11.1250 | 0.753757 |
| `strong_fixed_infogain` | **24 / 24** | 16 / 16 | 8 / 8 | 0.000000 | 27 | 407 | 16.9583 | 0.429176 |
| `learned_investigation_policy_random_curr` | **24 / 24** | 16 / 16 | 8 / 8 | 0.000000 | 27 | 357 | 14.8750 | 0.387513 |
| **`learned_investigation_policy_curriculum`** | **24 / 24** | **16 / 16** | **8 / 8** | **0.000000** | **27** | **350** | **14.5833** | **0.381680** |
| `strategy_reset_ablation` ($\phi \to \phi_0$) | **0 / 24** | 0 / 16 | 0 / 8 | 0.781250 | 0 | 321 | 13.3750 | 1.048752 |

Key findings:
1. **Bounded Learning-to-Learn with Capsules Cleared**: With zero stored skill capsules, `learned_investigation_policy_curriculum` solved **24 / 24** unfamiliar tasks (`0.0` assessment loss) at **`14.5833` mean executions** and **`J(\phi) = 0.381680`**, outperforming `original_untrained_policy` (`0/24`, $J = 1.048752$), `simple_frequency_prior` (`2/24`, $J = 0.975836$), `learned_grammar_prior_only` (`9/24`, $J = 0.753757$), `strong_fixed_infogain` (`24/24`, `16.9583` mean executions, $J = 0.429176$), and `learned_investigation_policy_random_curr` (`24/24`, `14.8750` mean executions, $J = 0.387513$).
2. **Causal Attribution via Strategy Reset Ablation**: Resetting the learned strategy (`strategy_reset_ablation`, restoring `learning_strategy_hash = c313d15c...`) immediately eliminated the gain (`24/24` $\to$ `0/24`, $J(\phi): 0.381680 \to 1.048752$), proving the improvement resides in `InvestigationStrategyStore` ($\phi$).

---

## 5. Experiment 3: Three-Tier Skill Reuse vs Learned Strategy vs Combined Dual-Engine

| Dual-Engine Configuration | Capsules Retained | Strategy Retained | Solved (`24` Tasks) | Capsule Reuses | Total Questions ($N_q$) | Total Executions ($N_e$) | Mean Executions | Mean Objective $J(\phi)$ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `skills_only_untrained_policy` | Yes (`8`) | No ($\phi_0$) | 8 / 24 | 8 | 0 | 208 | 8.6667 | 0.631690 |
| `strategy_only_capsules_cleared` | No (`0`) | Yes ($\phi^*$) | 24 / 24 | 0 | 27 | 350 | 14.5833 | 0.381680 |
| **`combined_dual_engine_skills_plus_strategy`** | **Yes (`8`)** | **Yes ($\phi^*$)** | **24 / 24** | **8** | **19** | **230** | **9.5833** | **0.255030** |

Combining both engines (`combined_dual_engine_skills_plus_strategy`) solved **24 / 24** tasks while reducing candidate executions by **34.29%** (`230` vs `350`), active oracle questions by **29.63%** (`19` vs `27`), and total objective cost $J(\phi)$ by **33.18%** (`0.255030` vs `0.381680`) compared to `strategy_only_capsules_cleared`.

---

## 6. Experiment 4: Five Explicit Engineering Replacements

1. **`ConformalCandidateCalibrator`**: Empirical top-5 candidate coverage was **`0.70`** (`top5_guarantees_95_percent = False`). Split-conformal calibration ($\alpha = 0.05$, $\hat{q}_{0.95} = 0.95$) achieved **`1.00`** empirical coverage (`mean_conformal_set_size = 7.0`).
2. **`BoundedEGraphOrganizer`**: Saturated `("reverse", "reverse", "sort_asc", "sort_asc")` into a 4-member equivalence class with canonical representative `["sort_asc"]`, verified `idempotent_sort` on probes (`universal_proof_claimed = False`), and rejected `unsound_abs_to_clamp` with explicit counterexample `[-3, 1, 2, 2]`.
3. **`BoundedContractCounterexampleSearcher`**: Found boundary counterexample `input = 100, output = 105.0` on `buggy_discount_fn` in 4 evaluations (`0.000018 s`, `universal_verification_claimed = False`).
4. **`AttributedClaimStore`**: Stored scoped claims from `service_docs_v2` (`120`, valid `2025-01-01..2025-12-31`) and `release_notes_v3` (`300`, valid `2025-06-01..`), flagging `2025-09-01` as `contradictory_attributed_claims` (`verified_fact = False`) and resolving `2026-03-01` cleanly after `v2` expiry.
5. **`VersionedCompiledArtifactMonitor`**: Executed `cap_monitored_v1` under valid assumptions `{"version": 1, "currency": "USD"}` and automatically invalidated it (`invalidated_on_assumption_change`) when assumptions changed to `{"version": 2, "currency": "EUR"}`.

---

## 7. Independent Verification & Resource Accounting

- **Independent Verifier (`scripts/verify_seed_learned_investigation_policy.py`)**: Re-executed all 240 episodes against private task oracles, checked $J(\phi)$ arithmetic, verified capsule-cleared invariants, and passed the tamper self-test (`valid: true`, `mismatches: []`, `tamper_self_test_passed: true`).
- **Resource Usage & Ledger**:
  - Total benchmark wall time (including outer training): `0.072965 s` (`1.0 s` debit against the standing Seed compute budget)
  - Total CPU time: `0.039112 s`
  - Peak RSS: `30.031 MB`
  - Updated standing ledger: `2206.632103455996 s` used / `1393.367896544004 s` remaining.
- **Claim Discipline**: Establishes bounded learning-to-learn within the evaluated sequence/record grammar and repository-repair families (with capsules cleared and strategy-reset ablation verified), plus complementary gains from the three-tier reuse pipeline. Does **not** establish unrestricted general learning-to-learn or AGI (`agi = false`).
