# NEXUS Seed Combined Wake–Sleep–Dream–Evolution Architecture & Meta-Rule Evolution v1 Results (`seed_meta_rule_evolution_v1`)

## 1. Executive Summary & Permitted Conclusion

- **Pre-Run Commit (Frozen Code, Protocol & Config Before Execution)**: `322583377f03ccca702dda5478d158f57c1b0408`
- **Host Run ID**: `seed-meta-rule-evolution-1` (`seed_meta_rule_evolution_v1`)
- **Artifact SHA-256**: `818300f5100bccf5fcbb461b03aee86742b2173847bbd09d1f52dbd811ec8292` ([`artifacts/seed_meta_rule_evolution.json`](../artifacts/seed_meta_rule_evolution.json))
- **Independent Audit**: [`artifacts/seed_meta_rule_evolution_audit.json`](../artifacts/seed_meta_rule_evolution_audit.json) (`valid: true`)
- **Protocol**: [NEXUS_SEED_META_RULE_EVOLUTION_PROTOCOL.md](NEXUS_SEED_META_RULE_EVOLUTION_PROTOCOL.md) (`942df433bb34e30a3f7c516b68227a5ff9154f1fe763c35e652e1437a183cead`)
- **Config**: [`configs/seed_meta_rule_evolution.json`](../configs/seed_meta_rule_evolution.json) (`f7384e7336bac063e39d944bd2be3d14c29d55792a783c10e222c44fef7db0b4`)
- **Verdict**: **`PASS_META_RULE_EVOLUTION_V1` (9 / 9 Registered Gates Passed)**

> **Adversarial v1 Audit & Scientific Retraction Notice ([NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md](NEXUS_SEED_META_RULE_EVOLUTION_V1_AUDIT.md), [`artifacts/seed_meta_rule_evolution_v1_audit.json`](../artifacts/seed_meta_rule_evolution_v1_audit.json))**:
> **Meta-Rule Evolution v1 passed its internal synthetic contract but does not establish bounded learning-to-learn because evaluator-derived hypothesis labels, isomorphic grammar families, guided rule injection and non-executed protected assessments confound the result.**
> *(The original v1 artifact and reported numbers below are preserved unchanged as historical records.)*

> **Original v1 Conclusion (Superseded by Audit Above)**:
> *NEXUS evolved an executable learning procedure that acquired bounded hidden mechanisms more efficiently than its handwritten learner and transferred to independently generated grammar families. This is genuine evidence of bounded learning-to-learn; it does not establish AGI, unrestricted self-improvement, or general language intelligence.*

---

## 2. Six-Component Architecture Verification

| Architectural Component | Implementation & Verification | Status |
| :--- | :--- | :--- |
| **1. Immutable Trusted Kernel** | Typed 13-opcode DSL interpreter, hard resource caps (`10..30` instructions, $Q_{\max}=6$, $E_{\max}=64$), admissibility screen, SHA-256 evidence journal, rollback guard, and protected assessment sets (`kernel_sha256_before == kernel_sha256_after` across all 8 seeds) | **VERIFIED** |
| **2. Executable Learning-Rule DSL** | 13 opcodes (`OBSERVE`, `GENERATE_TYPED_HYPOTHESES`, `FILTER_INCONSISTENT`, `PREDICT_EFFECTS`, `RANK_BY_MDL`, `SELECT_QUERY_BY_INFORMATION_GAIN`, `RUN_EXPERIMENT`, `ACCEPT_IF_IDENTIFIED`, `CREATE_CAPSULE`, `MERGE_EQUIVALENT`, `DISCARD_HYPOTHESIS`, `RUN_VALIDATION`, `STOP`) and 7 mutation operators | **VERIFIED** |
| **3. Wake: Concept Capsules** | Zero stored whole-program fingerprints (`0`), zero manually supplied cross-lab mappings (`False`); constructs unseen length 4–5 compositions from learned primitive models, including `["even", "decrement", "reverse", "unique"]` (`filter-even -> decrement -> reverse -> unique`) bound to `"zorp"` | **VERIFIED** |
| **4. Dream: Adversarial Task Generator** | Screened `80` candidates across 8 seeds (`64` admissible, `16/16` inadmissible foils rejected by the 6-criterion kernel screen), ranking novel low-complexity tasks by $\operatorname{Regret}(T,R) = \operatorname{Score}(\text{ref}, T) - \operatorname{Score}(R, T)$ (`mean_selected_regret = 1.4284`, `archive_cycle_rate = 0.0`) | **VERIFIED** |
| **5. Evolution: Lexicographic + Pareto** | `32` learning rules $\times$ `20` generations $\times$ `8` seeds (`5,120` rule evaluations); separate **Episodic** (`5.2361` work units) and **Continual** (`4.9080` work units) evaluations; frozen (`frozen_evolved_rule_sha256`) before generating the sealed final family | **VERIFIED** |
| **6. Sleep: Stitch Compression & Distillation** | Replayed verified traces, retained counterexamples, discovered repeated contiguous subprograms via Stitch-like anti-unification (`mdl_before = 34.0 -> mdl_after = 32.0`, `mean_mdl_reduction = 2.0`), passed `100%` of old-capsule regression tests, and distilled choice policy with `neural_decides_truth = False` | **VERIFIED** |

---

## 3. Primary Results Across Four Independent Grammars (`8` Seeds)

