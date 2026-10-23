# Item-anchored KeyError revision without test-literal echo — protocol

Base: reviewed tip `30127b2` of `cursor/seed-worker-div-confirm`.
Development evaluation only. Do not rescore closed artifacts
`31713e4d…`, `490ab00`, `50d65e1b…`, `c94addb`, `307bd89`,
`3b88ed3`, or `30127b2`. Do not edit
`src/nexus/seed/local_model_runtime.py`. Ranking, memory, and
acquired-experience comparison stay paused. Standing grant: 900 s this
experiment, carried session
**3506.581022455996 used / 93.418977544004 remaining**, local CPU.
Hard deadline **75 s** (below remaining). At most **2** completions
per task.

## Changes before scoring

1. The C2 prompt summarizes C1 as prose (accessed keys, lowercase,
   `'/'` separator, KeyError) and does not paste C1 source. String
   expected values are omitted from failed-case JSON. The last line
   requires an expression over `item` and forbids a constant string.
   No `.get` is planted.
2. A constant string body that does not name `item` is flagged
   `constant_literal_no_item` before the worker runs.
3. Tag/join private tests keep a disjoint missing-key case.

## Expected grid

1 inspect, 1 historical audit (no inference), 4 supplied cells on
fresh IDs `py_sack_tally`, `py_path_slash`, `py_load_div`,
`py_hold_pair`. Frozen 1.5B recipe plus `item_anchor=True` and
`constant_literal_guard=True`. Request timeout 20 s. External 75 s
deadline over the owned server.

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Do not assume 4/4. Do not merge `main`. Offline unit tests first
(0 model calls). One `--live-model` execution after this protocol is
committed.
