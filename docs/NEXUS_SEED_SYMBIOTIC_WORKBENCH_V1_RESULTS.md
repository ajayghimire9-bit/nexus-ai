# NEXUS Seed — Symbiotic Multi-Backend Workbench v1 Results (`seed-symbiotic-workbench-v1`)

- **Study ID**: `seed-symbiotic-workbench-v1`
- **Branch**: `codex/seed-symbiotic-workbench-v1`
- **Pre-Run Implementation & Protocol Commit**: `4d053d4`
- **Protocol**: [NEXUS_SEED_SYMBIOTIC_WORKBENCH_V1_PROTOCOL.md](NEXUS_SEED_SYMBIOTIC_WORKBENCH_V1_PROTOCOL.md)
- **Config**: [`configs/seed_symbiotic_workbench_v1.json`](../configs/seed_symbiotic_workbench_v1.json)
- **Raw Artifacts**:
  - [`artifacts/seed_symbiotic_workbench_v1/seed_symbiotic_workbench_v1.json`](../artifacts/seed_symbiotic_workbench_v1/seed_symbiotic_workbench_v1.json)
  - [`artifacts/seed_symbiotic_workbench_v1/seed_symbiotic_workbench_v1.jsonl`](../artifacts/seed_symbiotic_workbench_v1/seed_symbiotic_workbench_v1.jsonl)
- **Independent Verifier**: [`scripts/verify_seed_symbiotic_workbench.py`](../scripts/verify_seed_symbiotic_workbench.py) (`valid: true`, `mismatches: []`, `tamper_self_test_passed: true`, `model_inference: false`)

---

## 1. Executive Summary & Claim Discipline

The Symbiotic Multi-Backend NEXUS Workbench (`src/nexus/seed/symbiotic_workbench.py`) connects all 9 engineering subsystems directly to the unified `Conversation`, `SeedWorkspace`, `Session` journal, and `/chat` Learning Lab UI:

1. **Shared Execution Contract (`TypedActionProposal`)**: Every backend action records an explicit `proposal_id`, `intent`, `backend`, `target`, `input_type`, `output_type`, `preconditions`, `expected_effects`, `dependencies`, `version_id`, `resource_limits`, `execution_status`, `provenance_kind` (`model_generated`, `source_attributed`, `observed_execution`, `tested_hypothesis`, `formally_checked`), and `rollback_semantics`.
2. **Stateful Program Editor (`StatefulProgramEditor`)**: Application-owned persistent node IDs (`rf_1`, `grp_1`, `agg_1`, `gf_1`, `sort_1`), dependency tracking, version history, and structured edits (`insert`, `replace`, `remove`, `rebind`, `compose`, `selective_undo`), including the full 6-step regional sales workflow with selective undo of `gf_1` and cross-schema AST capsule rebinding after session restart.
3. **Multi-Format Data Backends (`MultiFormatDataBackend`)**: Read-only CSV, nested JSON path flattening and reconstruction (`customer.region`, `metrics.amount`), SQLite multi-table `JOIN` with `WHERE` vs `HAVING` and transactional output, plus **post-commit cancellation repair** in `workspace_conversation.py` so cancellation arriving after `os.replace` / DB commit preserves the receipt and workspace state and never reports the committed action as undone.
4. **Polyglot Coding Backends (`PolyglotCodingWorkbench`)**: Isolated worktree execution with `tree-sitter-python` and `tree-sitter-typescript` CST/AST node indexing, symbol lookup, multi-file Python repair (`pricing.py` + `checkout.py`; `stock.py` + `order_service.py`), TypeScript validation via real `tsc --noEmit` (v7.0.2) and `node --experimental-strip-types` (v22.18.0), unified diff preview, and selective per-edit undo.
5. **Formal & Symbolic Reasoning Backends (`StatefulZ3Coordinator`, `SymPySymbolicBackend`, `Lean4ProofBackend`)**:
   - Real `z3-solver` (`5.3.1.0`) constraint graph with named nodes (`c1..c4`), `sat`/`unsat`, unsat cores, selective constraint removal, and independent Python model translation verification.
   - Real `sympy` algebraic equation solving, symbolic differentiation, and equivalence proving with substitution verification.
   - `Lean4ProofBackend`: Rejects `sorry`, `admit`, and unverified `axiom` tokens (`rejected_unverified_token`), and honestly reports `blocked_missing_runtime` when the `lean` binary is absent on the host (never faking a proof check with a mock).
