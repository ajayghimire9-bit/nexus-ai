# Equal inclusive baseline and fresh API-ID — development results

Branch `cursor/seed-equal-inclusive`.
Protocol `3481406`. This results commit is separate.
Base `90eef6b`. Artifact hash
`0aaaeaae391af92468f7adc1765684fad3eb4b99560b47b2ab0493ff81a30f7f`.
Verifier `valid: true` on 36 experience cells and 4 API cells.
Opened acquired-experience and routes grids were not rescored. Not
confirmation. Not learning-to-learn. Not AGI. Ranking stayed paused.

Frozen weights `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`
`sha256:cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.
Weights were not written.

## Commands

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_equal_inclusive.py tests/test_seed_acquired_experience.py tests/test_seed_capability_routes.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_equal_inclusive.py artifacts/seed_equal_inclusive
PYTHONPATH=src:.deps python3 scripts/verify_seed_equal_inclusive.py artifacts/seed_equal_inclusive/seed_equal_inclusive.json
```

## What was acquired

`src_eq_span` public success → `compare_op_swap` Lt→LtE. Source
retention apply + private pass. `src_eq_null` stayed in the
irrelevant control. No private tests or task-ID features entered
memory.

The ordinary baseline is now `apply_make_inclusive` under the same
public gates, including `>` rebound. C and D invoke the same tool on
inclusive repairs.

## Later-task complete assistant behavior (5 cells; exact repeat excluded)

| Method | solutions | clarify/refuse | harmful | calls | fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: |
| A scratch | 2 | 0 | 0 | 5 | 0 |
| B exact cache | 2 | 0 | 0 | 5 | 5 |
| C inclusive tool | 3 | 2 | 0 | 1 | 1 |
| D acquired | 3 | 2 | 0 | 1 | 1 |
| E reset | 2 | 0 | 0 | 5 | 0 |
| F irrelevant | 2 | 0 | 0 | 5 | 5 |

C and D matched on every later cell: apply rename, apply `>` floor,
refuse exclusive, fallback on the unrelated join (both failed), ask
on the ambiguous edge. Scratch/reset solved `>` and left the exclusive
starter working; they did not ask or refuse and they missed the rename.
Cache and irrelevant memory fell back on misses and therefore paid the
same five later calls as scratch.

Exact repeat `tgt_eq_repeat`: B/C/D pass without a model call. A/E/F
fail. Reported separately from transfer.

Harmful changes: 0.

## Verdict

**Tool-tie.** Acquired experience did not contribute anything beyond
invoking the equally capable inclusive-repair tool. Reset and
irrelevant memory match scratch. This is not a NEXUS learning
advantage and not learning-to-learn. Broader learning research stays
paused.

## Fresh API-ID

| Score | direct | id_select_assemble |
| --- | ---: | ---: |
| selection | n/a | 2/2 |
| binding validity | n/a | 0/2 |
| bindings correct | n/a | 0/2 |
| assembled | 0 | 0 |
| private execution | 0/2 | 0/2 |

`api_eq_ceil`: chose `clip.cap_high` with only `field.vals` →
`missing_required`, empty source, not executable.
`api_eq_glue`: chose `tape.glue_bits` with extra `elem.bits` →
`extra_bindings`, empty source, not executable.

The prior routes miss (extra `elem.*` still assembled) does not
repeat. Invalid bindings never became calls. Selection on two items
is still not a general solve. Binding remains the gap.

## Cost

29 model calls, 103.799 s, frozen debit **0**. Product chat unused.
Metal unused. Process cleaned up. RSS reports the parent only
(`server_pid` null); measurement limit, not a memory claim.

C/D later cost is one fallback call each (unrelated join). Zero calls
on refuse/ask are correct assistant acts, not silent stops.

## Next

1. Keep broader learning and ranking paused. A reusable procedure must
   beat this inclusive-repair tool before a NEXUS-memory claim.
2. On a new API-ID grid, prefer a named parameter-to-ID schema so a
   missing `hi`/`mark` and an extra `elem.*` are harder to emit. Do
   not rescore these two cells.
3. Keep scoring selection, binding validity, assembly and execution
   separately. Do not treat selection-only hits as an API solve.

Do not tune this grid and rescore it.
