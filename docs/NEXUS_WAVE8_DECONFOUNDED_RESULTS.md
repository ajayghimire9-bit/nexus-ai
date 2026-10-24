# NEXUS Wave-8 Deconfounded Equal-Capability Results

- **Artifact**: [artifacts/seed_wave8_deconfounded_equal_capability.json](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/artifacts/seed_wave8_deconfounded_equal_capability.json)
- **Artifact Digest**: `611461d475f5dcb8fd7b1ae3a9be365419793800241b8b035658571cc973d586`
- **Reconstructing I/O & AST Verifier**: [scripts/verify_wave8_deconfounded_equal_capability.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/scripts/verify_wave8_deconfounded_equal_capability.py) $\to$ `"valid": true`, `"rows_verified": 252`, `"ast_clean": true`
- **Track B Status**: Closed (`0` language-model calls, `0 s` frozen 1.5B ledger debit)

---

## 1. Suite-Wide Summary Across All 6 Equal-Capability Methods (`252` Cells = `3` Seeds $\times$ `14` Tasks)

| Method | Mapping Correct | Private Correct | False Lock / False Unique | Schema Distill Cost | Role Probe Cost | Gate Evals | Synthesis Evals | Micro Codegen Evals | Compile Cost | Codegen + Synthesis | Total Work (`3` Seeds) | Per-Seed Total Work (`mean / min / max`) | L1 Sub-Pred Reused | Complete L2 Skill Reused | Memoized Prog Reused |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `equal_scratch` | `42/42` | `42/42` | `0 / 0` | `0` | `0` | `0` | `1989` | `279` | `0` | `2268` | `3414` | `1138.0 / 1138 / 1138` | `0` | `0` | `0` |
| `ordinary_persistent_memoization` | `42/42` | `42/42` | `0 / 0` | `0` | `0` | `0` | `2066` | `234` | `0` | `2300` | `3446` | `1148.67 / 1147 / 1150` | `0` | `0` | `3` |
| `persistent_nexus_hierarchy_disabled` | `42/42` | `42/42` | `0 / 0` | `36` | `168` | `39` | `1759` | `260` | `36` | `2019` | `3444` | `1148.0 / 1133 / 1159` | `13` | `0` | `0` |
| `persistent_nexus_gate_disabled` | `42/42` | `42/42` | `0 / 0` | `36` | `168` | `0` | `1630` | `174` | `84` | `1804` | `3238` | `1079.33 / 1062 / 1095` | `13` | `3` | `0` |
| `persistent_nexus_pruning_disabled` | `42/42` | `42/42` | `0 / 0` | `36` | `168` | `103` | `1463` | `140` | `72` | `1603` | `3128` | `1042.67 / 996 / 1082` | `16` | `3` | `0` |
| `persistent_nexus_full` | `42/42` | `42/42` | `0 / 0` | `36` | `168` | `83` | `1568` | `165` | `84` | `1733` | `3250` | `1083.33 / 1071 / 1107` | `13` | `3` | `0` |

---

## 2. Group-by-Group Breakdown (`codegen_plus_synthesis / total_work`, Private Correctness)

| Task Group | `equal_scratch` | `ordinary_persistent_memoization` | `persistent_nexus_hierarchy_disabled` | `persistent_nexus_gate_disabled` | `persistent_nexus_pruning_disabled` | `persistent_nexus_full` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **G1 Analogous (`6` cells)** | **`72 / 234`** (`6/6`) | `106 / 268` (`6/6`) | `99 / 336` (`6/6`) | `113 / 343` (`6/6`) | `128 / 374` (`6/6`) | `113 / 358` (`6/6`) |
| **G2 Lookalikes (`6` cells)** | `249 / 411` (`6/6`) | `290 / 452` (`6/6`) | **`75 / 309`** (`6/6`) | `79 / 309` (`6/6`) | `83 / 325` (`6/6`) | `79 / 317` (`6/6`) |
| **G1 + G2 Combined (`12` cells)** | `321 / 645` (`12/12`) | `396 / 720` (`12/12`) | **`174 / 645`** (`12/12`) | `192 / 652` (`12/12`) | `211 / 699` (`12/12`) | `192 / 675` (`12/12`) |
| **L1 Invention & Reuse (`9` cells)** | `627 / 870` (`9/9`) | `665 / 908` (`9/9`) | **`496 / 837`** (`9/9`) | `505 / 840` (`9/9`) | `513 / 859` (`9/9`) | `505 / 850` (`9/9`) |
| **L2 Composition & Reuse (`9` cells)** | `678 / 921` (`9/9`) | `529 / 772` (`9/9`) | `762 / 1022` (`9/9`) | **`441 / 736`** (`9/9`) | `452 / 775` (`9/9`) | `441 / 763` (`9/9`) |
| **L1 + L2 Combined (`18` cells)** | `1305 / 1791` (`18/18`) | `1194 / 1680` (`18/18`) | `1258 / 1859` (`18/18`) | **`946 / 1576`** (`18/18`) | `965 / 1634` (`18/18`) | `946 / 1613` (`18/18`) |
| **Delayed Post-Prune (`3` cells)** | `264 / 345` (`3/3`) | `292 / 373` (`3/3`) | `209 / 302` (`3/3`) | `217 / 306` (`3/3`) | **`49 / 144`** (`3/3`) | `217 / 316` (`3/3`) |
| **Ambiguous (`3` cells)** | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) |
| **OOG Caesar (`3` cells)** | **`282 / 363`** (`3/3`) | `322 / 403` (`3/3`) | `282 / 368` (`3/3`) | `353 / 434` (`3/3`) | `282 / 381` (`3/3`) | `282 / 376` (`3/3`) |
| **Domain A Retain (`3` cells)** | `96 / 174` (`3/3`) | `96 / 174` (`3/3`) | `96 / 174` (`3/3`) | `96 / 174` (`3/3`) | `96 / 174` (`3/3`) | `96 / 174` (`3/3`) |

