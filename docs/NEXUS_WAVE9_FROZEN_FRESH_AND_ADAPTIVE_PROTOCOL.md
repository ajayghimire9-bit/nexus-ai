# NEXUS Wave-9 Frozen-Fresh Holdout & Self-Adaptive Protocol

- **Branch**: `cursor/seed-wave9-frozen-fresh-and-adaptive` (branched from `bf66447`)
- **Frozen Reference Commit**: `bf66447` (`cursor/seed-wave8-deconfounded-equal-capability`)
- **Pinned `deconfounded_equal_capability.py` SHA-256**: `ef0bceb9e10d9f14febdb0df75a6516a9413878f3aa2d63177dda212de37fe1e`
- **Track B Status**: Closed (`0` language-model calls, `0 s` frozen 1.5B ledger debit)
- **Strict Single-Shot Scoring Rule**: All learner code, fresh holdout task definitions (`w9f_*`), seed permutations, and verifier checks are committed and locked in **Commit 1** before executing the benchmark runner or opening any `w9f_*` private world. Zero code or task edits are permitted after the benchmark runs (`git diff Commit_1 -- src/ scripts/ tests/` must be empty).

---

## 1. Part 1: Frozen `bf66447` 4-Method Comparison on a Genuinely Fresh Holdout Suite

1. **Strict Freeze of [src/nexus/seed/deconfounded_equal_capability.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/src/nexus/seed/deconfounded_equal_capability.py)**:
   - Zero lines of `deconfounded_equal_capability.py` are modified.
   - [scripts/verify_wave9_frozen_fresh_comparison.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/scripts/verify_wave9_frozen_fresh_comparison.py) verifies that its SHA-256 digest equals `ef0bceb9e10d9f14febdb0df75a6516a9413878f3aa2d63177dda212de37fe1e`.
2. **The 4 Required Frozen `bf66447` Methods**:
   - `persistent_nexus_full` (**Full NEXUS** — frozen from `bf66447`)
   - `persistent_nexus_pruning_disabled` (**NEXUS without pruning** — frozen from `bf66447`)
   - `ordinary_persistent_memoization` (**Ordinary persistent memoization** — frozen from `bf66447`)
   - `equal_scratch` (**Equal-capability scratch** — frozen from `bf66447`)
3. **Genuinely Fresh 14-Task Holdout Stream (`w9f_*` in [src/nexus/seed/mechanism_wave9_fresh_holdout.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/src/nexus/seed/mechanism_wave9_fresh_holdout.py))**:
   - **G1 Analogous (`2` tasks)**: `w9f_g1_even_append`, `w9f_g1_odd_dup` (fresh confirmation and private inputs).
   - **G2 Misleading Lookalikes (`2` tasks)**: `w9f_g2_len2_append_q` (`seq_len2_append_q`), `w9f_g2_len0_append_hash` (`seq_len0_append_hash`).
   - **L1 Invention, Compositional Reuse & Spurious (`3` tasks)**: `w9f_l1_inv_palindrome_z` (`seq_palindrome_z`), `w9f_l1_reuse_palindrome_m` (`seq_palindrome_m`), `w9f_l1_spurious_len_ge3_z` (`seq_len_ge3_z`).
   - **L2 Invention, Complete L2 Skill Reuse & Composition (`3` tasks)**: `w9f_l2_inv_pal_drop_head_bang` (`seq_pal_drop_head_bang`), `w9f_l2_reuse_full_drop_head_bang` (`seq_pal_drop_head_bang` on fresh confirmation/private inputs), `w9f_l2_compose_pal_swap_bang` (`seq_pal_swap_bang`).
   - **Delayed Post-Prune Reuse (`1` task)**: `w9f_delayed_len_ge3_hash` (`seq_len_ge3_hash`, arriving after an inactive window in Seeds 0 and 2 and immediately after `w9f_l1_spurious_len_ge3_z` in Seed 1).
   - **Ambiguous, OOG & Domain A Retention (`3` tasks)**: `w9f_amb_alias_odd` (`seq_odd_dup` under `alias_ambiguous`), `w9f_oog_vowel_shift` (`seq_vowel_shift`), `w9f_retain_domain_a_even3` (`w5_even_add3`, Domain A).

---

## 2. Part 2: Pre-Registered `wave9_self_adaptive_nexus` Learner

Implemented in [src/nexus/seed/wave9_learned_abstraction_meta_control.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/src/nexus/seed/wave9_learned_abstraction_meta_control.py) under the exact same label-blind `solve_unfamiliar_task(self, env, public_budget)` interface and universal catalog:
1. **Two-Tier Active Beam + Cold Signature Archive (`cold_archive_reactivate`)**:
   - When `usage_age_prune(min_age=2, min_uses=2)` demotes an unpinned inactive operator from the active beam, it moves the operator into `cold_archive` instead of deleting it.
   - When active beam + base search misses on a delayed-reuse task, `cold_archive_reactivate` checks `cold_archive` (`archive_lookup_evals` charged explicitly in `codegen_plus_synthesis` and `total_work`) and reactivates matching operators without re-enumerating `MICRO_PREDICATE_GRAMMAR` or re-paying `operator_compile_cost`.
2. **AST Subtree MDL Compression (`compress_solved_programs_mdl`)**:
   - Inspects solved program ASTs (`compression_evals` charged explicitly in `total_work`) and pins sub-predicates and macro-skills whose description length across solved programs satisfies `DL(library_with_op) + sum(DL(prog_i | op)) <= DL(library_without_op) + sum(DL(prog_i))`.
3. **Online Empirical ROI Gate Meta-Controller (`empirical_roi_gate_policy`)**:
   - Evaluates each unique prerequisite invariant (`alphabet_closed`) at most once per task boundary and tracks running `total_candidate_evals_avoided` vs `total_gate_evals_spent`.
