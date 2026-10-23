# Metal independent-vs-revision comparison — results

Protocol `f072270`. Verifier `valid: true`. Host `MTL0: Apple M4`.
1.5B coder, `k=4`, 128 tokens, no planted `.get` in prompts. Stubbed
call-2 versus call-4 remains control flow only.
`live_advantage_claimed = false`.

CPU ledger **3564.568 s / 0 s debit**. Pinned runtime unchanged.

## Complete assistant cost

| clock | seconds | in the Metal grant? |
| --- | --- | --- |
| startup | 1.565 | no |
| inference | 11.993 | mostly yes |
| retrieval | 0.001 | no |
| execution (private eval) | 0.000 | no; no winner to score |
| verification (split) | 0.000 | public/verifier time sits in unallocated |
| teardown | 0.037 | no |
| accounted | 13.597 | mixed |
| unallocated | 0.922 | public sandbox / JSON / overhead |
| **user total (runner wall)** | **14.519** | **no; this is the user cost** |
| grant-charged `guarded_call` | **12.011** | yes |
| peak process RSS | 1486.359 MiB | ceiling sample only |

Tokens: 3544 input / 546 generated. Process RSS is not Metal heap.
Grant remaining after this file: 600 − 12.011 = 587.989 s on this
study ledger (separate from the closed smoke ledger).

## Code `label(item)` hall/gate

Both arms used 4/4 calls. Independently replayed public pass: **false**
/ **false**. Private 3/3: not run.

Independent unique outputs: **1** — all four were
`return hall.lower() + '/' + gate.lower()`.

Revision unique outputs: **3**. After NameError feedback naming `hall`
and `gate` as input keys, later drafts moved toward `item['hall']` /
`item['gate']` and one truncated `.get` attempt. None passed the
missing-key public cases. Feedback did not supply the finished body.

## Sentence `dockbinding` / `[seed-compare-1]`

Both arms used 4/4. Independently replayed verifier pass: **false** /
**false**. Independent unique outputs: **2** (paraphrases of the fact,
no term, no citation). Revision unique outputs: **4** (the model echoed
JSON feedback instead of writing a grounded sentence).

## Retrieval provenance (offline)

Competing documents retrieve the relevant `doc_id`. Unrelated queries
and missing ids return nothing. A passing sentence must cite the
retrieved source. Updating the same `doc_id` changes `source_hash`;
old unique numbers/tokens fail against the live SQLite row even if
the citation id is reused.

## Claims

No live success advantage. More unique revision strings are not a
passed task. Not learning-to-learn. Ranking stays paused.
