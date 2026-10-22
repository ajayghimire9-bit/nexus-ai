# NEXUS Seed Real-Data Adapter Learning & Wall-Breaking Pillars (`seed_real_data_adapter_learning_v1`)

## 1. Executive Summary & Clean Starting Point
This document reports the implementation and independent verification of **`seed_real_data_adapter_learning_v1`** on top of the reviewed NEXUS Seed core (`EvidenceKernel`, `EvidenceRecord`, `MechanismCapsule`, `BeliefWorkspace`, `BatInvestigationScheduler`, and isolated black-box subprocess evaluation):

1. **Clean Starting Point & Strict Freeze Boundary**:
   - Built on branch `codex/seed-real-data-adapter-learning-v1` (branched from the reviewed commit lineage `d7865a2` $\to$ `f788bff`), preserving all prior artifacts and the corrected fixed-length, position-conditioned token decoder description.
   - Strictly separates **`development_results`** (used during algorithm and representation design) from **`independent_confirmation_results`** evaluated after `FREEZE_BEFORE_INDEPENDENT_CONFIRMATION` (`freeze_journal_sha256 = bf9adb8ec338dc76a0c1c3d1db717bcec8420cd7a44d6fcee9129a10c600908a`).
   - Reserves **entire datasets and schemas** (`A1_telemetry_alert_aggregation` on `clinical_sensor_telemetry`, `A2_ledger_department_reconciliation` on `financial_ledger_audit`, `SQL2_supply_chain_shipments_db`, and `SQL3_hospital_lab_results_db`) for frozen independent confirmation rather than merely withholding rows.
2. **Real CSV/JSON Workspace (`RealDataWorkspaceAdapter`)**:
   - Gives NEXUS read-only source files (`read_only_source/`, `0o444` permissions, SHA-256 verified before and after execution) and a separate writable `output/` directory.
   - Defines tasks through public input-output demonstrations and explicit column/ordering requirements—never a supplied winning program (`winning_program_supplied_to_learner = False`, `private_heldout_exposed_to_learner = False`).
3. **Compositional Typed Adapters Without Arbitrary Length Limits (`TypedDataAdapterProgram`)**:
   - Extends the typed program representation with field access, numeric parsing (`ParseNumberField`), missing-value handling (`DropMalformedRows`, `FillMissingField`, `on_error="drop_row"|"fill_default"`), text normalization (`NormalizeTextField`: `strip`, `lower`, `strip_trailing_slash`), filtering (`FilterEquals`, `FilterNumericThreshold`), derived fields (`ComputeDerivedField`), projection (`ProjectFields`), grouping (`GroupByField`), aggregation (`AggregateGroups`), and ordering (`OrderByFields`).
   - Starts with `initial_stored_compositions = 0` and imposes no arbitrary 15-operation limit (verified on an 18-operation pipeline in `verify_unbounded_composition_and_missing_value_semantics()`).

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

On `S1_filter_and_normalize_error_logs`, public demonstrations leave `2` surviving programs that disagree on the boundary `status_code == 500` vs `status_code == 501`. `construct_disambiguating_query_rows()` synthesizes valid boundary query rows on which the surviving programs disagree:

| Condition | Answer Source Available | Questions Charged | Ambiguity Reported | Pretended Resolved | Evidence Status | Promoted Capsules | Held-Out Accuracy |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`without_answer_source`** | `False` | `0` | **`True`** | **`False`** | **`"unknown"`** | `0` | — (abstains honestly) |
| **`with_reference_answer_source`** | `True` | `1` (`2.0` units) | `False` | `False` | `"verified"` | `1` | **`1.0000`** |

---

## 4. Fair Persistent Learning Comparison: Development vs Frozen Independent Confirmation (Step 6)

Every method receives identical execution access—including direct in-episode helper use in `active_fixed_library` without persistent capsule promotion—and pays full `EvidenceKernel` costs for candidate execution, active boundary queries, abstraction discovery, promotion validation, and retrieval/binding.

### 4.1 Development Results (`S1`, `S2`, `S3`, `D1`, `D2`)

| Method | Mean Held-Out Accuracy | Total Candidate Executions | Later-Tasks Executions (`S2..D2`) | Total Compute Cost | Later-Tasks Compute Cost | Old-Skill Retention |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `passive_fixed_library` | `0.0000` | `672` | `432` | `319.20` | `204.70` | `1.0000` |
| `passive_growing_library` | `0.0000` | `252` | `12` | `129.10` | `12.10` | `1.0000` |
| `active_fixed_library` (direct helper use, no capsule persistence) | `1.0000` | `684` | `442` | `335.00` | `217.50` | `1.0000` |
| `exact_program_cache_baseline` (caches unparameterized programs) | `1.0000` | `694` | `452` | `340.95` | `223.45` | `1.0000` |
| **`active_growing_library` (NEXUS Capsule Learner)** | **`1.0000`** | **`262`** | **`20`** | **`143.90`** | **`23.90`** | **`1.0000`** |

### 4.2 Independent Confirmation Results on Reserved CSV/JSON Schemas (`A1`, `A2`) After Freeze

| Method (Frozen Before Confirmation) | Mean Held-Out Accuracy | Total Candidate Executions (`A1 + A2`) | Total Compute Cost (`A1 + A2`) | Reused Promoted Capsule |
| :--- | :---: | :---: | :---: | :---: |
| `passive_fixed_library` | `0.0000` | `72` | `33.30` | `False` |
| `active_fixed_library` | `1.0000` | `78` | `40.00` | `False` |
| `exact_program_cache_baseline` | `1.0000` | `79` | `40.70` | `False` |
| **`active_growing_library` (Frozen NEXUS Capsules)** | **`1.0000`** | **`12`** (**`-66` execs saved**) | **`11.30`** (**`-28.70` cost saved**) | **`True` (`2/2`)** |

