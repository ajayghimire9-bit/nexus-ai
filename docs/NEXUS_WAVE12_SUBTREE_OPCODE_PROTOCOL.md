# NEXUS Wave 12 Pre-Registered Protocol: Subtree Invention and Opcode Accounting

**Branch:** `cursor/seed-wave12-subtree-invention-and-opcode-accounting`  
**Parent Commit:** `5777ea2` (`cursor/seed-wave11-typed-program-enumerator`)  
**Track B Policy:** LLM/coding closed (`model_calls == 0`, `frozen_debit_s == 0.0`)

## Two-commit physical separation

Commit 1 freezes the learner, runner, verifier, and unit tests. It must
not contain `mechanism_wave12_fresh_assessment.py` or any
`*wave12*assessment*` path. Commit 2 may create that assessment file
once, run the single-shot grid, and record results. Frozen Commit 1
files must stay byte-identical.

## Frozen SHA-256 digests (filled immediately before Commit 1)

- `src/nexus/seed/wave12_subtree_opcode_learner.py`: `2a79c50b5b324c0b0443aaedd5502a70bf8eb34a77b4b266cc556fa2afc540f4`
- `scripts/run_wave12_subtree_opcode_assessment.py`: `8033c79d775abdf3e46673d16950f9681f51811a7b7e7969a5f8346b41aca0aa`
- `scripts/verify_wave12_subtree_opcode_enumerator.py`: `08091081c9c4e10ddd617cf9afbdd5a8094d20349e16d1b042b772b3614c2aef`
- `tests/test_seed_wave12_subtree_opcode.py`: `51a1ff441a957ca43cffa4cffd219fd17e82fe4779c8699473f3778c6a73bba3`

## Architecture

1. Static constants are only INT `(0, 1, 2)` and empty SEQ `()`.
2. `extract_task_constants(public_observations)` supplies differential
   output tokens and at most two length thresholds.
   `const_extraction_work = len(public_observations)`.
3. Event-triggered MDL compression invents `EvolvedMacroNode` operators
   from recurring internal subtrees (`3 <= size <= 6`) as well as whole
   roots. `mdl_gain = (occ-1)*(size-1) - size`.
4. Dual identities:
   `total_work == probe_work + role_probe_work + const_extraction_work
   + gate_evals + archive_lookup_evals + synthesis_evals +
   compression_evals + compile_cost + schema_distill_cost`
   and
   `total_primitive_op_steps == synth + gate + archive + probe +
   compression primitive steps`.
5. `PiecewiseProgramAST` supports one- and two-guard programs.
6. Five label-blind methods share one enumerator:
   `equal_typed_scratch`, `ordinary_persistent_memoization`,
   `nexus_whole_macro_only`, `nexus_typed_without_pruning`,
   `nexus_typed_full`.

## Wave-11 audit disclosures carried forward

`w11a` closed on runner `suite_totals` vs `totals["suite"]`. `w11b`
closed on verifier `output` vs `observed_output`. Wave-12 tests replay
those exact keys on a synthetic in-memory payload before Commit 1.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_wave12_subtree_opcode.py -q
PYTHONPATH=src:.deps python3 scripts/run_wave12_subtree_opcode_assessment.py
PYTHONPATH=src:.deps python3 scripts/verify_wave12_subtree_opcode_enumerator.py
```
