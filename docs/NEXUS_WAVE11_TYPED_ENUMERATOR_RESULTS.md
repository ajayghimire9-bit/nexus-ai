# NEXUS Wave 11 Results: Bounded Typed Program Enumerator, Direct AST Interpreter & Wave-10 Forensic Recovery

**Branch:** `cursor/seed-wave11-typed-program-enumerator`  
**Parent Commit:** `f253be1` (`cursor/seed-wave10-atomic-self-evolving-operators`)  
**Learner File:** `src/nexus/seed/wave11_typed_program_enumerator.py` (SHA-256: `70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a`, untouched across `c72a690`, `b19b69a`, and `4353a0c`)  
**Pre-Assessment Freeze Commit (`Commit 1c`):** `4353a0c`  
**Artifact:** `artifacts/seed_wave11c_typed_program_enumerator.json` (`hash`: `44a84d7d2a63b74c88b37c98b79be05ac519cc243b5d9923fa11ef3ff1c0f43b`)  
**Verifier:** `scripts/verify_wave11_typed_enumerator.py` (`valid: true`, `replayed_rows: 192`, `lambda_count: 0`, `prim_opcode_count: 14`)  
**Zero-Diff Verification:** `git diff 4353a0c -- src/ scripts/ tests/` is **100% empty** (`0` post-freeze code edits, `0` uses of `git commit --amend`).

---

## Part 1: Forensic Recovery & Honest Disclosure of the Amended Wave-10 Run (`9afb110 -> 16bb044 -> f253be1`)

In Wave 10, local Commit 1 (`9afb1101f42972289d7c89173487ff45d7c2d0da`) was amended once (`git commit --amend` -> `16bb0443eb68a65ebdf5f6bcde51b0e180c2f96e`) after the initial scoring run exited with code `1` on Gate 2 (`compression_tax_not_reduced:143_vs_315`).
- **Classification of `16bb044 -> f253be1`:** **Developmental / Post-Amend Run (1 local commit amendment after initial run failure)**.
- **Reconstructed Pre-Amend Failure Artifact:** `artifacts/seed_wave10_pre_amend_failed_run.json` (`hash`: `6a8493a609fd7480f45deaf9061334f81442a5de5d49aa59ac6f5fa830761562`).
- **Exact Patch (`git diff 9afb110 16bb044 -- src/nexus/seed/wave10_atomic_self_evolving_learner.py`):**
  ```diff
  @@ -430,9 +430,9 @@ class SelfEvolvingOperatorLibrary:
           latest_ast: MultiNodeAtomicAST,
           structure_discovered: bool,
       ) -> int:
  -        self.solved_program_history.append(latest_ast)
           if self.use_event_triggered_mdl and not structure_discovered:
               return 0
  +        self.solved_program_history.append(latest_ast)
           if len(self.solved_program_history) < 2:
               return 0
  ```

### Wave-10 Pre-Amend (`9afb110`) vs Post-Amend (`16bb044 -> f253be1`) Side-by-Side Comparison

| Metric / Method (`288` cells = `3 seeds x 6 methods x 16 tasks`) | Pre-Amend (`9afb110`, Unamended Run 1) | Post-Amend (`16bb044 -> f253be1`, Run 2) |
|---|---|---|
| **Overall `gates.passed`** | **`false`** (`compression_tax_not_reduced:143_vs_315`) | **`true`** |
| **Gate 1 (`gate1_equal_atomic_catalog_and_label_blind`)** | `true` (`48/48` solved across all 6 methods) | `true` (`48/48` solved across all 6 methods) |
| **Gate 2 (`gate2_fixes_all_three_d0a8bb1_overheads`)** | **`false`** (`143` vs `315`, `54.6%` reduction vs `>60%` threshold) | **`true`** (`83` vs `315`, `73.7%` reduction) |
| **Gate 3 (`gate3_self_evolving_pareto_win`)** | `true` (`total_work = 3,931` lowest of all 6 methods) | `true` (`total_work = 3,871` lowest of all 6 methods) |
| `wave10_self_evolving_nexus` Solve Rate (`private_correct`) | `48/48` (`100.0%`) | `48/48` (`100.0%`) |
| `wave10_self_evolving_nexus` `compression_evals` | `143` | `83` |
| `wave10_self_evolving_nexus` `codegen_plus_synthesis` | `2,354` (`mean 784.67`) | `2,354` (`mean 784.67`) |
| `wave10_self_evolving_nexus` `total_work` | `3,931` (`mean 1,310.33 / min 1,306 / max 1,316`) | `3,871` (`mean 1,290.33 / min 1,288 / max 1,294`) |
| `equal_atomic_scratch` `total_work` | `4,884` (`mean 1,628.0`) | `4,884` (`mean 1,628.0`) |
| `ordinary_persistent_memoization` `total_work` | `4,650` (`mean 1,550.0`) | `4,650` (`mean 1,550.0`) |
| `atomic_nexus_predicate_evolution_only` `total_work` | `4,757` (`mean 1,585.67`) | `4,697` (`mean 1,565.67`) |
| `atomic_nexus_pruning_disabled` `total_work` | `4,009` (`mean 1,336.33`) | `3,949` (`mean 1,316.33`) |
| `wave9_frozen_adaptive_rules` `total_work` | `5,151` (`mean 1,717.0`) | `5,151` (`mean 1,717.0`) |

