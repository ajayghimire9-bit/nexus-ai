# Capability routes — development results

Branch `cursor/seed-capability-routes`.
Protocol `7fd62fe`. This results commit is separate.
Base `db20cb1`, product parent `e3d21b6`. Artifact hash
`10f7e0de3580a068d46d55405f84dd985a0ce93db4c5d5539a4f499ef7039534`.
Verifier `valid: true` on 24/24 cells. The 90-cell map and the
previous follow-up were not rescored. Not confirmation. Not
learning-to-learn. Not AGI. API selection is not generally solved.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_capability_routes.py tests/test_seed_capability_followup.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_capability_routes.py artifacts/seed_capability_routes
PYTHONPATH=src:.deps python3 scripts/verify_seed_capability_routes.py artifacts/seed_capability_routes/seed_capability_routes.json
```

## 1. Provenance (fresh documents)

| Method | Missing metadata | Dual authority | Ambiguous supersession | Clear update |
| --- | --- | --- | --- | --- |
| timestamp_sort | 0 (picked 08:45) | 0 (picked west) | 0 (picked blue) | 0 (picked v1) |
| provenance | unresolved_conflict | unresolved_conflict | unresolved_conflict | 11 tonnes |

No version or date: two quay notes stay unresolved. Two official
gauges with the same version stay unresolved. Red and blue both
supersede the unmarked sheet; neither replaces the other. Crane v3
supersedes v1 even though v1 was ingested later.

## 2. Selective mathematics

| Method | passed / 4 | interpretation | execution | answer |
| --- | ---: | ---: | ---: | ---: |
| calculator_direct | 3 | n/a | 2 | 2 |
| routed | 3 | 0 | 2 | 2 |

Units and percent used the calculator on both methods (`4.5 * 1000`,
`90 * 0.1`). Algebra stayed failed: the calculator emitted
`5n + 2 = 27`; interpret returned a statement that did not parse.
Underspecified distance asked on both. A number and a statement are
different scores; calculator cells have no interpretation score.

## 3. Typed API-ID assembly

Offline (frozen): gold `span.floor_cut` + `[field.nums, field.lo]`
executes; `[field.lo, field.nums]` is `type_mismatch`.

Live, scored separately (2 tasks):

| Score | direct | id_select_assemble |
| --- | ---: | ---: |
| api_id selection | n/a | 2/2 |
| bindings | n/a | 0/2 |
| assembled | 0 | 2/2 |
| private execution | 0/2 | 0/2 |

The model chose `span.floor_cut` and `marks.stitch` and then added
an extra `elem.*` binding. The assembler treated that as an
element loop and emitted `floor_cut(nums, element, lo)`. Types
passed; the call is the wrong shape. Selection on these two items
is not a general solve.

## 4. Coordinated staging

| Method | passed / 2 |
| --- | ---: |
| direct | 0 |
| staged_pair | 0 |

On `coord_rt_over` the helper `over` was written correctly in
`util.py`. The caller was `return 'yes'` and did not call `over`.
The publish gate kept helper_behavior true, caller_behavior false,
required_call false, and **did not publish**. Baseline files stayed
in place. Direct never wrote the helper file.

## Cost

18 model calls, 64.934 s, RSS 2120.969 MiB. Frozen debit **0**.
Product chat unused. Metal unused. Process cleaned up.

## Next

1. Reject extra ID bindings that change arity before emitting `all(...)`.
2. Keep scoring bindings separately; `elem.*` extras are the live miss.
3. After a helper stages, assemble or constrain the caller so
   `return 'yes'` cannot publish.

Do not tune this grid and rescore it. Experience-transfer remains unrun.
