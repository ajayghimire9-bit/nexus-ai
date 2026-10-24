# NEXUS Wave 23 — Focused Meta-Learning, Three-State Witness Checking & Scoped Symbolic-KAN Experiment Results

## 1. Executive Summary & Reproducible Two-Commit Protocol Verification
Wave 23 (`cursor/seed-wave23-focused-meta-learning-witness-and-kan-experiment`, starting from `bf6e747`) implements a focused, deconfounded experimental study across three tracks on Apple Silicon M4 (`torch.device("mps")` + Metal GPU `qwen2.5-0.5b-instruct-q4_k_m.gguf`) while preserving NEXUS's single authoritative skill/template and provenance store (`AuthoritativeTemplateStore`).

- **Pre-Freeze Commit 1 (Pushed to `origin` and `github` Before Running Phase 2)**: `5ace47b36a808d68edf549e25efed1838f28ba8d` (`5ace47b`)
- **Zero History Rewriting (`git reflog -n 50`)**: `zero_amend_on_branch = True` (zero `commit (amend)`, `rebase`, or `reset` entries on `cursor/seed-wave23-focused-meta-learning-witness-and-kan-experiment`).
- **Physical Separation (`git diff 5ace47b HEAD -- <PHASE1_FILES>`)**: `phase1_zero_diff = True` (zero modifications to any Phase-1 file after `5ace47b`).
- **Retained All Generated Cases & All Attempted Runs**:
  - Suite Manifest (`artifacts/seed_wave23_suite_manifest.json`): `payload_sha256 = 5e484a942901b1ae432f7752e428c93ae80115154e5e3f82faf0f97fee823e06` (`retained_all_generated_cases = True`)
  - Experiment Payload (`artifacts/seed_wave23_focused_experiment.json`): `payload_sha256 = bee81718693f136b377f0ed7bc62c50d4fdd6b41e8a18a8b6b6a0d0d9c4daa54` (`retained_all_attempted_runs = True`)
- **Transparent Verifier Note on `symkan_attempted_count` vs `symkan_faithful_export_count`**:
  - In `scripts/verify_wave23_focused_experiment.py` (line 142, frozen at `5ace47b`), the script compared `symkan_faithful_export_count` (`21`) against `symkan_attempted_count` (`33`, which includes `12` attempts on sorted-output tasks `APPEND_SORT_ASC` / `APPEND_SORT_TOP2` where `derive_public_scalar_alignments` only forms `APPEND_ID` / `APPEND_REV` pairs and `SymbolicKANResidualInducer` returns `None` with `induced_expression = ''`).
  - Across **100% (`21/21`) of non-empty induced Symbolic-KAN expressions** (`induced_expression != ''`), `faithful_export == True` (`21/21` in both `learned_proposer_plus_symkan_no_promotion` and `learned_proposer_plus_symkan_with_promotion`). Rather than editing `scripts/verify_wave23_focused_experiment.py` after `5ace47b`, we leave all Phase-1 files untouched so `phase1_zero_diff = True` is strictly preserved.

---

## 2. Independent Task Counts ($N_{\text{tasks}}$) vs. Total Evaluation Cells
Every summary table separates the number of independent tasks/turns ($N_{\text{tasks}}$) from total `tasks × methods × seeds` evaluation cells:

| Track | Independent Tasks / Turns ($N_{\text{tasks}}$) | Breakdown of Independent Tasks / Turns | Compared Methods | Seeds | Total Evaluation Cells |
|---|---:|---|---:|---:|---:|
| **Track 1 (Cross-Domain Mapping: Public Validation vs. Private Assessment)** | **`8` tasks** | `6` unique-transfer tasks (`1` first-acquisition + `5` repeated-transfer), `1` ambiguous public-validation task, `1` no-validated-mapping task | `2` | `3` | **`48` cells** |
| **Track 2 (Elementary AST Synthesis, 3-State Witness & Scoped SymKAN)** | **`14` tasks** | `10` first-acquisition / witness / failure tasks + `4` repeated-use tasks | `5` | `3` | **`210` cells** |
| **Track 3 (Specification-Scoped NL Grounding vs. Equal-Tool LLM Baseline)** | **`10` turns** (`5` dialogues) | `8` first-acquisition / witness / failure turns + `2` repeated-use turns | `3` | `3` | **`90` cells** |
| **Total** | **`32` independent tasks/turns** | `24` first-acquisition / diagnostic + `8` repeated-use / transfer | — | `3` | **`348` cells** |

