# NEXUS Seed Symbiotic Multi-Backend Workbench Protocol (`seed-symbiotic-workbench-v1`)

- **Study ID**: `seed-symbiotic-workbench-v1`
- **Branch**: `codex/seed-symbiotic-workbench-v1`
- **Base Commit**: `b4c969388ca5dcd5e3c1c2b5b7f97f18cb1e964b` (`cursor/seed-conversation-correctness-matrix`)
- **Pre-Registration Requirement**: This protocol and `configs/seed_symbiotic_workbench_v1.json` are committed to git before running and scoring the 30-task evaluation.

---

## 1. Scientific Scope & Claim Discipline

This study evaluates the **Symbiotic Multi-Backend NEXUS Workbench** across 30 distinct task cases spanning 7 categories (`data_programs`, `polyglot_coding`, `z3_sympy_reasoning`, `formal_proof`, `knowledge_wikidata`, `capsule_transfer`, and `mixed_workflows`), split into 20 `development` tasks and 10 reserved `confirmation` tasks.

**Strict Non-Claims**:
- Persistence, saved stateful AST capsules, and cross-profile capsule exchange demonstrate **verified procedural/capsule reuse and bounded compositional transfer**, **not** general learning-to-learn or AGI.
- No single weighted aggregate score is computed (`aggregate_score: false`, `weighting: null`). Every category, configuration, and resource dimension is reported separately.
- Missing host binaries (specifically Lean 4's `lean` executable when not installed on the local macOS host) are reported honestly as `blocked_missing_runtime` and never replaced by a mock or counted as a verified external proof check.

---

## 2. Compared Configurations & Controls

All configurations run in counterbalanced/randomized order (`order_seed: 20261023`) with isolated workspaces and caches:

1. **Configuration A (`model_tools_editor`)**:
   - Same local runtime, tools, context, and stateful program/code/constraint editors, but without cross-task template caching or cross-profile capsule transfer.
2. **Configuration B (`ordinary_cache_templates_retrieval`)**:
   - Configuration A + strong ordinary exact caching, parameterized templates, and local document/snapshot retrieval.
3. **Configuration C (`nexus_symbiotic_abstractions`)**:
   - Configuration B + NEXUS acquired abstractions, stateful AST capsule rebinding across schemas, and cross-profile stigmergic capsule exchange (`Profile A` $\to$ `Profile B` with sandbox probe revalidation).
4. **Controls**:
   - `nexus_reset_memory`: Resets saved procedures and capsules before transfer tasks to isolate the effect of persisted state.
   - `nexus_wrong_memory`: Seeds a deliberately incompatible/wrong capsule in memory to verify that precondition and behavioral probe checks reject inappropriate reuse rather than corrupting execution.

---

## 3. Independent Verification & Tamper Detection

`scripts/verify_seed_symbiotic_workbench.py` independently reconstructs expected outputs from the locked task specifications in `configs/seed_symbiotic_workbench_v1.json` and raw workspace files without invoking model inference, verifies hash chains and resource ledgers, and executes automated corruption/tamper rejection tests.
