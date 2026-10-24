# Unfamiliar sub-clause skill work-reduction results

Branch `cursor/seed-unfamiliar-skill-work-reduction` from `f2e8942`.
Protocol `4e57b37`. This results commit is separate.
Artifact hash
`0350a8f122482dda7d33de607d43f409ae27ac06e539261cf5b8f3944dfad2aa`.
Verifier `valid: true` on 72 cells. `f2e8942` and artifact
`6f7437ede1a0b5f582a0b1e71bdf83881fa2067011b0ee902740c20512f532ff`
were not edited. Track B not run. 0 model calls. Frozen debit **0**.
Pilot, not confirmation. Not general learning-to-learn. Not AGI.

## Auditor criterion

Memory does not need the fixed synthesizer to fail. Matching its
accuracy while reducing total acquisition cost is useful transfer.
Whole-mechanism Wave-2 hits stay 0. Sub-clause hits are 12/12.

## Four-way holdout totals (4 mechanisms × 3 seeds)

| Method | Useful | Env | Hyp | Policy | Retrieval | Total work | Sub hits | Whole hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| untrained_policy_no_memory | 12 | 42 | 816 | 0 | 0 | 858 | 0 | 0 |
| source_distilled_fixed_no_memory | 12 | 43 | 865 | 0 | 0 | 908 | 0 | 0 |
| learned_adaptive_policy_memory_cleared | 12 | **21** | 432 | **246** | 0 | 699 | 0 | 0 |
| learned_adaptive_policy_plus_subskill_memory | 12 | **21** | **213** | **246** | 60 | **540** | **12** | **0** |

Reserved retest: all four methods 6/6. Frozen policy env 21 and
policy evals 246 are unchanged from `f2e8942`.

## Gates

| Gate | Result |
| --- | --- |
| 1 Accuracy and reserved-retest parity | **pass** — 12/12 and 6/6 all methods |
| 2 Sub-clause hits > 0, whole-mechanism hits = 0, every seed | **pass** — 4/4 sub hits, 0 whole |
| 3 Memory total work < policy-only, every seed | **pass** — 180 < 233 |

## Per-seed holdout

| Seed | Untrained | Distilled | Cleared policy | + sub-clause memory |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 14 env / 286 | 14 / 296 | 7 / 233 | **7 / 180** (4 sub, 0 whole) |
| 1 | 14 / 286 | 15 / 316 | 7 / 233 | **7 / 180** (4 sub, 0 whole) |
| 2 | 14 / 286 | 14 / 296 | 7 / 233 | **7 / 180** (4 sub, 0 whole) |

Hypothesis evaluations fall from 144 to 71 per seed. Retrieval costs
20. Net saving 53 work units per seed.

## What this does not show

This is not general learning-to-learn, not open-domain coding, and not
Track B. The library is programmer-indexed by exclusive-or family
signatures from verified source acquisitions. A later family without
shared guard/leaf structure can still make sub-clause retrieval miss.
