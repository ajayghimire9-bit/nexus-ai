# NEXUS Wave 24 — Cross-Family Meta-Procedure Optimization, Observational Equivalence Quotienting & Interference Immunity Protocol

## 1. Pre-Freeze Scope, Branch & Reused Owners
- **Branch**: `cursor/seed-wave24-cross-family-meta-procedure-quotienting-and-interference-immunity`
- **Base Commit**: `30101c595970ee65abe6b2b024686768eeeee5e6` (`30101c5`)
- **Reused Existing Owners (`REUSED_MODULE_OWNERS`)**:
  - `src/nexus/seed/mechanism_policy.py`: Regularized ridge-regression linear policy fitting (`np.linalg.solve(xtx + l2 * I, xty)`), named public features, stored coefficients, training provenance, and per-feature score contributions.
  - `src/nexus/seed/mechanism_investigate.py`: Replayable investigation decision loop and cost accounting.
  - `src/nexus/seed/correspondence_learner.py` & `src/nexus/seed/mechanism_wave6_correspondence.py`: Competing correspondence hypothesis tracking, public validation before private assessment, and counter/timestamp sensitivity testing (never assuming "ignore stamp").
  - `src/nexus/seed/mechanism_skills.py` & `src/nexus/seed/skill_library.py`: Executable skill storage with input/output signatures, MDL description length, provenance, and rollback/quarantine history.
  - `src/nexus/seed/storage.py` & `src/nexus/evolution1/catalogue.py` (`canonical`, `digest`): Canonical JSON serialization and SHA-256 digesting.
  - `src/nexus/seed/recovery_evaluate.py` & `src/nexus/seed/process_memory.py`: Carried session resource ledger (`FROZEN_CPU_USED_S = 3128.309460455996`, `FROZEN_CPU_REMAINING_S = 471.690539544004`, `0.0s` Track B debit) and process RSS memory sampling.
  - `src/nexus/seed/wave23_focused_meta_learning_and_witness_engine.py`: Scoped `SymbolicKANResidualInducer` on `torch.device("mps")` and elementary AST verification.

---

## 2. Predeclared Causal Questions (H1 vs. H2) & Factorial Design
1. **H1 (Policy-Only Cross-Family Transfer After Task Solutions/Skills Are Cleared)**:
   - *Question*: Does the source-trained Level-2 Meta-Procedure Policy ($\pi_{\text{meta}}$, fitted strictly on source tasks from Families A `INT_SEQ` and B `STR_PARSE` via regularized ridge regression over domain-agnostic structural features) reduce **First-Acquisition Total Work** on completely unseen, family-disjoint Families C (`DICT_RECORD`) and D (`STATE_TRANSITION`) after all task solutions, exact caches, and skills are cleared (`learned_meta_procedure_skills_cleared` vs. `fixed_default_procedure_solver`, `object_level_weights_only_solver`, and `shuffled_meta_procedure_control`)?
2. **H2 (Acquired Compositional Structure + Policy vs. Ordinary Template Reuse)**:
   - *Question*: Does combining $\pi_{\text{meta}}$ with acquired skills and structural skeletons (`learned_meta_procedure_plus_skills`) reduce unseen-family total work and repeated/compositional transfer work compared to strong fixed investigation with ordinary acquired templates (`fixed_procedure_with_templates`) under **identical 2-task MDL promotion rules** (`MIN_TASKS_FOR_PROMOTION = 2`, zero 1-task promotion privilege)?

---

## 3. Family-Disjoint Separation & Structures Absent From Source Training
- **Source Training Suite (`build_wave24_source_training_suite`)**:
  - Contains `2` Track-1 source mapping episodes and `6` Track-2 source tasks drawn **exclusively from Family A (`INT_SEQ`) and Family B (`STR_PARSE`)**.
  - **Structures Completely Absent From Source Training**:
    - **Family C (`DICT_RECORD`)**: Lists of structured key-value records (`list[dict]`), key-grouped summation (`totals[r["k"]] = totals.get(r["k"], 0) + ...`), sequence/timestamp counter-dependent record valuation (`r["val"] + r.get("seq", 0)`), and priority-branch record valuation (`r["val"] * 2 if r.get("prio", 0) == 1 else r["val"]`).
    - **Family D (`STATE_TRANSITION`)**: Sequential state-machine / buffer event traces (`[{"op": ..., "arg": ...}, ...]`), stateful accumulator transitions (`state = ...; trace.append(state)`), and conditional floor-rollback transitions (`state + ev["arg"] if state + ev["arg"] >= 0 else state`).
- **Development Suite (`build_wave24_dev_suite`)**:
  - Separate development fixtures (`w24_dev_*`) used during Phase-1 `pytest` and pre-freeze verifier dry-run validation.