| Learner Rule / Control | Task Success | Protected Old-Skill Retention | Episodic Experiments | Episodic Execution Cost | Continual Execution Cost | Rule Length (Instructions) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`evolved_meta_rule` (Frozen Evolved Learner)** | **`1.0000`** | **`1.0000`** | **`1.0000`** | **`5.2361`** | **`4.9080`** | **`10.0`** |
| `exact_information_gain_learner` (Handwritten Info-Gain) | `0.0000` (3 unmerged equivalents) | `0.0000` | `3.0000` | `69.8039` | `69.8039` | `11.0` |
| `handwritten_learner` (Handwritten Disagreement) | `0.0000` (3 unmerged equivalents) | `0.0000` | `3.0000` | `67.7016` | `67.7016` | `11.0` |
| `random_question_learner` | `0.0000` | `0.0000` | `4.0000` | `67.5973` | `67.5973` | `10.0` |
| `shortest_program_learner` | `0.0000` | `0.0000` | `1.0000` | `49.2004` | `49.2004` | `10.0` |
| `minimal_noop_learner` | `0.0000` | `0.0000` | `1.0000` | `1.2500` | `1.2500` | `10.0` |
| `random_evolution_control` | `1.0000` (threshold=2) | `0.0000` (unsafe threshold) | `4.0000` | `68.2535` | `68.2535` | `10.0` |
| `rule_size_only_control` | `0.2500` | `0.0000` | `1.0000` | `48.2504` | `48.2504` | `10.0` |
| `remove_evolved_rule_ablation` | `0.0000` | `0.0000` | `3.0000` | `69.8039` | `69.8039` | `11.0` |

### Per-Grammar Breakdown (`evolved_meta_rule` vs. `exact_information_gain_learner`)

| Independent Grammar Family | Role | Evolved Rule Experiments | Handwritten Info-Gain Experiments | Evolved Rule Execution Cost | Handwritten Info-Gain Execution Cost | Paired Difference (`InfoGain - Evolved`, 95% CI, $df=7$) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `list_transformations` | Source Family 1 | **`1.0000`** | `3.0000` | **`5.2359`** | `69.8484` | **`+64.6125`** |
| `boolean_mechanisms` | Source Family 2 | **`1.0000`** | `3.0000` | **`5.2422`** | `69.7094` | **`+64.4672`** |
| `relational_graphs` | Development Transfer | **`1.0000`** | `3.0000` | **`5.2383`** | `69.9641` | **`+64.7258`** |
| `sealed_action_state_transitions` | **Sealed Final Family** (new sensor `thermal_flux`, action `calibrate_shield`, hidden `latent_drift_polarity`) | **`1.0000`** | `3.0000` | **`5.2281`** | `69.6938` | **`+64.4656` `[+63.8448, +65.0864]`** |
| **Overall Across All 4 Grammars** | All Families | **`1.0000`** (`66.67%` reduction) | `3.0000` | **`5.2361`** (`92.50%` reduction) | `69.8039` | **`+64.5678` `[+64.3495, +64.7860]`** |

---

## 4. Nine Registered Pass Gates Summary

| Gate | Requirement | Measured Value | Status |
| :--- | :--- | :--- | :---: |
| **Gate 1** | Beats handwritten exact-info-gain learner on sealed family (`ci95_low > 0`) | `+64.4656` cost reduction (`CI [+63.8448, +65.0864]`), `+2.0` experiment reduction | **PASS** |
| **Gate 2** | Requires fewer experiments ($\ge 25\%$) and less compute ($\ge 25\%$), with continual $<$ episodic cost | `66.67%` fewer experiments, `92.50%` less compute; continual `4.9080 < 5.2361` episodic | **PASS** |
| **Gate 3** | Retains $\ge 98\%$ of protected old skills and passes 100% of Sleep capsule regression tests | `100.0%` (`1.0000`) protected old-skill retention; `100.0%` (`8/8`) Sleep capsule test pass rate | **PASS** |
| **Gate 4** | Wins on more than one independent grammar (`4/4` required) | Won on **`4 / 4`** independent grammars (`list_transformations`, `boolean_mechanisms`, `relational_graphs`, `sealed_action_state_transitions`) | **PASS** |
| **Gate 5** | Target compositions not stored; `"zorp"` constructs `filter-even -> decrement -> reverse -> unique` from primitives | `stored_whole_program_fingerprints = 0`; `"zorp"` $\to$ `["even", "decrement", "reverse", "unique"]` verified across all 8 seeds | **PASS** |
| **Gate 6** | Removing the evolved rule removes the advantage | Ablation increases experiments `1.0000 -> 3.0000` and execution cost `5.2361 -> 69.8039` | **PASS** |
| **Gate 7** | Random evolution and rule-size-only controls do not match it | `random_evolution_control` (`68.2535` cost, `0.0` retention) and `rule_size_only_control` (`0.2500` accuracy, `0.0` retention) both fail | **PASS** |
| **Gate 8** | Improvement survives all 8 independent seeds (`1751000001..1751000008`) | **`8 / 8` seeds improved**, overall cost `CI [+64.3495, +64.7860]` | **PASS** |
| **Gate 9** | All construction and evolutionary compute reported; immutable kernel intact | `5,120` evolution rule evaluations, `24` primitive calibrations/seed, `4.9695s` wall, `4.8459s` CPU, `6s` debit (`2052.6321s` used / `1547.3679s` remaining) | **PASS** |