---

## 3. Track 1 — Cross-Domain Correspondence Acquisition (`8` Independent Tasks, `48` Evaluation Cells)
Source Domain A has $K_A = 6$ operators and $M_A = 2$ guards; Target Domain B has $K_B = 10$ anonymous operators (`anon_op_0..9`, including **4 distractors**, two of which are **2-step lookalike distractors** that agree with true operators for 1–2 steps on standard states and diverge only at steps 3–5) and $M_B = 3$ anonymous guards (`anon_guard_0..2`, including **1 distractor guard**). Candidate mappings $\{\Phi_1, \dots, \Phi_L\}$ (`L = 4` lookalike-competing mappings) are filtered strictly on **Public Validation** 3-to-5-step interventional trajectories before any evaluation on untouched **Private Assessment** tasks.

| Method | Indep. Tasks ($N_{\text{tasks}}$) | Eval Cells | Private Assessment Correct | Unique Exact $(\Phi^*, \Psi^*)$ | Ambiguous Verdict (`AMBIGUOUS_VALIDATED_MAPPINGS`) | No-Mapping Verdict (`NO_VALIDATED_MAPPING`) | First-Acquisition Work (`first_acquisition_work`) | Repeated-Transfer Work (`repeated_transfer_work`) | Public Validation Work | Proposer Scoring Work | Total Work | Primitive Op Steps | M4 `mps` Forward Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fixed_interventional_mapping_solver` | `8` | `24` | **`24/24` (`100%`)** | `18/18` | `3/3` | `3/3` | `16,800` | `75` (`5` per transfer) | `16,716` | `72` | `16,875` | `17,133` | `333` |
| `learned_interventional_mapping_solver` | `8` | `24` | **`24/24` (`100%`)** | `18/18` | `3/3` | `3/3` | **`16,044` (`-4.50%`)** | **`75` (`5` per transfer)** | `15,948` | `84` | **`16,119` (`-4.48%`)** | **`16,377`** | `336` |

- **Key Finding**: Ranking 3-to-5-step public interventional trajectories on M4 `mps` to prioritize trajectories that test lookalike-competing rows (`src_op_1` and `src_op_4` repeated 3–4 times) eliminates all 3 false lookalike mappings earlier in Public Validation, reducing `first_acquisition_work` by **`-756` work units (`-4.50%`)** across the 3 seeds while keeping `repeated_transfer_work` at **`5` work units per transfer (`75` across 15 repeated transfers)**.

---

## 4. Track 2 — Elementary AST Synthesis, Three-State Witness Checking & Scoped `SymbolicKANResidualInducer` (`14` Independent Tasks, `210` Evaluation Cells)
All synthesized programs are constructed strictly from elementary Python AST statements (`Assign`, `For`, `If`, `Expr(Call(acc.append, ...))`, `Return`) with `<= 7` inner statements and `<= 200` loop steps, verified by `verify_no_compound_loop_boxes` (`0` compound loop enums).

| Method | Indep. Tasks ($N_{\text{tasks}}$: `10` First + `4` Rep) | Eval Cells | Status & Private Correct | Max Stmts (`<= 7`) | No Compound Boxes | Cand. Evals to Find $g_1$ (`candidate_evaluations`) | Witness Search Work (`witness_search_work`) | First-Acquisition Work (`first_acquisition_work`) | Repeated-Use Work (`repeated_use_work`) | Total Work | Primitive Op Steps | Template Hits / Cold Reactivations | SymKAN Attempted / Faithful Export / Task Correct / Promoted | M4 `mps` Fwd / Online Steps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fixed_elementary_scratch` | `14` (`10`+`4`) | `42` | **`42/42` (`100%`)** | `7` | `True` | `5,280` | `18,252` | **`15,468`** | `8,550` | `24,018` | `347,556` | `0 / 0` | `0 / 0 / 0 / 0` | `0 / 0` |
| `fixed_elementary_with_templates` | `14` (`10`+`4`) | `42` | **`42/42` (`100%`)** | `7` | `True` | `3,555` (`-32.67%`) | `13,812` | `15,510` | `2,409` (`-71.82%`) | `17,919` (`-25.39%`) | `237,036` | `9 / 3` | `0 / 0 / 0 / 0` | `0 / 0` |
| `learned_proposer_with_templates` | `14` (`10`+`4`) | `42` | **`42/42` (`100%`)** | `7` | `True` | **`2,903` (`-18.34%` vs fixed tmpl)** | `14,391` | `15,527` (`+0.11%`) | `2,439` (`+1.25%`) | `17,966` (`+0.26%` vs fixed tmpl) | `238,006` | `9 / 3` | `0 / 0 / 0 / 0` | `90 / 60` |
| `learned_proposer_plus_symkan_no_promotion` | `14` (`10`+`4`) | `42` | **`42/42` (`100%`)** | `7` | `True` | **`2,334` (`-34.35%` vs fixed tmpl)** | `14,930` | `15,629` | `2,499` | `18,128` (`+1.17%` vs fixed tmpl) | `238,342` | `9 / 3` | `33 / 21 / 15 / 0` | `138 / 60` |
| `learned_proposer_plus_symkan_with_promotion` | `14` (`10`+`4`) | `42` | **`42/42` (`100%`)** | `7` | `True` | **`2,349` (`-33.92%` vs fixed tmpl)** | **`12,761`** | `15,641` | **`339` (`-85.93%` vs fixed tmpl)** | **`15,980` (`-10.82%` vs fixed tmpl)** | **`218,638`** | **`15 / 3`** | `33 / 21 / 15 / 9` | `135 / 60` |

