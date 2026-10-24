# NEXUS Wave-9 Frozen-Fresh Holdout & Self-Adaptive Results

- **Artifact**: [artifacts/seed_wave9_frozen_fresh_and_adaptive.json](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/artifacts/seed_wave9_frozen_fresh_and_adaptive.json)
- **Artifact Digest**: `40dc63d4a39f4921b71fda579e3fd066eb66df2552127d947771aeebf31c7e11`
- **Pre-Scoring Protocol & Code Lock Commit**: `f5741a6` (`git diff f5741a6 -- src/ scripts/ tests/` is empty — zero code, task, seed, or budget changes occurred after private evaluations ran)
- **Pinned `deconfounded_equal_capability.py` SHA-256 (`bf66447`)**: `ef0bceb9e10d9f14febdb0df75a6516a9413878f3aa2d63177dda212de37fe1e` (`"frozen_learner_sha256_verified": true`)
- **Reconstructing I/O & AST Verifier**: [scripts/verify_wave9_frozen_fresh_comparison.py](file:///Users/ajayghimire/.gemini/antigravity/scratch/nexus-ai/scripts/verify_wave9_frozen_fresh_comparison.py) $\to$ `"valid": true`, `"rows_verified": 210`
- **Track B Status**: Closed (`0` language-model calls, `0 s` frozen 1.5B ledger debit)

---

## 1. Suite-Wide Summary: 4 Frozen `bf66447` Methods + `wave9_self_adaptive_nexus` (`210` Cells = `3` Seeds $\times$ `14` Fresh `w9f_*` Tasks)

| Method | Frozen `bf66447`? | Mapping / Private Correct | Schema + Role Cost | Gate Evals | Archive Lookup Evals | MDL Compress Evals | Synthesis Evals | Micro Codegen Evals | Compile Cost | Codegen + Synthesis | Total Work (`3` Seeds) | Per-Seed Total Work (`mean / min / max`) | L1 Sub-Pred Reused | Complete L2 Skill Reused | Memoized Prog Reused | Cold Archive Reactivated |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `equal_scratch` | **Yes** | `42/42` (`100%`) | `0 + 0` | `0` | `0` | `0` | `2058` | `321` | `0` | `2379` | `3525` | `1175.0 / 1175 / 1175` | `0` | `0` | `0` | `0` |
| `ordinary_persistent_memoization` | **Yes** | `42/42` (`100%`) | `0 + 0` | `0` | `0` | `0` | `2133` | `276` | `0` | `2409` | `3555` | `1185.0 / 1184 / 1187` | `0` | `0` | `3` | `0` |
| `persistent_nexus_pruning_disabled` | **Yes** | `42/42` (`100%`) | `36 + 168` | `103` | `0` | `0` | `1742` | `161` | `72` | **`1903`** | **`3428`** | `1142.67 / 1087 / 1209` | `15` | `3` | `0` | `0` |
| `persistent_nexus_full` | **Yes** | `42/42` (`100%`) | `36 + 168` | `83` | `0` | `0` | `1869` | `200` | `84` | `2069` | `3586` | `1195.33 / 1180 / 1211` | `12` | `3` | `0` | `0` |
| `wave9_self_adaptive_nexus` | Pre-Reg Wave-9 | `42/42` (`100%`) | `36 + 168` | **`26`** | `18` | `198` | `1920` | **`159`** | `72` | `2097` | `3743` | `1247.67 / 1217 / 1291` | `15` | `2` | `0` | **`3`** |

---

## 2. Group-by-Group Breakdown (`codegen_plus_synthesis / total_work`, Private Correctness)

| Task Group (`w9f_*`) | `equal_scratch` (Frozen `bf66447`) | `ordinary_persistent_memoization` (Frozen `bf66447`) | `persistent_nexus_pruning_disabled` (Frozen `bf66447`) | `persistent_nexus_full` (Frozen `bf66447`) | `wave9_self_adaptive_nexus` (Pre-Reg Wave-9) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **G1 Analogous (`6` cells)** | **`72 / 234`** (`6/6`) | `100 / 262` (`6/6`) | `122 / 368` (`6/6`) | `110 / 355` (`6/6`) | `110 / 375` (`6/6`) |
| **G2 Lookalikes (`6` cells)** | **`225 / 387`** (`6/6`) | `254 / 416` (`6/6`) | `290 / 532` (`6/6`) | `282 / 520` (`6/6`) | `282 / 545` (`6/6`) |
| **G1 + G2 Combined (`12` cells)** | **`297 / 621`** (`12/12`) | `354 / 678` (`12/12`) | `412 / 900` (`12/12`) | `392 / 875` (`12/12`) | `392 / 920` (`12/12`) |
| **L1 Invention & Reuse (`9` cells)** | `708 / 951` (`9/9`) | `746 / 989` (`9/9`) | `589 / 935` (`9/9`) | **`581 / 926`** (`9/9`) | `581 / 963` (`9/9`) |
| **L2 Composition & Reuse (`9` cells)** | `630 / 873` (`9/9`) | `492 / 735` (`9/9`) | `425 / 748` (`9/9`) | **`414 / 736`** (`9/9`) | `462 / 830` (`9/9`) |
| **L1 + L2 Combined (`18` cells)** | `1338 / 1824` (`18/18`) | `1238 / 1724` (`18/18`) | `1014 / 1683` (`18/18`) | **`995 / 1662`** (`18/18`) | `1043 / 1793` (`18/18`) |
| **Delayed Post-Prune (`3` cells)** | `324 / 405` (`3/3`) | `357 / 438` (`3/3`) | **`57 / 152`** (`3/3`) | `262 / 361` (`3/3`) | `240 / 350` (`3/3`) |
| **Ambiguous (`3` cells)** | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) | `0 / 96` (`3/3`) |
| **OOG Vowel Shift (`3` cells)** | **`282 / 363`** (`3/3`) | `322 / 403` (`3/3`) | `282 / 381` (`3/3`) | `282 / 376` (`3/3`) | `284 / 368` (`3/3`) |
| **Domain A Retain (`3` cells)** | `138 / 216` (`3/3`) | `138 / 216` (`3/3`) | `138 / 216` (`3/3`) | `138 / 216` (`3/3`) | `138 / 216` (`3/3`) |

