# Guarded-template reuse on fresh cases — development results

Branch `cursor/seed-guarded-template-reuse`. Protocol `79b13c4` committed
before scoring. This results commit is separate. Base reviewed `e00b96c`.
Not confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 1 source / 15 transfer cells, 23 events. Historical
audit fingerprints unchanged. Wall **14.883401 s**. Ledger after this run:
**2433.667484455996 used / 1166.332515544004 remaining**.

`fixed_boundary` stays the default. Learned was not re-run and is not
promoted.

## Equally guarded comparison

Genuine AST source `py_cap_inclusive_src` acquired `Lt→LtE`. Memory rebound
that inclusive swap onto a later `>` when the public requirement was
inclusive. The ordinary template stayed `Lt→LtE` and used the same
inclusive/exclusive/ask gate.

| Later | Role | Memory | Guarded template | Scratch |
|---|---|---|---|---|
| py_span_ok | same polarity | apply / correct reuse | apply / correct reuse | fail |
| py_floor_ok | inclusive lower | apply / correct reuse | abstain / not applicable | fail |
| py_reject_floor | opposite | refuse / correct hold | refuse / correct hold | pass |
| py_note_join | unrelated | abstain / correct hold | abstain / correct hold | fail |
| py_threshold_fix | clarification | ask / correct hold | ask / correct hold | pass |

Memory: **2 correct reuse, 0 harmful, 0 unnecessary abstention, 3 holds**.
Guarded template: **1 correct reuse, 0 harmful, 1 unnecessary abstention, 3
holds**. Advantage is the one fresh lower-bound instance. Both refused the
exclusive floor and asked on the ambiguous threshold. Scratch passed 2/5
where the unpatched exclusive comparison already matched.

Same-repair private rate 2/2 is still a two-task development pair. The
`one_success_is_not_100_percent` flag remains. Cost: 6 scratch completions,
1967 input / 388 generated tokens.

## Next

Keep `fixed_boundary`. Do not promote learned. Do not retune closed grids.
Do not merge `main`.
