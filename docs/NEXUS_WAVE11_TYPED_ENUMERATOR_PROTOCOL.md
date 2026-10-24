# NEXUS Wave 11 Pre-Registered Protocol: Bounded Typed Program Enumerator & Direct AST Interpreter

**Branch:** `cursor/seed-wave11-typed-program-enumerator`  
**Parent Commit:** `f253be1` (`cursor/seed-wave10-atomic-self-evolving-operators`)  
**Track B Policy:** LLM/coding closed (`model_calls == 0`, `frozen_clock_Send == 0.0`)

---

## 1. Non-Negotiable Two-Commit Pre-Registered Protocol (`NEVER` Use `git commit --amend`)

1. **Part 1 — Forensic Recovery & Honest Disclosure of the Amended Wave-10 Run (`9afb110 -> 16bb044 -> f253be1`):**
   - Recovered original pre-amend commit `9afb1101f42972289d7c89173487ff45d7c2d0da` from `git reflog`.
   - Recovered the exact 3-line patch (`git diff 9afb110 16bb044 -- src/nexus/seed/wave10_atomic_self_evolving_learner.py`).
   - Reconstructed and saved the unamended failure artifact at `artifacts/seed_wave10_pre_amend_failed_run.json` (`hash`: `6a8493a609fd7480f45deaf9061334f81442a5de5d49aa59ac6f5fa830761562`).
   - Reclassified `16bb044 -> f253be1` in `docs/NEXUS_WAVE10_ATOMIC_SELF_EVOLVING_RESULTS.md` and `docs/NEXUS_CANONICAL_CURRENT_STATE.md` as **Developmental / Post-Amend Run (1 local commit amendment after initial run failure)**.
2. **Commit 1a (`c72a690`) -> Commit 2a (`ffa43de`, Closed `w11f_*` Attempt Without Amending):**
   - In `c72a690`, `src/nexus/seed/wave11_typed_program_enumerator.py` and `src/nexus/seed/mechanism_wave11_fresh_assessment.py` ran cleanly and produced `artifacts/seed_wave11_typed_program_enumerator.json` (`hash`: `3bd32ab59b10797fb76b13060a61a402e4fe44c547835f5db954626a15097f07`, `gates.passed == True`, `48/48` solved across all 4 methods), but the CLI wrapper `scripts/run_wave11_typed_assessment.py` raised `KeyError: 'suite_totals'` (`payload["totals"]["suite"]` vs `payload["suite_totals"]`).
   - Pursuant to the Part-3 Unconditional No-Amend Rule, `c72a690` was **never amended**; the `w11f_*` artifact was committed and closed as `"developmental / closed"` in `ffa43de`, and a brand-new unseen 16-task assessment suite `src/nexus/seed/mechanism_wave11b_fresh_assessment.py` (`w11b_*`) was constructed while keeping `src/nexus/seed/wave11_typed_program_enumerator.py` (`70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a`) 100% untouched.
3. **Commit 1b (`Pre-Assessment Code Freeze for mechanism_wave11b_fresh_assessment.py`):**
   - SHA-256 digests recorded in `scripts/verify_wave11_typed_enumerator.py`:
     - `src/nexus/seed/deconfounded_equal_capability.py`: `ef0bceb9e10d9f14febdb0df75a6516a9413878f3aa2d63177dda212de37fe1e`
     - `src/nexus/seed/wave9_learned_abstraction_meta_control.py`: `3be126c6470fc45d29a35863aea9d68ca30497756f9ef4ebbdd02c1662677143`
     - `src/nexus/seed/wave10_atomic_self_evolving_learner.py`: `3ee0a80e757f00b00bc7b73edbb2c665ac83109a59543b5a6b6b5646e62389d0`
     - `src/nexus/seed/wave11_typed_program_enumerator.py`: `70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a`
     - `src/nexus/seed/mechanism_wave11_fresh_assessment.py`: `ec99f31b07f01f4aa0dedf92584e1354a6ddf34b59984b8641b9462d015411a7`
     - `src/nexus/seed/mechanism_wave11b_fresh_assessment.py`: `adc0d49581b2d81c1b464c6f4185e77f5e2ded6460d0ef9a24cdca5799d0738e`