---

## 3. Findings from the Single-Shot Pre-Registered Evaluation

### A. Frozen `bf66447` 4-Method Comparison on Fresh `w9f_*` Tasks
1. **100% Solve Rate Across All 4 Frozen Methods (`42/42`)**: Without touching a single line of `deconfounded_equal_capability.py`, all 4 frozen `bf66447` methods solve `42/42` (`100%` mapping and private test accuracy) on the unseen `w9f_*` holdout suite.
2. **Where Frozen `persistent_nexus_full` Wins**:
   - **L1 + L2 Invention, Reuse & Composition (`18` cells)**: `persistent_nexus_full` achieves the **lowest `codegen_plus_synthesis` (`995`) and lowest `total_work` (`1662`) of all 5 methods**, beating `persistent_nexus_pruning_disabled` (`1014 / 1683`), `ordinary_persistent_memoization` (`1238 / 1724`), and `equal_scratch` (`1338 / 1824`).
   - **OOG Abstention (`w9f_oog_vowel_shift`)**: `persistent_nexus_full` (`282 / 376`) beats `persistent_nexus_pruning_disabled` (`282 / 381`) and `ordinary_persistent_memoization` (`322 / 403`).
3. **Where Frozen `persistent_nexus_full` Loses**:
   - **G1 and G2 Base Tasks**: `equal_scratch` (`297 / 621`) and `ordinary_persistent_memoization` (`354 / 678`) beat `persistent_nexus_full` (`392 / 875`) because the fresh G2 lookalike mechanisms (`seq_len2_append_q` and `seq_len0_append_hash`) are not in the 3 Domain A parity/symmetry schemas (`schema_prioritized_specs()` checks the 3 schema-prioritized specs first before scanning the remaining base specs), and in Seeds 1 and 2 evolved L1/L2 operators are checked before base specs.
   - **Delayed Post-Prune Reuse (`w9f_delayed_len_ge3_hash`)**: `persistent_nexus_pruning_disabled` (`57 / 152`) beats `persistent_nexus_full` (`262 / 361`) because `usage_age_prune` drops `len_ge3` in Seeds 0 and 2 before `w9f_delayed_len_ge3_hash` arrives, giving `persistent_nexus_pruning_disabled` the lowest suite-wide work (`1903 / 3428`).

### B. Pre-Registered `wave9_self_adaptive_nexus` Analysis
1. **What Improved Over Frozen `persistent_nexus_full`**:
   - **Cold Signature Archive Reactivation on Delayed Reuse**: Reactivated `len_ge3` (`cold_archive_reactivated = 3`), eliminating micro-codegen re-enumeration (`159` suite `micro_codegen_evals` vs `200` for `persistent_nexus_full`, the lowest of all 5 methods) and eliminating duplicate compile cost (`72` vs `84`), reducing `delayed` work from `262 / 361` to `240 / 350`.
   - **Empirical ROI Gate Meta-Controller**: Reduced suite-wide `gate_evals` by **`68.7%`** (`26` vs `83` in `persistent_nexus_full` and `103` in `persistent_nexus_pruning_disabled`), reducing OOG total work from `376` to `368`.
2. **Where Metered Meta-Control Costs Hurt `wave9_self_adaptive_nexus` (Reported Directly Without Post-Hoc Tuning)**:
   - **Metered `compression_evals` (`198` units)**: Scanning `solved_program_history` after each solved sequence task added `198` explicitly metered `compression_evals` to `total_work`.
   - **Single-Use Macro-Skill Demotion in Seed 2**: Because `compress_solved_programs_mdl` required `count >= 2` uses before MDL-pinning a macro-skill (`6 + 2*1 <= 2*6`), in Seed 2 where `w9f_l2_compose_pal_swap_bang` and `w9f_l1_reuse_palindrome_m` arrived between `w9f_l2_inv_pal_drop_head_bang` (step 7) and `w9f_l2_reuse_full_drop_head_bang` (step 9), `macro_palindrome_pred_drop_head_bang_tf` was demoted to `cold_archive` at step 8 (`l2_full_skill_reused = 2` instead of `3`), adding `48` extra L2 `codegen_plus_synthesis` evaluations in Seed 2 (`462` vs `414`).
