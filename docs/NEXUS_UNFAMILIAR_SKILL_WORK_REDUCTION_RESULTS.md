# Unfamiliar sub-clause skill work-reduction results

Branch `cursor/seed-unfamiliar-skill-work-reduction` from `f2e8942`.
Protocol `b132bef`. This results commit is separate.
Artifact hash
`a2cc77d66bcd80a3107e25542e8e96c94fea8348dd59b8c6496b3b568c1cabf2`.
Verifier `valid: true` on 72 cells. `f2e8942` and artifact
`6f7437ede1a0b5f582a0b1e71bdf83881fa2067011b0ee902740c20512f532ff`
were not edited. Track B not run. 0 model calls. Frozen debit **0**.
Pilot, not confirmation. Not general learning-to-learn. Not AGI.

## Equation

`total_acquisition_work = env + hyp + policy + distill_cost + retrieval_evals`

Wave-1 `distill_cost` is 28 per seed (84 across three seeds), charged
on the first holdout cell of the memory method.

## Four-way holdout totals (4 mechanisms × 3 seeds)

| Method | Useful | Env | Hyp | Policy | Retrieval | Distill | Total | Sub | Whole |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| untrained_default_policy | 12 | 42 | 816 | 0 | 0 | 0 | 858 | 0 | 0 |
| source_distilled_fixed_order | 12 | 43 | 865 | 0 | 0 | 0 | 908 | 0 | 0 |
| source_learned_adaptive_policy | 12 | **21** | 432 | **246** | 0 | 0 | 699 | 0 | 0 |
| adaptive_policy_plus_compositional_subskills | 12 | **21** | **213** | **246** | 60 | 84 | **624** | **12** | **0** |

Reserved retest: all four methods 6/6.

## Gates

| Gate | Result |
| --- | --- |
| 1 Accuracy and reserved-retest parity | **pass** — 12/12 and 6/6 |
| 2 Sub-skill hits > 0, whole-mechanism hits = 0, every seed | **pass** — 4/4 sub, 0 whole |
| 3 Memory total work < all three baselines, every seed | **pass** — 208 < 233, 286, 296/316 |

## Per-seed holdout

| Seed | Untrained | Distilled | Cleared policy | + subskills (incl. distill 28) |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 14 / 286 | 14 / 296 | 7 / 233 | **7 / 208** (4 sub, 0 whole) |
| 1 | 14 / 286 | 15 / 316 | 7 / 233 | **7 / 208** (4 sub, 0 whole) |
| 2 | 14 / 286 | 14 / 296 | 7 / 233 | **7 / 208** (4 sub, 0 whole) |

## Per-task table

| Seed | Task | Method | Env | Hyp | Pol | Ret | Dist | Tot | Solved | Sub |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 0 | up_hold_pos_plus2 | untrained | 3 | 58 | 0 | 0 | 0 | 61 | yes | 0 |
| 0 | up_hold_twice_plus1 | untrained | 3 | 58 | 0 | 0 | 0 | 61 | yes | 0 |
| 0 | up_hold_neg_gate | untrained | 4 | 78 | 0 | 0 | 0 | 82 | yes | 0 |
| 0 | up_hold_neg_twice | untrained | 4 | 78 | 0 | 0 | 0 | 82 | yes | 0 |
| 0 | up_hold_pos_plus2 | distilled | 5 | 100 | 0 | 0 | 0 | 105 | yes | 0 |
| 0 | up_hold_twice_plus1 | distilled | 5 | 100 | 0 | 0 | 0 | 105 | yes | 0 |
| 0 | up_hold_neg_gate | distilled | 2 | 40 | 0 | 0 | 0 | 42 | yes | 0 |
| 0 | up_hold_neg_twice | distilled | 2 | 42 | 0 | 0 | 0 | 44 | yes | 0 |
| 0 | up_hold_pos_plus2 | learned cleared | 2 | 40 | 22 | 0 | 0 | 64 | yes | 0 |
| 0 | up_hold_twice_plus1 | learned cleared | 1 | 24 | 16 | 0 | 0 | 41 | yes | 0 |
| 0 | up_hold_neg_gate | learned cleared | 2 | 40 | 22 | 0 | 0 | 64 | yes | 0 |
| 0 | up_hold_neg_twice | learned cleared | 2 | 40 | 22 | 0 | 0 | 64 | yes | 0 |
| 0 | up_hold_pos_plus2 | + subskills | 2 | 19 | 22 | 4 | 28 | 75 | yes | 1 |
| 0 | up_hold_twice_plus1 | + subskills | 1 | 8 | 16 | 4 | 0 | 29 | yes | 1 |
| 0 | up_hold_neg_gate | + subskills | 2 | 22 | 22 | 6 | 0 | 52 | yes | 1 |
| 0 | up_hold_neg_twice | + subskills | 2 | 22 | 22 | 6 | 0 | 52 | yes | 1 |
| 0 | up_ret_add1 / if_pos | all four | 1–2 | — | — | — | 0 | — | yes | 0–1 |
| 1 | holdout four × four methods | same pattern as seed 0 except distilled neg_twice 3/64 |  |  |  |  |  |  | yes |  |
| 2 | holdout four × four methods | same pattern as seed 0 |  |  |  |  |  |  | yes |  |

Seeds 1 and 2 match seed 0 on untrained, learned-cleared, and
+subskills cells. Seed 1 distilled `up_hold_neg_twice` is 3 env / 64
total instead of 2 / 44.

Reserved: every method 6/6 useful across seeds.

## What this does not show

This is not general learning-to-learn, not open-ended acquisition
beyond the supplied bank, and not Track B. Distillation and retrieval
are charged. A later family without shared guard/leaf signatures can
still make sub-skill retrieval miss.
