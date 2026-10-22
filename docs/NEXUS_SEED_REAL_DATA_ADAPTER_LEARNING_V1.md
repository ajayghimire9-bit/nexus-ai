# NEXUS Seed Real-Data Adapter Learning & Wall-Breaking Pillars (`seed_real_data_adapter_learning_v1`)

## 1. Executive Summary & Clean Starting Point
This document reports the implementation and independent verification of **`seed_real_data_adapter_learning_v1`** on top of the reviewed NEXUS Seed core (`EvidenceKernel`, `EvidenceRecord`, `MechanismCapsule`, `BeliefWorkspace`, `BatInvestigationScheduler`, and isolated black-box subprocess evaluation):

1. **Clean Starting Point & Strict Freeze Boundary**:
   - Built on branch `codex/seed-real-data-adapter-learning-v1` (branched from the reviewed commit lineage `d7865a2` $\to$ `f788bff`), preserving all prior artifacts and the corrected fixed-length, position-conditioned token decoder description.
   - Strictly separates **`development_results`** (used during algorithm and representation design) from **`independent_confirmation_results`** evaluated after `FREEZE_BEFORE_INDEPENDENT_CONFIRMATION` (`freeze_journal_sha256 = 6a456834c85ea9dfa3eeea1b0a531a1ac5c87a2efffe851bdfaa9c41a3780615`).
   - Reserves **entire datasets and schemas** (`A1_telemetry_alert_aggregation` on `clinical_sensor_telemetry`, `A2_ledger_department_reconciliation` on `financial_ledger_audit`, `SQL2_supply_chain_shipments_db`, and `SQL3_hospital_lab_results_db`) plus a **naturally occurring Python standard library AST corpus** (`R1_repo_python_ast_metrics` parsing real `.py` standard library modules on disk via `ast.parse`) for frozen independent confirmation.
2. **Stored Program Structure (`skeleton_ops`) Controls Execution Directly**:
   - `ParameterizedAdapterTemplate.skeleton_ops` stores the actual parameterized AST operation nodes (`list[dict[str, Any]]`) with symbolic `$SLOT` variables lifted directly from the discovered winning program.
   - `ParameterizedAdapterTemplate.instantiate(bindings, threshold)` contains **zero hardcoded `dict(op=...)` constructors**: it strictly walks `self.skeleton_ops` and substitutes `$SLOT` tokens.
   - `verify_skeleton_ast_controls_instantiation_and_sql()` proves that mutating `self.skeleton_ops` (reversing `OrderByFields`, removing `FilterNumericThreshold`, or emptying `skeleton_ops`) directly alters the instantiated program and execution output (`skeleton_controls_execution_verified = True`).
   - Candidate generation infers the structural type-state transition (`inferred_structural_signature`) from the input and output schemas (`set(req_cols).issubset(set(in_cols))`) without reading `task_kind`. When solving `S2` after `S1`, NEXUS extracts the cleaning/filtering prefix AST from `S1`'s `skeleton_ops` (`extract_cleaning_prefix_skeleton()`) and composes candidate `GroupByField -> AggregateGroups -> OrderByFields` suffix operators onto it.
3. **Real CSV/JSON Workspace (`RealDataWorkspaceAdapter`) & Compositional Adapters (`TypedDataAdapterProgram`)**:
   - Gives NEXUS read-only source files (`read_only_source/`, `0o444` permissions, SHA-256 verified before and after execution) and a separate writable `output/` directory (`winning_program_supplied_to_learner = False`, `private_heldout_exposed_to_learner = False`).
   - Supports field access, numeric parsing (`ParseNumberField`), missing-value handling (`DropMalformedRows`, `FillMissingField`, `on_error="drop_row"|"fill_default"`), text normalization (`NormalizeTextField`), filtering (`FilterEquals`, `FilterNumericThreshold`), derived fields (`ComputeDerivedField`), projection (`ProjectFields`), grouping (`GroupByField`), aggregation (`AggregateGroups`), and ordering (`OrderByFields`), verified on an 18-operation pipeline (`verify_unbounded_composition_and_missing_value_semantics()`).

---

## 2. Search Methods Comparison (Step 4)

