# Capability milestone — development results

Branch `cursor/seed-capability-milestone`. Protocol `7a654f4` committed
before scoring. This results commit is separate. Base reviewed `33b9fde`.
Not confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 2 ranking sources / 9 ranking / 4 token / 1 feature
/ 5 language cells, 88 events. Family scores reconstructed from execution
records; final patches replayed. Historical audit fingerprints unchanged.
Wall **40.901413 s**. Ledger after this run:
**2474.568897455996 used / 1125.431102544004 remaining**.

`fixed_boundary` stays the default. Learned investigation was not re-run and
is not promoted.

## Ranking on fresh mixed repositories

All three rankers put `compare_op_swap` first and passed the public equality
tests on mixed cues, misleading exclusive documentation, and the two-defect
repo. Private tests failed for the same reason: the applied swap was
`Lt→GtE` (`>=`), which still passes equality and then accepts values above
the bound.

Learned family rates did not beat fixed diagnostic rules or source-frequency
on this grid. Public pass is not private-test correctness.

## Token interface, unconfounded

One new-function task. Revision budget 2 in every cell.

| Cell | Completions | Structural | Private |
|---|---:|---|---|
| raw 128 (budget 256) | 2 | invalid (`create_overwrites`, then symbol action rejected) | fail |
| raw 512 (budget 1024) | 2 | same invalid pair | fail |
| symbol 128 (budget 256) | 2 | invalid then proposed | fail |
| symbol 512 (budget 1024) | 2 | invalid then proposed | fail |

Raising the per-call cap to 512 did not produce a private pass. Symbol
editing reached a structurally valid revision; raw did not. Those two
effects were previously confounded.

## Repository feature

`py_invoice_slug_feature` failed public and private checks. File discovery
and AST `insert_function` / arithmetic operators ran. The local model did
not contribute a queued proposal. Independent replay confirmed the failure.
Required parts were measured, not achieved.

## Conversation quality

| Turn | Kind | Passed | Notes |
|---|---|---|---|
| explain | explanation | no | Did not name `notes`; invented a topic-change story |
| paraphrase | paraphrase | yes | Executed regional totals on the selected file |
| correct | correction | no | Did not switch to `fees` |
| doc_q | document question | no | Repeated a tool preview; did not attribute `fees` |
| topic | topic change | no | Still reported `notes.csv` selected |

Scoring used factual content, attribution and workspace state. Keyword
presence was not enough.

## Next

Keep `fixed_boundary`. Do not promote learned ranking or learned
investigation. A later ranking study needs public tests that distinguish
`<=` from `>=`. Do not merge `main`.
