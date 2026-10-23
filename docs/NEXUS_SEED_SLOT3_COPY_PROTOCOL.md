# Slot-3 after a duplicated KeyError subscript — protocol

Base: reviewed tip `307bd89` of `cursor/seed-worker-div-confirm`.
Development evaluation only. Do not rescore closed artifacts
`31713e4d…`, `490ab00`, `50d65e1b…`, `c94addb`, or `307bd89`. Do not
edit `src/nexus/seed/local_model_runtime.py`. Ranking, memory, and
acquired-experience comparison stay paused. Standing grant: 900 s this
experiment, carried session
**3379.081862455996 used / 220.918137544004 remaining**, local CPU.
Hard deadline **70 s** so a completed run leaves **> 150 s** of the
session grant. Target wall **< 65 s**. If 70 s exceeds the verified
remaining balance, do not score: `BLOCKED_BUDGET`. At most 3
completions per task.

## Changes before scoring

1. After a public-behavior revision, if `completions_used < 3`, also
   spend the third completion when C2 is an exact normalized AST copy
   of a failed C1 (`duplicate_ast`) or still uses a bare `item[key]`
   subscript for a key that raised `KeyError`
   (`unchanged_subscript_on_keyerror`). Reasons name the defect only.
   No `.get` or finished expression is planted.
2. Tag/join private tests include a distinct missing-key case,
   disjoint from public inputs, so an unguarded `item['k']` cannot
   pass private while failing public.
3. Ranking, memory, and acquired-experience comparison remain paused.

## Expected grid

1 inspect, 1 historical audit (no inference), 4 supplied cells on
fresh IDs `py_crate_tally`, `py_post_slash`, `py_ratio_div`,
`py_clear_pair` with distinct fields and values. Frozen 1.5B recipe
plus `structural_slot3_copy=True`. Request timeout 20 s. External
70 s deadline over the owned server.

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Do not assume 4/4. Do not merge `main`. Offline unit tests first
(0 model calls). One `--live-model` execution after this protocol is
committed.
