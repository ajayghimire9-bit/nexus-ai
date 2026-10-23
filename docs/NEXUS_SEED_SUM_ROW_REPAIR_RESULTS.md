# Compact sum-row TypeError repair — development results

Branch `cursor/seed-worker-div-confirm`. Protocol `fc5ae21`, amendments
`791a231` and `b953201` committed before the scored run. This results
commit is separate. Base reviewed `490ab00`. Not confirmation of
learning-to-learn. Not AGI.

Verifier `valid: true` on 1 inspect / 1 audit / 4 confirm cells, 16
events (6 complete / 6 worker / 4 assessment). Scored wall
**66.328054 s** (confirm block **64.638989 s**). Two earlier attempts
are kept and charged: keyword-timeout partial
`artifacts/seed_sum_row_repair_confirm/seed_sum_row_repair_confirm_partial.json`
(sha256 `d7a41905de0e72a4f9ad9996e7ed99bd44386d4f5e4ab8fd191c740ec6f68efe`,
32.150602 s) and compact-initial 0/4
`artifacts/seed_sum_row_repair_confirm/seed_sum_row_repair_confirm_compact_initial.json`
(sha256 `023024e97b2cf5dc195ea3c02c8d77e05bdaab2ddd7593d456595bea115780bf`,
28.526798 s). Ledger after all three:
**3255.314914455996 used / 344.685085544004 remaining**.

The worker and prompt stayed frozen except the declared repair-loop
fixes: 1.5B / ChatML / `json_body` / contract / two-stage revision /
wired discovery / `ast.Div` + `ast.keyword` / compact unprojected-sum
revision. Ranking and memory were not resumed.
`local_model_runtime.py` was not edited. Closed harder-feature 1/5
(`31713e4d04ef63ca296ef4c78797ca11e4c87203ddce845ea82c3956646dbdc2`)
and worker-division 3/4 (`490ab00`) were not rescored.

Scored artifact
`artifacts/seed_sum_row_repair_confirm/seed_sum_row_repair_confirm.json`
sha256 `50d65e1b1a16527de826dc006e30856af165e9000e7d5ee87d44474eeb689426`.

## Offline (0 model, 0 s debit)

`compile_check` accepts
`sum((r.get('amount') or 0) for r in (item.get('rows') or []))`,
list-comprehension and `map(lambda ...)`, and that body passes
`py_bag_total` public/private cases. Compact feedback names dict
element keys `amount` and requires numeric extraction defaulting to 0.
Identical AST and guard-only revisions of `sum(item['rows'] or [0])`
are rejected as `sum() requires per-row numeric extraction over dict
elements`. `sum(..., default=0)` now compiles (`ast.keyword`).

## Confirmation (fresh IDs)

| Task | Family | Attempt 1 → Attempt 2 | Public | Private |
|---|---|---|---|---|
| `py_kit_sum` | nested bag | `sum(item['rows'], default=0)` → `{'body': '...'}` | fail | fail |
| `py_mark_empty` | absent flag | `item['kind'].lower() + ':' + item['name'].lower()` → f-string | fail (`JoinedStr`) | fail |
| `py_share_div` | rate division | `item['amount'] / item['unit']` (no revision) | **pass** | **pass** |
| `py_pass_both` | compound threshold | `age >= min_age and score >= floor` (no revision) | **pass** | **pass** |

2/4 private pass. Kit revision used the compact prompt (failed
expression + two failing public cases, 5.667721 s, no 20 s timeout)
and named keys `["amount"]`. The worker error was
`TypeError: sum() got an unexpected keyword argument 'default'`, not
int+dict; the revision dropped `sum` instead of projecting `amount`,
so the no-op/bare-container reject did not fire. Mark used the long
behavior prompt (19.130592 s) and replaced missing-field `get` with a
forbidden f-string.

## Resources

Confirm block wall **64.638989 s**. Combined RSS ~2118–2146 MiB, almost
all `llama-server`. Parent RSS is not that number. Weight-file size is
not runtime memory. Cell walls 8.7–29.1 s. Target ledger debit < 25 s
was missed; the scored run is the honest 66 s figure.

## Next

List-of-records sum still fails after compact shape feedback. The
1.5B coder does not emit a generator/list-comp projection from that
text. Do not resume ranking, memory, or acquired-experience
comparison. Do not merge `main`.