---

## Part 2 & Part 3: Wave-11 Bounded Typed Program Enumerator & Direct AST Interpreter

### 1. Unconditional No-Amend Audit Trail (`0` uses of `git commit --amend`)
- **`c72a690 -> ffa43de` (`w11f_*`, Closed as Developmental / Closed):**
  - `src/nexus/seed/wave11_typed_program_enumerator.py` (`70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a`) and `src/nexus/seed/mechanism_wave11_fresh_assessment.py` ran cleanly and produced `artifacts/seed_wave11_typed_program_enumerator.json` (`hash`: `3bd32ab59b10797fb76b13060a61a402e4fe44c547835f5db954626a15097f07`, `gates.passed == True`, `48/48` solved across all 4 methods), while `scripts/run_wave11_typed_assessment.py` exited with `KeyError: 'suite_totals'` (`payload["totals"]["suite"]`). Closed in `ffa43de` without amending `c72a690`.
- **`b19b69a -> 1d6a946` (`w11b_*`, Closed as Developmental / Closed):**
  - `scripts/run_wave11_typed_assessment.py` (`mechanism_wave11b_fresh_assessment.py`) exited with code `0` (`hash`: `1ca3083196104a5075b4cb81cd6ede54abf43ef099ed606ca2b77340d902a3cf`, `gates.passed == True`, `48/48` solved across all 4 methods), while `scripts/verify_wave11_typed_enumerator.py` referenced `obs["output"]` instead of `obs["observed_output"]`. Closed in `1d6a946` without amending `b19b69a`.
- **`4353a0c -> Commit 2c` (`w11c_*`, Pre-Registered Single-Shot Blind Run):**
  - `src/nexus/seed/wave11_typed_program_enumerator.py` (`70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a`, untouched since `c72a690`) was evaluated on the brand-new unseen 16-task suite `src/nexus/seed/mechanism_wave11c_fresh_assessment.py` (`bfc08b30d39472d0c86efcdc5334a98f9e5866f6896cf1403e09664b32c0cccb`).
  - Both `scripts/run_wave11_typed_assessment.py` and `scripts/verify_wave11_typed_enumerator.py` passed (`valid: true`, `192/192` rows replayed via `eval_expr_ast`) on the first and only run with `git diff 4353a0c -- src/ scripts/ tests/` **100% empty**.

### 2. Wave-11 4-Method Comparison Table (`w11c_*`, `192` Cells = `3 Seeds x 4 Methods x 16 Tasks`)

| Method | Solve Rate (`private_correct`) | Mapping Correct | False Analogy / False Unique | AST Synthesis Evals (`synthesis_evals`) | Archive Lookup Evals | Gate Evals | Compression Evals | Compile + Schema Cost | `codegen_plus_synthesis` | Cumulative `total_work` | Per-Seed `total_work` (`mean / min / max`) | Per-Seed `codegen_plus_synthesis` (`mean / min / max`) | Sub-Macro Reused | Full-Macro / Memo Reused | Cold Archive Reactivated |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `equal_typed_scratch` | **`48/48` (`100%`)** | `48/48` | `0 / 0` | `32,046` | `0` | `0` | `0` | `0 + 0` | `32,046` | `33,357` | `11,119.0 / 11,119 / 11,119` | `10,682.0 / 10,682 / 10,682` | `0` | `0 / 0` | `0` |
| `ordinary_persistent_memoization` | **`48/48` (`100%`)** | `48/48` | `0 / 0` | `26,155` | `0` | `0` | `0` | `0 + 0` | `26,155` | `27,466` | `9,155.33 / 9,155 / 9,156` | `8,718.33 / 8,718 / 8,719` | `0` | `0 / 3` | `0` |
| `nexus_typed_without_pruning` | **`48/48` (`100%`)** | `48/48` | `0 / 0` | `12,320` | `0` | `30` | `108` | `84 + 36` | `12,320` | `13,889` | `4,629.67 / 4,625 / 4,633` | `4,106.67 / 4,102 / 4,110` | `15` | `3 / 0` | `0` |
| **`nexus_typed_full`** | **`48/48` (`100%`)** | **`48/48`** | **`0 / 0`** | **`12,052`** | **`46`** | **`27`** | **`108`** | **`84 + 36`** | **`12,098`** | **`13,664`** | **`4,554.67 / 4,552 / 4,556`** | **`4,032.67 / 4,030 / 4,034`** | **`15`** | **`3 / 0`** | **`3`** |

