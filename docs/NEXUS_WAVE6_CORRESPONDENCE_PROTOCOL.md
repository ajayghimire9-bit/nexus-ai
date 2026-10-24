# Wave-6 correspondence disambiguation protocol

Isolated branch `cursor/seed-wave6-correspondence-disambiguation` from
`10f579d`. Protocol committed before scoring. Do not rescore `10f579d`
or earlier grids. Do not retrain the Wave-5 grammar prior. Track B
coding/LLM stays closed. Do not merge `main`.

Wave 5 showed a supplied mapping reused even structure while greedy
acquired mapping locked `stamp` (0/6). This study isolates
**correspondence learning** with competing bindings, disagreement
probes, public validation, and calibrated ambiguity.

## Equalized probes

Every method receives the same actions and `Wave6Meter`:

1. `READ_*` slot reads (full record)
2. `repeat` of a visited slot at a later time
3. `shuffle` of permitted slots
4. `public_validation` on held-out `epsilon`
5. `private_eval` only after lock / `ambiguous` / `abstain`

## Methods (seeds 0, 1, 2)

1. `greedy_first_fit_mapper` — Wave-5 first low-error lock
2. `random_disambiguation_mapper` — version space + random probes + public gate
3. `strong_fixed_mapping_solver` — fixed `initial + repeat-all + shuffle + validate`
4. `active_disambiguation_mapper_scratch` — disagreement probes, no clauses
5. `active_disambiguation_mapper_plus_clauses` — same probes + frozen Wave-5 clauses

Same candidate bindings, tools, and budgets. Grammar not expanded.

## Categories

1. Stamp/counter traps (`w5_even_add3`, `w5_abs_add4`)
2. Order/echo distractors
3. True alias ambiguity (`result` ≡ `alias`) → `status=ambiguous`
4. OOG `sum` abstain + Wave-2 even retention

```
total = public_env + public_validation + binding_evals
      + disagreement_policy + retrieval + synthesis
```

Private interactions are not in total work and must not affect admission.

## Gates

1. Verifier: `private_eval` never before lock (`valid: true`).
2. Fixed and plus-clauses: 100% mapping and private correctness on
   categories 1–2 (vs 0% greedy); 100% ambiguity, 0 false unique
   claims on category 3. OOG no unique claims. Retention on those two
   methods.
3. Plus-clauses strictly lower total work **and**
   `public_probes + binding_evals` than fixed and scratch on every seed.

## Resources

Symbolic standing-grant CPU. 0 model calls. Frozen debit **0**. Cap
120 s. Do not edit `local_model_runtime.py`.

```sh
PYTHONPATH=src:.deps python3 -m pytest tests/test_seed_wave6_correspondence.py -q
PYTHONPATH=src:.deps python3 scripts/run_wave6_correspondence.py artifacts/seed_wave6_correspondence_disambiguation
PYTHONPATH=src:.deps python3 scripts/verify_wave6_correspondence_disambiguation.py artifacts/seed_wave6_correspondence_disambiguation/seed_wave6_correspondence_disambiguation.json
```