We compare **`bounded_type_directed_enumeration`** (baseline) against **`backward_witness_constrained_search`** (using sound backward witness rules for sort direction, trailing-slash normalization, numeric value range, and categorical filter key survival), measuring candidate executions, runtime (ms), and peak memory (KB via `tracemalloc`):

| Task ID | Type-Valid Candidates | Enumeration Executions | Backward Witness Executions | Execution Reduction Ratio | Identical Surviving Version Space | Backward Witness Retained |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `S1_filter_and_normalize_error_logs` | `240` | `240` | `6` | `97.50%` | `True` (size `2`) | `True` |
| `S2_endpoint_latency_grouped_summary` | `240` | `240` | `6` | `97.50%` | `True` (size `2`) | `True` |
| `D1_clean_completed_orders` | `48` | `48` | `3` | `93.75%` | `True` (size `2`) | `True` |
| `D2_sku_revenue_grouped_summary` | `48` | `48` | `3` | `93.75%` | `True` (size `2`) | `True` |
| **Mean Across Multi-Step Tasks** | **`144.0`** | **`144.0`** | **`4.5`** | **`96.88%`** | **`True`** | **`True`** |
| *Trivial 1-Op Projection Policy* | `2` | `2` | — | — | — | `False` (uses `bounded_type_directed_enumeration`) |

---

## 3. Active Disambiguating Questions & Honest Ambiguity Reporting (Step 5)

On `S2_endpoint_latency_grouped_summary`, public demonstrations leave `2` surviving programs in version space $V$ that disagree on the boundary threshold. `construct_disambiguating_query_rows()` synthesizes valid boundary query rows on which the surviving programs disagree:

| Condition | Answer Source Available | Questions Charged | Ambiguity Reported | Pretended Resolved | Evidence Status | Promoted Capsules | Held-Out Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`without_answer_source`** | `False` | `0` | **`True`** | **`False`** | **`"unknown"`** | `0` | — (abstains honestly) |
| **`with_reference_answer_source`** | `True` | `1` (`2.0` units) | `False` | `False` | `"verified"` | `1` | **`1.0000`** |

---

## 4. Fair Persistent Learning Comparison: Development vs Frozen Independent Confirmation (Step 6)

Passive learners use the fair midpoint estimator `surviving[len(surviving) // 2]` (never `surviving[-1]`) AND are evaluated via the exact uniform version-space expectation $\frac{1}{|V|} \sum_{h \in V} \mathbb{I}[h(D_{\text{heldout}}) = y_{\text{heldout}}]$ (`mean_version_space_expected_accuracy`).

### 4.1 Development Results (`S1`, `S2`, `S3`, `D1`, `D2`)

| Method | Mean Held-Out Accuracy | Version-Space Expected Accuracy | Total Candidate Executions | Later-Tasks Executions (`S2..D2`) | Total Compute Cost | Later-Tasks Compute Cost | Old-Skill Retention |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `passive_fixed_library` | `0.2000` | `0.5000` | `672` | `432` | `319.20` | `204.70` | `1.0000` |
| `passive_growing_library` | `0.0000` | `0.5000` | `255` | `15` | `131.10` | `14.10` | `1.0000` |
| `active_fixed_library` (direct helper use, no capsule persistence) | `1.0000` | `1.0000` | `684` | `442` | `335.00` | `217.50` | `1.0000` |
| `exact_program_cache_baseline` (caches unparameterized programs) | `1.0000` | `1.0000` | `694` | `452` | `340.95` | `223.45` | `1.0000` |
| **`active_growing_library` (NEXUS Capsule Learner)** | **`1.0000`** | **`1.0000`** | **`265`** | **`23`** | **`145.90`** | **`25.90`** | **`1.0000`** |

### 4.2 Independent Confirmation Results on Reserved CSV/JSON Schemas (`A1`, `A2`) & Naturally Occurring Python Stdlib AST (`R1`)

