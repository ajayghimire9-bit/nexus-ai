# NEXUS Wave-10 Atomic Self-Evolving Operators & Cost-Ordered Meta-Control — Developmental / Post-Amend Results & Forensic Disclosure

## 1. Classification & Forensic Disclosure (`9afb110 -> 16bb044 -> f253be1`)
- **Classification:** **Developmental / Post-Amend Run (1 local commit amendment after initial run failure)** — *not* a zero-amend single-shot run.
- **Original Pre-Amend Commit (`HEAD@{3}`):** `9afb1101f42972289d7c89173487ff45d7c2d0da` (`9afb110`)
- **Amended Commit (`HEAD@{2}`):** `16bb04407d608bf3707ca894be3a2ca8bf5f2dd9` (`16bb044`)
- **Results Commit (`HEAD@{1}`):** `f253be1`
- **Saved Pre-Amend Artifact:** `artifacts/seed_wave10_pre_amend_failed_run.json` (`hash`: `6a8493a609fd7480f45deaf9061334f81442a5de5d49aa59ac6f5fa830761562`)
- **Saved Post-Amend Artifact:** `artifacts/seed_wave10_atomic_self_evolving_operators.json` (`hash`: `17656be31dcbfb23bc292ed1c021362eff236d8c851c6286039a9cd73aecdc0d`)

### Exact Patch Between Pre-Amend (`9afb110`) and Amended (`16bb044`)
```diff
diff --git a/src/nexus/seed/wave10_atomic_self_evolving_learner.py b/src/nexus/seed/wave10_atomic_self_evolving_learner.py
index dc1fa20..b50463d 100644
--- a/src/nexus/seed/wave10_atomic_self_evolving_learner.py
+++ b/src/nexus/seed/wave10_atomic_self_evolving_learner.py
@@ -441,9 +441,11 @@ class AtomicSelfEvolvingLibrary:
         """
         if latest_ast.kind == "abstain" or latest_ast.domain_kind != "sequence":
             return 0
-        self.solved_program_history.append(latest_ast)
+        if not self.use_predicate_evolution and not self.use_transform_evolution:
+            return 0
         if self.use_event_triggered_mdl and not structure_discovered:
             return 0
+        self.solved_program_history.append(latest_ast)
 
         compression_evals = 0
         pred_counts: Dict[str, int] = {}
```

### Technical Reason for the Amendment & Why Pre-Amend (`9afb110`) Exited with Code 1
1. In the original pre-amend commit `9afb110`, all `288` cells (`48/48` per method across 6 methods) solved `100%` of public and private evaluations (`mapping_correct = 48/48`, `private_correct = 48/48`, `0` false locks), and `Gate 1` (`gate1_equal_atomic_catalog_and_label_blind: true`) and `Gate 3` (`gate3_self_evolving_pareto_win: true`) both passed (`wave10_self_evolving_nexus` achieved the lowest `codegen_plus_synthesis = 2354` and lowest `total_work = 3931` of all 6 methods).
2. However, `Gate 2` failed with `"notes": ["compression_tax_not_reduced:143_vs_315"]` (causing `run_wave10_atomic_self_evolving.py` to exit with code 1) because:
   - In `compress_solved_programs_mdl` (`wave10_atomic_self_evolving_learner.py:L441-447`), `self.solved_program_history.append(latest_ast)` was placed *before* `if self.use_event_triggered_mdl and not structure_discovered: return 0`, so every solved Tier-0 base program (`G1`/`G2`) and Tier-1/Tier-2 reuse program was still appended to `solved_program_history` and scanned whenever a subsequent Tier-3 task triggered MDL consolidation (`143` vs `315` = `54.6%` reduction, missing the `> 60%` threshold `143 <= 126`).
   - Additionally, `compress_solved_programs_mdl` did not check `if not self.use_predicate_evolution and not self.use_transform_evolution: return 0`, so `equal_atomic_scratch` (`30`) and `ordinary_persistent_memoization` (`198`) were also charged `compression_evals` despite having no evolved operator library.
