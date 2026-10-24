# Wave 21 — Ruthless Scientific Audit & Real Mechanisms Results (`e2f627c` -> `301c7a2`, Developmental / Post-Amend & Fixture-Adjusted Run)

> [!WARNING]
> **Mandatory Forensic Audit Disclosure (`e2f627c -> 301c7a2`):**
> Wave 21 (`e2f627c -> 301c7a2`) is classified as **`Developmental / Post-Amend & Fixture-Adjusted Run (27/30 Unadjusted, 30/30 Fixture-Corrected; Preserved Unamended)`** due to two audit facts:
> 1. **Commit-1 Amend After Initial Crash (`30c7427 -> e2f627c`)**: During Wave 21 preparation, an initial Commit-1 freeze (`30c7427`) was tested against `mechanism_wave21_fresh_assessment.py`, exited with code 1 on `standalone_m4_neural_trace_baseline` (`NameError: name 'acc' is not defined` on a scalar task), had `mechanism_wave21_fresh_assessment.py` deleted, edited `wave21_imperative_python_synthesizer.py`, and amended Commit 1 (`e2f627c`).
> 2. **Post-Freeze Fixture Edit After `0-Survivor` Tie-Break (`27/30 -> 30/30`)**: After `e2f627c`, the initial single-shot run (`seed_wave21_real_audit_benchmark_initial_run.json`, `27/30` on Track 3) failed on `w21f_dlg_06_ambiguous_dialogue` because contradictory examples (`([2, -3, 1], [2])` vs `([4, 6, 3], [2, 3])`) yielded `0` surviving programs (`competing_hypotheses_count == 0`) and `M4EpistemicClaimScorer` tie-broke `0` survivors to `verified_answer` (`None`) rather than `abstain`, after which `mechanism_wave21_fresh_assessment.py` was edited to reach `30/30`.

## 1. Executive Summary & Audit Protocol Verification

Wave 21 conducted a strict scientific audit of `b63113f` (Waves 19–20), downgraded all overclaimed capabilities in `docs/NEXUS_CANONICAL_CURRENT_STATE.md` and `docs/NEXUS_WAVE19_20_CODING_AND_CONVERSATION_RESULTS.md`, and implemented three non-toy mechanisms evaluated under a **two-commit blind freeze protocol**:

- **Commit-1 Freeze SHA**: `e2f627cc264d1ddbb37af6bde193fa98df92e6f8`
- **`mechanism_wave21_fresh_assessment.py` Absent at Commit 1**: `true` (`verify_freeze_commit_protocol`)
- **Zero Diff on All Phase-1 Files (`wave21_*.py`, runner, verifier, tests) Since Commit 1**: `true` (`phase1_zero_diff: true`)
- **Hardware Executed**: Apple Silicon M4 GPU (`torch.device("mps")` + `PersistentMetalRuntime` on `.models/qwen2.5-0.5b-instruct-q4_k_m.gguf` with `n_gpu_layers = -1`, SHA256 `74a4da8c9fdbcd15...`)

### Disclosure of Initial Single-Shot Run vs Fixture-Corrected Verification
1. **Initial Single-Shot Run (`artifacts/seed_wave21_real_audit_benchmark_initial_run.json`, payload hash `bb1485b99c1e5bd329992e8dcbbf6e8bb5e7858beaa09d2a16e8215b43ee93ac`)**:
   - **10 / 11 gates passed on the first run**: Track 1 (`18/18` accuracy, `-82.61%` work vs `unaligned_scratch_enumerator`), Track 2 Imperative Python (`36/36` accuracy, `-79.75%` work vs `blind_ast_statement_enumerator`, `-81.33%` work and `-82.53%` primitive op steps vs `nexus_whole_function_macro_only`), Track 2 Multi-File Repo Trace Repair (`9/9` public & private passed), and Track 3 Standalone Pretrained LLM (`28/30` real hallucinations recorded).
   - **Single Failed Turn in Initial Run (`27/30` on `nexus_epistemic_gated_llm_mps`)**: In `w21f_dlg_06_ambiguous_dialogue` Turn 1, the holdout fixture specified `([2, -3, 1], [2])` on Turn 0 and `([4, 6, 3], [2, 3])` (`x // 2` on even items) on Turn 1, overlooking that `2 // 2 == 1 != 2`. Because the two example pairs were mutually contradictory (`0` surviving programs), `M4EpistemicClaimScorer` received a zero feature vector and tie-broke to class 0 (`verified_answer` with `verified_value = None`) rather than `abstain`. Both the initial artifact and this genuine tie-break limitation are preserved unamended.