- **Post-Freeze Assessment Suite (`build_wave24_post_freeze_assessment_suite(freeze_commit_sha)`)**:
  - Parameterized by the Commit-1 git SHA (`assessment_seed = int(sha256(freeze_commit_sha)[:16], 16)`) and instantiated once after Commit 1 is frozen and pushed to `origin` and `github`.

---

## 4. Predeclared Sample Sizes, Independent Units, Resource Caps & Thresholds
- **Track 1 (Active Info-Gain Correspondence Discovery)**:
  - `8` independent tasks (`2` first-acquisition domains—one where `stamp` genuinely affects the answer and one where `stamp` is a distractor, `4` repeated transfers, `1` ambiguous public-validation task, `1` out-of-correspondence task) $\times 4$ methods $\times 3$ seeds = **`96` evaluation cells**.
- **Track 2A (Cross-Family Factorial Comparison & Quotient Soundness)**:
  - `18` independent tasks across all 4 families (`4` `INT_SEQ`, `3` `STR_PARSE`, `4` unseen `DICT_RECORD`, `3` unseen `STATE_TRANSITION`, plus `4` diagnostic boundary tasks covering `AMBIGUOUS_WITNESS_FOUND`, `UNIQUENESS_UNKNOWN_BUDGET_EXHAUSTED`, `VIOLATES_DECLARED_DETERMINISTIC_ASSUMPTIONS`, and `NO_PROGRAM_IN_BOUNDED_GRAMMAR`) $\times 6$ methods $\times 3$ seeds = **`324` evaluation cells**.
- **Track 2B (Continual Learning Under 16 Injected Adversarial Distractor Skills)**:
  - `14` solvable independent tasks across all 4 families $\times 3$ hygiene methods (`naive_continual_accumulation_no_hygiene`, `utility_gated_continual_hygiene`, `clean_slate_per_family_oracle`) $\times 3$ seeds = **`126` evaluation cells**.
- **Track 3 (Multi-Family NL Grounding vs. Equal-Tool Pretrained LLM Baseline on Metal GPU)**:
  - `10` independent dialogue turns (`5` dialogues across all 4 families) $\times 3$ methods $\times 3$ seeds = **`90` evaluation cells**.
- **Total**: **`36` independent tasks/turns** (`636` total evaluation cells across Track 1, Track 2A, Track 2B, and Track 3).
- **Resource Caps & Practical Effect Thresholds**:
  - Max statement count per synthesized function: `<= 7` statements, expression depth `<= 3`, loop step cap `<= 200` steps, `0` compound loop boxes.
  - Default candidate budget: `400` equivalence classes (`40` on the budget-exhausted diagnostic task).
  - Required accuracy: `100%` status and private accuracy on all primary methods, `100%` agreement between `ObservationalQuotientWitnessEngine` and exhaustive unquotiented enumeration, and strict work reduction (`< 1.0x`) for H1, H2, and `UtilityGatedSkillHygiene`.

---

## 5. Phase-1 File SHA-256 Digests & Pre-Artifact Constructor Fix Disclosure
- `src/nexus/seed/wave24_cross_family_meta_and_quotient_engine.py`: `8304abc8c942de3c248c88988366e2c3a2c258c08c3e6d1f3a34d50b18155efb`
- `scripts/run_wave24_cross_family_experiment.py`: `a1a95b7442c3786a35aba54a076758b06ce0da5b755b7f031df76becb95f4c8e`
- `scripts/verify_wave24_cross_family_experiment.py`: `5256f7aa117303b7b867d33f844dec7d7d0e8aa3fe4acb2129374939f6517906`
- `tests/test_seed_wave24_cross_family_experiment.py`: `0396b68533888178ab9ad906090902c4f961d67edf00ec42a6de649526bf0059`
- **Transparent Pre-Artifact Commit Note (`f78a129`)**: In initial Phase-1 commit `f78a12900780ab583ecb61a8febafafaeedfe8f7`, `tests/test_seed_wave24_cross_family_experiment.py` ran with `execute_metal_llm=False`, and `ExplicitMetalGrant(granted_by=...)` at line 4065 threw `TypeError: ExplicitMetalGrant.__init__() got an unexpected keyword argument 'granted_by'` before executing any LLM turn or writing any artifact to `artifacts/`. To strictly obey the zero-amend rule (`zero_amend_on_branch == True`), `ExplicitMetalGrant(authorized=True, owner=..., reason=..., ledger_path=..., n_gpu_layers=-1)` was corrected in a forward Pre-Assessment Freeze Commit, `execute_metal_llm=True` was enabled in `tests/test_seed_wave24_cross_family_experiment.py`, and the post-freeze `assessment_seed` is derived via SHA-256 from this forward Pre-Assessment Freeze Commit SHA.
