# Function-output formats and placeholder rejection — development results

Branch `cursor/seed-function-format-compare`. Protocol `0408f34` committed
before scoring; crash-fix `4fc3f9c` treated a truncated body as a syntax
failure. This results commit is separate. Base reviewed `b6b70cf`. Not
confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 1 inspect / 6 format / 2 coder cells, 35 events.
A first live attempt aborted after **10.810 s** on an uncaught wrap of
`ok(item).`; the complete rerun wall was **56.573508 s**. Combined debit
**67.383508 s**. Ledger after this run:
**2566.777111455996 used / 1033.222888544004 remaining**.

`fixed_boundary` stays the default. Learned ranking and memory comparison
were not resumed.

## Request and decoding

`PersistentLocalRuntime.complete` posts a raw `/completion` `prompt`. There
is no chat template and no stop list. `n_predict` is 128, temperature 0,
seed 42. The JSON-function schema requires `function` with `minLength` 8;
that still admits `"ok(item)"`. Prompts now say the value is executable
Python source. `local_model_runtime.py` was not edited.

The same one-word pattern on both earlier tasks matches this schema: a
short string satisfies constrained decoding.

Target still comes from the public-test entry. Request-time discovery of
which function to edit is not implemented.

## 0.5B formats (same tasks and budget)

Best format by the predeclared score, then tie-break: **`json_body`**.

| Task | Format | Raw | Placeholder | Syntax | Executed | Public | Semantic |
|---|---|---|---|---|---|---|---|
| replace `level` | plain_code | yes | no | yes | yes | fail | fail |
| replace `level` | json_function | no | empty | no | prior | fail | fail |
| replace `level` | json_body | yes | no | yes | yes | fail | fail |
| insert `code` | plain_code | no | empty | no | no | fail | fail |
| insert `code` | json_function | yes | no | yes | yes | fail | fail |
| insert `code` | json_body | yes | no | yes | yes | pass | fail |

Plain replace copied the exclusive `<`. JSON-function wrote `ok(item)` /
`code(item)`. JSON-body replace copied `<`, then revised to `return None`
(allowed). JSON-body insert hardcoded `return 'src:beta'`: public pass,
private fail. That is not functional correctness.

## 1.5B coder on `json_body`

| Task | Completions | Public | Semantic | Body |
|---|---:|---|---|---|
| replace `level` | 2 | fail | fail | still `item['level'] < item['cap']` |
| insert `code` | 2 | pass | pass | `item['kind'].lower() + ':' + item['name'].lower()` |

The coding model wrote a general join after a failed attribute-access
first try. The 0.5B model did not. Inclusive-bound replace still failed
on both models.

| Model | Weights | Block wall | Parent RSS |
|---|---:|---:|---:|
| qwen2.5-0.5b | 491,400,032 B | 20.283010 s | 39.609 MiB |
| qwen2.5-coder-1.5b | 1,117,320,768 B | 33.710880 s | 39.609 MiB |

Parent RSS does not include the `llama-server` child. The coder weights
are 2.3× larger and the coder block took 1.7× the 0.5B block wall.

## Next

`json_body` is the better interface here. The 1.5B coder can generate a
new function the 0.5B model only memorized. Inclusive comparison still
needs a real rewrite, not a copied `<`. Do not resume ranking or memory
until replace also executes correctly. Do not merge `main`.
