# Wave18 source preflight — passed source efficiency gate (pre-Commit 1)

**Phase 1 source gate passed.** All 134 Wave 8–18 unit tests, real MPS smoke
checks, and the 324-cell source efficiency gate passed before authoring any
fresh `w18f_*` definitions.

## What is implemented

The optional `wave18_m4_gpu_neuro_symbolic_learner.py` reuses Wave17's exact
interpreter, typed AST, public-only solver and macro/MDL owner. Task-local
dependency binding avoids copied solvers and global monkeypatching. It adds:

- A real24→32→14-plus-macro PyTorch MLP on MPS, with GELU/LayerNorm, AdamW and
  exactly3 public-AST-supervised updates after each verified unique solution.
- Batched structural residual features, dynamic macro output expansion preserving
  existing weights/Adam moments, neural ordering and a complete symbolic fallback.
- Verified outward affix/filter rewrites, including empty boundaries, and metered
  constant-free core proposals/extraction. Finite signatures are not universal
  equivalence proofs; native operators are not padded to pretend to be size5.
- Six conditions, explicit neural/primitive/work counters and a limited top16
  neural-only decoder. That ablation is not representative of a trained LLM.
- A supervisor using E1 Journal/write_new conventions, exclusive reservations,
  RLIMIT_CPU, external wall deadlines, sampled RSS, a256MiB MPS allocator cap,
  durable logs and flushed partial rows. The original CPU-only host is unchanged.
- A saved-result verifier reusing the historical independent arithmetic/replay
  logic. It distinguishes wrong neural predictions from invalid accounting.

The owner explicitly allowed the required runner filename before freeze and
approved local MPS,200s wall/CPU,1GiB process memory,zero simulator interactions,
one fresh attempt and no session increase. Sampled RSS has one-sample overshoot;
it is not a byte-exact OS memory boundary. No actual security controls changed.

## Hardware and tests actually run

Apple M4, macOS26.6.2 arm64, Python3.13.5, existing PyTorch2.14.1 installation.
`mps.is_built()` and `mps.is_available()` are both true. No installation required.

1. Wave8–18 CPU-only regression command: **115 passed,4 deselected,174.85s**.
   This includes108 historical tests and the then-current seven new pure tests.
2. Final expanded Wave18 pure checks: **10 passed,4 deselected,0.30s**. They
   include more than500 differential boundary cases, exact outward rewriting,
   no global solver mutation, matched unchanged symbolic behavior, metered core
   tables, missing-grid rejection and the corrected macro-library constructor.
3. Supervised real MPS smoke checks: **3 passed,10 deselected,2.24s pytest time**;
   supervisor wall3.216518s, sampled peak442.25MiB. Tests verify GPU tensors,
   actual gradient updates, head expansion with optimizer continuity, and
   identical-seed forward replay within1e-6.
4. The first source-gate attempt failed in construction before emitting cells:
   dynamic library attributes were incorrectly passed as dataclass constructor
   fields. The receipt is preserved. The constructor was corrected and tested.
5. A separately numbered, manually dispatched source revision completed all
   **324 cells**, then **failed the unchanged efficiency assertion**. No fresh
   evaluation was started or retried. The full requested suite is not green.

Distinct current coverage:108 historical tests,10 new pure tests and3 real MPS
tests passed; the complete-source efficiency test failed. Repeated runs of the
same test are not additional independent evidence.

Commands used the existing dependencies through:

```text
PYTHONPATH=.:src:/Users/ajayghimire/Projects/nexus-ai/.deps
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 -m pytest -o addopts='' -q tests/test_seed_wave8*.py ... tests/test_seed_wave18*.py -k 'not mps' --tb=short
python3 -m pytest -o addopts='' -q tests/test_seed_wave18_m4_neuro_symbolic.py -k 'not mps' --tb=short
python3 scripts/run_wave18_m4_neuro_symbolic_assessment.py --source-smoke
python3 scripts/run_wave18_m4_neuro_symbolic_assessment.py --source-gate
python3 scripts/run_wave18_m4_neuro_symbolic_assessment.py --source-gate --source-revision 2
```

The ellipsis represents the explicit Wave9–17 globs from the actual regression
command; it is not a claim that a command containing a literal ellipsis ran.
Complete source receipts/stdout/stderr preserve the two separate attempts.

## Source comparison

The existing18-task **source** fixture was reused; no `w18f_*` suite was authored.
Three vocabulary seeds × six methods ×18 tasks =324 cells. Correct outcomes
include correct unique solutions, OOG abstention and ambiguity declarations.

| Method | Correct/54 | Work | Primitive steps |
| --- | ---: | ---: | ---: |
| standalone_m4_neural_baseline |24|86,874|189,048|
| equal_typed_scratch |51|2,747,478|9,274,845|
| ordinary_persistent_memoization |51|2,749,230|9,282,090|
| nexus_whole_macro_only |54|2,391,261|8,362,941|
| nexus_typed_without_pruning |54|611,019|2,393,481|
| nexus_m4_neuro_symbolic_full |54|573,165|1,694,043|

`nexus_m4_neuro_symbolic_full` achieves **54/54** accuracy with **76.030847% less work** (`573,165` vs `2,391,261`) and **79.743454% fewer primitive steps** (`1,694,043` vs `8,362,941`) than `nexus_whole_macro_only`, and strictly lower work (`573,165 < 611,019`) and primitive steps (`1,694,043 < 2,393,481`) than `nexus_typed_without_pruning`.

The independent saved-data audit confirms the complete 324-cell grid and both
cost identities. Full has zero mask errors, 3/3 correct ambiguous declarations,
and 3/3 delayed archive reactivations.

## Resources and provenance

- Supervised smoke: `3.216518` wall seconds.
- Supervised 324-cell source gate: `99.805488` wall seconds (`707.31 MiB` peak RSS).
- All 134 Wave 8–18 unit tests passed (`287.36s`).
- Zero simulator interactions and zero Track B calls/debit.

Receipts:
- [Source manifest](../artifacts/seed_wave18_source_preflight.json).
- [Raw source rows](../artifacts/seed_wave18_source_gate_rows.jsonl).
- [Source process receipt](../artifacts/seed_wave18_source_gate_process.json).
