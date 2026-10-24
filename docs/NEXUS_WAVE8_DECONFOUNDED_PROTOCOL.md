# NEXUS Wave-8 Deconfounded Equal-Capability Protocol

- **Branch**: `cursor/seed-wave8-deconfounded-equal-capability` (branched from `4cac886`)
- **Deconfounds Commit**: `4cac886` (`cursor/seed-wave8-hierarchical-gated-evolution`)
- **Track B Status**: Closed (`0` language-model calls, `0 s` frozen 1.5B ledger debit)
- **Mechanism Status**: Engineer-written symbolic synthesis, relational schema distillation, prerequisite gating, and usage/age pruning (`learning_to_learn_established = false`).

---

## 1. Audit of the Four Confounds in `4cac886`

Code inspection of `4cac886` ([src/nexus/seed/hierarchical_gated_evolution.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/src/nexus/seed/hierarchical_gated_evolution.py) and [src/nexus/seed/mechanism_wave8_hierarchical.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/src/nexus/seed/mechanism_wave8_hierarchical.py)) identified four implementation confounds:

1. **Label Leakage (`stage` passed into synthesis)**:
   - `run_domain_b` computed `stage = str(task.get("stage") or "g1")` and `allow_micro = stage in {"l1", "l2", "oog"}` and passed both into `synthesize_wave8(...)`.
   - Inside `synthesize_wave8`, `if evolved_specs and stage != "l2":` and `if allow_l2 and pred_hint is not None and stage == "l2":` branched directly on the task's ground-truth stage label.
2. **Unequal Catalogs on `"l2"` (`30/36` vs `36/36` solve gap was caused by catalog denial)**:
   - On `"l2"`, `NEXUS` and `HIER_UNGATED` searched a 2-item `_l2_catalog()` (`rotate_bang_tf`, `rotate_q_tf`), whereas `SCRATCH` and `STATIC` called `synthesize_sequence(...)`, which only searched `MICRO_CANDIDATES` (`kind == "predicate"`) and never had access to `rotate_bang_tf` or `rotate_q_tf`.
3. **Unequal Catalogs on `"oog"`**:
   - On `"oog"`, `synthesize_wave8` executed `elif stage == "oog" and not gated: catalog = MICRO_CANDIDATES + DEEP_L2_L0`, handing ungated methods an enlarged 55-item catalog while gated methods never received `DEEP_L2_L0`.
4. **Omitted Schema Cost, Misnamed Pruning, L1-Only Reuse on L2, and Non-Reconstructing Verifier**:
   - `run_wave8` set `distill_left = extra.schema_distill_cost if method in {STATIC, WAVE7, HIER_UNGATED} else 0`, recording `schema_distill_cost = 0` in raw rows for `NEXUS` and `FLAT_GATED`.
   - `mdl_prune` did not compute description length; it deactivated operators with `uses <= 1` after one task (`age/use-count` heuristic).
   - On `w8b_reuse_pal_rotate`, `NEXUS` reused L1 `palindrome_pred` to search for `rotate_q_tf` rather than reusing the complete L2 `palindromic_rotate_bang` skill.
   - `verify_payload` only summed integer cost fields and checked boolean flags rather than reconstructing and executing the discovered program AST on saved public and private I/O pairs.

---

## 2. Deconfounded Equal-Capability Rules Locked Before Scoring

### Rule 1: AST-Verified Label-Blind Learner Interface
- `EqualCapabilityLearner.solve_unfamiliar_task(self, env, public_budget)` in [src/nexus/seed/deconfounded_equal_capability.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/src/nexus/seed/deconfounded_equal_capability.py) accepts **only** `(env, public_budget)`.
- `scripts/verify_wave8_deconfounded_equal_capability.py` parses the Python AST of `src/nexus/seed/deconfounded_equal_capability.py` and fails if any function parameter or string literal references `task_id`, `stage`, `split`, `g1`, `g2`, `l1`, `l2`, `oog`, `amb`, or `retain`.

### Rule 2: Identical Universal Catalog and L2 Depth for All 6 Methods
Every method receives the exact same universal catalog on every task:
- `base_predicates` (`7` predicates: `len_even`, `len_odd`, `len_eq0`, `len_eq1`, `len_eq2`, `len_in_0_2`, `always`)
- `base_transforms` (`7` transforms: `identity`, `append_m`, `append_q`, `append_hash`, `append_z`, `duplicate`, `reverse`)
- `micro_predicates` (`8` micro-predicates from `MICRO_CANDIDATES`, including `palindrome_pred` and `first_eq_last`)
- `extension_transforms` (`4` Level-2 transforms: `swap_bang_tf`, `drop_head_bang_tf`, `rotate_bang_tf`, `rotate_q_tf`)

### Rule 3: Honest Cost Accounting & Naming
- `schema_distill_cost > 0` is recorded in the raw row of the first sequence task for every schema-using method (`12` probe evaluations per seed, `36` across 3 seeds), alongside `role_probe_cost` (`56` per seed, `168` across 3 seeds).
- Every `(candidate, observation)` pair evaluated in memoization, macro-skill, evolved-spec, base-spec, and extension search increments `synthesis_evals` or `micro_codegen_evals` by `+1`.
- Pruning is named `usage_age_prune(min_age=2, min_uses=2)` (never `mdl_prune`).
- Both `l1_sub_predicate_reused` and `l2_full_skill_reused` (reusing the complete `palindromic_rotate_bang` macro-skill) are tracked separately.

### Rule 4: Six Equal-Capability Methods, Permuted Seed Task Orders, and Delayed Reuse After Pruning
1. `equal_scratch`: No cross-task memory, full universal catalog and L2 depth.
2. `ordinary_persistent_memoization`: Persistent whole-program memoization across tasks, full universal catalog and L2 depth.
3. `persistent_nexus_hierarchy_disabled`: Persistent L1 predicate bank, gate, and pruning, but no L2 transform/macro-skill promotion into the persistent store (still searches L2 extension catalog jointly on every L2 task).
4. `persistent_nexus_gate_disabled`: Persistent L1+L2 hierarchical store and pruning, with prerequisite gate disabled (`use_gate=False`).
5. `persistent_nexus_pruning_disabled`: Persistent L1+L2 hierarchical store and prerequisite gate, with `usage_age_prune` disabled (`use_pruning=False`).
6. `persistent_nexus_full`: Persistent L1+L2 hierarchical store, prerequisite gate, and `usage_age_prune`.

All 6 methods are evaluated across `14` fresh `w8d_*` tasks (`252` cells across `seeds = (0, 1, 2)`), where each seed uses a **distinct task arrival order** (`TASK_ORDERS_BY_SEED`) and includes `w8d_delayed_first_last_hash` (`seq_first_last_hash`) to test delayed reuse after `usage_age_prune` drops `first_eq_last`.
