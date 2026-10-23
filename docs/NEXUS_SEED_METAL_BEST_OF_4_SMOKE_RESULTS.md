# Metal Best-of-4 smoke — results

Protocol commit `592aa81`. Live collection on
`cursor/seed-lexicon-knowledge-vault`. Verifier `valid: true`. Host
device `MTL0: Apple M4` (not M5). Model 1.5B coder Q4_K_M
`cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
`n_gpu_layers = -1`. Cold start 1.234 s.

CPU ledger **3564.568 s used / 0 s debit**.
`local_model_runtime.py` hash unchanged
`5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`.

## Metal ledger

| field | value |
| --- | --- |
| kind | `metal_session_ledger` |
| used_s | **2.545** |
| remaining_s | 597.455 / 600 |
| peak RSS | **1511.594 MiB** (cap 4096) |
| cell 1 wall | 1.312 s |
| cell 2 wall | 1.232 s |
| runner wall | 5.232 s |

Both batches sat under the 30 s call cap and the 15 s Metal-wall
target. The CPU 3564.568 s ledger was not mixed in.

## Cell 1 — missing-key `mark(item)`

All four raw candidates were identical:

`{"body": "return yard.lower() + '/' + slip.lower()"}`

Temperature 0.0 / seed 42 and temperature 0.35 / seeds 43–45 did not
diverge under `json_body`. Each body is structurally valid and fails
all three public tests (`NameError` on bare `yard` / `slip`). Promoted
winner: **none**. Private 3/3: **not run**. No planted `.get`.

## Cell 2 — lexicon sentence

All four drafts were identical:

`In 2026, the Seed lab stores verified lexicon sentences in the knowledge vault.`

Verifier reasons: `term_missing` (`metalvault`), `frame_mismatch`,
`missing_citation:seed-metal-1`. Promoted winner: **none**.
`write_sleep_jsonl` wrote **0** rows.

## Claims

Best-of-4 Metal sampling executed under the grant. It did not produce
diverse candidates and did not pass public tests or the sentence
verifier. This is not learning-to-learn, not confirmation, and not a
reason to retune the closed stepwise beam. Ranking stays paused.