4. **Commit 2b (`Single-Shot Assessment Run & Results Report`):**
   - Runs `scripts/run_wave11_typed_assessment.py` (`mechanism_wave11b_fresh_assessment.py`) once and verifies `artifacts/seed_wave11b_typed_program_enumerator.json` with `scripts/verify_wave11_typed_enumerator.py`.
   - **NEVER** uses `git commit --amend`.
   - `git diff Commit_1b -- src/ scripts/ tests/` must remain **100% empty**.

---

## 2. Typed Algebraic Expression Tree (`ExprAST`) & Direct AST Interpreter

In `src/nexus/seed/wave11_typed_program_enumerator.py`, all handwritten composite candidate tables and `lambda` callables are eliminated (`lambda_count == 0` verified by Python `ast` inspection):
- **Types (`TypeTag`):** `SEQ` (`Tuple[str, ...]`), `TOK` (`str`), `INT` (`int`), `BOOL` (`bool`).
- **AST Nodes (`ExprAST`):**
  - `VarNode(name="x", out_type=TypeTag.SEQ)`
  - `ConstNode(value, out_type)`
  - `PrimOpNode(op_name, args, out_type)`
  - `EvolvedMacroNode(macro_id, body_ast, args, out_type)`
- **14 Atomic Primitive Opcodes (`ALLOWED_PRIM_OPCODES`):**
  1. `IDENTITY(x: SEQ) -> SEQ`
  2. `REVERSE(x: SEQ) -> SEQ`
  3. `HEAD(x: SEQ) -> TOK`
  4. `LAST(x: SEQ) -> TOK`
  5. `TAIL(x: SEQ) -> SEQ`
  6. `INIT(x: SEQ) -> SEQ`
  7. `LEN(x: SEQ) -> INT`
  8. `MOD2(n: INT) -> INT`
  9. `INT_EQ(a: INT, b: INT) -> BOOL`
  10. `INT_GE(a: INT, b: INT) -> BOOL`
  11. `TOK_EQ(a: TOK, b: TOK) -> BOOL`
  12. `SEQ_EQ(a: SEQ, b: SEQ) -> BOOL`
  13. `APPEND_TOK(seq: SEQ, tok: TOK) -> SEQ`
  14. `IF_THEN_ELSE(cond: BOOL, then_seq: SEQ, else_seq: SEQ) -> SEQ`
- **Direct Recursive AST Interpreter (`eval_expr_ast`):**
  - Executes `ExprAST` nodes directly without compiling Python strings or calling `lambda` objects, and increments `op_counter[0]` on every primitive opcode evaluation.

---

## 3. Incremental Size-Bounded Typed Enumerator (`TypedProgramEnumerator`)

Shared identically across all 4 methods (`equal_typed_scratch`, `ordinary_persistent_memoization`, `nexus_typed_without_pruning`, `nexus_typed_full`):
- Generates type-correct expressions of size $s = 1, 2, \dots, S_{\max}$ (`max_guard_size = 6`, `max_transform_size = 7`) bottom-up from atomic primitives, grammar constants, and active evolved `EvolvedMacroNode` operators.
- Deduplicates candidate expressions within each size tier via observational equivalence on the task's core public inputs (`4` core pairs).
- When `EvolvedMacroNode` operators are promoted into the active library with effective step cost `1`, compositional expressions (`APPEND_TOK(M_rot(x), '!')`, size `3`) are enumerated at size `3` instead of size `7` (`APPEND_TOK(APPEND_TOK(TAIL(x), HEAD(x)), '!')`).

---

## 4. Pre-Registered Acceptance Gates

1. **Gate 1 (Strict Zero-Lambda AST & Equal Grammar Check):**
   - `inspect_wave11_learner_ast` confirms `lambda_count == 0`, `prim_opcode_count == 14`, and zero forbidden stage/split/task_id string literals or attributes.
   - All 4 methods share the identical `TypedProgramEnumerator` and `ALLOWED_PRIM_OPCODES`.
2. **Gate 2 (Full 5-Term Accounting Honesty):**
   - `total_work = candidate_programs_evaluated + atomic_op_executions + ast_nodes_constructed + public_test_executions + compression_work` across all `192` cells (`3 seeds x 4 methods x 16 tasks`).
3. **Gate 3 (Cumulative Scaling & Macro Reuse):**
   - `nexus_typed_full` achieves `>=` private accuracy of `equal_typed_scratch` (`48/48` across 3 seeds), strictly lower cumulative `candidate_programs_evaluated + atomic_op_executions`, strictly lower cumulative `total_work`, and `sub_macro_reuse_count >= 1` per seed on `deep_macro_reuse`.
