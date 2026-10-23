# Interrupt, bottleneck and fresh transfer — development results

Branch `cursor/seed-interrupt-and-transfer`. Protocol `8fa9864` committed
before scoring. This results commit is separate. Base reviewed `99c7341`.
Not confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 4 investigation / 3 coding / 15 transfer / 8
language cells, 1179 events. Historical audit fingerprints unchanged.
Wall **26.232319 s**. Ledger after this run:
**2395.682841455996 used / 1204.317158544004 remaining**.

## Conversation interrupt

A leftover coding-workspace question no longer captures later turns.

| Turn | Kind | Pending after | Notes |
|---|---|---|---|
| Implement slug | clarification | set | Asks which workspace |
| List workspaces instead | correction | still set in this run | Replied “none registered”; listing did not re-ask |
| Implement slug | clarification | set | |
| Never mind | cancel | cleared | Dropped |
| Implement slug | clarification | set | |
| Book a flight | unsupported | cleared | Refused; no booking |
| Implement slug | clarification | set | |
| What file is selected? | topic change | cleared | Real empty state |

Cancel, unsupported and topic-change superseded the pending question. The
list-instead turn answered but left the flag set when no workspaces exist;
that clear is now in the follow-up patch and was not used to rescore.

## Coding diagnosis after the two crash fixes

Closed six-area labels, development re-run only:

| Task | Prior class | This run | Outcome |
|---|---|---|---|
| py_retry_last | missing_inference (`doc_id` KeyError) | none | solved / private pass |
| py_levy_then_credit | invalid_edits (`old_text_not_unique`) | invalid_edits | still failed; fallback did not accept the model snippets |
| py_slug_join | incorrect_implementation then invalid revision | incorrect_implementation | first proposal still omitted `slug` |

Largest measured crash is gone: documented-API inference now runs. The
remaining live-model bottleneck is invalid or incomplete edits, not a new
architecture.

## Fresh repair transfer

Genuine AST source `py_hi_inclusive_src` acquired `compare_op_swap`.

| Later | Appropriate? | Memory | Template | Exact cache | Model scratch | None |
|---|---|---|---|---|---|---|
| py_width_ok | yes | pass | pass | miss | fail | fail |
| py_keep_exclusive | no | fail (wrong apply) | fail (wrong apply) | miss | pass | pass |
| py_pair_label | no | not applied | not applied | miss | fail | fail |

Memory tied the ordinary template, beat cache and scratch on the appropriate
instance, and correctly failed when `Lt→LtE` was the wrong repair. One
appropriate success is not a 100% rate.

## Investigation policy

`fixed_boundary` stays the default and is not replaced.

| Method | Match /2 | Calls | Support checks | Probe constructions | Questions |
|---|---:|---:|---:|---:|---:|
| fixed_boundary | 1 | 336 | 322 | 14 | 2 |
| learned | 0 | 72 | 60 | 12 | 0 |

On this pair learned spent fewer support checks and asked no questions, then
matched worse. The six-area grid had the opposite cost pattern at equal
match. Neither is a promotion gate. Learned is cheaper here because ranking
filled a shortlist faster and skipped probing; that cheaper stop was wrong.

## Next

Do not promote the learned policy. Next useful coding work is making
multi-file and new-function proposals structurally applicable without
handwritten task bodies. Do not retune the closed six-area grid. Do not
merge `main`.
