# NEXUS Wave-10 Pre-Registered Protocol: Atomic Self-Evolving Operators & Cost-Ordered Meta-Control

## 1. Scientific Rule (Two-Commit Blind Protocol)
1. **Commit 1 (`Protocol + Code + Fresh Atomic Suite Lock`):** Commit this protocol, `src/nexus/seed/wave10_atomic_self_evolving_learner.py`, `src/nexus/seed/mechanism_wave10_atomic_evolution.py`, `scripts/run_wave10_atomic_self_evolving.py`, `scripts/verify_wave10_atomic_self_evolving.py`, and `tests/test_seed_wave10_atomic_self_evolving.py` **before** executing the benchmark runner or inspecting any private outcome.
2. **Commit 2 (`Single-Shot Scoring Run`):** Execute `scripts/run_wave10_atomic_self_evolving.py` once, verify `git diff <Commit_1> -- src/ scripts/ tests/` is **100% empty**, and report all raw outcomes without post-hoc edits.

## 2. Three Architectural Fixes Over `d0a8bb1` (`wave9_self_adaptive_nexus`)
1. **Fix 1 — Base-First Cost-Ordered Search Beam (`Tier 0 -> Tier 1`):**
   - Tier 0 (memoized whole programs + partition-filtered atomic depth-1 base catalog) runs **before** Tier 1 (active evolved L1/L2 operators gated once per task boundary by the Empirical ROI Gate).
   - Evolving L1/L2 operators never adds beam-order or gate overhead to `G1`/`G2` base tasks.
2. **Fix 2 — Pre-Synthesis $O(1)$ Cold Signature Archive Lookup (`Tier 2` before `Tier 3`):**
   - Tier 2 (`cold_archive_reactivate`) runs immediately after Tier 1 misses and **before** Tier 3 multi-node atomic AST synthesis, and composite L2 macro-skills are MDL-pinned non-destructively.
3. **Fix 3 — Event-Triggered Wake-Sleep AST Subtree MDL Consolidation:**
   - `compress_solved_programs_mdl` executes **only** when new multi-node AST structure or a new composite macro is discovered (`structure_discovered=True`), eliminating the eager per-task scan tax on Tier-0/1/2 hits.

## 3. Universal Atomic-Only Starting Catalog & 6 Equal-Capability Methods
All 6 methods start with the **exact same atomic depth-1 catalog** (`7` atomic base predicates, `7` atomic base transforms, and `10` atomic sequence combinators that enumerate `6` multi-node predicate ASTs and `6` multi-node transform ASTs bottom-up in Tier 3):
1. `equal_atomic_scratch`
2. `ordinary_persistent_memoization`
3. `atomic_nexus_predicate_evolution_only`
4. `atomic_nexus_pruning_disabled`
5. `wave9_frozen_adaptive_rules`
6. `wave10_self_evolving_nexus`

## 4. Fresh 16-Task Atomic Suite (`288` Cells = `3 Seeds x 6 Methods x 16 Tasks`)
- `2` Base Depth-1 Tasks (`w10a_g1_even_append`, `w10a_g1_odd_dup`)
- `2` Lookalike Boundary Tasks (`w10a_g2_len2_append_q`, `w10a_g2_len0_append_hash`)
- `4` Stepwise Operator-Evolution Tasks (`w10a_step_pred_pal_z`, `w10a_step_pred_pal_m_reuse`, `w10a_step_tf_even_rot_bang`, `w10a_step_tf_odd_drop_bang`)
- `3` Deep Multi-Operator Compositional Tasks (`w10a_deep_pal_rot_bang`, `w10a_deep_pal_rot_bang_reuse`, `w10a_deep_pal_drop_bang`)
- `2` Spurious Once-Used Operator Tasks (`w10a_spurious_head_eq_last_z`, `w10a_spurious_len_ge3_z`)
- `1` Delayed Post-Prune Reuse Task (`w10a_delayed_len_ge3_q`)
- `2` Safety Tasks (`w10a_amb_alias_odd`, `w10a_oog_vowel_shift`)

## 5. Pre-Registered Acceptance Gates
- **Gate 1 (Equal Atomic Starting Catalog & Label-Blindness):** `wave10_ast_audit.ast_clean == True`, identical `catalog_audit` across all 288 rows, `0` `private_before_lock`, `0` `false_analogy_lock`, `0` `false_unique`, and `100%` I/O replay verification (`288/288`).
- **Gate 2 (Fixes All 3 `d0a8bb1` Overheads):**
  - `wave10_self_evolving_nexus` matches `equal_atomic_scratch` on `G1 + G2` `codegen_plus_synthesis` (`306 <= 306`).
  - `wave10_self_evolving_nexus` solves `Delayed Post-Prune Reuse` via pre-synthesis Cold Archive reactivation in `< 90` `codegen_plus_synthesis` across 3 seeds.
  - `wave10_self_evolving_nexus` reduces `compression_evals` by `> 60%` vs `wave9_frozen_adaptive_rules`.
- **Gate 3 (Genuine Self-Evolving Pareto Win):** `wave10_self_evolving_nexus` achieves the **lowest `codegen_plus_synthesis`** AND the **lowest `total_work`** of all 6 methods across the 48-episode stream.
