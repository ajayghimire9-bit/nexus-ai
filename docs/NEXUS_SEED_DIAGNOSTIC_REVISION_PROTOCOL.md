# Diagnostic-only revision, two completions — protocol

Base: reviewed tip `3b88ed3` of `cursor/seed-worker-div-confirm`.
Development evaluation only. Do not rescore closed artifacts
`31713e4d…`, `490ab00`, `50d65e1b…`, `c94addb`, `307bd89`, or
`3b88ed3`. Do not edit `src/nexus/seed/local_model_runtime.py`.
Ranking, memory, and acquired-experience comparison stay paused.
Standing grant: 900 s this experiment, carried session
**3451.157780455996 used / 148.842219544004 remaining**, local CPU.
Hard deadline **90 s** (below remaining). Target wall **< 55 s**.
At most **2** completions per task so the fourth cell is not starved.

## Changes before scoring

1. After a public failure, the revision prompt contains the signature,
   the request, and structured diagnostics (exception, failed public
   cases, list-of-dict schema, KeyError-on-missing-key). It does not
   paste the failed C1 source. No `.get` or finished expression is
   planted.
2. Per-task cap is 2 (initial + one diagnostic revision; a placeholder
   C1 uses the second slot for format repair). Unprojected-sum reject
   and slot-3 structural completions are not charged when the cap is
   already reached.
3. Tag/join private tests keep a disjoint missing-key case.

## Expected grid

1 inspect, 1 historical audit (no inference), 4 supplied cells on
fresh IDs `py_box_tally`, `py_lane_slash`, `py_quota_div`,
`py_meet_pair`. Frozen 1.5B recipe plus `diagnostic_revision=True`
and `max_completions=2`. Request timeout 20 s. External 90 s deadline
over the owned server.

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Do not assume 4/4. Do not merge `main`. Offline unit tests first
(0 model calls). One `--live-model` execution after this protocol is
committed.
