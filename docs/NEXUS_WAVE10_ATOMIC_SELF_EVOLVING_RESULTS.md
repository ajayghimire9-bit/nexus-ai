# NEXUS Wave-10 Atomic Self-Evolving Operators & Cost-Ordered Meta-Control — Single-Shot Results

## 1. Two-Commit Blind Protocol Verification
- **Commit 1 (`Protocol + Code + Fresh Atomic Suite Lock`):** `16bb044`
- **Single-Shot Artifact:** `artifacts/seed_wave10_atomic_self_evolving_operators.json` (`17656be31dcbfb23bc292ed1c021362eff236d8c851c6286039a9cd73aecdc0d`)
- **Reconstructing Verifier (`scripts/verify_wave10_atomic_self_evolving.py`):** `"valid": true` across all `288` cells (`3 seeds x 6 methods x 16 tasks`).
- **Prior Learner Freeze Verification:**
  - `src/nexus/seed/deconfounded_equal_capability.py` SHA-256: `ef0bceb9e10d9f14febdb0df75a6516a9413878f3aa2d63177dda212de37fe1e` (`verified: true`)
  - `src/nexus/seed/wave9_learned_abstraction_meta_control.py` SHA-256: `3be126c6470fc45d29a35863aea9d68ca30497756f9ef4ebbdd02c1662677143` (`verified: true`)
- **Post-Lock Code Diff Check:** `git diff 16bb044 -- src/ scripts/ tests/` is **100% empty**.

---

## 2. Suite-Wide Totals Across All 6 Equal-Capability Methods (`48` Episodes per Method = `3 Seeds x 16 Tasks`)

| Method | Mapping / Private Correct | False Locks / False Unique | `synthesis_evals` | `micro_codegen_evals` | `archive_lookup_evals` | **`codegen_plus_synthesis`** | `schema + role + compile` | `gate_evals` | `compression_evals` | **`total_work`** | Per-Seed `total_work` `mean [min..max]` |
| --- | :---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |
| `equal_atomic_scratch` | `48/48` (`100%`) | `0 / 0` | `1674` | `3645` | `0` | `5319` | `0 + 0 + 0` | `0` | `0` | `6630` | `2210.0 [2210..2210]` |
| `ordinary_persistent_memoization` | `48/48` (`100%`) | `0 / 0` | `1850` | `2784` | `0` | `4634` | `0 + 0 + 0` | `0` | `0` | `5945` | `1981.67 [1978..1986]` |
| `wave9_frozen_adaptive_rules` | `48/48` (`100%`) | `0 / 0` | `2551` | `1047` | `3` | `3601` | `36 + 168 + 60` | `37` | `315` | `5528` | `1842.67 [1807..1861]` |
| `atomic_nexus_predicate_evolution_only` | `48/48` (`100%`) | `0 / 0` | `1493` | `1446` | `91` | `3030` | `36 + 0 + 36` | `27` | `108` | `4548` | `1516.0 [1511..1524]` |
| `atomic_nexus_pruning_disabled` | `48/48` (`100%`) | `0 / 0` | `1458` | `1035` | `0` | `2493` | `36 + 0 + 60` | `30` | `84` | `4014` | `1338.0 [1335..1341]` |
| **`wave10_self_evolving_nexus`** | **`48/48` (`100%`)** | **`0 / 0`** | **`1271`** | **`1035`** | **`48`** | **`2354`** | **`36 + 0 + 60`** | **`27`** | **`84`** | **`3872`** | **`1290.67 [1285..1295]`** |

---

## 3. Per-Split Breakdown (`codegen_plus_synthesis / total_work`)

