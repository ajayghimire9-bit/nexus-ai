# NEXUS Wave 23 — Focused Meta-Learning, Three-State Witness Checking & Scoped Symbolic-KAN Experiment Protocol

## 1. Branch & Base Commit
- **Branch**: `cursor/seed-wave23-focused-meta-learning-witness-and-kan-experiment`
- **Base Commit**: `bf6e747777b564cc6c8f042f896db60e04421b5f` (`bf6e747`)
- **Part 1 Mandatory Wave 22 Audit Correction**: Recorded in `docs/NEXUS_WAVE22_OMEGA_RESULTS.md` and `docs/NEXUS_CANONICAL_CURRENT_STATE.md`, documenting all six external audit findings and relabeling Wave 22 (`c1b1a19 -> bf6e747`) as **`Developmental / In-Memory Screened Small Suite & Conflated OOG/Contradiction States (Preserved Unamended)`**.

## 2. Reproducible Two-Commit Protocol (Push Commit 1 First, Retain All Cases & Runs)
1. **Zero History Rewriting**: `git commit --amend`, `git rebase`, and `git reset` are strictly prohibited on `cursor/seed-wave23-focused-meta-learning-witness-and-kan-experiment`. `scripts/verify_wave23_focused_experiment.py` inspects `git reflog -n 50` and verifies `zero_amend_on_branch == True`.
2. **Commit 1 (Pre-Freeze Code & Protocol — Pushed Before Phase 2)**:
   - Commits `docs/NEXUS_CANONICAL_CURRENT_STATE.md`, `docs/NEXUS_WAVE22_OMEGA_RESULTS.md`, `docs/NEXUS_WAVE23_FOCUSED_EXPERIMENT_PROTOCOL.md`, `src/nexus/seed/wave23_focused_meta_learning_and_witness_engine.py`, `scripts/run_wave23_focused_experiment.py`, `scripts/verify_wave23_focused_experiment.py`, and `tests/test_seed_wave23_focused_experiment.py`.
   - **Pushed to `origin` and `github` BEFORE executing Phase 2**.
3. **Commit 2 (Post-Freeze Execution — Retaining All Cases & Reporting Honest Outcomes)**:
   - Runs `scripts/run_wave23_focused_experiment.py --freeze-commit <commit_1_sha>` and `scripts/verify_wave23_focused_experiment.py --freeze-commit <commit_1_sha>` once, retaining 100% of generated cases in `artifacts/seed_wave23_suite_manifest.json` and 100% of attempted runs in `artifacts/seed_wave23_focused_experiment.json` with zero diff on all Phase-1 files (`phase1_zero_diff == True`).
   - Reports independent task counts ($N_{\text{tasks}}$) separately from total evaluation cells (`tasks × methods × seeds`), separates **First-Acquisition Cost** from **Repeated-Use Cost**, and reports honestly whether `learned_proposer_with_templates` beat `fixed_elementary_with_templates` and whether `SymbolicKANResidualInducer` (`no_promotion` vs `with_promotion`) earned its cost or added net overhead.

## 3. Pre-Freeze Phase-1 File SHA-256 Digests
| File | SHA-256 |
|---|---|
| `src/nexus/seed/wave23_focused_meta_learning_and_witness_engine.py` | `ab239678252d98944f0dcc8813fc9a2229fdc3a72f02904e8165ce2ea2e0315b` |
| `scripts/run_wave23_focused_experiment.py` | `55da2dd6e06fe7933dd560f4fa98783fb5f48b69242fcebc2c98033b7ef7f65f` |
| `scripts/verify_wave23_focused_experiment.py` | `670f2e52adea9d4c52e05b5582e8a5c86c8cd7b07348109ff88866044c652c5f` |
| `tests/test_seed_wave23_focused_experiment.py` | `be6cc9e28e2e70abeb8a281dcbf4ca507f8f0153db48a89a107beac932a6093a` |

## 4. Independent Task Counts ($N_{\text{tasks}}$) vs. Total Evaluation Cells
- **Track 1 (Cross-Domain Correspondence Acquisition — Public Validation vs. Private Assessment)**:
  - **Independent Tasks**: $N_{\text{tasks}} = 8$ (`6` unique transfer tasks (`1` first-acquisition + `5` repeated-transfer), `1` ambiguous public-validation task, `1` no-validated-mapping task) across $K_A=6, M_A=2 \to K_B=10, M_B=3$ with 2-step lookalike distractors.
  - **Methods**: `2` (`fixed_interventional_mapping_solver`, `learned_interventional_mapping_solver`) × `3` seeds = **`48` evaluation cells**.
- **Track 2 (Elementary AST Synthesis, Three-State Witness Checking & Scoped `SymbolicKANResidualInducer`)**:
  - **Independent Tasks**: $N_{\text{tasks}} = 14$ (`10` first-acquisition / witness / failure tasks + `4` repeated-use tasks) under elementary AST bounds (`<= 7` statements, `<= 200` loop steps, zero compound loop boxes).
  - **Methods**: `5` (`fixed_elementary_scratch`, `fixed_elementary_with_templates`, `learned_proposer_with_templates`, `learned_proposer_plus_symkan_no_promotion`, `learned_proposer_plus_symkan_with_promotion`) × `3` seeds = **`210` evaluation cells**.
- **Track 3 (Specification-Scoped NL Grounding vs. Equal-Tool Pretrained LLM Baseline on Metal GPU)**:
  - **Independent Turns**: $N_{\text{turns}} = 10$ across `5` dialogues (`8` first-acquisition / witness / failure turns + `2` repeated-use turns) on local `qwen2.5-0.5b-instruct-q4_k_m.gguf` (`n_gpu_layers = -1`).
  - **Methods**: `3` (`standalone_pretrained_llm_mps`, `tool_equipped_llm_with_skill_cache_mps`, `nexus_witness_gated_agent_mps`) × `3` seeds = **`90` evaluation cells**.
- **Grand Total**: **`32` independent tasks/turns** (`8 + 14 + 10`) evaluated across **`348` total evaluation cells** (`48 + 210 + 90`).
