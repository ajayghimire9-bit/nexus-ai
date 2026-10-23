# Compact sum-row TypeError repair, then confirmation — protocol

Base: reviewed tip `490ab00` of `cursor/seed-worker-div-confirm`.
Development only. Do not rescore the closed harder-feature grid
(`31713e4d04ef63ca296ef4c78797ca11e4c87203ddce845ea82c3956646dbdc2`)
or the closed worker-division confirmation (`490ab00`). Do not edit
`src/nexus/seed/local_model_runtime.py`. Ranking, memory, and acquired-
experience comparison stay paused. Standing grant: 900 s this
experiment, carried session
**3128.309460455996 used / 471.690539544004 remaining**, local CPU.

## Changes before scoring

1. Confirm the worker AST allowlist compiles
   `sum((r.get('amount') or 0) for r in (item.get('rows') or []))`
   (`GeneratorExp` / `ListComp` / `comprehension`, plus worker `Lambda`
   / `map`). Offline unit test, 0 model calls.
2. When `sum(...)` raises `TypeError` involving `int` and `dict` on a
   list of row dicts, revision feedback names the element keys and
   requires numeric extraction (missing → 0) inside `sum(...)`.
   Revision prompts include only the failed expression and failed
   public cases.
3. If Attempt 1 failed that `TypeError` and the revision is the same
   normalized AST or still passes a bare container to `sum(...)`,
   reject before the worker re-run with
   `sum() requires per-row numeric extraction over dict elements`.

## Expected grid

1 inspect, 1 historical audit (no inference), 4 confirmation cells on
fresh IDs (`py_kit_sum`, `py_mark_empty`, `py_share_div`,
`py_pass_both`) covering nested bag sum, absent flag tag, rate
division, and compound threshold. Frozen 1.5B recipe. Request timeout
20 s. Target ledger debit < 25 s.

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Historical 1/5 and prior 3/4 are not rewritten. Do not merge `main`.
