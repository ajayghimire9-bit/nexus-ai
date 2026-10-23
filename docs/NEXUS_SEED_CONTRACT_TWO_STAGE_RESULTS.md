# Explicit input contract, two-stage revision, wired e2e — results

Branch `cursor/seed-contract-two-stage`. Protocol `403fc15` committed
before scoring. This results commit is separate. Base reviewed `7f9fbac`.
Not confirmation. Not learning-to-learn. Not AGI.

Verifier `valid: true` on 1 inspect / 8 contract / 6 e2e cells, 57 events
(24 complete / 19 worker / 14 assessment). Wall **110.344686 s**. Ledger
after this run: **2806.847834455996 used / 793.152165544004 remaining**.

`fixed_boundary` stays the default. Ranking and memory were not resumed.
`local_model_runtime.py` was not edited. ChatML and `json_body` were kept.

## 1. Input contract versus the existing prompt

The contract block adds `Signature: def title(item)`,
`item: {"text": str}`, and the public example. The rest of the user text
matches the existing prompt.

Best 0.5B variant: **`contract`**.

| Task | Variant | 0.5B | 1.5B |
|---|---|---|---|
| `title` spaces | existing | truncated; format repair failed; no dict fields | `item.lower()`; public fail |
| `title` spaces | contract | first `item.lower()`, then truncated | `item['text'].lower().replace(' ', '_')`; private pass |
| `mass` inclusive | existing | format then copied `<` after three-point | `<=` on the first call; private pass |
| `mass` inclusive | contract | copied `<` after three-point | `<=` on the first call; private pass |

The contract is what let the 1.5B coder read `item['text']`. The 0.5B
model still treated the dict as a string or copied `<`.

## 2. Format repair did not consume the behavioral slot

Cap: 3 charged `complete` calls (initial + format + behavior).

Existing `mass` on 0.5B used all three: malformed `{`, format repair to a
valid `<`, then a behavioral call with below/equal/above. Existing
`title` never became executable, so behavior was correctly skipped.
Contract `title` on 0.5B executed and received a behavioral call after a
valid first body. Every call was metered.

## 3. Public-case feedback

Failed cases listed input, expected, and actual or exception. Comparison
cells that reached behavior included below/equal/above and did not name
`<=`. The 0.5B model still copied `<` / `return item['n'] < item['cap']`
after that evidence. First-try 1.5B successes did not need the revision.

## 4. Wired end-to-end (contract prompt)

Discovery selected every gold target (6/6), including `beta.hold` beside
`alpha.keep`. Implementation used that plan.

| Task | Kind | 0.5B | 1.5B |
|---|---|---|---|
| `hold` inclusive | replace | copied `<` after three-point | `item['cap'] >= item['n']`; private pass |
| `span` nonempty count | insert | iterated the dict as keys | `sum(1 for v in [item['a'], item['b'], item['c']] if v)` |
| `clip` floor | insert | `return None`, then `max(value, floor)` | `max(item['value'], item['floor'])` |

Target selection, executable code, revision success and private
correctness were scored separately. 1.5B: 3/3 private pass, all first
call. 0.5B: 3/3 executable after the reserved stages, 0/3 private pass.

## Resources

Combined RSS is almost all `llama-server`: ~826–869 MiB (0.5B) and
~1990–2127 MiB (1.5B). Parent RSS ~24–38 MiB. Weight-file size is not
that memory. 0.5B cells 2.4–5.4 s; 1.5B cells 8.1–18.8 s.

## Next

Keep the explicit contract, ChatML, two-stage revision and wired
discovery on the 1.5B coder. The 0.5B model still does not use
below/equal/above evidence. Do not resume ranking or memory. Do not
merge `main`.
