# Scoped identification, charged indexing, insertion and staging — locked development protocol

Base: reviewed tip `0a8df5d` of `cursor/seed-capability-widening-coding`.
Branch `cursor/seed-scoped-id-staging`. Authored source-development work, never
confirmation. Closed audit artifacts stay unread as new scores. Do not edit
`src/nexus/seed/local_model_runtime.py` (hash-pinned).

Executable source of truth: `configs/seed_scoped_id_staging.json`.
Verifier: `scripts/verify_seed_scoped_id_staging.py`.
Runner: `scripts/run_seed_scoped_id_staging.py`.

`identified` counts only `identified_within_catalogue`. Publishing a staged
repository requires a passing test receipt bound to the exact staged-file
hashes. Repair memory stores parameterized AST transforms and persists them.
`local_model_per_file` is one `complete()` per file under a shared intent, not
`apply_per_file` helpers. Families were chosen before scoring:
`comparison_boundary`, `missing_function`, `null_default`. Assessment instances
are new members of those families, not historical failures selected after the
fact.

## Questions

1. Can scoped identification statuses replace shortlist certainty without
   improving the score by renaming? `identified` counts only
   `identified_within_catalogue`. `unique_among_checked` is reported, not a win.
   Zero survivors among 24 checked programs is `no_checked_candidate_fits` when
   catalogue remainder is nonzero. `catalogue_inconsistent` requires every
   catalogue candidate checked and contradicted.
2. Does a charged behavioral index reduce executed candidates versus simple
   enumeration and ordinary caching? Static length theorems may eliminate
   without a current-input call. Empirical fingerprints may reorder only. They
   must not discard a potentially correct program. Stratified widening is
   compared with ranked widening; one family representative does not eliminate
   siblings.
3. Do `insert_function` / `insert_after_symbol` (qualified symbol, source hash,
   scope, duplicate and syntax checks, missing `end_lineno` fallback) let a
   proposer add a function without reproducing an existing block? The
   deterministic baseline may insert a generic stub. It must not contain a
   handwritten midpoint body.
4. After the revision work-queue fix, does a shared staging workspace publish
   only after syntax and public-test validation? Inspect raw completions,
   generated-token counts and API stop reasons. Do not claim truncation caused
   failures. Compare per-file generation with a larger single-response budget
   under comparable total token/time.
5. Does repair-schema memory transfer to new instances of predeclared families
   better than ordinary exact caches, after charging acquisition? Families are
   chosen before scoring. One success is not a 100% rate. Do not pick
   assessment tasks because a baseline already failed them.
6. Does a workspace header generated from registered capabilities, active
   files, pending clarification and tool results make replies describe real
   state and ask the needed question? Missing coding-workspace selection must
   trigger deterministic clarification. Header input tokens are recorded.

## Gates

No automatic promotion. Learning-to-learn remains unestablished unless a
predeclared transfer comparison beats ordinary templates and caching after
acquisition costs. Do not merge `main`.
