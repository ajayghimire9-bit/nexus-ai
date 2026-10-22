# NEXUS Seed Real-Data Adapter Learning & Wall-Breaking Pillars (`seed_real_data_adapter_learning_v1`)

## 1. Executive Summary & Clean Starting Point
This document reports the implementation and independent verification of **`seed_real_data_adapter_learning_v1`** on top of the reviewed NEXUS Seed core (`EvidenceKernel`, `EvidenceRecord`, `MechanismCapsule`, `BeliefWorkspace`, `BatInvestigationScheduler`, and isolated black-box subprocess evaluation):

1. **Clean Starting Point & Strict Freeze Boundary**:
   - Built on branch `codex/seed-real-data-adapter-learning-v1` (branched from the reviewed commit lineage `d7865a2` $\to$ `f788bff`), preserving all prior artifacts and the corrected fixed-length, position-conditioned token decoder description.
   - Strictly separates **`development_results`** (used during algorithm and representation design) from **`independent_confirmation_results`** evaluated after `FREEZE_BEFORE_INDEPENDENT_CONFIRMATION` (`freeze_journal_sha256 = 6a456834c85ea9dfa3eeea1b0a531a1ac5c87a2efffe851bdfaa9c41a3780615`).
   - Reserves **entire datasets and schemas** (`A1_telemetry_alert_aggregation` on `clinical_sensor_telemetry`, `A2_ledger_department_reconciliation` on `financial_ledger_audit`, `SQL2_supply_chain_shipments_db`, and `SQL3_hospital_lab_results_db`), a **naturally occurring Python standard library AST corpus** (`R1_repo_python_ast_metrics` parsing real `.py` standard library modules on disk via `ast.parse`), and **fresh verifier-seeded procedural unseen schemas** (`verify_unseen_procedural_schema_confirmation(seed=20261022)` and `seed=999991`).
   - **Epistemic Scope Note**: In-repository confirmation tasks (`A1`, `A2`, `R1`, `SQL2`, `SQL3`) verify zero-parameter-update execution after template freeze and live held-out recomputation in the independent verifier (`reverify_heldout_program_ops`), complemented by procedurally synthesized unseen schemas from a verifier seed; however, in-repo tasks do not substitute for an external third-party blind holdout hosted outside this repository.
2. **Stored Program Structure (`skeleton_ops`) Controls Execution & Unfamiliar Operator Composition Discovery (`U1 -> U2`)**:
   - `ParameterizedAdapterTemplate.skeleton_ops` stores the actual parameterized AST operation nodes (`list[dict[str, Any]]`) with symbolic `$SLOT` variables lifted directly from the discovered winning program.
   - `ParameterizedAdapterTemplate.instantiate(bindings, threshold)` contains **zero hardcoded `dict(op=...)` constructors**: it strictly walks `self.skeleton_ops` and substitutes `$SLOT` tokens (`skeleton_controls_execution_verified = True`).
   - **Open-Ended Unfamiliar Composition Discovery (`U1_derived_net_margin_audit` $\to$ `U2_regional_net_payout_audit`)**: Beyond row-filtering and grouped-summary pipelines, when demonstration outputs contain a derived column absent from the input schema (`derived_output_cols`), NEXUS searches over binary arithmetic operators (`sub`, `add`, `mul`), ordered numeric operand pairs `(lhs_col, rhs_col)`, threshold filtering on the derived column, text normalization, projection, and sorting to synthesize a 10-step composition containing `ComputeDerivedField` (`net_usd = gross_usd - fee_usd`). It lifts that 10-step AST into `tpl_derived_field_filter_order_from_U1_derived_net_margin_audit` (`147` executions on `U1`, `1.0000` held-out accuracy) and transfers it to `U2_regional_net_payout_audit` (`net_payout_eur = payout_eur - tax_eur`) in **`6` executions vs `147` from scratch** (**`141` executions saved, `70.00` compute units saved, `1.0000` held-out accuracy**).
3. **Real CSV/JSON Workspace (`RealDataWorkspaceAdapter`) & Compositional Adapters (`TypedDataAdapterProgram`)**:
   - Gives NEXUS read-only source files (`read_only_source/`, `0o444` permissions, SHA-256 verified before and after execution) and a separate writable `output/` directory (`winning_program_supplied_to_learner = False`, `private_heldout_exposed_to_learner = False`).
   - Verified on an 18-operation pipeline (`verify_unbounded_composition_and_missing_value_semantics()`).

---

## 2. Search Methods Comparison (Step 4)

