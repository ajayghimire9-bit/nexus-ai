# Six-area capability comparison — locked development protocol

Base: reviewed tip `a47c070` of `cursor/seed-scoped-id-staging`.
Branch `cursor/seed-six-area-comparison`. Authored source-development work,
never confirmation. Closed scoped-id, widening and capability-audit artifacts
stay unread as new scores. Do not edit `src/nexus/seed/local_model_runtime.py`.

Executable source of truth: `configs/seed_six_area_comparison.json`.
Verifier: `scripts/verify_seed_six_area_comparison.py`.
Runner: `scripts/run_seed_six_area_comparison.py`.

The intended loop is request → language interpretation → memory retrieval →
planning or code proposal → sandbox execution → tests → result and
explanation. Afterward the system may retain a procedure or repair pattern.
Across tasks the investigation policy may also change. Those are two separate
improvements and are scored separately.

`identified` counts only `identified_within_catalogue`. Repair schemas are
acquired only from genuine public-passing solves. Handwritten `patched` fields
are forbidden. Closed coding IDs from the scoped-id and widening pilots are
excluded.

## Areas

1. Unfamiliar coding — bug fix, new function, multi-file change, documented
   API. Progress: independent private tests pass without supplied solution
   patches.
2. Language — paraphrase, imperfect spelling, ambiguous request, multi-turn
   correction, factual question, unsupported request. Progress: real-state
   interpretation, useful refusal or clarification. Not a keyword score.
3. Reasoning — multi-step calculation and a half-open constraint, both
   execution-backed in the existing worker. Progress: correct answers with
   passing sandbox checks.
4. Knowledge reuse — solve `py_clip_hi_src`, then a different instance
   `py_age_cap`. Progress: better private pass or lower path cost than
   ordinary exact caching and than doing nothing.
5. Learning-to-learn — train investigation choices on source tasks; test new
   compositions and an out-of-grammar family. Methods: `fixed_boundary`,
   `learned` (policy + capsules), `capsules_reset` (clear task memories, keep
   policy), `shuffled` (destroy policy structure). Progress: learned is more
   efficient than the fixed policy at comparable accuracy, the advantage
   remains after capsule reset, and it disappears when shuffled. If the
   advantage disappears on reset, that is memory reuse, not an improved
   learning strategy.
6. Retention — revisit the source clip task after later acquisition.
   Progress: the useful repair still applies without claiming unbounded
   memory growth.

## Conditions

Same installed Qwen 0.5B, tools, public task information and budgets:

1. `model_tools` — local model + repository tools; acquired memory off.
2. `model_tools_cache` — the same plus an ordinary exact request/file cache.
3. `nexus_repair_memory` — AST + model + parameterized repair-schema memory.
4. `learned` investigation — retained policy with optional source capsules.
5. `capsules_reset` and `shuffled` — controls for what caused any gain.

Unseen levels: L1 new inputs; L2 new compositions and repositories; L3
out-of-grammar square plus coding IDs excluded from prior closed grids.

## Expected grid

12 investigation episodes (1 seed × (2 assessment + 1 oog) × 4 methods),
12 coding cells (4 specs × 3 conditions), 3 reuse cells, 3 retention cells,
2 reasoning cells, 6 language cells.

The verifier requires that grid, replays `final_files`, reconstructs
completion counts and costs from raw traces, and rejects a learning-to-learn
claim that lacks the reset/shuffle controls.

## Gates

No automatic promotion. Learning-to-learn remains unestablished unless the
predeclared control triple holds. Do not merge `main`.