| Method (Frozen Before Confirmation) | Task Suite | Mean Held-Out Accuracy | Total Candidate Executions | Total Compute Cost | Reused Promoted Capsule |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `passive_fixed_library` | `A1 + A2` | `0.0000` (`0.5000` VS exp.) | `72` | `33.30` | `False` |
| `active_fixed_library` | `A1 + A2` | `1.0000` | `78` | `40.00` | `False` |
| `exact_program_cache_baseline` | `A1 + A2` | `1.0000` | `79` | `40.70` | `False` |
| **`active_growing_library` (Frozen NEXUS Capsules)** | `A1 + A2` | **`1.0000`** | **`12`** (**`-66` execs saved**) | **`11.30`** (**`-28.70` cost saved**) | **`True` (`2/2`)** |
| **`active_growing_library` (Naturally Occurring Stdlib AST)** | `R1_repo_python_ast_metrics` | **`1.0000`** | **`5`** | **`5.20`** | **`True` (`1/1`)** |

---

## 5. True Relational Transfer to Normalized Multi-Table SQLite Databases After Freeze (Step 7)

Each SQLite database stores a normalized 2-table schema (`dim_entities` + `fact_events` linked via `FOREIGN KEY("entity_fk") REFERENCES "dim_entities"("entity_id")`). NEXUS introspects both tables via `PRAGMA table_info` and `PRAGMA foreign_key_list`, compiles `skeleton_ops` into an executable multi-table `SELECT ... FROM "fact_events" f JOIN "dim_entities" d ON ... WHERE ... GROUP BY ... ORDER BY ...` query (`compile_to_relational_sql()`), and the evaluator executes `submitted_sql_query` directly inside an isolated held-out SQLite DB containing **only** `dim_entities` and `fact_events` (`relational_sql_exact_match = True`):

| Assessment Tier | SQLite Task IDs | With Prior CSV/JSON Learning (Execs / Cost / Acc / SQL JOIN Match) | From Scratch (Execs / Cost / Acc) | Execution Savings | Compute Cost Savings |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Development SQLite** | `SQL1_service_telemetry_db` | `6` execs / `5.65` cost / `1.0000` acc / `True` | `63` execs / `30.80` cost / `1.0000` acc | `57` execs (`90.48%`) | `25.15` units (`81.66%`) |
| **Independent Confirmation SQLite** | `SQL2_supply_chain_shipments_db`, `SQL3_hospital_lab_results_db` | **`12` execs / `11.30` cost / `1.0000` acc / `True`** | **`102` execs / `50.80` cost / `1.0000` acc** | **`90` execs (`88.24%`)** | **`39.50` units (`77.76%`)** |
| **Overall SQLite Transfer** | `SQL1 + SQL2 + SQL3` | **`18` execs / `16.95` cost / `1.0000` acc / `True`** | **`165` execs / `81.60` cost / `1.0000` acc** | **`147` execs (`89.09%`)** | **`64.65` units (`79.23%`)** |

---

## 6. Unscripted Four Wall-Breaking Research Pillars

1. **Pillar 1 — Category Theory & Functorial Metaphor Transfer (`FunctorialCategoryBridge`)**:
   - Extracts the categorical skeleton `["Partition_By_Equivalence", "Filter_By_Monotonic_Threshold", "Fold_Associative_Monoid"]` from `tpl_grouped.skeleton_ops`.
   - Wraps black-box network functions in `_CountingCallable` to record both `algebraic_probes_used = 3` and `total_blackbox_function_calls_during_probing = 14`, verifies true triple associativity $(M(B_1) \oplus M(B_2)) \oplus M(B_3) = M(B_1) \oplus (M(B_2) \oplus M(B_3)) = M(B_1 + B_2 + B_3)$ (`associativity_verified_on_triples = True`), and dynamically verifies the functorial composition law $F(h \circ g \circ f)(x) = (F(h) \circ F(g) \circ F(f))(x)$ on held-out streams (`composition_law_preserved = True`, `heldout_packet_routing_accuracy = 1.0000`).
2. **Pillar 2 — Black-Box System Identification & AST Patch Synthesis via Dynamic Slicing (`AutodidactTracerSlicer`)**:
   - **Zero-Knowledge API Discovery**: Inspects Python signatures and runs active I/O probes to discriminate candidate behavioral hypotheses (`verified_on_heldout = True`).
   - **Dynamic Slicing & Real AST Source Patch Synthesis**: Uses `sys.settrace` and AST backward dataflow slicing to prune **`88.89%`** (`32/36` lines), reducing candidate AST `BinOp` patches from `24` (unsliced) to `3` (sliced), and synthesizes + compiles (`ast.parse` $\to$ `ast.unparse` $\to$ `compile()`) the repaired function `alert_total = alert_total + delta_load` (with zero `abs()` shortcuts), achieving `120` on witness and `250` on held-out packets (`repair_matches_oracle = True`).