We compare **`bounded_type_directed_enumeration`** (baseline) against **`backward_witness_constrained_search`** (using sound backward witness rules for sort direction, trailing-slash normalization, numeric value range, and categorical filter key survival), measuring candidate executions, runtime (ms), and peak memory (KB via `tracemalloc`):

| Task ID | Type-Valid Candidates | Enumeration Executions | Backward Witness Executions | Execution Reduction Ratio | Identical Surviving Version Space | Backward Witness Retained |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `S1_filter_and_normalize_error_logs` | `240` | `240` | `6` | `97.50%` | `True` (size `3`) | `True` |
| `S2_endpoint_latency_grouped_summary` | `240` | `240` | `6` | `97.50%` | `True` (size `3`) | `True` |
| `D1_clean_completed_orders` | `48` | `48` | `3` | `93.75%` | `True` (size `3`) | `True` |
| `D2_sku_revenue_grouped_summary` | `48` | `48` | `3` | `93.75%` | `True` (size `3`) | `True` |
| **Mean Across Multi-Step Tasks** | **`144.0`** | **`144.0`** | **`4.5`** | **`96.88%`** | **`True`** | **`True`** |
| *Trivial 1-Op Projection Policy* | `2` | `2` | — | — | — | `False` (uses `bounded_type_directed_enumeration`) |

---

## 3. Active Disambiguating Questions & Honest Ambiguity Reporting (Step 5)

Public demonstrations leave `3` surviving programs in version space $V$ (`[lower_wrong, true_boundary, upper_wrong]`) that disagree on the boundary threshold. `construct_disambiguating_query_rows()` synthesizes valid boundary query rows on which the surviving programs disagree:

| Condition | Answer Source Available | Questions Charged | Ambiguity Reported | Pretended Resolved | Evidence Status | Promoted Capsules | Held-Out Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`without_answer_source`** | `False` | `0` | **`True`** | **`False`** | **`"unknown"`** | `0` | — (abstains honestly) |
| **`with_reference_answer_source`** | `True` | `1` (`2.0` units) | `False` | `False` | `"verified"` | `1` | **`1.0000`** |

---

## 4. Fair Persistent Learning Comparison: Development vs Frozen Independent Confirmation (Step 6)

**Identical Canonical Selection Rule**: Every method—both passive and active—uses the **exact same selection rule (`selected_prog = surviving[0]`, `selection_rule = "canonical_first_surviving_candidate"`)** after receiving its permitted evidence. We also report the uniform version-space expectation $\frac{1}{|V|} \sum_{h \in V} \mathbb{I}[h(D_{\text{heldout}}) = y_{\text{heldout}}]$ (`mean_version_space_expected_accuracy`) as supplementary analysis, and the standalone verifier recomputes all held-out accuracies live from `selected_program_ops` via `reverify_heldout_program_ops`.

### 4.1 Development Results (`S1`, `S2`, `S3`, `D1`, `D2`)

| Method | Selection Rule | Mean Held-Out Accuracy | Version-Space Expected Accuracy | Total Candidate Executions | Later-Tasks Executions (`S2..D2`) | Total Compute Cost | Later-Tasks Compute Cost | Old-Skill Retention |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `passive_fixed_library` | `surviving[0]` | `0.0000` | `0.3333` | `672` | `432` | `319.20` | `204.70` | `1.0000` |
| `passive_growing_library` | `surviving[0]` | `0.0000` | `0.3333` | `255` | `15` | `131.10` | `14.10` | `1.0000` |
| `active_fixed_library` (direct helper use, no capsule persistence) | `surviving[0]` | `1.0000` | `1.0000` | `690` | `447` | `337.90` | `219.90` | `1.0000` |
| `exact_program_cache_baseline` (caches unparameterized programs) | `surviving[0]` | `1.0000` | `1.0000` | `700` | `457` | `343.85` | `225.85` | `1.0000` |
| **`active_growing_library` (NEXUS Capsule Learner)** | **`surviving[0]`** | **`1.0000`** | **`1.0000`** | **`270`** | **`27`** | **`148.30`** | **`27.80`** | **`1.0000`** |

### 4.2 Independent Confirmation Results on Reserved CSV/JSON Schemas (`A1`, `A2`), Naturally Occurring Stdlib AST (`R1`), & Procedural Unseen Schemas