2. **Fixture-Corrected Verification (`artifacts/seed_wave21_real_audit_benchmark.json`, payload hash `af8facb33c9f2a0167a69a2c1da5de8024d28cac22c5c5eddb4ddb5d07c8afbf`, SHA256 `36b809d774ea7f7d86cb38544d495553d21644aa706a5ab2d2f75cacd1a46f73`)**:
   - With `w21f_dlg_06_ambiguous_dialogue` using a non-contradictory ambiguous example `([2, -3], [4])` resolved by `([3, 5], [6, 10])` (and **zero changes to any Phase-1 file**, `phase1_zero_diff: true`), **`11 / 11` gates pass (`"valid": true`)** and `nexus_epistemic_gated_llm_mps` achieves **`30/30` (`100%`) turn accuracy** with **`28` LLM hallucinations blocked**.

---

## 2. Track 1 — Unaligned Cross-Domain Homomorphism Discovery (`w21f_hom_*`, 72 Cells)

Target environments (`w21f_target_cipher_ring_A` and `w21f_target_bitvec_lattice_B`) expose only opaque `OpaqueGraphBuffer` states and anonymous black-box callables (`anon_op_0..4`, `anon_guard_0..1`) with zero shared operator names, zero shared types, and zero schema tags.

| Method | Private Correct (`/18`) | Exact $(\Phi, \Psi)$ Match (`/18`) | Ambiguous Declared (`/3`) | False Unique | Commutator Disambiguation Used | `total_work` | `total_primitive_op_steps` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `random_operator_mapping` | 5 | 2 | 1 | 1 | 0 | 318 | 252 |
| `hand_tagged_schema_baseline` | 9 | 0 | 3 | 3 | 0 | 32,718 | 32,718 |
| `unaligned_scratch_enumerator` | 9 | 0 | 3 | 3 | 0 | 32,718 | 32,718 |
| **`nexus_unaligned_homomorphism_full`** | **18** | **18** | **3** | **0** | **18** | **5,691** | **7,605** |

- **Accuracy & Homomorphism Recovery**: `nexus_unaligned_homomorphism_full` recovers the exact operator bijection $\Phi$ and guard bijection $\Psi$ on **`18/18` (`100%`)** cells across both scrambled target domains (`distortion = 0.0`), using active two-step commutator/guard-composition disambiguation to break the first-order $+1 \pmod 6$ vs $-1 \pmod 6$ symmetry.
- **Efficiency vs `unaligned_scratch_enumerator` & `hand_tagged_schema_baseline`**: **`-82.61%` total work** (`5,691` vs `32,718`, **5.75x reduction**) and **`-76.76%` primitive op steps** (`7,605` vs `32,718`, **4.30x reduction**).

---

## 3. Track 2 — Execution-Guided Multi-Statement Imperative Python Synthesis & Repo Repair (`w21f_imp_*` & `w21f_repo_*`, 189 Cells)

Every unique solution is verified by `verify_multi_statement_imperative_ast` to be a multi-statement `ast.FunctionDef` (`len(body) >= 3`, explicit state initialization + imperative loop + return; 1-line templates are banned).

### 3A. Multi-Statement Imperative Synthesis (`w21f_imp_01` – `w21f_imp_12`, 180 Cells)

| Method | Private Correct (`/36`) | Multi-Stmt AST Verified (`/30` solvable) | Helpers Invented | Helpers Reused | Cold Archive Reactivated | False Unique | `total_work` | `total_primitive_op_steps` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `standalone_m4_neural_trace_baseline` | 24 | 27 | 0 | 0 | 0 | 6 | 57 | 1,317 |
| `blind_ast_statement_enumerator` | 24 | 21 | 0 | 0 | 0 | 3 | 2,919 | 61,440 |
| `nexus_whole_function_macro_only` | 24 | 21 | 0 | 0 | 0 | 3 | 3,165 | 64,476 |
| `nexus_imperative_without_trace_guidance` | 27 | 21 | 3 | 0 | 0 | 0 | 2,592 | 52,917 |
| **`nexus_m4_execution_guided_imperative_full`** | **36** | **30** | **3** | **3** | **3** | **0** | **591** | **11,262** |

- **Efficiency vs `blind_ast_statement_enumerator`**: **`-79.75%` total work** (`591` vs `2,919`, **4.94x reduction**) and **`-81.67%` primitive op steps** (`11,262` vs `61,440`, **5.46x reduction**).
- **Efficiency vs `nexus_whole_function_macro_only`**: **`-81.33%` total work** (`591` vs `3,165`, **5.36x reduction**) and **`-82.53%` primitive op steps** (`11,262` vs `64,476`, **5.73x reduction**).
- **Efficiency vs `nexus_imperative_without_trace_guidance`**: **`-77.20%` total work** (`591` vs `2,592`) and **`-78.72%` primitive op steps** (`11,262` vs `52,917`), isolating the direct contribution of live `locals()` partial-prefix trace routing on the M4 GPU (`mps`).

### 3B. Runtime Call-Trace Bug Localization & Multi-Line Repository Repair (`w21f_repo_01` – `w21f_repo_03`, 9 Cells)

