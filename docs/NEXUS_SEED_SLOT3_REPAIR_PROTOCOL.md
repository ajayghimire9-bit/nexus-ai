# Unused third completion after a degenerate revision — protocol

Base: reviewed tip `c94addb` of `cursor/seed-worker-div-confirm`.
Development evaluation only. Do not rescore closed artifacts
`31713e4d…`, `490ab00`, `50d65e1b…`, or `c94addb`. Do not edit
`src/nexus/seed/local_model_runtime.py`. Ranking, memory, and
acquired-experience comparison stay paused. Standing grant: 900 s this
experiment, carried session
**3314.967351455996 used / 285.032648544004 remaining**, local CPU.
Hard deadline **150 s** (below remaining). If 150 s exceeds the verified
remaining balance, do not score: `BLOCKED_BUDGET`. At most 3 completions
per task.

## Changes before scoring

1. After a public-behavior revision (Completion 2), if
   `completions_used < 3` and the revision is structurally degenerate,
   spend the unused third completion. Trigger only on: placeholder
   (`...` / empty / `Ellipsis` after unwrap), `compile_check` failure
   (including unbound names not in parameters or allowed builtins), or
   a constant/literal that does not reference `item`. No task solution
   is planted in the prompt.
2. Completion 3 keeps Completion 1's expression and behavioral
   feedback (TypeError, AttributeError, observational schema) and adds
   a structural rejection reason for Completion 2. Format hints must
   not write `{"body": "..."}`.
3. Ranking, memory, and acquired-experience comparison remain paused.

## Expected grid

1 inspect, 1 historical audit (no inference), 4 supplied cells on
fresh IDs `py_lot_count`, `py_job_slash`, `py_part_div`,
`py_ok_pair` with distinct fields and values. Frozen 1.5B recipe plus
`structural_slot3=True`. Request timeout 20 s. External 150 s deadline
over the owned server.

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Do not assume 4/4. Do not merge `main`. Offline unit tests first
(0 model calls). One `--live-model` execution after this protocol is
committed.