---

## 3. Key Findings After Removing All Four Confounds

1. **The `30/36` vs `36/36` Solve Gap in `4cac886` Disappears Under Equal Capability**:
   - Once `equal_scratch`, `ordinary_persistent_memoization`, and `persistent_nexus_hierarchy_disabled` are given the same universal catalog (`rotate_bang_tf`, `rotate_q_tf`) and full L2 composition depth, **all 6 methods achieve `42/42` (`100%`) private correctness**. Hierarchical evolution is a search-efficiency mechanism on compositional tasks, not an accuracy gate.
2. **Where `persistent_nexus_full` Loses or Ties Once Costs and Catalogs Are Equalized**:
   - **G1 and G1+G2 Total Work**: Once one-time `schema_distill_cost` (`36`) and `role_probe_cost` (`168`) are charged in the raw rows where schemas are first distilled, and task arrival orders are permuted across seeds so evolved operators are checked before base operators when L1/L2 tasks precede G1/G2, `equal_scratch` beats `persistent_nexus_full` on G1 (`234` vs `358` total work) and on G1+G2 total work (`645` vs `675`), even though `persistent_nexus_full` uses fewer `codegen_plus_synthesis` evaluations on G1+G2 (`192` vs `321`).
   - **Exact Whole-Program Reuse vs Compositional Reuse**: On `w8d_l2_reuse_full_rotate_bang` (where the complete `seq_pal_rotate_bang` mechanism repeats on new confirmation/private inputs), `ordinary_persistent_memoization` ties `persistent_nexus_full` on synthesis evaluations (`5` vs `5` per seed) and pays `0` gate evaluations (`memoized_program_reused = 3`). Whole-program memoization only falls behind when a learned sub-predicate (`palindrome_pred`) must be re-composed with a *different* transform (`w8d_l1_reuse_palindrome_q` and `w8d_l2_compose_pal_rotate_q`), where `persistent_nexus_full` beats `ordinary_persistent_memoization` (`946` vs `1194` `codegen_plus_synthesis` on L1+L2).
   - **Delayed Post-Prune Reuse (`w8d_delayed_first_last_hash`)**: In Seeds 0 and 2, `w8d_delayed_first_last_hash` arrives after `usage_age_prune(min_age=2, min_uses=2)` has already pruned `first_eq_last`, forcing `persistent_nexus_full` to re-invent and re-compile `first_eq_last` (`132` and `137` work units vs `46` and `54` for `persistent_nexus_pruning_disabled`). In Seed 1, where the permuted task arrival order places `w8d_delayed_first_last_hash` immediately after `w8d_l1_spurious_first_last_z` (`age = 1 < 2`), `persistent_nexus_full` reuses `first_eq_last` in `46` work units and retains it for the rest of Seed 1. Because of the Seed 0 and Seed 2 re-invention penalty, `persistent_nexus_pruning_disabled` achieves lower suite-wide total work (`3128`) than `persistent_nexus_full` (`3250`).
   - **Prerequisite Gate Overhead vs Single-Task OOG Savings**: On `w8d_oog_caesar`, the `alphabet_closed` prerequisite gate reduces `persistent_nexus_full` work relative to `persistent_nexus_gate_disabled` (`282` vs `353` `codegen_plus_synthesis`, `376` vs `434` total work across 3 seeds). However, because the suite contains only `1` OOG task (`3` cells) and `12` in-grammar sequence tasks (`36` cells) where `persistent_nexus_full` pays `83` cumulative `gate_evals`, `persistent_nexus_gate_disabled` finishes `12` work units ahead on suite-wide `total_work` (`3238` vs `3250`), while `persistent_nexus_full` wins on `codegen_plus_synthesis` (`1733` vs `1804`).
