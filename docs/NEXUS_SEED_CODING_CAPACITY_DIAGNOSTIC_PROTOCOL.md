# Coding capacity diagnostic — protocol

Development only. Do not edit `local_model_runtime.py`. Do not debit
the frozen CPU ledger **3564.568 s**. Ranking stays paused.

This is **prepared**, not scored. A comparison claim requires both
GGUF files on disk and a later live commit after this protocol.

## Corrected interface (from the live-compare audit)

- ChatML (`<|im_start|>` system/user/assistant)
- Code uses `json_body` schema; sentences do not
- Feedback stays in a labeled note. Do not append verifier JSON that
  the model can echo as the answer
- Record `truncated`, `tokens_predicted`, and `hit_token_cap`
- Stop on `<|im_end|>`
- No planted `.get`

The closed compare artifact did **not** log stop flags. A malformed
`.get` draft and echoed JSON feedback are interface symptoms. They
do not prove a 128-token hit.

## Models

- **current:** 1.5B coder Q4_K_M
  `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`
- **stronger:** local coder GGUF at
  `.models/qwen2.5-coder-7b-instruct-q4_k_m.gguf` (or another owner-
  supplied stronger local file). Missing file →
  `BLOCKED_MISSING_STRONGER_MODEL`. That is not a 1.5B win.

## Families (same interface)

1. Field access
2. Missing values
3. Aggregation
4. Simple composition (`join_parts`)

Metrics: public/private task success, user-total latency, process RSS.
Not parameter count.

## Structured rendering vs free-form language

Checked facts and lexical bindings are assembled by
`render_structured_binding` (term, current value, `[doc_id]`). That is
**structured rendering**, not generation. Free-form explanations are
scored separately with `verify_composed_response`.

## Retrieval is not learning

The vault can retain documents and capsules. An acquired-knowledge
benefit is a later comparison of fresh tasks under **relevant**,
**none**, and **irrelevant** stored knowledge. Vault write/read alone
does not establish that.