### 3. Split-by-Split Breakdown (`w11c_*`, `3 Seeds Combined`)

| Split | `equal_typed_scratch` (`codegen` / `total_work`) | `ordinary_persistent_memoization` (`codegen` / `total_work`) | `nexus_typed_without_pruning` (`codegen` / `total_work`) | `nexus_typed_full` (`codegen` / `total_work`) | Key Mechanism Demonstrated |
|---|---|---|---|---|---|
| **Deep Compositional (`w11c_deep_compositional`, `12` eps)** | `19,824 / 20,148` | `13,620 / 13,944` | `521 / 937` | **`294 / 710`** | Composing evolved `SEQ_EQ(x, REVERSE(x))` + `APPEND_TOK(M_rot(x), '#')` at effective AST size `3` instead of size `7` reduces `total_work` by **96.5%** (`710` vs `20,148`). |
| **Delayed Post-Prune (`w11c_delayed_post_prune`, `3` eps)** | `615 / 696` | `671 / 752` | `142 / 226` | **`144 / 228`** (`3/3` reactivated) | `INT_GE(LEN(x), 3)` is pruned after age `4` to keep the active library compact and reactivated in `O(1)` (`1` probe) from the Cold Signature Archive. |
| **Stepwise Evolution (`step_pred + step_tf`, `9` eps)** | `2,934 / 3,177` | `3,010 / 3,253` | `2,975 / 3,302` | **`2,975 / 3,300`** | Invents `SEQ_EQ(x, REVERSE(x))`, `APPEND_TOK(TAIL(x), HEAD(x))`, and `APPEND_TOK(TAIL(x), '#')` via size-bounded bottom-up AST enumeration. |
| **Spurious Once-Used (`w11c_spurious_once_used`, `6` eps)** | `1,518 / 1,680` | `1,542 / 1,704` | `1,527 / 1,753` | **`1,527 / 1,752`** | Usage-age pruning evicts once-used `TOK_EQ(HEAD(x), LAST(x))` and `INT_GE(LEN(x), 3)` guards into the Cold Signature Archive. |
| **Base + Lookalike (`g1 + g2`, `12` eps)** | `360 / 1,332` | `376 / 1,348` | `420 / 1,419` | **`416 / 1,412`** | Zero false-analogy locks (`0/6`) on `w11c_g2_len2_bang` and `w11c_g2_len0_q`. |
| **Safety (`amb + oog`, `6` eps)** | `6,795 / 7,324` | `6,936 / 7,465` | `6,735 / 7,252` | **`6,742 / 7,262`** | `3/3` ambiguous detection and `3/3` out-of-grammar abstention (`seq_vowel_shift`). |

### 4. Consistency Across All Three Unseen Suites (`w11a`, `w11b`, `w11c` = `576` Total Cells)

Across all three 16-task suites (`w11f_*`, `w11b_*`, `w11c_*`) evaluated with the exact same untouched learner `src/nexus/seed/wave11_typed_program_enumerator.py` (`70076ef08dc310399878372710387da9833ba295d0374a2a031249e2987ae86a`):
- **`w11a` (`w11f_*`, `3bd32ab5...`):** `48/48` solved across all 4 methods; `nexus_typed_full` `total_work = 13,682` vs `nexus_typed_without_pruning = 13,907`, `ordinary_persistent_memoization = 27,440`, `equal_typed_scratch = 33,366`.
- **`w11b` (`w11b_*`, `1ca30831...`):** `48/48` solved across all 4 methods; `nexus_typed_full` `total_work = 13,670` vs `nexus_typed_without_pruning = 13,895`, `ordinary_persistent_memoization = 27,454`, `equal_typed_scratch = 33,363`.
- **`w11c` (`w11c_*`, `44a84d7d...`):** `48/48` solved across all 4 methods; `nexus_typed_full` `total_work = 13,664` vs `nexus_typed_without_pruning = 13,889`, `ordinary_persistent_memoization = 27,466`, `equal_typed_scratch = 33,357`.
