# NEXUS Wave 13 Pre-Registered Protocol: Bounded Subtree and Opcode Accounting

**Branch:** `cursor/seed-wave13-mdl-guarded-subtree-and-bounded-macro-beam`  
**Parent Commit:** `6bdf9ae` (Wave 12 closed developmental / invalid)  
**Track B Policy:** LLM/coding closed (`model_calls == 0`, `frozen_debit_s == 0.0`)

Wave 12 (`e940b82` → `6bdf9ae`, `w12f_*`) is permanently closed. This
protocol does not amend those commits or reuse that suite.

## Two-commit physical separation

Commit 1 freezes the learner, runner, verifier, unit tests, Wave-12
postmortem, and this protocol. It must not contain
`mechanism_wave13_fresh_assessment.py` or any `*wave13*assessment*`
path. Commit 2 may create that assessment file once, run the single-shot
grid, and record results. Frozen Commit 1 files must stay byte-identical.

## Frozen SHA-256 digests (filled immediately before Commit 1)

- `src/nexus/seed/wave13_bounded_subtree_learner.py`: `20fae5c0472833e182c9087f42657f3acf1c6cc811060da258005b3f042dd869`
- `scripts/run_wave13_bounded_subtree_assessment.py`: `0dc214674723af4b86d32248e719ea20e242d320664b5a088b87754aaa6af182`
- `scripts/verify_wave13_bounded_subtree_enumerator.py`: `110ba74a96a6de51237be17ab1c6ce67e29f5659fad3a70bc0edd22f11f070a7`
- `tests/test_seed_wave13_bounded_subtree.py`: `8644487621f691b21498ad6cf0e159aa13acd568365213fd3d8caab17d34d222`

## Architecture (four Wave-12 fixes)

1. Static constants are only INT `(0, 1, 2)` and empty SEQ `()`.
2. `extract_task_constants(public_observations)` supplies differential
   output tokens and at most two length thresholds.
   `const_extraction_work = len(public_observations)`.
3. **Fix 1.** Evolved macros never enter Tier-3. Tier-1 is a
   relevance-gated direct / 1-wrapper macro beam. Tier-2 is the cold
   signature archive. Tier-3 enumerates pure atomic trees only.
4. **Fix 2.** Shared atomic cores through size 5; sizes 6–7 are
   observation-guided affix/unary wrappers. Identical for all 5 methods.
5. **Fix 3.** Internal subtree anti-unification (`4 <= size <= 6`) after
   two wrapped solves; L2 when a later root wraps an L1 macro.
   `nexus_whole_macro_only` promotes whole roots only.
6. **Fix 4.** Collect every public-consistent `(G, T)`, query up to 4
   discriminating probes, and require confirmatory holdouts on 2-guard
   programs (`>= 3` examples per residual branch).
7. Dual identities:
   `total_work == probe_work + role_probe_work + const_extraction_work
   + gate_evals + archive_lookup_evals + synthesis_evals +
   compression_evals + compile_cost + schema_distill_cost`
   and
   `total_primitive_op_steps == synth + gate + archive + probe +
   compression primitive steps`.
8. Five label-blind methods share one enumerator:
   `equal_typed_scratch`, `ordinary_persistent_memoization`,
   `nexus_whole_macro_only`, `nexus_typed_without_pruning`,
   `nexus_typed_full`.

## Wave-11 / Wave-12 audit disclosures carried forward

- `w11a`: runner `suite_totals` vs `totals["suite"]`.
- `w11b`: verifier `output` vs `observed_output`.
- Wave 12: assessment created before Commit 1. Wave-13 tests replay the
  exact JSON keys and the Commit-1 blindness check on a synthetic
  payload **before** the assessment module exists.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_wave13_bounded_subtree.py -q
PYTHONPATH=src:.deps python3 scripts/run_wave13_bounded_subtree_assessment.py
PYTHONPATH=src:.deps python3 scripts/verify_wave13_bounded_subtree_enumerator.py
```
