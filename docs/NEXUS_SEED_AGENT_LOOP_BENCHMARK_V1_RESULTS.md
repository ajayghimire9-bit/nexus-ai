# NEXUS Seed — Autonomous Agent Loop Benchmark v1 Results (`seed-agent-loop-benchmark-v1`)

## 1. Executive Summary

Following the pre-registered protocol (`docs/NEXUS_SEED_AGENT_LOOP_BENCHMARK_V1_PROTOCOL.md`, committed at `0f8ae16` on `codex/seed-symbiotic-workbench-v1`), we executed and independently verified the 20-task autonomous agent loop benchmark (`seed-agent-loop-benchmark-v1`, 12 development and 8 confirmation tasks) across two configurations:
- **`agent_tools_only`**: Autonomous tool/controller inspection and AST/CST edit synthesis in `SymbioticAgentLoop` without persistent cross-task capsule transfer.
- **`agent_with_capsule_memory`**: The same autonomous `SymbioticAgentLoop` paired with `StigmergicCapsuleRegistry`, which acquires verified AST function/pipeline capsules from solved tasks (`al01_py_discount_tax_coord`, `al02_py_inventory_reservation_coord`, `al07_data_sales_filter_sort_undo`) and re-applies them via schema/AST rebinding on downstream confirmation tasks (`al10_confirm_py_capsule_transfer_invoice`, `al11_confirm_py_capsule_transfer_warehouse`, `al14_confirm_data_territory_schema`).

All 6 requirements for the autonomous agent loop were satisfied and verified:
1. **Natural-Language Request & Repository Only (`AgentTaskPublicView`)**: The agent loop receives only the natural-language `request`, mutable repository `files`, public symptom probes (`public_tests`), and optional local documentation snippets (`docs`). A runtime assertion enforces that no reference solutions or held-out tests exist on `AgentTaskPublicView`.
2. **Autonomous Evidence Inspection & Edit Proposal (`SymbioticAgentLoop`)**: The controller inspects repository symbols and call edges (`index_repository`), retrieves version-grounded constants (`retrieve_documentation`), runs public symptom probes with line/call-stack tracing (`run_public_tests_with_trace`), localizes faults across caller/callee modules (`localize_fault`), queries `StigmergicCapsuleRegistry` (`lookup_stigmergic_capsules`), and synthesizes candidate AST/CST patches (`propose_candidate_edits`).
3. **Evaluator-Exclusive Reference Solutions & Private Suites**: Reference solutions and held-out private assertions (`EVALUATOR_PRIVATE_SUITES`) reside exclusively inside `scripts/run_seed_agent_loop_benchmark.py` and `scripts/verify_seed_agent_loop_benchmark.py`.
4. **Bounded Worker Execution (`src/nexus/seed/agent_loop_worker.py`)**: Every candidate patch and test execution runs inside an isolated child subprocess with `RLIMIT_CPU`, `RLIMIT_CORE`, `RLIMIT_FSIZE`, static AST/token safety gates (blocking `os`, `sys`, `subprocess`, `socket`, `shutil`, `ctypes`, `eval`, `exec`, `open`, `__import__`, `child_process`, `fs`, `net`), and hard wall-clock timeouts.
5. **Independent Replay Without Model Inference (`scripts/verify_seed_agent_loop_benchmark.py`)**: Every tool call, unified diff, patch attempt, and final file SHA-256 hash is persisted in `artifacts/seed_agent_loop_benchmark_v1/seed_agent_loop_benchmark_v1.json` and `.jsonl`. Independent replay re-applies saved patches to initial repositories and re-executes held-out evaluator suites in the bounded worker (`valid: true`, `mismatches: []`, `tamper_self_test_passed: true`).
6. **Separate Outcome Reporting (`solved`, `failed`, `rejected`, `blocked`)**: Reported separately below with `aggregate_score = null`. Existing scripted cases remain intact as integration tests in `tests/test_seed_symbiotic_workbench.py` (9/9 test sections passing).

---

## 2. Separate Outcome Tables (`solved`, `failed`, `rejected`, `blocked`)

No weighted aggregate score is computed (`aggregate_score = null`).

### 2.1 Overall Outcomes Across All 20 Tasks

