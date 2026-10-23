# Acquired experience transfer — development results

Branch `cursor/seed-acquired-experience`.
Protocol `aab3477`. This results commit is separate.
Base `1a1b932`, routes protocol `7fd62fe`. Artifact hash
`f6dc938d2328ecbda9d2d2f350414a40ee86b81332b0a7ea5907538519a46101`.
Verifier `valid: true` on 36/36 cells. Routes, follow-up and the
90-cell map were not rescored. Not confirmation. Not
learning-to-learn. Not AGI. Ranking stayed paused.

Frozen weights `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`
`sha256:cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
The runtime helper does not hash files ≥1 byte; this hash was taken
from the same file on disk after the run. Weights were not written.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_acquired_experience.py tests/test_seed_capability_routes.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_acquired_experience.py artifacts/seed_acquired_experience
PYTHONPATH=src:.deps python3 scripts/verify_seed_acquired_experience.py artifacts/seed_acquired_experience/seed_acquired_experience.json
```

## Interface fixes (applied to every method)

Extra API-ID bindings are rejected before assembly. The live routes
miss (`field.nums` + `elem.nums` + `field.lo`) now yields empty
source and `executable=false`. Named parameter-to-ID bindings are
preferred. Selection, binding validity, binding correctness and
assembly are scored separately. Selection is not generally solved.

Caller staging now sees the actual helper source and import path.
Publish requires a hash-bound receipt. Constants are not globally
banned; a caller that does not make the required call still cannot
publish.

## What was acquired

Two public source episodes. Only the comparison success entered the
NEXUS store. The null-default success was held for the irrelevant
control. No handwritten answers, task-ID features or private tests
entered memory.

Readable example, `src_allow_limit`:

```
# public request
Allow score equal to the limit in accept(item).

# initial
def accept(item):
    return item['score'] < item['limit']

# programmer-supplied tool: apply_make_inclusive
def accept(item):
    return item['score'] <= item['limit']

# captured schema b7352788704ca745
family=comparison_boundary
transformation=compare_op_swap
from_op=Lt to_op=LtE
supporting public test: score=5, limit=5 → True
```

Abstraction is `infer_ast_transform` plus `apply_make_inclusive`.
Those transforms are programmer-supplied. Acquisition cost: 0 model
calls, 0.000772 s, 1 tool.

## Source versus target

| Target | Change | Repair family |
| --- | --- | --- |
| `tgt_rename_layout` | identifiers `width`/`max`, file `gate.py` | same Lt→LtE |
| `tgt_gt_floor` | operator `>` held out | rebound Gt→GtE |
| `tgt_strict_cut` | exclusive; starter already correct | must refuse |
| `tgt_join_parts` | missing function | must abstain |
| `tgt_near_bound` | ambiguous “near the bound” | must ask |
| `tgt_exact_limit` | exact request+files repeat | cache, not transfer |

C and D were not collapsed. C applies only `Lt→LtE`. D’s inclusive
path uses `apply_make_inclusive` and can rebound `Gt→GtE`.

## Later-task private correctness (5 cells; exact repeat excluded)

| Method | private | harmful | applicability | model calls |
| --- | ---: | ---: | ---: | ---: |
| A scratch | 3 | 0 | 0 | 5 |
| B exact cache | 1 | 0 | 2 | 0 |
| C ordinary template | 2 | 0 | 4 | 0 |
| D acquired | 3 | 0 | 5 | 0 |
| E reset | 3 | 0 | 0 | 5 |
| F irrelevant | 1 | 0 | 2 | 0 |

Per later task, private pass:

| Task | A | B | C | D | E | F |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rename/layout | 0 | 0 | 1 | 1 | 0 | 0 |
| Gt floor rebound | 1 | 0 | 0 | 1 | 1 | 0 |
| exclusive cut | 1 | 1 | 1 | 1 | 1 | 1 |
| unrelated join | 0 | 0 | 0 | 0 | 0 | 0 |
| ambiguous near | 1 | 0 | 0 | 0 | 1 | 0 |

D applied the captured inclusive repair on rename and on the held-out
`>` floor, refused the exclusive cut, abstained on join, and asked on
the ambiguous bound. C could not apply `Gt→GtE`. Scratch independently
passed Gt floor, exclusive cut and the ambiguous item (it guessed
inclusive). Reset matched scratch. Irrelevant memory matched exact
cache: no comparison schema, starter-only.

Harmful transfer: 0. Exclusive refuse held.

## Exact repeat (reported separately)

`tgt_exact_limit`: B/C/D private pass by cache or template. A/E/F
fail. This is exact-repeat caching, not later-task transfer.

## Source retention

After acquisition, `src_allow_limit` retrieved and applied; private
passed. The comparison skill was not overwritten.

## Cost

12 model calls (A+E only), 43.089 s wall, frozen debit **0**.
Product chat unused. Metal unused. Process cleaned up.
Acquisition 0 model calls. Retrieval charged as events, not GPU.
RSS 37.188 MiB reports the parent only (`server_pid` null); that is
a measurement limit, not a claim that llama-server used no memory.

Observed break-even on this grid: acquisition cost was ~0 model
calls, and D matched A’s 3/5 later accuracy without those 5 later
calls. That is an observed cost note, not a projected reuse rate.
D’s extra later pass versus C is `tgt_gt_floor` only.

## Verdict

**Inconclusive** for a unique NEXUS acquired-memory advantage.
D beats the ordinary Lt template on the held-out `>` rebound and
ties scratch/reset on later private correctness. Reset and
irrelevant-memory controls remove D’s comparison benefit. No
unacceptable harmful transfer. This is useful scoped template
reuse plus a documented rebound, not learning-to-learn.

## Next

1. Keep ranking paused. Do not treat persistence as a new learning
   procedure.
2. If a unique NEXUS claim is still wanted, freeze a composition
   where a stored multi-step procedure is required and the ordinary
   rebound template is not enough. New IDs only.
3. Re-test live API-ID selection on a new locked grid now that extra
   bindings cannot assemble. Do not rescore the opened routes cells.

Do not tune this grid and rescore it.