3. Moving `self.solved_program_history.append(latest_ast)` after the `structure_discovered` check and guarding on `use_predicate_evolution or use_transform_evolution` reduced `compression_evals` on `wave10_self_evolving_nexus` from `143` to `84` (`-73.3%` vs `315`), while leaving `synthesis_evals`, `micro_codegen_evals`, `archive_lookup_evals`, `codegen_plus_synthesis`, `gate_evals`, and all `288` synthesized programs and private outcomes **100% identical**.

---

## 2. Side-by-Side Comparison: Pre-Amend (`9afb110`) vs Post-Amend (`16bb044 -> f253be1`) (`48` Episodes per Method)

| Method | Solve Rate (Pre / Post) | `codegen_plus_synthesis` (Pre / Post) | `compression_evals` (**Pre `9afb110`**) | `compression_evals` (**Post `16bb044`**) | `total_work` (**Pre `9afb110`**) | `total_work` (**Post `16bb044`**) | Per-Seed `total_work` `mean [min..max]` (**Pre `9afb110`**) | Per-Seed `total_work` `mean [min..max]` (**Post `16bb044`**) |
| --- | :---: | :---: | ---: | ---: | ---: | ---: | :---: | :---: |
| `equal_atomic_scratch` | `48/48` / `48/48` | `5319` / `5319` | `30` | `0` | `6660` | `6630` | `2220.0 [2220..2220]` | `2210.0 [2210..2210]` |
| `ordinary_persistent_memoization` | `48/48` / `48/48` | `4634` / `4634` | `198` | `0` | `6143` | `5945` | `2047.67 [2037..2059]` | `1981.67 [1978..1986]` |
| `wave9_frozen_adaptive_rules` | `48/48` / `48/48` | `3601` / `3601` | `315` | `315` | `5528` | `5528` | `1842.67 [1807..1861]` | `1842.67 [1807..1861]` |
| `atomic_nexus_predicate_evolution_only` | `48/48` / `48/48` | `3030` / `3030` | `175` | `108` | `4615` | `4548` | `1538.33 [1528..1551]` | `1516.0 [1511..1524]` |
| `atomic_nexus_pruning_disabled` | `48/48` / `48/48` | `2493` / `2493` | `143` | `84` | `4073` | `4014` | `1357.67 [1351..1367]` | `1338.0 [1335..1341]` |
| **`wave10_self_evolving_nexus`** | **`48/48` / `48/48`** | **`2354` / `2354`** | **`143`** | **`84`** | **`3931`** | **`3872`** | **`1310.33 [1301..1321]`** | **`1290.67 [1285..1295]`** |

---

## 3. Per-Split Breakdown (`codegen_plus_synthesis / total_work` on `16bb044 -> f253be1`)

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
| **Suite Total (`48`, Post-Amend `16bb044`)** | `5319 / 6630` | `4634 / 5945` | `3601 / 5528` | `3030 / 4548` | `2493 / 4014` | **`2354 / 3872`** |
| **Suite Total (`48`, Pre-Amend `9afb110`)** | `5319 / 6660` | `4634 / 6143` | `3601 / 5528` | `3030 / 4615` | `2493 / 4073` | **`2354 / 3931`** |

---

## 4. Remaining Architectural Limitation Addressed in Wave 11
While Wave 10 replaced monolithic domain operators with multi-node predicate and transform trees (`ATOMIC_PREDICATE_TREES` and `ATOMIC_TRANSFORM_TREES`), those candidate trees in `wave10_atomic_self_evolving_learner.py:L127-220` were still defined as a fixed tuple of `MultiNodeAtomicAST` objects with attached `lambda` callables. Wave 11 eliminates all handwritten composite candidate lists and attached `lambda` callables by introducing a **Bounded, Typed Program Enumerator (`TypedProgramEnumerator`) and Direct Recursive AST Interpreter (`eval_expr_ast`)**.