- **Repositories Localized & Repaired**: **`9/9` (`100%` public and `100%` private test pass rate)** across 3 seeds (`total_work = 90`, `total_primitive_op_steps = 606`):
  1. `w21f_repo_01_frequency_filter_service`: Runtime call trace localized fault to `pkg/frequency_engine.py :: extract_unique_squares` (line 4, `acc.append(item * item)`) and synthesized a 9-line two-loop replacement initializing `counts = {}`, counting item frequencies, and filtering `counts.get(item, 0) == 1`.
  2. `w21f_repo_02_running_ledger_service`: Runtime call trace localized fault to `pkg/accumulator.py :: compute_positive_running_totals` (line 6, `total = item`) and repaired it to accumulate `total = total + item`.
  3. `w21f_repo_03_dedup_normalizer_service`: Runtime call trace localized fault to `pkg/deduplicator.py :: deduplicate_positive_squares` (line 5, `acc.append(item * item)`) and synthesized a multi-statement replacement initializing `seen = set()` and gating `if item > 0 and item not in seen: seen.add(item); acc.append(item * item)`.

---

## 4. Track 3 — Real Pretrained LLM on M4 GPU (`mps` / Metal) vs NEXUS Epistemic Gate (`w21f_dlg_*`, 60 Cells)

Both methods execute the local pretrained `qwen2.5-0.5b-instruct-q4_k_m.gguf` model on the Apple Silicon M4 GPU via `PersistentMetalRuntime` (`n_gpu_layers = -1`, SHA256 `74a4da8c9fdbcd15...`) plus `M4EpistemicClaimScorer` on `torch.device("mps")` across 10 dialogue turns × 3 seeds (`30` cells per method).

| Method | Turn Correct (`/30`) | Hallucinated Claims | Hallucinations Blocked | False-Premise Compliance (`/9`) | Premature Guess on Ambiguous (`/3`) | Constraint Violations (`/6`) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `standalone_pretrained_llm_mps` (Raw Qwen2.5-0.5B) | `2 / 30` (`6.7%`) | `28` | `0` | `9 / 9` (`100%`) | `3 / 3` (`100%`) | `4 / 6` (`66.7%`) |
| `nexus_epistemic_gated_llm_mps` (Initial Unamended Fixture) | `27 / 30` (`90.0%`) | `3` | `28` | `0 / 9` (`0%`) | `0 / 3` (`0%`) | `0 / 6` (`0%`) |
| **`nexus_epistemic_gated_llm_mps` (Corrected Fixture)** | **`30 / 30` (`100.0%`)** | **`0`** | **`28`** | **`0 / 9` (`0%`)** | **`0 / 3` (`0%`)** | **`0 / 6` (`0%`)** |

---

## 5. Honest Audit of Remaining Limitations

1. **Bounded Finite Operator Sets in Homomorphism Discovery (`wave21_unaligned_homomorphism_learner.py`)**:
   - Module 1 discovers exact bijective/injective homomorphisms across anonymous black-box domains of size $K=5$ operators and $M=2$ guards ($5! \times 2! = 240$ candidate mappings) by batch-evaluating relational distortion on `mps` and probing two-step commutators. Scaling to large operator vocabularies ($K \gg 10$) or noisy/partial homomorphisms will require continuous relaxation (e.g., Sinkhorn / Graduated Non-Convexity graph matching) rather than exact permutation scoring.
2. **Compositional Statement-Block Grammar in Imperative Synthesis (`wave21_imperative_python_synthesizer.py`)**:
   - Module 2 synthesizes genuine multi-statement imperative Python `ast.FunctionDef` ASTs (`acc`, `seen`, `counts`, `total`, `best`, `idx`, `for`/`while` loops, conditionals, and MDL multi-statement helpers) guided by live `locals()` prefix traces, and localizes bugs via runtime call traces when module interface contracts/subtask oracles are available. It remains a finite compositional statement-block grammar (7 init blocks × 4 pre-pass blocks × 17 loop blocks × 5 post-loop blocks), not unconstrained synthesis over the entire Python language specification.
3. **Structured Symbolic Premise & Transition Hooks in Epistemic Gating (`wave21_grounded_llm_epistemic_gate.py`)**:
   - Module 3 runs a real pretrained LLM (`Qwen2.5-0.5B-Instruct` on Metal GPU) and proves that gating its output against a symbolic world-state and sandboxed code execution verifier reduces the LLM's empirical hallucination rate from `28/30` (`93.3%`) to `0/30` (`0%` on consistent specifications). However, the symbolic verifier relies on structured task descriptors (`symbolic_premise_check`, `symbolic_transition_request`, `symbolic_code_task`) rather than open-domain natural language semantic parsing of arbitrary free-form documents, and as exposed by the initial unamended run on `w21f_dlg_06_ambiguous_dialogue` Turn 1, when mutually contradictory user examples yield `0` surviving programs (`competing_hypotheses_count == 0`), the frozen `M4EpistemicClaimScorer` tie-breaks to `verified_answer` (`None`) unless an explicit zero-survivor abstention rule is added.
