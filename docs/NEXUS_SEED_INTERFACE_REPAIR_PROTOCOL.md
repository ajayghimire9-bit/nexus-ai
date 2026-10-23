# Envelope, sum-API, schema, and f-string repair — protocol

Base: reviewed tip `6259d55` of `cursor/seed-worker-div-confirm`.
Development evaluation only. Do not rescore closed artifacts
`31713e4d…`, `490ab00`, or `50d65e1b…`. Do not edit
`src/nexus/seed/local_model_runtime.py`. Ranking, memory, and
acquired-experience comparison stay paused. Standing grant: 900 s this
experiment, carried session
**3255.314914455996 used / 344.685085544004 remaining**, local CPU.
Hard deadline **150 s** (below remaining, with reserve for cleanup and
verification). If 150 s exceeds the verified remaining balance, do not
score: `BLOCKED_BUDGET`.

## Changes before scoring

1. Unwrap an accidentally nested code envelope only when it is a single
   recognized string key (`body` / `expr` / `expression` / `code`).
   JSON or `ast.literal_eval` only. Bound depth and size. Reject `...`
   after unwrap. Preserve `return {"k": v}`. Log raw, extracted,
   normalized, and unwrap operations. Do not invent a solution.
2. Feedback layers: API diagnostic for `sum(..., default=)` vs
   `sum(iterable, start=0)`; conservative public list-of-dict schema;
   missing/empty requirements only from the public specification.
   Failed public cases only. No private tests. No finished projection
   expression.
3. Shared AST policy includes `JoinedStr` / `FormattedValue`. Compile
   and execute use the same allowlist. No f-string rewriting.
4. Format and behavior revisions remain explicit completions inside
   `MAX_COMPLETIONS=3`. Deterministic unwrap is logged, not charged.

## Expected grid

1 inspect, 1 historical audit (no inference), 4 supplied cells on
fresh IDs `py_bin_tally`, `py_role_dash`, `py_split_num`,
`py_years_bar` with distinct fields and values. Frozen 1.5B recipe.
Request timeout 20 s. External 150 s deadline over the owned server.

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Do not assume 4/4. Do not merge `main`. One `--live-model` execution.