6. **Hierarchical Planning (`HierarchicalPlanner`)**: 3-level linked contract graph (`project_goal` $\leftrightarrow$ `module_contract` $\leftrightarrow$ `function_or_program`) that automatically invalidates and revalidates dependent modules and goals when a function contract changes.
7. **Knowledge & Wikidata Snapshot Adapter (`KnowledgeAndDocRetriever`)**: Versioned local documentation (`sha256`, `version`, `timestamp`) and offline `WikidataSnapshotAdapter` with contradiction detection across competing claims and strict separation between lexical candidate meanings and grounded executable bindings.
8. **Stigmergic Capsule Registry & Cross-Profile Exchange (`StigmergicCapsuleRegistry`, `BoundedIngestionJob`)**: Bounded code/doc capsule acquisition with behavioral probes, counterexample retention, active/cold storage consolidation, and cross-profile capsule transfer (`Profile A` exports $\to$ `Profile B` imports and revalidates in sandbox without auto-executing on import).
9. **Repaired Capability Verifier (`scripts/verify_seed_conversation_capability.py`)**: Reconstructs expected outputs independently from `configs/seed_conversation_capability_v1.json` and saved input CSV files rather than comparing `output == reference_output` inside the same artifact.

---

## 2. Results by Configuration & Control (30 Tasks × 3 Configurations + Controls)

No single weighted aggregate score is used (`aggregate_score: null`).

| Configuration | Correct / Total | Development (`n=19`) | Confirmation (`n=11`) | External Runtime Blocked (`Lean 4`) | Candidate / Editor Ops | Capsule Reuses | Wall Time (s) | CPU Time (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A: `model_tools_editor`** | **30 / 30** | 19 / 19 | 11 / 11 | 1 (`t19`) | 63 | 0 | 0.696269 | 0.102236 |
| **B: `ordinary_cache_templates_retrieval`** | **30 / 30** | 19 / 19 | 11 / 11 | 1 (`t19`) | 63 | 0 | 0.520702 | 0.088129 |
| **C: `nexus_symbiotic_abstractions`** | **30 / 30** | 19 / 19 | 11 / 11 | 1 (`t19`) | **58** | **2** | 0.640594 | 0.152686 |
| **Control: `nexus_reset_memory`** | **1 / 1** (expected clarify when memory wiped) | — | — | 0 | 0 | 0 | 0.001207 | 0.001206 |
| **Control: `nexus_wrong_memory`** | **2 / 2** (rejected incompatible schema & wrong probe capsule) | — | — | 0 | 0 | 0 | 0.002065 | 0.002048 |

### Breakdown by Task Category (`Configurations A / B / C`)

| Category | Tasks (`n`) | `model_tools_editor` Ops | `ordinary_cache_templates_retrieval` Ops | `nexus_symbiotic_abstractions` Ops | Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `data_programs` | 6 | 17 (6/6) | 17 (6/6) | **14** (6/6) | Rebinding the saved stateful AST capsule on `t05_data_confirm_schema_rebind` reduces editor operations from 4 to 1. |
| `polyglot_coding` | 5 | 9 (5/5) | 9 (5/5) | 9 (5/5) | Real Python subprocess tests + TypeScript `tsc --noEmit` & Node execution pass across all 3 configs. |
| `z3_sympy_reasoning` | 5 | 13 (5/5) | 13 (5/5) | 13 (5/5) | Real `z3-solver` (`sat`/`unsat`/selective undo) and `sympy` symbolic verification. |
| `formal_proof` | 3 | 3 (3/3) | 3 (3/3) | 3 (3/3) | `t17` (`sorry`) and `t18` (`axiom`) rejected; `t19` honestly reported as `blocked_missing_runtime` (`lean` binary absent on host). |
| `knowledge_wikidata` | 4 | 4 (4/4) | 4 (4/4) | 4 (4/4) | Versioned doc grounding and Wikidata contradiction detection (`Q9902` Mercury density, `Q153` ethanol boiling point). |
| `capsule_transfer` | 4 | 8 (4/4) | 8 (4/4) | **6** (4/4) | Cross-profile transfer (`Profile A` $\to$ `Profile B`) on `t27_cap_confirm_cross_profile_zscore_norm` avoids local candidate search in Profile B (1 op vs 3 ops). |
| `mixed_workflows` | 3 | 9 (3/3) | 9 (3/3) | 9 (3/3) | Hierarchical 3-level contract propagation (`t28`), unsafe/ambiguous guards (`t29`), and doc $\to$ Z3 $\to$ Python SLA verification (`t30`). |

---

## 3. Live Local Pretrained Runtime Probe & Resource Accounting

- **Live Pretrained Model Probe (`qwen2.5-0.5b-instruct-q4_k_m.gguf` via `llama-server`)**:
  - `available: true`, `inference_ran: true`, `model_calls: 1`, `request_wall_s: 1.3196s`.
  - Properly labeled in chat UI and turn cards as `source="model_generated"`, `executed=False`.
- **Total Study Resource Debit**:
  - `total_wall_s`: `3.240204 s` (debit `4.0 s` against standing budget)
  - `total_cpu_s`: `0.598799 s`
  - `peak_rss_mb`: `113.328 MB`
  - **Updated Scientific Ledger**: `2197.632103455996 s` used / `1402.367896544004 s` remaining.
- **Limitations & Honest Non-Claims**:
  - Saving and rebinding stateful program AST capsules and exchanging verified function capsules across profiles reduce downstream editor/candidate operations on compatible target tasks (`58` vs `63` ops), but this is **explicit/verified procedural and capsule reuse**, **not** general learning-to-learn, unrestricted program synthesis, or AGI.
