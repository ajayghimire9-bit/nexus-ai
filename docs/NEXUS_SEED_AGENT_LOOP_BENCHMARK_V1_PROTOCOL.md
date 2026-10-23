# NEXUS Seed Autonomous Agent Loop Benchmark Protocol (`seed-agent-loop-benchmark-v1`)

- **Study ID**: `seed-agent-loop-benchmark-v1`
- **Branch**: `codex/seed-symbiotic-workbench-v1`
- **Pre-Registration Requirement**: This protocol and [`configs/seed_agent_loop_benchmark_v1.json`](../configs/seed_agent_loop_benchmark_v1.json) are locked before running and scoring the autonomous agent-loop benchmark.

---

## 1. Architectural Separation (Agent Loop vs Evaluator)

This benchmark evaluates the **Autonomous Symbiotic Agent Loop** ([`src/nexus/seed/symbiotic_agent_loop.py`](../src/nexus/seed/symbiotic_agent_loop.py)) while keeping the existing scripted cases in [`tests/test_seed_symbiotic_workbench.py`](../tests/test_seed_symbiotic_workbench.py) as deterministic subsystem integration tests:

1. **Public Task View Only (`AgentTaskPublicView`)**:
   - The agent loop receives only `task_id`, `cohort`, `domain`, `language`, natural-language `request`, initial `files`, `public_tests`, and optional `docs`.
   - It has **zero access** to reference solutions, oracle patches, or held-out private evaluation test suites.
2. **Autonomous Evidence Inspection & Proposal Synthesis**:
   - The agent controller inspects the repository AST/CST and dependency graph (`index_repository`), retrieves grounded bindings from local documentation (`retrieve_documentation`), runs `public_tests` with line/call profiling inside the bounded worker (`run_public_tests_with_trace`), localizes faults across the call graph (`localize_fault`), queries any active stigmergic capsules (`lookup_stigmergic_capsules`), and generates candidate AST/CST patches (`propose_candidate_edits`).
3. **Reference Solutions & Held-Out Tests Exclusively in Evaluator**:
   - Private held-out test cases and reference oracle checks reside exclusively in [`scripts/run_seed_agent_loop_benchmark.py`](../scripts/run_seed_agent_loop_benchmark.py) and [`scripts/verify_seed_agent_loop_benchmark.py`](../scripts/verify_seed_agent_loop_benchmark.py), and are invoked only **after** `SymbioticAgentLoop.solve()` returns its locked final repository state (`final_files_sha256`).
4. **Bounded Subprocess Worker Execution**:
   - Every candidate patch is compiled and tested in an isolated child process ([`src/nexus/seed/agent_loop_worker.py`](../src/nexus/seed/agent_loop_worker.py)) enforcing `RLIMIT_CPU`, `RLIMIT_CORE`, `RLIMIT_FSIZE`, and static AST/token safety checks.
5. **Independent Replay of Saved Patches, Tool Calls & Outcomes**:
   - Every trial saves its ordered `tool_calls`, `patch_attempts` (with unified diffs and worker statuses), `final_diff`, and `final_files`.
   - [`scripts/verify_seed_agent_loop_benchmark.py`](../scripts/verify_seed_agent_loop_benchmark.py) replays the saved `final_diff` / `final_files` inside the bounded worker against both the public and private evaluator suites and verifies the exact breakdown of outcome categories.
6. **Separate Outcome Reporting (`solved`, `failed`, `rejected`, `blocked`)**:
   - Every configuration reports counts and task lists separately for:
     - `solved`: Agent proposed a patch/solution that passed public checks AND passed the evaluator's private held-out verification suite.
     - `failed`: Agent exhausted its step budget or produced a patch that failed verification.
     - `rejected`: Agent or bounded worker refused an unsafe request, forbidden import, or contradictory specification before mutating state.
     - `blocked`: Agent produced a valid candidate (`Proof.lean`), but external verification was blocked by an absent host binary (`lean` not installed on host, reported honestly as `blocked`).
