# Diagnostic-only revision, two completions — development results

Branch `cursor/seed-worker-div-confirm`. Baseline `3b88ed3`. Protocol
`a36c3d2` committed before scoring. This results commit is separate.
Not confirmation of learning-to-learn. Not AGI. Not a 4/4 claim.

Verifier `valid: true` on 1 inspect / 1 audit / 4 supplied cells, 13
events (5 complete / 4 worker / 4 assessment). Replay of saved final
files matched reported public and private flags. Scored wall
**55.423242 s** (confirm block **53.495174 s**). Hard deadline 90 s
was not hit. All four cells kept combined RSS ~2077–2086 MiB; the
owned server did not die. Offline tests were **1.19 s** wall with 0
model calls; they are engineering checks and are not added to the
scientific ledger. Ledger after this live debit:
**3506.581022455996 used / 93.418977544004 remaining** of 3600 s.

Artifact
`artifacts/seed_diagnostic_revision_confirm/seed_diagnostic_revision_confirm.json`
sha256 `4bd7d5ece9f1c4e0eb09423c14be61a099fd4a2121a105a9a40bcab1d143f468`.
Model `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
`local_model_runtime.py` was not edited. Closed historical artifacts
were not rescored.

## Offline

Focused `not live_model` tests passed: C2 prompts contain TypeError /
KeyError, failed public cases, and schema notes, and do not contain
the C1 source or `Failed body:`. The verifier reconstructs a
2-completion chain and public/private parity. An unguarded
`item['lane']` still fails the fresh private missing-key cases.

## Live cells (one run)

| Task | C1 | C2 | Public | Private |
|---|---|---|---|---|
| `py_box_tally` | `sum((box.get('num', 0) for box in item.get('boxes', [])))` | none | **3/3** | **3/3** |
| `py_lane_slash` | f-string `item['lane']`/`item['bay']` → KeyError | `/lab/` (empty/placeholder; C1 source absent from prompt) | 1/3 | 0/3 |
| `py_quota_div` | `item['used'] / item['cap']` | none | **2/2** | **2/2** |
| `py_meet_pair` | `hours >= need and mark >= line` | none | **2/2** | **2/2** |

Public **3/4**, private **3/4**. Completions charged **5** (1+2+1+1),
all ≤ 2. Task 4 ran to completion. The C2 prompt for `lane` included
`KeyError` and omitted the C1 f-string; the coder did not echo that
f-string and wrote a non-executable `/lab/` instead. No `.get` was
planted. Bag-sum passed on the first completion of this fresh id.

## Next

Diagnostic-only revision stopped verbatim echo and kept the fourth
cell alive. The leftover coding failure is missing-field handling on
the tag family after KeyError feedback. Do not resume ranking,
memory, or experience comparison. Do not merge `main`.
