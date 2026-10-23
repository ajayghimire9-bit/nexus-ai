# Envelope, sum-API, schema, and f-string repair — development results

Branch `cursor/seed-worker-div-confirm`. Baseline `6259d55`. Protocol
`8f2a8c1` committed before scoring. This results commit is separate.
Not confirmation of learning-to-learn. Not AGI. Not a 4/4 claim.

Verifier `valid: true` on 1 inspect / 1 audit / 4 supplied cells, 15
events (6 complete / 5 worker / 4 assessment). Replay of saved final
files matched reported public and private flags. Scored wall
**59.652437 s** (confirm block **57.75468 s**). Hard deadline 150 s
was not hit. Offline tests were **0.835 s** wall with 0 model calls;
they are engineering checks and are not added to the scientific
ledger. Ledger after this live debit:
**3314.967351455996 used / 285.032648544004 remaining**.

Artifact
`artifacts/seed_interface_repair_confirm/seed_interface_repair_confirm.json`
sha256 `b6c72e4ff32561bf8653b40f7038955869e106f22302d897bfb201e08d45fcbc`.
Model `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
`local_model_runtime.py` was not edited. Closed 1/5, 3/4, and prior
2/4 artifacts were not rescored.

## Offline

31 focused tests passed, including nested-envelope unwrap, `...`
reject, preserved `return {'total': 0}`, `sum(..., default=)`
signature, valid `sum(..., start=0)`, list-schema for empty /
nonempty / heterogeneous public inputs, f-string compile=execute,
deadline cleanup, and replay mismatch on a tampered private-success
flag. Historical `JoinedStr` reject remains on the saved harder
`tag` trace; the current worker allowlist now includes `JoinedStr`
and `FormattedValue` on every compile/execute path.

## Live cells (one run)

| Task | Raw → extracted / unwrap | Revision feedback | Final code | Public | Private |
|---|---|---|---|---|---|
| `py_bin_tally` | `sum(item['bins'] or [0])` / no unwrap | API: int+dict; schema `bins` keys `qty`; missing/empty from spec | revision `{"body":"..."}` rejected as placeholder | fail | fail |
| `py_role_dash` | `'-'.join([...].lower())` / later unwrap `{'body':'-lead'}` → `-lead` | `AttributeError` list has no `lower`; missing-field requirement | `def label(item): -lead` | fail | fail |
| `py_split_num` | `item['num'] / item['den']` | none | same | **pass** | **pass** |
| `py_years_bar` | `years >= need and rating >= bar` | none | same | **pass** | **pass** |

2/4 private pass. Completions charged **6** (2+2+1+1), all ≤ 3.
Combined RSS ~2123–2130 MiB (`llama-server`). Request walls 5.7–12.4 s.
Bin revision prefill 6.76 s; no 20 s timeout.

Bin failure is model semantics after accurate feedback: it replaced
the unprojected `sum` with an ellipsis instead of reading `qty`.
Role failure is model semantics: `.lower()` on a list, then a nested
envelope hardcoding a public expected string. Unwrap logged
`unwrap_body` and did not invent a correct implementation. Division
and the compound predicate succeeded on the first completion.

## Next

The leftover mechanical gap is that a placeholder produced *after*
the behavior slot does not spend the unused third completion on a
format repair. Do not resume ranking, memory, or experience
comparison. Do not merge `main`.
