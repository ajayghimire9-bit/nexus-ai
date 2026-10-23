# Worker division and public missing cases — development results

Branch `cursor/seed-worker-div-confirm`. Protocol `5ab1d1f` committed
before scoring. This results commit is separate. Base reviewed
`e5d41fd`. Not confirmation of learning-to-learn. Not AGI.

Verifier `valid: true` on 1 inspect / 1 audit / 4 confirm cells, 15
events (6 complete / 5 worker / 4 assessment). Scored wall
**85.537099 s**. An earlier attempt timed out at 20 s on the longer
public-case revision and is kept as
`artifacts/seed_worker_div_confirm/seed_worker_div_confirm_timeout.json`
(sha256 `64af3eb08bd7d18f8ac0779c826092b42b568bfcab61ef8b11e292c05883d101`);
the runner timeout was then 45 s. Ledger after both attempts:
**3126.028358455996 used / 473.9716415440039 remaining**.

The worker and prompt stayed frozen: 1.5B / ChatML / `json_body` /
contract / two-stage revision / wired discovery / `ast.Div` allowed /
`compare_python_result`. Ranking and memory were not resumed.
`local_model_runtime.py` was not edited. The closed harder-feature 1/5
was not rescored
(`31713e4d04ef63ca296ef4c78797ca11e4c87203ddce845ea82c3956646dbdc2`).

## Saved `due` replay (no inference)

The historical `quote.py` body `return item['cents'] / 100` was rejected
as `forbidden_ast_node:quote.py:Div`. After allowing true division, the
same files pass public 250→2.5 and assessment 0→0.0, 100→1.0. Expected
floats match int or float within 1e-6; expected ints require an int;
bool is not int. Division by zero is a runtime `ZeroDivisionError`, not
a compile reject.

## Historical revision audit (`total`, `tag`, `fit`)

| Task | Saw feedback | Changed body | Same core bug |
|---|---|---|---|
| `total` | yes: `TypeError` int+dict | yes (`or [0]` → `if 'rows' in item`) | still `sum(item['rows']...)`; never reads `amount` |
| `tag` | no exception; compile `JoinedStr` omitted | yes (shorter f-string) | still an f-string |
| `fit` | no revision | public all-pass | private `KeyError:'value'` never reached the loop |

`total` saw the relevant exception and still summed row dicts. `tag`
never saw `JoinedStr` in `failed_cases`. `fit` had no public missing
`value`, so revision never ran. Compile rejects are now attached to
behavioral feedback.

## Confirmation (fresh IDs, frozen recipe)

Public tests included the empty list and a missing amount on `total`,
and missing `kind` / `name` on `flag`. Private combinations stayed
distinct.

| Task | Family | Body | Public | Private |
|---|---|---|---|---|
| `py_bag_total` | aggregation | `sum(item['rows'] or [0])` | fail (`TypeError` on amounts and missing amount) | fail |
| `py_flag_absent` | missing fields | `':'.join([item.get('kind', ''), item.get('name', '')]).lower()` | **pass** | **pass** |
| `py_rate_div` | arithmetic | `item['amount'] / item['unit']` | **pass** | **pass** |
| `py_enter_both` | combined conditions | `age >= min_age and score >= floor` | **pass** | **pass** |

3/4 private pass. Division now executes. Missing-field `get` worked
after a format repair from a truncated f-string. Aggregation saw the
`TypeError` on both filled and missing-amount public cases and left
the expression unchanged.

## Resources

Confirm block wall **83.506 s**. Combined RSS ~1993–2010 MiB, almost all
`llama-server`. Parent RSS is not that number. Weight-file size is not
runtime memory. Cell walls 10–36 s.

## Next

List-of-records sum still fails after the worker and public-case fixes.
The repair loop reached the exception and did not change the failing
expression. Do not resume ranking, memory, or acquired-experience
comparison. Do not merge `main`.
