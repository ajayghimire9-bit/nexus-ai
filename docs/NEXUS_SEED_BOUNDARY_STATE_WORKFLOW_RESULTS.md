# Boundary evidence, conversation state and one workflow — development results

Branch `cursor/seed-boundary-state-workflow`. Protocol `765ffcd` committed
before scoring. This results commit is separate. Base reviewed `01a434b`.
Not confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 2 boundary / 2 workflow / 4 language cells, 22
events. Historical audit fingerprints unchanged. Wall **15.857908 s**.
Ledger after this run:
**2490.426805455996 used / 1109.573194544004 remaining**.

`fixed_boundary` stays the default. Learned ranking was not re-run and is
not promoted.

## Teacher-labeled boundary evidence

| Cell | Public suite | Evidence | Accepted | Private |
|---|---|---|---|---|
| `py_span_three_point` | below / equal / above | resolved | yes (`span.py:ok:lt_to_lte`) | pass |
| `py_span_equal_only` | equal only | missing below/above | no | fail (unpatched) |

Candidate disagreement was not used. Private tests stayed assessment-only.
Equality-only public tests no longer accept `<=` or `>=`.

## Proposal lifecycle

Inference ran on both workflow cells. Raw JSON was parsed. Validation
rejected every model edit. Queue insertion never occurred.

| Project | Round 1 | Round 2 | Verdict |
|---|---|---|---|
| development `width` | `symbol_not_found:width` | `duplicate_definition:ok` | `no_usable_edit` |
| fresh `height` | `unsupported_patch_suffix` (`height.ok`) | `duplicate_definition:ok` (body used `<=`) | `no_usable_edit` |

This is “the model produced no usable edit,” not “the orchestration
discarded a usable proposal.” The fresh second completion wrote the
correct inclusive comparison and still failed because `insert_function`
cannot replace `ok`.

## One complete workflow, then a frozen fresh project

Both cells recorded all six stages: discovery → proposed edits →
execution → failure feedback → revision → accurate explanation.
Structural validity came from the AST `Lt→LtE` operator. Functional
correctness (private below-bound assessment) passed on both projects.
The local model did not contribute the accepted patch.

## Conversation state

| Turn | Kind | Passed | Notes |
|---|---|---|---|
| explain | explanation | yes | Named `notes` and the selected file |
| use_fees | correction | yes | Selected `fees.csv` before the next answer |
| doc_q | document question | yes | `Source file: fees.csv` |
| topic | topic change | yes | Still `fees`; pending cleared |

Scoring used factual content, attribution and workspace state.

## Next

Keep `fixed_boundary`. Do not promote learned ranking. The immediate
model bottleneck is validation of symbol edits, not ranking or
orchestration discard. A later workflow check should freeze this
inclusive-bound recipe and use a fresh project the AST catalogue cannot
solve. Do not merge `main`.