---

## 5. Transfer to Real SQLite Databases After Freeze (Step 7)

After `FREEZE_BEFORE_SQLITE_TRANSFER_ASSESSMENT`, NEXUS connects to real on-disk SQLite databases (`sqlite3`) in read-only URI mode (`?mode=ro`), discovers tables and columns generically via `sqlite_master` and `PRAGMA table_info`, and binds its CSV/JSON-learned capsule templates without any supplied schema mappings:

| Assessment Tier | SQLite Task IDs | With Prior CSV/JSON Learning (Execs / Cost / Acc) | From Scratch (Execs / Cost / Acc) | Execution Savings | Compute Cost Savings |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Development SQLite** | `SQL1_service_telemetry_db` | `6` execs / `5.65` cost / `1.0000` acc | `63` execs / `30.80` cost / `1.0000` acc | `57` execs (`90.48%`) | `25.15` units (`81.66%`) |
| **Independent Confirmation SQLite** | `SQL2_supply_chain_shipments_db`, `SQL3_hospital_lab_results_db` | **`12` execs / `11.30` cost / `1.0000` acc** | **`102` execs / `50.80` cost / `1.0000` acc** | **`90` execs (`88.24%`)** | **`39.50` units (`77.76%`)** |
| **Overall SQLite Transfer** | `SQL1 + SQL2 + SQL3` | **`18` execs / `16.95` cost / `1.0000` acc** | **`165` execs / `81.60` cost / `1.0000` acc** | **`147` execs (`89.09%`)** | **`64.65` units (`79.23%`)** |

---

## 6. Four Wall-Breaking Research Pillars

1. **Pillar 1 — Category Theory & Functorial Metaphor Transfer (`FunctorialCategoryBridge`)**:
   - Strips domain types from the learned grouped-summary adapter to extract the type-erased categorical skeleton `["Partition_By_Equivalence", "Filter_By_Monotonic_Threshold", "Fold_Associative_Monoid"]`.
   - Runs **3 Algebraic Property Probes** on an unfamiliar Network Packet Routing domain (`net_morph_alpha`, `net_morph_beta`, `net_morph_gamma`) testing length-preserving idempotence, subset-shrinking idempotence, and associative monoid folding, achieving **`1.0000` held-out accuracy** in 3 probes.
2. **Pillar 2 — Black-Box System Identification & Tracer-Dye Dynamic Program Slicing (`AutodidactTracerSlicer`)**:
   - **Zero-Knowledge API Discovery**: Inspects Python signatures (`inspect.signature`) and runs active I/O probes on an undocumented module function to synthesize a verified behavioral capsule (`verified_on_heldout = True`).
   - **Tracer-Dye Dynamic Program Slicing**: Uses `sys.settrace` and AST backward dataflow slicing from the failing return variable `alert_total` to prune **`88.89%`** (`32/36` lines) of a multi-subsystem router pipeline, isolating the exact `4` causal lines and repairing `alert_total = alert_total - delta_load` $\to$ `alert_total = alert_total + delta_load` (`repair_matches_oracle = True`).
3. **Pillar 3 — Judea Pearl's `do(X)` Calculus & Imre Lakatos's Proofs and Refutations (`CausalInterventionAndLakatosEngine`)**:
   - **Surgical `do(X)` Interventions**: Confirms passive observational equivalence across `G1_confounded_Z_to_X_and_Y`, `G2_direct_X_to_Y`, and `G3_reverse_Y_to_X`, then executes a single surgical intervention `do(X=10)` to uniquely recover `G2_direct_X_to_Y` (`exact_recovery = True`).
   - **Lakatosian Refutation & Lemma Incorporation**: Generates a naive conjecture `len(f(x)) == len(x) and is_sorted(f(x))` from seed examples, actively searches for a "Monster" counterexample (`[2, 2, 5]`) that falsifies the naive conjecture, and incorporates the lemma `len(f(x)) <= len(x) and set(f(x)) == set(x) and is_sorted_unique(f(x))` (`refined_conjecture_holds_across_all_heldout = True`).
4. **Pillar 4 — Pidgin Semantic Bootstrapping & Verifiable Counterfactual Trace Explanations (`PidginBootstrapAndCounterfactualExplainer`)**:
   - **1-Turn Pidgin Bootstrapping**: Isolates the unknown token `"debounce"` in `"Please debounce the event stream"` (`Verb[Stream -> Stream]`), synthesizes a minimal disambiguating event stream `[A@0ms, A@2ms, B@50ms, A@100ms]`, resolves `"collapse_rapid_duplicates_within_10ms"` in 1 question, and verifies execution on held-out streams (`heldout_verified = True`).
   - **Verifiable Counterfactual Explanations**: Generates explanations directly from counterfactual threshold interventions on the actual pipeline trace (`status_code >= 500.0` retaining `4` rows vs counterfactual `status_code >= 200.0` retaining `6` rows; `counterfactual_sensitivity_verified = True`).

---

## 7. Verification Commands

```bash
PYTHONPATH=src python3 scripts/verify_seed_real_data_adapter_learning.py
PYTHONPATH=src python3 -m pytest tests/test_seed_real_data_adapter_learning.py -v
```
