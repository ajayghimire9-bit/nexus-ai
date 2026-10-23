# Selective reuse — development results

Branch `cursor/seed-selective-reuse`. Protocol `6629d1b` committed before
scoring. This results commit is separate. Base reviewed `e6515fa`. Not
confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 2 coding / 1 source / 12 transfer cells, 25 events.
Historical audit fingerprints unchanged. Wall **23.101242 s**. Ledger after
this run: **2418.784083455996 used / 1181.215916544004 remaining**.

`fixed_boundary` stays the default. Learned was not re-run and is not
promoted: a lower call count that solves fewer tasks is not a benefit.

## Retrieved repairs are proposals

Genuine AST source `py_hi_inclusive_src` acquired `compare_op_swap`. Memory
then checked the later request and public tests only.

| Later | Role | Memory | Template | Scratch private |
|---|---|---|---|---|
| py_width_ok | same repair | apply / correct reuse | apply / correct reuse | fail |
| py_keep_exclusive | opposite | refuse / correct hold | apply / harmful reuse | pass |
| py_pair_label | unrelated | abstain / correct hold | miss / correct hold | fail |
| py_cutoff_ambiguous | clarification | ask / correct hold | apply / harmful reuse | pass |

Memory: **1 correct reuse, 0 harmful reuse, 0 unnecessary abstention, 3
correct holds**. Inclusive and exclusive produced different decisions. The
ambiguous cutoff asked whether equality should pass. Private tests were not
used to choose.

The ordinary template still applies `Lt→LtE` whenever the family matches: it
tied memory on the appropriate instance and harmed the exclusive and
ambiguous ones. Scratch passed 2/4 private suites (exclusive and ambiguous
already matched the unpatched exclusive comparison). One appropriate memory
success is not a 100% rate.

Cost: 4 scratch + 4 coding completions; 1306 + 1744 input tokens; 305 + 318
generated tokens.

## Structured edits vs functional correctness

Valid-edit rate is reported separately from private-test pass.

| Task | Structural | Valid-edit rate | Private | Class |
|---|---|---:|---|---|
| py_slug_join | 0/2 | 0.0 | fail | invalid_edits (`duplicate_definition:echo`) |
| py_levy_then_credit | 0/2 | 0.0 | fail | invalid_edits (JSON then `symbol_not_found:apply_levy`) |

Revisions saw the staged source and the validation error; both second rounds
still failed. The model used symbol-targeted actions and still proposed
invalid edits. That is a remaining live-model bottleneck, not a reason to
add architecture.

## Next

Keep `fixed_boundary`. Do not promote learned. Do not retune closed grids.
Do not merge `main`.
