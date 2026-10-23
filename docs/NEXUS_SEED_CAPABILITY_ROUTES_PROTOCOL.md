# Capability routes — locked development protocol

Branch `cursor/seed-capability-routes`.
Base `db20cb1` (follow-up results). Product parent `e3d21b6`.
Do not rescore the 90-cell map or the previous follow-up. Do not merge
`main`. Do not edit `local_model_runtime.py`. Do not debit the frozen
CPU ledger **3564.568 s / 0 s debit**. Ranking stays paused. Acquired
solution memory stays empty.

API selection has succeeded on some examples. It is **not** solved
generally. Selection, bindings and assembled execution are scored
separately.

## 1. Provenance on fresh documents

Keep the existing resolver. New corpus, not harbor/weather/Mora.

- Missing version, effective date and supersession →
  `unresolved_conflict`.
- Two authoritative sources, same subject, no replacement →
  `unresolved_conflict`.
- Two later sheets that both supersede the same old row →
  `unresolved_conflict`.
- A clear later version that names `supersedes` still replaces.

Timestamp sort remains the naive control. Offline.

## 2. Selective mathematics

Straightforward units and percentages keep the calculator route.
An unknown variable is required only for algebra. Interpretation,
execution and answer are reported separately. A correct number with
a broken statement is not a full pass.

Fresh tasks, not the follow-up `math_int_*` set.

## 3. Typed API-ID assembly

Offline first (this commit): a valid ID proposal assembles, wraps
and executes; a swapped scalar/list binding is `type_mismatch`.
Then live: the model chooses `api_id` and field IDs; deterministic
code writes the import, access and call. Direct generation is the
equal-docs baseline.

IDs narrow the output space. That is not schema learning.

## 4. Coordinated multi-file staging

Each function has a destination, signature and output contract.
The helper is written first, then the caller, against the staged
files. Publish only if helper behavior, caller behavior and the
required call all pass. Extract eligibility is not this route.

## Budgets

Standing grant: **900 s**, 80 live calls, local CPU
(`-ngl 0 --device none`), temperature 0, seed 42. Planned live
cells: 16. Save a partial grid if the cap is hit.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_capability_routes.py tests/test_seed_capability_followup.py -q
PYTHONPATH=src:.deps python3 scripts/run_seed_capability_routes.py artifacts/seed_capability_routes
PYTHONPATH=src:.deps python3 scripts/verify_seed_capability_routes.py artifacts/seed_capability_routes/seed_capability_routes.json
```