| Split (`Cells per Method`) | `equal_atomic_scratch` | `ordinary_persistent_memoization` | `wave9_frozen_adaptive_rules` | `atomic_nexus_predicate_evolution_only` | `atomic_nexus_pruning_disabled` | **`wave10_self_evolving_nexus`** |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`G1` Base (`6`)** | `75 / 237` | `114 / 276` | `161 / 434` | `75 / 249` | `75 / 249` | **`75 / 249`** |
| **`G2` Lookalike (`6`)** | `99 / 261` | `142 / 304` | `313 / 521` | `99 / 261` | `99 / 261` | **`99 / 261`** |
| **`G1 + G2` Combined (`12`)** | **`174 / 498`** | `256 / 580` | `474 / 955` | **`174 / 510`** | **`174 / 510`** | **`174 / 510`** |
| **`Step-Pred` Evolution & Reuse (`6`)** | `213 / 375` | `244 / 406` | `218 / 433` | `163 / 346` | `210 / 396` | **`165 / 348`** |
| **`Step-Trans` Evolution (`6`)** | `330 / 492` | `385 / 547` | `572 / 815` | `363 / 563` | `367 / 591` | **`367 / 591`** |
| **`Deep` Multi-Operator Composition (`9`)** | `3207 / 3450` | `2225 / 2468` | `95 / 436` | `915 / 1219` | `325 / 607` | **`227 / 509`** |
| **`Spurious` Once-Used Operators (`6`)** | `210 / 372` | `232 / 394` | `631 / 976` | `218 / 440` | `218 / 440` | **`218 / 440`** |
| **`Delayed` Post-Prune Reuse (`3`)** | `69 / 150` | `119 / 200` | `324 / 446` | **`78 / 162`** | `83 / 167` | **`84 / 168`** |
| **`Ambiguous` Alias Trap (`3`)** | `0 / 96` | `0 / 96` | `0 / 96` | `0 / 96` | `0 / 96` | **`0 / 96`** |
| **`OOG` Honest Abstention (`3`)** | `1116 / 1197` | `1173 / 1254` | `1287 / 1371` | `1119 / 1203` | `1116 / 1200` | **`1119 / 1203`** |
| **Suite Total (`48`)** | `5319 / 6630` | `4634 / 5945` | `3601 / 5528` | `3030 / 4548` | `2493 / 4014` | **`2354 / 3872`** |

---

## 4. Verification of All 3 `d0a8bb1` Overhead Bottleneck Fixes & Self-Evolving Pareto Win
1. **Fix 1 — Base-First Cost-Ordered Beam (`Tier 0 -> Tier 1`):**
   - On `G1 + G2` (`12` episodes across 3 seeds), `wave10_self_evolving_nexus` cuts `codegen_plus_synthesis` from `474` (`wave9_frozen_adaptive_rules`) down to **`174`** (`-63.3%`), **matching `equal_atomic_scratch` (`174`) identically** (`0` `gate_evals` and `0` evolved-operator beam tax on base tasks even when `G1`/`G2` arrive late in permuted seeds).
2. **Fix 2 — Pre-Synthesis $O(1)$ Cold Signature Archive Lookup (`Tier 2` before `Tier 3`):**
   - On `Delayed Post-Prune Reuse` (`w10a_delayed_len_ge3_q`), `wave10_self_evolving_nexus` reactivates the demoted `ast_len_ge_3` operator in Tier 2 (`cold_archive_reactivated = 3/3`, `0` `micro_codegen_evals`) in **`84` `codegen_plus_synthesis` (`< 90`)** (`168` `total_work` vs `324 / 446` in `wave9_frozen_adaptive_rules`), while retaining full composite L2 macro reuse across all 3 seeds (`l2_full_skill_reused = 3/3`).
3. **Fix 3 — Event-Triggered Wake-Sleep AST Subtree MDL Consolidation:**
   - `wave10_self_evolving_nexus` spends **`0` `compression_evals`** on `G1`, `G2`, and `Delayed Post-Prune Reuse` (`0` vs `117` in `wave9_frozen_adaptive_rules`) and reduces suite-wide `compression_evals` from **`315` down to `84` (`-73.3%`)**.
4. **Genuine Self-Evolving Operator Advantage (`Gate 3`):**
   - Starting from a strictly atomic depth-1 catalog (`7` base predicates, `7` base transforms, `10` sequence combinators), `wave10_self_evolving_nexus` evolves multi-node predicate subtrees (`ast_eq_reverse`, `ast_len_ge_3`) and multi-node transform subtrees (`ast_rotate_left_bang`, `ast_drop_head_bang`) on stepwise tasks and recombines them in Tier 1 on deep compositional tasks (`227 / 509` on `Deep` vs `915 / 1219` for `atomic_nexus_predicate_evolution_only`, `2225 / 2468` for `ordinary_persistent_memoization`, and `3207 / 3450` for `equal_atomic_scratch`).
   - Across all 48 episodes (`3 seeds x 16 tasks`), `wave10_self_evolving_nexus` achieves the **lowest `codegen_plus_synthesis` (`2,354`)** and the **lowest `total_work` (`3,872`)** of all 6 methods, winning on every single seed (`max = 1,295` vs `min = 1,335` for the runner-up `atomic_nexus_pruning_disabled`).