3. **Pillar 3 — Judea Pearl's `do(X)` Calculus & Imre Lakatos's Proofs and Refutations (`CausalInterventionAndLakatosEngine`)**:
   - **Entropy-Maximizing `do(X)` Interventions**: Computes expected Shannon entropy across candidate interventions (`do(Y=23)` at `0.9183` bits followed by `do(X=10)` at `1.0` bit) to recover `G2_direct_X_to_Y` (`exact_recovery = True`).
   - **Lakatosian Counterexample Search & Predicate Lattice Refinement**: Synthesizes initial invariant predicates `["len_eq", "len_le", "set_eq", "is_sorted", "is_strictly_increasing_unique"]`, systematically enumerates `[2, 2, 2]` to falsify `len_eq`, and refines the conjecture to `["len_le", "set_eq", "is_sorted", "is_strictly_increasing_unique"]` (`refined_conjecture_holds_across_all_heldout = True`).
4. **Pillar 4 — Pidgin Semantic Bootstrapping & Verifiable Counterfactual Trace Explanations (`PidginBootstrapAndCounterfactualExplainer`)**:
   - **1-Turn Subprocess Pidgin Bootstrapping**: Searches over candidate streams to find a disambiguating probe stream, queries the isolated teacher subprocess (`teacher_subprocess_receipt = c50fb43eeaddcd4aad3822e020af3596f22ac1c59306ab96d0dc070394c3f737`), persists `"debounce"` in `lexicon_memory`, and executes `"Now debounce the telemetry stream"` with **`0` follow-up questions** (`heldout_verified = True`).
   - **Verifiable Counterfactual Explanations**: Records per-step row-drop counts across all 10 pipeline steps and verifies counterfactual threshold sensitivity (`4` actual rows vs `6` counterfactual rows; `counterfactual_sensitivity_verified = True`).

---

## 7. Local Model Structured-Intent Interface & 3-Way Benchmark Against Ordinary Caching

We evaluate three configurations on an $N=6$ task workload (including exact repeat, schema shift, reserved schema, ambiguous `revenue_eur` with negative refunds on `AMB1_revenue_eur_semantic_disambiguation`, and inappropriate `grouped_summary` reuse rejection on row-level task `S1_filter_and_normalize_error_logs`), measuring real Mac CPU latency (`ms`), tokens, unified process RSS (`KB`), and explicit Net Savings:
$$\text{Net savings over } N \text{ tasks} = \sum_{t=1}^{N} \left(C_{\text{baseline},t} - C_{\text{NEXUS},t}\right) - C_{\text{initial learning}}$$

| Configuration | Mean Held-Out Accuracy | Total Candidate Executions ($N=6$) | Total Compute Cost ($N=6$) | Wall-Clock Latency (`ms`) | Peak Process RSS (`KB`) | Net Savings vs Config (Execs / Compute Cost) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `model_plus_tools_and_retrieval` | `1.0000` | `853` | `417.00` | `545.53` | `32160.0` | **`+352` execs / `+159.70` net cost saved** |
| `same_system_plus_ordinary_program_caching` | `1.0000` | `612` | `300.75` | `534.99` | `32160.0` | **`+111` execs / `+43.45` net cost saved** |
| **`same_system_plus_nexus_abstractions_and_adaptation`** | **`1.0000`** | **`501`** | **`257.30`** (incl. `5.00` learning cost) | **`532.93`** | **`32176.0`** | *Reference (`inappropriate_reuse_rejected = True`, `AMB1` clarified)* |

---

## 8. Verification Commands

```bash
PYTHONPATH=src python3 scripts/verify_seed_real_data_adapter_learning.py
PYTHONPATH=src python3 -m pytest tests/test_seed_real_data_adapter_learning.py -v
```
