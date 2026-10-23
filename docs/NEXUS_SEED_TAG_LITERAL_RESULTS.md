# Item-anchored KeyError revision without test-literal echo — development results

Branch `cursor/seed-worker-div-confirm`. Baseline `30127b2`. Protocol
`666071b` committed before scoring. This results commit is separate.
Not confirmation of learning-to-learn. Not AGI. Not a 4/4 claim.

Verifier `valid: true` on 1 inspect / 1 audit / 4 supplied cells, 14
events (5 complete / 5 worker / 4 assessment). Replay of saved final
files matched reported public and private flags. Scored wall
**57.987323 s** (confirm block **56.102399 s**). Hard deadline 75 s
was not hit. Combined RSS ~2032–2126 MiB on all four cells. Offline
tests were **0.77 s** wall with 0 model calls; they are engineering
checks and are not added to the scientific ledger. Ledger after this
live debit:
**3564.568345455996 used / 35.431654544004 remaining** of 3600 s.

Artifact
`artifacts/seed_tag_literal_confirm/seed_tag_literal_confirm.json`
sha256 `f1586805c758aa02c0dc27a820c3fb9ec81edf72bb7f60363153fcd70825cbbc`.
Model `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
`local_model_runtime.py` was not edited. Closed historical artifacts
were not rescored.

## Offline

Focused `not live_model` tests passed: C2 includes the prose key
summary `['lane', 'bay']`, omits C1 source and `.get`, and ends on
the `item` instruction. `return '/lab/'` and `/lab/` are flagged
`constant_literal_no_item` before the worker. The verifier
reconstructs the 2-completion chain and rejects a tampered private
flag.

## Live cells (one run)

| Task | C1 | C2 | Public | Private | RSS |
|---|---|---|---|---|---|
| `py_sack_tally` | loop + `sack.get('size', 0)` | none | **3/3** | **3/3** | 2126.0 |
| `py_path_slash` | f-string `item['path']`/`item['zone']` KeyError | `{item['zone'].lower()}/{item['path'].lower()}` (uses `item`; set/set TypeError) | 0/3 | 0/3 | 2031.7 |
| `py_load_div` | `item['load'] / item['span']` | none | **2/2** | **2/2** | 2042.4 |
| `py_hold_pair` | `days >= wait and rank >= step` | none | **2/2** | **2/2** | 2054.6 |

Public **3/4**, private **3/4**. Completions charged **5** (1+2+1+1),
all ≤ 2. The C2 prompt named `['path', 'zone']`, included KeyError,
ended on the `item` instruction, and contained neither C1 source nor
`.get` nor `/lab/`. The coder no longer echoed a test string; it
wrote a parameterized but invalid set-division expression and still
used bare subscripts. No `.get` was planted.

## Next

Test-literal echo is stopped. The leftover coding failure is
missing-field handling on the tag family after a KeyError summary.
Do not resume ranking, memory, or experience comparison. Do not
merge `main`.
