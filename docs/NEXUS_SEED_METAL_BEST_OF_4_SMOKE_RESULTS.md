# Metal Best-of-4 smoke — results

Protocol commit `592aa81`. Live collection on
`cursor/seed-lexicon-knowledge-vault`. Verifier `valid: true`. Host
device `MTL0: Apple M4` (not M5). Model 1.5B coder Q4_K_M
`cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
`n_gpu_layers = -1`. Cold start 1.234 s.

CPU ledger **3564.568 s used / 0 s debit**.
`local_model_runtime.py` hash unchanged
`5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`.

## Metal ledger and resource claims

The grant charges only `MetalGrantEnforcer.guarded_call` wall: the two
Best-of-4 generation batches. That sum is **2.545 s**. Runner wall is
**5.232 s** and also includes llama-server cold start (1.234 s),
sandbox scoring, SQLite ingest, verifier time, and teardown. Startup
and CPU scoring are **not** Metal-grant seconds and are **not** CPU
scientific-ledger seconds (CPU debit remains 0; frozen used
**3564.568 s**).

| field | value | in the grant? |
| --- | --- | --- |
| kind | `metal_session_ledger` | yes (file only) |
| grant-charged wall | **2.545 s** | yes |
| remaining grant | 597.455 / 600 s | yes |
| cell 1 generation | 1.312 s | yes |
| cell 2 generation | 1.232 s | yes |
| runner wall | **5.232 s** | no; report separately |
| cold start | 1.234 s | no |
| sampled process RSS | **1511.594 MiB** | ceiling check only |

RSS is parent-plus-llama-server process RSS, sampled immediately
before and after each `guarded_call`. That cannot prove the absence of
a transient spike between the two samples, and process RSS is not
total Metal / unified-memory allocation.

The smoke artifact did not log per-request `/completion` payloads.
Identical drafts therefore do not prove that temperature or seed were
dropped. A later sampling audit records those posted fields.

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
`write_sleep_jsonl` wrote **0** rows. That empty export is correct:
failed drafts must not become training examples merely because they
were generated locally.

Facts and the `metalvault` binding from this cell live in
`vault.sqlite` and `capsules.sqlite`, not in `metal_ledger.json`.

## Claims

Best-of-4 Metal sampling executed under the grant. It did not produce
diverse candidates and did not pass public tests or the sentence
verifier. This is not learning-to-learn, not confirmation, and not a
reason to retune the closed stepwise beam. Ranking stays paused.
