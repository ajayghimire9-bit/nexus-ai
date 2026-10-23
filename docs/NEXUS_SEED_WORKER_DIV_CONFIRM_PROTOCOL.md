# Worker division, public missing-field cases, then confirmation — protocol

Base: reviewed tip `e5d41fd` of `cursor/seed-harder-features-acquisition`.
Branch `cursor/seed-worker-div-confirm`. Development only. Do not rescore
the closed harder-feature grid. The historical 1/5 supplied private
result stays in
`artifacts/seed_harder_features/seed_harder_features.json`
(sha256 `31713e4d04ef63ca296ef4c78797ca11e4c87203ddce845ea82c3956646dbdc2`).
Do not edit `src/nexus/seed/local_model_runtime.py`. Standing grant:
900 s this experiment, carried session
**3005.155682455996 used / 594.844317544004 remaining**, local CPU.

## Changes before scoring

1. Allow true division (`ast.Div`) in `agent_loop_worker`. Define numeric
   comparison (`compare_python_result`), bool-is-not-int, float tolerance
   1e-6, and division-by-zero as a runtime `ZeroDivisionError`. Replay the
   saved `due` patch with no new inference.
2. When a specification requires missing fields or empty lists, put
   representative cases in **public** tests. Private tests keep fresh
   combinations and values. Compilation rejections are included in
   behavioral feedback.
3. Audit the saved `total`, `tag` and `fit` supplied traces: whether
   feedback contained the exception or mismatch, and whether the body
   changed. No new inference for that audit.
4. After the worker and prompt are frozen in this protocol commit, run
   four new confirmation tasks on the frozen 1.5B recipe: aggregation,
   missing fields, arithmetic, combined conditions.

## Expected grid

1 inspect, 4 confirmation cells (1.5B, supplied contract), plus the
offline due replay and revision audit.

## Gates

`fixed_boundary` remains the default. No ranking or memory promotion.
Historical 1/5 is not rewritten. Do not merge `main`.
