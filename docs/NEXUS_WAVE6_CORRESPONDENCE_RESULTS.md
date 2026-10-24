# Wave-6 correspondence disambiguation results

Branch `cursor/seed-wave6-correspondence-disambiguation` from `10f579d`.
Protocol `aa34924`. This results commit is separate.
Artifact hash
`a88765e9238d10d30a8b236c88115dafcf8b4ba5f651ffd741aa6d1d865fb031`.
Verifier `valid: true` on 120 cells. Historical grids were not
rescored. Track B coding/LLM closed. 0 model calls. Frozen 1.5B
debit **0**. Wall **0.226 s**, classified as symbolic standing-grant
CPU (not the frozen 1.5B ledger). Grammar prior was not retrained.
Pilot, not confirmation. Not general learning-to-learn. Not AGI.

```
total = public_env + public_validation + binding_evals
      + disagreement_policy + retrieval + synthesis
```

Private interactions are excluded from total work and were never
read before lock.

## Mapping correctness

Exact identity+`result` on identifiable tasks; exact `ambiguous` on
Category 3; exact `abstain` on OOG `sum`. Greedy locked `stamp` on
every cell (`24/24`).

| Method | Stamp 1 | Echo 2 | Ident 1+2 | Amb 3 | OOG 4 | Retain | Suite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| greedy_first_fit_mapper | 0/6 | 0/6 | 0/12 | 0/6 | 0/3 | 0/3 | 0/24 |
| random_disambiguation_mapper | 6/6 | 6/6 | 12/12 | 6/6 | 3/3 | 3/3 | 24/24 |
| strong_fixed_mapping_solver | 6/6 | 6/6 | **12/12** | **6/6** | 3/3 | 3/3 | 24/24 |
| active_disambiguation_mapper_scratch | 6/6 | 6/6 | 12/12 | 6/6 | 3/3 | 3/3 | 24/24 |
| active_disambiguation_mapper_plus_clauses | 6/6 | 6/6 | **12/12** | **6/6** | 3/3 | 3/3 | 24/24 |

False `stamp` locks: greedy 24; all other methods 0.

## Private task correctness

Evaluated only after lock on the held-out private stream.

| Method | Stamp 1 | Echo 2 | Ident 1+2 | Amb 3 | OOG 4 | Retain | Suite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| greedy_first_fit_mapper | 0/6 | 0/6 | 0/12 | 0/6 | 0/3 | 0/3 | 0/24 |
| random_disambiguation_mapper | 6/6 | 6/6 | 12/12 | 6/6 | 3/3 | 3/3 | 24/24 |
| strong_fixed_mapping_solver | 6/6 | 6/6 | **12/12** | 6/6 | 3/3 | **3/3** | 24/24 |
| active_disambiguation_mapper_scratch | 6/6 | 6/6 | 12/12 | 6/6 | 3/3 | 3/3 | 24/24 |
| active_disambiguation_mapper_plus_clauses | 6/6 | 6/6 | **12/12** | 6/6 | 3/3 | **3/3** | 24/24 |

## Ambiguity reporting (Category 3)

`result` ≡ `alias` on every public record. The only correct status is
`ambiguous`.

| Method | Ambiguous declared | False unique | Mapping correct |
| --- | ---: | ---: | ---: |
| greedy_first_fit_mapper | 0/6 | **6** | 0/6 |
| random_disambiguation_mapper | 6/6 | 0 | 6/6 |
| strong_fixed_mapping_solver | **6/6** | **0** | 6/6 |
| active_disambiguation_mapper_scratch | 6/6 | 0 | 6/6 |
| active_disambiguation_mapper_plus_clauses | **6/6** | **0** | 6/6 |

## Total acquisition cost

| Method | Suite total | public+binding | Stamp | Echo | Amb | OOG | Retain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| greedy_first_fit_mapper | 1044 | 708 | 252 | 252 | 288 | 126 | 126 |
| random_disambiguation_mapper | 10214 | 1043 | 3906 | 3887 | 335 | 141 | 1945 |
| strong_fixed_mapping_solver | 10299 | 1269 | 3924 | 3906 | 360 | 147 | 1962 |
| active_disambiguation_mapper_scratch | 10326 | 1074 | 3918 | 3951 | 354 | 144 | 1959 |
| active_disambiguation_mapper_plus_clauses | **9714** | **597** | 3792 | 3732 | 252 | 42 | 1896 |

Per-seed suite (Gate 3: plus-clauses strictly below fixed and scratch):

| Seed | Plus total / pb | Fixed total / pb | Scratch total / pb |
| ---: | ---: | ---: | ---: |
| 0 | **3238 / 199** | 3433 / 423 | 3442 / 358 |
| 1 | **3238 / 199** | 3433 / 423 | 3442 / 358 |
| 2 | **3238 / 199** | 3433 / 423 | 3442 / 358 |

Greedy is cheaper because it commits on the first low-error column
and never validates; that column is `stamp` (`0/12` identifiable).

## Gates

| Gate | Result |
| --- | --- |
| 1 Private isolation | **pass** (verifier reconstructs; tamper rejected) |
| 2 Mapping + private + ambiguity | **pass** (fixed and plus-clauses 12/12 ident, 6/6 amb, 0 false unique; greedy 0/12) |
| 3 Efficiency vs fixed and scratch | **pass** on seeds 0–2 |

Conclusion: competing bindings plus a public validation gate recover
the identity+`result` correspondence that Wave-5 greedy mapping lost
to `stamp`. Transferred Wave-5 clauses reduce binding evaluations
(411 vs 885 / 906) without retraining the grammar prior. Random
disambiguation also reached 24/24 once the version space and
validation gate were shared; the active+clauses advantage here is
cost, not unique correctness. Not general learning-to-learn.
Retention 3/3 is not universally zero forgetting.

## Three next steps

1. Keep the identity correspondence privileged only when it is the
   named slot encoding; do not treat leftover 4-point aliasings of
   `result` as Category-3 ambiguity.
2. Test a correspondence family whose true field is not `result`, so
   preferring `result` cannot paper over a different binding.
3. Do not retrain the Wave-5 prior on this interface; mapping and
   grammar remain separate measurements.