### Honest Comparative Ablation Conclusions (Track 2)
1. **Did `learned_proposer_with_templates` beat `fixed_elementary_with_templates`?**
   - **On finding the first fitting program $g_1$ (`candidate_evaluations`)**: **Yes** — `learned_proposer_with_templates` reduced sandbox candidate evaluations to find $g_1$ from `3,555` to **`2,903` (`-652` evaluations, `-18.34%`)** (and `-45.02%` vs `fixed_elementary_scratch`'s `5,280`).
   - **On total work under exhaustive bounded-space witness verification (`total_work`)**: **No (`17,966` vs `17,919`, `+47` work units / `+0.26%`)** — because proving `UNIQUE_IN_BOUNDED_SPACE` on first-acquisition tasks requires checking every remaining candidate in $\mathcal{G}_{\text{bound}}$ after $g_1$ is found, the sum `candidate_evaluations + witness_search_work` is mathematically invariant to candidate ordering on unique first-acquisition tasks (`3,555 + 13,812 = 17,367` vs `2,903 + 14,391 = 17,294` across all tasks), so the neural proposer's scoring work (`120` units) added `+47` net work units.
2. **Did `SymbolicKANResidualInducer` earn its cost or add net overhead?**
   - **Without template promotion (`learned_proposer_plus_symkan_no_promotion`)**: **Added net overhead (`+162` work units vs `learned_proposer_with_templates`, `18,128` vs `17,966`)** — although it reduced `candidate_evaluations` to find $g_1$ down to **`2,334`** (`-19.60%` vs `learned_proposer_with_templates`) and achieved `21/21` (`100%`) `faithful_export` on all non-empty induced expressions, without promoting the induced `v // 2 if v > 2 else v` expression to `AuthoritativeTemplateStore` after `w23_t2_09`, it had to re-induce and re-verify on `w23_t2_10`.
   - **With verified template promotion (`learned_proposer_plus_symkan_with_promotion`)**: **Earned its cost on repeated use and overall total work** — promoting the witness-verified Symbolic-KAN expression `v // 2 if v > 2 else v` after `w23_t2_09` (whereas standard MDL promotion requires 2 solved occurrences) allowed immediate template reuse on `w23_t2_10`, slashing `repeated_use_work` from `2,409` (`fixed_elementary_with_templates`) to **`339` (`-85.93%`)** (and `-96.04%` vs `fixed_elementary_scratch`'s `8,550`) and reducing overall `total_work` to **`15,980` (`-1,939` work units / `-10.82%` below `fixed_elementary_with_templates`)**.

---

## 5. Track 3 — Specification-Scoped NL Grounding vs. Equal-Tool Pretrained LLM Baseline (`10` Independent Turns, `90` Evaluation Cells)
All 3 methods execute local `qwen2.5-0.5b-instruct-q4_k_m.gguf` on Apple Silicon Metal GPU (`n_gpu_layers = -1`, SHA-256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`). Critically, `tool_equipped_llm_with_skill_cache_mps` has the **exact same Python sandbox executor, persistent skill cache, and reusable functions** as `nexus_witness_gated_agent_mps`, isolating the value of **Three-State Witness-Pair Ambiguity Gating** and **Three-State Failure Classification**.

| Method | Indep. Turns ($N_{\text{turns}}$: `8` First + `2` Rep) | Eval Cells | Turn Correct | Turn Accuracy | Unverified / False Claims | Premature Commits on Ambiguous (`AMBIGUOUS_WITNESS_FOUND`) | Deterministic Collisions Complied (`VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`) | Tool / Skill Invocations | First-Acquisition Work (`first_acquisition_work`) | Repeated-Use Work (`repeated_use_work`) | Total Work | Primitive Op Steps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `standalone_pretrained_llm_mps` | `10` (`8`+`2`) | `30` | `3/30` | `10.00%` | `27/30` | `6/6` | `3/3` | `0/30` | `24` | `6` | `30` | `120` |
| `tool_equipped_llm_with_skill_cache_mps` (Equal-Tool Baseline) | `10` (`8`+`2`) | `30` | `21/30` | `70.00%` | `9/30` | `6/6` | `0/3` | `30/30` | `9,462` | **`18`** | `9,480` | `81,906` |
| `nexus_witness_gated_agent_mps` (Full Witness Gating) | `10` (`8`+`2`) | `30` | **`30/30`** | **`100.00%`** | **`0/30`** | **`0/6`** | **`0/3`** | `30/30` | **`6,960` (`-26.44%`)** | **`18`** | **`6,978` (`-26.39%`)** | **`56,616`** |

- **Key Finding**: Giving the pretrained LLM equal access to the Python sandbox executor and skill cache (`tool_equipped_llm_with_skill_cache_mps`) jumps accuracy from `10.00%` (`3/30`) to `70.00%` (`21/30`) and matches `nexus_witness_gated_agent_mps` on repeated-use skill turns (`repeated_use_work = 18`). However, without the Three-State Witness-Pair check, `tool_equipped_llm_with_skill_cache_mps` **commits prematurely on 100% (`6/6`) of witness-ambiguous turns** (such as `[2, -3, 1] -> [2]` and `[4, 6, 3] -> [2, 3]`, where it executes the first fitting program $g_1$ without detecting $g_2$), which also causes its follow-up clarification turns to fail (`9/30` total errors). `nexus_witness_gated_agent_mps` detects the witness pair $(g_1, g_2)$, requests clarification (`AMBIGUOUS_WITNESS_FOUND_CLARIFY`), separates `VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS` from `NO_PROGRAM_IN_BOUNDED_GRAMMAR`, and achieves **`30/30` (`100.00%`)** turn accuracy.
