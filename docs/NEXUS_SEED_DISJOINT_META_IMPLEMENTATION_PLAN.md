# NEXUS Seed — Disjoint Meta-Learning Implementation Plan (`seed_disjoint_meta_v1`)

## 1. Two-Commit Scientific Execution Plan

1. **Commit 1 (Locked Pre-Execution Commit)**:
   - Audit and relabel `src/nexus/seed/master/meta_learning.py`, `src/nexus/seed/master/runtime.py`, `src/nexus/seed/conversation.py`, `web/learning-lab/chat.html`, `web/learning-lab/chat.js`, and `docs/NEXUS_SEED_MASTER_ARCHITECTURE.md`.
   - Commit locked protocol (`docs/NEXUS_SEED_DISJOINT_META_PROTOCOL.md`), implementation plan (`docs/NEXUS_SEED_DISJOINT_META_IMPLEMENTATION_PLAN.md`), configuration (`configs/seed_disjoint_meta.json`), experiment-local implementation (`src/nexus/seed/disjoint_meta.py`), host adapter wiring (`src/nexus/seed/experimental.py`, `src/nexus/seed/experimental_worker.py`, `scripts/run_learning_lab.py`), execution runner (`scripts/run_seed_disjoint_meta.py`), independent verifier (`scripts/verify_seed_disjoint_meta.py`), and pre-execution unit/integrity tests (`tests/test_seed_disjoint_meta.py`).
   - Verify all tests and `scripts/check_repository.py`, then commit and push Commit 1 before generating any target outcomes.
2. **Single Registered Run & Independent Verification**:
   - Execute `scripts/run_seed_disjoint_meta.py` once through `Sandbox` (`seed-disjoint-meta-1`) to generate `artifacts/seed_disjoint_meta.json`.
   - Execute `scripts/verify_seed_disjoint_meta.py --write` once to independently recompute all canonical/semantic hashes, splits, traces, metrics, intervals, and advancement gates into `artifacts/seed_disjoint_meta_audit.json`.
3. **Commit 2 (Post-Run Results & Documentation Commit)**:
   - Record honest results in `docs/NEXUS_SEED_DISJOINT_META_RESULTS.md`, `web/learning-lab/experimental.html`, `README.md`, `docs/NEXUS_CANONICAL_CURRENT_STATE.md`, `docs/NEXUS_PROGRESS.md`, `docs/NEXUS_NEXT_EXPERIMENT.md`, `docs/NEXUS_HYPOTHESIS_REGISTER.md`, `docs/NEXUS_FULL_RESEARCH_REGISTRY.md`, `docs/NEXUS_CODE_REUSE_MAP.md`, `docs/MASTER_CONTEXT.md`, and `artifacts/seed_disjoint_meta_changes.json`.
   - Run the complete test suite and `scripts/check_repository.py`, then commit and push Commit 2.

## 2. Module Responsibilities

- [`src/nexus/seed/disjoint_meta.py`](../src/nexus/seed/disjoint_meta.py):
  - Experiment-local length 1–3 list grammar and canonicalizer $C(p)$ over $O = (\text{reverse}, \text{sort}, \text{unique}, \text{increment}, \text{even})$.
  - Exhaustive commutation proof over $X_{\text{probe}}$ (781 inputs) and semantic behavior hashing $h(p)$.
  - Global source/target partition ($\mathcal{C}_{\text{source}} = 17$, $\mathcal{C}_{\text{target}} = 24$) and 8-family non-repeating assignment.
  - Secondary sequence domain (`action_token_sequence`) with concrete operations (`reverse_actions`, `order_actions`, `dedup_actions`, `advance_mag`, `filter_even_mag`) and explicit operator-role mapping.
  - Candidate learner (`structural_meta_prior`) and all 6 baselines (`flat_catalogue`, `shortest_program`, `operator_frequency`, `exact_macro_cache`, `random_ordering`, `bayesian_model_based`).
  - Strict artifact-derived scientific acceptance gate `evaluate_disjoint_meta_artifact(raw_artifact, locked_protocol, locked_config)`.
- [`scripts/verify_seed_disjoint_meta.py`](../scripts/verify_seed_disjoint_meta.py):
  - Independent stdlib-based verifier that implements its own primitive semantics, canonicalizer, semantic probe table, ridge solver, and gate evaluator without calling `MetaLearningEngine`, the candidate ranker, or saved summary functions.