| Method (Frozen Before Confirmation) | Task Suite | Mean Held-Out Accuracy | Total Candidate Executions | Total Compute Cost | Reused Promoted Capsule |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `passive_fixed_library` | `A1 + A2` | `0.0000` (`0.3333` VS exp.) | `72` | `33.30` | `False` |
| `active_fixed_library` | `A1 + A2` | `1.0000` | `78` | `40.00` | `False` |
| `exact_program_cache_baseline` | `A1 + A2` | `1.0000` | `79` | `40.70` | `False` |
| **`active_growing_library` (Frozen NEXUS Capsules)** | `A1 + A2` | **`1.0000`** | **`12`** (**`-66` execs saved**) | **`11.30`** (**`-28.70` cost saved**) | **`True` (`2/2`)** |
| **`active_growing_library` (Naturally Occurring Stdlib AST)** | `R1_repo_python_ast_metrics` | **`1.0000`** | **`6`** | **`5.65`** | **`True` (`1/1`)** |
| **`active_growing_library` (Procedural Unseen Schema `seed=20261022` & `999991`)** | `PROC_UNSEEN_*` | **`1.0000`** | **`3` bound vs `24` scratch** (**`-21` execs saved**) | — | **`True`** |

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

## 7. Quantized Pretrained GGUF Model (`llama.cpp`) Structured-Intent Interface & 3-Way Benchmark ($R=5$ Repeated Trials)

`GrammarConstrainedLocalIntentModel` executes grammar-constrained JSON schema decoding on a real 4-bit quantized pretrained GGUF model (**`qwen2.5-0.5b-instruct-q4_k_m.gguf`**, `491,400,032` bytes = `479,882.84 KB` on disk) via **`llama.cpp` (`llama-completion -ngl 0 -j <JSON_SCHEMA>`)**, with **zero keyword checks (`used_keyword_matching = False`)** and real model tokenizer token counts (`1,262` input tokens + `166` output tokens = `1,428` total tokens across the $N=6$ workload).

We evaluate three configurations across $R=5$ repeated independent trials on the $N=6$ task workload (including exact repeat, schema shift, reserved schema, ambiguous `revenue_eur` with negative refunds on `AMB1_revenue_eur_semantic_disambiguation`, and inappropriate `grouped_summary` reuse rejection on row-level task `S1_filter_and_normalize_error_logs`):
$$\text{Net savings over } N \text{ tasks} = \sum_{t=1}^{N} \left(C_{\text{baseline},t} - C_{\text{NEXUS},t}\right) - C_{\text{initial learning}}$$

| Configuration | Mean Held-Out Accuracy | Total Candidate Executions ($N=6$) | Total Compute Cost ($N=6$) | In-Process Solver Latency (`ms`, Mean $\pm$ SD, 95% CI) | Shared `llama.cpp` CPU Latency (`ms`) | Model Tokens (In / Out / Total) | Net Savings vs Config (Execs / Compute Cost / Paired Solver Latency 95% CI) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `model_plus_tools_and_retrieval` | `1.0000` | `857` | `418.95` | `15.31 ± 0.97` (`[14.11, 16.51]`) | `3260.35` | `1262 / 166 / 1428` | **`+353` execs / `+160.20` net cost / `+6.08 ms` (`[+5.20, +6.95]`)** |
| `same_system_plus_ordinary_program_caching` | `1.0000` | `615` | `302.20` | `10.73 ± 0.39` (`[10.25, 11.22]`) | `3260.35` | `1262 / 166 / 1428` | **`+111` execs / `+43.45` net cost / `+1.50 ms` (`[+1.09, +1.91]`)** |
| **`same_system_plus_nexus_abstractions_and_adaptation`** | **`1.0000`** | **`504`** | **`258.75`** (incl. `5.00` learning cost) | **`9.23 ± 0.29` (`[8.87, 9.60]`)** | `3260.35` | `1262 / 166 / 1428` | *Reference (`inappropriate_reuse_rejected = True`, `AMB1` clarified)* |

> **Latency Interpretation Note**: End-to-end harness wall-clock time (`~526.56 ms` vs `~528.79 ms` after warm `llama.cpp` prompt cache) is dominated by isolated subprocess evaluator I/O (`~500 ms` across 6 tasks) and shared `llama.cpp` GGUF inference (`3,260.35 ms` across 6 prompts), which are identical across all three configurations. When isolating in-process solver search, binding validation, and candidate execution latency (`solver_search_and_execution_latency_ms`), NEXUS achieves a statistically reliable speedup (`+1.50 ms` vs ordinary caching, 95% CI `[+1.09, +1.91] ms`; `+6.08 ms` vs baseline, 95% CI `[+5.20, +6.95] ms`) alongside `111` fewer candidate executions than ordinary caching and `353` fewer than baseline.

---

## 8. Verification Commands

```bash
PYTHONPATH=src python3 scripts/verify_seed_real_data_adapter_learning.py
PYTHONPATH=src python3 -m pytest tests/test_seed_real_data_adapter_learning.py -v
```
