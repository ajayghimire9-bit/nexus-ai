# Metal Best-of-4 smoke — protocol

Base: `7e70564` on `cursor/seed-lexicon-knowledge-vault`. Development
smoke only. Do not edit `src/nexus/seed/local_model_runtime.py`. Do not
debit the frozen CPU ledger **3564.568 s**. Do not retune the closed
stepwise residual beam. Ranking stays paused.

Commit this protocol and the tested runner **before** writing the
scored live artifact.

## Authorization

One bounded live batch under `ExplicitMetalGrant(authorized=True)` and
`MetalGrantEnforcer`:

- Hardware: macOS `arm64` Apple Silicon Metal (`mps` / llama-server
  `-ngl -1`). Record the host device string as reported.
- `max_rss_mib = 4096` (parent plus llama-server RSS, before and after
  every Best-of-4 batch).
- `max_wall_seconds_per_call = 30.0` per Best-of-4 batch.
- `max_session_metal_seconds = 600.0` in a separate
  `metal_ledger.json`. Mixing that file with the CPU 3564.568 s ledger
  is a verifier failure.
- CPU ledger debit is **0 s**. Target Metal wall for both cells is
  `< 15 s`; the hard cap remains 30 s/batch.

Without the explicit grant the host stays fail-closed
(`gpu_memory_enforcement_backend_unavailable_no_execution`).

## Locked recipe

- Model: 1.5B coder Q4_K_M
  `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`
- Format `json_body`, ChatML, `k = 4`
- Candidate 0: `temperature=0.0`, `seed`
- Candidates 1–3: `temperature=0.35`, seeds `[seed+1, seed+2, seed+3]`
- `n_gpu_layers = -1`
- No planted `.get` in either prompt

## Cells

1. **Code — missing-key tag family.** Fresh `mark(item)` over `yard` /
   `slip`. Public and private missing-key cases are disjoint. Score
   four live Metal candidates in the existing sandbox. Record all four
   raw expressions, the promoted public-test winner, and whether that
   winner passes private 3/3.
2. **Lexicon sentence.** Ingest one `KnowledgeVault` fact
   (`seed-metal-1`) and one `LexicalCapsule` (`metalvault`). Score four
   live Metal sentences with `verify_composed_response`. Export the
   winning triple through `write_sleep_jsonl` if one passes.

## Verifier

Replay the four saved candidates per cell against the CPU sandbox and
`verify_composed_response`. Check the CPU ledger constant, empty
`local_model_runtime.py` diff hash
`5b5b0aed48c9f1e0809f53b6cfc66a6d73ccc11b35798ad3ff6c99e8d48ce781`,
Metal ledger kind, and RSS cap. Tampered CPU-ledger or promotion
fields must fail.

Best-of-4 selection is not learning-to-learn. This smoke is not
confirmation and does not reopen closed CPU artifacts.