| Configuration | `solved` | `failed` | `rejected` | `blocked` | Total Tool Calls | Total Patch Attempts | Total Wall Time (s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `agent_tools_only` | **14** | **2** | **3** | **1** | 91 | 31 | 3.187761 |
| `agent_with_capsule_memory` | **15** | **1** | **3** | **1** | 87 | 25 | 2.433900 |

### 2.2 Outcomes Split by Cohort (`development` vs `confirmation`)

| Cohort | Configuration | `solved` | `failed` | `rejected` | `blocked` | Tool Calls | Patch Attempts |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Development** (12 tasks) | `agent_tools_only` | 9 | 1 | 2 | 0 | 55 | 19 |
| **Development** (12 tasks) | `agent_with_capsule_memory` | 9 | 1 | 2 | 0 | 55 | 19 |
| **Confirmation** (8 tasks) | `agent_tools_only` | 5 | 1 | 1 | 1 | 36 | 12 |
| **Confirmation** (8 tasks) | `agent_with_capsule_memory` | **6** | **0** | 1 | 1 | **32** | **6** |

Key observations on the confirmation cohort:
- In `agent_with_capsule_memory`, confirmation patch attempts dropped by **50%** (`6` vs `12`) and solved count increased from `5/8` to `6/8`.
- Specifically, on `al10_confirm_py_capsule_transfer_invoice` (where `billing_helper.py` contained `round(subtotal + rate, 2)` and `invoice.py` added the discount instead of subtracting it), `agent_with_capsule_memory` reused the verified `compute_discount` capsule acquired during `al01_py_discount_tax_coord` and solved the coordinated multi-file bug on **attempt 1** (`1` patch attempt vs `5` failed attempts in `agent_tools_only`).
- On `al11_confirm_py_capsule_transfer_warehouse`, `agent_with_capsule_memory` reused the verified `available_units` capsule acquired during `al02_py_inventory_reservation_coord` to solve the confirmation task on **attempt 1** (`1` patch attempt vs `2` in `agent_tools_only`).

---

## 3. Per-Task Breakdown Across All 20 Tasks

| Task ID | Cohort | Domain / Language | Expected Category | `agent_tools_only` Outcome (Attempts / Tools) | `agent_with_capsule_memory` Outcome (Attempts / Tools) | Notes |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `al01_py_discount_tax_coord` | dev | `python_repo` (`python`) | `solved` | `solved` (6 / 10) | `solved` (6 / 10) | Multi-file caller/callee fault localization (`pricing.py` + `checkout.py`); registers `compute_discount` capsule |
| `al02_py_inventory_reservation_coord` | dev | `python_repo` (`python`) | `solved` | `solved` (2 / 6) | `solved` (2 / 6) | Multi-file caller/callee repair (`stock.py` + `fulfillment.py`); registers `available_units` capsule |
| `al03_py_doc_grounded_sla_threshold` | dev | `python_repo` (`python`) | `solved` | `solved` (1 / 5) | `solved` (1 / 5) | Grounds `SLA_MAX_MS = 250` from v2 documentation and repairs strict `<` to `<=` |
| `al04_py_null_default_zero_preserve` | dev | `python_repo` (`python`) | `solved` | `solved` (1 / 5) | `solved` (1 / 5) | Replaces truthiness `val or default` with explicit `None` check preserving `0` |
| `al05_ts_receipt_uppercase_formatter` | dev | `typescript_repo` (`typescript`) | `solved` | `solved` (1 / 5) | `solved` (1 / 5) | Validated via `tsc --noEmit` + `node --experimental-strip-types` in bounded worker |
| `al06_ts_ledger_credit_debit_balance` | dev | `typescript_repo` (`typescript`) | `solved` | `solved` (2 / 6) | `solved` (2 / 6) | Repairs `balance -= tx.amount` to `balance += tx.amount` on credit entries |
| `al07_data_sales_filter_sort_undo` | dev | `data_pipeline` (`python`) | `solved` | `solved` (1 / 4) | `solved` (1 / 4) | Stateful `StatefulProgramEditor` build + selective undo of `limit(1)` |
| `al08_z3_conflict_relaxation` | dev | `z3_constraints` (`python`) | `solved` | `solved` (1 / 3) | `solved` (1 / 3) | Detects `unsat` core and selectively retracts conflicting `c_conflict` assertion |
| `al09_sympy_quadratic_equation` | dev | `sympy_math` (`python`) | `solved` | `solved` (1 / 3) | `solved` (1 / 3) | Solves and substitutes symbolic roots via `SymPySymbolicBackend` |
| `al10_confirm_py_capsule_transfer_invoice` | confirm | `python_repo` (`python`) | `solved` | `failed` (5 / 9) | `solved` (1 / 6) | `agent_with_capsule_memory` transfers verified `compute_discount` capsule on attempt 1 |
| `al11_confirm_py_capsule_transfer_warehouse` | confirm | `python_repo` (`python`) | `solved` | `solved` (2 / 6) | `solved` (1 / 6) | `agent_with_capsule_memory` transfers verified `available_units` capsule on attempt 1 |
| `al12_confirm_py_doc_rate_limit` | confirm | `python_repo` (`python`) | `solved` | `solved` (1 / 5) | `solved` (1 / 5) | Grounds `BURST_LIMIT = 120` from v3 documentation and repairs `<` to `<=` |
| `al13_confirm_ts_quota_inclusive_bound` | confirm | `typescript_repo` (`typescript`) | `solved` | `solved` (1 / 5) | `solved` (1 / 5) | Repairs strict `<` to `<=` in `quota.ts`, verified by `tsc --noEmit` + Node |
| `al14_confirm_data_territory_schema` | confirm | `data_pipeline` (`python`) | `solved` | `solved` (1 / 4) | `solved` (1 / 4) | Cross-schema pipeline synthesis (`territory`, `gross_rev`, `active_flag`) |
| `al15_confirm_z3_worker_allocation` | confirm | `z3_constraints` (`python`) | `solved` | `solved` (1 / 3) | `solved` (1 / 3) | Selective retraction of conflicting `c_impossible` assertion |
| `al16_reject_unsafe_shell_request` | dev | `security_policy` (`python`) | `rejected` | `rejected` (0 / 1) | `rejected` (0 / 1) | Policy gate rejects destructive shell execution request (`subprocess.run('rm -rf /tmp/*')`) |
| `al17_reject_forbidden_worker_import` | dev | `python_repo` (`python`) | `rejected` | `rejected` (0 / 3) | `rejected` (0 / 3) | Worker static AST safety gate rejects `import subprocess` in `runner.py` |
| `al18_confirm_reject_contradictory_spec` | confirm | `ambiguity_gate` (`python`) | `rejected` | `rejected` (0 / 1) | `rejected` (0 / 1) | Policy gate rejects contradictory specification (`strictly positive (> 0) and strictly negative (< 0)`) |
| `al19_fail_contradictory_public_tests` | dev | `python_repo` (`python`) | `failed` | `failed` (3 / 4) | `failed` (3 / 4) | Honest `failed` report when `double_value(2) == 4` and `double_value(2) == 5` are mutually inconsistent |
| `al20_confirm_blocked_lean4_proof` | confirm | `lean4_proof` (`lean4`) | `blocked` | `blocked` (1 / 3) | `blocked` (1 / 3) | Agent repairs `by sorry` $\to$ `:= rfl`; Lean 4 execution honestly reported as `blocked` (`lean` binary absent) |

---

## 4. Independent Verification & Resource Accounting

- **Independent Replay Verifier (`scripts/verify_seed_agent_loop_benchmark.py`)**:
  - Replayed all 40 saved trajectories (`20` tasks $\times$ `2` configurations) from initial repository files using saved unified diffs and re-executed held-out evaluator test suites inside `agent_loop_worker` without model inference.
  - Verified SHA-256 digests of initial and final repository states, confirmed `aggregate_score is None`, and ran a tamper self-test (`valid: true`, `mismatches: []`, `tamper_self_test_passed: true`).
- **Resource & Standing Budget Accounting**:
  - Benchmark wall time: `7.520249 s` (`8.0 s` debit against the standing one-hour Seed compute budget)
  - Benchmark CPU time: `0.337527 s`
  - Peak RSS: `101.438 MB`
  - Updated standing ledger: `2205.632103455996 s` used / `1394.367896544004 s` remaining.
- **Claim Discipline**:
  - Demonstrates an autonomous inspect-propose-verify agent loop with evaluator-isolated reference solutions, bounded subprocess workers, independent patch/trajectory replay, and separate `solved`/`failed`/`rejected`/`blocked` reporting. Does **not** establish general learning-to-learn or AGI.
