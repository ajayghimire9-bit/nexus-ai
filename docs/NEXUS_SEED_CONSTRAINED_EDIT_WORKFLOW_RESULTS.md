# Constrained function edits and one generated-code feature — development results

Branch `cursor/seed-constrained-edit-workflow`. Protocol `e4cbc0d`
committed before scoring. This results commit is separate. Base reviewed
`aa2b015`. Not confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 1 semantic / 2 feature / 4 language cells, 22
events. Catalogue check rebuilt: `py_tag_colon_feature` still has 0
passing AST operators. Historical audit fingerprints unchanged. Wall
**8.966798 s**. Ledger after this run:
**2499.393603455996 used / 1100.606396544004 remaining**.

`fixed_boundary` stays the default. Learned ranking and acquired-memory
comparison were not run and are not resumed.

## Interface versus semantics

NEXUS supplied path, symbol and replace-versus-insert. The model returned
only `function`. Source hashes and previews were recorded.

| Cell | Raw valid | Normalization | Queued | Public | Semantic |
|---|---|---|---|---|---|
| `py_depth_three_point` replace | yes | `wrapped_body` | yes | fail | fail |
| `py_tag_colon_feature` AST | n/a | none | no | fail | fail |
| `py_tag_colon_feature` AST+constrained | yes | `wrapped_body` | yes | fail | fail |

This is an **incorrect body accepted by the interface**, not a correct
body rejected by it.

The replace completion was `{"function": "ok"}`, normalized to
`def ok(item):\n    ok\n`. The insert completion was
`{"function": "echo"}`, normalized to `def tag(item):\n    echo\n`.
Both parse. Neither implements below/equal/above or `kind:name`.

The previous `height.ok` suffix error and `insert_function` on an
existing symbol did not recur.

## Catalogue-inexpressible feature

`formatted_identifier` was locked before outcomes. The AST catalogue
produced two stubs (`return_none`, `return_first`) and passed none of
the public tests. AST-only failed. Constrained model queued a no-op
`tag` and also failed. The model did not add a passing solution beyond
the AST baseline.

## Conversation beyond resource names

| Turn | Kind | Passed | Notes |
|---|---|---|---|
| explain_contents | content | yes | Named north/south and 1/3 from `fees.csv` |
| change_operation | operation | yes | `last_op` became `rows` |
| topic | topic change | yes | Still `fees`; pending cleared |
| return_file | return | yes | `last_op` became `sum` on `fees` |

Naming the source was not enough; contents and the requested operation
were checked.

## Next

Do not resume learned ranking or memory comparison. Generate → queue now
works; execute/revise does not. The immediate bottleneck is a wrapped
identifier treated as a function body. A later check can refuse that
normalization without treating it as a model-written comparison. Do not
merge `main`.
