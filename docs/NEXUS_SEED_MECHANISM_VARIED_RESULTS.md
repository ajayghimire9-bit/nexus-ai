# Varied-probe challenge — development results

Branch `cursor/seed-mechanism-varied-probes`.
Protocol `bf7ee42`. This results commit is separate.
Base `5575762`. Artifact hash
`79ffc21ac69e0507a08288cda8e74c90f7eebb23dd2a9be7c3fb1ad5fdb30467`.
Verifier `valid: true` on 147 cells; opened C/D/E/mismatch IDs
rejected. Prior grids were not rescored. Pilot, not confirmation.
Not learning-to-learn. Not AGI.

## Missing baseline

Diagnostic-plus-MEASURE is now a fixed method. On a singleton it
charges MEASURE at oracle cost 3 before identifying. Cost-aware
information gain maximises language split per charged cost and uses a
cheap confirmation probe. It is not learned.

## Competence

All three training seeds passed: 7/7 success, 6 correct IDs, 1 correct
unresolved. Assessment opened.

## Assessment (7 tasks × 3 seeds)

| Method | Correct solutions | False ID | Inconsistency | Uncertainty | Oracle | Ordinary MEASURE | Ordinary oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| trained | 9 | 4 | 8 | 0 | 73 | 5 / 9 | 3.78 |
| reset | 3 | 0 | 3 | 15 | 59 | 7 / 9 | 4.33 |
| shuffled | 0 | 0 | 3 | 18 | 32 | 3 / 9 | 1.33 |
| diagnostic | 9 | 9 | 3 | 0 | 63 | 0 / 9 | 2.67 |
| **diagnostic+MEASURE** | **9** | **3** | **9** | 0 | 99 | 9 / 9 | 4.67 |
| cost-aware IG | 9 | 7 | 5 | 0 | **48** | 0 / 9 | **2.56** |
| information gain | 9 | 5 | 7 | 0 | 65 | 5 / 9 | 3.67 |

By role:

- MEASURE-exposed `id_exact0`: diagnostic and cost-aware IG name
  `noisy_add1` on all three seeds. Diagnostic+MEASURE and trained empty
  the language after MEASURE. Vanilla IG misses one seed.
- Sequence-exposed: diagnostic+MEASURE empties all six. Trained misses
  one `plus_prev` seed (`ACT_2`, `MEASURE`, `RESET`, identify `sum`).
  Diagnostic names `noisy_add1` on all three `mod2` seeds because it
  repeats `ACT_1` instead of taking `ACT_1, ACT_0, ACT_2`.
- Twins: every identifying method names `add1` on all three seeds.
  Nobody reports unresolved uncertainty. A catalogue confirmation is
  still not independent evidence.
- Ordinary: all identifying methods 9/9. Diagnostic and cost-aware IG
  never MEASURE. Diagnostic+MEASURE always does. Trained MEASURES 5/9,
  matching vanilla IG, so some checking is unnecessary.

Reset and shuffle collapse ordinary identification, so the weights are
used. They are not a stronger baseline.

## Costs

0.212 s wall, 0 model calls, frozen debit **0**. Product chat unused.
Metal unused.

## Verdict

**negative** versus the strongest fixed method,
`fixed_diagnostic_measure`. Same 9/9 ordinary solutions, 4 versus 3
false identifications, 8 versus 9 demonstrated inconsistencies. The
previous mismatch “advantage” was the untested MEASURE habit. Giving
that confirmation to the diagnostic removes the gap and shows the extra
ordinary-task cost.

Do not rescore this grid, `5575762`, `ff26a18`, or `92d6f19`. Ranking
stays paused. Learning-to-learn remains unestablished.
