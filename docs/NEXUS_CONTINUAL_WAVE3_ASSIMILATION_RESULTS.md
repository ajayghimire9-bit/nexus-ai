# Continual Wave-3 assimilation results

Branch `cursor/seed-continual-wave3-assimilation` from `0d4596e`.
Protocol `79c53a5`. This results commit is separate.
Artifact hash
`ad9b569c4910c4084a3faa60625bf805bf175e472c083abcb920eb3d5fe933d6`.
Verifier `valid: true` on 156 cells. `0d4596e`, `6e0df3a`, and
`f2e8942` artifacts were not edited. Track B not run. 0 model calls.
Frozen debit **0**. Pilot, not confirmation. Not general
learning-to-learn. Not AGI.

Wave 2 rediscovers the out-of-bank suite, including Type B
`even_add2`. Continual assimilates that even guard and ACT_0/ACT_1
parity priority. Wave 3 tests unseen parity compositions plus true
out-of-grammar `count`/`delay`, then reserved Wave-1/Wave-2 retests.

```
total_acquisition_work = env + confirmatory + bank_hyp + policy
                       + distill + retrieval + residual_synthesis
```

Wave-3 continual totals include Wave-1 distill 26 + Wave-2 even
assimilation 4 (`30` on the first expressible cell per seed). Frozen
is charged Wave-1 distill 26 only.

## Wave-3 expressible totals (3 mechanisms × 3 seeds)

| Method | Useful | Env | Confirm | Bank hyp | Policy | Retr | Distill | Synth | env+synth | **Total** | Sub |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| untrained_open_grammar | 9 | 39 | 9 | 531 | 0 | 0 | 0 | 6267 | 6306 | **6846** | 0 |
| learned_policy_open_grammar_cleared | 9 | 27 | 9 | 225 | 144 | 0 | 0 | 6108 | 6135 | **6513** | 0 |
| wave1_frozen_abductive | 9 | 27 | 9 | 225 | 144 | 18 | 78 | 6612 | 6639 | **7113** | 0 |
| continual_assimilating_nexus | 9 | 21 | 12 | 255 | 36 | 9 | 90 | **2418** | **2439** | **2841** | **9** |

Per seed, continual **947** vs frozen 2371 / learned-open 2171 / untrained 2282, and env+synth **813** vs 2213 / 2045 / 2102.

## Wave-3 out-of-grammar abstention (2 tasks × 3 seeds)

| Method | Useful | Abstain | FP |
| --- | ---: | ---: | ---: |
| untrained_open_grammar | 0 | **6** | **0** |
| learned_policy_open_grammar_cleared | 0 | **6** | **0** |
| wave1_frozen_abductive | 0 | **6** | **0** |
| continual_assimilating_nexus | 0 | **6** | **0** |

## Wave-2 totals (4 mechanisms × 3 seeds)

Continual and the Wave-1 freeze match here: even is discovered last and is not yet available for the three Type A cells.

| Method | Useful | Env | Confirm | Synth | **Total** | Sub |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| untrained_open_grammar | 12 | 54 | 12 | 8391 | **9144** | 0 |
| learned_policy_open_grammar_cleared | 12 | 36 | 12 | 8421 | **8898** | 0 |
| wave1_frozen_abductive | 12 | 36 | 12 | 7095 | **7596** | 18 |
| continual_assimilating_nexus | 12 | 36 | 12 | 7095 | **7596** | 18 |

Per seed: untrained 3048, learned-open 2966, frozen/continual 2532.

## Retention after Wave 3 (Wave-1 + Wave-2, 4 tasks × 3 seeds)

All four methods **12/12**. Continual reuses the assimilated even residual on `even_add2` (280 vs frozen Type B 844 per seed).

## Gates

| Gate | Result |
| --- | --- |
| 1 True out-of-grammar calibrated abstention | **pass** — 6/6 abstain, 0 useful, 0 FP every method |
| 2 Wave-2 experience accelerates Wave-3 | **pass** — continual 947 < 2171 / 2282 / 2371 and env+synth 813 < 2045 / 2102 / 2213 every seed |
| 3 Multi-wave retention without forgetting | **pass** — 4/4 reserved Wave-1 and Wave-2 retests every method and seed |

## Per-seed Wave-3 expressible

| Seed | Untrained | Learned open | Wave-1 freeze | Continual (distill 30) |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 13 / 2282 | 9 / 2171 | 9 / 2371 | **7 / 947** (3 sub) |
| 1 | 13 / 2282 | 9 / 2171 | 9 / 2371 | **7 / 947** |
| 2 | 13 / 2282 | 9 / 2171 | 9 / 2371 | **7 / 947** |

## Per-task Wave-2 (seeds 0–2 identical)

| Task | Kind | Untrained | Learned open | Freeze / continual |
| --- | --- | ---: | ---: | ---: |
| w2a_hold_pos_plus3 | Type A | 5+1 / 796 | 3+1 / 696 | 3+1 / **526** (sub 2) |
| w2a_hold_pos_mul3 | Type A | 5+1 / 815 | 3+1 / 786 | 3+1 / **609** (sub 2) |
| w2a_hold_neg_add1 | Type A | 5+1 / 745 | 3+1 / 699 | 3+1 / **553** (sub 2) |
| w2a_hold_even_add2 | Type B | 3+1 / 692 | 3+1 / 785 | 3+1 / 844 (sub **0**, fallback) |

## Per-task Wave-3 expressible (seeds 0–2 identical)

| Task | Untrained | Learned open | Wave-1 freeze | Continual |
| --- | ---: | ---: | ---: | ---: |
| w3a_hold_even_mul3 | 3+1 / 713 | 3+1 / 785 | 3+1 / 872 (Type B) | 3+1 / **357** (Type A, sub 1, distill 30) |
| w3a_hold_even_sub1 | 5+1 / 722 | 3+1 / 693 | 3+1 / 751 (Type B) | 2+1 / **275** (Type A, sub 1) |
| w3a_hold_odd_plus2 | 5+1 / 847 | 3+1 / 693 | 3+1 / 748 (Type B) | 2+2 / **315** (Type A, sub 1) |

## Per-task Wave-3 out-of-grammar (seeds 0–2 identical)

| Task | Untrained | Learned open | Wave-1 freeze | Continual |
| --- | ---: | ---: | ---: | ---: |
| w3a_hold_count | 3+0 / 691 abstain | 2+2 / 690 abstain | 2+2 / 743 abstain | 3+0 / 756 abstain |
| w3a_hold_delay | 5+0 / 766 abstain | 3+0 / 692 abstain | 3+0 / 767 abstain | 3+1 / 403 abstain |

`env+c` written as diagnostic + confirmatory. False positives are 0.

## What this does not show

This is not general learning-to-learn, not open-domain coding, and not
Track B. Assimilation helps the next problem only when the new family
reuses the stored even residual. A later novel guard still falls back
to open grammar. Out-of-grammar abstention is grammar-exhaustion plus
confirmatory falsification, not an open-world unknown detector.
