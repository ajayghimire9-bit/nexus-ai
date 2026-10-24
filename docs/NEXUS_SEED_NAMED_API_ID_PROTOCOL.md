# Named API-ID schema — protocol

Isolated branch `cursor/seed-named-api-id` from reviewed
`cursor/seed-equal-inclusive` `4def313`. Protocol committed before
scoring. Opened positional API cells (`api_id_floor`, `api_id_stitch`,
`api_eq_ceil`, `api_eq_glue`) are not rescored. Not confirmation. Not
learning-to-learn. Ranking and broader learning stay paused. Do not
merge `main`.

## Questions

On a fresh frozen grid, with a named parameter-to-ID schema:

1. Does the model request satisfy that schema?
2. Did it bind the correct fields?
3. Does the assembled program satisfy the task?

The direct baseline receives the same interface brief and the same
one-call generation budget. Extra bindings still never assemble.

## Grid

| ID | Phenomenon | Gold bindings |
| --- | --- | --- |
| `api_nb_band` | two numeric fields plus a list | `vals, lo, hi` → `field.*` |
| `api_nb_stamp` | optional default `mark` | `text` only |
| `api_nb_over` | list vs element | `value`→`elem.loads`, `floor`→`field.floor` |
| `api_nb_scale` | list, not element | `vals`→`field.vals`, `factor`→`field.factor` |

Methods: `direct` and `named_id`. One model call each. Same
`interface_brief` (API IDs, parameter names and optional flags, field
IDs, compact interface). `named_id` returns
`{"api_id", "bindings": {param: field_id}}`. Direct writes the function.

## Scores (separate)

- `schema_ok`: parsed object matches the named schema (API enum, bindings
  object, field-ID values). Not binding correctness.
- `bindings_correct`: named bindings equal gold.
- `task_satisfied`: assembled executable program passes private tests
  (`named_id`) or private pass (`direct`).

Selection is not generally solved. Invalid bindings never become calls.

## Decision rule

A useful named-schema result requires higher `schema_ok` and
`bindings_correct` than the previous positional extra/`elem.*` miss,
and `task_satisfied` on the assembled program, without inventing
arguments. Direct is the equally informed generation baseline. Binding
gains without task satisfaction are incomplete.

## Budget

Standing local-CPU grant. 8 cells × 1 call. Cap 80 / 900 s. Frozen
ledger, product chat and Metal unused.

## Verifier

Replay saved programs against private tests. Do not trust success flags.
